"""Tests for generator.income — income assignment and document creation."""

import numpy as np
import pandas as pd
import pytest
import random

from generator.income import (
    IncomeGenerator,
    _compute_withholding,
    _estimate_federal_tax,
    _generate_ein,
    _get_state_tax_rate,
    _SS_TAX_RATE,
    _SS_WAGE_BASE,
    _MEDICARE_TAX_RATE,
)
from generator.models import (
    Household,
    Person,
    RelationshipType,
    W2,
    Form1099INT,
    Form1099NEC,
    SSA1099,
)


# ── Fixtures ───────────────────────────────────────────────────────────


def _make_person(
    age: int,
    employment_status: str = "employed",
    education: str = "bachelors",
    occupation_code: str = "management",
    relationship: RelationshipType = RelationshipType.HOUSEHOLDER,
) -> Person:
    return Person(
        person_id=f"p-{age}",
        age=age,
        sex="M",
        relationship=relationship,
        employment_status=employment_status,
        education=education,
        occupation_code=occupation_code,
        occupation_title="Management",
    )


def _make_household(state: str = "HI", *persons: Person) -> Household:
    members = list(persons) if persons else [_make_person(35)]
    return Household(
        household_id="hh-test",
        state=state,
        members=members,
    )


def _make_distributions() -> dict:
    """Build synthetic Part 2 distribution tables for income sampling."""
    occ_wages = pd.DataFrame([
        {"occupation_group": "management", "occupation_title": "Management",
         "median_wage": 60000, "p25_wage": 45000, "p75_wage": 85000,
         "mean_wage": 65000, "count": 100, "weight": 5000},
        {"occupation_group": "sales", "occupation_title": "Sales",
         "median_wage": 35000, "p25_wage": 25000, "p75_wage": 50000,
         "mean_wage": 38000, "count": 80, "weight": 4000},
    ])

    age_adj = pd.DataFrame([
        {"age_bracket": "18-24", "median_wage": 25000, "mean_wage": 28000,
         "adjustment_factor": 0.60, "count": 50, "weight": 2000},
        {"age_bracket": "25-34", "median_wage": 40000, "mean_wage": 43000,
         "adjustment_factor": 0.85, "count": 80, "weight": 4000},
        {"age_bracket": "35-44", "median_wage": 55000, "mean_wage": 58000,
         "adjustment_factor": 1.10, "count": 90, "weight": 5000},
        {"age_bracket": "45-54", "median_wage": 58000, "mean_wage": 60000,
         "adjustment_factor": 1.15, "count": 85, "weight": 4500},
        {"age_bracket": "55-64", "median_wage": 52000, "mean_wage": 55000,
         "adjustment_factor": 1.05, "count": 70, "weight": 3500},
        {"age_bracket": "65+", "median_wage": 42000, "mean_wage": 45000,
         "adjustment_factor": 0.80, "count": 30, "weight": 1500},
    ])

    social_security = pd.DataFrame([
        {"age_bracket": "65+", "income_bracket": "$10K-$15K", "weight": 300,
         "has_ss_proportion": 0.85},
        {"age_bracket": "65+", "income_bracket": "$15K-$20K", "weight": 400,
         "has_ss_proportion": 0.85},
        {"age_bracket": "65+", "income_bracket": "$20K-$25K", "weight": 200,
         "has_ss_proportion": 0.85},
    ])

    retirement = pd.DataFrame([
        {"age_bracket": "65+", "income_bracket": "$5K-$10K", "weight": 200,
         "has_ret_proportion": 0.40},
        {"age_bracket": "65+", "income_bracket": "$10K-$15K", "weight": 300,
         "has_ret_proportion": 0.40},
        {"age_bracket": "65+", "income_bracket": "$15K-$20K", "weight": 150,
         "has_ret_proportion": 0.40},
    ])

    interest_div = pd.DataFrame([
        {"age_bracket": "25-34", "income_bracket": "$1-$1K", "weight": 100,
         "has_inv_proportion": 0.15},
        {"age_bracket": "45-54", "income_bracket": "$1K-$5K", "weight": 200,
         "has_inv_proportion": 0.30},
        {"age_bracket": "65+", "income_bracket": "$1K-$5K", "weight": 300,
         "has_inv_proportion": 0.40},
    ])

    se_rates = pd.DataFrame([
        {"occupation_group": "management", "se_rate": 0.12,
         "se_count": 12, "total_count": 100, "weight": 5000},
        {"occupation_group": "sales", "se_rate": 0.08,
         "se_count": 8, "total_count": 100, "weight": 4000},
    ])

    return {
        "occupation_wages": occ_wages,
        "age_income_adjustments": age_adj,
        "social_security": social_security,
        "retirement_income": retirement,
        "interest_and_dividend_income": interest_div,
        "occupation_self_employment_rates": se_rates,
    }


