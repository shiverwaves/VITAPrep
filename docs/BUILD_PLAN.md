# Build Plan — Step-by-Step Implementation Guide

This document is the chronological "what to build next" guide for VITAPrep. It is paired with [`SCENARIO_LIFECYCLE.md`](./SCENARIO_LIFECYCLE.md), which describes the target architecture and data flow this build plan converges toward. Read the lifecycle doc first if you are new to the project or picking up a sprint and need the conceptual frame.

---

## Architecture overview

VITAPrep is organized as three logical layers. They live in one repository at the MVP stage but are designed for eventual separation into independent products (e.g. a return-preparation engine, an intake simulator, and a curriculum/progression layer).

### `tax_core` — the rules engine

Pure functions over scenario data. No UI, no narrative, no curriculum logic. Encodes tax-law predicates, threshold lookups, classification tests, and computation routines. Examples: `qualifying_child_residency_test()`, `is_self_employment_threshold_met()`, `filing_threshold_for(status, year)`.

`tax_core` is the source of truth for what is correct. The scenario generator (when computing ground truth) and the grader (when evaluating submissions) both call into the same `tax_core` functions. There is exactly one definition of correctness per rule. `tax_core` has no dependencies on the layers above it.

### `intake` — scenario generation and presentation

Consumes `tax_core`. Generates coherent households, runs the analyzer to attach narrative cover to generated facts, renders documents, and produces the obfuscated interview-notes view the player sees. Does not know about concepts, learner progression, or curriculum.

### `learn` — curriculum and progression

Consumes both layers below. Owns the concept catalog (predicate-based labels for tax-law features), concept-driven generation requests, player progression, and grading. The only layer that knows what a "concept" is.

### How the original sprint structure relates to this

The completed sprints were authored before the three-layer split was made explicit. They remain valid as a chronological record. They cut vertically (by feature) where the new architecture cuts horizontally (by layer). Most existing sprints map cleanly onto `intake`. The restructuring sprints (A–E, below) carve out `tax_core` and `learn` as separate concerns and migrate code accordingly. New work after Sprint 9 should follow the layered structure.

---

## Completed sprints (summary)

These sprints have been implemented. Detail lives in code; this section is a quick map of what exists and where it'll move during restructuring. Update this section when sprints are reordered or rescoped.

