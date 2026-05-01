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

**Reference:** [`CONCEPT_CATALOG.md`](./CONCEPT_CATALOG.md) — the "Predicate inventory for `tax_core`" section is the authoritative work order. The MVP predicates list (18 predicates) and infrastructure predicates list define what goes into `tax_core`. This sprint section summarizes the tasks; the catalog has the details.

**Line-drawing principle:** Would this function be called during preparation of an actual return against real client data? If yes → `tax_core`. If it exists only to fabricate plausible documents or scenarios → `intake`. When ambiguous, ask: is this a fact about the return we'd compute, or about a document we'd fabricate?

**Operation — two phases, same sprint:**

Restructure A is both a **move** (extracting existing tax logic) and a **build** (implementing new predicates the concept catalog requires). The move is low-risk mechanical work. The build involves encoding tax law and needs careful testing. Both phases ship together because the new predicates depend on the infrastructure the move establishes.

#### Phase 1: Move existing tax logic (mechanical)

1. Create `tax_core/` at the repo root with `__init__.py`, `thresholds.py`, `predicates/`, and `state_tax/`.
2. **`tax_core/thresholds.py`** — Move all year-indexed constants from `generator/expenses.py`: `STANDARD_DEDUCTION`, `SALT_CAP`, `IRA_CONTRIBUTION_LIMIT`, `IRA_CONTRIBUTION_LIMIT_50_PLUS`, `STUDENT_LOAN_INTEREST_LIMIT`, `EDUCATOR_EXPENSE_LIMIT`. Structure as year-keyed lookups, not bare constants.
3. **`tax_core/state_tax/hawaii.py`** — Move `HAWAII_TAX_BRACKETS_SINGLE`, `HAWAII_TAX_BRACKETS_MFJ`, and the progressive tax calculation from `ExpenseGenerator._assign_state_income_tax()`. Add a dispatch function (`compute_state_income_tax(income, filing_status, state, year)`) so other state modules can be added later. **Multi-state support is deferred** — Hawaii moves as-is. See "Future: State Tax Generalization" for the expansion plan.
4. **`tax_core/predicates/filing_status.py`** — Move `Household.derive_filing_status()` logic. The `Household` method becomes a thin wrapper that delegates to `tax_core`.
5. **`tax_core/predicates/deductions.py`** — Move the SALT cap application, medical 7.5% AGI floor, itemized total aggregation, and standard-vs-itemized comparison from `ExpenseGenerator._calculate_totals()`. The expense generator calls these functions instead of doing the math inline.
6. Replace all original call sites with imports from `tax_core`. Behavior must not change.
7. **Stays in `intake`:** Income withholding calculation (`generator/income.py`). On a real return, withholding is *read* from a W-2, not computed. The calculation exists only to make documents look realistic.

**Phase 1 checkpoint:** All existing tests pass. `tax_core/` is independently importable. The import graph is clean: nothing under `tax_core/` imports from `generator/`, `training/`, `api/`, or any future `intake/`/`learn/` path.

#### Phase 2: Implement MVP predicates (new code)

