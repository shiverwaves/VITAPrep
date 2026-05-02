"""
Exercise engine — orchestrates full scenario creation.

Pipeline: generate → analyze → ground truth → obfuscate → boilerplate
          → inject errors → package

The analyzer runs before ground truth so that unrescuable scenarios
(no matching narrative templates) are caught before paying the cost of
ground-truth computation.

Documents are rendered on-demand by the API layer (HTML served directly
to the browser), not pre-generated at scenario creation time.

Modes:
- "encounter": Student gets source docs, fills blank 13614-C Part I
- "verify": Student gets pre-filled 13614-C + source docs, finds discrepancies
- "crosscheck": Student verifies 1040 against source docs (future)
"""

import logging
import uuid
from dataclasses import fields as dataclass_fields
from datetime import datetime
from typing import List, Optional, Set

from generator.models import Scenario
from generator.pipeline import HouseholdGenerator
from intake.analyzer.analyzer import MAX_REROLL_ATTEMPTS, ScenarioAnalyzer
from intake.analyzer.slots.address_mismatch import AddressMismatchSlot
from intake.analyzer.slots.dependent_residency import DependentResidencySlot
from intake.analyzer.slots.zero_income_reason import ZeroIncomeReasonSlot
from intake.analyzer.types import Unrescuable
from intake.boilerplate import generate_boilerplate
from intake.obfuscator import obfuscate
from learn.concept_catalog import ConceptCatalog
from learn.concepts.base import GenerationHints
from learn.concepts.deductions import StandardVsItemizedConcept
from learn.concepts.dependency import QualifyingChildResidencyConcept
from learn.concepts.education import FullTimeStudentDependentConcept
from learn.concepts.filing_status import (
    HoHQualifyingPersonConcept,
    RefundableCreditOnlyFilerConcept,
)
from learn.concepts.income import (
    SelfEmploymentThresholdConcept,
    SocialSecurityTaxabilityConcept,
)
from tax_core.ground_truth import compute_ground_truth
from .error_injector import ErrorInjector
from .grader import build_form_answers

logger = logging.getLogger(__name__)

MAX_GEN_ATTEMPTS = 5


class ConceptMissed(Exception):
    """Raised when a generated scenario doesn't fire all requested concepts."""

    def __init__(self, missing: Set[str]) -> None:
        self.missing = missing
        super().__init__(
            f"Couldn't generate a scenario matching all selected concepts. "
            f"Missing: {', '.join(sorted(missing))}. "
            f"Try fewer concepts or different combinations."
        )


