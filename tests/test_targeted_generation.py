"""Tests for Restructure E — targeted generation.

Tests cover:
- GenerationHints population by each concept
- Hint merging logic in ExerciseEngine
- Generator respects hints (children months, SE, SS, homeowner, wage cap)
- Concept-targeted generation produces scenarios that fire requested concepts
- ConceptMissed exception on failure
- API validation of concept names
"""

from datetime import date
from typing import Optional
from unittest.mock import MagicMock, patch

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
    Scenario,
)
from learn.concepts.base import GenerationHints
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
from training.exercise_engine import (
    ConceptMissed,
    ExerciseEngine,
    MAX_GEN_ATTEMPTS,
)


# =========================================================================
# 1. Generation hints per concept
# =========================================================================

class TestConceptHints:

    def test_qualifying_child_residency_hints(self) -> None:
        c = QualifyingChildResidencyConcept()
        h = c.generation_hints()
        assert "single_parent" in h.preferred_patterns
        assert h.child_months_in_home_range == (1, 11)

    def test_hoh_qualifying_person_hints(self) -> None:
        c = HoHQualifyingPersonConcept()
        h = c.generation_hints()
        assert h.preferred_patterns == ["single_parent"]

    def test_refundable_credit_only_filer_hints(self) -> None:
        c = RefundableCreditOnlyFilerConcept()
        h = c.generation_hints()
        assert "single_parent" in h.preferred_patterns
        assert h.max_wage_income == 12000

    def test_self_employment_threshold_hints(self) -> None:
        c = SelfEmploymentThresholdConcept()
        h = c.generation_hints()
        assert h.force_self_employment is True

    def test_social_security_taxability_hints(self) -> None:
        c = SocialSecurityTaxabilityConcept()
        h = c.generation_hints()
        assert h.force_ss_recipient is True
        assert h.min_other_income == 15000

    def test_standard_vs_itemized_hints(self) -> None:
        c = StandardVsItemizedConcept()
        h = c.generation_hints()
        assert h.force_homeowner is True

    def test_full_time_student_dependent_hints(self) -> None:
        from learn.concepts.education import FullTimeStudentDependentConcept
        c = FullTimeStudentDependentConcept()
        h = c.generation_hints()
        assert h.force_full_time_student is True
        assert "single_parent" in h.preferred_patterns


# =========================================================================
# 2. Hint merging
# =========================================================================

class TestHintMerging:

    @pytest.fixture
    def engine(self):
        with patch("training.exercise_engine.HouseholdGenerator"):
            eng = ExerciseEngine.__new__(ExerciseEngine)
            from learn.concept_catalog import ConceptCatalog
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

    def test_single_concept_merge(self, engine) -> None:
        merged = engine._merge_hints(["self_employment_threshold"])
        assert merged.force_self_employment is True
        assert merged.force_ss_recipient is False

    def test_multi_concept_merge(self, engine) -> None:
        merged = engine._merge_hints([
            "self_employment_threshold",
            "social_security_taxability",
        ])
        assert merged.force_self_employment is True
        assert merged.force_ss_recipient is True
        assert merged.min_other_income == 15000

    def test_preferred_patterns_deduplicated(self, engine) -> None:
        merged = engine._merge_hints([
            "qualifying_child_residency",
            "hoh_qualifying_person",
        ])
        assert "single_parent" in merged.preferred_patterns
        assert merged.preferred_patterns.count("single_parent") == 1

    def test_unknown_concept_ignored(self, engine) -> None:
        merged = engine._merge_hints(["nonexistent_concept"])
        assert merged == GenerationHints()

    def test_empty_concepts_returns_empty(self, engine) -> None:
        merged = engine._merge_hints([])
        assert merged == GenerationHints()


# =========================================================================
# 3. ConceptMissed exception
# =========================================================================

class TestConceptMissed:

    def test_exception_message(self) -> None:
        exc = ConceptMissed({"self_employment_threshold", "hoh_qualifying_person"})
        assert "hoh_qualifying_person" in str(exc)
        assert "self_employment_threshold" in str(exc)

    def test_missing_attribute(self) -> None:
        exc = ConceptMissed({"foo"})
        assert exc.missing == {"foo"}


