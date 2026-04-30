"""Tests for extraction.extract_part2 — Part 2 distribution extraction.

Uses synthetic PUMS-like DataFrames to verify each extraction function
produces the expected table schema and reasonable results.
"""

import numpy as np
import pandas as pd
import pytest

from extraction.extract_part2 import (
    _age_to_bracket,
    _amount_to_benefit_bracket,
    _amount_to_small_bracket,
    _amount_to_wage_bracket,
    _occp_to_group,
    extract_age_income_adjustments,
    extract_disability_by_age,
    extract_education_by_age,
    extract_education_occupation_probabilities,
    extract_employment_by_age,
    extract_interest_and_dividend_income,
    extract_occupation_self_employment_rates,
    extract_occupation_wages,
    extract_other_income_by_employment_status,
    extract_public_assistance_income,
    extract_retirement_income,
    extract_social_security,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def persons_df() -> pd.DataFrame:
    """Synthetic person records with Part 2 PUMS columns."""
    np.random.seed(42)
    n = 200
    ages = np.random.choice(range(18, 80), size=n)
    return pd.DataFrame({
        "SERIALNO": [f"HH{i // 3}" for i in range(n)],
        "AGEP": ages,
        "PWGTP": np.random.randint(10, 500, size=n),
        "ESR": np.random.choice([1, 2, 3, 6], size=n, p=[0.5, 0.1, 0.1, 0.3]),
        "SCHL": np.random.choice(range(16, 25), size=n),
        "DIS": np.random.choice([1, 2], size=n, p=[0.15, 0.85]),
        "OCCP": np.random.choice([110, 1005, 2200, 4700, 5100, 7700, 9100], size=n),
        "COW": np.random.choice([1, 2, 3, 6, 7], size=n, p=[0.5, 0.15, 0.1, 0.15, 0.1]),
        "WAGP": np.where(
            np.random.choice([1, 2, 3, 6], size=n, p=[0.5, 0.1, 0.1, 0.3]) <= 2,
            np.random.randint(15000, 120000, size=n),
            0,
        ),
        "SSP": np.where(ages >= 62, np.random.randint(5000, 30000, size=n), 0),
        "SSIP": np.zeros(n, dtype=int),
        "RETP": np.where(ages >= 55, np.random.randint(0, 40000, size=n), 0),
        "INTP": np.where(
            np.random.random(n) < 0.3,
            np.random.randint(100, 20000, size=n),
            0,
        ),
        "OIP": np.where(
            np.random.random(n) < 0.1,
            np.random.randint(500, 15000, size=n),
            0,
        ),
        "PAP": np.where(
            np.random.random(n) < 0.05,
            np.random.randint(1000, 8000, size=n),
            0,
        ),
    })


# ── Helper tests ───────────────────────────────────────────────────────


class TestHelpers:
    def test_age_to_bracket(self) -> None:
        assert _age_to_bracket(5) == "Under 18"
        assert _age_to_bracket(18) == "18-24"
        assert _age_to_bracket(30) == "25-34"
        assert _age_to_bracket(65) == "65+"
        assert _age_to_bracket(99) == "65+"

    def test_wage_brackets(self) -> None:
        assert _amount_to_wage_bracket(5000) == "Under $10K"
        assert _amount_to_wage_bracket(25000) == "$20K-$30K"
        assert _amount_to_wage_bracket(200000) == "$150K+"

    def test_benefit_brackets(self) -> None:
        assert _amount_to_benefit_bracket(3000) == "$1-$5K"
        assert _amount_to_benefit_bracket(15000) == "$15K-$20K"
        assert _amount_to_benefit_bracket(50000) == "$30K+"

    def test_small_brackets(self) -> None:
        assert _amount_to_small_bracket(500) == "$1-$1K"
        assert _amount_to_small_bracket(3000) == "$1K-$5K"
        assert _amount_to_small_bracket(100000) == "$50K+"

    def test_occp_to_group(self) -> None:
        assert _occp_to_group(110) == "management"
        assert _occp_to_group(1005) == "computer_math"
        assert _occp_to_group(4700) == "sales"
        assert _occp_to_group(9999) is None


# ── Extraction function tests ─────────────────────────────────────────


class TestEmploymentByAge:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_employment_by_age(persons_df)
        assert not result.empty
        assert set(result.columns) == {"age_bracket", "employment_status", "weight", "proportion"}
        assert set(result["employment_status"].unique()) <= {"employed", "unemployed", "not_in_labor_force"}

    def test_proportions_sum_to_one(self, persons_df: pd.DataFrame) -> None:
        result = extract_employment_by_age(persons_df)
        for bracket in result["age_bracket"].unique():
            total = result[result["age_bracket"] == bracket]["proportion"].sum()
            assert abs(total - 1.0) < 0.01

    def test_empty(self) -> None:
        empty = pd.DataFrame(columns=["AGEP", "PWGTP", "ESR"])
        result = extract_employment_by_age(empty)
        assert result.empty


class TestEducationByAge:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_education_by_age(persons_df)
        assert not result.empty
        assert "education_level" in result.columns

    def test_valid_levels(self, persons_df: pd.DataFrame) -> None:
        result = extract_education_by_age(persons_df)
        valid = {
            "less_than_hs", "high_school", "some_college", "associates",
            "bachelors", "masters", "professional", "doctorate",
        }
        assert set(result["education_level"].unique()) <= valid


class TestDisabilityByAge:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_disability_by_age(persons_df)
        assert not result.empty
        assert set(result["has_disability"].unique()) <= {0, 1}


class TestSocialSecurity:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_social_security(persons_df)
        assert not result.empty
        assert "income_bracket" in result.columns
        assert "has_ss_proportion" in result.columns

    def test_only_recipients(self, persons_df: pd.DataFrame) -> None:
        result = extract_social_security(persons_df)
        assert (result["weight"] > 0).all()


class TestRetirementIncome:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_retirement_income(persons_df)
        assert not result.empty
        assert "has_ret_proportion" in result.columns


class TestInterestDividend:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_interest_and_dividend_income(persons_df)
        assert not result.empty
        assert "has_inv_proportion" in result.columns


class TestOtherIncome:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_other_income_by_employment_status(persons_df)
        assert not result.empty
        assert "employment_status" in result.columns


class TestPublicAssistance:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_public_assistance_income(persons_df)
        assert "has_pa_proportion" in result.columns


class TestOccupationWages:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_occupation_wages(persons_df)
        assert not result.empty
        expected_cols = {
            "occupation_group", "occupation_title",
            "median_wage", "p25_wage", "p75_wage", "mean_wage",
            "count", "weight",
        }
        assert set(result.columns) == expected_cols

    def test_wage_ordering(self, persons_df: pd.DataFrame) -> None:
        result = extract_occupation_wages(persons_df)
        for _, row in result.iterrows():
            assert row["p25_wage"] <= row["median_wage"] <= row["p75_wage"]


class TestEducationOccupation:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_education_occupation_probabilities(persons_df)
        assert not result.empty
        assert "proportion" in result.columns

    def test_proportions(self, persons_df: pd.DataFrame) -> None:
        result = extract_education_occupation_probabilities(persons_df)
        for level in result["education_level"].unique():
            total = result[result["education_level"] == level]["proportion"].sum()
            assert abs(total - 1.0) < 0.01


class TestAgeIncomeAdjustments:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_age_income_adjustments(persons_df)
        assert not result.empty
        assert "adjustment_factor" in result.columns

    def test_adjustment_reasonable(self, persons_df: pd.DataFrame) -> None:
        result = extract_age_income_adjustments(persons_df)
        for _, row in result.iterrows():
            assert 0.1 < row["adjustment_factor"] < 5.0


class TestSelfEmploymentRates:
    def test_basic(self, persons_df: pd.DataFrame) -> None:
        result = extract_occupation_self_employment_rates(persons_df)
        assert not result.empty
        assert "se_rate" in result.columns

    def test_rate_range(self, persons_df: pd.DataFrame) -> None:
        result = extract_occupation_self_employment_rates(persons_df)
        assert (result["se_rate"] >= 0).all()
        assert (result["se_rate"] <= 1).all()
