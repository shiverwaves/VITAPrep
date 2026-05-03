# Single-Scroll Form Integration — Implementation Plan

This plan replaces the encounter view's three-page tab-swap form with a
single continuously-scrolling form that stacks Pages 1, 2, and 3 in one
DOM. The page tab strip is disabled; it will be repurposed for document
labels in a future feature, but for this sprint it just goes away.

This sits alongside [`PAGE1_INTEGRATION_PLAN.md`](./PAGE1_INTEGRATION_PLAN.md)
(which brought Pages 1–3 online as separate tabs) and
[`ENCOUNTER_UI_PLAN.md`](./ENCOUNTER_UI_PLAN.md) (the broader Encounter UI
architecture).

---

## Rationale

Three observations from using the multi-tab form in practice:

1. **The Submit button already grades comprehensively.** Pages I + II + III
   are submitted and graded together. The multi-tab UI splits the form
   into three views even though the underlying mental model — "fill out
   the whole thing, then submit" — is one continuous task.

2. **Most player effort is on Pages 2 and 3.** Page 1 is mostly
   pre-filled. Forcing tab swaps between Page 2 and Page 3 adds friction
   with no clarifying benefit.

3. **Cross-page reference is currently impossible.** A player on Page 3
   can't glance back at the filer's Page 1 data without leaving Page 3.

A single scroll consolidates the form into one mental object. The page
tabs become unnecessary; the navy form banner (Form 13614-C —
Intake/Interview Sheet / OMB 1545-2272) stays at the top as the form's
own header, and the player just scrolls.

---

## Decisions made

These need to be locked in before implementation:

1. **Tabs disabled, not navigated.** The `.sheet__tabs` strip is removed
   from the rendered DOM (or hidden with `display: none`). No scroll-spy,
   no anchor nav, no JS click handlers. The tab strip will be
   repurposed for document labels in a future sprint; until then it
   doesn't render.

2. **All three sections always render, stacked.** The
   `sheet__page--active` / non-active CSS toggle is removed. Every page
   partial is mounted at page load; the form pane just becomes taller.

3. **Navy form banner stays.** The `.sheet__header` (Form 13614-C —
   Intake/Interview Sheet / OMB 1545-2272) remains at the top of the
   sheet — it's the form's identifying header, separate from the
   page-tab navigation we're removing.

4. **Per-section grade cards stay inline as section dividers.** The
   existing form-card header (`Part II — Income / Not yet submitted` →
   `23/30 (76%)` after submission) is per-section already and serves as
   a strong visual section break. No additional dividers needed.

5. **Page-indicator chrome (`Page 2`, `Page 3` in the top-right of each
   partial) is removed.** Redundant once the tab strip is gone and the
   section grade cards do the section-marking.

6. **No JS work required.** The current `encounter.js` `switchTab`
   function and its IIFE that wires tab clicks become dead code —
   delete the tab-handling block. Anything else `encounter.js` does
   (status bar updates, etc.) stays.

7. **Section-completion progress indicators are out of scope for v1.**
   Filled-N-of-M badges per section are the obvious recovery for the
   lost page-completion milestone, but they need separate thinking and
   would attach to the (now-absent) tab strip.

8. **No URL fragment routing.** Without scroll-spy or jump-anchors,
   there's nothing to write to `location.hash`. If a player wants to
   scroll fast they use `Home` / `End` / browser find.

A meta-principle: this is the simplest possible UI migration. The
populator, grader, submit handler, and answer-key model don't change.
Even the tab DOM stays in the rendered HTML for tests / future
repurposing — it just doesn't show up.

---

## Out of scope

