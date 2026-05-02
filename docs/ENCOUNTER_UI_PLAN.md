# Encounter UI — Implementation Plan

This plan covers the transition from the current server-rendered MVP to the
redesigned Encounter/Verify UI described in the transition doc. The goal is the
structural shell with real data binding, not full feature implementation.

Reference materials:
- Transition doc (Intake/Verify → Encounter/Verify)
- HTML mockups: `home.html`, `encounter.html`
- Wireframe image (multi-pane layout with document viewers + probes sidebar)
- VIDA_DESIGN.md (procedure steps, coach integration)

---

## Current state

The MVP frontend is **server-rendered HTML built from Python f-strings** in
`api/routes/scenarios.py` (~1800 lines). There is no JavaScript, no frontend
framework, no client-side routing. Documents open in separate browser tabs.
Jinja2 is used only for document templates (`training/templates/`), not for
page templates.

This approach cannot support the new design's multi-pane layout, document
tab-switching, collapsible panels, right-click menus, or chat infrastructure.
The plan replaces the f-string HTML with Jinja2 page templates and vanilla JS,
matching the mockup's approach.

---

## Architecture decisions

1. **Jinja2 for page templates.** Move page HTML from f-strings in Python to
   `.html` files in a new `api/templates/` directory. Jinja2 is already a
   dependency (used by document renderer). This separates layout from logic.

2. **Vanilla JS for interactivity.** No React/Vue/Svelte. The mockups
   demonstrate that vanilla JS handles the required interactions (menus,
   panel toggle, tab switching, context menu, pane resizing). Adding a
   framework introduces build tooling complexity with no clear benefit at
   this scale.

3. **CSS in dedicated files.** Extract styles from inline `<style>` blocks
   into `.css` files served via FastAPI's static mount. Use CSS custom
   properties (variables) for the design tokens (colors, radii, spacing)
   from the mockups.

4. **Documents loaded as HTML fragments.** The existing document routes
   return full HTML pages. Add a `?fragment=1` query parameter that returns
   just the document body (no `<html>`/`<head>` wrapper), suitable for
   injection into a document pane via `fetch()`. Existing routes continue
   working unchanged for backwards compatibility.

5. **Form left column driven by boilerplate notes.** The client column
   renders from `scenario.interview_notes`, filtered by category to the
   active page. Each note becomes a form row: checkmark (Yes/No) + label
   (question) + optional follow-up (detail note). The boilerplate system
   we built is the data source.

6. **Mode rename is a codebase-wide find/replace.** `intake` → `encounter`
   in mode strings, route names, and variable names. Done as a single
   atomic commit before any UI work so the new code never uses the old name.

---

## Phases

### Phase 0: Infrastructure

Groundwork that everything else depends on.

**0.1 — Mode rename: Intake → Encounter**
- Find/replace `intake` → `encounter` in mode strings across the codebase
  (scenario model, exercise engine, API routes, grader, tests).
- The `intake/` Python package (analyzer, boilerplate) keeps its directory
  name — it's a domain concept, not a mode name.
- `Verify` mode name stays unchanged.
- Migration: treat any persisted `intake`-mode scenario as `encounter`-mode
  when loading from the scenario store.

**0.2 — Jinja2 page template setup**
- Create `api/templates/` directory for page templates.
- Configure FastAPI's Jinja2Templates to load from this directory.
- Create `api/static/` directory for CSS and JS files.
- Mount `/static` to serve from `api/static/`.
- Create base template (`base.html`) with the app shell: `<html>`, `<head>`,
  CSS links, viewport meta. All pages extend this.

**0.3 — CSS foundation**
- Create `api/static/styles/app.css` with design tokens from the mockups:
  - Colors: `--color-navy: #1e3a5f`, `--color-bg: #f5f5f1`, etc.
  - Typography: system font stack, sizes (11–14px range).
  - Spacing, border-radius, shadow values.
- Create component CSS files: `titlebar.css`, `sheet.css`, `chat.css`,
  `contextmenu.css`, `dropdown.css`.
- Reusable `.iconbtn`, `.btn-primary`, `.btn-ghost`, `.tag` classes.