class ExerciseEngine:
    """Orchestrates generation of complete training scenarios."""

    def __init__(self, state: str = "HI", year: int = 2022) -> None:
        self.generator = HouseholdGenerator(state, year)
        self.error_injector = ErrorInjector()
        self.analyzer = ScenarioAnalyzer()
        self.analyzer.register(AddressMismatchSlot())
        self.analyzer.register(ZeroIncomeReasonSlot())
        self.analyzer.register(DependentResidencySlot())
        self.concept_catalog = ConceptCatalog()
        self.concept_catalog.register(QualifyingChildResidencyConcept())
        self.concept_catalog.register(HoHQualifyingPersonConcept())
        self.concept_catalog.register(RefundableCreditOnlyFilerConcept())
        self.concept_catalog.register(SelfEmploymentThresholdConcept())
        self.concept_catalog.register(SocialSecurityTaxabilityConcept())
        self.concept_catalog.register(StandardVsItemizedConcept())
        self.concept_catalog.register(FullTimeStudentDependentConcept())

    def generate_scenario(
        self,
        mode: str = "encounter",
        difficulty: str = "easy",
        error_count: int = 3,
        pattern: Optional[str] = None,
        seed: Optional[int] = None,
        concepts: Optional[List[str]] = None,
    ) -> Scenario:
        """Generate a complete training scenario.

        Retries with a new seed if the analyzer deems the scenario
        unrescuable (no matching narrative templates for a fired slot).
        When *concepts* is provided, also retries if the generated
        scenario doesn't fire all requested concepts.

        Args:
            mode: "encounter" (fill blank form), "verify" (find errors),
                or "crosscheck" (future).
            difficulty: "easy", "medium", or "hard".
            error_count: Number of errors to inject (verify mode).
                Ignored for encounter mode.
            pattern: Specific household pattern or None for random.
            seed: Random seed for reproducibility.
            concepts: Optional list of concept names to target. When
                provided, generation hints are merged and the engine
                rerolls if requested concepts don't all fire.

        Returns:
            Scenario with household, ground truth, errors, and interview notes.

        Raises:
            Unrescuable: If all retry attempts produce unrescuable scenarios.
            ConceptMissed: If requested concepts can't be satisfied after
                MAX_GEN_ATTEMPTS attempts.
        """
        hints = self._merge_hints(concepts) if concepts else None
        max_attempts = MAX_GEN_ATTEMPTS if concepts else MAX_REROLL_ATTEMPTS
        requested = set(concepts) if concepts else set()
        last_missing: Set[str] = set()

        for attempt in range(max_attempts):
            try:
                scenario = self._build_scenario(
                    mode=mode,
                    difficulty=difficulty,
                    error_count=error_count,
                    pattern=pattern,
                    seed=seed,
                    attempt=attempt,
                    hints=hints,
                )
            except Unrescuable:
                logger.warning(
                    "Attempt %d unrescuable, retrying with new seed",
                    attempt + 1,
                )
                seed = None
                continue

            if requested:
                fired = set(scenario.concept_tags or [])
                last_missing = requested - fired
                if last_missing:
                    logger.warning(
                        "Attempt %d missing concepts %s, retrying",
                        attempt + 1, last_missing,
                    )
                    seed = None
                    continue

            return scenario

        if requested and last_missing:
            raise ConceptMissed(last_missing)

        raise Unrescuable(
            f"Failed to generate rescuable scenario after "
            f"{max_attempts} attempts"
        )

    def _merge_hints(self, concept_names: List[str]) -> GenerationHints:
        """Merge generation hints from requested concepts (last-write-wins)."""
        merged = GenerationHints()
        empty = GenerationHints()
        by_name = {c.name: c for c in self.concept_catalog.concepts}

        for name in concept_names:
            concept = by_name.get(name)
            if concept is None:
                continue
            hints = concept.generation_hints()
            if hints.preferred_patterns:
                merged.preferred_patterns.extend(hints.preferred_patterns)
            for f in dataclass_fields(GenerationHints):
                if f.name == "preferred_patterns":
                    continue
                val = getattr(hints, f.name)
                if val != getattr(empty, f.name):
                    setattr(merged, f.name, val)

        if merged.preferred_patterns:
            merged.preferred_patterns = list(dict.fromkeys(merged.preferred_patterns))

        logger.info("Merged hints for concepts %s: %s", concept_names, merged)
        return merged

    def _build_scenario(
        self,
        mode: str,
        difficulty: str,
        error_count: int,
        pattern: Optional[str],
        seed: Optional[int],
        attempt: int,
        hints: Optional[GenerationHints] = None,
    ) -> Scenario:
        """Single attempt at building a scenario. May raise Unrescuable."""
        scenario_id = f"sc-{uuid.uuid4().hex[:12]}"

        # Stage 1: Generate household with demographics + PII
        household = self.generator.generate_with_pii(
            pattern=pattern, seed=seed, hints=hints,
        )

        # Stage 2: Build provisional scenario for analysis
        scenario = Scenario(
            scenario_id=scenario_id,
            mode=mode,
            difficulty=difficulty,
            household=household,
            document_paths={},
            created_at=datetime.utcnow().isoformat(),
        )

        # Stage 3: Analyze — evaluate slots, pick templates.
        # Raises Unrescuable if a fired slot has no matching template.
        narrative_slots = self.analyzer.analyze(scenario)

        # Stage 4: Compute ground truth from the clean household
        # (before error injection so it reflects correct answers)
        gt = compute_ground_truth(household, year=self.generator.year)
        gt.form_answers = build_form_answers(household)
        gt_dict = gt.to_dict()

        # Stage 4b: Concept labeling — tag the scenario for learning analytics
        scenario.ground_truth = gt_dict
        concept_tags = sorted(self.concept_catalog.run_all(scenario))

        # Stage 5: Obfuscate — render fired templates into interview notes
        slot_notes = obfuscate(narrative_slots, scenario, difficulty)

        # Stage 6: Boilerplate — factual notes from household fields
        boilerplate_notes = generate_boilerplate(household, difficulty)

        # Stage 7: Inject errors (verify mode only)
        injected_errors = []
        if mode == "verify":
            household, injected_errors = self.error_injector.inject(
                household,
                difficulty=difficulty,
                error_count=error_count,
            )

        # Merge slot-rendered + boilerplate into interview_notes
        all_notes = slot_notes + boilerplate_notes
        serialized_notes = [
            {
                "category": n.category,
                "question": n.question,
                "answer": n.answer,
                "source_slot": n.source_slot,
            }
            for n in all_notes
        ] if all_notes else None

        # Package
        scenario.household = household
        scenario.injected_errors = injected_errors
        scenario.ground_truth = gt_dict
        scenario.concept_tags = concept_tags if concept_tags else None
        scenario.narrative_slots = {
            name: [
                {"slot_name": ft.slot_name, "instance_id": _instance_id(ft.instance)}
                for ft in fired_list
            ]
            for name, fired_list in narrative_slots.items()
        } if narrative_slots else None
        scenario.interview_notes = serialized_notes

        logger.info(
            "Generated scenario %s (attempt %d): mode=%s, difficulty=%s, "
            "members=%d, errors=%d, slots_fired=%d, notes=%d, concepts=%d",
            scenario_id, attempt + 1, mode, difficulty,
            len(household.members),
            len(injected_errors),
            len(narrative_slots),
            len(all_notes),
            len(concept_tags),
        )
        return scenario


def _instance_id(instance: object) -> str:
    """Extract a serializable identifier from a triggering instance."""
    if hasattr(instance, "person_id"):
        return instance.person_id
    return str(instance)
