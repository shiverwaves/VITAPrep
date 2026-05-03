# Single-Scroll Form Integration — Implementation Plan

This plan replaces the encounter view's three-page tab-swap form with a
single continuously-scrolling form that stacks Pages 1, 2, and 3 in one
DOM. The page tabs become scroll-spy / jump-anchor navigation rather than
visibility toggles.

This sits alongside [`PAGE1_INTEGRATION_PLAN.md`](./PAGE1_INTEGRATION_PLAN.md)
(which brought Pages 1–3 online as separate tabs) and
[`ENCOUNTER_UI_PLAN.md`](./ENCOUNTER_UI_PLAN.md) (the broader Encounter UI
architecture). Where they conflict, those docs are the frame; this doc is
the tactical migration.

---

## Rationale

Three observations from using the multi-tab form in practice:

1. **The Submit button already grades comprehensively.** Pages I + II + III
   are submitted and graded together. The multi-tab UI splits the form
   into three views even though the underlying mental model — "fill out
   the whole thing, then submit" — is one continuous task. The UI lags
   behind the data model.

2. **Most player effort is on Pages 2 and 3.** Page 1 is mostly
   pre-filled (filer info, address, marital, dependents). Pages 2 and 3
   are where the work is. Forcing tab swaps between Page 2 and Page 3
   adds friction with no clarifying benefit.

3. **Cross-page reference is currently impossible.** A player on Page 3
   can't glance back at the filer's Page 1 data without leaving Page 3.
   In a continuous scroll, both are reachable with a wrist flick.

A single scroll consolidates the form into one mental object that
matches the comprehensive-grade model. The page tabs survive as a
sticky table-of-contents for fast jumps.

---

## Decisions made

These need to be locked in before implementation:

1. **Tabs become scroll-anchor links, not visibility toggles.** Click
   smooth-scrolls to the section. The "active tab" highlight is driven
   by which section is currently in view (IntersectionObserver). The
   user's URL gets the fragment (`#page-2`) so deep-linking works.

2. **All three sections always render.** The `sheet__page--active` /
   non-active CSS toggle is removed. Every page partial is mounted at
   page load; the form pane just becomes taller. This is the simplest
   path; performance is fine since the form is static markup.

3. **Tabs sticky at the top of the form pane.** The `.sheet__tabs` strip
   becomes `position: sticky; top: 0` inside `#form-pane`. As the user
   scrolls the form, the tab strip stays visible and the active tab
   updates from the scroll-spy.

4. **Section dividers are visual, not structural.** Heavy top-border on
   each `.sheet__page` so sections feel distinct as the user scrolls
   through; no separate footer between sections (one footer at the very
   bottom of the form).

5. **The grade-card header (`Part II — Income / Not yet submitted`)
   stays at the top of each section.** Already shows per-section score
   from `section_grades`. This is the section heading, basically. After
   submission, the player can scroll down and see "23/30 (76%)" inline
   with the Income section — a strong visual progress signal.

6. **Page-indicator chrome (`Page 2`, `Page 3` in the top-right of each
   partial) is removed.** Redundant with the sticky tab strip + section
   header. Saves vertical space.

7. **Section-completion progress indicators are out of scope for the
   first cut.** "Filled-N-of-M" badges per section are the obvious
   recovery for the lost page-completion milestone, but they need
   thinking about (which fields count as "required"? does the grade
   card already cover this once submitted?). Defer.

8. **No JS auto-scroll on submit.** Result page is its own view; the
   form scrolls back to top on next load.

A meta-principle: this is purely a UI migration. The populator, grader,
submit handler, and answer-key model don't change at all.

---

## Out of scope

Listed explicitly so they don't creep into this sprint:

- Section-completion progress indicators (filled-N-of-M badges).
- Per-section submit (not implemented today either; comprehensive
  submit stays as the only path).
- Multi-doc workspace tweaks (covered separately in the document
  switcher redesign).
- Changes to the form partial contents or the populator output. The
  three partials render exactly as they do now; only their wrapper
  visibility behavior changes.

---

## Architectural commitments

