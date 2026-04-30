"""
Part 2 extraction — employment, income, and occupation tables.

Extracts distribution tables from PUMS data needed for Part 2 of VITA intake
(income verification).  Output is appended to the same SQLite file that Part 1
extraction created: data/distributions_{state}_{year}.sqlite

Usage:
    python -m extraction.extract_part2 --state HI --year 2022

Tables extracted (12):
    1.  employment_by_age                   — Employment status by age bracket
    2.  education_by_age                    — Education level by age bracket
    3.  disability_by_age                   — Disability rate by age bracket
    4.  social_security                     — SS income distribution by age
    5.  retirement_income                   — Retirement income by age
    6.  interest_and_dividend_income        — Interest/dividend income by age
    7.  other_income_by_employment_status   — Other income by employment status
    8.  public_assistance_income            — Public assistance by age
    9.  occupation_wages                    — Wage percentiles by occupation group
   10.  education_occupation_probabilities  — Education × occupation cross-tab
   11.  age_income_adjustments              — Wage adjustment factors by age
   12.  occupation_self_employment_rates    — Self-employment rates by occupation

Reference: HouseholdRNG/scripts/extract_pums.py + extract_bls.py
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
# PUMS code mappings
# =========================================================================

AGE_BRACKETS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

# ESR (Employment Status Recode) — only valid for persons 16+
_ESR_EMPLOYED = {1, 2, 4, 5}  # civilian at work, with job, armed forces
_ESR_UNEMPLOYED = {3}
_ESR_NILF = {6}  # not in labor force

EMPLOYMENT_STATUS_MAP = {
    1: "employed", 2: "employed",
    3: "unemployed",
    4: "employed", 5: "employed",
    6: "not_in_labor_force",
}

# SCHL (Schooling) → EducationLevel enum values
EDUCATION_MAP = {
    **{i: "less_than_hs" for i in range(1, 16)},
    16: "high_school", 17: "high_school",
    18: "some_college", 19: "some_college",
    20: "associates",
    21: "bachelors",
    22: "masters",
    23: "professional",
    24: "doctorate",
}

# OCCP (Occupation) grouped into major categories by code range
OCCUPATION_GROUPS = [
    (10, 440, "management", "Management"),
    (500, 960, "business_financial", "Business and Financial Operations"),
    (1005, 1240, "computer_math", "Computer and Mathematical"),
    (1305, 1560, "architecture_engineering", "Architecture and Engineering"),
    (1600, 1980, "science", "Life, Physical, and Social Science"),
    (2001, 2060, "community_social", "Community and Social Service"),
    (2100, 2180, "legal", "Legal"),
    (2200, 2555, "education", "Education, Training, and Library"),
    (2600, 2970, "arts_media", "Arts, Design, Entertainment, Sports, and Media"),
    (3000, 3550, "healthcare_practitioner", "Healthcare Practitioners and Technical"),
    (3600, 3655, "healthcare_support", "Healthcare Support"),
    (3700, 3960, "protective_service", "Protective Service"),
    (4000, 4160, "food_service", "Food Preparation and Serving"),
    (4200, 4255, "maintenance_grounds", "Building and Grounds Maintenance"),
    (4340, 4655, "personal_care", "Personal Care and Service"),
    (4700, 4965, "sales", "Sales and Related"),
    (5000, 5940, "office_admin", "Office and Administrative Support"),
    (6005, 6130, "farming", "Farming, Fishing, and Forestry"),
    (6200, 6950, "construction", "Construction and Extraction"),
    (7000, 7640, "repair", "Installation, Maintenance, and Repair"),
    (7700, 8990, "production", "Production"),
    (9005, 9760, "transportation", "Transportation and Material Moving"),
    (9800, 9830, "military", "Military Specific"),
]

# COW (Class of Worker) — self-employed codes
_COW_SELF_EMPLOYED = {6, 7}  # 6=SE incorporated, 7=SE not incorporated

# Income bracket definitions for distribution tables
WAGE_BRACKETS = [
    "Under $10K", "$10K-$20K", "$20K-$30K", "$30K-$40K", "$40K-$50K",
    "$50K-$75K", "$75K-$100K", "$100K-$150K", "$150K+",
]

BENEFIT_BRACKETS = [
    "$1-$5K", "$5K-$10K", "$10K-$15K", "$15K-$20K",
    "$20K-$25K", "$25K-$30K", "$30K+",
]

SMALL_INCOME_BRACKETS = [
    "$1-$1K", "$1K-$5K", "$5K-$10K", "$10K-$25K", "$25K-$50K", "$50K+",
]


# =========================================================================
# Helpers
# =========================================================================


def _age_to_bracket(age: int) -> str:
    if age < 18:
        return "Under 18"
    elif age <= 24:
        return "18-24"
    elif age <= 34:
        return "25-34"
    elif age <= 44:
        return "35-44"
    elif age <= 54:
        return "45-54"
    elif age <= 64:
        return "55-64"
    else:
        return "65+"


def _amount_to_wage_bracket(amount: int) -> str:
    if amount < 10_000:
        return "Under $10K"
    elif amount < 20_000:
        return "$10K-$20K"
    elif amount < 30_000:
        return "$20K-$30K"
    elif amount < 40_000:
        return "$30K-$40K"
    elif amount < 50_000:
        return "$40K-$50K"
    elif amount < 75_000:
        return "$50K-$75K"
    elif amount < 100_000:
        return "$75K-$100K"
    elif amount < 150_000:
        return "$100K-$150K"
    else:
        return "$150K+"


def _amount_to_benefit_bracket(amount: int) -> str:
    if amount < 5_000:
        return "$1-$5K"
    elif amount < 10_000:
        return "$5K-$10K"
    elif amount < 15_000:
        return "$10K-$15K"
    elif amount < 20_000:
        return "$15K-$20K"
    elif amount < 25_000:
        return "$20K-$25K"
    elif amount < 30_000:
        return "$25K-$30K"
    else:
        return "$30K+"


def _amount_to_small_bracket(amount: int) -> str:
    if amount < 1_000:
        return "$1-$1K"
    elif amount < 5_000:
        return "$1K-$5K"
    elif amount < 10_000:
        return "$5K-$10K"
    elif amount < 25_000:
        return "$10K-$25K"
    elif amount < 50_000:
        return "$25K-$50K"
    else:
        return "$50K+"


def _occp_to_group(occp_code: int) -> Optional[str]:
    for low, high, group_id, _ in OCCUPATION_GROUPS:
        if low <= occp_code <= high:
            return group_id
    return None


def _occp_to_title(occp_code: int) -> Optional[str]:
    for low, high, _, title in OCCUPATION_GROUPS:
        if low <= occp_code <= high:
            return title
    return None


# =========================================================================
# Extraction functions — one per distribution table
# =========================================================================


def extract_employment_by_age(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract employment status distribution by age bracket.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, employment_status, weight, proportion].
    """
    logger.info("Extracting employment_by_age...")

    adults = persons_df[persons_df["AGEP"] >= 16].copy()
    if adults.empty:
        return pd.DataFrame(columns=["age_bracket", "employment_status", "weight", "proportion"])

    adults = adults.dropna(subset=["ESR"])
    adults["age_bracket"] = adults["AGEP"].apply(_age_to_bracket)
    adults["employment_status"] = adults["ESR"].astype(int).map(EMPLOYMENT_STATUS_MAP)

    result = (
        adults.groupby(["age_bracket", "employment_status"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    totals = result.groupby("age_bracket")["weight"].transform("sum")
    result["proportion"] = result["weight"] / totals
    result = result.sort_values(["age_bracket", "employment_status"]).reset_index(drop=True)

    logger.info("  %d rows", len(result))
    return result


def extract_education_by_age(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract education level distribution by age bracket (adults 18+ only).

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, education_level, weight, proportion].
    """
    logger.info("Extracting education_by_age...")

    adults = persons_df[persons_df["AGEP"] >= 18].copy()
    if adults.empty:
        return pd.DataFrame(columns=["age_bracket", "education_level", "weight", "proportion"])

    adults = adults.dropna(subset=["SCHL"])
    adults["age_bracket"] = adults["AGEP"].apply(_age_to_bracket)
    adults["education_level"] = adults["SCHL"].astype(int).map(EDUCATION_MAP)
    adults = adults.dropna(subset=["education_level"])

    result = (
        adults.groupby(["age_bracket", "education_level"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    totals = result.groupby("age_bracket")["weight"].transform("sum")
    result["proportion"] = result["weight"] / totals
    result = result.sort_values(["age_bracket", "education_level"]).reset_index(drop=True)

    logger.info("  %d rows", len(result))
    return result


def extract_disability_by_age(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract disability rate by age bracket.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, has_disability, weight, proportion].
    """
    logger.info("Extracting disability_by_age...")

    df = persons_df.dropna(subset=["DIS"]).copy()
    if df.empty:
        return pd.DataFrame(columns=["age_bracket", "has_disability", "weight", "proportion"])

    df["age_bracket"] = df["AGEP"].apply(_age_to_bracket)
    df["has_disability"] = (df["DIS"].astype(int) == 1).astype(int)

    result = (
        df.groupby(["age_bracket", "has_disability"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    totals = result.groupby("age_bracket")["weight"].transform("sum")
    result["proportion"] = result["weight"] / totals
    result = result.sort_values(["age_bracket", "has_disability"]).reset_index(drop=True)

    logger.info("  %d rows", len(result))
    return result


def extract_social_security(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract Social Security income distribution by age bracket.

    Combines SSP (Social Security) and SSIP (Supplemental Security Income).
    Only includes persons with positive SS income.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, income_bracket, weight, has_ss_proportion].
    """
    logger.info("Extracting social_security...")

    df = persons_df.copy()
    ss_cols = []
    if "SSP" in df.columns:
        ss_cols.append("SSP")
    if "SSIP" in df.columns:
        ss_cols.append("SSIP")
    if not ss_cols:
        logger.warning("  No SSP/SSIP columns found in PUMS data")
        return pd.DataFrame(columns=["age_bracket", "income_bracket", "weight", "has_ss_proportion"])

    df["ss_total"] = df[ss_cols].fillna(0).sum(axis=1)
    df["age_bracket"] = df["AGEP"].apply(_age_to_bracket)

    age_totals = df.groupby("age_bracket")["PWGTP"].sum()

    recipients = df[df["ss_total"] > 0].copy()
    if recipients.empty:
        return pd.DataFrame(columns=["age_bracket", "income_bracket", "weight", "has_ss_proportion"])

    recipients["income_bracket"] = recipients["ss_total"].astype(int).apply(_amount_to_benefit_bracket)

    result = (
        recipients.groupby(["age_bracket", "income_bracket"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    recipient_totals = recipients.groupby("age_bracket")["PWGTP"].sum()
    result["has_ss_proportion"] = result["age_bracket"].map(
        lambda ab: recipient_totals.get(ab, 0) / age_totals.get(ab, 1)
    )

    result = result.sort_values(["age_bracket", "income_bracket"]).reset_index(drop=True)
    logger.info("  %d rows", len(result))
    return result


def extract_retirement_income(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract retirement income distribution by age bracket.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, income_bracket, weight, has_ret_proportion].
    """
    logger.info("Extracting retirement_income...")

    if "RETP" not in persons_df.columns:
        logger.warning("  No RETP column found in PUMS data")
        return pd.DataFrame(columns=["age_bracket", "income_bracket", "weight", "has_ret_proportion"])

    df = persons_df.copy()
    df["age_bracket"] = df["AGEP"].apply(_age_to_bracket)
    age_totals = df.groupby("age_bracket")["PWGTP"].sum()

    recipients = df[df["RETP"].fillna(0) > 0].copy()
    if recipients.empty:
        return pd.DataFrame(columns=["age_bracket", "income_bracket", "weight", "has_ret_proportion"])

    recipients["income_bracket"] = recipients["RETP"].astype(int).apply(_amount_to_benefit_bracket)

    result = (
        recipients.groupby(["age_bracket", "income_bracket"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    recipient_totals = recipients.groupby("age_bracket")["PWGTP"].sum()
    result["has_ret_proportion"] = result["age_bracket"].map(
        lambda ab: recipient_totals.get(ab, 0) / age_totals.get(ab, 1)
    )

    result = result.sort_values(["age_bracket", "income_bracket"]).reset_index(drop=True)
    logger.info("  %d rows", len(result))
    return result


def extract_interest_and_dividend_income(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract interest/dividend income distribution by age bracket.

    PUMS INTP combines interest, dividends, and net rental income.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, income_bracket, weight, has_inv_proportion].
    """
    logger.info("Extracting interest_and_dividend_income...")

    if "INTP" not in persons_df.columns:
        logger.warning("  No INTP column found in PUMS data")
        return pd.DataFrame(
            columns=["age_bracket", "income_bracket", "weight", "has_inv_proportion"]
        )

    df = persons_df.copy()
    df["age_bracket"] = df["AGEP"].apply(_age_to_bracket)
    age_totals = df.groupby("age_bracket")["PWGTP"].sum()

    recipients = df[df["INTP"].fillna(0) > 0].copy()
    if recipients.empty:
        return pd.DataFrame(
            columns=["age_bracket", "income_bracket", "weight", "has_inv_proportion"]
        )

    recipients["income_bracket"] = recipients["INTP"].astype(int).apply(_amount_to_small_bracket)

    result = (
        recipients.groupby(["age_bracket", "income_bracket"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    recipient_totals = recipients.groupby("age_bracket")["PWGTP"].sum()
    result["has_inv_proportion"] = result["age_bracket"].map(
        lambda ab: recipient_totals.get(ab, 0) / age_totals.get(ab, 1)
    )

    result = result.sort_values(["age_bracket", "income_bracket"]).reset_index(drop=True)
    logger.info("  %d rows", len(result))
    return result


def extract_other_income_by_employment_status(
    persons_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract other income distribution by employment status.

    PUMS OIP covers income sources like unemployment compensation,
    alimony, and miscellaneous.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [employment_status, income_bracket, weight].
    """
    logger.info("Extracting other_income_by_employment_status...")

    if "OIP" not in persons_df.columns:
        logger.warning("  No OIP column found in PUMS data")
        return pd.DataFrame(columns=["employment_status", "income_bracket", "weight"])

    df = persons_df[persons_df["AGEP"] >= 16].copy()
    df = df.dropna(subset=["ESR"])

    recipients = df[df["OIP"].fillna(0) > 0].copy()
    if recipients.empty:
        return pd.DataFrame(columns=["employment_status", "income_bracket", "weight"])

    recipients["employment_status"] = recipients["ESR"].astype(int).map(EMPLOYMENT_STATUS_MAP)
    recipients["income_bracket"] = recipients["OIP"].astype(int).apply(_amount_to_small_bracket)

    result = (
        recipients.groupby(["employment_status", "income_bracket"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    result = result.sort_values(["employment_status", "income_bracket"]).reset_index(drop=True)
    logger.info("  %d rows", len(result))
    return result


def extract_public_assistance_income(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract public assistance income distribution by age bracket.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, income_bracket, weight, has_pa_proportion].
    """
    logger.info("Extracting public_assistance_income...")

    if "PAP" not in persons_df.columns:
        logger.warning("  No PAP column found in PUMS data")
        return pd.DataFrame(columns=["age_bracket", "income_bracket", "weight", "has_pa_proportion"])

    df = persons_df.copy()
    df["age_bracket"] = df["AGEP"].apply(_age_to_bracket)
    age_totals = df.groupby("age_bracket")["PWGTP"].sum()

    recipients = df[df["PAP"].fillna(0) > 0].copy()
    if recipients.empty:
        return pd.DataFrame(columns=["age_bracket", "income_bracket", "weight", "has_pa_proportion"])

    recipients["income_bracket"] = recipients["PAP"].astype(int).apply(_amount_to_small_bracket)

    result = (
        recipients.groupby(["age_bracket", "income_bracket"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    recipient_totals = recipients.groupby("age_bracket")["PWGTP"].sum()
    result["has_pa_proportion"] = result["age_bracket"].map(
        lambda ab: recipient_totals.get(ab, 0) / age_totals.get(ab, 1)
    )

    result = result.sort_values(["age_bracket", "income_bracket"]).reset_index(drop=True)
    logger.info("  %d rows", len(result))
    return result


def extract_occupation_wages(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract wage percentiles by major occupation group.

    Derives occupation-specific wage distributions from PUMS WAGP × OCCP
    as a proxy for BLS OEWS data.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [occupation_group, occupation_title,
            median_wage, p25_wage, p75_wage, mean_wage, count, weight].
    """
    logger.info("Extracting occupation_wages...")

    if "OCCP" not in persons_df.columns or "WAGP" not in persons_df.columns:
        logger.warning("  No OCCP/WAGP columns found in PUMS data")
        return pd.DataFrame(columns=[
            "occupation_group", "occupation_title",
            "median_wage", "p25_wage", "p75_wage", "mean_wage", "count", "weight",
        ])

    employed = persons_df[
        (persons_df["ESR"].isin(_ESR_EMPLOYED))
        & (persons_df["WAGP"].fillna(0) > 0)
        & (persons_df["OCCP"].notna())
    ].copy()

    if employed.empty:
        return pd.DataFrame(columns=[
            "occupation_group", "occupation_title",
            "median_wage", "p25_wage", "p75_wage", "mean_wage", "count", "weight",
        ])

    employed["occupation_group"] = employed["OCCP"].astype(int).apply(_occp_to_group)
    employed["occupation_title"] = employed["OCCP"].astype(int).apply(_occp_to_title)
    employed = employed.dropna(subset=["occupation_group"])

    records = []
    for group, grp_df in employed.groupby("occupation_group"):
        wages = grp_df["WAGP"].values
        weights = grp_df["PWGTP"].values
        title = grp_df["occupation_title"].iloc[0]

        sorted_idx = np.argsort(wages)
        sorted_wages = wages[sorted_idx]
        sorted_weights = weights[sorted_idx]
        cumulative = np.cumsum(sorted_weights)
        total_weight = cumulative[-1]

        def _weighted_percentile(p: float) -> int:
            target = total_weight * p
            idx = np.searchsorted(cumulative, target)
            idx = min(idx, len(sorted_wages) - 1)
            return int(sorted_wages[idx])

        records.append({
            "occupation_group": group,
            "occupation_title": title,
            "median_wage": _weighted_percentile(0.50),
            "p25_wage": _weighted_percentile(0.25),
            "p75_wage": _weighted_percentile(0.75),
            "mean_wage": int(np.average(wages, weights=weights)),
            "count": len(grp_df),
            "weight": int(total_weight),
        })

    result = pd.DataFrame(records).sort_values("weight", ascending=False).reset_index(drop=True)
    logger.info("  %d occupation groups", len(result))
    return result


def extract_education_occupation_probabilities(
    persons_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract education × occupation cross-tabulation for employed adults.

    Used by the generator to sample likely occupations given a person's
    education level.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [education_level, occupation_group, weight, proportion].
    """
    logger.info("Extracting education_occupation_probabilities...")

    if "SCHL" not in persons_df.columns or "OCCP" not in persons_df.columns:
        logger.warning("  No SCHL/OCCP columns found")
        return pd.DataFrame(columns=["education_level", "occupation_group", "weight", "proportion"])

    employed = persons_df[
        (persons_df["ESR"].isin(_ESR_EMPLOYED))
        & (persons_df["OCCP"].notna())
        & (persons_df["SCHL"].notna())
    ].copy()

    if employed.empty:
        return pd.DataFrame(columns=["education_level", "occupation_group", "weight", "proportion"])

    employed["education_level"] = employed["SCHL"].astype(int).map(EDUCATION_MAP)
    employed["occupation_group"] = employed["OCCP"].astype(int).apply(_occp_to_group)
    employed = employed.dropna(subset=["education_level", "occupation_group"])

    result = (
        employed.groupby(["education_level", "occupation_group"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    totals = result.groupby("education_level")["weight"].transform("sum")
    result["proportion"] = result["weight"] / totals

    result = result.sort_values(["education_level", "weight"], ascending=[True, False])
    result = result.reset_index(drop=True)
    logger.info("  %d rows", len(result))
    return result


def extract_age_income_adjustments(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract wage statistics by age bracket for employed adults.

    Provides adjustment factors so the generator can scale occupation
    wages by age (e.g., early-career workers earn less than mid-career).

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, median_wage, mean_wage,
            adjustment_factor, count, weight].
    """
    logger.info("Extracting age_income_adjustments...")

    if "WAGP" not in persons_df.columns:
        logger.warning("  No WAGP column found")
        return pd.DataFrame(columns=[
            "age_bracket", "median_wage", "mean_wage",
            "adjustment_factor", "count", "weight",
        ])

    employed = persons_df[
        (persons_df["ESR"].isin(_ESR_EMPLOYED))
        & (persons_df["WAGP"].fillna(0) > 0)
    ].copy()

    if employed.empty:
        return pd.DataFrame(columns=[
            "age_bracket", "median_wage", "mean_wage",
            "adjustment_factor", "count", "weight",
        ])

    employed["age_bracket"] = employed["AGEP"].apply(_age_to_bracket)

    overall_median = float(np.median(employed["WAGP"]))

    records = []
    for bracket, grp in employed.groupby("age_bracket"):
        wages = grp["WAGP"].values
        weights = grp["PWGTP"].values

        sorted_idx = np.argsort(wages)
        sorted_wages = wages[sorted_idx]
        sorted_weights = weights[sorted_idx]
        cumulative = np.cumsum(sorted_weights)
        total_weight = cumulative[-1]
        target = total_weight * 0.5
        idx = min(np.searchsorted(cumulative, target), len(sorted_wages) - 1)
        median = int(sorted_wages[idx])

        mean = int(np.average(wages, weights=weights))
        adjustment = median / overall_median if overall_median > 0 else 1.0

        records.append({
            "age_bracket": bracket,
            "median_wage": median,
            "mean_wage": mean,
            "adjustment_factor": round(adjustment, 3),
            "count": len(grp),
            "weight": int(total_weight),
        })

    result = pd.DataFrame(records).sort_values("age_bracket").reset_index(drop=True)
    logger.info("  %d brackets", len(result))
    return result


def extract_occupation_self_employment_rates(
    persons_df: pd.DataFrame,
) -> pd.DataFrame:
    """Extract self-employment rates by occupation group.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [occupation_group, se_rate, se_count, total_count, weight].
    """
    logger.info("Extracting occupation_self_employment_rates...")

    if "COW" not in persons_df.columns or "OCCP" not in persons_df.columns:
        logger.warning("  No COW/OCCP columns found")
        return pd.DataFrame(columns=["occupation_group", "se_rate", "se_count", "total_count", "weight"])

    employed = persons_df[
        (persons_df["ESR"].isin(_ESR_EMPLOYED))
        & (persons_df["COW"].notna())
        & (persons_df["OCCP"].notna())
    ].copy()

    if employed.empty:
        return pd.DataFrame(columns=["occupation_group", "se_rate", "se_count", "total_count", "weight"])

    employed["occupation_group"] = employed["OCCP"].astype(int).apply(_occp_to_group)
    employed["is_se"] = employed["COW"].astype(int).isin(_COW_SELF_EMPLOYED)
    employed = employed.dropna(subset=["occupation_group"])

    records = []
    for group, grp in employed.groupby("occupation_group"):
        total_weight = int(grp["PWGTP"].sum())
        se_weight = int(grp.loc[grp["is_se"], "PWGTP"].sum())
        se_rate = se_weight / total_weight if total_weight > 0 else 0.0

        records.append({
            "occupation_group": group,
            "se_rate": round(se_rate, 4),
            "se_count": int(grp["is_se"].sum()),
            "total_count": len(grp),
            "weight": total_weight,
        })

    result = pd.DataFrame(records).sort_values("weight", ascending=False).reset_index(drop=True)
    logger.info("  %d occupation groups", len(result))
    return result


# =========================================================================
# Main extraction pipeline
# =========================================================================


def extract_all_part2(
    state: str,
    year: int,
    output_path: Optional[Path] = None,
) -> Path:
    """Run the full Part 2 extraction pipeline.

    Downloads PUMS data (if not cached), extracts all 12 income/employment
    distribution tables, and appends them to the existing SQLite database
    created by Part 1 extraction.

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
    logger.info("Part 2 Extraction: %s %d", state.upper(), year)
    logger.info("Output: %s", output_path)
    logger.info("=" * 60)

    # Step 1: Download PUMS data
    logger.info("Step 1/3: Downloading PUMS data...")
    household_zip, person_zip = download_pums_files(state, year)

    # Step 2: Load into DataFrames
    logger.info("Step 2/3: Loading PUMS data...")
    _households_df, persons_df = load_pums_data(household_zip, person_zip)

    # Step 3: Extract all 12 tables
    logger.info("Step 3/3: Extracting Part 2 distribution tables...")

    tables = {
        "employment_by_age": extract_employment_by_age(persons_df),
        "education_by_age": extract_education_by_age(persons_df),
        "disability_by_age": extract_disability_by_age(persons_df),
        "social_security": extract_social_security(persons_df),
        "retirement_income": extract_retirement_income(persons_df),
        "interest_and_dividend_income": extract_interest_and_dividend_income(persons_df),
        "other_income_by_employment_status": extract_other_income_by_employment_status(persons_df),
        "public_assistance_income": extract_public_assistance_income(persons_df),
        "occupation_wages": extract_occupation_wages(persons_df),
        "education_occupation_probabilities": extract_education_occupation_probabilities(persons_df),
        "age_income_adjustments": extract_age_income_adjustments(persons_df),
        "occupation_self_employment_rates": extract_occupation_self_employment_rates(persons_df),
    }

    # Write to SQLite (append to existing DB from Part 1)
    engine = create_engine(f"sqlite:///{output_path}")
    for table_name, df in tables.items():
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        logger.info("  Wrote %s: %d rows", table_name, len(df))

    engine.dispose()

    logger.info("=" * 60)
    logger.info("Part 2 extraction complete: %s", output_path)
    logger.info("Tables written: %d", len(tables))
    logger.info("=" * 60)

    return output_path


def main() -> None:
    """CLI entry point for Part 2 extraction."""
    parser = argparse.ArgumentParser(
        description="Extract Part 2 distribution tables (employment/income) from PUMS data"
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
        output = extract_all_part2(args.state, args.year, args.output)
        print(f"\nSuccess: {output}")
    except Exception:
        logger.exception("Extraction failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
