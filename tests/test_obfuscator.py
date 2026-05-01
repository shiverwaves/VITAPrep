"""Tests for the obfuscator and C1 Phase 3 pipeline integration.

Covers:
- Obfuscator renders FiredTemplates at all three subtlety levels.
- ExerciseEngine registers all three starter slots.
- Pipeline integration: narrative_slots and interview_notes populated
  when slots fire, None when no slots fire.
- Boilerplate notes included in interview_notes alongside slot-rendered notes.
"""

from datetime import date
from typing import List
from unittest.mock import MagicMock, patch

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
    Scenario,
)
from intake.analyzer.slots.address_mismatch import AddressMismatchSlot
from intake.analyzer.slots.dependent_residency import DependentResidencySlot
from intake.analyzer.slots.zero_income_reason import ZeroIncomeReasonSlot
from intake.analyzer.types import FiredTemplate, InterviewNote
from intake.obfuscator import DIFFICULTY_TO_SUBTLETY, obfuscate
from training.exercise_engine import ExerciseEngine


# =========================================================================
# Helpers
# =========================================================================

def _hh_address():
    return Address(
        street="100 Main St", city="Honolulu",
        state="HI", zip_code="96816",
    )


def _different_address():
    return Address(
        street="200 Oak Ave", city="Hilo",
        state="HI", zip_code="96720",
    )


def _make_household_clean() -> Household:
    """Household where no slots fire: addresses match, income > 0, no dependents."""
    return Household(
        household_id="hh-clean",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=_hh_address(),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30, sex="F", race="white",
                legal_first_name="Jane", legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                id_address=_hh_address(),
                wage_income=50000,
            ),
        ],
    )


def _make_household_address_mismatch() -> Household:
    """Household where address_mismatch fires (different city on ID)."""
    return Household(
        household_id="hh-addr",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=_hh_address(),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30, sex="F", race="white",
                legal_first_name="Jane", legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                id_address=_different_address(),
                wage_income=50000,
            ),
        ],
    )


def _make_household_zero_income() -> Household:
    """Married household where spouse has zero income → zero_income_reason fires."""
    return Household(
        household_id="hh-zero",
        state="HI",
        year=2022,
        pattern="married_with_children",
        address=_hh_address(),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=35, sex="M", race="white",
                legal_first_name="John", legal_last_name="Smith",
                ssn="900-11-1111",
                dob=date(1987, 3, 10),
                id_address=_hh_address(),
                wage_income=60000,
            ),
            Person(
                person_id="p-02",
                relationship=RelationshipType.SPOUSE,
                age=33, sex="F", race="white",
                legal_first_name="Mary", legal_last_name="Smith",
                ssn="900-22-2222",
                dob=date(1989, 7, 20),
                id_address=_hh_address(),
                wage_income=0,
            ),
            Person(
                person_id="p-03",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=5, sex="M", race="white",
                legal_first_name="Tommy", legal_last_name="Smith",
                ssn="900-33-3333",
                dob=date(2017, 1, 15),
                id_address=_hh_address(),
                months_in_home=12,
                is_dependent=True,
            ),
        ],
    )


def _make_household_partial_residency() -> Household:
    """Household with a child at 8 months → dependent_residency fires."""
    return Household(
        household_id="hh-dep",
        state="HI",
        year=2022,
        pattern="single_with_children",
        address=_hh_address(),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=28, sex="F", race="white",
                legal_first_name="Sara", legal_last_name="Lee",
                ssn="900-44-4444",
                dob=date(1994, 11, 5),
                id_address=_hh_address(),
                wage_income=40000,
            ),
            Person(
                person_id="p-02",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=7, sex="F", race="white",
                legal_first_name="Lily", legal_last_name="Lee",
                ssn="900-55-5555",
                dob=date(2015, 4, 12),
                id_address=_hh_address(),
                months_in_home=8,
                is_dependent=True,
            ),
        ],
    )


def _make_scenario(household: Household) -> Scenario:
    """Wrap a household in a minimal Scenario for analyzer/obfuscator."""
    return Scenario(
        scenario_id="sc-test",
        mode="intake",
        difficulty="easy",
        household=household,
        document_paths={},
        created_at="2024-01-01T00:00:00",
    )


# =========================================================================
# 1. Obfuscator unit tests
# =========================================================================