# =========================================================================
# 4. MAX_GEN_ATTEMPTS constant
# =========================================================================

class TestConstants:

    def test_max_gen_attempts(self) -> None:
        assert MAX_GEN_ATTEMPTS == 5


# =========================================================================
# 5. Generator hint application (unit tests)
# =========================================================================

def _addr():
    return Address(
        street="100 Main St", city="Honolulu",
        state="HI", zip_code="96816",
    )


def _person(
    pid: str = "p-01",
    rel: RelationshipType = RelationshipType.HOUSEHOLDER,
    age: int = 30,
    wage_income: int = 50000,
    se_income: int = 0,
    ss_income: int = 0,
    is_dependent: bool = False,
) -> Person:
    return Person(
        person_id=pid,
        relationship=rel,
        age=age, sex="F", race="white",
        legal_first_name="Jane", legal_last_name="Doe",
        ssn=f"900-{pid[-2:]}-0000",
        dob=date(2022 - age, 1, 1),
        id_address=_addr(),
        wage_income=wage_income,
        self_employment_income=se_income,
        social_security_income=ss_income,
        is_dependent=is_dependent,
    )


def _household(members: list, pattern: str = "single_adult") -> Household:
    return Household(
        household_id="hh-test",
        state="HI",
        year=2022,
        pattern=pattern,
        address=_addr(),
        members=members,
    )


class TestChildMonthsHint:

    def test_months_overridden_when_hint_set(self) -> None:
        from generator.children import ChildGenerator
        cg = ChildGenerator({})
        hh = _household(
            [_person(age=35)],
            pattern="single_parent",
        )
        hh.expected_children_range = (1, 3)

        hints = GenerationHints(child_months_in_home_range=(3, 7))
        children = cg.generate_children(hh, hints=hints)
        assert len(children) >= 1
        partial = [c for c in children if 0 < c.months_in_home < 12]
        assert len(partial) >= 1
        for c in partial:
            assert 3 <= c.months_in_home <= 7

    def test_months_default_12_without_hint(self) -> None:
        from generator.children import ChildGenerator
        cg = ChildGenerator({})
        hh = _household(
            [_person(age=35)],
            pattern="single_parent",
        )
        hh.expected_children_range = (1, 3)
        children = cg.generate_children(hh)
        for c in children:
            assert c.months_in_home == 12


class TestExpenseHint:

    def test_force_homeowner(self) -> None:
        from generator.expenses import ExpenseGenerator
        eg = ExpenseGenerator({}, state="HI")
        hh = _household([_person(wage_income=30000)])
        hints = GenerationHints(force_homeowner=True)
        eg.overlay(hh, hints=hints)
        assert hh.is_homeowner is True
        assert hh.property_taxes > 0


class TestIncomeHint:

    def test_force_self_employment(self) -> None:
        from generator.income import IncomeGenerator
        ig = IncomeGenerator({}, tax_year=2022)
        hh = _household([_person(wage_income=0)])
        hh.members[0].employment_status = "employed"
        hints = GenerationHints(force_self_employment=True)
        ig.overlay(hh, hints=hints)
        has_se = any(p.self_employment_income >= 400 for p in hh.members)
        assert has_se

    def test_max_wage_income(self) -> None:
        from generator.income import IncomeGenerator
        ig = IncomeGenerator({}, tax_year=2022)
        hh = _household([_person(wage_income=0)])
        hh.members[0].employment_status = "employed"
        hints = GenerationHints(max_wage_income=5000)
        ig.overlay(hh, hints=hints)
        for p in hh.members:
            if p.wage_income > 0:
                assert p.wage_income <= 5000

    def test_force_ss_recipient(self) -> None:
        from generator.income import IncomeGenerator
        ig = IncomeGenerator({}, tax_year=2022)
        hh = _household([_person(age=40, wage_income=0)])
        hh.members[0].employment_status = "employed"
        hints = GenerationHints(force_ss_recipient=True)
        ig.overlay(hh, hints=hints)
        has_ss = any(p.social_security_income > 0 for p in hh.members)
        assert has_ss

    def test_min_other_income(self) -> None:
        from generator.income import IncomeGenerator
        ig = IncomeGenerator({}, tax_year=2022)
        p = _person(age=40, wage_income=0)
        p.employment_status = "employed"
        hh = _household([p])
        hints = GenerationHints(min_other_income=20000)
        ig.overlay(hh, hints=hints)
        total = hh.total_household_income()
        assert total >= 20000


