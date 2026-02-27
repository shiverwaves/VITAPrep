#!/usr/bin/env python3
"""Generate a sample household with PII and print as JSON.

This is the script invoked by the Test Generators workflow to show
what the pipeline actually produces at runtime.

Usage:
    python scripts/generate_sample.py                          # random pattern
    python scripts/generate_sample.py --pattern single_parent  # specific pattern
    python scripts/generate_sample.py --seed 42 --format json  # reproducible
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.models import Household, PATTERN_METADATA
from generator.demographics import DemographicsGenerator
from generator.children import ChildGenerator
from generator.pii import PIIGenerator
from generator.sampler import set_random_seed


logger = logging.getLogger(__name__)


# Lightweight in-memory distribution tables so the script works
# without the real SQLite database (same tables used by the test suite).
def _build_in_memory_distributions():
    """Build minimal distribution tables for standalone generation."""
    import pandas as pd

    return {
        "household_patterns": pd.DataFrame([
            {"pattern": "married_couple_with_children", "weight": 30},
            {"pattern": "single_parent", "weight": 15},
            {"pattern": "married_couple_no_children", "weight": 20},
            {"pattern": "single_adult", "weight": 15},
            {"pattern": "blended_family", "weight": 5},
            {"pattern": "multigenerational", "weight": 5},
            {"pattern": "unmarried_partners", "weight": 5},
            {"pattern": "other", "weight": 5},
        ]),
        "race_by_age": pd.DataFrame([
            {"age_bracket": "18-24", "race": "white", "weight": 30},
            {"age_bracket": "18-24", "race": "asian", "weight": 40},
            {"age_bracket": "18-24", "race": "black", "weight": 10},
            {"age_bracket": "18-24", "race": "native_hawaiian_pacific_islander", "weight": 20},
            {"age_bracket": "25-34", "race": "asian", "weight": 40},
            {"age_bracket": "25-34", "race": "white", "weight": 30},
            {"age_bracket": "25-34", "race": "black", "weight": 10},
            {"age_bracket": "25-34", "race": "native_hawaiian_pacific_islander", "weight": 20},
            {"age_bracket": "35-44", "race": "asian", "weight": 35},
            {"age_bracket": "35-44", "race": "white", "weight": 30},
            {"age_bracket": "35-44", "race": "black", "weight": 15},
            {"age_bracket": "35-44", "race": "native_hawaiian_pacific_islander", "weight": 20},
            {"age_bracket": "45-54", "race": "white", "weight": 35},
            {"age_bracket": "45-54", "race": "asian", "weight": 35},
            {"age_bracket": "45-54", "race": "black", "weight": 10},
            {"age_bracket": "45-54", "race": "native_hawaiian_pacific_islander", "weight": 20},
            {"age_bracket": "55-64", "race": "white", "weight": 40},
            {"age_bracket": "55-64", "race": "asian", "weight": 35},
            {"age_bracket": "55-64", "race": "black", "weight": 10},
            {"age_bracket": "55-64", "race": "native_hawaiian_pacific_islander", "weight": 15},
            {"age_bracket": "65+", "race": "white", "weight": 45},
            {"age_bracket": "65+", "race": "asian", "weight": 35},
            {"age_bracket": "65+", "race": "black", "weight": 10},
            {"age_bracket": "65+", "race": "native_hawaiian_pacific_islander", "weight": 10},
        ]),
        "race_distribution": pd.DataFrame([
            {"race": "asian", "weight": 380},
            {"race": "white", "weight": 250},
            {"race": "native_hawaiian_pacific_islander", "weight": 200},
            {"race": "two_or_more", "weight": 100},
            {"race": "black", "weight": 40},
            {"race": "other", "weight": 30},
        ]),
        "hispanic_origin_by_age": pd.DataFrame([
            {"age_bracket": "18-24", "is_hispanic": 0, "weight": 85},
            {"age_bracket": "18-24", "is_hispanic": 1, "weight": 15},
            {"age_bracket": "25-34", "is_hispanic": 0, "weight": 87},
            {"age_bracket": "25-34", "is_hispanic": 1, "weight": 13},
            {"age_bracket": "35-44", "is_hispanic": 0, "weight": 88},
            {"age_bracket": "35-44", "is_hispanic": 1, "weight": 12},
            {"age_bracket": "45-54", "is_hispanic": 0, "weight": 90},
            {"age_bracket": "45-54", "is_hispanic": 1, "weight": 10},
            {"age_bracket": "55-64", "is_hispanic": 0, "weight": 92},
            {"age_bracket": "55-64", "is_hispanic": 1, "weight": 8},
            {"age_bracket": "65+", "is_hispanic": 0, "weight": 94},
            {"age_bracket": "65+", "is_hispanic": 1, "weight": 6},
        ]),
        "spousal_age_gaps": pd.DataFrame([
            {"age_gap": 0, "weight": 25},
            {"age_gap": 1, "weight": 20},
            {"age_gap": 2, "weight": 15},
            {"age_gap": -1, "weight": 15},
            {"age_gap": 3, "weight": 10},
            {"age_gap": -2, "weight": 8},
            {"age_gap": 5, "weight": 4},
            {"age_gap": -5, "weight": 3},
        ]),
        "couple_sex_patterns": pd.DataFrame([
            {"relationship": "spouse", "householder_sex": "M", "partner_sex": "F", "weight": 48},
            {"relationship": "spouse", "householder_sex": "F", "partner_sex": "M", "weight": 48},
            {"relationship": "spouse", "householder_sex": "M", "partner_sex": "M", "weight": 2},
            {"relationship": "spouse", "householder_sex": "F", "partner_sex": "F", "weight": 2},
            {"relationship": "unmarried_partner", "householder_sex": "M", "partner_sex": "F", "weight": 45},
            {"relationship": "unmarried_partner", "householder_sex": "F", "partner_sex": "M", "weight": 45},
            {"relationship": "unmarried_partner", "householder_sex": "M", "partner_sex": "M", "weight": 5},
            {"relationship": "unmarried_partner", "householder_sex": "F", "partner_sex": "F", "weight": 5},
        ]),
        "children_by_parent_age": pd.DataFrame([
            {"parent_age_bracket": "18-24", "num_children": 1, "weight": 70},
            {"parent_age_bracket": "18-24", "num_children": 2, "weight": 30},
            {"parent_age_bracket": "25-29", "num_children": 1, "weight": 50},
            {"parent_age_bracket": "25-29", "num_children": 2, "weight": 35},
            {"parent_age_bracket": "25-29", "num_children": 3, "weight": 15},
            {"parent_age_bracket": "30-34", "num_children": 1, "weight": 30},
            {"parent_age_bracket": "30-34", "num_children": 2, "weight": 40},
            {"parent_age_bracket": "30-34", "num_children": 3, "weight": 20},
            {"parent_age_bracket": "30-34", "num_children": 4, "weight": 10},
            {"parent_age_bracket": "35-39", "num_children": 1, "weight": 25},
            {"parent_age_bracket": "35-39", "num_children": 2, "weight": 35},
            {"parent_age_bracket": "35-39", "num_children": 3, "weight": 25},
            {"parent_age_bracket": "35-39", "num_children": 4, "weight": 15},
            {"parent_age_bracket": "40-44", "num_children": 1, "weight": 30},
            {"parent_age_bracket": "40-44", "num_children": 2, "weight": 35},
            {"parent_age_bracket": "40-44", "num_children": 3, "weight": 25},
            {"parent_age_bracket": "40-44", "num_children": 4, "weight": 10},
            {"parent_age_bracket": "45-54", "num_children": 1, "weight": 40},
            {"parent_age_bracket": "45-54", "num_children": 2, "weight": 35},
            {"parent_age_bracket": "45-54", "num_children": 3, "weight": 25},
        ]),
        "child_age_distributions": pd.DataFrame([
            {"relationship": "biological_child", "age": a, "weight": max(1, 17 - a)}
            for a in range(18)
        ] + [
            {"relationship": "stepchild", "age": a, "weight": max(1, 17 - a + 3)}
            for a in range(18)
        ] + [
            {"relationship": "grandchild", "age": a, "weight": max(1, 15 - a)}
            for a in range(16)
        ]),
        "stepchild_patterns": pd.DataFrame([
            {"num_stepchildren": 1, "weight": 60},
            {"num_stepchildren": 2, "weight": 30},
            {"num_stepchildren": 3, "weight": 10},
        ]),
        "multigenerational_patterns": pd.DataFrame([
            {"num_generations": 3, "weight": 70},
            {"num_generations": 2, "weight": 30},
        ]),
    }


def generate_household(pattern=None, seed=None):
    """Generate a single household with demographics + PII.

    Args:
        pattern: Household pattern name, or None for random.
        seed: Random seed for reproducibility.

    Returns:
        Household with all fields populated.
    """
    import numpy as np
    from generator.sampler import weighted_sample

    if seed is not None:
        set_random_seed(seed)

    distributions = _build_in_memory_distributions()

    # Select pattern
    if pattern is None:
        hp_df = distributions["household_patterns"]
        row = weighted_sample(hp_df, "weight").iloc[0]
        pattern = str(row["pattern"])

    # Build household
    import uuid
    metadata = PATTERN_METADATA.get(pattern, PATTERN_METADATA["other"])
    expected_adults = metadata.get("expected_adults")
    if isinstance(expected_adults, tuple):
        expected_adults = expected_adults[0]

    household = Household(
        household_id=str(uuid.uuid4()),
        state="HI",
        year=2022,
        pattern=pattern,
        expected_adults=expected_adults,
        expected_children_range=metadata.get("expected_children"),
        expected_complexity=metadata.get("complexity"),
    )

    # Demographics
    demo_gen = DemographicsGenerator(distributions)
    adults = demo_gen.generate_adults(household)
    household.members = adults

    child_gen = ChildGenerator(distributions)
    children = child_gen.generate_children(household)
    household.members.extend(children)

    # PII overlay
    pii_gen = PIIGenerator(tax_year=2024)
    pii_gen.overlay(household)

    return household


def main():
    parser = argparse.ArgumentParser(
        description="Generate a sample household with PII"
    )
    parser.add_argument(
        "--pattern",
        choices=list(PATTERN_METADATA.keys()),
        default=None,
        help="Household pattern (default: random)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    household = generate_household(pattern=args.pattern, seed=args.seed)
    data = household.to_dict()

    if args.format == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Pattern: {data['pattern']}")
        print(f"Adults: {data['adult_count']}, Children: {data['child_count']}")
        print(f"Filing status: {data['filing_status']}")
        print(f"Address: {household.address.one_line()}")
        print()
        for i, m in enumerate(data["members"], 1):
            name = f"{m['legal_first_name']} {m['legal_last_name']}"
            if m.get("suffix"):
                name += f" {m['suffix']}"
            print(f"  {i}. {name} ({m['relationship']}, {m['age']}{m['sex']}) SSN: {m['ssn']} DOB: {m['dob']}")


if __name__ == "__main__":
    main()
