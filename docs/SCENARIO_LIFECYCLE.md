# Scenario Lifecycle Specification

> **Status:** Draft. This document defines the target data flow and operational stages of scenario generation in VITAPrep. It is the contract between modules — anything in code that contradicts this spec should be reconciled by updating the doc first, then the code.
>
> **Relationship to current code:** Parts of this lifecycle exist already (generator, document rendering). Other parts are new (analyzer, slots, concept catalog, obfuscation layer). Treat this as the target architecture; integration is a migration, not a rewrite.

---

## Purpose

VITAPrep generates synthetic but coherent VITA client scenarios for training tax preparers. A scenario is a self-contained unit comprising:

- A household with realistic demographic, employment, and income composition.
- A set of supporting documents (SSN cards, IDs, W-2s, 1099s, 1098s, etc.).
- An interview transcript (the client's stated answers to intake questions).
- A ground-truth answer key for grading.
- Metadata tagging which tax-law concepts the scenario exercises.

This document specifies the lifecycle that produces and serves these scenarios.

---

## Architectural layers

VITAPrep is organized as three logical layers. They live in one repository at the MVP stage but are designed for eventual separation.

### `tax_core` — the rules engine

Pure functions over scenario data. No UI, no narrative, no curriculum logic. Encodes tax-law predicates, threshold lookups, classification tests, and computation routines. Examples: `qualifying_child_residency_test()`, `is_self_employment_threshold_met()`, `filing_threshold_for(status, year)`.

`tax_core` is the source of truth for what is correct. Both the scenario generator (when computing ground truth) and the grader (when evaluating submissions) call into the same `tax_core` functions. There is exactly one definition of correctness per rule.

`tax_core` has no dependencies on the layers above it.

### `intake` — scenario generation and presentation

Consumes `tax_core`. Responsible for:

- Generating coherent households via the existing demographic / income / document pipelines.
- Running the analyzer to attach narrative cover to generated facts.
- Rendering documents.
- Producing the obfuscated interview-notes view the player sees.

`intake` does not know about concepts, learner progression, or curriculum.

### `learn` — curriculum and progression

Consumes both layers below. Responsible for:

- The concept catalog (predicate-based labels for tax-law features present in a scenario).
- Concept-driven generation requests (target a concept, get a scenario that exercises it).
- Player progression, weakness detection, and recommendation.
- Post-game explanations and feedback.

`learn` is the only layer that knows what a "concept" is.

---

## The Scenario object

The unit that flows through the pipeline. Append-only across the lifecycle: each layer adds fields but does not mutate prior layers' contributions.

```
Scenario
├── seed                  # int, for reproducibility
├── request               # original ScenarioRequest (mode, difficulty, etc.)
├── tax_year              # int
├── state                 # str, e.g. "HI"
├── pattern               # str, e.g. "married_couple_no_children"
├── household             # Household (existing model)
│   ├── members           # list[Person]
│   └── address           # Address
├── documents             # list[Document]
├── narrative_slots       # dict[slot_name, fired_template]   (Stage 3)
├── ground_truth          # GroundTruth                       (Stage 4)
├── concept_tags          # set[str]                          (Stage 5)
├── interview_notes       # list[InterviewNote]               (Stage 6)
├── pre_filled_form       # optional, Review mode only        (Stage 8)
├── corruption_manifest   # optional, Review mode only        (Stage 8)
└── generation_log        # list[Event] for diagnostics
```

---

## Lifecycle stages

### Stage 1: Request

**Caller:** Player UI, CLI, or API.

**Inputs:**
- `mode` — `intake` or `review`
- `difficulty` — abstract level (easy/medium/hard) OR explicit subtlety knob
- `state`, `tax_year` — bounds
- `pattern` — optional household pattern constraint
- `concepts` — optional set of concept names to target
- `seed` — optional, for reproducibility

**Output:** A `ScenarioRequest` object handed to the pipeline.

**Notes:** The request layer normalizes inputs and resolves abstract difficulty into concrete generation parameters. Concept filtering, if present, is passed through to Stage 2 as generation hints.

---

### Stage 2: Generation

**Module:** `intake.generator`

**Inputs:** `ScenarioRequest`

**Operation:**

1. If `concepts` are specified, query the concept catalog (in `learn`) for each concept's `generation_hints()` and merge them into a `GenerationHints` object.
2. Run the existing household generator with hints applied. Hints can constrain: pattern, household size, dependent ages, income sources, document presence.
3. Produce a `Household` populated with all demographic, employment, income, and expense fields per existing logic.
4. Generate documents corresponding to the household's facts.

**Output:** A `Scenario` with `household`, `documents`, and `seed` populated. No ground truth, no interview notes, no concepts yet.

**Failure mode:** If concept hints are incompatible (e.g., conflicting constraints) or the generator cannot satisfy them, raise `GenerationFailed` and let the orchestrator retry with a different seed.

---

### Stage 3: Analysis

**Module:** `intake.analyzer`

**Inputs:** `Scenario` from Stage 2

**Operation:**

1. Walk the slot catalog. For each slot, evaluate `fires_for(scenario)` to find triggering instances (e.g., each child whose months-in-home is < 12).
2. For each fired instance, evaluate templates in priority order. Pick the first template whose `requirements()` predicate matches, or sample weighted-randomly among matching templates.
3. If a fired slot has zero matching templates, the scenario is **unrescuable** — abort and signal reroll to the orchestrator.
4. Record fired templates in `scenario.narrative_slots`. Templates are not yet rendered into text; that is Stage 6.

**Output:** `Scenario` with `narrative_slots` populated. May raise `Unrescuable` to trigger reroll.

**Notes:** The analyzer is the gatekeeper for coherence. Generation produces statistical realism; the analyzer enforces narrative realism. Most rerolls happen here, not at the generator.

---

### Stage 4: Ground truth

**Module:** `tax_core.ground_truth`

**Inputs:** `Scenario` after analysis

**Operation:**

1. Compute the canonical correct answers for the scenario by running `tax_core` predicates and computations over the generated facts.
2. Populate fields including: `filing_status`, `dependent_status` per person, `agi`, `taxable_income`, `total_tax`, `refund_or_owed`, `credits_claimed`, `deductions_claimed`.
3. For each predicate that returned a meaningful result (not just true/false), record the structured detail (e.g., `qualifying_child_residency_test` returns months, pass/fail, exception flags).

**Output:** `Scenario` with `ground_truth` populated.

**Notes:** Ground truth is computed exactly once, immediately after generation, before any obfuscation occurs. The grader at Stage 10 reads this value verbatim. The obfuscation layer at Stage 6 cannot modify it.

---

### Stage 5: Concept labeling

**Module:** `learn.concept_catalog`

**Inputs:** `Scenario` with ground truth

**Operation:**

1. Iterate the full concept catalog. For each concept, evaluate `concept.matches(scenario)`.
2. Collect the set of matching concepts into `scenario.concept_tags`.
3. (Optional) If the request specified target concepts, verify all target concepts matched. If not, raise `ConceptMissedError` to trigger reroll with adjusted hints.

**Output:** `Scenario` with `concept_tags` populated.

**Notes:** Labeling is read-only with respect to the scenario. It does not modify any field. Concept evaluation is independent of slot evaluation; both layers may share predicate helpers from `tax_core` but produce different artifacts.

---

### Stage 6: Obfuscation rendering

**Module:** `intake.obfuscator`

**Inputs:** `Scenario` with slots, ground truth, concepts

**Operation:**

1. For each fired slot in `scenario.narrative_slots`, call the template's `render()` method with the chosen subtlety level.
2. Subtlety is determined per slot from request difficulty, with per-concept overrides if a target concept specifies a subtlety in its definition.
3. Each render produces an `InterviewNote` (category, question, answer triple).
4. Concatenate all rendered notes plus the structured factual notes (citizenship, contact info, filing status the client claimed) into `scenario.interview_notes`.

**Output:** `Scenario` with `interview_notes` populated.

**Constraint:** The obfuscation layer can introduce ambiguity but cannot lie about ground truth. If the ground truth is "child lived with taxpayer 7 months," the obfuscation can say "she stayed with her dad over the summer" (forces inference) but cannot say "she lived with me all year" (contradicts truth). A competent reader must in principle be able to reconstruct ground truth from the interview notes plus documents.

---

### Stage 7: Document rendering

**Module:** `intake.document_renderer`

**Inputs:** `Scenario`

**Operation:** Render each document in `scenario.documents` to the appropriate format (PNG, PDF). Documents reflect ground-truth facts (no falsification at this layer). Errors injected for Review mode are applied as a *separate* perturbation pass at Stage 8.

**Output:** Rendered document files referenced by `scenario.documents`.

---

### Stage 8: Mode-specific finalization

**Module:** `intake.modes`

**Operation differs by mode:**

**Intake mode:** No finalization beyond what's already done. Player receives the scenario as-is and fills the form from blank.

**Review mode:**

1. Generate a "candidate filled form" from ground truth.
2. Apply N corruptions to the candidate form, where N and the corruption types depend on difficulty. Corruption types include: wrong filing status, missed dependent, transposed amount, missing income source, claimed expense without basis.
3. Record the corruption manifest separately from `ground_truth` for grading.
4. Hand player the corrupted form to audit.

**Output:** `Scenario` ready to serve, possibly with `pre_filled_form` and `corruption_manifest` for Review mode.

---

### Stage 9: Serve

The scenario is persisted to the scenario store and exposed via the API or UI. The player sees only:

- Documents (rendered images / PDFs).
- Interview notes (from Stage 6).
- The form to fill (Intake) or audit (Review).

**Hidden from the player:** `ground_truth`, `concept_tags`, `narrative_slots`, `corruption_manifest`.

---

### Stage 10: Submission and grading

**Module:** `learn.grader` (consumes `tax_core` for re-derivation if needed)

**Inputs:** Player submission (form fields + flags), `scenario.ground_truth`, `scenario.corruption_manifest` (Review only)

**Operation:**

1. Compare submission fields to ground truth field-by-field.
2. In Review mode, additionally compare flagged corruptions to the corruption manifest.
3. Produce a `GradingResult` with score, missed items, false positives, and field-level feedback.
4. Record the result against the player's progression history (in `learn`).

**Output:** `GradingResult` returned to the player.

---

### Stage 11: Post-game (optional)

**Module:** `learn.feedback`

After grading, surface to the player:

- Concepts the scenario tested.
- Concepts the player got right vs. missed.
- Updated weakness map.
- Suggested next scenario (concept-driven recommendation).

This is where the curriculum loop closes.

---

## Module layout

Suggested directory structure. Names are negotiable; structure is the point.

```
vitaprep/
├── tax_core/
│   ├── predicates/
│   │   ├── dependency.py         # qualifying_child_residency_test, etc.
│   │   ├── filing_status.py
│   │   ├── income.py
│   │   └── deductions.py
│   ├── thresholds.py              # filing_threshold_for, hsa_limits, etc.
│   ├── computation.py             # AGI, taxable income, tax calculation
│   └── ground_truth.py            # compose ground truth from a scenario
├── intake/
│   ├── generator/                 # existing demographic/income/document logic
│   ├── analyzer/
│   │   ├── slots/                 # one file per slot family
│   │   └── analyzer.py            # walks slots, attaches templates
│   ├── obfuscator.py              # renders templates to interview notes
│   ├── document_renderer.py
│   └── modes/
│       ├── intake.py
│       └── review.py              # corruption injection
├── learn/
│   ├── concepts/                  # one file per concept family
│   │   ├── dependency.py
│   │   ├── filing_status.py
│   │   ├── income.py
│   │   └── deductions.py
│   ├── concept_catalog.py         # registry, matches() runner
│   ├── grader.py
│   └── progression.py
├── api/
└── docs/
```

---

## Failure modes and reroll policy

**Where rerolls happen:**

1. **Generator failure** (Stage 2): Hints unsatisfiable. Retry with a new seed up to `MAX_GEN_ATTEMPTS` (suggest 10). If still failing, raise to caller.
2. **Analyzer unrescuable** (Stage 3): No template matches a fired slot. Reroll generation with new seed. Same retry cap.
3. **Concept missed** (Stage 5, only when targeting): Generated scenario doesn't actually match a target concept after all. Reroll.

**Never reroll for:**

- Ground truth disagreement (impossible by construction — ground truth is computed from facts).
- Obfuscation difficulty (subtlety is a knob, not a failure).
- Document rendering errors (those are bugs, not generation failures).

**Reroll cost:** Each reroll runs Stages 2–5 again. Stages 1, 6–11 only execute on the surviving scenario. Keep stages 2–5 cheap to allow generous retry caps.

---

## Determinism and seeding

The scenario pipeline must be deterministic given a seed. Same seed + same code = same scenario.

**Implications:**

- All RNG draws derive from the seed (no `random.random()` outside seeded contexts).
- Slot template selection is seeded.
- Subtlety randomization is seeded.
- Review-mode corruption choices are seeded.

**Why it matters:**

- Bug reports become reproducible by sharing a seed.
- Player can revisit a scenario.
- Grading can be replayed.

**Implementation note:** Use a single seeded RNG threaded through the pipeline, or per-stage seeded RNGs derived from the master seed (`stage_seed = hash((master_seed, stage_name))`). The latter is cleaner for parallelism; the former is simpler.

---

## Testing surface

Each layer should have its own tests:

- `tax_core`: unit tests of predicates against hand-built scenarios.
- `intake.generator`: existing tests; no change.
- `intake.analyzer`: tests that confirm slot firing logic and template requirement matching.
- `intake.obfuscator`: snapshot tests on rendered interview notes per subtlety level.
- `learn.concepts`: each concept tested against scenarios that should and should not match.
- End-to-end: full lifecycle smoke test producing a scenario from a fixed seed and asserting all expected fields populated.

---

## Open questions deferred to implementation

These are intentionally not specified here. Resolve in code, then update this doc.

- Whether to use Python `random.Random` instances or NumPy generators throughout.
- Whether `tax_core` predicates return rich result objects or simple booleans (worked example used rich; revisit per predicate).
- How concept hints merge when multiple target concepts conflict (last-wins, error, soft preference).
- Where document corruption manifests live for Review mode (in `Scenario` or sidecar table).
- Subtlety dial: global per scenario, per slot, or per concept? Spec hedges; pick one in code.

---

## Migration order (suggested)

The lifecycle described here is the target. To get there from where the codebase is now, suggested order:

1. **Carve out `tax_core`.** Move existing predicates, thresholds, and any tax-rule logic into `tax_core/` as pure functions. Don't add features yet — just establish the boundary.
2. **Add `ground_truth.py` to `tax_core`.** Implement the Stage 4 computation as a function over the existing Scenario shape. Wire it into the existing pipeline so every generated scenario has ground truth attached.
3. **Build the analyzer and slot catalog (Stage 3).** Start with three high-frequency slots: `zero_income_reason`, `dependent_residency`, `address_mismatch`. Get the unrescuable-reroll path working.
4. **Build the obfuscator (Stage 6).** Render those three slots to interview notes. Verify the interview-notes table in the player UI is now populated by templates instead of hardcoded values.
5. **Add `learn.concept_catalog`.** Implement Stage 5 with three concepts: `qualifying_child_residency`, `hoh_qualifying_person`, `refundable_credit_only_filer`. Generate-then-tag only — no targeting yet.
6. **Add Review mode (Stage 8).** Corruption injection on top of ground truth.
7. **Wire targeted generation (concept hints into Stage 2).** This is the last step because it's the most fragile; everything else should work without it.

Each step produces a working system. Skip ahead at your peril.
