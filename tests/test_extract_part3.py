"""Tests for extraction.extract_part3 — Part 3 distribution extraction.

Uses synthetic PUMS-like DataFrames to verify each extraction function
produces the expected table schema and reasonable results.
"""

import numpy as np
import pandas as pd
import pytest

from extraction.extract_part3 import (
    _age_to_bracket,
    _income_to_bracket,
    extract_homeownership_rates,
    extract_mortgage_costs,
    extract_property_taxes,
)


# ── Fixtures ───────────────────────────────────────────────────────────


@pytest.fixture
def households_df() -> pd.DataFrame:
    """Synthetic household records with Part 3 PUMS columns."""
    np.random.seed(42)
    n = 200
    tenures = np.random.choice([1, 2, 3, 4], size=n, p=[0.35, 0.15, 0.45, 0.05])

    taxamt = np.where(
        np.isin(tenures, [1, 2]),
        np.random.randint(500, 12000, size=n),
        0,
    )

    mrgp = np.where(
        tenures == 1,
        np.random.randint(800, 4000, size=n),
        0,
    )

    smocp = np.where(
        np.isin(tenures, [1, 2]),
        np.random.randint(1000, 5000, size=n),
        0,
    )

    return pd.DataFrame({
        "SERIALNO": [f"HH{i}" for i in range(n)],
        "WGTP": np.random.randint(10, 500, size=n),
        "NP": np.random.randint(1, 6, size=n),
        "TYPE": np.ones(n, dtype=int),
        "TEN": tenures,
        "TAXAMT": taxamt,
        "HINCP": np.random.randint(10000, 200000, size=n),
        "MRGP": mrgp,
        "SMOCP": smocp,
    })


@pytest.fixture
def persons_df(households_df: pd.DataFrame) -> pd.DataFrame:
    """Synthetic person records matching household serial numbers."""
    np.random.seed(42)
    records = []
    for _, hh in households_df.iterrows():
        records.append({
            "SERIALNO": hh["SERIALNO"],
            "AGEP": np.random.randint(25, 80),
            "PWGTP": np.random.randint(10, 500),
            "RELSHIPP": 20,
            "SEX": np.random.choice([1, 2]),
        })
    return pd.DataFrame(records)


# ── Helper tests ───────────────────────────────────────────────────────


class TestHelpers:
    def test_age_to_bracket(self) -> None:
        assert _age_to_bracket(20) == "<25"
        assert _age_to_bracket(25) == "25-34"
        assert _age_to_bracket(34) == "25-34"
        assert _age_to_bracket(35) == "35-44"
        assert _age_to_bracket(55) == "55-64"
        assert _age_to_bracket(65) == "65+"
        assert _age_to_bracket(90) == "65+"

    def test_income_to_bracket(self) -> None:
        assert _income_to_bracket(10000) == "<$25K"
        assert _income_to_bracket(25000) == "$25-50K"
        assert _income_to_bracket(49999) == "$25-50K"
        assert _income_to_bracket(75000) == "$75-100K"
        assert _income_to_bracket(150000) == "$150K+"
        assert _income_to_bracket(500000) == "$150K+"


# ── Homeownership rates ───────────────────────────────────────────────


class TestHomeownershipRates:
    def test_basic(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_homeownership_rates(households_df, persons_df)
        assert not result.empty
        expected_cols = {
            "age_bracket", "income_bracket", "tenure",
            "weighted_count", "proportion",
        }
        assert set(result.columns) == expected_cols

    def test_tenure_labels(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_homeownership_rates(households_df, persons_df)
        valid_tenures = {
            "owner_with_mortgage", "owner_free_clear",
            "renter", "renter_no_rent",
        }
        assert set(result["tenure"].unique()) <= valid_tenures

    def test_proportions_sum_to_one(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_homeownership_rates(households_df, persons_df)
        for (age, inc), grp in result.groupby(["age_bracket", "income_bracket"]):
            total = grp["proportion"].sum()
            assert abs(total - 1.0) < 0.01, (
                f"Proportions for {age}/{inc} sum to {total}"
            )

    def test_empty_households(self, persons_df: pd.DataFrame) -> None:
        empty_hh = pd.DataFrame(columns=[
            "SERIALNO", "WGTP", "TYPE", "TEN", "HINCP",
        ])
        result = extract_homeownership_rates(empty_hh, persons_df)
        assert result.empty

    def test_no_ten_column(self, persons_df: pd.DataFrame) -> None:
        hh = pd.DataFrame({"SERIALNO": ["HH0"], "WGTP": [100], "TYPE": [1]})
        result = extract_homeownership_rates(hh, persons_df)
        assert result.empty


# ── Property taxes ─────────────────────────────────────────────────────


class TestPropertyTaxes:
    def test_basic(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_property_taxes(households_df, persons_df)
        assert not result.empty
        expected_cols = {
            "income_bracket", "mean_amount", "median_amount",
            "p25", "p75", "count", "weight",
        }
        assert set(result.columns) == expected_cols

    def test_percentile_ordering(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_property_taxes(households_df, persons_df)
        for _, row in result.iterrows():
            assert row["p25"] <= row["median_amount"] <= row["p75"]

    def test_positive_amounts(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_property_taxes(households_df, persons_df)
        assert (result["mean_amount"] > 0).all()
        assert (result["median_amount"] > 0).all()

    def test_empty_no_taxamt(self, persons_df: pd.DataFrame) -> None:
        hh = pd.DataFrame({
            "SERIALNO": ["HH0"], "WGTP": [100], "TYPE": [1],
            "TEN": [3], "TAXAMT": [0], "HINCP": [50000],
        })
        result = extract_property_taxes(hh, persons_df)
        assert result.empty

    def test_no_taxamt_column(self, persons_df: pd.DataFrame) -> None:
        hh = pd.DataFrame({"SERIALNO": ["HH0"], "WGTP": [100], "TYPE": [1]})
        result = extract_property_taxes(hh, persons_df)
        assert result.empty


# ── Mortgage costs ─────────────────────────────────────────────────────


class TestMortgageCosts:
    def test_basic(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_mortgage_costs(households_df, persons_df)
        assert not result.empty
        expected_cols = {
            "income_bracket", "age_bracket",
            "mean_monthly", "median_monthly",
            "p25", "p75", "count", "weight",
        }
        assert set(result.columns) == expected_cols

    def test_has_age_bracket(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_mortgage_costs(households_df, persons_df)
        valid_ages = {"<25", "25-34", "35-44", "45-54", "55-64", "65+"}
        assert set(result["age_bracket"].unique()) <= valid_ages

    def test_percentile_ordering(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_mortgage_costs(households_df, persons_df)
        for _, row in result.iterrows():
            assert row["p25"] <= row["median_monthly"] <= row["p75"]

    def test_positive_amounts(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        result = extract_mortgage_costs(households_df, persons_df)
        assert (result["mean_monthly"] > 0).all()

    def test_only_mortgage_owners(
        self, households_df: pd.DataFrame, persons_df: pd.DataFrame,
    ) -> None:
        """Only TEN=1 (owner with mortgage) should be included."""
        hh_renters = households_df.copy()
        hh_renters["TEN"] = 3
        hh_renters["MRGP"] = 0
        result = extract_mortgage_costs(hh_renters, persons_df)
        assert result.empty

    def test_no_mrgp_column(self, persons_df: pd.DataFrame) -> None:
        hh = pd.DataFrame({"SERIALNO": ["HH0"], "WGTP": [100], "TYPE": [1]})
        result = extract_mortgage_costs(hh, persons_df)
        assert result.empty
