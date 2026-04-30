"""
Part 3 extraction — housing, homeownership, and deduction-related tables.

Extracts distribution tables from PUMS data needed for Part 3 of VITA intake
(expenses and deductions).  Output is appended to the same SQLite file that
Part 1/2 extraction created: data/distributions_{state}_{year}.sqlite

Usage:
    python -m extraction.extract_part3 --state HI --year 2022

Tables extracted (3):
    1.  homeownership_rates   — Owner vs renter by age bracket and income bracket
    2.  property_taxes        — Property tax amounts by income bracket (owners only)
    3.  mortgage_costs        — Monthly mortgage payment distribution by income bracket

Notes on mortgage interest:
    PUMS does not provide a direct mortgage-interest variable.  MRGP gives the
    total first-mortgage payment (principal + interest).  We store the raw MRGP
    distribution; the expense generator estimates the interest portion using a
    standard amortization split (early in a 30-year loan ~70-80% of the payment
    is interest; later ~20-30%).  The generator applies an interest-fraction
    heuristic based on householder age as a proxy for loan maturity.

Reference: HouseholdRNG/generator/expense_generator.py
See docs/DATA_DICTIONARY.md for PUMS variable mappings.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
from sqlalchemy import create_engine

from .pums_download import download_pums_files, load_pums_data, validate_inputs

logger = logging.getLogger(__name__)

PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# =========================================================================
# Bracket helpers
# =========================================================================

AGE_BRACKETS = ["<25", "25-34", "35-44", "45-54", "55-64", "65+"]

INCOME_BRACKETS = [
    "<$25K", "$25-50K", "$50-75K", "$75-100K", "$100-150K", "$150K+",
]

# TEN (tenure) codes
TEN_OWNED_WITH_MORTGAGE = 1
TEN_OWNED_FREE_CLEAR = 2
TEN_RENTED = 3
TEN_NO_RENT = 4

TENURE_LABELS = {
    TEN_OWNED_WITH_MORTGAGE: "owner_with_mortgage",
    TEN_OWNED_FREE_CLEAR: "owner_free_clear",
    TEN_RENTED: "renter",
    TEN_NO_RENT: "renter_no_rent",
}


def _age_to_bracket(age: int) -> str:
    if age < 25:
        return "<25"
    elif age < 35:
        return "25-34"
    elif age < 45:
        return "35-44"
    elif age < 55:
        return "45-54"
    elif age < 65:
        return "55-64"
    return "65+"


def _income_to_bracket(income: int) -> str:
    if income < 25000:
        return "<$25K"
    elif income < 50000:
        return "$25-50K"
    elif income < 75000:
        return "$50-75K"
    elif income < 100000:
        return "$75-100K"
    elif income < 150000:
        return "$100-150K"
    return "$150K+"


# =========================================================================
# Extraction functions
# =========================================================================


def extract_homeownership_rates(
    households_df: pd.DataFrame,
    persons_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract homeownership rates by age bracket and income bracket.

    Uses household tenure (TEN), householder age (AGEP), and household
    income (HINCP) to build a cross-tabulated distribution of owner vs
    renter status.

    Args:
        households_df: Household-level PUMS records with TEN, HINCP, WGTP.
        persons_df: Person-level PUMS records (for householder age).

    Returns:
        DataFrame with columns: [age_bracket, income_bracket, tenure,
            weighted_count, proportion].
    """
    logger.info("Extracting homeownership_rates...")

    if "TEN" not in households_df.columns:
        logger.warning("  No TEN column found in household data")
        return pd.DataFrame(
            columns=["age_bracket", "income_bracket", "tenure",
                     "weighted_count", "proportion"]
        )

    # Housing units only (TYPE=1), with valid tenure
    hh = households_df.copy()
    if "TYPE" in hh.columns:
        hh = hh[hh["TYPE"] == 1]
    hh = hh[hh["TEN"].notna() & hh["TEN"].isin(TENURE_LABELS.keys())]

    # Get householder age from person records
    householders = persons_df[persons_df["RELSHIPP"] == 20][
        ["SERIALNO", "AGEP"]
    ].copy()
    householders = householders.rename(columns={"AGEP": "hh_age"})

    merged = hh.merge(householders, on="SERIALNO", how="inner")
    if merged.empty:
        logger.warning("  No matched householder records")
        return pd.DataFrame(
            columns=["age_bracket", "income_bracket", "tenure",
                     "weighted_count", "proportion"]
        )

    merged["age_bracket"] = merged["hh_age"].astype(int).apply(_age_to_bracket)
    merged["income_bracket"] = merged["HINCP"].fillna(0).astype(int).apply(
        _income_to_bracket
    )
    merged["tenure"] = merged["TEN"].astype(int).map(TENURE_LABELS)

    result = (
        merged.groupby(["age_bracket", "income_bracket", "tenure"])["WGTP"]
        .sum()
        .reset_index()
        .rename(columns={"WGTP": "weighted_count"})
    )

    # Within-cell proportions (within each age × income group)
    group_totals = result.groupby(
        ["age_bracket", "income_bracket"]
    )["weighted_count"].transform("sum")
    result["proportion"] = result["weighted_count"] / group_totals
    result["proportion"] = result["proportion"].fillna(0).round(4)

    result = result.sort_values(
        ["age_bracket", "income_bracket", "tenure"]
    ).reset_index(drop=True)

    logger.info("  %d rows across %d age × income cells",
                len(result), len(result.groupby(["age_bracket", "income_bracket"])))
    return result


