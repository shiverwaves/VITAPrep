"""TDD tests for the exercise engine.

The ExerciseEngine orchestrates the full pipeline:
generate → PII → inject errors → client profile → package.

These tests mock the heavy dependencies (HouseholdGenerator)
so they run fast without SQLite data.

Contract
--------
ExerciseEngine.generate_scenario(mode, difficulty, error_count, pattern, seed)
  → Scenario

Requirements:
1. Returns a Scenario with a unique scenario_id and created_at timestamp.
2. Household is fully populated (demographics + PII).
3. Mode "intake":
   - injected_errors is empty (student fills from clean docs).
   - interview_notes populated and filtered by difficulty.
4. Mode "verify":
   - injected_errors populated with error_count errors.
   - interview_notes populated.
5. difficulty propagates to error injection and client fact filtering.
6. pattern is forwarded to the household generator.
7. seed is forwarded for reproducibility.
"""

from datetime import date
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from generator.models import (
    Address,
    Household,
    InjectedError,
    Person,
    RelationshipType,
    Scenario,
)
from intake.analyzer.analyzer import ScenarioAnalyzer
from training.exercise_engine import ExerciseEngine


# =========================================================================
# Helpers
# =========================================================================

def _make_household(pattern: str = "single_adult") -> Household:
    """Build a household with full PII for testing."""
    members = [
        Person(
            person_id="p-01",
            relationship=RelationshipType.HOUSEHOLDER,
            age=30,
            sex="F",
            race="white",
            legal_first_name="Jane",
            legal_middle_name="Ann",
            legal_last_name="Doe",
            ssn="900-12-3456",
            dob=date(1992, 5, 15),
            phone="(808) 555-1234",
            email="jane@example.com",
            id_type="drivers_license",
            id_state="HI",
            id_number="H1234567",
            id_expiry=date(2028, 6, 15),
            id_address=Address(
                street="100 Main St", city="Honolulu",
                state="HI", zip_code="96816",
            ),
        ),
    ]
    if "married" in pattern or "children" in pattern:
        members.append(Person(
            person_id="p-02",
            relationship=RelationshipType.SPOUSE,
            age=32,
            sex="M",
            legal_first_name="John",
            legal_last_name="Doe",
            ssn="900-65-4321",
            dob=date(1990, 8, 20),
            id_type="drivers_license",
            id_state="HI",
            id_number="H7654321",
            id_expiry=date(2027, 3, 10),
            id_address=Address(
                street="100 Main St", city="Honolulu",
                state="HI", zip_code="96816",
            ),
        ))
    return Household(
        household_id="hh-test-001",
        state="HI",
        year=2022,
        pattern=pattern,
        address=Address(
            street="100 Main St", city="Honolulu",
            state="HI", zip_code="96816",
        ),
        members=members,
    )


# =========================================================================
# Fixtures — patch heavy dependencies
# =========================================================================

@pytest.fixture
def engine():
    """Create an ExerciseEngine with mocked generator."""
    with patch("training.exercise_engine.HouseholdGenerator") as MockGen:
        mock_gen_instance = MockGen.return_value
        mock_gen_instance.generate_with_pii.return_value = _make_household()
        mock_gen_instance.year = 2022

        eng = ExerciseEngine.__new__(ExerciseEngine)
        eng.generator = mock_gen_instance
        eng.error_injector = MagicMock()
        eng.analyzer = ScenarioAnalyzer()
        # Make error_injector.inject return a realistic result
        eng.error_injector.inject.side_effect = _mock_inject

        from learn.concept_catalog import ConceptCatalog
        from learn.concepts.deductions import StandardVsItemizedConcept
        from learn.concepts.dependency import QualifyingChildResidencyConcept
        from learn.concepts.filing_status import (
            HoHQualifyingPersonConcept,
            RefundableCreditOnlyFilerConcept,
        )
        from learn.concepts.income import (
            SelfEmploymentThresholdConcept,
            SocialSecurityTaxabilityConcept,
        )
        eng.concept_catalog = ConceptCatalog()
        eng.concept_catalog.register(QualifyingChildResidencyConcept())
        eng.concept_catalog.register(HoHQualifyingPersonConcept())
        eng.concept_catalog.register(RefundableCreditOnlyFilerConcept())
        eng.concept_catalog.register(SelfEmploymentThresholdConcept())
        eng.concept_catalog.register(SocialSecurityTaxabilityConcept())
        eng.concept_catalog.register(StandardVsItemizedConcept())
        from learn.concepts.education import FullTimeStudentDependentConcept
        eng.concept_catalog.register(FullTimeStudentDependentConcept())

        yield eng


def _mock_inject(household, difficulty="medium", error_count=3):
    """Mock inject that returns household + plausible errors."""
    from training.error_injector import ErrorInjector
    real = ErrorInjector()
    return real.inject(household, difficulty=difficulty, error_count=error_count)


# =========================================================================
# 1. Return type and basic fields
# =========================================================================

