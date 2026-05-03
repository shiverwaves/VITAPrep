# 13614-C Page 1 Integration + Multi-Pane Layout — Implementation Plan

This plan covers two intertwined pieces of work that land together as the
Encounter UI's core MVP:

1. Wire the new Page 1 mockup (`docs/mockups/13614c_page1.html`) into the
   scenario flow so a generated scenario pre-fills the form on load.
2. Replace the current single-pane Encounter view with a flexible multi-pane
   workspace (form + document panes + chat).

This document sits alongside [`ENCOUNTER_UI_PLAN.md`](./ENCOUNTER_UI_PLAN.md),
which describes the broader Encounter UI redesign (mode rename, base
templates, home screen, etc.). That doc is the architectural frame; this doc
is a tactical implementation plan for the specific sprint that brings the
new form template online. Where the two overlap (Jinja2 templates, vanilla
JS choice, document fragment loading), this doc defers to the architectural
decisions in `ENCOUNTER_UI_PLAN.md`.

---

## Decisions made

These three load-bearing decisions were made before this plan was written.
Everything below assumes them.

1. **Rename `form_fields.py` constants to the `filer.*` namespace; write a
   one-shot migration script that re-runs the populator over stored
   scenarios to regenerate `ground_truth`.** No alias layer. Pre-product is
   the right time to absorb the migration cost; alias layers compound as
   technical debt that every future reader has to learn.

2. **Vanilla JS for the layout system, with explicit architectural
   commitments that keep a future React migration mechanical (not
   greenfield).** Vanilla doesn't preclude migration if the code is written
   carefully; the cost of the build step now is real and immediate, and the
   deferred items (probe interaction, Vida coach scripts, Verify-mode
   per-field verbs) are gated on preconditions that are themselves months of
   work.

3. **Score three of the five volunteer columns
   (`vol_income_under`, `vol_support`, `vol_home_cost`); leave
   `vol_qc_other` and `vol_self_support` visibly marked as "not graded in
   this version"** — both in the form UI and in the result page. Silent
   passes on hard-to-grade fields produce a wrong mental model in the
   player ("I got it right" when the grader didn't actually check).

A meta-principle behind all three: prefer migrations and explicit
limitations over hidden complexity. Each decision trades short-term effort
for long-term clarity.

---

## Architectural commitments for Part 2

These are the patterns Part 2 must follow so vanilla → React (or any other
framework) is mechanical translation rather than rewrite. They cost nothing
extra to follow up front:

- **Reducer is a pure function in its own file**
  (`api/static/js/layout-reducer.js`). Takes `(state, action) → newState`.
  No DOM access, no `document` references, no side effects. Independently
  testable.
- **Pane renderers are pure template functions.**
  `renderDocPane(paneIdx, docId, allDocs) → htmlString`. Take data, return
  string.
- **One render entry point.** `applyState(newState)` is the only function
  that touches the DOM. Everything else dispatches actions.
- **State lives in a single closed-over object** with a `dispatch` function.
  Not on `window`, not in DOM `data-*` attributes, not in `sessionStorage`
  directly (sessionStorage is a *sync target*, not source of truth).
- **Event delegation, not inline handlers.** One listener on `#workspace`,
  dispatch on `event.target.dataset.action`. Makes pane DOM disposable
  without leaking listeners; matches React's synthetic event model.
- **No DOM nodes stored in state.** Only IDs, indices, doc keys.
  `getElementById` at render time. (DOM refs in state are the single biggest
  blocker to a future migration.)

---

## Part 1 — Form integration

### Phase 1A: Model extensions (additive, default-safe)

**File:** `generator/models.py`

Add to `Person`:
- `us_citizen: bool = True`
- `on_visa: bool = False`
- `legally_blind: bool = False`
- `has_ippin: bool = False`
- `marital_history: str = ""`
  (`"never" | "divorced" | "separated" | "widowed" | "married"`)

Add to `Household`:
- `lived_in_two_states: bool = False`
- `spouses_lived_apart_h2: bool = False`
- `divorce_date: Optional[date] = None`
- `separation_date: Optional[date] = None`
- `spouse_death_year: Optional[int] = None`
- `has_digital_assets: bool = False`

Update `to_dict()` on both. Defaults preserve existing scenario generation —
no generator changes required.

### Phase 1B: Constant rename + new populator

**File:** `training/form_fields.py`

- Rename constant *values* from `"you.*"` to `"filer.*"`. Keep Python
  identifiers as `YOU_*` for now to minimize import churn — the rename is at
  the *string value* layer, which is the wire format. (If you want full
  identifier rename too, do it in a follow-up commit; not required for
  correctness.)
- Replace `DEP_FIRST_NAME` + `DEP_LAST_NAME` with single `DEP_NAME = "name"`.
- Drop `YOU_SSN` / `SPOUSE_SSN` from `PART1_FIELDS` (Page 1 has no SSN
  inputs in the new template).
- Add new constants for every input that didn't have one (status trios,
  marital trio, claimable, refund/payment, language, election, two-states,
  `DEP_RESIDENT`, `DEP_IPPIN`, `DEP_MARITAL_EOY`, the five `DEP_VOL_*`).