def extract_property_taxes(
    households_df: pd.DataFrame,
    persons_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract property tax distribution by income bracket for homeowners.

    Uses TAXAMT (annual property taxes, only populated for owners) grouped
    by household income bracket.  Computes mean, median, and percentiles.

    PUMS TAXAMT coding:
        0 or NaN = N/A (renter or not reported)
        1        = None (owner, no property tax — rare)
        2+       = Annual property tax in dollars

    Args:
        households_df: Household-level PUMS records with TAXAMT, HINCP, WGTP.
        persons_df: Person-level records (for householder age).

    Returns:
        DataFrame with columns: [income_bracket, mean_amount, median_amount,
            p25, p75, count, weight].
    """
    logger.info("Extracting property_taxes...")

    if "TAXAMT" not in households_df.columns:
        logger.warning("  No TAXAMT column found in household data")
        return pd.DataFrame(
            columns=["income_bracket", "mean_amount", "median_amount",
                     "p25", "p75", "count", "weight"]
        )

    hh = households_df.copy()
    if "TYPE" in hh.columns:
        hh = hh[hh["TYPE"] == 1]

    # Owners with actual property tax amounts (TAXAMT >= 2 means real dollars)
    hh = hh[hh["TAXAMT"].notna() & (hh["TAXAMT"] >= 2)]

    if hh.empty:
        logger.warning("  No property tax records found")
        return pd.DataFrame(
            columns=["income_bracket", "mean_amount", "median_amount",
                     "p25", "p75", "count", "weight"]
        )

    hh["income_bracket"] = hh["HINCP"].fillna(0).astype(int).apply(
        _income_to_bracket
    )

    records = []
    for bracket, grp in hh.groupby("income_bracket"):
        amounts = grp["TAXAMT"].values.astype(float)
        weights = grp["WGTP"].values.astype(float)

        sorted_idx = np.argsort(amounts)
        sorted_amounts = amounts[sorted_idx]
        sorted_weights = weights[sorted_idx]
        cumulative = np.cumsum(sorted_weights)
        total_weight = cumulative[-1]

        def _weighted_percentile(pct: float) -> int:
            target = total_weight * pct
            idx = min(np.searchsorted(cumulative, target), len(sorted_amounts) - 1)
            return int(sorted_amounts[idx])

        records.append({
            "income_bracket": bracket,
            "mean_amount": int(np.average(amounts, weights=weights)),
            "median_amount": _weighted_percentile(0.5),
            "p25": _weighted_percentile(0.25),
            "p75": _weighted_percentile(0.75),
            "count": len(grp),
            "weight": int(total_weight),
        })

    result = pd.DataFrame(records)

    # Sort by bracket order
    bracket_order = {b: i for i, b in enumerate(INCOME_BRACKETS)}
    result["_sort"] = result["income_bracket"].map(bracket_order)
    result = result.sort_values("_sort").drop(columns="_sort").reset_index(drop=True)

    logger.info("  %d income brackets", len(result))
    return result


def extract_mortgage_costs(
    households_df: pd.DataFrame,
    persons_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract monthly mortgage payment distribution by income and age bracket.

    Uses MRGP (first mortgage monthly payment) for owners with a mortgage
    (TEN=1).  The expense generator derives annual mortgage interest from
    these payments using an amortization heuristic.

    PUMS MRGP coding:
        0 or NaN = N/A (no mortgage or renter)
        1+       = Monthly first-mortgage payment in dollars

    Storing the distribution by both income and age bracket allows the
    generator to estimate the interest fraction: younger householders
    are earlier in their loan, so a larger share of the payment is
    interest.

    Args:
        households_df: Household-level PUMS records with MRGP, TEN, HINCP, WGTP.
        persons_df: Person-level records (for householder age).

    Returns:
        DataFrame with columns: [income_bracket, age_bracket,
            mean_monthly, median_monthly, p25, p75, count, weight].
    """
    logger.info("Extracting mortgage_costs...")

    if "MRGP" not in households_df.columns:
        logger.warning("  No MRGP column found in household data")
        return pd.DataFrame(
            columns=["income_bracket", "age_bracket",
                     "mean_monthly", "median_monthly",
                     "p25", "p75", "count", "weight"]
        )

    hh = households_df.copy()
    if "TYPE" in hh.columns:
        hh = hh[hh["TYPE"] == 1]

    # Owners with mortgage (TEN=1) and valid mortgage payment
    hh = hh[
        (hh["TEN"] == TEN_OWNED_WITH_MORTGAGE)
        & hh["MRGP"].notna()
        & (hh["MRGP"] > 0)
    ]

    if hh.empty:
        logger.warning("  No mortgage records found")
        return pd.DataFrame(
            columns=["income_bracket", "age_bracket",
                     "mean_monthly", "median_monthly",
                     "p25", "p75", "count", "weight"]
        )

    # Get householder age
    householders = persons_df[persons_df["RELSHIPP"] == 20][
        ["SERIALNO", "AGEP"]
    ].copy()
    householders = householders.rename(columns={"AGEP": "hh_age"})

    hh = hh.merge(householders, on="SERIALNO", how="inner")

    hh["income_bracket"] = hh["HINCP"].fillna(0).astype(int).apply(
        _income_to_bracket
    )
    hh["age_bracket"] = hh["hh_age"].astype(int).apply(_age_to_bracket)

    records = []
    for (inc_bracket, age_bracket), grp in hh.groupby(
        ["income_bracket", "age_bracket"]
    ):
        amounts = grp["MRGP"].values.astype(float)
        weights = grp["WGTP"].values.astype(float)

        if len(amounts) == 0:
            continue

        sorted_idx = np.argsort(amounts)
        sorted_amounts = amounts[sorted_idx]
        sorted_weights = weights[sorted_idx]
        cumulative = np.cumsum(sorted_weights)
        total_weight = cumulative[-1]

        def _weighted_percentile(pct: float) -> int:
            target = total_weight * pct
            idx = min(np.searchsorted(cumulative, target), len(sorted_amounts) - 1)
            return int(sorted_amounts[idx])

        records.append({
            "income_bracket": inc_bracket,
            "age_bracket": age_bracket,
            "mean_monthly": int(np.average(amounts, weights=weights)),
            "median_monthly": _weighted_percentile(0.5),
            "p25": _weighted_percentile(0.25),
            "p75": _weighted_percentile(0.75),
            "count": len(grp),
            "weight": int(total_weight),
        })

    result = pd.DataFrame(records)

    bracket_order = {b: i for i, b in enumerate(INCOME_BRACKETS)}
    age_order = {b: i for i, b in enumerate(AGE_BRACKETS)}
    result["_sort_inc"] = result["income_bracket"].map(bracket_order)
    result["_sort_age"] = result["age_bracket"].map(age_order)
    result = (
        result.sort_values(["_sort_inc", "_sort_age"])
        .drop(columns=["_sort_inc", "_sort_age"])
        .reset_index(drop=True)
    )

    logger.info("  %d income × age cells", len(result))
    return result


# =========================================================================
# Main extraction pipeline
# =========================================================================


def extract_all_part3(
    state: str,
    year: int,
    output_path: Optional[Path] = None,
) -> Path:
    """Run the full Part 3 extraction pipeline.

    Downloads PUMS data (if not cached), extracts housing/deduction
    distribution tables, and appends them to the existing SQLite database
    created by Part 1/2 extraction.

    Args:
        state: Two-letter state abbreviation.
        year: ACS 5-Year data year.
        output_path: Optional output SQLite path. Defaults to
            data/distributions_{state}_{year}.sqlite.

    Returns:
        Path to the SQLite file.
    """
    state_lower = validate_inputs(state, year)

    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DATA_DIR / f"distributions_{state_lower}_{year}.sqlite"

    logger.info("=" * 60)
    logger.info("Part 3 Extraction: %s %d", state.upper(), year)
    logger.info("Output: %s", output_path)
    logger.info("=" * 60)

    # Step 1: Download PUMS data
    logger.info("Step 1/3: Downloading PUMS data...")
    household_zip, person_zip = download_pums_files(state, year)

    # Step 2: Load into DataFrames
    logger.info("Step 2/3: Loading PUMS data...")
    households_df, persons_df = load_pums_data(household_zip, person_zip)

    # Step 3: Extract all 3 tables
    logger.info("Step 3/3: Extracting Part 3 distribution tables...")

    tables = {
        "homeownership_rates": extract_homeownership_rates(
            households_df, persons_df
        ),
        "property_taxes": extract_property_taxes(
            households_df, persons_df
        ),
        "mortgage_costs": extract_mortgage_costs(
            households_df, persons_df
        ),
    }

    # Write to SQLite (append to existing DB from Part 1/2)
    engine = create_engine(f"sqlite:///{output_path}")
    for table_name, df in tables.items():
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        logger.info("  Wrote %s: %d rows", table_name, len(df))

    engine.dispose()

    logger.info("=" * 60)
    logger.info("Part 3 extraction complete: %s", output_path)
    logger.info("Tables written: %d", len(tables))
    logger.info("=" * 60)

    return output_path


def main() -> None:
    """CLI entry point for Part 3 extraction."""
    parser = argparse.ArgumentParser(
        description="Extract Part 3 distribution tables (housing/deductions) from PUMS data"
    )
    parser.add_argument(
        "--state",
        required=True,
        help="Two-letter state abbreviation (e.g., HI, CA)",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="ACS 5-Year data year (e.g., 2022)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output SQLite path (default: data/distributions_{state}_{year}.sqlite)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        output = extract_all_part3(args.state, args.year, args.output)
        print(f"\nSuccess: {output}")
    except Exception:
        logger.exception("Extraction failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