class TestReturnType:

    def test_returns_scenario(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert isinstance(result, Scenario)

    def test_has_scenario_id(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.scenario_id
        assert len(result.scenario_id) > 0

    def test_has_created_at(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.created_at is not None
        assert len(result.created_at) > 0

    def test_unique_ids(self, engine: ExerciseEngine) -> None:
        s1 = engine.generate_scenario(mode="intake", difficulty="easy")
        s2 = engine.generate_scenario(mode="intake", difficulty="easy")
        assert s1.scenario_id != s2.scenario_id

    def test_mode_stored(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="verify", difficulty="medium")
        assert result.mode == "verify"

    def test_difficulty_stored(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="hard")
        assert result.difficulty == "hard"


# =========================================================================
# 2. Household
# =========================================================================

class TestHousehold:

    def test_household_populated(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.household is not None
        assert len(result.household.members) > 0

    def test_household_has_pii(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        primary = result.household.members[0]
        assert primary.legal_first_name
        assert primary.ssn

    def test_pattern_forwarded(self, engine: ExerciseEngine) -> None:
        engine.generate_scenario(
            mode="intake", difficulty="easy", pattern="single_adult",
        )
        engine.generator.generate_with_pii.assert_called()
        call_kwargs = engine.generator.generate_with_pii.call_args
        assert call_kwargs[1].get("pattern") == "single_adult" or \
               (call_kwargs[0] and call_kwargs[0][0] == "single_adult") or \
               call_kwargs[1].get("pattern") == "single_adult"

    def test_seed_forwarded(self, engine: ExerciseEngine) -> None:
        engine.generate_scenario(
            mode="intake", difficulty="easy", seed=42,
        )
        call_kwargs = engine.generator.generate_with_pii.call_args
        assert call_kwargs[1].get("seed") == 42 or \
               (len(call_kwargs[0]) > 1 and call_kwargs[0][1] == 42)


# =========================================================================
# 3. Intake mode specifics
# =========================================================================

class TestIntakeMode:

    def test_no_injected_errors(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.injected_errors == []

    def test_interview_notes_populated(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.interview_notes is not None
        assert len(result.interview_notes) > 0

    def test_interview_notes_are_dicts(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert all(isinstance(n, dict) for n in result.interview_notes)
        assert all("category" in n for n in result.interview_notes)


# =========================================================================
# 5. Verify mode specifics
# =========================================================================

class TestVerifyMode:

    def test_injected_errors_populated(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="medium", error_count=2,
        )
        assert len(result.injected_errors) > 0

    def test_error_count_forwarded(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="easy", error_count=1,
        )
        assert len(result.injected_errors) == 1

    def test_injected_errors_are_injected_error_objects(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="medium", error_count=2,
        )
        assert all(isinstance(e, InjectedError) for e in result.injected_errors)

    def test_interview_notes_present(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="medium", error_count=2,
        )
        assert result.interview_notes is not None
        assert len(result.interview_notes) > 0

    def test_zero_errors_verify(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="easy", error_count=0,
        )
        assert result.injected_errors == []


# =========================================================================
# 6. Difficulty propagation
# =========================================================================

class TestDifficultyPropagation:

    def test_verify_errors_match_difficulty(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="hard", error_count=1,
        )
        if result.injected_errors:
            assert result.injected_errors[0].difficulty == "hard"

    def test_easy_has_more_notes_than_hard(
        self, engine: ExerciseEngine,
    ) -> None:
        easy = engine.generate_scenario(mode="intake", difficulty="easy")
        hard = engine.generate_scenario(mode="intake", difficulty="hard")
        assert len(easy.interview_notes) >= len(hard.interview_notes)


# =========================================================================
# 7. Ground truth integration (B Phase 3)
# =========================================================================

class TestGroundTruth:

    def test_ground_truth_present(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.ground_truth is not None

    def test_ground_truth_has_schema_version(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.ground_truth["schema_version"] == 1

    def test_ground_truth_has_form_answers(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        fa = result.ground_truth.get("form_answers", {})
        assert len(fa) > 0
        assert "you.first_name" in fa

    def test_ground_truth_computed_before_errors(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="easy", error_count=2,
        )
        fa = result.ground_truth.get("form_answers", {})
        assert fa.get("you.first_name") == "Jane"

    def test_ground_truth_has_filing_status(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.ground_truth["filing_status"] != ""

    def test_ground_truth_roundtrip_dict(
        self, engine: ExerciseEngine,
    ) -> None:
        from tax_core.ground_truth import GroundTruth
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        gt = GroundTruth.from_dict(result.ground_truth)
        assert gt.schema_version == 1
        assert len(gt.form_answers) > 0

    def test_grader_uses_ground_truth(
        self, engine: ExerciseEngine,
    ) -> None:
        from training.grader import Grader
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        grader = Grader()
        sub = {"you.first_name": "Jane"}
        grade = grader.grade_intake(sub, result.ground_truth)
        correct = [f for f in grade.field_feedback
                   if f["field"] == "you.first_name"]
        assert correct[0]["status"] == "correct"

    def test_grader_wrong_answer(self, engine: ExerciseEngine) -> None:
        from training.grader import Grader
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        grader = Grader()
        sub = {"you.first_name": "WRONG"}
        grade = grader.grade_intake(sub, result.ground_truth)
        wrong = [f for f in grade.field_feedback
                 if f["field"] == "you.first_name"]
        assert wrong[0]["status"] == "incorrect"


# =========================================================================
# Concept tags
# =========================================================================

class TestConceptTags:

    def test_concept_tags_present(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.concept_tags is None or isinstance(result.concept_tags, list)

    def test_concept_tags_are_sorted_strings(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        if result.concept_tags:
            assert all(isinstance(t, str) for t in result.concept_tags)
            assert result.concept_tags == sorted(result.concept_tags)

    def test_concept_catalog_registered(
        self, engine: ExerciseEngine,
    ) -> None:
        assert len(engine.concept_catalog.concepts) == 7

    def test_concept_tags_none_when_empty(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(
            mode="intake", difficulty="easy",
            pattern="single_adult", seed=42,
        )
        if result.concept_tags is not None:
            assert len(result.concept_tags) > 0
