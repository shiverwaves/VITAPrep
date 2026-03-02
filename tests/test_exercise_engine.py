"""TDD tests for the exercise engine — Sprint 6 Step 3.

The ExerciseEngine orchestrates the full pipeline:
generate → PII → render docs → inject errors → client profile → package.

These tests mock the heavy dependencies (HouseholdGenerator,
DocumentRenderer) so they run fast without SQLite or WeasyPrint.

Contract
--------
ExerciseEngine.generate_scenario(mode, difficulty, error_count, pattern, seed)
  → Scenario

Requirements:
1. Returns a Scenario with a unique scenario_id and created_at timestamp.
2. Household is fully populated (demographics + PII).
3. document_paths is a non-empty dict of {label: path_string}.
4. Mode "intake":
   - injected_errors is empty (student fills from clean docs).
   - client_facts populated and filtered by difficulty.
5. Mode "verify":
   - injected_errors populated with error_count errors.
   - client_facts populated.
6. Mode "crosscheck": reserved for future — should raise or fallback.
7. difficulty propagates to error injection and client fact filtering.
8. pattern is forwarded to the household generator.
9. seed is forwarded for reproducibility.
"""

from datetime import date
from pathlib import Path
from typing import Dict, Optional
from unittest.mock import MagicMock, patch

import pytest

from generator.models import (
    Address,
    ClientFact,
    Household,
    InjectedError,
    Person,
    RelationshipType,
    Scenario,
)
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


def _mock_doc_paths() -> Dict[str, Path]:
    return {
        "ssn_p-01": Path("/tmp/docs/ssn_p-01.pdf"),
        "id_p-01": Path("/tmp/docs/dl_p-01.pdf"),
    }


# =========================================================================
# Fixtures — patch heavy dependencies
# =========================================================================

@pytest.fixture
def engine():
    """Create an ExerciseEngine with mocked generator and renderer."""
    with patch("training.exercise_engine.HouseholdGenerator") as MockGen, \
         patch("training.exercise_engine.DocumentRenderer") as MockRend:
        mock_gen_instance = MockGen.return_value
        mock_gen_instance.generate_with_pii.return_value = _make_household()

        mock_rend_instance = MockRend.return_value
        mock_rend_instance.render_household_documents.return_value = _mock_doc_paths()

        eng = ExerciseEngine.__new__(ExerciseEngine)
        eng.generator = mock_gen_instance
        eng.renderer = mock_rend_instance
        eng.error_injector = MagicMock()
        # Make error_injector.inject return a realistic result
        eng.error_injector.inject.side_effect = _mock_inject
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
# 3. Document paths
# =========================================================================

class TestDocuments:

    def test_document_paths_populated(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert len(result.document_paths) > 0

    def test_document_paths_are_strings(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        for key, val in result.document_paths.items():
            assert isinstance(key, str)
            assert isinstance(val, str)

    def test_renderer_called(self, engine: ExerciseEngine) -> None:
        engine.generate_scenario(mode="intake", difficulty="easy")
        engine.renderer.render_household_documents.assert_called_once()


# =========================================================================
# 4. Intake mode specifics
# =========================================================================

class TestIntakeMode:

    def test_no_injected_errors(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.injected_errors == []

    def test_client_facts_populated(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert len(result.client_facts) > 0

    def test_client_facts_are_client_fact_objects(
        self, engine: ExerciseEngine,
    ) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert all(isinstance(f, ClientFact) for f in result.client_facts)


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

    def test_client_facts_present(self, engine: ExerciseEngine) -> None:
        result = engine.generate_scenario(
            mode="verify", difficulty="medium", error_count=2,
        )
        assert len(result.client_facts) > 0

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

    def test_easy_has_more_client_facts_than_hard(
        self, engine: ExerciseEngine,
    ) -> None:
        easy = engine.generate_scenario(mode="intake", difficulty="easy")
        hard = engine.generate_scenario(mode="intake", difficulty="hard")
        assert len(easy.client_facts) >= len(hard.client_facts)