Patterns the implementation must follow:

- **Tabs strip remains the same DOM element**
  (`.sheet__tabs > .sheet__tab[data-page="N"]`). Only its CSS positioning
  and JS click handler change. Existing tests against the DOM structure
  stay valid.
- **Scroll-spy is one IntersectionObserver, one render path.** The
  observer fires when a `.sheet__page` enters/leaves the viewport; the
  callback sets `.sheet__tab--active` on the matching tab and removes
  it from the others. No side effects elsewhere.
- **No global scroll listeners.** IntersectionObserver only;
  `scroll`-event throttling is the slow path the spec was written to
  replace.
- **Hash routing is one-way write.** The URL fragment updates as the
  user scrolls (so the back button moves between sections); but
  arriving with `#page-2` in the URL on initial load triggers a
  `scrollIntoView`. We don't trap the back button or override anything
  else.
- **All scroll behavior is opt-in via `prefers-reduced-motion`.** Users
  who've turned off motion get instant jumps, not smooth scroll.

---

## Phased plan

Mirroring the Phase 3 / Phase 4 sequence (atomic phases that each leave
the test suite green).

### Phase A — Plan + Decisions

This document. Done before implementation starts.

### Phase B — Template restructure

In `api/templates/encounter.html`:

- Drop the `{% if tab.active %} sheet__page--active{% endif %}`
  conditional. Every section is always rendered; activeness is no
  longer a visibility flag.
- Add `id="section-{{ tab.page }}"` (or reuse the existing
  `id="page-{{ tab.page }}"`) so tabs can scroll to anchors.
- The Page-1-specific layout-override CSS
  (`.sheet__page--p1 / --p2 / --p3 { padding: 0; overflow: visible; }`)
  stays — it applies to all three sections.
- Add a heavy `border-top` rule for the second and third sections so
  they have a visible divider as the user scrolls past.

In `api/templates/components/form_13614c_p{2,3}.html`:

- Remove the `f13c-p{2,3}-page-indicator` (`Page 2` / `Page 3`
  top-right). Already-rendered scroll-spy + section header replace it.

In `api/static/styles/sheet.css` (or wherever `.sheet__tabs` lives):

- Add `position: sticky; top: 0; z-index: 5; background: var(--color-surface);`
  to `.sheet__tabs`. The sticky context is `#form-pane` (the
  scroll container), which already has `overflow: auto`.

Tests touched:

- Existing render tests that assert exactly one section is visible
  (`sheet__page--active` count). Update to: all sections rendered;
  active tab is highlighted but all sections present.

### Phase C — JS scroll-spy + anchor navigation

In `api/static/js/encounter.js`:

- Replace the `switchTab(pageNum)` visibility-toggle logic with:
  - **Tab click**: smooth-scroll the form pane to the target section's
    `offsetTop`. Update `window.location.hash` to `#page-N` (using
    `history.replaceState` so the back button doesn't stack a new entry
    per click).
  - **IntersectionObserver**: one observer watching `.sheet__page`
    elements; on intersection-change, set the `--active` class on the
    matching tab and remove it from siblings.
  - **Initial load**: if `window.location.hash` matches a section,
    `scrollIntoView` that section. Otherwise scroll to top.
- Honor `prefers-reduced-motion` for both the click-scroll and the
  initial-load scroll.
- The form-pane scroll container is `#form-pane`. The observer's
  `root` should be that element.

Tests touched / added:

- `test_encounter_p1_render.py` (existing) — section visibility
  assertion update if any tests pin to a specific page being
  exclusively visible.
- New JS tests are out of scope; these are integration-level concerns
  best validated by hand. (We don't have a JSDOM-based test harness
  for `encounter.js` today; introducing one is a separate decision.)

### Phase D — CSS polish

In `api/static/styles/sheet.css`:

- Section divider between consecutive `.sheet__page` elements
  (`.sheet__page + .sheet__page { border-top: 1.5px solid #000; }`
  or a similar marker).
