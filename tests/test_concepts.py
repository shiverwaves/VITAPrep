"""Tests for the seven concepts (D Phase 2 + education).

Each concept has:
- At least one positive fixture (concept matches).
- At least two negative fixtures (close-but-not-quite, absent).
- Docstrings explaining what each fixture demonstrates.

Final test: multi-concept scenario that fires several concepts at once.
"""

from datetime import date
from typing import Any, Optional

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
    Scenario,
)
from learn.concept_catalog import ConceptCatalog
from learn.concepts.base import Concept
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
from learn.concepts.education import FullTimeStudentDependentConcept


# =========================================================================
# Helpers
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
    sex: str = "F",
    first: str = "Jane",
    last: str = "Doe",
    wage_income: int = 50000,
    se_income: int = 0,
    ss_income: int = 0,
    months_in_home: int = 12,
    is_dependent: bool = False,
    can_be_claimed: bool = False,
    is_full_time_student: bool = False,
) -> Person:
    return Person(
        person_id=pid,
        relationship=rel,
        age=age, sex=sex, race="white",
        legal_first_name=first, legal_last_name=last,
        ssn=f"900-{pid[-2:]}-0000",
        dob=date(2022 - age, 1, 1),
        id_address=_addr(),
        wage_income=wage_income,
        self_employment_income=se_income,
        social_security_income=ss_income,
        months_in_home=months_in_home,
        is_dependent=is_dependent,
        can_be_claimed=can_be_claimed,
        is_full_time_student=is_full_time_student,
    )


def _household(
    members: list,
    pattern: str = "single_adult",
) -> Household:
    return Household(
        household_id="hh-test",
        state="HI",
        year=2022,
        pattern=pattern,
        address=_addr(),
        members=members,
    )


def _scenario(
    hh: Household,
    gt: Optional[dict] = None,
) -> Scenario:
    if gt is None:
        gt = {
            "schema_version": 1,
            "filing_status": "single",
            "deduction_type": "standard",
        }
    return Scenario(
        scenario_id="sc-test",
        mode="encounter",
        difficulty="easy",
        household=hh,
        document_paths={},
        created_at="2024-01-01T00:00:00",
        ground_truth=gt,
    )


# =========================================================================
# 1. qualifying_child_residency
# =========================================================================

class TestQualifyingChildResidency:
    concept = QualifyingChildResidencyConcept()

    def test_positive_partial_year(self) -> None:
        """Child at 7 months — partial-year residency triggers the concept."""
        hh = _household([
            _person(),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=7, is_dependent=True),
        ])
        assert self.concept.matches(_scenario(hh)) is True

    def test_negative_full_year(self) -> None:
        """Child at 12 months — no partial-year issue to drill."""
        hh = _household([
            _person(),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=12, is_dependent=True),
        ])
        assert self.concept.matches(_scenario(hh)) is False

    def test_negative_no_children(self) -> None:
        """No dependents at all — concept does not fire."""
        hh = _household([_person()])
        assert self.concept.matches(_scenario(hh)) is False

    def test_negative_zero_months(self) -> None:
        """Child at 0 months — not partial year (never lived there)."""
        hh = _household([
            _person(),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=0, is_dependent=True),
        ])
        assert self.concept.matches(_scenario(hh)) is False

    def test_boundary_six_months(self) -> None:
        """Child at exactly 6 months — partial year, concept fires."""
        hh = _household([
            _person(),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=6, is_dependent=True),
        ])
        assert self.concept.matches(_scenario(hh)) is True


# =========================================================================
# 2. hoh_qualifying_person
# =========================================================================

class TestHoHQualifyingPerson:
    concept = HoHQualifyingPersonConcept()

    def test_positive_single_parent(self) -> None:
        """Unmarried filer with qualifying child — HoH eligible."""
        hh = _household([
            _person(),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=12, is_dependent=True),
        ])
        assert self.concept.matches(_scenario(hh)) is True

    def test_negative_married(self) -> None:
        """Married filer with child — not HoH (married disqualifies)."""
        hh = _household([
            _person(),
            _person(pid="p-02", rel=RelationshipType.SPOUSE,
                    age=32, sex="M", first="John", wage_income=40000),
            _person(pid="p-03", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=12, is_dependent=True),
        ], pattern="married_with_children")
        assert self.concept.matches(_scenario(hh)) is False

    def test_negative_no_children(self) -> None:
        """Unmarried filer without qualifying person — not HoH."""
        hh = _household([_person()])
        assert self.concept.matches(_scenario(hh)) is False


# =========================================================================
# 3. refundable_credit_only_filer
# =========================================================================

