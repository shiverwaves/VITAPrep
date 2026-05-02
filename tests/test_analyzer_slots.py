"""Tests for C1 Phase 2 starter slots.

Validates:
- Each slot fires correctly against hand-built scenario fixtures.
- Template requirements() are selective — not all templates fire
  for every instance.
- Slot evaluation constraint: slots work with lifecycle fields = None.
- render() produces valid InterviewNote at all three subtlety levels.
- Fallback templates prevent Unrescuable for common cases.
"""

from datetime import date
from typing import Any

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
    Scenario,
)
from intake.analyzer.analyzer import ScenarioAnalyzer
from intake.analyzer.types import FiredTemplate, InterviewNote, Unrescuable
from intake.analyzer.slots.address_mismatch import (
    AddressMismatchSlot,
    GenericAddressUpdateTemplate,
    RecentMoveTemplate,
    SameAreaNewStreetTemplate,
)
from intake.analyzer.slots.zero_income_reason import (
    BetweenJobsTemplate,
    FullTimeStudentTemplate,
    StayAtHomeParentTemplate,
    ZeroIncomeReasonSlot,
)
from intake.analyzer.slots.dependent_residency import (
    DependentResidencySlot,
    JoinedMidYearTemplate,
    PartialYearFallbackTemplate,
    SharedCustodyTemplate,
)


# =========================================================================
# Helpers
# =========================================================================

SUBTLETY_LEVELS = ["obvious", "moderate", "subtle"]


def _scenario(household: Household) -> Scenario:
    return Scenario(
        scenario_id="sc-test",
        mode="encounter",
        difficulty="easy",
        household=household,
    )


def _addr(street="100 Main St", city="Honolulu", state="HI", zip_code="96816"):
    return Address(street=street, city=city, state=state, zip_code=zip_code)


def _person(**kwargs) -> Person:
    defaults = dict(
        person_id="p-01",
        relationship=RelationshipType.HOUSEHOLDER,
        age=35, sex="M",
        legal_first_name="Test", legal_last_name="Person",
        ssn="900-11-1111", dob=date(1987, 1, 1),
    )
    defaults.update(kwargs)
    return Person(**defaults)


# =========================================================================
# address_mismatch slot
# =========================================================================

class TestAddressMismatchSlot:

    def test_fires_when_id_address_differs(self) -> None:
        hh = Household(
            household_id="hh-1", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[_person(
                id_type="drivers_license",
                id_address=_addr(street="999 Old Rd"),
            )],
        )
        slot = AddressMismatchSlot()
        assert len(slot.fires_for(_scenario(hh))) == 1

    def test_does_not_fire_when_addresses_match(self) -> None:
        addr = _addr()
        hh = Household(
            household_id="hh-2", state="HI", year=2022,
            pattern="single_adult", address=addr,
            members=[_person(id_type="drivers_license", id_address=addr)],
        )
        slot = AddressMismatchSlot()
        assert slot.fires_for(_scenario(hh)) == []

    def test_does_not_fire_without_id_address(self) -> None:
        hh = Household(
            household_id="hh-3", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[_person()],
        )
        slot = AddressMismatchSlot()
        assert slot.fires_for(_scenario(hh)) == []

    def test_fires_for_multiple_members(self) -> None:
        hh = Household(
            household_id="hh-4", state="HI", year=2022,
            pattern="married_couple_no_children", address=_addr(),
            members=[
                _person(
                    person_id="p-01",
                    id_type="drivers_license",
                    id_address=_addr(street="Old St 1"),
                ),
                _person(
                    person_id="p-02",
                    relationship=RelationshipType.SPOUSE,
                    id_type="drivers_license",
                    id_address=_addr(street="Old St 2"),
                ),
            ],
        )
        slot = AddressMismatchSlot()
        assert len(slot.fires_for(_scenario(hh))) == 2


