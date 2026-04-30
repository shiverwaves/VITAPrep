"""Tests for generator.expenses — Part 3 expense generation.

Covers:
- Homeownership determination (with and without distribution data)
- Property tax sampling
- Mortgage interest derivation from MRGP
- State income tax (progressive brackets)
- Medical expenses (probabilistic with AGI floor)
- Charitable contributions
- Above-the-line deductions (student loan, educator, IRA)
- Credit-related expenses (child care, education)
- Standard vs itemized deduction determination
- Pipeline integration via generate_part3
"""

from datetime import date

import numpy as np
import pandas as pd
import pytest

from generator.expenses import (
    EDUCATOR_EXPENSE_LIMIT,
    HAWAII_TAX_BRACKETS_MFJ,
    HAWAII_TAX_BRACKETS_SINGLE,
    IRA_CONTRIBUTION_LIMIT,
    IRA_CONTRIBUTION_LIMIT_50_PLUS,
    SALT_CAP,
    STANDARD_DEDUCTION,
    STUDENT_LOAN_INTEREST_LIMIT,
    ExpenseGenerator,
)
from generator.models import (
    Address,
    EmploymentStatus,
    Household,
    Person,
    RelationshipType,
)


# =========================================================================
# Fixtures
# =========================================================================


def _make_person(**kwargs) -> Person:
    defaults = dict(
        person_id="p-1",
        relationship=RelationshipType.HOUSEHOLDER,
        age=40,
        sex="M",
        race="white",
        legal_first_name="Test",
        legal_last_name="User",
        ssn="900-11-2222",
        dob=date(1982, 5, 15),
        employment_status=EmploymentStatus.EMPLOYED.value,
        education="bachelors",
        occupation_code="1100",
        wage_income=60000,
    )
    defaults.update(kwargs)
    return Person(**defaults)


def _make_household(
    members=None,
    pattern="single_adult",
    income_override=None,
) -> Household:
    if members is None:
        members = [_make_person()]
    hh = Household(
        household_id="hh-test",
        state="HI",
        year=2022,
        pattern=pattern,
        members=members,
        address=Address(
            street="100 Main St",
            city="Honolulu",
            state="HI",
            zip_code="96815",
        ),
    )
    return hh


def _empty_distributions() -> dict:
    return {}


def _mock_homeownership_dist() -> pd.DataFrame:
    return pd.DataFrame([
        {"age_bracket": "35-44", "income_bracket": "$50-75K",
         "tenure": "owner_with_mortgage", "weighted_count": 700, "proportion": 0.70},
        {"age_bracket": "35-44", "income_bracket": "$50-75K",
         "tenure": "renter", "weighted_count": 300, "proportion": 0.30},
    ])


def _mock_property_tax_dist() -> pd.DataFrame:
    return pd.DataFrame([
        {"income_bracket": "$50-75K", "mean_amount": 3000,
         "median_amount": 2800, "p25": 2000, "p75": 4000,
         "count": 100, "weight": 5000},
    ])


def _mock_mortgage_costs_dist() -> pd.DataFrame:
    return pd.DataFrame([
        {"income_bracket": "$50-75K", "age_bracket": "35-44",
         "mean_monthly": 2000, "median_monthly": 1800,
         "p25": 1500, "p75": 2500, "count": 80, "weight": 4000},
    ])


# =========================================================================
# Homeownership
# =========================================================================


class TestHomeownership:
    def test_fallback_no_distributions(self) -> None:
        np.random.seed(42)
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household()
        gen._assign_housing_expenses(hh)
        # Should complete without error; result depends on random draw

    def test_with_distribution_data(self) -> None:
        np.random.seed(1)
        dists = {"homeownership_rates": _mock_homeownership_dist()}
        gen = ExpenseGenerator(dists)
        results = []
        for _ in range(100):
            hh = _make_household()
            is_owner = gen._determine_homeownership(hh)
            results.append(is_owner)
        owner_rate = sum(results) / len(results)
        assert 0.4 < owner_rate < 0.95

    def test_renter_no_property_tax(self) -> None:
        np.random.seed(0)
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household(members=[_make_person(age=22, wage_income=15000)])
        # Force renter
        hh.is_homeowner = False
        gen._assign_housing_expenses(hh)
        if not hh.is_homeowner:
            assert hh.property_taxes == 0
            assert hh.mortgage_interest == 0