| Sprint | Scope | Current location | Target location |
|---|---|---|---|
| 1 — Data Models + Sampling | `Person`, `Household`, `FilingUnit`, enums, `PATTERN_METADATA`, `weighted_sample`, bracket parsing, seed control | `generator/models.py`, `generator/sampler.py` | `intake/generator/models.py`, `intake/generator/sampler.py` |
| 2 — Database Layer + Part 1 Extraction | SQLite distribution loader, PUMS download/cache, 12 Part 1 distribution tables (household patterns, race, age, partner, etc.) | `generator/db.py`, `extraction/pums_download.py`, `extraction/extract_part1.py` | `intake/generator/db.py`, `extraction/` (unchanged) |
| 3 — Part 1 Generators | Demographics generator (adults: age, sex, race, relationships), child generator, pipeline orchestration | `generator/demographics.py`, `generator/children.py`, `generator/pipeline.py` | `intake/generator/*` |
| 4 — PII Generator | Names, SSNs (test range), DOBs, addresses, ID documents, phone/email overlay onto generated households | `generator/pii.py` | `intake/generator/pii.py` |
| 5 — Document Rendering + Templates | Jinja2 templates for SSN cards, driver licenses, Form 13614-C; HTML-to-image rendering | `training/templates/`, `training/document_renderer.py` | `intake/document_renderer.py`, `intake/templates/` |
| 6 — Error Injection + Grading | Error injector for pre-filled forms, grader, exercise engine, scenario store | `training/error_injector.py`, `training/grader.py`, `training/exercise_engine.py`, `training/scenario_store.py` | Split: error injection → `intake/modes/review.py`; grader → `learn/grader.py`; scenario store → `intake/scenario_store.py`; exercise engine → split between `intake/` and `learn/` |
| 7 — API | FastAPI app, scenario/config/progress routes, CLI for scenario generation | `api/`, `cli.py` | `api/` (unchanged), `cli.py` (unchanged) |
| 8 — Web UI | Document viewer + interactive intake form (Phase 2 — partial / in progress) | `web/` or equivalent | unchanged |
| 9 — Part 2 Income | Employment/income extraction (12 Part 2 distribution tables), employment generator (status, education, occupation, disability), income generator (wages, withholding, all document types), income document templates (W-2, 1099-INT/DIV/R/NEC, SSA-1099), Part II form fields, populator, grader, error injector, and API routes | `extraction/extract_part2.py`, `generator/employment.py`, `generator/income.py`, `training/templates/w2.html`, `training/templates/1099_*.html`, `training/templates/ssa_1099.html`, `training/form_fields.py`, `training/form_populator.py` | `intake/generator/*`, `intake/templates/*` |
| 10 — Multi-Section Intake UI | Section-aware forms (Part I, Part II) with per-section navigation bar, independent per-section submission and grading, landing page score cards with grade status badges, document grouping by type (identity vs income) | `api/routes/scenarios.py` | `api/routes/scenarios.py` (unchanged) |
| 12 — Part 3 Expenses | Part 3 extraction (3 tables: `homeownership_rates`, `property_taxes`, `mortgage_costs`), expense generator (housing, state tax, medical, charitable, above-the-line deductions, credits, standard vs itemized determination), Form 1098/1098-E/1098-T templates and rendering, Part III form field constants, form populator, grader answer key, Part III form route and section navigation | `extraction/extract_part3.py`, `generator/expenses.py`, `generator/pipeline.py`, `training/templates/form_1098*.html`, `training/form_fields.py`, `training/form_populator.py`, `training/grader.py`, `api/routes/scenarios.py` | `intake/generator/expenses.py`, `intake/templates/form_1098*.html`, `extraction/` (unchanged) |
| Post-Sprint 12 Fixes | **(12.H)** Data inventory Part 3 support: corrected Part 2 table names, added `PART3_TABLES` classification, added `part3_complete` flag; added descriptive captions to GitHub Actions data-management workflow inputs. **(12.I)** Document deserialization: reconstructed all 9 income/expense document types in `_deserialize_person()` (W-2, 1099-INT/DIV/R/NEC, SSA-1099, Form 1098/1098-E/1098-T), added `_deserialize_w2()` and `_deserialize_employer()` helpers, added missing Household expense fields (`is_homeowner`, `total_itemized_deductions`, `total_above_line_deductions`, `uses_standard_deduction`) | `scripts/data_inventory.py`, `.github/workflows/data-management.yml`, `training/scenario_store.py` | `scripts/data_inventory.py` (unchanged), `intake/scenario_store.py` |

If sprint scope drifted from the original plan during implementation, edit the table to match reality before working through the restructuring sprints. The migrations in A–E assume this table is accurate.

---

## Vocabulary shifts

Where old terms map to new ones. Use this when reading old code or comments.

| Old term | New term | Lives in |
|---|---|---|
| `training/` | split between `intake/` (rendering, modes) and `learn/` (grading, progression) | — |
| "Error injection" | "Review mode corruption" | `intake/modes/review.py` |
| "Exercise engine" | Lifecycle orchestrator | `intake/orchestrator.py` (new) |
| "Profile" or raw `Household` | `Scenario` (envelope object — wraps household and adds ground truth, concepts, slots, notes) | `intake/scenario.py` (new) |
| "Difficulty" as info-hiding | Subtlety dial on obfuscation layer + concept count/complexity | per-slot, per-concept |
| "Answer key" | `ground_truth` field on `Scenario` | `tax_core/ground_truth.py` |

---

## Restructuring sprints

These sprints carve out the layered architecture without rewriting the engine. Each produces a working system. Do not skip ahead.

### Restructure A: Carve out `tax_core`