class TestObfuscator:

    def test_empty_narrative_slots(self) -> None:
        scenario = _make_scenario(_make_household_clean())
        notes = obfuscate({}, scenario, "easy")
        assert notes == []

    def test_renders_at_obvious_subtlety(self) -> None:
        hh = _make_household_address_mismatch()
        scenario = _make_scenario(hh)
        slot = AddressMismatchSlot()
        instances = slot.fires_for(scenario)
        templates = slot.templates()
        ft = FiredTemplate(
            slot_name="address_mismatch",
            instance=instances[0],
            template=templates[0],
        )
        notes = obfuscate({"address_mismatch": [ft]}, scenario, "easy")
        assert len(notes) == 1
        assert isinstance(notes[0], InterviewNote)
        assert notes[0].category == "address"
        assert "Hilo" in notes[0].question or "Hilo" in notes[0].answer

    def test_renders_at_moderate_subtlety(self) -> None:
        hh = _make_household_address_mismatch()
        scenario = _make_scenario(hh)
        slot = AddressMismatchSlot()
        instances = slot.fires_for(scenario)
        ft = FiredTemplate(
            slot_name="address_mismatch",
            instance=instances[0],
            template=slot.templates()[0],
        )
        notes = obfuscate({"address_mismatch": [ft]}, scenario, "medium")
        assert len(notes) == 1
        assert notes[0].category == "address"

    def test_renders_at_subtle_subtlety(self) -> None:
        hh = _make_household_address_mismatch()
        scenario = _make_scenario(hh)
        slot = AddressMismatchSlot()
        instances = slot.fires_for(scenario)
        ft = FiredTemplate(
            slot_name="address_mismatch",
            instance=instances[0],
            template=slot.templates()[0],
        )
        notes = obfuscate({"address_mismatch": [ft]}, scenario, "hard")
        assert len(notes) == 1
        assert notes[0].category == "address"

    def test_unknown_difficulty_defaults_to_obvious(self) -> None:
        hh = _make_household_address_mismatch()
        scenario = _make_scenario(hh)
        slot = AddressMismatchSlot()
        instances = slot.fires_for(scenario)
        ft = FiredTemplate(
            slot_name="address_mismatch",
            instance=instances[0],
            template=slot.templates()[0],
        )
        notes_unknown = obfuscate({"address_mismatch": [ft]}, scenario, "bogus")
        notes_easy = obfuscate({"address_mismatch": [ft]}, scenario, "easy")
        assert notes_unknown[0].question == notes_easy[0].question

    def test_multiple_slots_multiple_instances(self) -> None:
        hh = _make_household_partial_residency()
        hh.members[0].id_address = _different_address()
        scenario = _make_scenario(hh)

        addr_slot = AddressMismatchSlot()
        dep_slot = DependentResidencySlot()

        addr_instances = addr_slot.fires_for(scenario)
        dep_instances = dep_slot.fires_for(scenario)

        slots = {}
        if addr_instances:
            slots["address_mismatch"] = [
                FiredTemplate("address_mismatch", i, addr_slot.templates()[0])
                for i in addr_instances
            ]
        if dep_instances:
            slots["dependent_residency"] = [
                FiredTemplate("dependent_residency", i, dep_slot.templates()[-1])
                for i in dep_instances
            ]

        notes = obfuscate(slots, scenario, "easy")
        assert len(notes) == len(addr_instances) + len(dep_instances)
        categories = {n.category for n in notes}
        assert "address" in categories
        assert "dependent" in categories

    def test_difficulty_to_subtlety_mapping(self) -> None:
        assert DIFFICULTY_TO_SUBTLETY["easy"] == "obvious"
        assert DIFFICULTY_TO_SUBTLETY["medium"] == "moderate"
        assert DIFFICULTY_TO_SUBTLETY["hard"] == "subtle"

    def test_source_slot_populated(self) -> None:
        hh = _make_household_address_mismatch()
        scenario = _make_scenario(hh)
        slot = AddressMismatchSlot()
        instances = slot.fires_for(scenario)
        ft = FiredTemplate(
            slot_name="address_mismatch",
            instance=instances[0],
            template=slot.templates()[0],
        )
        notes = obfuscate({"address_mismatch": [ft]}, scenario, "easy")
        assert notes[0].source_slot == "RecentMoveTemplate"


# =========================================================================
# 2. Slot registration in ExerciseEngine
# =========================================================================

class TestSlotRegistration:

    def test_engine_registers_three_slots(self) -> None:
        with patch("training.exercise_engine.HouseholdGenerator"):
            engine = ExerciseEngine(state="HI", year=2022)
        slot_names = [s.name for s in engine.analyzer.slots]
        assert "address_mismatch" in slot_names
        assert "zero_income_reason" in slot_names
        assert "dependent_residency" in slot_names

    def test_engine_has_exactly_three_slots(self) -> None:
        with patch("training.exercise_engine.HouseholdGenerator"):
            engine = ExerciseEngine(state="HI", year=2022)
        assert len(engine.analyzer.slots) == 3


