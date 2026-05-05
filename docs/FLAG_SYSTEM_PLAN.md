# Flag + Marked-for-Follow-Up MVP — Implementation Plan

This plan covers the first vertical slice of the gameplay loop described in
[`GAMEPLAY_DESIGN_NOTES.md`](./GAMEPLAY_DESIGN_NOTES.md). It builds the
per-field flag mechanic + the marked-for-follow-up review panel, *without*
the chat backend, probe sending, probe budget, or game-over machinery
those notes also describe.

The slice exercises the load-bearing pieces: per-field flag data model,
right-click context menu, sidebar tool architecture, JRPG-style review
surface. Later sprints layer probe sending, multi-stage submissions, and
the rest of the gameplay loop on top of this foundation without rework.

---

## Scope

**In scope:**

- Right-click any form field → custom context menu offers "Flag for
  follow-up" with a submenu of contexts (Missing / Confirm / Other).
  "Other" requires free-form text.
- Already-flagged fields offer "Unflag" or "Change context" instead.
- Visual indicator (small colored dot) on flagged fields.
- New **Flags** icon in the titlebar next to the chat-toggle, with a
  count badge.
- Click Flags icon → right-column sidebar tool opens, replacing chat
  if chat was open. Mutually exclusive with chat (the existing chat
  pane and the new flags pane share right-column real estate).
- Flags panel content: list of flags, JRPG-style nested navigation
  (per-row submenu for set-context / set-action / dismiss), batch
  actions at the bottom (Clear all; "Send all" placeholder button).
- Per-flag dismiss removes the flag.
- All form fields are flaggable, including checkboxes (per-checkbox
  individually for MVP; trio-aware probe composition is later work).

**Out of scope (deliberately deferred):**

- Chat backend / probe sending / probe responses.
- Probe budget, tone scaling, reaffirming-redirected-to-docs, game-over
  state. The action picker stores the player's choice as data on each
  flag but does not actually send anything.