# =========================================================================
# Property taxes
# =========================================================================


class TestPropertyTaxes:
    def test_with_distribution(self) -> None:
        np.random.seed(42)
        dists = {"property_taxes": _mock_property_tax_dist()}
        gen = ExpenseGenerator(dists)
        hh = _make_household()
        amount = gen._sample_property_taxes(hh)
        assert amount >= 500

    def test_fallback(self) -> None:
        np.random.seed(42)
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household()
        amount = gen._sample_property_taxes(hh)
        assert amount > 0


# =========================================================================
# Mortgage interest
# =========================================================================


class TestMortgageInterest:
    def test_with_distribution(self) -> None:
        np.random.seed(42)
        dists = {"mortgage_costs": _mock_mortgage_costs_dist()}
        gen = ExpenseGenerator(dists)
        hh = _make_household()
        amount = gen._sample_mortgage_interest(hh)
        assert amount >= 0

    def test_seniors_sometimes_no_mortgage(self) -> None:
        np.random.seed(42)
        gen = ExpenseGenerator(_empty_distributions())
        results = []
        for i in range(100):
            np.random.seed(i)
            hh = _make_household(
                members=[_make_person(age=70, wage_income=40000)],
            )
            amount = gen._sample_mortgage_interest(hh)
            results.append(amount)
        assert any(a == 0 for a in results)


# =========================================================================
# State income tax
# =========================================================================