- Add `UNGRADED_FIELDS: list[str]` listing the `dep.{i}.vol_qc_other` and
  `dep.{i}.vol_self_support` fields for `i in 0..3`. The result-rendering
  layer reads this to apply the "not graded" label.
- Update `PART1_FIELDS`, `TEXT_FIELDS`, `CHECKBOX_FIELDS`,
  `_DETAIL_FIELD_MAP`, `_YESNO_FIELD_MAP`.

**File:** `training/form_populator.py`

- Add `build_p1_field_values(household: Household) → Dict[str, str | bool]`
  that returns text strings and checkbox booleans keyed by the new names.
  Volunteer columns (`vol_*`) and pure UI defaults (refund/payment/
  language/election checkboxes) are *never* emitted — those stay blank for
  the player.
- Migrate `build_field_values` (the answer-key generator) to emit the new
  names too. For Page 1, it should call `build_p1_field_values` plus add
  the volunteer-column ground truth (see Phase 1E for which columns get
  scored).

### Phase 1C: Convert mockup to Jinja partial

**New file:** `api/templates/components/form_13614c_p1.html`

- Copy the inner content of `docs/mockups/13614c_page1.html` (everything
  inside `<div class="f13c-form">`).
- Replace each `<input type="text" name="X" value="...">` with
  `value="{{ p1.get('X', '') }}"`.
- Replace each `<input type="checkbox" name="Y">` with
  `<input type="checkbox" name="Y"{% if p1.get('Y') %} checked{% endif %}>`.
- For the dependents grid: drive rows with `{% for i in range(4) %}` —
  populated rows for `i < len(dependents)`, blank for the remainder.
- Add a `class="f13c-vol-col-ungraded"` decoration on the two ungraded
  volunteer column headers and their cells (CSS in 1D).

**New file:** `api/static/styles/form_13614c_p1.css`

- Copy the entire `<style>` block from the mockup's `<head>`.
- Adjust `body { background: #d0d0d0; ... }` → scope to `.f13c-form-shell`
  so it doesn't fight the page chrome.
- Add `.f13c-vol-col-ungraded` styling — a subtle visual marker (faint
  diagonal stripes or a `(not graded)` label in the header).

### Phase 1D: Wire into encounter view

**File:** `api/templates/encounter.html`

- Inside the `sheet__page` for `data-page="1"`, replace the existing
  two-column inline layout with
  `{% include "components/form_13614c_p1.html" %}`.
- Pages 2, 3, 4 keep their existing markup for now (out of scope).
- Add `<link rel="stylesheet" href="/app-static/styles/form_13614c_p1.css">`
  to the `<head>` block.

**File:** `api/routes/scenarios.py` (`page_exercise`)

- **Always** call `p1 = build_p1_field_values(scenario.household)` — drop
  the `mode == "verify"` gate for Page 1 client-column prefill.
- Pass `p1=p1` to the template context.
- Continue building the legacy `prefill` dict for pages 2 and 3 until those
  pages are migrated.