- Multi-stage submission tracking. Flags don't propagate between
  intake / verify / prep stages (those stages don't exist yet anyway).
- Server-side persistence. Flag state lives in `sessionStorage`,
  scoped per `scenario_id`. Lost on hard refresh from a different
  session. Server-side case-state structure is its own future sprint.
- Grading impact. Submitting a form with unresolved flags neither
  raises nor lowers the score; flags are purely a player workspace
  affordance.
- Concept tagging on flags (which concepts are involved). Flags are
  per-field; concept attribution comes when the concept catalog work
  lands.
- Auto-tailored probe text based on detected discrepancies. MVP uses
  generic per-context probe templates only when probes finally send;
  for this slice probes don't send.
- Trio-aware checkbox flagging. Each checkbox is independently
  flaggable.

---

## Decisions locked in

These are the load-bearing decisions the discussion converged on, listed
here so future readers (and tests) can refer back without re-deriving.

1. **Three contexts (+ free-form):** Missing / Confirm / Other.
   Confirm covers verify, disambiguate, and suspect-wrong cognitive
   states; the system handles the analytical distinction internally
   when probes eventually send. Other requires text.
2. **Four actions:** Email / Chat / Ask Vida / Other. Stored as data
   on the flag for MVP; not connected to send pipelines yet.
3. **Mark first, decide action later.** Context is required at flag
   time (right-click submenu); action is set later from the review
   panel. Flag without action is a valid state (status: "draft").
4. **Per-field granularity.** Marks are per-field; checkboxes are
   per-checkbox, not per-trio. Trio-aware behavior is a v2 add.
5. **Flag's data shape:**
   ```
   {
     field_id: "income.wages",
     context: "Missing" | "Confirm" | "Other",
     context_text: string | null,        // required when context = Other
     action: "Email" | "Chat" | "AskVida" | "Other" | null,
     status: "draft" | "ready" | "sent" | "answered" | "applied" | "dismissed",
     created_at: number,                 // monotonic counter, for ordering
   }
   ```
   `status` defaults to "draft" (just flagged, no action yet); becomes
   "ready" once the player picks an action; further states are placeholders
   for when probe sending lands.
6. **Sidebar tools are mutually exclusive.** New layout-state field
   `sidebarTool: "chat" | "flags" | null`. Replaces (or supersedes)
   the boolean `chatOpen`. Chat-toggle and Flags-toggle are sibling
   buttons in the titlebar; each sets `sidebarTool` to its own value
   on click, or to `null` if already active (toggle off).
7. **State persistence: sessionStorage, client-side only.** One key
   per scenario_id. The full case-state structure (server-persisted
   across pages, players, stages) is a separate planning effort.
8. **Visual indicator: small colored dot in the field's top-right
   corner.** Color is the existing focus-state orange
   (`var(--color-accent)` if present, otherwise hardcoded). Position:
   absolute, anchored to the flagged input or its label.

---

## Architectural commitments

Following the patterns the existing layout-reducer / layout-render code
established:

- **Pure reducer for flag state.** A new `api/static/js/flags-reducer.js`
  module exports `initialState()` and `reduce(state, action)`, just like
  `layout-reducer.js`. No DOM, no globals, independently testable.
- **Renderer is the only DOM mutator.** Flag-state changes flow through
  one render path that updates the visual indicators on form fields and
  the flags panel content.
- **Event delegation, not inline handlers.** One `contextmenu` listener
  on the form pane; one `click` listener at document root catching the
  context menu's data-flag-action verbs. Same pattern as the layout
  system's `data-layout-action` dispatch.
- **Dispatch through actions.** Flag mutations happen via `dispatch({type, ...})`,
  not direct mutation. Action types: `FLAG_FIELD`, `UNFLAG_FIELD`,
  `SET_CONTEXT`, `SET_ACTION`, `CLEAR_ALL`.
- **Persistence on every state change.** sessionStorage write happens
  at dispatch boundary, not from individual action handlers. One write,
  one place.
- **No DOM nodes in state.** Field IDs only; resolve to DOM at render time.

---

## Phased plan

Each phase commits separately with the test suite green; matches the
cadence of the doc-switcher and single-scroll-form sprints.

### Phase A — Plan + decisions (this doc)

### Phase B — Flag state module

In `api/static/js/flags-reducer.js`:

- `initialState()` returns `{ flags: {}, tick: 0 }` (`flags` is a map
  from `field_id` to flag object; `tick` is a monotonic counter for
  `created_at` stamps).
- `reduce(state, action)` handles `FLAG_FIELD`, `UNFLAG_FIELD`,
  `SET_CONTEXT`, `SET_ACTION`, `CLEAR_ALL`.
- Pure function. No DOM. Independently testable via node.

In `api/static/js/flags-render.js` (new):

- One module-level `state` reference + `dispatch(action)` function.
- `applyState()` is the single render entry point — updates field
  indicators and (when the panel is open) the flag list.
- sessionStorage hydration on init; save on every dispatch.
- Storage key: `flags-{scenario_id}`.

### Phase C — Right-click context menu + visual indicator

In `api/static/js/encounter.js` (currently a stub):

- Bind `contextmenu` listener on `#form-pane`.
- For form-input targets, prevent the browser's default menu and
  render a custom menu at the click position.
- Menu items dispatch flag actions:
  - Unflagged field: "Flag for follow-up" → submenu (Missing /
    Confirm / Other → text prompt).
  - Flagged field: "Change context" / "Unflag".
- Reuse the existing `api/static/styles/contextmenu.css` skeleton.

In `api/static/styles/sheet.css` (or a new `flags.css`):

- `.f13c-flagged` modifier class on form fields (or wrapper).
- Small colored dot positioned absolute top-right of the flagged
  control. ~7px, accent color, navy ring (matches the cached-doc
  indicator on pane 2 banner — visual rhyme).

The renderer adds/removes `.f13c-flagged` based on flag state on every
`applyState` call.

### Phase D — Flags sidebar tool (icon + skeleton)

In `api/templates/encounter.html`:

- Add Flags icon button next to chat-toggle in titlebar:
  ```
  <button class="layout-btn" id="flags-toggle-btn" type="button"
          data-layout-action="toggle-flags"
          aria-pressed="false" aria-label="Toggle flags">
      <svg>...</svg>  <!-- flag icon -->
      <span class="layout-btn-badge" id="flags-count-badge" hidden></span>
  </button>
  ```
- The right-column container previously named `#chat-pane` becomes
  `#sidebar-pane` (or stays `#chat-pane` for back-compat with the
  existing CSS selectors and tests, with the flags panel as a sibling
  inside).

In `api/static/js/layout-reducer.js`:

- Replace `chatOpen: boolean` with `sidebarTool: "chat" | "flags" | null`.
  Or add `sidebarTool` alongside `chatOpen` for back-compat — pick one
  in the implementation. Lean: replace, accept the migration cost.
- New action `TOGGLE_SIDEBAR_TOOL` with `tool` arg.
- Existing `TOGGLE_CHAT` becomes a thin wrapper that dispatches
  `TOGGLE_SIDEBAR_TOOL` with `tool: "chat"`, keeping the chat-toggle
  button working without churning the existing test surface.

In `api/static/styles/layout.css`:

- Update `body[data-chat]` selectors to `body[data-sidebar]` (with
  values `chat` / `flags` / `closed`).
- Add empty Flags panel container styling (full-height, scrollable).

The Flags panel renders empty content for this phase — Phase E fills it.

### Phase E — Flags review panel content

In `api/static/js/flags-render.js`:

- Render flag list when `sidebarTool === "flags"`. Each row:
  - Field label (human-readable; need a label registry or just the
    field name for now).
  - Context badge (Missing / Confirm / Other).
  - Action badge (Email / Chat / AskVida / Other / —).
  - Click row → expand into per-row submenu (set context / set action
    / dismiss).
- JRPG-style nested navigation: clicking a row replaces the list with
  a detail view; "Back" returns to the list. Or slide-in animation if
  we want to be fancy. Lean: replacement, not slide.
- Batch actions footer:
  - "Clear all" — dispatches `CLEAR_ALL` (asks for confirm).
  - "Send all" — placeholder button, stub action dispatch (no real
    sending). Visible but disabled in MVP, or just a no-op that logs
    a console message.
- Empty state: friendly message when no flags exist.

In `api/static/styles/flags.css` (new):

- Panel layout, list rows, badges, submenu styling.
- Hover / focus states.

### Phase F — Tests

A new `tests/test_flag_system_render.py`:

- Asserts the Flags icon renders in the titlebar with the toggle
  attribute.
- Asserts `#sidebar-pane` (or whatever we call it) is present.
- Asserts the chat-toggle still works (smoke).

Reducer tests in node (or a new test file pattern if we want them in
pytest via subprocess) cover:

- FLAG_FIELD adds a flag with the right context.
- UNFLAG_FIELD removes the flag.
- SET_CONTEXT / SET_ACTION mutate without removing.
- CLEAR_ALL resets to empty.
- State serialization round-trips through JSON cleanly.

End-to-end isn't really testable without a JS test harness, which we
don't have. Manual verification (Phase G) covers the integrated flow.

### Phase G — Manual browser verification

After Phase F lands and tests pass:

- Generate a scenario, right-click a form field, flag it with each
  context. Confirm the visual indicator appears.
- Open the Flags icon; confirm the panel shows the flag with correct
  badges.
- Switch action via per-row submenu; confirm the badge updates.
- Dismiss a flag; confirm it disappears from list and indicator clears.
- Hard refresh (same session); confirm flags persist via sessionStorage.
- Open chat; confirm Flags panel closes (mutual exclusion).
- Open Flags; confirm chat closes.
- Right-click a checkbox; confirm same affordance works.
- Check count badge updates as flags are added/removed.

---

## Risks + mitigations

- **Right-click on macOS Safari.** Trackpad two-finger-tap fires
  `contextmenu` events, but some users disable this in OS settings.
  Mitigation: keep right-click as the primary, but add a small flag
  icon on hover (or via a per-field secondary affordance) as a v2
  fallback. Defer for MVP.
- **Field IDs vs human labels.** The flag list should show
  human-readable field names ("Filer first name") not raw field IDs
  ("filer.first_name"). Need a label registry. Options:
  1. Hardcode a mapping in JS for MVP — annoying but tractable.
  2. Generate from the form HTML (read each field's preceding label
     element). More robust but DOM-dependent.
  3. Just show the raw field ID for MVP.
  Lean: #3 for the prototype (raw IDs), upgrade to #2 when polishing.
- **sessionStorage size limits.** Flags map could grow large for
  scenarios with many flags + long Other-context text. Browsers
  typically allow 5–10 MB per origin; flag state will be well under
  that. Not a real risk but worth noting.
- **Layout-reducer migration churn.** Replacing `chatOpen` with
  `sidebarTool` touches the layout-reducer and a few tests. Doable
  cleanly but it's not a one-line change. Worth one careful
  commit.

---

## Sequencing

| Phase | What | Tests | Commit |
|-------|------|-------|--------|
| A | Plan doc | — | this commit |
| B | flags-reducer + flags-render scaffolding + sessionStorage | reducer unit smoke | one commit |
| C | Right-click context menu + flag indicator | — | one commit |
| D | Flags sidebar tool icon + layout-reducer migration | render assertion | one commit |
| E | Flags panel content + per-row submenu + batch actions | — | one commit |
| F | Test cleanup if needed | full suite green | (folded into earlier phases if small) |
| G | Manual browser verification | — | sign-off, no commit |

Each phase commit pushes to the working branch; test suite stays green
end-to-end. Mirrors the cadence of recent sprints.

---

## What this enables (after)

- The case-state structure has its first concrete user. When server-
  side persistence + multi-stage tracking land, flags graduate from
  client-only sessionStorage to first-class state on the case object.
- The chat backend, when built, plugs into the existing flag actions
  — picking "Email" or "Chat" on a flag eventually routes to the
  probe-send pipeline. The data model already carries the action;
  the pipeline just connects to it.
- Probe budget, tone scaling, and game-over land later as additions
  to the send pipeline; the flag mechanic itself doesn't change.
- Verify mode reuses the same flag mechanic. A verifier flagging a
  field they suspect is wrong creates the same kind of flag, just
  in a different scenario stage.
- The right-click context menu becomes the entry point for any future
  per-field affordance (jump to source document, view related
  interview-note, mark as concept-of-interest, etc.) — the menu
  framework is reusable.

---

## Marked Panel Chain Redesign (post-MVP, in progress)

The original MVP shipped the marked panel as a JRPG-style nested
menu (per-row drilldown for set-context / set-action / dismiss).
That UI was retired pending a redesign of the follow-up workflow.
The replacement is a **chain-link sentence builder** — each row in
the marked panel composes one follow-up action as a chain of
clickable pills.

### Row structure

Each marked row is a single sentence:

    [field] [verb ▾] from [target ▾] via [channel ▾] [Confirm | ▾]

- **field** — the flagged field id, immutable display
- **verb ▾** — `Request Information` | `Request Confirmation`
  (extensible; more verbs added as the workflow grows)
- **target ▾** — recipient pulled from the scenario's chat contact
  list. MVP set: `Vida` (senior preparer) and `Client`. Future
  scenarios may add external contacts (employer for a missing W-2,
  bank for a 1099-INT, etc.). Scenario-driven, not universal.
- **channel ▾** — `Email` | `Message`
- **Confirm | ▾** — split button. Primary action is Confirm
  (toggle); dropdown carries `Execute` and `Discard`.

The "from / via" connector words are conceptual — the sentence is
read as a sentence but the words are decorative. The schema isn't
strictly grammatical (e.g. "Request Confirmation from Vida via
Message" is fine even though English would prefer "Ask Vida to
confirm…"). Trying to enforce perfect grammar isn't worth the
state-machine complexity.

### Status lifecycle + archive split

State is split into two collections:

- **`flags: { [field_id]: ActiveFlag }`** — only `draft` + `ready`
  rows live here. The form-side dot + `.f13c-flagged` class read
  from this map, so once a flag fires, the field is automatically
  un-flagged on the form (the player can re-flag it as a fresh
  entry without losing the archived history).
- **`archive: [SentFlag, ...]`** — append-only log of fired actions,
  ordered by `sent_at` tick. Immutable. Re-flagging a previously-
  sent field creates a new active entry; the archived entry stays
  in the panel as history. Only a scenario restart / abandon
  clears the archive.

Status values:

- **draft** — chain incomplete (any pill at "No <thing>") OR
  Confirm not toggled. Send all ignores draft rows.
- **ready** — chain complete and Confirm toggled on. Picked up by
  Send all on next batch fire.
- **in_progress** — fired; flavor state, ~2-3 seconds, then
  auto-transitions to sent. Lives in `flags` for the duration of
  the animation, then moves to `archive` (Phase 3 of the
  redesign — Phase 1 jumps directly active → archive).
- **sent** — only ever in the `archive` collection. Read-only
  display. Click jumps to the associated chat-log / email entry
  (placeholder hook until the log is wired).

### Confirm semantics

Confirm is the multi-select mechanism. Toggling Confirm on a row
moves it to `ready` (eligible for Send all); toggling off returns
to `draft`. No separate checkboxes, no "select all" — the toggled
set IS the batch. Confirm is disabled until the chain is complete
(all three pills set).

### Split-button dropdown

The Confirm split button's dropdown menu carries two one-off
actions:

- **Execute** — fires this row immediately, bypassing the Send all
  batch. Only enabled when the chain is complete. Transitions to
  `in_progress` then `sent`.
- **Discard** — removes the flag entirely. Functionally identical
  to right-click → Unflag; one reducer action (`UNFLAG_FIELD`),
  two entry points.

### List ordering

Active rows (`draft` + `ready` + `in_progress`) sit at the top in
flag-order (newest at the top of the active set). A divider
separates the active section from the archived (`sent`) section,
which lives below the fold and lists rows in reverse-send order.

When a new flag is created mid-session, it inserts at the top of
the active section so the player sees it immediately.

### Pill option lists (extensibility)

Each pill's option list is a config-style array in
`flags-reducer.js`, not a hard-coded enum. Adding a new verb /
target / channel is a one-file edit. Targets are scenario-driven —
loaded from the scenario's contact list rather than a global
enum.

### Phasing

Implementation breakdown for the chain-link redesign:

1. **Reducer + status field** — extend the flag model with
   `verb` / `target` / `channel` / `status`; new actions
   (`SET_VERB` / `SET_TARGET` / `SET_CHANNEL` / `TOGGLE_CONFIRM` /
   `EXECUTE_FLAG` / `SEND_ALL`). Update right-click menu to set
   verb instead of legacy context. **Phase 1 deliverable: a
   clickable chain in the marked panel.**
2. **Active / archived partition + list ordering** — divider,
   newest-on-top within active.
3. **Execute → in_progress → sent transition** — flavor delay,
   visual states.
4. **Click-to-log on sent rows** — placeholder hook; wires up
   when the chat-log / email log lands.
5. **Send all wiring + scenario-driven contact list** — pull
   targets from the scenario rather than a hard-coded list; sweep
   ready rows in batch.