- Sticky-tabs padding + shadow when scrolled (a subtle drop-shadow once
  the user scrolls past the sheet header — communicates "this is
  pinned").
- Optional: `scroll-padding-top` on the `#form-pane` container so
  fragment-scrolls don't land underneath the sticky tab strip.

### Phase E — Test updates

Across:

- `tests/test_encounter_p1_render.py`
- `tests/test_encounter_p2_render.py`
- `tests/test_encounter_p3_render.py`

Each currently slices the rendered HTML by section and asserts the
section's content is correct. With all sections always rendered, the
slicing logic still works (`id="page-N"` boundaries are unchanged) —
the assertions about *visibility* become assertions about *active-tab
state*. Concretely:

- Replace `sheet__page--active` checks (where they exist) with
  presence-of-tab-with-`sheet__tab--active` for the expected page.
- New test: tabs strip carries the sticky-positioning class.
- New test: clicking a tab updates `location.hash` (would need a
  JSDOM-style harness; alternative is asserting the click handler
  exists and is wired).

### Phase F — Manual verification

After Phase E lands and all tests pass:

- Generate a scenario, scroll through the form end-to-end.
- Click each tab from each starting position; confirm smooth scroll +
  sticky tab + URL hash update.
- Open with `#page-2` in the URL; confirm initial scroll lands on
  section 2.
- Toggle reduced-motion in the browser; confirm jumps are instant.
- Submit with the form filled out; confirm result page renders
  correctly.
- Cross-browser smoke test (Safari especially — `position: sticky`
  inside an `overflow: auto` container has historically been finicky).

---

## Risks + mitigations

- **Sticky positioning inside `#form-pane`** (which itself has
  `overflow: auto`). This works in modern browsers but historically
  tripped Safari. Mitigation: explicit `position: sticky` test in a
  small fixture page; fall back to `position: absolute` with manual
  scroll-handler if needed (last resort).

- **Form pane gets very tall on small screens.** Three pages stacked
  is a long scroll. Mitigation: sticky tabs are *the* mitigation; the
  user can always jump back to the top and choose a section.

- **IntersectionObserver thresholds.** If two sections overlap the
  viewport (e.g. a short Section 1 next to a tall Section 2), the
  active tab needs to pick one. Mitigation: use the section closest
  to the form-pane's `scroll-padding-top` line, not the whole
  viewport. Explicit threshold: `[0, 0.25, 0.5, 0.75, 1.0]` and pick
  the entry with the highest intersection ratio in the callback.

- **URL fragment churn.** Updating `location.hash` on every section
  change could spam the back-button history. Mitigation:
  `history.replaceState`, not `pushState`. The back button moves
  between *pages* the user actually navigated to, not scroll
  positions.

- **Existing test surface.** Phase 3-G and 4-G tests slice the page-N
  region by id boundary. That keeps working — no slicing changes
  needed. The visibility-based assertions are the small set of test
  changes.

---

## Sequencing

| Phase | What | Tests | Commit |
|-------|------|-------|--------|
| A | Plan doc | — | this commit |
| B | Template restructure: drop `--active`, anchors, page-indicator removal, sticky-tab CSS skeleton | render tests adjusted | one commit |
| C | JS: scroll-spy + smooth-scroll click handler + hash routing | — | one commit |
| D | CSS polish: section dividers, sticky-tab shadow, scroll-padding | — | one commit |
| E | Test updates | full suite green | one commit |
| F | Manual browser verification | — | sign-off, no commit |

Each phase commit pushes to the working branch and leaves the test
suite green; that pattern matches the Phase 3 / Phase 4 cadence.

---

## What this enables (after)

- Cross-page reference (look at filer's name on Page 1 while filling
  Page 3) becomes a wrist flick.
- The Submit button matches the user's mental model — "I'm done with
  the whole thing" is a single act, not three confused tab swaps.
- Section grades render inline as the user scrolls through after a
  graded submission, putting the feedback right next to the work.
- Future progress indicators (deferred) get a clear surface — they
  attach to the sticky tabs.
- Sets up the consolidated document switcher (separately planned)
  cleanly: the form pane is now one tall thing, the doc panes are
  switched from a single global title bar. Two single-source-of-truth
  controls.
