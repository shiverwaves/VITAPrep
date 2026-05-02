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

### Files

**New:**
- `api/static/js/layout-reducer.js` — pure reducer + state shape. ~100
  LOC. Importable by tests.
- `api/static/js/layout-render.js` — `applyState(state)`, pane template
  functions, event delegation. ~200 LOC.
- `api/static/styles/layout.css` — seven CSS Grid configurations as
  `[data-layout="..."]` selectors.

**Modified:**
- `api/templates/encounter.html` — replace `.workspace` markup with new
  pane structure; add
  `<script>window.SCENARIO_DOCS = {{ doc_urls|tojson }};</script>`; add
  layout-control icons to titlebar.
- `api/templates/components/titlebar.html` — three new buttons
  (vertical-split, horizontal-split, chat-toggle).
- `api/routes/scenarios.py` (`page_exercise`) — pass the existing
  `doc_urls` map (currently built but unused) to the template; build a
  `doc_labels` map for tab strip readability.

### State shape

```js
const initialState = {
    panes: 1,                      // 1, 2, or 3
    axis: "vertical",              // only meaningful when panes >= 2
    direction: "expanding",        // for icon state display
    docSlots: [],                  // doc_ids; length = panes - 1
    chatOpen: false,
    hiddenDocCache: null,          // doc_id stashed during chat-open
    formState: {
        currentPage: 1             // 1-4. Field values are NOT in state.
    }
};
```

Field values stay in the DOM, not in state. This is intentional — the form
pane is never re-rendered on layout transitions, so DOM is the source of
truth for field values, and we never have to round-trip through
`applyState` for keystrokes.

### CSS Grid layouts

```css
#workspace { display: grid; gap: 4px; height: 100%; }

#workspace[data-layout="form-only"] { grid-template: "f" / 1fr; }
#workspace[data-layout="v2"]        { grid-template: "f d0" / 1fr 1fr; }
#workspace[data-layout="v3"]        { grid-template: "f d0" 1fr "f d1" 1fr / 1fr 1fr; }
#workspace[data-layout="h2"]        { grid-template: "f" 1fr "d0" 1fr / 1fr; }
#workspace[data-layout="h3"]        { grid-template: "f f" 1fr "d0 d1" 1fr / 1fr 1fr; }

/* Chat-open variants live in left 2/3; chat lives outside #workspace */
#workspace[data-layout="v2-chat"]   { grid-template: "f" / 1fr; }
#workspace[data-layout="h2-chat"]   { grid-template: "f" 1fr "d0" 1fr / 1fr; }

#form-pane  { grid-area: f; }
#doc-pane-0 { grid-area: d0; }
#doc-pane-1 { grid-area: d1; }
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
  sub-tabs (Probes/Flags/Notes). Hidden via
  `body:not([data-chat="open"]) #chat-pane { display: none; }`.

Iframes for documents avoid all style collision with the form (each
rendered document is a complete HTML page with its own styles). Future
right-click integration with documents will need to evolve past iframes,
but that's deferred.

### Reducer behavior

Cycle for split-axis click: `1 → 2 → 3 → 2 → 1`, with `direction` flipping
at endpoints. Cross-axis click collapses to 1 along current axis and
immediately splits to 2 along new axis.

Chat-toggle:
- **Open from 3-pane**: cache `docSlots[1]` in `hiddenDocCache`, set
  `panes = 2, axis = "horizontal"` (the only valid 2-pane chat-open state
  per spec), `chatOpen = true`. Show small "1 doc hidden" indicator.
- **Open from 1- or 2-pane**: just set `chatOpen = true`. If currently
  2-pane vertical, force axis to horizontal (or to form-only — see open
  question 7 below).
- **Close with cached doc**: restore `docSlots[1] = hiddenDocCache`,
  `panes = 3`, `axis = previousAxis`, clear cache.
- **Close without cache**: just `chatOpen = false`.

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

## Suggested implementation order

1. **Phase 1A** (model extensions) — additive, lands in isolation.
2. **Phase 1B + 1F** (rename + migration) — atomic. Includes the startup
   check that loudly fails on un-migrated scenarios.
3. **Phase 1C + 1D + 1E** (Jinja partial + encounter integration + answer
   key) — lands as one PR; testable end-to-end.
4. **Phase 1G** (tests) — actually written in parallel with 1C/D/E, just
   listed last for narrative clarity.
5. **Part 2** — layout reducer first (testable in isolation), then
   renderer + CSS, then titlebar wiring, then chat toggle, then end-to-end.

Each phase is independently shippable behind a feature flag (e.g.,
`ENCOUNTER_V2=true` env var) until you're confident.

---

## Open questions still on the table

1. **Verify mode prefill.** The new flow always prefills the client column.
   Verify mode currently prefills more than that. What's Verify mode's
   behavior post-migration? (Worth resolving before 1D.)
2. **Generator diversity.** `Person.us_citizen`, `legally_blind`, etc.
   default to safe values. Should the generator actively diversify (produce
   some non-citizen, some legally-blind scenarios)?
   *Recommendation: not in this work. Defer to a separate generator-update
   task.*
3. **Dependent name format.** Single combined `dep.{i}.name` per template,
   or split? Decision affects the answer key.
   *Recommendation: combined*, since that's what the rendered template
   expects.
4. **DOB format for dependents.** Template hint says `mm/dd/yy`; populator
   emits 4-digit.
   *Recommendation: align both to `MM/DD/YYYY`*, update the template hint.
5. **Legacy `/form`, `/form/income`, `/form/expenses` pages.** Keep as-is,
   retire, or hide behind a debug flag?
   *Recommendation: keep for now, retire after Pages 2/3/4 are migrated.*
6. **Layout-control icon location.** Titlebar (with gear and Submit) or a
   new bar above the workspace?
   *Recommendation: titlebar.*
7. **Chat-open layout from a 1-pane state.** Spec says two valid chat-open
   layouts (form-only-2/3 and form-top + doc-bottom-2/3). What does opening
   chat from form-only do — stay form-only, or auto-add a doc pane?
   *Recommendation: stay form-only*; player explicitly clicks split if
   they want a doc.

Most of these are tactical and resolvable when their step lands. #1
(Verify mode prefill) is the only one that could change Phase 1D's scope.

---

## Acceptance criteria

After this work:

- Loading a scenario shows the form with Page 1 pre-filled from the
  household data.
- The player can switch among the five chat-closed layouts via the two
  layout-control icons.
- The player can open chat (which reorients the layout) and close chat
  (which restores the prior layout).
- Each document pane has a tab strip showing all scenario documents;
  clicking a tab swaps the pane's content.
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
- Layout customization beyond the seven preset layouts.
- Mobile / touch.
- Generator diversification of the new boolean fields (`Person.us_citizen`
  etc. default to safe values until a separate generator-update task).
- Scoring `vol_qc_other` and `vol_self_support` (requires modeling
  dependent-support economics; "not graded in this version" until then).