# =========================================================================
# 6. Pipeline pattern selection with hints
# =========================================================================

class TestPatternSelection:

    def test_preferred_patterns_used(self) -> None:
        from generator.pipeline import HouseholdGenerator
        with patch.object(HouseholdGenerator, "__init__", lambda self, *a, **kw: None):
            gen = HouseholdGenerator.__new__(HouseholdGenerator)
            gen.state = "HI"
            gen.year = 2022
            gen.distributions = {}
            hints = GenerationHints(preferred_patterns=["single_parent"])
            hh = gen._select_pattern(hints=hints)
            assert hh.pattern == "single_parent"

    def test_explicit_pattern_overrides_hints(self) -> None:
        from generator.pipeline import HouseholdGenerator
        with patch.object(HouseholdGenerator, "__init__", lambda self, *a, **kw: None):
            gen = HouseholdGenerator.__new__(HouseholdGenerator)
            gen.state = "HI"
            gen.year = 2022
            gen.distributions = {}
            hints = GenerationHints(preferred_patterns=["single_parent"])
            hh = gen._select_pattern(pattern="single_adult", hints=hints)
            assert hh.pattern == "single_adult"


# =========================================================================
# 7. Student status assignment
# =========================================================================

class TestStudentStatus:

    def test_student_assigned_from_distribution(self) -> None:
        """Children aged 18-23 get is_full_time_student based on distribution."""
        import pandas as pd
        from generator.children import ChildGenerator
        enrollment_df = pd.DataFrame([
            {"age_bracket": "18-19", "enrolled_proportion": 1.0, "weight": 100},
            {"age_bracket": "20-21", "enrolled_proportion": 1.0, "weight": 100},
            {"age_bracket": "22-24", "enrolled_proportion": 1.0, "weight": 100},
        ])
        cg = ChildGenerator({"student_enrollment": enrollment_df})
        hh = _household(
            [_person(age=45)],
            pattern="single_parent",
        )
        hh.expected_children_range = (1, 3)
        children = cg.generate_children(hh)
        students = [c for c in children if 18 <= c.age <= 23]
        for s in students:
            assert s.is_full_time_student is True

    def test_young_child_never_student(self) -> None:
        """Children under 18 never get is_full_time_student."""
        from generator.children import ChildGenerator
        cg = ChildGenerator({})
        hh = _household(
            [_person(age=35)],
            pattern="single_parent",
        )
        hh.expected_children_range = (1, 3)
        children = cg.generate_children(hh)
        for c in children:
            if c.age < 18:
                assert c.is_full_time_student is False

    def test_force_full_time_student_hint(self) -> None:
        """force_full_time_student hint guarantees at least one student."""
        from generator.children import ChildGenerator
        import pandas as pd
        enrollment_df = pd.DataFrame([
            {"age_bracket": "18-19", "enrolled_proportion": 0.0, "weight": 100},
            {"age_bracket": "20-21", "enrolled_proportion": 0.0, "weight": 100},
            {"age_bracket": "22-24", "enrolled_proportion": 0.0, "weight": 100},
        ])
        cg = ChildGenerator({"student_enrollment": enrollment_df})
        parent = _person(age=50)
        child = _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                        age=20, is_dependent=True)
        hh = _household([parent, child], pattern="single_parent")
        hh.expected_children_range = (1, 3)
        hints = GenerationHints(force_full_time_student=True)
        children = cg.generate_children(hh, hints=hints)
        eligible = [c for c in children if 18 <= c.age <= 23]
        if eligible:
            assert any(c.is_full_time_student for c in eligible)

    def test_national_fallback_used(self) -> None:
        """When no distribution table, national rates are used (no crash)."""
        from generator.children import ChildGenerator
        cg = ChildGenerator({})
        prob = cg._enrollment_probability(19, None)
        assert 0.0 < prob <= 1.0