Implement the 18 MVP predicates listed in [`CONCEPT_CATALOG.md` § "MVP predicates"](./CONCEPT_CATALOG.md#mvp-predicates-restructure-a-first-pass). These are net-new `tax_core` functions that don't exist in the codebase today.

**Accuracy tiers.** Not all 18 predicates require the same level of tax-law scrutiny. The table below classifies each by how much work is needed now vs what can be deferred.

| Tier | Description | Count | Approach |
|---|---|---|---|
| **Exact** | Arithmetic or table lookups. Hard to get wrong. | 8 | Implement fully, cite source in docstring. |
| **Stub** | Simplified version works for scenarios we generate today. Full rule requires data or edge cases we don't yet produce. | 7 | Implement simplified logic. Docstring notes what's simplified and cites the IRC section for the full rule. Refine incrementally as generation capabilities expand. |
| **Careful** | Requires faithful encoding of an IRS worksheet or multi-step rule. Getting it wrong produces wrong grading. | 3 | Implement against the IRS publication worksheet. Test with worked examples from the publication. |

**Exact (8) — implement fully:**
- `standard_deduction_for(status, year)` — lookup table, 2022 values already in `expenses.py`
- `compute_salt(state_tax, property_tax, year)` — `min(total, 10000)`
- `compute_medical_deduction(medical_expenses, agi)` — `max(0, expenses - agi * 0.075)`
- `compute_itemized_total(household, year)` — aggregation of Schedule A categories
- `should_itemize(household, year)` — comparison of itemized total vs standard deduction
- `total_income(person)` — sum of income fields, already exists as `Person.total_income()`
- `total_self_employment_income(person)` — sum of 1099-NEC amounts
- `requires_schedule_se(person)` — `se_income >= 400`

**Stub (7) — simplified now, refine later:**
- `derive_filing_status(household)` — current logic (married → MFJ, has kids → HoH, else single) is wrong for edge cases (HoH requires more than just having children) but correct for the household patterns we generate today. Refine when `hoh_qualifying_person` concept is drilled.
- `is_unmarried(filer, year)` — stub as "no spouse in household." Full rule includes "considered unmarried" status (lived apart last 6 months with dependent child), which requires data we don't generate yet.
- `paid_more_than_half_household_costs(filer, household)` — stub as `True` for single-adult households. We don't generate cost-of-household data. Document as a known gap.
- `has_qualifying_person_for_hoh(filer)` — depends on residency and relationship tests. Can compose from simplified versions of those tests.
- `qualifying_child_residency_test(child, year)` — core "more than half the year" test is straightforward using `months_in_home`. Temporary absence exceptions (school, illness, military, kidnapping) deferred — we don't generate those scenarios yet.
- `qualifying_relative_test(person, household)` — four-part test (relationship, gross income under threshold, support, not a QC of another). Implement the parts we have data for (relationship, gross income); stub the support test as `True` for now.
- `qualifies_for_eitc(filer, year)` / `qualifies_for_actc(filer, year)` — explicitly stubs (qualifying child + earned income > 0). Full EITC rules are a P2 concept (`eitc_qualifying_child_rules`).

**Careful (3) — requires IRS worksheet fidelity:**
- `filing_threshold_for(status, year)` — straightforward lookup but the values must be exact for each year and filing status. Source: IRS Publication 501, Table 1.
- `compute_provisional_income(filer)` — AGI + tax-exempt interest + ½ SS benefits. We don't generate tax-exempt interest, so for current scenarios it simplifies to `income + ss/2`. Document that tax-exempt interest is a known gap.
- `ss_taxability_thresholds(filing_status, year)` / `compute_taxable_ss(filer, year)` — must faithfully encode the two-tier IRS Publication 915 worksheet (~10 steps). Test against worked examples from the publication. The MFS-living-with-spouse edge case (zero threshold, 85% taxable) must be handled correctly.

**Steps:**

8. **`tax_core/predicates/filing_status.py`** — Add `is_unmarried` (stub), `paid_more_than_half_household_costs` (stub), `has_qualifying_person_for_hoh` (stub). Each docstring cites IRC §2(b) and notes what's simplified.
9. **`tax_core/predicates/dependency.py`** — Add `qualifying_child_residency_test` (stub — core test only, no temporary absence exceptions), `qualifying_relative_test` (stub — relationship + gross income, support test deferred). Return structured results (pass/fail + detail) so grader and slots can inspect *why*.
10. **`tax_core/predicates/income.py`** — Add exact predicates (`total_income`, `total_self_employment_income`, `requires_schedule_se`, `filing_threshold_for`) and careful predicates (`compute_provisional_income`, `ss_taxability_thresholds`, `compute_taxable_ss`). SS taxability tested against IRS Pub 915 worksheet examples.
11. **`tax_core/predicates/deductions.py`** — Add all 5 deduction predicates (all exact tier).
12. **Refundable credit stubs** — `qualifies_for_eitc` and `qualifies_for_actc` as documented stubs.
13. Add unit tests in `tests/tax_core/` for every predicate, using hand-built `Household` fixtures. Test boundary cases explicitly (6 months exactly fails residency, $399 SE income below threshold, provisional income at each SS tier, itemized total $1 above/below standard deduction). Careful-tier predicates get additional tests against IRS publication worked examples. These tests are the regression suite for every future change.

**Phase 2 checkpoint:** All 18 predicates pass their unit tests. Import graph constraint still holds. Every stub-tier predicate has a docstring noting its simplification and the IRC section governing the full rule.

**Relationship to a tax engine.** Individual predicates are better written by hand — they're testable, auditable, and cite specific IRC sections. An open-source tax engine becomes relevant in **Restructure B** when we compute full ground truth (AGI → taxable income → total tax → refund). That's a return-level computation chaining dozens of rules; a tax engine may be more maintainable than hand-rolling it. The decision belongs in B's scope, not A's. See "Future: Tax Engine References" for the candidates.

**Output:**

- `tax_core/` exists with predicates, thresholds, state tax modules, and tests.
- Existing generators and grader import from `tax_core` instead of defining tax logic locally.
- The import graph is clean: nothing under `tax_core/` imports from `intake/`, `learn/`, or `api/`. Enforce this in CI (e.g., `grep` in a pre-commit check or a dedicated test).
- Every stub-tier predicate is documented: what's simplified, what IRC section governs the full rule, and what data/generation capability is needed to remove the simplification.

**Final checkpoint:** All existing tests pass. All new predicate tests pass. `tax_core` is independently importable. The concept catalog's MVP predicate inventory is fully implemented (exact, stub, or careful as classified).

**Failure mode to watch for:** The temptation to "improve" predicates while moving them in Phase 1. Resist. Move first, build new in Phase 2. Refactor in a follow-up if warranted. For Phase 2: the temptation to implement the full rule when a stub suffices. Stubs are deliberate — they match the scenarios we can currently generate. Over-engineering a predicate against edge cases we can't test is worse than a documented simplification.

---

### Restructure B: Ground truth computation + Scenario envelope

**Goal:** Every generated scenario carries a canonical answer key from the moment of creation. The grader consumes it directly with zero domain logic of its own.

**Prerequisites:** Restructure A complete (predicates and thresholds exist in `tax_core`).

#### Design decisions

**GroundTruth shape — three layers.**

`GroundTruth` contains three layers of content, each with a different rationale:

1. **Return-level answers** — the values a grader needs to score a submission. Filing status, AGI, taxable income, total tax, refund or balance due, deduction type (standard vs itemized), standard deduction amount, itemized total, credits claimed. These are the things the player ultimately enters.
2. **Per-person classifications** — for each person, their role on the return. Primary filer, spouse, or dependent? If dependent, qualifying child or qualifying relative? What credits do they generate (CTC, ODC, EITC qualifying child)? This is what dependency-related grading consumes.
3. **Predicate detail snapshots** — the structured results returned by rich-result predicates. `qualifying_child_residency_test` returns months and exception flags; that whole result object is stored, not just the boolean. Any predicate where the *why* matters for grading feedback or concept evaluation stores its full result.

Two fields that aren't strictly tax answers but earn their place because they're cheap to capture and expensive to recompute: `tax_year` (so the grader knows which thresholds applied) and `schema_version` (so future predicate changes don't silently grade against stale truth — the store refuses mismatched versions).

What `GroundTruth` deliberately does **not** contain: narrative content, concept tags, document references. Those live elsewhere on `Scenario`. `GroundTruth` is the answer key, nothing more.

```python
@dataclass
class GroundTruth:
    schema_version: int
    tax_year: int

    # Return-level
    filing_status: FilingStatus
    agi: int
    taxable_income: int
    total_tax: int
    refund_or_owed: int
    deduction_type: Literal["standard", "itemized"]
    standard_deduction: int
    itemized_deduction_total: int
    credits_claimed: dict[str, int]   # "ctc": 2000, "eitc": 0, etc.

    # Per-person
    person_classifications: dict[str, PersonClassification]  # keyed by person_id

    # Predicate detail
    predicate_results: dict[str, Any]   # keyed by predicate name
```

The dict-keyed-by-name pattern for `predicate_results` is intentional. It keeps `GroundTruth` extensible — adding a new rich-result predicate doesn't require schema changes — at the cost of being slightly less type-safe. Worth it for MVP.

**Grader consumption — direct, no fallback.**

The fallback pattern ("use `ground_truth` if present, else recompute") is tempting but is a trap. Two code paths with different bug surfaces silently drift apart. The only reason to need a fallback is if you don't trust ground truth — which means the actual problem (persistence or computation) needs fixing at the source, not papering over.

Implications:
- Every `Scenario` must have `ground_truth` populated before grading. This is a precondition, asserted early. Scenarios without ground truth are bugs.
- Scenarios persisted before B ships won't have `ground_truth`. Invalidate them — generated scenarios are cheap. Add a check at scenario-load time that refuses scenarios without `ground_truth` or with mismatched `schema_version`.
- The grader's job simplifies dramatically: "compare submission to `ground_truth`" with zero domain logic. Any tax-rule reasoning previously in the grader migrates to `tax_core` during A or B.

**Computation approach — hand-roll the orchestration.**

Hand-roll `compute_ground_truth()`, not by reimplementing bracket math inline, but by orchestrating calls to `tax_core` functions. Each individual computation (AGI, deduction choice, taxable income, bracket tax, credits, refund) is a small function in `tax_core/computation.py`. The orchestrator walks the scenario, calls them in order, and assembles `GroundTruth`.

Why not a tax engine library:
- Existing engines are either incomplete for VITA scope, written for production prep, or commercial.
- A tax engine is a dependency you can't easily debug. When the grader says "expected $X, got $Y," walking into `tax_core/computation.py` line by line is more valuable than tracing a third-party engine.
- VITA Basic scope is small: maybe a dozen return computations, a few hundred lines of code.
- VITALearn will need introspectable explanations ("your AGI was wrong because you missed the educator expense adjustment"). That requires computation logic VITAPrep can walk, not a black box.

IRS Direct File's fact graph remains useful as a **reference source** for verifying dependency chains. Consult the fact dictionary XMLs to confirm our AGI/taxable income/credit computations consider the same inputs the IRS system does. See "Future: Tax Engine References."

```python
def compute_ground_truth(scenario: Scenario) -> GroundTruth:
    filing_status = determine_filing_status(scenario.household)
    classifications = classify_persons(scenario.household, filing_status)

    agi = compute_agi(scenario.household, classifications)
    deduction = choose_deduction(scenario.household, filing_status, agi)
    taxable = max(0, agi - deduction.amount)
    tax_before_credits = compute_tax(taxable, filing_status, scenario.tax_year)
    credits = compute_credits(scenario.household, classifications, agi, tax_before_credits)
    total_tax = max(0, tax_before_credits - credits.nonrefundable_total)
    refund_or_owed = credits.refundable_total + total_payments(scenario) - total_tax

    return GroundTruth(...)
```

Each function called above is a few dozen lines in `tax_core/computation.py`.

**Scenario envelope — wrapper, not subclass, not replacement.**

`Scenario` wraps `Household` and accumulates lifecycle metadata stage by stage. `Household` is a stable model with downstream consumers (generators, document renderers) — subclassing or replacing it would force every consumer to update. Wrapping leaves `Household` untouched.

```python
@dataclass
class Scenario:
    seed: int
    request: ScenarioRequest
    tax_year: int

    household: Household                                     # existing model, unchanged
    documents: list[Document]                                # existing
    pattern: str                                             # existing

    # Lifecycle additions, populated by their respective stages:
    narrative_slots: dict[str, FiredTemplate] | None = None
    ground_truth: GroundTruth | None = None
    concept_tags: set[str] | None = None
    interview_notes: list[InterviewNote] | None = None

    pre_filled_form: dict | None = None                      # Review mode only
    corruption_manifest: list[Corruption] | None = None      # Review mode only

    generation_log: list[Event] = field(default_factory=list)
```

Design principles:
- **Append-only across the lifecycle.** Each stage adds fields; no stage mutates fields written by an earlier stage. This makes the pipeline debuggable — at any point you can inspect `Scenario` and see which stages have run.
- **`Optional` fields document preconditions.** A consumer that asserts `scenario.ground_truth is not None` documents what it requires.
- **Migration is incremental.** Introduce `Scenario`, route new code (ground truth, analyzer, obfuscator) through it. Leave existing generator/renderer code reading `scenario.household` until there's a reason to change. No big-bang rename.

#### Serialization contract

The scenario store (Fix 12.I) demonstrated the cost of relying on `dataclasses.asdict()` without matching deserialization. `GroundTruth` and `Scenario` must not repeat that pattern:

1. Both get explicit `to_dict()` and `from_dict()` methods. Never rely on `__dict__`, `asdict()` alone, or pickle.
2. `schema_version` on `GroundTruth` from the first commit. The store refuses mismatched versions on load.
3. Round-trip serialization tests (`to_dict → JSON → from_dict → assert equal`) are part of B's checkpoint, not a follow-up.

#### Phase 1: Data models + serialization (containers)

Build the data structures and prove they round-trip through the store. Nothing computes yet.

1. **Define `GroundTruth` and `PersonClassification`** in `tax_core/ground_truth.py`. Schema version 1. Include `to_dict()` / `from_dict()` from the start. `PersonClassification` holds role (primary/spouse/dependent), dependency type (qualifying child/qualifying relative/none), and credit eligibility flags (CTC, ACTC, EITC qualifying child).
2. **Define `Scenario`** wrapper in `intake/scenario.py`. All lifecycle fields start as `None`. `Scenario` delegates to `scenario.household` for generator/renderer compatibility — existing code doesn't change.
3. **Migrate the scenario store** to serialize/deserialize `Scenario` (not `Household` directly). The store writes `Scenario.to_dict()` and reads via `Scenario.from_dict()`. `GroundTruth` is serialized as a nested dict within the scenario JSON; `schema_version` is checked on load.
4. **Round-trip serialization tests** for both `GroundTruth` and `Scenario` — `to_dict → JSON → from_dict → assert equal`. Cover: empty `GroundTruth` (all fields populated), `Scenario` with `ground_truth=None` (pre-computation state), `Scenario` with populated `ground_truth`, `PersonClassification` with various roles. Also test that loading a scenario with wrong `schema_version` raises cleanly.

**Phase 1 checkpoint:** `GroundTruth`, `PersonClassification`, and `Scenario` can be instantiated, serialized to JSON, deserialized, and compared for equality. The scenario store reads and writes `Scenario` objects. All existing tests still pass (generators and renderers work through `scenario.household`).

**Failure mode to watch for:** Trying to migrate every consumer of `Household` to `Scenario` at once. Don't — Phase 1 introduces the wrapper; existing code keeps passing `Household` through `scenario.household`. Migration is incremental.

#### Phase 2: Computation functions (fill the containers)

Implement the individual tax computation functions and the orchestrator that assembles `GroundTruth`. Each function is small, tested, and lives in `tax_core`.

5. **Implement `tax_core/computation.py`** with return-level computation functions. Each calls existing `tax_core` predicates and thresholds from Restructure A:
   - `compute_agi(household, classifications)` — gross income minus above-the-line deductions (student loan interest, educator expenses, IRA contributions, half of SE tax).
   - `choose_deduction(household, filing_status, agi)` — calls `should_itemize()` from A, returns the chosen amount and type.
   - `compute_tax(taxable_income, filing_status, year)` — applies federal tax brackets for the filing status. Bracket tables in `tax_core/thresholds.py` (add federal brackets alongside the existing standard deduction table).
   - `compute_credits(household, classifications, agi, tax_before_credits)` — CTC/ACTC, EITC (stub from A), other applicable credits. Returns a structured object splitting refundable vs nonrefundable.
   - `total_payments(scenario)` — sum of federal withholding from all W-2s and 1099s (reads Box 2 / Box 4 values from the generated documents).
   - `classify_persons(household, filing_status)` — runs dependency predicates from A against each member, returns `dict[person_id, PersonClassification]`.
6. **Unit tests for each computation function** in `tests/tax_core/test_computation.py`. Hand-built `Household` fixtures with known expected values. Test at least: single filer with one W-2, married couple with children (CTC), senior with SS income (taxability tiers), self-employed above SE threshold, itemizer vs standard deduction boundary case.
7. **Implement `compute_ground_truth(scenario) -> GroundTruth`** orchestration in `tax_core/ground_truth.py`. Calls `classify_persons`, then computation functions in order, collects predicate detail snapshots, assembles all three layers. Integration test: generate a full scenario from the pipeline, run `compute_ground_truth`, hand-verify every field.

**Phase 2 checkpoint:** `compute_ground_truth` produces correct `GroundTruth` for at least five distinct household patterns. Each computation function has boundary-case unit tests. Federal bracket tables are in `tax_core/thresholds.py`.

**Failure mode to watch for:** Duplicating logic that already exists in Restructure A predicates. If `compute_agi` needs the SE threshold check, it calls `requires_schedule_se()` — it doesn't reimplement the $400 check. The computation layer orchestrates; the predicate layer decides.

#### Phase 3: Integration + migration (swap the wiring)

Wire ground truth into the live pipeline and migrate the grader. This is the highest-risk phase — it changes runtime behavior.

8. **Wire `compute_ground_truth`** into the generation pipeline immediately after generation completes. Every scenario gets `ground_truth` populated before being served. The pipeline now produces `Scenario` objects (wrapping `Household`) instead of bare `Household` objects.
9. **Migrate the grader** to consume `scenario.ground_truth` exclusively. Delete the ad-hoc on-the-fly key building (`_build_personal_key()`, `_build_income_key()`, `_build_expense_key()` in `training/grader.py`). The grader becomes a pure comparison function: read expected value from `ground_truth`, compare to submitted value, produce feedback.
10. **Invalidate existing scenarios.** Add a check at scenario-load time that refuses scenarios without `ground_truth` or with mismatched `schema_version`. Pre-B scenarios are cheap to regenerate. Log a clear message explaining why the scenario was refused.
11. **End-to-end test**: generate scenario → verify `ground_truth` populated → submit a known-correct answer → confirm grader scores 100% from `ground_truth` → submit a known-wrong answer → confirm grader catches the error and feedback references the correct value from `ground_truth`. Serialize → reload → re-grade → same result.

**Phase 3 checkpoint:** Full player flow works: generate scenario → `ground_truth` is present → review documents → fill form → submit → grader scores against `ground_truth` → feedback is correct. No ad-hoc key building remains in the grader. Pre-B scenarios are refused on load. Round-trip through SQLite preserves `ground_truth` exactly.

**Failure mode to watch for:** The temptation to add a fallback recomputation path in the grader "just in case." Don't — if `ground_truth` is missing or wrong, fix the source. Also: ground truth drifting from what the grader compares to. If you find yourself adding logic to the grader that should be in `compute_ground_truth`, move it.

#### Output

- `Scenario` envelope wraps `Household` with lifecycle metadata.
- Every scenario has `ground_truth` populated before being served.
- The grader has exactly one source of truth, zero domain logic.
- `GroundTruth` and `Scenario` round-trip cleanly through the scenario store.
- Federal tax bracket tables added to `tax_core/thresholds.py`.
- Pre-B scenarios are refused cleanly on load.

**Final checkpoint:** All existing tests pass. All new computation and serialization tests pass. The grader contains no tax-rule logic — it's a pure comparison function. `compute_ground_truth` is the single source of truth for every graded field.

---

### Restructure C1: Analyzer framework and starter slots (additive)

**Goal:** Build the slot-based analyzer that produces narrative cover for generated facts. Wire it into the pipeline alongside the existing interview-notes path. The old path continues to work; nothing changes for the player.

**Prerequisites:** Restructure B complete. Read the Type Definitions, Worked Example, and Stage 3/Stage 6 sections of `SCENARIO_LIFECYCLE.md` before starting — the base classes, data models, and constraint rules are specified there.

**Operation:**

0. **Insert analyzer call site into the pipeline orchestrator.** The pipeline currently runs: generate → ground truth → serve. After this step: generate → **analyze** → ground truth → serve. This is a wiring change only — the analyzer is a no-op stub that returns an empty `narrative_slots` dict until step 3 populates it. The ordering matters: ground truth runs *after* analysis so that scenarios destined for reroll (unrescuable) never pay the cost of ground-truth computation.
1. **Create `intake/analyzer/`** with `types.py`, `analyzer.py` (orchestrator), and `slots/` (one module per slot family).
2. **Define the type system in `intake/analyzer/types.py`.** Four types, specified in `SCENARIO_LIFECYCLE.md` § Type Definitions:
   - `Slot` (ABC) — `name`, `fires_for(scenario)`, `templates()`. The docstring enforces the **slot evaluation constraint**: slots access `scenario.household` and `scenario.documents` only. Other lifecycle fields (`ground_truth`, `concept_tags`, `interview_notes`) are `None` at Stage 3 and must not be read. This is enforced by ordering, documented in the base class, and verified by test (see checkpoint).
   - `NarrativeTemplate` (ABC) — `requirements(scenario, instance)`, `render(scenario, instance, subtlety)`.
   - `InterviewNote` (dataclass) — `category: str`, `question: str`, `answer: str`, `source_slot: str | None`. `source_slot` is a debug field (hidden from the player) that traces each note back to the slot that produced it. `None` for boilerplate notes not produced by a slot.
   - `FiredTemplate` (dataclass) — `slot_name: str`, `instance: Any`, `template: NarrativeTemplate`. `scenario.narrative_slots` is `dict[slot_name, list[FiredTemplate]]`.
3. **Implement three starter slots** covering the highest-frequency cases. Follow the `dependent_residency` worked example in `SCENARIO_LIFECYCLE.md`:
   - `zero_income_reason` — fires when a person has zero total income.
   - `dependent_residency` — fires when a child's `months_in_home < 12`.
   - `address_mismatch` — fires when an ID address differs from the household address.
4. For each slot, implement at least three narrative templates with distinct `requirements()` predicates. Each template produces `InterviewNote` objects at three subtlety levels (`obvious`, `moderate`, `subtle`).
5. Wire the analyzer into the pipeline at the call site from step 0. Populate `scenario.narrative_slots` on every scenario. If a fired slot has zero matching templates, raise `Unrescuable` and let the orchestrator reroll.
6. Build the obfuscator (`intake/obfuscator.py`) that calls each fired template's `render()` method at the scenario-level subtlety (derived from `request.difficulty`: easy → obvious, medium → moderate, hard → subtle) and assembles `scenario.interview_notes`. Store the result on the scenario but **do not yet wire it to the UI**.

**Output:**

- Every scenario carries `narrative_slots` and new-path `interview_notes`.
- The player UI still reads the old hardcoded interview structure (unchanged).
- Unrescuable scenarios trigger reroll instead of being served.

**Checkpoint:** Generate ten scenarios. Confirm `narrative_slots` and new-path `interview_notes` are populated, vary across scenarios, make narrative sense, and never contradict the generated facts. At least one should trigger a reroll due to slot failure (induce this with a constrained generation if needed). All existing tests still pass — the old UI path is untouched. **Additionally:** run a constraint test that executes all slots against a scenario with `ground_truth=None`, `concept_tags=None`, `interview_notes=None` to confirm no slot or template attempts to read those fields.

**Failure mode to watch for:** Templates that lie about ground truth. The obfuscation layer must preserve truth — it can introduce ambiguity, not contradictions.

**Ships as:** Separate PR from C1.5 and C2. At the end of C1, the new pipeline is running and testable but invisible to the player.

---

### Restructure C1.5: Coverage parity audit

**Goal:** Before swapping the player UI to analyzer-driven interview notes (C2), inventory every interview-note-shaped fact the existing path produces and confirm the new path covers them — or deliberately defers them.

**Prerequisites:** C1 merged and stable. The new analyzer pipeline is running and populating `narrative_slots` + `interview_notes` alongside the old path.

**Operation:**

1. Walk `training/exercise_engine.py` (and any other code that currently assembles the player-facing interview or intake view). For each fact surfaced to the player, record: the fact, where it comes from (household field, document, hardcoded), and what it looks like in the UI.
2. Classify each fact into one of three buckets:
   - **Slot-rendered** — covered by a C1 slot, or requires a new slot to be written before C2 ships. If a new slot is needed, note it and add it to C2's scope.
   - **Boilerplate** — read directly from household fields (name, SSN, address, filing status claim, citizenship, contact info). These are rendered by the boilerplate renderer in Stage 6, not by slots.
   - **Deferred** — acceptable to drop in C2 with a logged decision and a tracking item. Example: expense-related interview notes that depend on Restructure D concepts.
3. Produce the coverage checklist. Every fact is accounted for. No fact is silently dropped.

**Output:**

- A checklist (can live in a tracking issue or in this doc as a table) mapping every old-path fact to its new-path equivalent or its deferral justification.
- Any new slots identified as required are added to C2's scope before C2 starts.

**Checkpoint:** The checklist is complete and reviewed. Every fact from the old path has an explicit disposition. C2 can proceed with confidence that the swap won't silently lose player-visible information.

**Ships as:** A document / checklist, not code. No separate PR needed — the output gates C2.

---

### Restructure C2: Swap to analyzer-driven interview notes (substitution)

**Goal:** Replace the old hardcoded interview-notes path with the analyzer-driven path from C1. Delete the old code.

**Prerequisites:** C1 merged and stable. **C1.5 coverage audit complete** — every old-path fact has an explicit disposition (slot-rendered, boilerplate, or deferred). Any new slots identified in C1.5 are implemented as part of this sprint before the swap.

**Operation:**

1. Implement any new slots identified by the C1.5 coverage audit.
2. Implement the boilerplate renderer for structured factual notes (`intake/boilerplate_notes.py`) — renders household fields (name, SSN, address, citizenship, contact info, filing status claim) as `InterviewNote` objects with `source_slot=None`.
3. Update the player UI to read from `scenario.interview_notes` (the analyzer-driven field) instead of the old hardcoded interview structure.
4. Delete the old interview-notes generation code.
5. Verify all exercise modes (intake and review) work against the new path.

**Output:**

- The player UI is reading the new analyzer-driven path.
- The old hardcoded interview-notes path is gone.

**Checkpoint:** Full player flow works: generate scenario → review documents → read interview notes → fill form → submit → grade. Interview notes vary by scenario and subtlety level. No references to the old interview path remain in the codebase. Every fact from the C1.5 checklist that was classified as slot-rendered or boilerplate appears in the new output.

**Failure mode to watch for:** Facts that the C1.5 audit classified as "boilerplate" but that actually need slot-level narrative treatment. If a boilerplate note looks wrong in context (e.g., a filing status claim that should vary by subtlety), promote it to a slot.

**Ships as:** Separate PR from C1 and C1.5. Independently revertible if the swap reveals issues in production.

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

## Future: State Tax Generalization

The expense generator currently uses hardcoded Hawaii state income tax brackets (`HAWAII_TAX_BRACKETS_SINGLE`, `HAWAII_TAX_BRACKETS_MFJ` in `generator/expenses.py`). Restructure A moves these to `tax_core/state_tax/hawaii.py` but does not add other states. This section documents the expansion plan.

### Why this isn't in PUMS

State tax brackets are **statutory data** — published by each state's department of taxation and indexed annually. They are not in PUMS or any Census product. They cannot be extracted the way demographics, housing costs, or income distributions are. This is a separate data source with a separate maintenance cycle.

### Recommended approach: YAML config files

Store brackets as YAML (or JSON) files under `tax_core/state_tax/brackets/`, one per state:

```
tax_core/state_tax/
├── __init__.py
├── compute.py          # dispatch + progressive_tax() shared logic
└── brackets/
    ├── HI.yaml         # Hawaii brackets by year + filing status
    ├── CA.yaml         # California (when added)
    └── ...
```

Each file contains bracket tables keyed by year and filing status:

```yaml
# HI.yaml
2022:
  single:
    - [2400, 0.014]
    - [4800, 0.032]
    # ...
  married_filing_jointly:
    - [4800, 0.014]
    # ...
```

**Why YAML over SQLite:** Bracket data is small (< 50 lines per state per year), changes once per legislative session, and benefits from being version-controlled and diff-readable. It doesn't need query semantics. A YAML file is auditable by reading it; a SQLite row requires a query tool.

**Why not a third-party package:** Adds a dependency for a narrow need. The bracket data itself is public and small. If a reliable open-source tax bracket library emerges, revisit.

### Maintenance burden

Adding a state is a 15-minute task: copy a YAML template, fill in brackets from Tax Foundation or the state's published rate schedule, add a test. When brackets change for a new tax year, update the YAML file and add the new year key. The `compute_state_income_tax()` dispatch function already selects the right file by state code.

### Data sources for bracket compilation

- **Tax Foundation** — publishes annual state income tax rate tables in structured format (taxfoundation.org). Best single source.
- **State revenue department websites** — authoritative but harder to parse. Use for verification.
- **IRS Publication 4012** (VITA Resource Guide) — includes state supplement pages for VITA-active states.

### Prerequisite for multi-state scenarios

Before adding a new state's brackets, that state must also have PUMS extraction data (`data/distributions_{state}_{year}.sqlite`). Property tax and housing cost distributions are state-specific and come from PUMS. Without both bracket data and distribution data, scenarios for that state will be incomplete.

### When to implement

Not during Restructure A. Implement when VITAPrep expands beyond Hawaii — likely triggered by a request to support a second VITA site's state. The `tax_core/state_tax/` directory structure established in Restructure A is designed to accommodate this without refactoring.

---

## Future: Tax Engine References

When Restructure B requires full return-level computation (`compute_ground_truth` producing AGI, taxable income, total tax, refund), implementing it by hand means encoding the entire Form 1040 dependency chain. Two open-source projects are potential references or integration candidates.

### IRS Direct File — Fact Graph

**Repository:** [github.com/IRS-Public/direct-file](https://github.com/IRS-Public/direct-file)

The IRS's own free filing service, open-sourced. Its core is a **declarative fact graph** — XML-based fact dictionaries define writable facts (user input), derived facts (computed from dependency chains), and collections. The Scala runtime (`fact-graph-scala/`) resolves the graph, and the result exports to IRS MeF XML for e-filing.

**Architecture:** Fact dictionaries organized by tax topic (`elderlyAndDisabled.xml`, `filers.xml`, etc.). Each fact is writable or derived, with explicit dependencies. Computational nodes (`compnodes/`) evaluate derived facts. The graph handles incomplete information (partially completed returns) natively — facts are `unknown` until their dependencies resolve.

**What's useful for VITAPrep:**
- The XML fact dictionaries document which tax outcomes depend on which inputs — exactly the dependency chain `compute_ground_truth()` must encode. Even if we don't use the Scala runtime, the dictionaries are a **reference source** for correct fact-to-form-line mappings.
- The `definitions/` and `compnodes/` source code shows how the IRS itself models derived tax computations. This is an authoritative implementation, not a third-party interpretation.
- The approach of declaring facts and deriving outcomes is architecturally similar to what `tax_core` predicates do — VITAPrep's predicates are imperative Python functions, but they encode the same dependency relationships.

**What doesn't fit:**
- Scala/JVM stack — not Python. Integration would require a JVM sidecar or porting the fact dictionaries to a Python evaluation engine.
- Designed for *filing* (user → IRS), not *training* (generate scenario → grade student). The data flows in opposite directions.
- Scoped to Direct File's supported return types (currently W-2 income, limited deductions). VITAPrep's VITA scope is broader in some areas (e.g., self-employment) and narrower in others.

**Recommendation:** Use as a **reference**, not a runtime dependency. When implementing `compute_ground_truth()`, consult the fact dictionary XMLs to verify that our dependency chains match the IRS's own encoding. If VITAPrep ever needs to produce actual MeF-compatible XML (e.g., for integration with a real filing workflow), Direct File's export layer is the reference implementation.

### OpenTaxEngine

**Repository:** [github.com/cameronehrlich/opentaxengine](https://github.com/cameronehrlich/opentaxengine)

A Python rule-based tax engine using YAML-defined form specifications. Supports Form 1040, 1120-S, 1065. CLI with compute, fill, explain, inspect commands.

**What's useful for VITAPrep:**
- Python-native — no language bridge needed.
- YAML form specs are readable and auditable.
- The `explain` command traces how a line value was computed — useful for grading feedback.

**What doesn't fit:**
- Very early stage (as of 2026): limited to 2025 tax year, minimal test coverage.
- Must support the tax year matching our PUMS data (currently 2022) before we can use it.
- Uncertain long-term maintenance.

**Recommendation:** Monitor for maturity. If it stabilizes and adds multi-year support, it could replace hand-rolled `compute_ground_truth()` logic. Evaluate during Restructure B scoping.

### When to decide

The tax engine decision belongs in **Restructure B's planning phase**, not A. Restructure A's predicates are individual rule checks that are better hand-written. Restructure B's `compute_ground_truth()` is a return-level computation where an engine adds value. Before starting B, evaluate:

1. Does Direct File's fact graph cover the VITA Basic/Advanced scope we need?
2. Has OpenTaxEngine added 2022 tax year support?
3. Is hand-rolling `compute_ground_truth()` with our existing predicates simpler than integrating either engine?

The answer determines whether B wraps an external engine or extends `tax_core` with line-level computation functions.

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
- Concept catalog registration: explicit list vs decorator-based vs autodiscovery. Recommend explicit list for MVP.

**Resolved:**

- ~~Subtlety dial: global per scenario, per slot, or per concept?~~ **Global per scenario for MVP**, derived from `request.difficulty` (`easy → obvious`, `medium → moderate`, `hard → subtle`). Per-slot or per-concept overrides deferred to Restructure D. See `SCENARIO_LIFECYCLE.md` § Stage 6.