**Goal:** Establish the rules-engine layer as a pure, dependency-free module.

**Prerequisites:** Sprints 1–3 complete (existing code has tax-rule logic worth extracting).

**Line-drawing principle:** Would this function be called during preparation of an actual return against real client data? If yes → `tax_core`. If it exists only to fabricate plausible documents or scenarios → `intake`. When ambiguous, ask: is this a fact about the return we'd compute, or about a document we'd fabricate?

**Operation:**

1. Create `tax_core/` at the repo root.
2. Identify all tax-rule logic currently embedded in generators, the grader, the error injector, or anywhere else, applying the line-drawing principle above. The extraction targets below are specific to the current codebase as of Sprint 12.
3. Move that logic into `tax_core/` modules:
   - `tax_core/predicates/filing_status.py` — filing status derivation (currently `Household.derive_filing_status()` in `generator/models.py`)
   - `tax_core/predicates/dependency.py` — dependency tests (qualifying child/relative)
   - `tax_core/predicates/income.py` — income classification predicates
   - `tax_core/predicates/deductions.py` — standard vs itemized comparison logic (currently in `ExpenseGenerator._calculate_totals()` in `generator/expenses.py`)
   - `tax_core/thresholds.py` — SALT cap ($10K), standard deduction amounts by filing status, IRA contribution limits, student loan interest limit, educator expense limit (currently module-level constants in `generator/expenses.py`)
   - `tax_core/state_tax/hawaii.py` — Hawaii state tax brackets and progressive tax calculation (currently `HAWAII_TAX_BRACKETS_SINGLE`, `HAWAII_TAX_BRACKETS_MFJ`, and `_assign_state_income_tax()` in `generator/expenses.py`). State-specific tax law is still tax law; the fact that it varies by state doesn't change its category. This structure (`tax_core/state_tax/<state>.py`) supports adding other states later.
4. Replace the original call sites with imports from `tax_core`. The behavior must not change — this is a reorganization, not a rewrite.
5. **Stays in `intake`:** Income withholding calculation (`generator/income.py`). On a real return, withholding is *read* from a W-2, not computed. The calculation exists only to make the W-2 document look realistic — that's a generation concern.
6. Add unit tests in `tests/tax_core/` that exercise predicates against hand-built `Household` fixtures. These tests are the regression suite for every future change.

**Output:**

- `tax_core/` exists with predicates, thresholds, state tax modules, and tests.
- The import graph is clean: nothing under `tax_core/` imports from `intake/`, `learn/`, or `api/`. Enforce this in CI if practical (e.g., via `grep` in a pre-commit check).

**Checkpoint:** All existing tests pass. The import graph constraint holds. `tax_core` is independently importable.

**Failure mode to watch for:** The temptation to "improve" predicates while moving them. Resist. Move first, refactor in a follow-up sprint if warranted.

---

### Restructure B: Add ground truth computation

**Goal:** Every generated scenario carries a canonical answer key from the moment of creation.

**Prerequisites:** Restructure A complete.

**Serialization contract (bake in from day one):**

The scenario store (Fix 12.I) already demonstrated the cost of relying on `dataclasses.asdict()` for serialization without matching deserialization. `GroundTruth` must not repeat that pattern:

1. `GroundTruth` gets explicit `to_dict()` and `from_dict()` methods (or a trusted serialization library). Never rely on `__dict__`, `asdict()` alone, or pickle.
2. Include a `schema_version: int` field from the first commit. Future predicate changes will produce different ground-truth shapes; the store must refuse mismatched versions cleanly rather than silently loading stale truth against a newer grader.
3. Round-trip serialization tests (`to_dict → JSON → from_dict → assert equal`) are part of B's checkpoint, not a follow-up.

**Operation:**