class TestAddressMismatchTemplates:

    def test_recent_move_fires_for_different_city(self) -> None:
        person = _person(id_address=_addr(city="Kailua"))
        hh = Household(
            household_id="hh-t1", state="HI", year=2022,
            pattern="single_adult", address=_addr(city="Honolulu"),
            members=[person],
        )
        t = RecentMoveTemplate()
        assert t.requirements(_scenario(hh), person) is True

    def test_recent_move_does_not_fire_same_city(self) -> None:
        person = _person(id_address=_addr(street="999 Other"))
        hh = Household(
            household_id="hh-t2", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[person],
        )
        t = RecentMoveTemplate()
        assert t.requirements(_scenario(hh), person) is False

    def test_same_area_fires_for_same_city_diff_street(self) -> None:
        person = _person(id_address=_addr(street="999 Other"))
        hh = Household(
            household_id="hh-t3", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[person],
        )
        t = SameAreaNewStreetTemplate()
        assert t.requirements(_scenario(hh), person) is True

    def test_same_area_does_not_fire_different_city(self) -> None:
        person = _person(id_address=_addr(city="Kailua"))
        hh = Household(
            household_id="hh-t4", state="HI", year=2022,
            pattern="single_adult", address=_addr(city="Honolulu"),
            members=[person],
        )
        t = SameAreaNewStreetTemplate()
        assert t.requirements(_scenario(hh), person) is False

    def test_generic_always_matches(self) -> None:
        t = GenericAddressUpdateTemplate()
        assert t.requirements(None, None) is True

    @pytest.mark.parametrize("subtlety", SUBTLETY_LEVELS)
    def test_recent_move_renders_all_subtleties(self, subtlety) -> None:
        person = _person(id_address=_addr(city="Kailua"))
        hh = Household(
            household_id="hh-r1", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[person],
        )
        note = RecentMoveTemplate().render(_scenario(hh), person, subtlety)
        assert isinstance(note, InterviewNote)
        assert note.category == "address"
        assert len(note.question) > 0
        assert len(note.answer) > 0

    @pytest.mark.parametrize("subtlety", SUBTLETY_LEVELS)
    def test_same_area_renders_all_subtleties(self, subtlety) -> None:
        person = _person(id_address=_addr(street="999 Other"))
        hh = Household(
            household_id="hh-r2", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[person],
        )
        note = SameAreaNewStreetTemplate().render(
            _scenario(hh), person, subtlety,
        )
        assert isinstance(note, InterviewNote)
        assert note.category == "address"


# =========================================================================
# zero_income_reason slot
# =========================================================================

class TestZeroIncomeReasonSlot:

    def test_fires_for_zero_income_householder(self) -> None:
        hh = Household(
            household_id="hh-z1", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[_person(wage_income=0)],
        )
        slot = ZeroIncomeReasonSlot()
        assert len(slot.fires_for(_scenario(hh))) == 1

    def test_does_not_fire_with_income(self) -> None:
        hh = Household(
            household_id="hh-z2", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[_person(wage_income=50000)],
        )
        slot = ZeroIncomeReasonSlot()
        assert slot.fires_for(_scenario(hh)) == []

    def test_does_not_fire_for_dependents(self) -> None:
        hh = Household(
            household_id="hh-z3", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[
                _person(wage_income=50000),
                _person(
                    person_id="p-child", age=10,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, wage_income=0,
                ),
            ],
        )
        slot = ZeroIncomeReasonSlot()
        # Only filers, not dependents
        assert slot.fires_for(_scenario(hh)) == []

    def test_fires_for_zero_income_spouse(self) -> None:
        hh = Household(
            household_id="hh-z4", state="HI", year=2022,
            pattern="married_couple_no_children", address=_addr(),
            members=[
                _person(wage_income=60000),
                _person(
                    person_id="p-sp",
                    relationship=RelationshipType.SPOUSE,
                    age=33, sex="F",
                    legal_first_name="Spouse",
                    wage_income=0,
                ),
            ],
        )
        slot = ZeroIncomeReasonSlot()
        fired = slot.fires_for(_scenario(hh))
        assert len(fired) == 1
        assert fired[0].person_id == "p-sp"


class TestZeroIncomeTemplates:

    def test_stay_at_home_parent_requires_married_with_deps(self) -> None:
        spouse = _person(
            person_id="p-sp", relationship=RelationshipType.SPOUSE,
            age=33, sex="F", wage_income=0,
        )
        child = _person(
            person_id="p-ch", relationship=RelationshipType.BIOLOGICAL_CHILD,
            age=5, is_dependent=True,
        )
        hh = Household(
            household_id="hh-st1", state="HI", year=2022,
            pattern="married_couple_with_children", address=_addr(),
            members=[_person(wage_income=60000), spouse, child],
        )
        t = StayAtHomeParentTemplate()
        assert t.requirements(_scenario(hh), spouse) is True

    def test_stay_at_home_parent_does_not_fire_single(self) -> None:
        hh = Household(
            household_id="hh-st2", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[_person(wage_income=0)],
        )
        t = StayAtHomeParentTemplate()
        assert t.requirements(_scenario(hh), hh.members[0]) is False

    def test_stay_at_home_parent_does_not_fire_no_deps(self) -> None:
        hh = Household(
            household_id="hh-st3", state="HI", year=2022,
            pattern="married_couple_no_children", address=_addr(),
            members=[
                _person(wage_income=60000),
                _person(
                    person_id="p-sp",
                    relationship=RelationshipType.SPOUSE,
                    wage_income=0,
                ),
            ],
        )
        t = StayAtHomeParentTemplate()
        assert t.requirements(_scenario(hh), hh.members[1]) is False

    def test_student_template_requires_student_flag(self) -> None:
        person = _person(is_full_time_student=True, wage_income=0)
        t = FullTimeStudentTemplate()
        assert t.requirements(None, person) is True

    def test_student_template_does_not_fire_non_student(self) -> None:
        person = _person(is_full_time_student=False, wage_income=0)
        t = FullTimeStudentTemplate()
        assert t.requirements(None, person) is False

    def test_between_jobs_always_matches(self) -> None:
        t = BetweenJobsTemplate()
        assert t.requirements(None, _person()) is True

    @pytest.mark.parametrize("subtlety", SUBTLETY_LEVELS)
    def test_stay_at_home_renders_all_subtleties(self, subtlety) -> None:
        spouse = _person(
            person_id="p-sp", relationship=RelationshipType.SPOUSE,
            sex="F", wage_income=0,
        )
        child = _person(
            person_id="p-ch", relationship=RelationshipType.BIOLOGICAL_CHILD,
            age=5, is_dependent=True,
        )
        hh = Household(
            household_id="hh-r", state="HI", year=2022,
            pattern="married_couple_with_children", address=_addr(),
            members=[_person(wage_income=60000), spouse, child],
        )
        note = StayAtHomeParentTemplate().render(
            _scenario(hh), spouse, subtlety,
        )
        assert isinstance(note, InterviewNote)
        assert note.category == "income"

    @pytest.mark.parametrize("subtlety", SUBTLETY_LEVELS)
    def test_between_jobs_renders_all_subtleties(self, subtlety) -> None:
        person = _person(wage_income=0)
        note = BetweenJobsTemplate().render(None, person, subtlety)
        assert isinstance(note, InterviewNote)
        assert note.category == "income"