- Scroll-spy / sticky tab strip / smooth-scroll click handlers (the
  original draft of this plan included these; the user clarified they
  weren't needed once the tabs are gone entirely).
- Section-completion progress indicators.
- Per-section submit (comprehensive submit stays as the only path).
- Document switcher redesign (separate plan).
- Any change to the populator, grader, submit handler, or partials'
  field structure.

---

## Phased plan

### Phase A — Plan + Decisions

This document.

### Phase B — Template + CSS

In `api/templates/encounter.html`:

- Drop the `{% if tab.active %} sheet__page--active{% endif %}`
  conditional. Every section renders all the time.
- Hide the `.sheet__tabs` strip (or wrap it in
  `<div hidden>` / drop the `{% for tab %}` loop entirely). Decision:
  drop the loop. Less DOM, no chance of unstyled flash.

In `api/templates/components/form_13614c_p{2,3}.html`:

- Remove the `f13c-p{2,3}-page-indicator` (`Page 2` / `Page 3`
  top-right). Dead chrome once tabs are gone.

In `api/static/styles/sheet.css`:

- Drop the `.sheet__page` visibility rule that depends on
  `--active` (if one exists). All sections always visible.
- Optional: heavier top border on the second and third
  `.sheet__page` so sections feel demarcated as the user scrolls.
  The grade-card form-card already provides a visual break, so this
  is taste-driven; review before committing.

In `api/static/js/encounter.js`:

- Delete the `switchTab` function and its `tab.click` listener IIFE.
- Anything else (status-bar updates, etc.) stays.

### Phase C — Test updates

- `tests/test_encounter_p1_render.py`,
  `tests/test_encounter_p2_render.py`,
  `tests/test_encounter_p3_render.py`: any assertion that hinges on
  exactly one section being marked `--active` becomes "all sections
  rendered, none have the active class" — adjust as needed.
- `tests/test_encounter_submit_p{1,2,3}.py`: submit flow doesn't
  depend on tab state, but the perfect-submission helpers may scrape
  the rendered HTML to build their submission. Confirm scraping still
  works when all sections are simultaneously visible (it should — the
  scrapers don't filter by active class).
- New test (optional): assert the tab strip isn't rendered (no
  `.sheet__tab` elements in the encounter HTML).

### Phase D — Manual verification

- Generate a scenario, scroll through end-to-end.
- Confirm the navy banner header stays at the top of the sheet.
- Confirm Pages 1, 2, 3 stack cleanly with no awkward visual seam.
- Submit; confirm the result page renders correctly and section
  grades show inline on the next form load.
- Cross-browser smoke test (Safari especially, even though we're
  not using sticky positioning anymore).

---

## Risks + mitigations

- **Layout-overrride CSS pinned to `--p1` class.** The encounter
  template currently keys some overrides off `.sheet__page--p1` /
  `--p2` / `--p3`. With all three sections always rendered, those
  overrides apply to every section as before. No change.

- **Form pane gets very tall on small screens.** Three pages stacked
  is a long scroll. Mitigation: this is the explicitly-chosen UX. The
  form pane already has `overflow: auto`; users scroll. If this turns
  out to be too aggressive in practice, a scroll-spy / sticky-section
  affordance can be added later — the underlying DOM structure
  supports it.

- **Existing tests reference tab DOM.** `encounter.js` test (none
  exist as Python tests today; the JS isn't unit-tested). Render
  tests don't pin on tab existence specifically. Should be a clean
  removal.

---

## Sequencing

| Phase | What | Tests | Commit |
|-------|------|-------|--------|
| A | Plan doc | — | this commit |
| B | Template + CSS + JS removal | render tests adjusted | one commit |
| C | Test updates | full suite green | (with phase B if straightforward) |
| D | Manual browser verification | — | sign-off, no commit |

If Phase C ends up small (a handful of `--active` assertion edits),
fold it into the Phase B commit. If it's a bigger surface, split.

---

## What this enables (after)

- The Submit button matches the user's mental model — "I'm done with
  the whole thing" is a single act, no tab swaps.
- Cross-section reference (look at filer's name on Section 1 while
  filling Section 3) becomes a wrist flick.
- Section grades render inline as the user scrolls through after a
  graded submission, putting the feedback right next to the work.
- The tab strip DOM is freed up for the future document-labels
  feature without any structural rework.