**0.4 — Interview notes debug panel**
- Add "Show interview notes" item to the scenario dropdown menu.
- Renders the raw `interview_notes` array as a simple table
  (category | question | answer) in a modal or slide-in panel.
- Available in both Encounter and Verify modes.
- Purpose: debugging and ground-truth inspection during development.

### Phase 1: Home screen

The meta-game screen where the player configures and launches scenarios.

**1.1 — Home page template**
- Create `api/templates/home.html` extending `base.html`.
- Titlebar with hamburger menu (shared component).
- Content area: mode selector, difficulty selector, household pattern
  selector, target concepts grid, Generate + Resume buttons.
- Quick links footer.

**1.2 — Wire to existing API**
- `GET /scenarios/new` renders the new template instead of f-string HTML.
- Mode dropdown: `encounter` (default), `verify`.
- Difficulty dropdown: easy, medium, hard.
- Pattern dropdown: populated from `/api/v1/config/patterns`.
- Concept checkboxes: populated from the concept catalog.
- `POST /scenarios/new` generates scenario and redirects to encounter screen.
- Resume button: loads most recent in-progress scenario from store.

**1.3 — Hamburger menu**
- Shared dropdown component (used on both Home and Encounter screens).
- Items: Home, Scenario Library, My Progress, Preferences, Help, Log out.
- Keyboard shortcut hints displayed but non-functional for now.
- Backdrop click closes menu.

### Phase 2: Encounter screen shell

The structural layout without real form content.

**2.1 — App shell layout**
- Create `api/templates/encounter.html` extending `base.html`.
- Vertical flex layout: titlebar (40px) → main shell (flex: 1) → status bar.
- Main shell: horizontal flex with workspace (flex: 1) + collapsible right
  sidebar.
- All panels collapse cleanly without layout breakage.

**2.2 — Titlebar**
- Left: hamburger + wordmark.
- Center: scenario menu trigger showing scenario ID + mode tag + practice tag.
  Scenario dropdown: Restart, Abandon, Show seed, Show interview notes,
  mode toggle (Tutorial / Practice / Solo).
- Right: chat toggle icon + Submit button.

**2.3 — Page tab strip**
- Four tabs: 1·Personal, 2·Income, 3·Expenses, 4·Optional.
- Active tab highlighted; completed tabs show checkmark.
- Clicking a tab switches the form sheet content (client-side, no page reload).
- Tab state tracked in JS; initial tab set from URL parameter or default to 1.

**2.4 — Status bar**
- Left: scenario ID, current page, fields complete count, flags count.
- Right: contextual hint ("Right-click a field for actions").
- Updated dynamically as the student interacts.

**2.5 — Route wiring**
- `GET /scenarios/{scenario_id}` renders `encounter.html` with scenario data
  passed as Jinja2 context (household, documents, interview notes, ground
  truth reference for debug panel).
- The current exercise overview page is retired. Its content (document links,
  interview notes table, form section cards) is absorbed into the encounter
  screen's panes.

### Phase 3: Form sheet

The faux-paper 13614-C with two-column layout.

**3.1 — Sheet structure**
- Navy banner header: form name, page number, revision.
- Section heads: gray background, bold label.
- Two-column rows: left = client column, right = volunteer column.
- Sheet footer: catalog number, irs.gov, form revision.

**3.2 — Client column (left) — boilerplate-driven**
- Each row renders from an `InterviewNote`:
  - Filled checkbox (■) for answer="Yes", empty (□) for answer="No".
  - Question text as the row label.
  - Follow-up notes indented below (e.g., "How many jobs: 2").
- Notes filtered by category to the active page tab:
  - Page 1: `citizenship`, `filing`, `contact`, `employment`, `dependent`.
  - Page 2: `income`.
  - Page 3: `expenses`, `credits`.
  - Page 4: read-only demographic display (not from notes).
- Category-to-page mapping defined as a constant, not hardcoded per-note.