# =========================================================================
# dependent_residency slot
# =========================================================================

class TestDependentResidencySlot:

    def test_fires_for_partial_year_child(self) -> None:
        hh = Household(
            household_id="hh-d1", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[
                _person(),
                _person(
                    person_id="p-ch", age=8,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, months_in_home=7,
                ),
            ],
        )
        slot = DependentResidencySlot()
        fired = slot.fires_for(_scenario(hh))
        assert len(fired) == 1
        assert fired[0].person_id == "p-ch"

    def test_does_not_fire_for_full_year(self) -> None:
        hh = Household(
            household_id="hh-d2", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[
                _person(),
                _person(
                    person_id="p-ch", age=8,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, months_in_home=12,
                ),
            ],
        )
        slot = DependentResidencySlot()
        assert slot.fires_for(_scenario(hh)) == []

    def test_does_not_fire_for_zero_months(self) -> None:
        hh = Household(
            household_id="hh-d3", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[
                _person(),
                _person(
                    person_id="p-ch", age=8,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, months_in_home=0,
                ),
            ],
        )
        slot = DependentResidencySlot()
        assert slot.fires_for(_scenario(hh)) == []

    def test_fires_for_multiple_partial_year_children(self) -> None:
        hh = Household(
            household_id="hh-d4", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[
                _person(),
                _person(
                    person_id="p-c1", age=10,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, months_in_home=8,
                ),
                _person(
                    person_id="p-c2", age=6,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, months_in_home=5,
                ),
            ],
        )
        slot = DependentResidencySlot()
        assert len(slot.fires_for(_scenario(hh))) == 2


class TestDependentResidencyTemplates:

    def test_shared_custody_requires_other_parent_and_month_range(self) -> None:
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=6,
            has_other_parent=True,
        )
        t = SharedCustodyTemplate()
        assert t.requirements(None, child) is True

    def test_shared_custody_does_not_fire_without_other_parent(self) -> None:
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=6,
            has_other_parent=False,
        )
        t = SharedCustodyTemplate()
        assert t.requirements(None, child) is False

    def test_shared_custody_does_not_fire_outside_month_range(self) -> None:
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=10,
            has_other_parent=True,
        )
        t = SharedCustodyTemplate()
        assert t.requirements(None, child) is False

    def test_joined_mid_year_requires_flag_and_months(self) -> None:
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=7,
            entered_household_during_year=True,
        )
        t = JoinedMidYearTemplate()
        assert t.requirements(None, child) is True

    def test_joined_mid_year_does_not_fire_without_flag(self) -> None:
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=7,
        )
        t = JoinedMidYearTemplate()
        assert t.requirements(None, child) is False

    def test_joined_mid_year_does_not_fire_under_6_months(self) -> None:
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=4,
            entered_household_during_year=True,
        )
        t = JoinedMidYearTemplate()
        assert t.requirements(None, child) is False

    def test_fallback_always_matches(self) -> None:
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=3,
        )
        t = PartialYearFallbackTemplate()
        assert t.requirements(None, child) is True

    @pytest.mark.parametrize("subtlety", SUBTLETY_LEVELS)
    def test_shared_custody_renders_all_subtleties(self, subtlety) -> None:
        child = _person(
            person_id="p-ch", age=8, sex="F",
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=6,
            has_other_parent=True,
            legal_first_name="Lily",
        )
        hh = Household(
            household_id="hh-r", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[_person(), child],
        )
        note = SharedCustodyTemplate().render(_scenario(hh), child, subtlety)
        assert isinstance(note, InterviewNote)
        assert note.category == "dependent"

    @pytest.mark.parametrize("subtlety", SUBTLETY_LEVELS)
    def test_fallback_renders_all_subtleties(self, subtlety) -> None:
        child = _person(
            person_id="p-ch", age=8, months_in_home=5,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, legal_first_name="Sam",
        )
        hh = Household(
            household_id="hh-r2", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[_person(), child],
        )
        note = PartialYearFallbackTemplate().render(
            _scenario(hh), child, subtlety,
        )
        assert isinstance(note, InterviewNote)
        assert note.category == "dependent"


