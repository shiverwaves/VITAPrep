"""
Part 1 extraction — household structure + demographics tables.

Extracts 12 distribution tables from PUMS data needed for Part 1 of VITA intake.
Output: SQLite file in data/distributions_{state}_{year}.sqlite

Usage:
    python -m extraction.extract_part1 --state HI --year 2022

The 12 tables extracted:
    1. household_patterns       — Household type distribution
    2. children_by_parent_age   — Child count by parent age bracket
    3. child_age_distributions  — Child ages by relationship type
    4. adult_child_ages         — Adult children (18+) still in household
    5. stepchild_patterns       — Stepchild frequency and household composition
    6. multigenerational_patterns — 3+ generation household structures
    7. unmarried_partner_patterns — Cohabiting couple demographics
    8. race_distribution        — Overall race distribution (weighted)
    9. race_by_age              — Race distribution by age bracket
    10. hispanic_origin_by_age  — Hispanic/Latino origin by age bracket
    11. spousal_age_gaps        — Age difference between householder and spouse
    12. couple_sex_patterns     — Same-sex vs opposite-sex couple distribution

Reference: HouseholdRNG/scripts/extract_pums.py — port the 12 Part 1 functions.
See docs/DATA_DICTIONARY.md for the complete table list.
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import Optional, Union

import pandas as pd
from sqlalchemy import create_engine

from .pums_download import download_pums_files, load_pums_data, validate_inputs

logger = logging.getLogger(__name__)

# Project root (two levels up from extraction/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# PUMS relationship codes (RELSHIPP field)
REL_HOUSEHOLDER = 20
REL_SPOUSE = 21
REL_BIO_CHILD = 23
REL_ADOPTED_CHILD = 24
REL_STEPCHILD = 25
REL_SIBLING = 26
REL_PARENT = 27
REL_GRANDCHILD = 28
REL_OTHER_RELATIVE = 29
REL_UNMARRIED_PARTNER = 30
REL_ROOMMATE = 34
REL_OTHER_NONRELATIVE = 36

# Age brackets for distribution tables
AGE_BRACKETS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]
PARENT_AGE_BRACKETS = [
    "18-24", "25-29", "30-34", "35-39", "40-44", "45-54", "55-64", "65+",
]

# Race code mapping (RAC1P → label)
RACE_MAP = {
    1: "white",
    2: "black",
    3: "american_indian",
    4: "alaska_native",
    5: "american_indian_alaska_native",
    6: "asian",
    7: "native_hawaiian_pacific_islander",
    8: "other",
    9: "two_or_more",
}


def _age_to_bracket(age: int, brackets: list) -> str:
    """Map an age to its bracket string.

    Args:
        age: Integer age.
        brackets: List of bracket strings.

    Returns:
        Matching bracket string, or 'Unknown'.
    """
    for bracket in brackets:
        if bracket.startswith("Under "):
            limit = int(bracket.split()[-1])
            if age < limit:
                return bracket
        elif bracket.endswith("+"):
            limit = int(bracket.rstrip("+"))
            if age >= limit:
                return bracket
        elif "-" in bracket:
            parts = bracket.split("-")
            low, high = int(parts[0]), int(parts[1])
            if low <= age <= high:
                return bracket
    return "Unknown"


def _classify_household(persons_in_hh: pd.DataFrame) -> str:
    """Classify a household into a pattern based on its members.

    Args:
        persons_in_hh: DataFrame of person records for one household.

    Returns:
        Pattern string (e.g., 'married_couple_with_children').
    """
    relationships = set(persons_in_hh["RELSHIPP"].values)
    has_spouse = REL_SPOUSE in relationships
    has_partner = REL_UNMARRIED_PARTNER in relationships
    has_parent = REL_PARENT in relationships

    child_rels = {REL_BIO_CHILD, REL_ADOPTED_CHILD, REL_STEPCHILD, REL_GRANDCHILD}
    has_children = bool(relationships & child_rels)
    has_stepchild = REL_STEPCHILD in relationships

    # Check for multigenerational (parent + grandchild, or 3+ generations)
    has_grandchild = REL_GRANDCHILD in relationships
    if has_parent or (has_grandchild and has_children):
        return "multigenerational"

    if has_partner:
        return "unmarried_partners"

    if has_spouse:
        if has_stepchild:
            return "blended_family"
        if has_children:
            return "married_couple_with_children"
        return "married_couple_no_children"

    # No spouse
    if has_children:
        return "single_parent"

    num_persons = len(persons_in_hh)
    if num_persons == 1:
        return "single_adult"

    return "other"


# =========================================================================
# Extraction functions — one per distribution table
# =========================================================================


def extract_household_patterns(
    households_df: pd.DataFrame, persons_df: pd.DataFrame
) -> pd.DataFrame:
    """Extract household type distribution.

    Classifies each household into a pattern and computes weighted counts.

    Args:
        households_df: Household-level PUMS records.
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [pattern, weight, proportion].
    """
    logger.info("Extracting household_patterns...")

    # Only housing units (TYPE=1), not group quarters
    if "TYPE" in households_df.columns:
        hh_ids = set(
            households_df.loc[households_df["TYPE"] == 1, "SERIALNO"]
        )
        persons_filtered = persons_df[persons_df["SERIALNO"].isin(hh_ids)]
    else:
        persons_filtered = persons_df

    # Classify each household
    classifications = []
    for serialno, group in persons_filtered.groupby("SERIALNO"):
        pattern = _classify_household(group)
        classifications.append({
            "SERIALNO": serialno,
            "pattern": pattern,
        })

    if not classifications:
        logger.warning("No households classified")
        return pd.DataFrame(columns=["pattern", "weight", "proportion"])

    class_df = pd.DataFrame(classifications)

    # Join with household weights
    merged = class_df.merge(
        households_df[["SERIALNO", "WGTP"]],
        on="SERIALNO",
        how="left",
    )
    merged["WGTP"] = merged["WGTP"].fillna(1)

    # Aggregate by pattern
    result = (
        merged.groupby("pattern")["WGTP"]
        .sum()
        .reset_index()
        .rename(columns={"WGTP": "weight"})
    )
    total = result["weight"].sum()
    result["proportion"] = result["weight"] / total if total > 0 else 0
    result = result.sort_values("weight", ascending=False).reset_index(drop=True)

    logger.info("  Found %d household patterns, total weight: %d", len(result), total)
    return result


def extract_children_by_parent_age(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract child count distribution by parent age bracket.

    For each householder with children, counts the number of children
    and groups by the householder's age bracket.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [parent_age_bracket, num_children, weight].
    """
    logger.info("Extracting children_by_parent_age...")

    child_rels = {REL_BIO_CHILD, REL_ADOPTED_CHILD, REL_STEPCHILD}

    records = []
    for serialno, group in persons_df.groupby("SERIALNO"):
        householder = group[group["RELSHIPP"] == REL_HOUSEHOLDER]
        if householder.empty:
            continue

        children = group[
            (group["RELSHIPP"].isin(child_rels)) & (group["AGEP"] < 18)
        ]
        if children.empty:
            continue

        hh_age = int(householder.iloc[0]["AGEP"])
        hh_weight = int(householder.iloc[0]["PWGTP"])
        num_children = len(children)
        age_bracket = _age_to_bracket(hh_age, PARENT_AGE_BRACKETS)

        records.append({
            "parent_age_bracket": age_bracket,
            "num_children": min(num_children, 5),  # Cap at 5 for distribution
            "weight": hh_weight,
        })

    if not records:
        return pd.DataFrame(columns=["parent_age_bracket", "num_children", "weight"])

    result = (
        pd.DataFrame(records)
        .groupby(["parent_age_bracket", "num_children"])["weight"]
        .sum()
        .reset_index()
    )
    return result