**3.3 — Volunteer column (right) — input fields**
- Each row has document-type labels and input fields.
- Inputs bound to `data-field` attributes matching `form_fields.py` constants.
- Focus state: dashed orange outline on the active cell.
- Empty-state hints (e.g., "1099-R —") shown when no input expected.
- Page 4 volunteer column is pre-filled and read-only.

**3.4 — Verify mode variation**
- Same sheet structure, but volunteer column arrives pre-filled from the
  scenario's `form_answers` (possibly with injected errors).
- Right-click menu emphasizes Confirm/Flag instead of Record.
- Visual indicator that the column is pre-filled (different background tint).

### Phase 4: Document panes

Multi-pane document viewer with independent tab switching.

**4.1 — Document pane component**
- Reusable panel that displays one document at a time.
- Tab strip at top: one tab per document in the scenario (SSN, DL, W-2 #1,
  W-2 #2, 1099-INT, 1099-NEC, 1098, etc.).
- Tab labels generated from the scenario's document manifest.
- Clicking a tab loads the document HTML fragment into the pane via fetch().
- Active tab highlighted.

**4.2 — Fragment endpoint**
- Modify existing document routes to accept `?fragment=1`.
- When fragment=1, return just the `<div class="document">...</div>` body
  without the `<html>`, `<head>`, `<link>` wrapper.
- Include document-specific CSS inline (already the pattern in templates).
- Existing full-page routes unchanged (no fragment param = full HTML page).

**4.3 — Default layout**
- Default: form sheet on top, two document panes side-by-side on bottom.
- CSS Grid layout, configurable via class swap for future layout presets.
- Each pane independently scrollable.
- Minimum pane size enforced; panes can be collapsed to give more space to
  the form or to a single document.

**4.4 — Document manifest**
- Build a document manifest from the scenario's household:
  ```python
  [
    {"type": "ssn", "label": "SSN · Jane Doe", "url": "/scenarios/.../documents/ssn-card/p-01"},
    {"type": "w2", "label": "W-2 #1 · Acme Corp", "url": "/scenarios/.../documents/w2/p-01/0"},
    ...
  ]
  ```
- Passed to the template as JSON. JS reads it to populate pane tab strips.
- Shared across all document panes (each pane picks independently).

### Phase 5: Right sidebar

Collapsible panel for probes, flags, and notes.

**5.1 — Sidebar shell**
- Three tabs: PROBES, FLAGS, NOTES.
- Collapsible via chat toggle button in titlebar.
- Slides in/out from the right, same animation as the mockup's chat panel.
- Default state: collapsed (maximizes form + document space).

**5.2 — Probes tab (stub)**
- Header: "Available Probes · Contextual".
- Empty state: "Select a field and right-click to see available probes."
- Future: populated with probe options contextual to the focused field.
- Each probe card shows the question text, probe type tag (Dig / Confirm /
  Negative), and field/document reference.

**5.3 — Flags tab (stub)**
- List of fields the student has flagged (out of scope, return visit).
- Empty state: "No flags yet."
- Future: flags affect grading and Vida's coaching.

**5.4 — Notes tab (stub)**
- Free-text scratchpad for the student.
- Persisted in the scenario's session state (localStorage for now).
- No backend integration needed.

### Phase 6: Context menu and interactions

**6.1 — Right-click context menu**
- Summoned by right-clicking any form cell or input in the volunteer column.
- Menu items: Probe about this, Verify against documents, Mark out of scope,
  Flag for return visit, Clear.
- Header shows the field name (from `data-field`).
- Keyboard shortcut hints displayed.
- All actions are stubs (console.log) except Clear (clears the input).

**6.2 — Keyboard shortcuts (stub wiring)**
- Escape closes menus.
- Tab/Shift+Tab navigates form fields.
- Future: P for Probe, V for Verify, etc.

### Phase 7: Submission and grading

**7.1 — Submit flow**
- Submit button in titlebar collects all form inputs from all four pages.
- Confirmation modal: "Submit your work? This cannot be undone."
- POST to existing grading endpoint with the collected field values.
- Locks the scenario (inputs become read-only).

**7.2 — Results display**
- After grading, the form sheet shows per-field feedback inline:
  - Green check for correct fields.
  - Red highlight + expected value for incorrect fields.
- Score summary in the status bar or a results modal.
- Option to start a new scenario or return to home.

---

## What's explicitly deferred

These features are mentioned in the transition doc or mockups but not built
in this plan:

- **Probe interaction logic.** Probe selection, client responses, probe
  grading. Requires the probe system design (not yet written).
- **Vida's coach script.** Tutorial mode procedure walking, coaching
  bubbles, nudge triggers. Requires VIDA_DESIGN implementation.
- **Chat/conversation infrastructure.** Real WhatsApp-styled chat with
  Daniel and Vida. The sidebar replaces the chat panel for now; chat
  ships when probes ship.
- **Layout presets.** View menu with one-pane, two-h, two-v, three-pane
  configurations. Default layout only for now.
- **Multiplayer hand-off.** Contacts list, conversation switching.
- **Progress persistence.** Save/restore mid-scenario state.
- **Scenario library.** Browse and replay past scenarios.
- **Page 4 rendering.** Optional demographics page (low priority, read-only).

---

## File structure (new files)

```
api/
├── templates/
│   ├── base.html              # App shell, CSS/JS links
│   ├── home.html              # Home / scenario generation
│   ├── encounter.html         # Encounter / verify screen
│   └── components/
│       ├── titlebar.html      # Shared titlebar partial
│       ├── hamburger.html     # Hamburger menu partial
│       └── statusbar.html     # Status bar partial
├── static/
│   ├── styles/
│   │   ├── app.css            # Design tokens, reset, base
│   │   ├── titlebar.css       # Titlebar + menus
│   │   ├── sheet.css          # Form sheet (faux paper)
│   │   ├── sidebar.css        # Right sidebar (probes/flags/notes)
│   │   ├── contextmenu.css    # Right-click menu
│   │   ├── document-pane.css  # Document viewer panes
│   │   └── home.css           # Home page specific
│   └── js/
│       ├── encounter.js       # Encounter screen logic
│       ├── menus.js           # Dropdown/context menu handling
│       ├── document-pane.js   # Document loading + tab switching
│       ├── sidebar.js         # Sidebar toggle + tab switching
│       └── home.js            # Home page logic
```

---

## Implementation order

Smallest working delta at each step. The product remains usable between steps.

| Step | Phase | Deliverable | Dependencies |
|------|-------|-------------|--------------|
| 1 | 0.1 | Mode rename (intake → encounter) | None |
| 2 | 0.2–0.3 | Template + CSS infrastructure | Step 1 |
| 3 | 1.1–1.3 | Home screen | Step 2 |
| 4 | 2.1–2.5 | Encounter shell (titlebar, tabs, status bar) | Step 2 |
| 5 | 3.1–3.3 | Form sheet with boilerplate left column | Step 4 |
| 6 | 4.1–4.4 | Document panes with tab switching | Step 4 |
| 7 | 5.1–5.4 | Right sidebar (stub) | Step 4 |
| 8 | 6.1–6.2 | Context menu (stub) | Step 5 |
| 9 | 3.4 | Verify mode variation | Step 5 |
| 10 | 7.1–7.2 | Submission + grading flow | Step 5 |
| 11 | 0.4 | Interview notes debug panel | Step 4 |

Steps 5, 6, and 7 can be developed in parallel after step 4 completes.
Step 8 requires step 5 (needs form fields to attach to).
Steps 9 and 10 require step 5 (need the form sheet).
Step 11 can happen any time after step 4.

---

## Migration notes

- The current f-string HTML pages in `scenarios.py` are not deleted
  immediately. New routes are added alongside old ones. Once the new UI is
  stable, old routes are removed in a cleanup pass.
- Existing JSON API routes (`/api/v1/...`) are unchanged.
- Document rendering templates (`training/templates/`) are unchanged except
  for adding fragment support (Phase 4.2).
- The grader, ground truth, boilerplate, and concept systems are unchanged.
- Test coverage for the new routes: integration tests that verify the
  templates render without error and contain expected elements (scenario ID,
  form fields, document tabs). Not pixel-level UI tests.