# =========================================================================
# Slot evaluation constraint: lifecycle fields None
# =========================================================================

class TestSlotConstraint:

    @pytest.mark.parametrize("slot_cls", [
        AddressMismatchSlot,
        ZeroIncomeReasonSlot,
        DependentResidencySlot,
    ])
    def test_slots_work_with_lifecycle_fields_none(self, slot_cls) -> None:
        """All three slots run without touching lifecycle fields."""
        hh = Household(
            household_id="hh-con", state="HI", year=2022,
            pattern="single_adult", address=_addr(),
            members=[_person(
                id_type="drivers_license",
                id_address=_addr(street="Old St"),
            )],
        )
        sc = Scenario(
            scenario_id="sc-con", mode="encounter", difficulty="easy",
            household=hh,
            ground_truth=None,
            concept_tags=None,
            interview_notes=None,
        )
        slot = slot_cls()
        # Should not raise
        slot.fires_for(sc)


# =========================================================================
# Analyzer integration: all three slots together
# =========================================================================

class TestAnalyzerWithAllSlots:

    def test_all_slots_registered(self) -> None:
        analyzer = ScenarioAnalyzer()
        analyzer.register(AddressMismatchSlot())
        analyzer.register(ZeroIncomeReasonSlot())
        analyzer.register(DependentResidencySlot())
        assert len(analyzer.slots) == 3

    def test_no_unrescuable_with_fallback_templates(self) -> None:
        """Scenarios with partial-year children never cause Unrescuable
        because the fallback template always matches."""
        hh = Household(
            household_id="hh-int", state="HI", year=2022,
            pattern="single_parent", address=_addr(),
            members=[
                _person(wage_income=40000),
                _person(
                    person_id="p-ch", age=8,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, months_in_home=7,
                ),
            ],
        )
        analyzer = ScenarioAnalyzer()
        analyzer.register(AddressMismatchSlot())
        analyzer.register(ZeroIncomeReasonSlot())
        analyzer.register(DependentResidencySlot())

        result = analyzer.analyze(_scenario(hh))
        assert "dependent_residency" in result
        assert len(result["dependent_residency"]) == 1

    def test_multiple_slots_fire_together(self) -> None:
        """Address mismatch + zero income + partial-year child."""
        spouse = _person(
            person_id="p-sp", relationship=RelationshipType.SPOUSE,
            age=33, sex="F", wage_income=0,
            id_type="drivers_license",
            id_address=_addr(city="Kailua"),
        )
        child = _person(
            person_id="p-ch", age=8,
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            is_dependent=True, months_in_home=8,
        )
        hh = Household(
            household_id="hh-multi", state="HI", year=2022,
            pattern="married_couple_with_children", address=_addr(),
            members=[_person(wage_income=60000), spouse, child],
        )
        analyzer = ScenarioAnalyzer()
        analyzer.register(AddressMismatchSlot())
        analyzer.register(ZeroIncomeReasonSlot())
        analyzer.register(DependentResidencySlot())

        result = analyzer.analyze(_scenario(hh))
        assert "address_mismatch" in result
        assert "zero_income_reason" in result
        assert "dependent_residency" in result

    def test_clean_scenario_fires_no_slots(self) -> None:
        """Householder with income, full-year child, matching address."""
        addr = _addr()
        hh = Household(
            household_id="hh-clean", state="HI", year=2022,
            pattern="single_parent", address=addr,
            members=[
                _person(
                    wage_income=50000,
                    id_type="drivers_license",
                    id_address=addr,
                ),
                _person(
                    person_id="p-ch", age=10,
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    is_dependent=True, months_in_home=12,
                ),
            ],
        )
        analyzer = ScenarioAnalyzer()
        analyzer.register(AddressMismatchSlot())
        analyzer.register(ZeroIncomeReasonSlot())
        analyzer.register(DependentResidencySlot())

        result = analyzer.analyze(_scenario(hh))
        assert result == {}