def extract_child_age_distributions(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract child age distribution by relationship type.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [relationship, age, weight].
    """
    logger.info("Extracting child_age_distributions...")

    rel_map = {
        REL_BIO_CHILD: "biological_child",
        REL_ADOPTED_CHILD: "adopted_child",
        REL_STEPCHILD: "stepchild",
        REL_GRANDCHILD: "grandchild",
    }

    children = persons_df[
        (persons_df["RELSHIPP"].isin(rel_map.keys())) & (persons_df["AGEP"] < 18)
    ].copy()

    if children.empty:
        return pd.DataFrame(columns=["relationship", "age", "weight"])

    children["relationship"] = children["RELSHIPP"].map(rel_map)
    result = (
        children.groupby(["relationship", "AGEP"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"AGEP": "age", "PWGTP": "weight"})
    )
    return result


def extract_adult_child_ages(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract age distribution of adult children (18+) still in household.

    These are biological/adopted/step children aged 18+ who still live
    with their parents. Important for VITA dependent rules (full-time
    student under 24, permanently disabled, etc.).

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age, relationship, weight].
    """
    logger.info("Extracting adult_child_ages...")

    child_rels = {REL_BIO_CHILD, REL_ADOPTED_CHILD, REL_STEPCHILD}
    rel_map = {
        REL_BIO_CHILD: "biological_child",
        REL_ADOPTED_CHILD: "adopted_child",
        REL_STEPCHILD: "stepchild",
    }

    adult_children = persons_df[
        (persons_df["RELSHIPP"].isin(child_rels)) & (persons_df["AGEP"] >= 18)
    ].copy()

    if adult_children.empty:
        return pd.DataFrame(columns=["age", "relationship", "weight"])

    adult_children["relationship"] = adult_children["RELSHIPP"].map(rel_map)
    result = (
        adult_children.groupby(["AGEP", "relationship"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"AGEP": "age", "PWGTP": "weight"})
    )
    return result


def extract_stepchild_patterns(
    households_df: pd.DataFrame, persons_df: pd.DataFrame
) -> pd.DataFrame:
    """Extract stepchild frequency and household composition patterns.

    Args:
        households_df: Household-level PUMS records.
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [has_bio_children, num_stepchildren,
        num_bio_children, weight].
    """
    logger.info("Extracting stepchild_patterns...")

    records = []
    for serialno, group in persons_df.groupby("SERIALNO"):
        stepchildren = group[
            (group["RELSHIPP"] == REL_STEPCHILD) & (group["AGEP"] < 18)
        ]
        if stepchildren.empty:
            continue

        bio_children = group[
            (group["RELSHIPP"] == REL_BIO_CHILD) & (group["AGEP"] < 18)
        ]
        householder = group[group["RELSHIPP"] == REL_HOUSEHOLDER]
        weight = int(householder.iloc[0]["PWGTP"]) if not householder.empty else 1

        records.append({
            "has_bio_children": len(bio_children) > 0,
            "num_stepchildren": len(stepchildren),
            "num_bio_children": len(bio_children),
            "weight": weight,
        })

    if not records:
        return pd.DataFrame(
            columns=["has_bio_children", "num_stepchildren", "num_bio_children", "weight"]
        )

    result = (
        pd.DataFrame(records)
        .groupby(["has_bio_children", "num_stepchildren", "num_bio_children"])["weight"]
        .sum()
        .reset_index()
    )
    return result


def extract_multigenerational_patterns(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract multigenerational household structure patterns.

    Identifies households with 3+ generations (e.g., grandparent +
    parent + grandchild) and records their composition.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [pattern_detail, num_generations,
        household_size, weight].
    """
    logger.info("Extracting multigenerational_patterns...")

    records = []
    for serialno, group in persons_df.groupby("SERIALNO"):
        rels = set(group["RELSHIPP"].values)

        has_parent = REL_PARENT in rels
        has_grandchild = REL_GRANDCHILD in rels
        child_rels = {REL_BIO_CHILD, REL_ADOPTED_CHILD, REL_STEPCHILD}
        has_children = bool(rels & child_rels)

        # Must have indicators of 3+ generations
        if not (has_parent or (has_grandchild and has_children)):
            continue

        householder = group[group["RELSHIPP"] == REL_HOUSEHOLDER]
        weight = int(householder.iloc[0]["PWGTP"]) if not householder.empty else 1

        # Determine generation count and pattern detail
        num_generations = 2
        if has_parent and has_children:
            num_generations = 3
        if has_parent and has_grandchild:
            num_generations = 3

        detail_parts = []
        if has_parent:
            detail_parts.append("parent")
        if has_children:
            detail_parts.append("children")
        if has_grandchild:
            detail_parts.append("grandchild")
        pattern_detail = "+".join(detail_parts)

        records.append({
            "pattern_detail": pattern_detail,
            "num_generations": num_generations,
            "household_size": len(group),
            "weight": weight,
        })

    if not records:
        return pd.DataFrame(
            columns=["pattern_detail", "num_generations", "household_size", "weight"]
        )

    result = (
        pd.DataFrame(records)
        .groupby(["pattern_detail", "num_generations", "household_size"])["weight"]
        .sum()
        .reset_index()
    )
    return result


def extract_unmarried_partner_patterns(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract cohabiting couple demographic patterns.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [householder_sex, partner_sex,
        has_children, age_bracket, weight].
    """
    logger.info("Extracting unmarried_partner_patterns...")

    records = []
    for serialno, group in persons_df.groupby("SERIALNO"):
        partner = group[group["RELSHIPP"] == REL_UNMARRIED_PARTNER]
        if partner.empty:
            continue

        householder = group[group["RELSHIPP"] == REL_HOUSEHOLDER]
        if householder.empty:
            continue

        child_rels = {REL_BIO_CHILD, REL_ADOPTED_CHILD, REL_STEPCHILD}
        children = group[
            (group["RELSHIPP"].isin(child_rels)) & (group["AGEP"] < 18)
        ]

        hh_row = householder.iloc[0]
        pt_row = partner.iloc[0]

        hh_sex = "M" if int(hh_row["SEX"]) == 1 else "F"
        pt_sex = "M" if int(pt_row["SEX"]) == 1 else "F"
        age_bracket = _age_to_bracket(int(hh_row["AGEP"]), AGE_BRACKETS)

        records.append({
            "householder_sex": hh_sex,
            "partner_sex": pt_sex,
            "has_children": len(children) > 0,
            "age_bracket": age_bracket,
            "weight": int(hh_row["PWGTP"]),
        })

    if not records:
        return pd.DataFrame(
            columns=[
                "householder_sex", "partner_sex", "has_children",
                "age_bracket", "weight",
            ]
        )

    result = (
        pd.DataFrame(records)
        .groupby(["householder_sex", "partner_sex", "has_children", "age_bracket"])[
            "weight"
        ]
        .sum()
        .reset_index()
    )
    return result


def extract_race_distribution(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract overall race distribution (weighted).

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [race, weight, proportion].
    """
    logger.info("Extracting race_distribution...")

    persons_copy = persons_df.copy()
    persons_copy["race"] = persons_copy["RAC1P"].map(RACE_MAP).fillna("other")

    result = (
        persons_copy.groupby("race")["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )
    total = result["weight"].sum()
    result["proportion"] = result["weight"] / total if total > 0 else 0
    result = result.sort_values("weight", ascending=False).reset_index(drop=True)

    logger.info("  Found %d race categories", len(result))
    return result


def extract_race_by_age(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract race distribution by age bracket.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, race, weight, proportion].
    """
    logger.info("Extracting race_by_age...")

    persons_copy = persons_df.copy()
    persons_copy["race"] = persons_copy["RAC1P"].map(RACE_MAP).fillna("other")
    persons_copy["age_bracket"] = persons_copy["AGEP"].apply(
        lambda a: _age_to_bracket(a, AGE_BRACKETS)
    )

    result = (
        persons_copy.groupby(["age_bracket", "race"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    # Compute within-bracket proportions
    bracket_totals = result.groupby("age_bracket")["weight"].transform("sum")
    result["proportion"] = result["weight"] / bracket_totals
    result["proportion"] = result["proportion"].fillna(0)

    return result


def extract_hispanic_origin_by_age(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract Hispanic/Latino origin distribution by age bracket.

    PUMS HISP: 1 = Not Hispanic, 2-24 = specific Hispanic origins.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_bracket, is_hispanic, weight, proportion].
    """
    logger.info("Extracting hispanic_origin_by_age...")

    persons_copy = persons_df.copy()
    persons_copy["is_hispanic"] = persons_copy["HISP"] > 1
    persons_copy["age_bracket"] = persons_copy["AGEP"].apply(
        lambda a: _age_to_bracket(a, AGE_BRACKETS)
    )

    result = (
        persons_copy.groupby(["age_bracket", "is_hispanic"])["PWGTP"]
        .sum()
        .reset_index()
        .rename(columns={"PWGTP": "weight"})
    )

    bracket_totals = result.groupby("age_bracket")["weight"].transform("sum")
    result["proportion"] = result["weight"] / bracket_totals
    result["proportion"] = result["proportion"].fillna(0)

    return result


def extract_spousal_age_gaps(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract age difference distribution between householder and spouse.

    Positive gap = householder is older; negative = spouse is older.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [age_gap, weight].
    """
    logger.info("Extracting spousal_age_gaps...")

    records = []
    for serialno, group in persons_df.groupby("SERIALNO"):
        householder = group[group["RELSHIPP"] == REL_HOUSEHOLDER]
        spouse = group[group["RELSHIPP"] == REL_SPOUSE]

        if householder.empty or spouse.empty:
            continue

        hh_age = int(householder.iloc[0]["AGEP"])
        sp_age = int(spouse.iloc[0]["AGEP"])
        weight = int(householder.iloc[0]["PWGTP"])

        # Cap extreme gaps for cleaner distributions
        gap = max(min(hh_age - sp_age, 30), -30)

        records.append({"age_gap": gap, "weight": weight})

    if not records:
        return pd.DataFrame(columns=["age_gap", "weight"])

    result = (
        pd.DataFrame(records)
        .groupby("age_gap")["weight"]
        .sum()
        .reset_index()
        .sort_values("age_gap")
        .reset_index(drop=True)
    )
    return result


def extract_couple_sex_patterns(persons_df: pd.DataFrame) -> pd.DataFrame:
    """Extract same-sex vs opposite-sex couple distribution.

    Covers both married spouses and unmarried partners.

    Args:
        persons_df: Person-level PUMS records.

    Returns:
        DataFrame with columns: [couple_type, householder_sex, partner_sex,
        relationship, weight, proportion].
    """
    logger.info("Extracting couple_sex_patterns...")

    partner_rels = {REL_SPOUSE: "spouse", REL_UNMARRIED_PARTNER: "unmarried_partner"}

    records = []
    for serialno, group in persons_df.groupby("SERIALNO"):
        householder = group[group["RELSHIPP"] == REL_HOUSEHOLDER]
        if householder.empty:
            continue

        for rel_code, rel_label in partner_rels.items():
            partner = group[group["RELSHIPP"] == rel_code]
            if partner.empty:
                continue

            hh_sex = "M" if int(householder.iloc[0]["SEX"]) == 1 else "F"
            pt_sex = "M" if int(partner.iloc[0]["SEX"]) == 1 else "F"
            weight = int(householder.iloc[0]["PWGTP"])

            couple_type = "same_sex" if hh_sex == pt_sex else "opposite_sex"

            records.append({
                "couple_type": couple_type,
                "householder_sex": hh_sex,
                "partner_sex": pt_sex,
                "relationship": rel_label,
                "weight": weight,
            })

    if not records:
        return pd.DataFrame(
            columns=[
                "couple_type", "householder_sex", "partner_sex",
                "relationship", "weight", "proportion",
            ]
        )

    result = (
        pd.DataFrame(records)
        .groupby(
            ["couple_type", "householder_sex", "partner_sex", "relationship"]
        )["weight"]
        .sum()
        .reset_index()
    )
    total = result["weight"].sum()
    result["proportion"] = result["weight"] / total if total > 0 else 0

    return result


# =========================================================================
# Main extraction pipeline
# =========================================================================


def extract_all_part1(
    state: str,
    year: int,
    output_path: Optional[Path] = None,
) -> Path:
    """Run the full Part 1 extraction pipeline.

    Downloads PUMS data (if not cached), extracts all 12 distribution tables,
    and writes them to a SQLite database.

    Args:
        state: Two-letter state abbreviation.
        year: ACS 5-Year data year.
        output_path: Optional output SQLite path. Defaults to
            data/distributions_{state}_{year}.sqlite.

    Returns:
        Path to the created SQLite file.
    """
    state_lower = validate_inputs(state, year)

    if output_path is None:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        output_path = DATA_DIR / f"distributions_{state_lower}_{year}.sqlite"

    logger.info("=" * 60)
    logger.info("Part 1 Extraction: %s %d", state.upper(), year)
    logger.info("Output: %s", output_path)
    logger.info("=" * 60)

    # Step 1: Download PUMS data
    logger.info("Step 1/3: Downloading PUMS data...")
    household_zip, person_zip = download_pums_files(state, year)

    # Step 2: Load into DataFrames
    logger.info("Step 2/3: Loading PUMS data...")
    households_df, persons_df = load_pums_data(household_zip, person_zip)

    # Step 3: Extract all 12 tables
    logger.info("Step 3/3: Extracting distribution tables...")

    tables = {
        "household_patterns": extract_household_patterns(households_df, persons_df),
        "children_by_parent_age": extract_children_by_parent_age(persons_df),
        "child_age_distributions": extract_child_age_distributions(persons_df),
        "adult_child_ages": extract_adult_child_ages(persons_df),
        "stepchild_patterns": extract_stepchild_patterns(households_df, persons_df),
        "multigenerational_patterns": extract_multigenerational_patterns(persons_df),
        "unmarried_partner_patterns": extract_unmarried_partner_patterns(persons_df),
        "race_distribution": extract_race_distribution(persons_df),
        "race_by_age": extract_race_by_age(persons_df),
        "hispanic_origin_by_age": extract_hispanic_origin_by_age(persons_df),
        "spousal_age_gaps": extract_spousal_age_gaps(persons_df),
        "couple_sex_patterns": extract_couple_sex_patterns(persons_df),
    }

    # Write to SQLite
    engine = create_engine(f"sqlite:///{output_path}")
    for table_name, df in tables.items():
        df.to_sql(table_name, engine, if_exists="replace", index=False)
        logger.info("  Wrote %s: %d rows", table_name, len(df))

    engine.dispose()

    logger.info("=" * 60)
    logger.info("Extraction complete: %s", output_path)
    logger.info(
        "Tables: %d, Total size: %.1f KB",
        len(tables),
        output_path.stat().st_size / 1024,
    )
    logger.info("=" * 60)

    return output_path


def main() -> None:
    """CLI entry point for Part 1 extraction."""
    parser = argparse.ArgumentParser(
        description="Extract Part 1 distribution tables from PUMS data"
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
        output = extract_all_part1(args.state, args.year, args.output)
        print(f"\nSuccess: {output}")
    except Exception:
        logger.exception("Extraction failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