# =========================================================================
# 3. Pipeline integration — full generate_scenario
# =========================================================================

def _mock_inject(household, difficulty="medium", error_count=3):
    from training.error_injector import ErrorInjector
    real = ErrorInjector()
    return real.inject(household, difficulty=difficulty, error_count=error_count)


def _engine_with_household(household: Household) -> ExerciseEngine:
    """Build an ExerciseEngine that returns the given household."""
    eng = ExerciseEngine.__new__(ExerciseEngine)
    mock_gen = MagicMock()
    mock_gen.generate_with_pii.return_value = household
    mock_gen.year = 2022
    eng.generator = mock_gen
    eng.error_injector = MagicMock()
    eng.error_injector.inject.side_effect = _mock_inject
    from intake.analyzer.analyzer import ScenarioAnalyzer
    eng.analyzer = ScenarioAnalyzer()
    eng.analyzer.register(AddressMismatchSlot())
    eng.analyzer.register(ZeroIncomeReasonSlot())
    eng.analyzer.register(DependentResidencySlot())
    return eng


class TestPipelineIntegration:

    def test_clean_scenario_no_slot_notes(self) -> None:
        eng = _engine_with_household(_make_household_clean())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        assert result.narrative_slots is None or result.narrative_slots == {}
        slot_notes = [
            n for n in (result.interview_notes or [])
            if n["source_slot"] is not None
        ]
        assert slot_notes == []
        boilerplate = [
            n for n in result.interview_notes
            if n["source_slot"] is None
        ]
        assert len(boilerplate) > 0

    def test_address_mismatch_populates_notes(self) -> None:
        eng = _engine_with_household(_make_household_address_mismatch())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        assert result.narrative_slots is not None
        assert "address_mismatch" in result.narrative_slots
        assert result.interview_notes is not None
        assert len(result.interview_notes) > 0
        assert result.interview_notes[0]["category"] == "address"

    def test_zero_income_populates_notes(self) -> None:
        eng = _engine_with_household(_make_household_zero_income())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        assert result.interview_notes is not None
        income_notes = [n for n in result.interview_notes if n["category"] == "income"]
        assert len(income_notes) > 0

    def test_partial_residency_populates_notes(self) -> None:
        eng = _engine_with_household(_make_household_partial_residency())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        assert result.interview_notes is not None
        dep_notes = [n for n in result.interview_notes if n["category"] == "dependent"]
        assert len(dep_notes) > 0

    def test_narrative_slots_serialized_as_dicts(self) -> None:
        eng = _engine_with_household(_make_household_address_mismatch())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        for slot_name, fired_list in result.narrative_slots.items():
            assert isinstance(slot_name, str)
            for entry in fired_list:
                assert "slot_name" in entry
                assert "instance_id" in entry

    def test_interview_notes_serialized_as_dicts(self) -> None:
        eng = _engine_with_household(_make_household_address_mismatch())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        for note in result.interview_notes:
            assert isinstance(note, dict)
            assert "category" in note
            assert "question" in note
            assert "answer" in note
            assert "source_slot" in note

    def test_boilerplate_notes_included(self) -> None:
        eng = _engine_with_household(_make_household_address_mismatch())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        boilerplate = [n for n in result.interview_notes if n["source_slot"] is None]
        assert len(boilerplate) > 0

    def test_ground_truth_still_computed(self) -> None:
        eng = _engine_with_household(_make_household_address_mismatch())
        result = eng.generate_scenario(mode="intake", difficulty="easy")
        assert result.ground_truth is not None
        assert "form_answers" in result.ground_truth

    def test_verify_mode_with_slots(self) -> None:
        eng = _engine_with_household(_make_household_address_mismatch())
        result = eng.generate_scenario(
            mode="verify", difficulty="medium", error_count=1,
        )
        assert result.interview_notes is not None
        assert len(result.injected_errors) > 0

    def test_difficulty_affects_subtlety(self) -> None:
        eng_easy = _engine_with_household(_make_household_address_mismatch())
        eng_hard = _engine_with_household(_make_household_address_mismatch())
        easy = eng_easy.generate_scenario(mode="intake", difficulty="easy")
        hard = eng_hard.generate_scenario(mode="intake", difficulty="hard")
        assert easy.interview_notes[0]["question"] != hard.interview_notes[0]["question"]