class TestRefundableCreditOnlyFiler:
    concept = RefundableCreditOnlyFilerConcept()

    def test_positive_below_threshold_with_credits(self) -> None:
        """Low income with qualifying child — files for refundable credits."""
        hh = _household([
            _person(wage_income=5000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=12, is_dependent=True),
        ])
        sc = _scenario(hh, gt={
            "schema_version": 1,
            "filing_status": "single",
            "deduction_type": "standard",
        })
        assert self.concept.matches(sc) is True

    def test_negative_above_threshold(self) -> None:
        """Income above filing threshold — must file regardless of credits."""
        hh = _household([
            _person(wage_income=50000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=12, is_dependent=True),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False

    def test_negative_no_credits(self) -> None:
        """Below threshold but no qualifying children — no credits."""
        hh = _household([_person(wage_income=0)])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False

    def test_negative_zero_income_no_earned(self) -> None:
        """Zero earned income — EITC requires earned income > 0."""
        hh = _household([
            _person(wage_income=0),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=12, is_dependent=True),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False


# =========================================================================
# 4. self_employment_threshold
# =========================================================================

class TestSelfEmploymentThreshold:
    concept = SelfEmploymentThresholdConcept()

    def test_positive_500_se(self) -> None:
        """$500 SE income — above $400 threshold, Schedule SE required."""
        hh = _household([_person(wage_income=0, se_income=500)])
        assert self.concept.matches(_scenario(hh)) is True

    def test_positive_exactly_400(self) -> None:
        """$400 SE income — at threshold, Schedule SE required."""
        hh = _household([_person(wage_income=0, se_income=400)])
        assert self.concept.matches(_scenario(hh)) is True

    def test_negative_399(self) -> None:
        """$399 SE income — below threshold, no Schedule SE."""
        hh = _household([_person(wage_income=50000, se_income=399)])
        assert self.concept.matches(_scenario(hh)) is False

    def test_negative_zero_se(self) -> None:
        """No SE income at all."""
        hh = _household([_person(wage_income=50000, se_income=0)])
        assert self.concept.matches(_scenario(hh)) is False

    def test_positive_spouse_has_se(self) -> None:
        """Spouse has SE income — concept fires for any household member."""
        hh = _household([
            _person(wage_income=50000, se_income=0),
            _person(pid="p-02", rel=RelationshipType.SPOUSE,
                    age=32, sex="M", first="John",
                    wage_income=0, se_income=600),
        ])
        assert self.concept.matches(_scenario(hh)) is True


# =========================================================================
# 5. social_security_taxability
# =========================================================================

class TestSocialSecurityTaxability:
    concept = SocialSecurityTaxabilityConcept()

    def test_positive_ss_above_threshold(self) -> None:
        """SS income plus wages push provisional income above $25K threshold."""
        hh = _household([
            _person(wage_income=20000, ss_income=15000),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is True

    def test_negative_ss_only_below_threshold(self) -> None:
        """SS income only, below $25K — provisional income = half SS."""
        hh = _household([
            _person(wage_income=0, ss_income=10000),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False

    def test_negative_no_ss(self) -> None:
        """No SS income — concept cannot fire."""
        hh = _household([_person(wage_income=50000, ss_income=0)])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False

    def test_positive_mfj_above_threshold(self) -> None:
        """MFJ with SS above $32K threshold."""
        hh = _household([
            _person(wage_income=25000, ss_income=20000),
            _person(pid="p-02", rel=RelationshipType.SPOUSE,
                    age=67, sex="M", first="Bob",
                    wage_income=0, ss_income=0),
        ])
        sc = _scenario(hh, gt={
            "schema_version": 1,
            "filing_status": "married_filing_jointly",
            "deduction_type": "standard",
        })
        assert self.concept.matches(sc) is True


# =========================================================================
# 6. standard_vs_itemized
# =========================================================================

class TestStandardVsItemized:
    concept = StandardVsItemizedConcept()

    def test_positive_itemized(self) -> None:
        """Ground truth says itemized — concept fires."""
        sc = _scenario(
            _household([_person()]),
            gt={
                "schema_version": 1,
                "filing_status": "single",
                "deduction_type": "itemized",
            },
        )
        assert self.concept.matches(sc) is True

    def test_negative_standard(self) -> None:
        """Ground truth says standard — concept does not fire."""
        sc = _scenario(
            _household([_person()]),
            gt={
                "schema_version": 1,
                "filing_status": "single",
                "deduction_type": "standard",
            },
        )
        assert self.concept.matches(sc) is False

    def test_negative_no_ground_truth(self) -> None:
        """No ground truth — concept cannot evaluate."""
        sc = _scenario(_household([_person()]), gt=None)
        sc.ground_truth = None
        assert self.concept.matches(sc) is False


# =========================================================================
# 7. full_time_student_dependent
# =========================================================================

class TestFullTimeStudentDependent:
    concept = FullTimeStudentDependentConcept()

    def test_positive_student_age_20(self) -> None:
        """Dependent age 20, is_full_time_student=True — concept fires."""
        hh = _household([
            _person(wage_income=50000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=20, first="Alex", wage_income=0,
                    is_dependent=True, is_full_time_student=True),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is True

    def test_negative_student_age_17(self) -> None:
        """Dependent age 17, is_full_time_student=True — concept does NOT fire
        (under 19, doesn't need the student exception)."""
        hh = _household([
            _person(wage_income=50000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=17, first="Alex", wage_income=0,
                    is_dependent=True, is_full_time_student=True),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False

    def test_negative_not_student(self) -> None:
        """Dependent age 20, NOT full-time student — concept does NOT fire."""
        hh = _household([
            _person(wage_income=50000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=20, first="Alex", wage_income=0,
                    is_dependent=True, is_full_time_student=False),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False

    def test_positive_age_23(self) -> None:
        """Dependent age 23, full-time student — boundary case, fires."""
        hh = _household([
            _person(wage_income=50000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=23, first="Alex", wage_income=0,
                    is_dependent=True, is_full_time_student=True),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is True

    def test_negative_age_24(self) -> None:
        """Dependent age 24, full-time student — too old, concept does NOT fire."""
        hh = _household([
            _person(wage_income=50000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=24, first="Alex", wage_income=0,
                    is_dependent=True, is_full_time_student=True),
        ])
        sc = _scenario(hh)
        assert self.concept.matches(sc) is False

    def test_hints(self) -> None:
        hints = self.concept.generation_hints()
        assert hints.force_full_time_student is True
        assert "single_parent" in hints.preferred_patterns


# =========================================================================
# 8. Multi-concept scenario
# =========================================================================

class TestMultiConceptScenario:

    def test_multi_concept_fires_correctly(self) -> None:
        """Single parent with borderline child, 1099-NEC, and itemized deduction.

        Should fire: qualifying_child_residency (child at 8 months),
        hoh_qualifying_person (unmarried with qualifying child),
        self_employment_threshold ($600 SE income),
        standard_vs_itemized (itemized deduction).
        Should NOT fire: social_security_taxability (no SS income),
        refundable_credit_only_filer (income above threshold).
        """
        hh = _household([
            _person(wage_income=40000, se_income=600),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=8, is_dependent=True),
        ])
        sc = _scenario(hh, gt={
            "schema_version": 1,
            "filing_status": "head_of_household",
            "deduction_type": "itemized",
        })

        catalog = ConceptCatalog()
        catalog.register(QualifyingChildResidencyConcept())
        catalog.register(HoHQualifyingPersonConcept())
        catalog.register(RefundableCreditOnlyFilerConcept())
        catalog.register(SelfEmploymentThresholdConcept())
        catalog.register(SocialSecurityTaxabilityConcept())
        catalog.register(StandardVsItemizedConcept())
        catalog.register(FullTimeStudentDependentConcept())

        tags = catalog.run_all(sc)

        assert "qualifying_child_residency" in tags
        assert "hoh_qualifying_person" in tags
        assert "self_employment_threshold" in tags
        assert "standard_vs_itemized" in tags
        assert "social_security_taxability" not in tags
        assert "refundable_credit_only_filer" not in tags

    def test_catalog_has_seven_concepts(self) -> None:
        """Registry holds all seven concepts."""
        catalog = ConceptCatalog()
        catalog.register(QualifyingChildResidencyConcept())
        catalog.register(HoHQualifyingPersonConcept())
        catalog.register(RefundableCreditOnlyFilerConcept())
        catalog.register(SelfEmploymentThresholdConcept())
        catalog.register(SocialSecurityTaxabilityConcept())
        catalog.register(StandardVsItemizedConcept())
        catalog.register(FullTimeStudentDependentConcept())
        assert len(catalog.concepts) == 7

    def test_empty_scenario_no_tags(self) -> None:
        """Simple wage earner with no special situations — no concepts fire."""
        hh = _household([_person(wage_income=50000)])
        sc = _scenario(hh)

        catalog = ConceptCatalog()
        catalog.register(QualifyingChildResidencyConcept())
        catalog.register(HoHQualifyingPersonConcept())
        catalog.register(RefundableCreditOnlyFilerConcept())
        catalog.register(SelfEmploymentThresholdConcept())
        catalog.register(SocialSecurityTaxabilityConcept())
        catalog.register(StandardVsItemizedConcept())
        catalog.register(FullTimeStudentDependentConcept())

        tags = catalog.run_all(sc)
        assert tags == set()


# =========================================================================
# 8. Concept evaluation constraint
# =========================================================================

class TestConceptConstraint:

    def test_concepts_work_with_lifecycle_fields_none(self) -> None:
        """All seven concepts run without error when interview_notes and
        concept_tags are None (as they are at Stage 5)."""
        hh = _household([
            _person(wage_income=5000, se_income=500, ss_income=30000),
            _person(pid="p-02", rel=RelationshipType.BIOLOGICAL_CHILD,
                    age=10, first="Tommy", wage_income=0,
                    months_in_home=8, is_dependent=True),
        ])
        sc = _scenario(hh)
        assert sc.interview_notes is None
        assert sc.concept_tags is None

        catalog = ConceptCatalog()
        catalog.register(QualifyingChildResidencyConcept())
        catalog.register(HoHQualifyingPersonConcept())
        catalog.register(RefundableCreditOnlyFilerConcept())
        catalog.register(SelfEmploymentThresholdConcept())
        catalog.register(SocialSecurityTaxabilityConcept())
        catalog.register(StandardVsItemizedConcept())
        catalog.register(FullTimeStudentDependentConcept())

        tags = catalog.run_all(sc)
        assert isinstance(tags, set)