### Phase 1E: Migrate grader answer key + submission

**File:** `api/routes/scenarios.py` (`page_submit`)

- Reads `PART1_FIELDS` from `form_fields.py` — gets the new names
  automatically once 1B lands.
- No code changes needed here — the rename in 1B drives everything.

**File:** `training/grader.py` or wherever `compute_ground_truth` lives

Update answer-key generation for the three scored volunteer columns:

- `dep.{i}.vol_income_under`: `"Yes"` if `dep.total_income() < 5200` else
  `"No"`. For dependents without an income field, default `"Yes"` (children
  with no W-2).
- `dep.{i}.vol_support`: `"Yes"` if `dep.months_in_home >= 6` else `"No"`
  (loose MVP heuristic — anyone who lived in the home half the year is
  presumed supported).
- `dep.{i}.vol_home_cost`: `"Yes"` for the householder's primary home —
  assume Yes when the householder is the head of the filing unit. Refine
  later.

Skip emission for `vol_qc_other` and `vol_self_support` — these are in
`UNGRADED_FIELDS` and the grader gracefully ignores missing keys.

**Result-rendering layer** (the page that shows the score after
submission): read `UNGRADED_FIELDS` from `form_fields.py` and label those
fields explicitly as "Not graded in this version" rather than showing them
as missing or zero-scored.

### Phase 1F: Migration script

**New file:** `scripts/migrate_p1_field_names.py`

Standalone script. For each row in `data/scenarios.sqlite`'s scenarios
table:
- Load the `Household` from the row.
- Call `build_p1_field_values(household)` plus the volunteer-column
  ground-truth logic from 1E.
- Write the result back to the row's `ground_truth["form_answers"]` for
  Page 1 fields.
- Leave Pages 2/3 ground truth untouched (out of scope for this work).

The script is idempotent — running it twice produces the same result. Add
a `--dry-run` flag.

**Belt-and-suspenders check:** add a startup check in `api/main.py` (or
scenario-load path) that detects old field names in
`ground_truth["form_answers"]` and refuses to grade with a loud error
pointing at the migration script. Better than silent zero scores.

### Phase 1G: Tests

- `tests/test_form_populator_p1.py`: name/address/dob mapping; spouse
  absent path; status checkbox trios; marital row logic; up-to-4
  dependents; `full_legal_name` in `dep.{i}.name`; volunteer columns *not*
  present in output.
- `tests/test_encounter_p1_render.py` (FastAPI TestClient): GET
  `/scenarios/{id}` returns 200, HTML contains
  `value="<filer first name>"` and `name="filer.first_name"`, and the two
  ungraded volunteer column headers carry the `f13c-vol-col-ungraded`
  class.
- `tests/test_encounter_submit_p1.py`: POST with new field names; grader
  scores expected number of fields; ungraded columns appear in result with
  "Not graded" label.
- `tests/test_models_new_fields.py`: dataclass defaults preserve `to_dict`
  round-trip.
- `tests/test_migration_p1.py`: migration script over a fixture scenario
  produces the right `ground_truth` shape; idempotent.

### Sequencing

1A → 1B (atomic with 1F migration script) → 1C → 1D → 1E → 1G.

The atomicity of 1B + 1F matters: **the codebase must never be in a state
where `form_fields.py` has been renamed but stored scenarios haven't been
migrated** (otherwise any grade attempt against a stored scenario silently
zeroes). Land them in the same commit, or land 1F first as a no-op (still
emits old names), then 1B flips everything in one commit.

---

## Part 2 — Layout system

### Simplified scope (rev 2)

The original spec had a two-axis layout system (vertical and horizontal
splits, seven valid grid configurations, two split-cycle icons plus a
chat toggle). After watching Part 1 land in the encounter view we
decided to reduce scope: a single horizontal axis is enough for this
product because every relevant document is letter-format and reads
top-to-bottom alongside the form, and the form itself is 980px wide so
a vertical split would squeeze it below readable width.

The simplified system:

| State | Layout | Pane cycle |
|---|---|---|
| 1-pane (chat closed, **default on load**) | Form full screen | active |
| 2-pane (chat closed) | Form top, one doc bottom | active |
| 3-pane (chat closed) | Form top, two docs split side-by-side bottom | active |
| 1-pane (chat open) | Form 2/3 left, chat 1/3 right | **disabled** |
| 2-pane (chat open) | Form top + one doc bottom (in left 2/3) + chat 1/3 right | **disabled** |

**Chat-open is a view mode.** While chat is open, pane structure is
frozen — the pane-cycle button is disabled. To change pane count, the
player closes chat, cycles, and re-opens.

3 panes is forbidden in chat-open: two docs side-by-side at ~1/3 of
the screen each is unreadable, so opening chat from a 3-pane state
caches one doc and drops to 2-pane in the left 2/3.

Two buttons in the chrome:

1. **Pane cycle** — wraps forward through `1 → 2 → 3 → 1 → 2 → ...`.
   No endpoint flips, no direction tracking — every click advances;
   the 3 → 1 wrap drops both docs back to a clean form-only view.
   Disabled while chat is open.
2. **Chat toggle** — opens / closes the chat pane.

What dropped vs. the original spec:
- No vertical-split layouts (form-left + doc-right, etc.).
- No second split-axis icon.
- No cross-axis transitions (no "click the other axis to collapse and
  re-split").
- `LayoutState.axis` and `LayoutState.direction` fields both deleted —
  the wrapping cycle needs no direction memory.
- Two CSS Grid layouts removed (the v2 / v3 vertical configurations).

Effort drops by ~30% across the reducer, renderer, and CSS.

### Default layout

**On first load of a scenario, the workspace renders form-only at full
viewport width.** This is the simpler default for a new player and
sidesteps the current half-width-by-default behavior the encounter view
shows today (where `workspace__form` is one of three pre-allocated grid
cells regardless of whether doc panes have content).

Implementation: `data-layout="form-only"` is the initial state of
`#workspace`; doc panes don't exist in the DOM until pane cycle adds
them, or they're hidden via `display: none` until activated. The grid
template for `form-only` is a single 1fr cell.

### Horizontal scrolling on the form pane

The new 13614-C Page 1 partial has a fixed `width: 980px` (chosen to
match the IRS form's reading width). When chat is open, the workspace
collapses to the left 2/3 of the screen — on a typical 1280px window
that's ~853px, narrower than the form. Without explicit handling the
form gets clipped or the layout breaks.

Required CSS at the form pane level:

```css
#form-pane {
    min-width: 0;       /* opt out of the flex/grid default that
                           prevents shrinking below content size */
    overflow: auto;     /* horizontal scroll when content > pane width */
}
```

The `f13c-form` keeps its 980px and becomes scrollable inside the pane
whenever the pane is narrower. This applies in both chat-open and
chat-closed states; document panes get the same treatment for the same
reason (W-2s and 1099s want ~600px to read comfortably; squeezed
narrower they should scroll, not wrap).

### Files

**New:**
- `api/static/js/layout-reducer.js` — pure reducer + state shape.
  ~60 LOC (down from ~100 in the dual-axis design). Importable by
  tests.
- `api/static/js/layout-render.js` — `applyState(state)`, pane template
  functions, event delegation. ~150 LOC (down from ~200).
- `api/static/styles/layout.css` — five CSS Grid configurations as
  `[data-layout="..."]` selectors.

**Modified:**
- `api/templates/encounter.html` — replace `.workspace` markup with new
  pane structure; add
  `<script>window.SCENARIO_DOCS = {{ doc_urls|tojson }};</script>` and
  `<script>window.SCENARIO_DOC_LABELS = {{ doc_labels|tojson }};</script>`;
  add layout-control icons to titlebar.
- `api/templates/components/titlebar.html` — two new buttons (pane
  cycle, chat toggle).
- `api/routes/scenarios.py` (`page_exercise`) — pass the existing
  `doc_urls` map (currently built but unused) to the template; build a
  `doc_labels` map for tab-strip readability per the rule below.

### Document tab labels

The tab strip on a `DocumentPane` shows readable labels, not the
opaque `{type}_{person_id}_{idx}` keys used internally. The label rule
leads with the most identifying piece of information for that document
type:

| Case | Format | Example |
|---|---|---|
| Person-owned, single of its type | `{Person}'s {Type}` | `Maria's W-2` |
| Person-owned, multiple of same type | `{Person}'s {Type} ({n} of {total})` | `Maria's W-2 (1 of 2)` |
| Household-owned, with issuer | `{Type} — {Issuer}` | `1098 — Bank of Hawaii` |
| Household-owned, no issuer | `{Type}` | `1098` |

The `(n of total)` disambiguator only fires when a single person owns
multiple documents of the same type — Maria with one W-2 and one
1099-INT gets `Maria's W-2` and `Maria's 1099-INT`, no disambiguator.

`doc_labels` is built once in `page_exercise` alongside `doc_urls` and
passed to the template as a `dict[doc_id, str]`. The renderer reads
labels by id; no per-tab logic on the JS side.

### State shape

```js
const initialState = {
    panes: 1,                      // 1, 2, or 3 (max 2 when chatOpen)
    docSlots: [],                  // doc_ids; length = panes - 1
    chatOpen: false,
    hiddenDocCache: null,          // doc_id stashed during chat-open
    formState: {
        currentPage: 1             // 1-4. Field values are NOT in state.
    }
};
```

No `axis` field — there's only one axis. No `direction` field — the
wrapping cycle needs no direction memory; the next state is always
`(panes % 3) + 1`. Field values stay in the DOM, not in state. The
form pane is never re-rendered on layout transitions, so the live
DOM is the source of truth for field values; we never round-trip
through `applyState` for keystrokes.

### CSS Grid layouts

```css
#workspace {
    display: grid;
    gap: 4px;
    height: 100%;
}

#workspace[data-layout="form-only"] {
    grid-template: "f" / 1fr;
}

#workspace[data-layout="h2"] {
    grid-template:
        "f"  1fr
        "d0" 1fr
        / 1fr;
}

#workspace[data-layout="h3"] {
    grid-template:
        "f  f"  1fr
        "d0 d1" 1fr
        / 1fr 1fr;
}

/* Chat-open variants live in the left 2/3 of the screen;
   chat itself sits outside #workspace in the right 1/3. */
#workspace[data-layout="form-only-chat"] {
    grid-template: "f" / 1fr;
}

#workspace[data-layout="h2-chat"] {
    grid-template:
        "f"  1fr
        "d0" 1fr
        / 1fr;
}

#form-pane  { grid-area: f; min-width: 0; overflow: auto; }
#doc-pane-0 { grid-area: d0; min-width: 0; overflow: auto; }
#doc-pane-1 { grid-area: d1; min-width: 0; overflow: auto; }
```

Chat allocation: `.app-main` is itself a grid with
`grid-template-columns: 1fr 0` normally, `2fr 1fr` when
`body[data-chat="open"]`.

### Pane content rendering

- **FormPane** — server-rendered into `#form-pane` at initial page load.
  Never destroyed. Layout transitions only resize its grid cell.
- **DocumentPane** — `<iframe>` pointing at the existing per-doc HTML
  route (`/scenarios/{id}/documents/{type}/{pid}/{idx}`). Tabs populated
  from `window.SCENARIO_DOCS`. JS swaps the iframe `src` on tab click.
- **ChatPane** — static `<aside id="chat-pane">` with three placeholder
  sub-tabs (Probes / Flags / Notes). Hidden via
  `body:not([data-chat="open"]) #chat-pane { display: none; }`.

Iframes for documents avoid all style collision with the form (each
rendered document is a complete HTML page with its own styles). Future
right-click integration with documents will need to evolve past iframes,
but that's deferred.

### Reducer behavior

Pane-cycle click (no-op while `chatOpen` is true). Wrapping cycle —
every click advances; the 3 → 1 wrap drops both docs:
- From `panes: 1`: go to `panes: 2`, pick first available doc into
  `docSlots[0]`.
- From `panes: 2`: go to `panes: 3`, pick first not-yet-visible doc
  into `docSlots[1]`.
- From `panes: 3`: go to `panes: 1`, clear `docSlots`.

The icon shows the state the *next* click will produce: at `panes:1`
the icon shows the 2-pane figure; at `panes:2` it shows 3-pane; at
`panes:3` it shows 1-pane.

Chat-toggle:
- **Open from `panes:1`**: just set `chatOpen = true`. Workspace shrinks
  to the left 2/3; form gets horizontal scroll if needed. No cache.
- **Open from `panes:2`**: just set `chatOpen = true`. Both panes shrink
  into the left 2/3; form and the one doc each scroll horizontally as
  needed. No cache.
- **Open from `panes:3`**: stash `docSlots[1]` in `hiddenDocCache`, set
  `panes = 2`, `chatOpen = true`. The other doc remains visible in the
  left 2/3. Show a small "1 doc hidden" indicator near the chat-toggle
  button.
- **Close with `hiddenDocCache` set**: restore `docSlots[1] =
  hiddenDocCache`, `panes = 3`, clear cache.
- **Close without cache**: just `chatOpen = false`. Pane count and
  docSlots are unchanged from before chat opened.

The cache is a single `doc_id | null` — only the third doc that has to
be shed when chat opens from a 3-pane state. Player's panes/docSlots
state isn't snapshotted because it doesn't change while chat is open
(pane cycle is disabled).

### State persistence

`sessionStorage` keyed by `scenario_id`. Layout state survives reload.
Form field values survive automatically because they live in the DOM and
the form pane is never destroyed during a session (and on reload, the
server re-renders the form with the initial prefill — any in-progress
changes are lost on reload, which is acceptable for MVP).

### Pane content defaults

When a new doc pane is added: pick the first `doc_id` not already in
`docSlots`. If all docs are visible elsewhere, default to the first doc.
When a pane is removed: discard its doc reference (the doc is still
available in the tab strip of any remaining pane).

---

### Phase 2A: Pure logic — reducer + doc_labels helper

Pure functions only. No DOM, no CSS, no markup. Nothing renders
differently after this phase lands; this is foundation work that 2B
builds on.

**Files:**

- `api/static/js/layout-reducer.js` (new, ~60 LOC) — exports a single
  `reduce(state, action) → newState` function. Handles three action
  types: `CYCLE_PANES`, `TOGGLE_CHAT`, `SELECT_DOC`. No dependencies,
  no DOM access, no `document` references.
- `api/routes/scenarios.py` — add `_build_doc_labels(scenario) →
  dict[doc_id, str]` helper following the four-case rule from the
  *Document tab labels* section. Built once in `page_exercise` next to
  `doc_urls` and passed to the template (the template won't read it
  until 2B, but the data is in place).
- `tests/test_doc_labels.py` (new) — table-driven tests covering each
  of the four cases (person-owned single, person-owned multiple,
  household with issuer, household without).

**Test approach for the reducer:** the reducer is JS; the test suite
is Python. Two options considered:
- *Option 1 (chosen):* skip JS unit tests for now. Phase 2C's
  TestClient integration tests will exercise the reducer through
  real state transitions in the rendered DOM; isolated unit tests
  on a 60-LOC pure function add tooling overhead (`js2py` or a JS
  test runner) for marginal benefit.
- *Option 2 (deferred):* introduce a JS test runner if the reducer
  grows in complexity past Part 2.

**Verification:** `_build_doc_labels` covered by the new Python
tests; reducer eyeballed and committed for use in 2B.

**Why first:** the reducer is the brain of the layout system. If we
get its semantics wrong, 2B paints over the bug with markup and CSS
that's harder to dig out later. Landing it in isolation forces us to
write down the state machine before we have anything to fudge it
against.

### Phase 2B: Wire it up

The structural change. Workspace markup, CSS layouts, JS renderer,
and titlebar buttons are interdependent — partial rewrites break the
page — so this phase lands as one commit.

**New files:**

- `api/static/js/layout-render.js` (~150 LOC) — `applyState(state)`
  that mutates the DOM in response to reducer output. Pane template
  functions (`renderDocPane(paneIdx, docId, allDocs)`), event
  delegation (`handleClick(e)`), and the `dispatch(action)` entry
  point. Only this file touches the DOM; `applyState` is the single
  render entry point.
- `api/static/styles/layout.css` — the five CSS Grid configs as
  `[data-layout="..."]` selectors on `#workspace`, plus `.app-main`
  chat-1/3-or-0 grid template, plus `min-width:0; overflow:auto` on
  `#form-pane`, `#doc-pane-0`, `#doc-pane-1`.

**Modified files:**

- `api/templates/encounter.html` — replace the existing `.workspace`
  markup with the new pane structure. Add
  `<script>window.SCENARIO_DOCS = {{ doc_urls|tojson }};</script>` and
  `<script>window.SCENARIO_DOC_LABELS = {{ doc_labels|tojson }};</script>`.
  The default `data-layout="form-only"` is baked in server-side so
  the no-JS first paint is form-only-full-width (never half-hydrated).
- `api/templates/components/titlebar.html` — two new SVG buttons:
  pane-cycle (icon shows the next state per *Reducer behavior*), and
  chat-toggle. The chat-toggle button doubles as the host for the
  "1 doc hidden" indicator badge when `hiddenDocCache` is set.
- `api/routes/scenarios.py` (`page_exercise`) — pass `doc_urls` and
  `doc_labels` (built in 2A) to the template context.
- `api/static/js/encounter.js` — re-test against the new pane
  structure; page-tab switching inside the form pane should still
  work since it's orthogonal to the layout system.

**Deleted files:**

- `api/static/js/sidebar.js` — replaced by the chat-toggle action in
  `layout-render.js`. The `aside#sidebar` markup and its CSS go too.

**SessionStorage hydration:** at the bottom of `layout-render.js`, on
DOMContentLoaded, read `sessionStorage[scenarioId]` and call
`applyState()` with the parsed snapshot. If absent, leave the
server-rendered form-only default in place.

**Visual change goes live in this phase.** From here on, scenarios
load with the new chrome.

### Phase 2C: Tests + polish

Focused tests for the integration, plus any rough edges that surfaced
during 2B.

- `tests/test_encounter_layout_system.py` (FastAPI TestClient):
  - GET `/scenarios/{id}` returns 200 with `data-layout="form-only"`
    on `#workspace` (the server-rendered default).
  - The pane-cycle and chat-toggle buttons are present in the
    titlebar; `sidebar` markup is gone.
  - `window.SCENARIO_DOCS` and `window.SCENARIO_DOC_LABELS` are
    present in the rendered HTML and match the route's `doc_urls` /
    `doc_labels`.
  - Submitting the form post-rewrite still grades correctly
    (regression check on Phase 1's submit path).
- `tests/test_layout_doc_label_rendering.py`: per-case label
  assertions against scenarios with single-W-2, multi-W-2, household
  1098 with issuer.
- Polish: any layout glitches or chat-toggle edge cases observed
  while integrating in 2B (e.g., focus restoration when the cached
  doc returns).

**Out of scope for 2C:** browser-driven UI tests (Playwright /
Selenium). The DOM-mutating code is exercised at integration time
manually; automating the click-through is a separate effort.

### Sequencing

2A → 2B → 2C, all on the same branch. 2A is small enough (a few
hours) that we can review and decide on test approach for the JS
reducer before committing to 2B. 2B is the largest phase by far.
2C lands as a follow-up to whatever broke or felt rough during 2B.

Each phase is independently shippable in principle; in practice 2A
ships behind a useless data-pipe (the doc_labels arrive but nothing
reads them) and 2B ships the user-visible feature.

---

## Suggested implementation order

**Part 1 (form integration) — complete:**

1. **Phase 1A** (model extensions) — additive, lands in isolation.
2. **Phase 1B + 1F** (rename + migration) — atomic. Includes the startup
   check that loudly fails on un-migrated scenarios.
3. **Phase 1C + 1D + 1E** (Jinja partial + encounter integration + answer
   key) — lands as one PR; testable end-to-end.
4. **Phase 1G** (tests) — actually written in parallel with 1C/D/E, just
   listed last for narrative clarity.

**Part 2 (layout system) — three phases on one branch:**

5. **Phase 2A** (pure logic) — `layout-reducer.js` plus
   `_build_doc_labels` helper + tests. No UI change. Hours, not days.
6. **Phase 2B** (wire it up) — workspace markup replacement, CSS
   layouts, JS renderer, titlebar buttons, sessionStorage hydration.
   The visual change goes live here. Lands as one commit since the
   pieces are interdependent.
7. **Phase 2C** (tests + polish) — TestClient integration tests for
   the new chrome; per-case doc-label assertions; cleanup of any
   rough edges from 2B.

Phases of Part 1 each had distinct correctness concerns (migration
atomicity, schema changes, etc.) so they were split fine-grained.
Part 2 is one feature with no migration concerns and no atomicity
requirements; phasing here is purely about review surface and
bisect-ability — three phases is enough.

---

## Open questions still on the table

1. **Verify mode prefill.** The new flow always prefills the client column.
   Verify mode currently prefills more than that. What's Verify mode's
   behavior post-migration?
2. **Generator diversity.** `Person.us_citizen`, `legally_blind`, etc.
   default to safe values. Should the generator actively diversify (produce
   some non-citizen, some legally-blind scenarios)?
   *Recommendation: not in this work. Defer to a separate generator-update
   task.*
3. **Legacy `/form`, `/form/income`, `/form/expenses` pages.** Keep as-is,
   retire, or hide behind a debug flag?
   *Recommendation: keep for now, retire after Pages 2/3/4 are migrated.*

### Resolved

- **Dependent name format**: single combined `dep.{i}.name` (matches the
  template). Implemented in Phase 1B.
- **DOB format for dependents**: `MM/DD/YYYY` everywhere. Template hint
  updated to match.
- **Layout-control icon location**: titlebar (alongside the gear and
  Submit buttons).
- **Chat-open layout from a 1-pane state**: stay form-only; the player
  explicitly clicks pane-cycle to add a doc. (Resolved trivially by the
  Part 2 simplification — there's no axis decision left to make.)
- **Layout axes**: dropped vertical splitting entirely. Single horizontal
  axis. Five layouts instead of seven; two chrome buttons instead of
  three.

---

## Acceptance criteria

After this work:

- Loading a scenario shows the form with Page 1 pre-filled from the
  household data.
- The workspace defaults to **form-only at full viewport width** on
  first load (no half-screen-by-default behavior).
- The player can cycle through the three chat-closed layouts (form-only,
  form-top + 1-doc, form-top + 2-docs) via a single pane-cycle button.
- The player can toggle chat on/off; opening chat from a 3-pane state
  caches one doc and surfaces a "1 doc hidden" indicator; closing chat
  restores the cached doc.
- Each document pane has a tab strip showing all scenario documents;
  clicking a tab swaps the pane's content.
- The form pane scrolls horizontally when the pane is narrower than the
  form's 980px width (in particular when chat is open).
- Submitting the form posts the volunteer-column data to the grader;
  grading runs and returns a result.
- The two ungraded volunteer columns are visibly marked in the form and
  in the result page.

Pages 2, 3, 4 of the form being placeholders is acceptable — the layout
system handles them being empty without issue (the page tab strip is
present; pages render as empty templates).

---

## What's deferred

- Pages 2, 3, 4 of the form (each gets its own template + wiring task).
- Right-click context menu on form fields.
- Probe interaction in the chat pane.
- Verify mode (different right-click verbs, different submission flow).
- Vida coach scripts.
- Layout customization beyond the five preset layouts (no free-form
  resizing, no drag-and-drop pane rearrangement, no vertical splitting).
- Mobile / touch.
- Generator diversification of the new boolean fields (`Person.us_citizen`
  etc. default to safe values until a separate generator-update task).
- Scoring `vol_qc_other` and `vol_self_support` (requires modeling
  dependent-support economics; "not graded in this version" until then).