@pytest.fixture
def gen() -> IncomeGenerator:
    return IncomeGenerator(_make_distributions())


@pytest.fixture
def gen_no_tables() -> IncomeGenerator:
    return IncomeGenerator({})


# ── Withholding math tests ─────────────────────────────────────────────


class TestWithholdingMath:
    def test_ss_tax_capped(self) -> None:
        wh = _compute_withholding(200_000, "HI")
        assert wh["social_security_wages"] == _SS_WAGE_BASE
        assert wh["social_security_tax"] == int(_SS_WAGE_BASE * _SS_TAX_RATE)

    def test_ss_tax_under_cap(self) -> None:
        wh = _compute_withholding(50_000, "HI")
        assert wh["social_security_wages"] == 50_000
        assert wh["social_security_tax"] == int(50_000 * _SS_TAX_RATE)

    def test_medicare_not_capped(self) -> None:
        wh = _compute_withholding(200_000, "HI")
        assert wh["medicare_wages"] == 200_000
        assert wh["medicare_tax"] == int(200_000 * _MEDICARE_TAX_RATE)

    def test_federal_tax_progressive(self) -> None:
        low = _estimate_federal_tax(20_000)
        mid = _estimate_federal_tax(60_000)
        high = _estimate_federal_tax(150_000)
        assert low < mid < high
        assert low > 0

    def test_no_income_tax_states(self) -> None:
        for state in ["FL", "TX", "WA", "NV"]:
            assert _get_state_tax_rate(state) == 0.0

    def test_hawaii_has_state_tax(self) -> None:
        wh = _compute_withholding(50_000, "HI")
        assert wh["state_tax"] > 0

    def test_florida_no_state_tax(self) -> None:
        wh = _compute_withholding(50_000, "FL")
        assert wh["state_tax"] == 0


class TestEINFormat:
    def test_format(self) -> None:
        ein = _generate_ein()
        assert len(ein) == 10
        assert ein[2] == "-"
        assert ein[:2].isdigit()
        assert ein[3:].isdigit()


# ── Overlay tests ──────────────────────────────────────────────────────


class TestOverlay:
    def test_employed_gets_wage_income(self, gen: IncomeGenerator) -> None:
        np.random.seed(42)
        random.seed(42)
        hh = _make_household("HI", _make_person(35))
        gen.overlay(hh)
        p = hh.members[0]
        assert p.wage_income > 0 or p.self_employment_income > 0

    def test_w2_created_for_wage_earner(self, gen: IncomeGenerator) -> None:
        np.random.seed(42)
        random.seed(42)
        # Run until we get a non-SE person
        for seed in range(50):
            np.random.seed(seed)
            random.seed(seed)
            p = _make_person(35)
            hh = _make_household("HI", p)
            gen.overlay(hh)
            if p.w2s:
                break
        if p.w2s:
            w2 = p.w2s[0]
            assert w2.wages > 0
            assert w2.employer is not None
            assert w2.employer.name != ""
            assert w2.employer.ein != ""
            assert w2.federal_tax_withheld > 0
            assert w2.social_security_tax > 0
            assert w2.medicare_tax > 0

    def test_unemployed_no_wage(self, gen: IncomeGenerator) -> None:
        p = _make_person(35, employment_status="unemployed")
        hh = _make_household("HI", p)
        gen.overlay(hh)
        assert p.wage_income == 0
        assert len(p.w2s) == 0

    def test_child_skipped(self, gen: IncomeGenerator) -> None:
        child = Person(person_id="child", age=10, relationship=RelationshipType.BIOLOGICAL_CHILD)
        hh = _make_household("HI", _make_person(35), child)
        gen.overlay(hh)
        assert child.wage_income == 0
        assert child.total_income() == 0

    def test_senior_gets_ss(self, gen: IncomeGenerator) -> None:
        np.random.seed(42)
        random.seed(42)
        ss_count = 0
        for seed in range(50):
            np.random.seed(seed)
            random.seed(seed)
            p = _make_person(70, employment_status="not_in_labor_force",
                             occupation_code=None)
            hh = _make_household("HI", p)
            gen.overlay(hh)
            if p.ssa_1099 is not None:
                ss_count += 1
        assert ss_count > 10  # Should be high for age 70

    def test_ssa_1099_fields(self, gen: IncomeGenerator) -> None:
        for seed in range(50):
            np.random.seed(seed)
            random.seed(seed)
            p = _make_person(70, employment_status="not_in_labor_force",
                             occupation_code=None)
            hh = _make_household("HI", p)
            gen.overlay(hh)
            if p.ssa_1099:
                assert p.ssa_1099.net_benefits > 0
                assert p.ssa_1099.net_benefits == p.social_security_income
                break

    def test_young_person_no_ss(self, gen: IncomeGenerator) -> None:
        p = _make_person(30)
        hh = _make_household("HI", p)
        gen.overlay(hh)
        assert p.social_security_income == 0
        assert p.ssa_1099 is None

    def test_household_total_income(self, gen: IncomeGenerator) -> None:
        np.random.seed(42)
        random.seed(42)
        p1 = _make_person(35)
        p2 = _make_person(33, relationship=RelationshipType.SPOUSE)
        hh = _make_household("HI", p1, p2)
        gen.overlay(hh)
        assert hh.total_household_income() >= 0