1. Add `tax_core/ground_truth.py` with a function `compute_ground_truth(scenario) -> GroundTruth`.
2. The function runs `tax_core` predicates and computations over a generated scenario's facts and produces a structured object containing: `filing_status`, per-person `dependent_status`, `agi`, `taxable_income`, `total_tax`, `refund_or_owed`, `credits_claimed`, `deductions_claimed`, plus per-predicate detail objects where the predicate returns rich results.
3. Wire `compute_ground_truth` into the generation pipeline immediately after generation completes.
4. Add a `ground_truth` field to the `Scenario` envelope (introduce the envelope here if it doesn't exist yet — it wraps the existing `Household` plus lifecycle metadata).
5. Migrate the grader to compare submissions against `scenario.ground_truth` instead of recomputing answers ad-hoc.
6. Update `scenario_store.py` to serialize/deserialize `GroundTruth` using the explicit `to_dict()`/`from_dict()` methods, checking `schema_version` on load.

**Output:**

- Every scenario has `ground_truth` populated before being served.
- The grader has exactly one source of truth.
- `GroundTruth` round-trips cleanly through the scenario store.

**Checkpoint:** Generate a scenario, inspect `ground_truth`, hand-verify the values are correct against the household's facts. Run a submission through the grader and confirm it scores against `ground_truth`. Serialize the scenario to SQLite, reload it, and confirm `ground_truth` survives intact with correct `schema_version`.

**Failure mode to watch for:** Ground truth drifting from what the grader actually compares to. If you find yourself adding logic to the grader that should be in `compute_ground_truth`, move it.

---

### Restructure C1: Analyzer framework and starter slots (additive)

**Goal:** Build the slot-based analyzer that produces narrative cover for generated facts. Wire it into the pipeline alongside the existing interview-notes path. The old path continues to work; nothing changes for the player.

**Prerequisites:** Restructure B complete. Read the Stage 3 and Stage 6 sections of `SCENARIO_LIFECYCLE.md` before starting.

**Operation:**

1. Create `intake/analyzer/` with `analyzer.py` (orchestrator) and `slots/` (one module per slot family).
2. Define the `Slot` and `NarrativeTemplate` base classes per the worked example in `SCENARIO_LIFECYCLE.md`.
3. Implement three starter slots covering the highest-frequency cases:
   - `zero_income_reason` — fires when a person has zero total income.
   - `dependent_residency` — fires when a child's `months_in_home < 12`.
   - `address_mismatch` — fires when an ID address differs from the household address.
4. For each slot, implement at least three narrative templates with distinct `requirements()` predicates. Each template produces `InterviewNote` objects at three subtlety levels (`obvious`, `moderate`, `subtle`).
5. Add the analyzer to the pipeline. It runs after generation, before ground truth. Populate `scenario.narrative_slots` on every scenario. If a fired slot has zero matching templates, raise `Unrescuable` and let the orchestrator reroll.
6. Build the obfuscator (`intake/obfuscator.py`) that calls each fired template's `render()` method at the chosen subtlety and assembles `scenario.interview_notes`. Store the result on the scenario but **do not yet wire it to the UI**.

**Output:**

- Every scenario carries `narrative_slots` and new-path `interview_notes`.
- The player UI still reads the old hardcoded interview structure (unchanged).
- Unrescuable scenarios trigger reroll instead of being served.

**Checkpoint:** Generate ten scenarios. Confirm `narrative_slots` and new-path `interview_notes` are populated, vary across scenarios, make narrative sense, and never contradict the generated facts. At least one should trigger a reroll due to slot failure (induce this with a constrained generation if needed). All existing tests still pass — the old UI path is untouched.

**Failure mode to watch for:** Templates that lie about ground truth. The obfuscation layer must preserve truth — it can introduce ambiguity, not contradictions.

**Ships as:** Separate PR from C2. At the end of C1, the new pipeline is running and testable but invisible to the player.

---

### Restructure C2: Swap to analyzer-driven interview notes (substitution)

**Goal:** Replace the old hardcoded interview-notes path with the analyzer-driven path from C1. Delete the old code.

**Prerequisites:** C1 merged and stable.

**Operation:**

1. Update the player UI to read from `scenario.interview_notes` (the analyzer-driven field) instead of the old hardcoded interview structure.
2. Delete the old interview-notes generation code.
3. Verify all exercise modes (intake and verify) work against the new path.

**Output:**

- The player UI is reading the new analyzer-driven path.
- The old hardcoded interview-notes path is gone.

**Checkpoint:** Full player flow works: generate scenario → review documents → read interview notes → fill form → submit → grade. Interview notes vary by scenario and subtlety level. No references to the old interview path remain in the codebase.

**Failure mode to watch for:** Edge cases where the old path produced notes that the new analyzer doesn't cover yet (e.g., expense-related interview facts — see Future: Scenario Validation). Audit the old path's output before deleting to ensure coverage parity or document known gaps.

**Ships as:** Separate PR from C1. Independently revertible if the swap reveals issues in production.

---

### Restructure D: Concept catalog (generate-then-tag)

**Goal:** Every scenario carries metadata identifying which tax-law features it exercises.

**Prerequisites:** Restructure C complete.

**Operation:**

1. Create `learn/concepts/` with one module per concept family (`dependency.py`, `filing_status.py`, `income.py`, `deductions.py`).
2. Define the `Concept` base class with `matches(scenario) -> bool` and `generation_hints() -> GenerationHints` methods.
3. Implement a starter set of three concepts for initial validation:
   - `qualifying_child_residency`
   - `hoh_qualifying_person`
   - `refundable_credit_only_filer`
4. Add `learn/concept_catalog.py` with an explicit registry (no autodiscovery) and a `run_all(scenario) -> set[str]` method.
5. Wire concept labeling into the pipeline at Stage 5 (after ground truth, before obfuscation rendering). Every scenario gets `concept_tags` populated.
6. Surface concept tags in the post-game screen (or wherever grading results are shown). The player sees what they were tested on after submission.

**Output:**

- Every scenario has `concept_tags` populated.
- Post-game UI shows which concepts were exercised.

**Checkpoint:** Generate twenty scenarios and inspect their concept tags. Confirm the tags actually correspond to features present in the scenario. A scenario with a borderline-residency child should fire `qualifying_child_residency`; a scenario without one should not.

**Failure mode to watch for:** Concepts that fire too eagerly (false positives) or too rarely (false negatives). Predicates need to be exact; "almost" doesn't count.

---

### Restructure E: Targeted generation

**Goal:** Players can request scenarios that exercise specific concepts.

**Prerequisites:** Restructure D complete. This is the most fragile sprint and should not be attempted until A–D are stable in production.

**Operation:**

1. Add a `concepts` parameter to the `ScenarioRequest` model.
2. In the orchestrator, when concepts are requested, query their `generation_hints()` and merge into the generator's hint object.
3. After generation, verify all requested concepts actually fired (in Stage 5). If not, reroll with a new seed up to `MAX_GEN_ATTEMPTS`.
4. Surface the concept selector in the scenario-generation UI — replace the old "Difficulty: easy/medium/hard" dropdown with a concept picker plus a subtlety slider.
5. Document the failure path: if `MAX_GEN_ATTEMPTS` is exhausted, surface a clear error to the player ("This concept combination is too rare or contradictory; try fewer concepts").

**Output:**

- Concept-driven generation works end to end.
- The UI exposes it cleanly.

**Checkpoint:** For each starter concept, request a scenario targeting only that concept and verify the resulting scenario fires it. Then request two concepts simultaneously and verify both fire. Then request a deliberately incompatible pair and confirm graceful failure.

**Failure mode to watch for:** Generation hints from different concepts conflicting silently. Add hint-conflict detection (or document that last-write-wins is the policy) before this sprint ships.

---

## A–E coverage of post-Sprint 9 code

The restructuring sprints were originally scoped when Sprint 9 was the frontier. Sprints 10, 12, and post-sprint fixes added code surfaces that the migrations must cover. This section confirms where each new surface lands.

| New code surface | Introduced in | Migration | Notes |
|---|---|---|---|
| `generator/expenses.py` — Hawaii tax brackets, SALT cap, standard deduction thresholds, standard vs itemized comparison | Sprint 12 | **A** | Tax-law constants and deduction-type determination → `tax_core/thresholds.py`, `tax_core/state_tax/hawaii.py`, `tax_core/predicates/deductions.py`. The expense *generation* logic (sampling housing costs, medical probability, charitable rates) stays in `intake`. |
| `generator/expenses.py` — withholding-style fabrication logic | Sprint 12 | stays in `intake` | Same principle as income withholding: exists to make documents look realistic, not to compute return values. |
| `generator/models.py` — `Household.derive_filing_status()` | Sprint 1 (updated through Sprint 12) | **A** | Filing status derivation is a tax-law predicate → `tax_core/predicates/filing_status.py`. `Household` retains a thin wrapper that delegates to `tax_core`. |
| `training/form_fields.py` — Part 3 field constants | Sprint 12 | stays in `intake` | Field constants define the UI contract, not tax rules. The grader's use of thresholds (standard deduction lookup) migrates to `tax_core` calls in **A**; the field names themselves stay. |
| `training/grader.py` — `_build_expense_key()` standard vs itemized logic | Sprint 12 | **B** | Currently recomputes the answer inline. After **B**, reads from `scenario.ground_truth` instead. |
| `training/form_populator.py` — expense field population | Sprint 12 | stays in `intake` | Presentation concern: populates form fields for verify mode. |
| `api/routes/scenarios.py` — multi-section routing, Part III form/grading | Sprint 10, Sprint 12 | stays in `api` | Routing is pure API/UI. No tax-rule logic to extract. |
| `training/scenario_store.py` — document deserialization (12.I) | Post-Sprint 12 | stays in `intake` | The `to_dict()`/`from_dict()` patterns established here inform **B**'s `GroundTruth` serialization design. |
| `scripts/data_inventory.py`, `.github/workflows/data-management.yml` | Post-Sprint 12 (12.H) | unchanged | Tooling; not part of the runtime layering. |

Everything folds in cleanly. No new migration steps are needed beyond what A–E already describe; the new code surfaces are additional extraction targets within existing operations.

---

## Beyond restructuring

Once A–E are complete, new work follows the layered structure naturally:

- New tax rules → new predicates in `tax_core/predicates/`.
- New scenario types → new generation hints + slots in `intake/`.
- New training drills → new concepts in `learn/concepts/`.
- New form sections (Part IV, Part V, etc.) → cross-layer additions, but each layer's contribution is local.

Each future VITA section follows the existing pattern: extract distributions → generate facts → render documents → analyze and obfuscate → tag concepts → grade.

---

## Testing surface

Each layer has its own test directory:

- `tests/tax_core/` — unit tests of predicates and computations against hand-built scenarios.
- `tests/intake/generator/` — existing generator tests; no change.
- `tests/intake/analyzer/` — slot firing logic and template requirement matching.
- `tests/intake/obfuscator/` — snapshot tests on rendered interview notes per subtlety level.
- `tests/learn/concepts/` — each concept tested against scenarios that should and should not match.
- `tests/end_to_end/` — full lifecycle smoke tests producing scenarios from fixed seeds and asserting all expected fields populated.

Add the import-graph check (`tax_core` must not import from `intake` or `learn`) to CI as a separate test or pre-commit hook.

---

## Open questions

These are not decided here. Resolve in code, then update this document.

- Whether to use Python `random.Random` instances or NumPy generators throughout.
- Whether `tax_core` predicates return rich result objects or simple booleans (the worked example used rich; revisit per predicate).
- How concept hints merge when multiple target concepts conflict (last-wins, error, soft preference).
- Where document corruption manifests live for Review mode (in `Scenario` or sidecar table).
- Subtlety dial: global per scenario, per slot, or per concept? Pick one when implementing Restructure C.
- Concept catalog registration: explicit list vs decorator-based vs autodiscovery. Recommend explicit list for MVP.