class TestStateIncomeTax:
    def test_progressive_brackets(self) -> None:
        tax = ExpenseGenerator._progressive_tax(50000, HAWAII_TAX_BRACKETS_SINGLE)
        assert tax > 0

    def test_zero_income(self) -> None:
        tax = ExpenseGenerator._progressive_tax(0, HAWAII_TAX_BRACKETS_SINGLE)
        assert tax == 0

    def test_married_uses_mfj_brackets(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household(
            members=[
                _make_person(relationship=RelationshipType.HOUSEHOLDER),
                _make_person(
                    person_id="p-2",
                    relationship=RelationshipType.SPOUSE,
                    wage_income=40000,
                ),
            ],
            pattern="married_couple_no_children",
        )
        gen._assign_state_income_tax(hh)
        assert hh.state_income_tax > 0

    def test_higher_income_higher_tax(self) -> None:
        low = ExpenseGenerator._progressive_tax(30000, HAWAII_TAX_BRACKETS_SINGLE)
        high = ExpenseGenerator._progressive_tax(100000, HAWAII_TAX_BRACKETS_SINGLE)
        assert high > low


# =========================================================================
# Medical expenses
# =========================================================================


class TestMedicalExpenses:
    def test_sometimes_zero(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        results = []
        for i in range(100):
            np.random.seed(i)
            hh = _make_household()
            gen._assign_medical_expenses(hh)
            results.append(hh.medical_expenses)
        assert any(m == 0 for m in results)
        assert any(m > 0 for m in results)

    def test_elderly_more_likely(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        young_hits = 0
        old_hits = 0
        for i in range(200):
            np.random.seed(i)
            hh_young = _make_household(members=[_make_person(age=30)])
            gen._assign_medical_expenses(hh_young)
            if hh_young.medical_expenses > 0:
                young_hits += 1

            np.random.seed(i)
            hh_old = _make_household(members=[_make_person(age=70)])
            gen._assign_medical_expenses(hh_old)
            if hh_old.medical_expenses > 0:
                old_hits += 1

        assert old_hits > young_hits


# =========================================================================
# Charitable contributions
# =========================================================================


class TestCharitable:
    def test_sometimes_zero(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        results = []
        for i in range(100):
            np.random.seed(i)
            hh = _make_household()
            gen._assign_charitable_contributions(hh)
            results.append(hh.charitable_contributions)
        assert any(c == 0 for c in results)
        assert any(c > 0 for c in results)

    def test_capped_at_60_pct_agi(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        for i in range(100):
            np.random.seed(i)
            hh = _make_household()
            gen._assign_charitable_contributions(hh)
            income = hh.total_household_income()
            if income > 0:
                assert hh.charitable_contributions <= int(income * 0.60)


# =========================================================================
# Above-the-line deductions
# =========================================================================


class TestAboveLine:
    def test_student_loan_requires_college(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        p = _make_person(age=30, education="high_school")
        assert gen._student_loan_interest(p) == 0

    def test_student_loan_capped(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        for i in range(50):
            np.random.seed(i)
            p = _make_person(age=28, education="masters")
            amount = gen._student_loan_interest(p)
            assert amount <= STUDENT_LOAN_INTEREST_LIMIT

    def test_educator_requires_soc_25(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        p = _make_person(occupation_code="1100")
        assert gen._educator_expenses(p) == 0

    def test_educator_for_teacher(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        results = []
        for i in range(50):
            np.random.seed(i)
            p = _make_person(occupation_code="2500")
            results.append(gen._educator_expenses(p))
        assert any(e > 0 for e in results)
        assert all(e <= EDUCATOR_EXPENSE_LIMIT for e in results)

    def test_ira_requires_employment(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        p = _make_person(employment_status=EmploymentStatus.UNEMPLOYED.value)
        assert gen._ira_contributions(p) == 0

    def test_ira_50_plus_higher_limit(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        for i in range(50):
            np.random.seed(i)
            p = _make_person(age=55, wage_income=80000)
            amount = gen._ira_contributions(p)
            assert amount <= IRA_CONTRIBUTION_LIMIT_50_PLUS

    def test_ira_under_50_limit(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        for i in range(50):
            np.random.seed(i)
            p = _make_person(age=35, wage_income=80000)
            amount = gen._ira_contributions(p)
            assert amount <= IRA_CONTRIBUTION_LIMIT


# =========================================================================
# Credit-related expenses
# =========================================================================


class TestCreditExpenses:
    def test_child_care_requires_young_children(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household()
        assert gen._child_care_expenses(hh) == 0

    def test_child_care_requires_working_parent(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household(
            members=[
                _make_person(employment_status=EmploymentStatus.UNEMPLOYED.value),
                _make_person(
                    person_id="child",
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    age=5, sex="F",
                    employment_status="",
                ),
            ],
            pattern="single_parent",
        )
        assert gen._child_care_expenses(hh) == 0

    def test_child_care_with_eligible_family(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        results = []
        for i in range(50):
            np.random.seed(i)
            hh = _make_household(
                members=[
                    _make_person(),
                    _make_person(
                        person_id="child",
                        relationship=RelationshipType.BIOLOGICAL_CHILD,
                        age=5, sex="F",
                        employment_status="",
                    ),
                ],
                pattern="single_parent",
            )
            results.append(gen._child_care_expenses(hh))
        assert any(c > 0 for c in results)

    def test_education_no_students(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household()
        hh.members[0].age = 40
        assert gen._education_expenses(hh) == 0

    def test_education_with_college_student(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        results = []
        for i in range(50):
            np.random.seed(i)
            hh = _make_household(
                members=[
                    _make_person(),
                    _make_person(
                        person_id="student",
                        relationship=RelationshipType.BIOLOGICAL_CHILD,
                        age=20, sex="F",
                        education="some_college",
                        employment_status="",
                    ),
                ],
            )
            results.append(gen._education_expenses(hh))
        assert any(e > 0 for e in results)


# =========================================================================
# Standard vs Itemized
# =========================================================================


class TestStandardVsItemized:
    def test_low_income_uses_standard(self) -> None:
        np.random.seed(42)
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household(
            members=[_make_person(wage_income=30000)],
        )
        gen.overlay(hh)
        assert hh.uses_standard_deduction is True

    def test_salt_cap_applied(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household()
        hh.state_income_tax = 8000
        hh.property_taxes = 5000
        hh.mortgage_interest = 10000
        hh.charitable_contributions = 2000
        hh.medical_expenses = 0
        gen._calculate_totals(hh)
        salt_portion = min(8000 + 5000, SALT_CAP)
        expected = salt_portion + 10000 + 2000
        assert hh.total_itemized_deductions == expected

    def test_itemized_when_exceeds_standard(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household()
        hh.state_income_tax = 8000
        hh.property_taxes = 5000
        hh.mortgage_interest = 15000
        hh.charitable_contributions = 5000
        hh.medical_expenses = 0
        gen._calculate_totals(hh)
        standard = STANDARD_DEDUCTION["single"]
        if hh.total_itemized_deductions > standard:
            assert hh.uses_standard_deduction is False

    def test_above_line_totals(self) -> None:
        gen = ExpenseGenerator(_empty_distributions())
        p = _make_person()
        p.student_loan_interest = 1500
        p.educator_expenses = 250
        p.ira_contributions = 3000
        hh = _make_household(members=[p])
        gen._calculate_totals(hh)
        assert hh.total_above_line_deductions == 4750


# =========================================================================
# Full overlay integration
# =========================================================================


class TestFullOverlay:
    def test_overlay_populates_fields(self) -> None:
        np.random.seed(42)
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household(
            members=[_make_person(wage_income=80000)],
        )
        gen.overlay(hh)
        assert hh.state_income_tax > 0
        assert isinstance(hh.is_homeowner, bool)
        assert isinstance(hh.uses_standard_deduction, bool)
        assert hh.total_itemized_deductions >= 0
        assert hh.total_above_line_deductions >= 0

    def test_overlay_with_distributions(self) -> None:
        np.random.seed(42)
        dists = {
            "homeownership_rates": _mock_homeownership_dist(),
            "property_taxes": _mock_property_tax_dist(),
            "mortgage_costs": _mock_mortgage_costs_dist(),
        }
        gen = ExpenseGenerator(dists)
        hh = _make_household(
            members=[_make_person(wage_income=60000)],
        )
        gen.overlay(hh)
        assert hh.state_income_tax > 0

    def test_married_couple_with_children(self) -> None:
        np.random.seed(42)
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household(
            members=[
                _make_person(wage_income=70000),
                _make_person(
                    person_id="p-2",
                    relationship=RelationshipType.SPOUSE,
                    sex="F",
                    wage_income=45000,
                ),
                _make_person(
                    person_id="child-1",
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    age=5, sex="F",
                    employment_status="",
                    education="",
                    wage_income=0,
                ),
            ],
            pattern="married_couple_with_children",
        )
        gen.overlay(hh)
        assert hh.state_income_tax > 0
        assert hh.total_itemized_deductions >= 0

    def test_zero_income_household(self) -> None:
        np.random.seed(42)
        gen = ExpenseGenerator(_empty_distributions())
        hh = _make_household(
            members=[_make_person(
                wage_income=0,
                employment_status=EmploymentStatus.NOT_IN_LABOR_FORCE.value,
            )],
        )
        gen.overlay(hh)
        assert hh.state_income_tax == 0
        assert hh.uses_standard_deduction is True


# =========================================================================
# Bracket helpers
# =========================================================================


class TestBracketHelpers:
    def test_age_brackets(self) -> None:
        assert ExpenseGenerator._age_to_bracket(20) == "<25"
        assert ExpenseGenerator._age_to_bracket(30) == "25-34"
        assert ExpenseGenerator._age_to_bracket(65) == "65+"

    def test_income_brackets(self) -> None:
        assert ExpenseGenerator._income_to_bracket(10000) == "<$25K"
        assert ExpenseGenerator._income_to_bracket(60000) == "$50-75K"
        assert ExpenseGenerator._income_to_bracket(200000) == "$150K+"