class TestSelfEmployment:
    def test_1099_nec_created(self, gen: IncomeGenerator) -> None:
        for seed in range(100):
            np.random.seed(seed)
            random.seed(seed)
            p = _make_person(40)
            hh = _make_household("HI", p)
            gen.overlay(hh)
            if p.form_1099_necs:
                assert p.self_employment_income > 0
                nec = p.form_1099_necs[0]
                assert nec.nonemployee_compensation > 0
                assert nec.payer_name != ""
                break


class TestInvestmentIncome:
    def test_investment_income_generated(self, gen: IncomeGenerator) -> None:
        found_int = False
        found_div = False
        for seed in range(300):
            np.random.seed(seed)
            random.seed(seed)
            p = _make_person(65, employment_status="not_in_labor_force",
                             occupation_code=None)
            hh = _make_household("HI", p)
            gen.overlay(hh)
            if p.form_1099_ints:
                found_int = True
            if p.form_1099_divs:
                found_div = True
            if found_int and found_div:
                break
        assert found_int or found_div

    def test_1099_int_fields(self, gen: IncomeGenerator) -> None:
        for seed in range(200):
            np.random.seed(seed)
            random.seed(seed)
            p = _make_person(65, employment_status="not_in_labor_force",
                             occupation_code=None)
            hh = _make_household("HI", p)
            gen.overlay(hh)
            if p.form_1099_ints:
                f = p.form_1099_ints[0]
                assert f.interest_income > 0
                assert f.payer_name != ""
                assert f.payer_tin != ""
                break


class TestRetirement:
    def test_1099_r_for_retiree(self, gen: IncomeGenerator) -> None:
        found = False
        for seed in range(100):
            np.random.seed(seed)
            random.seed(seed)
            p = _make_person(70, employment_status="not_in_labor_force",
                             occupation_code=None)
            hh = _make_household("HI", p)
            gen.overlay(hh)
            if p.form_1099_rs:
                found = True
                r = p.form_1099_rs[0]
                assert r.gross_distribution > 0
                assert r.taxable_amount > 0
                assert r.distribution_code == "7"  # Normal for age 70
                break
        assert found

    def test_young_no_retirement(self, gen: IncomeGenerator) -> None:
        p = _make_person(30)
        hh = _make_household("HI", p)
        gen.overlay(hh)
        assert p.retirement_income == 0
        assert len(p.form_1099_rs) == 0


class TestFallbacks:
    def test_no_tables_still_works(self, gen_no_tables: IncomeGenerator) -> None:
        np.random.seed(42)
        random.seed(42)
        p = _make_person(35)
        hh = _make_household("HI", p)
        gen_no_tables.overlay(hh)
        assert p.wage_income > 0 or p.self_employment_income > 0

    def test_fallback_wage_by_education(self, gen_no_tables: IncomeGenerator) -> None:
        np.random.seed(42)
        random.seed(42)
        wages = []
        for _ in range(20):
            p = _make_person(35, education="doctorate")
            hh = _make_household("HI", p)
            gen_no_tables.overlay(hh)
            if p.wage_income > 0:
                wages.append(p.wage_income)
        if wages:
            avg = sum(wages) / len(wages)
            assert avg > 30_000  # Doctorate should average well above minimum
