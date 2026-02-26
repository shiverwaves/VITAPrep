"""
Database connection and distribution table loading.

Loads PUMS/BLS distribution tables from SQLite (default) or PostgreSQL.
Auto-detects SQLite files in data/ directory if no connection string is provided.

Reference: HouseholdRNG/generator/database.py — simplify and add SQLite auto-detect.
"""

import os
import logging
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, text, inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


# Part 1 tables (personal information — 12 tables)
PART1_TABLES = [
    "household_patterns",
    "children_by_parent_age",
    "child_age_distributions",
    "adult_child_ages",
    "stepchild_patterns",
    "multigenerational_patterns",
    "unmarried_partner_patterns",
    "race_distribution",
    "race_by_age",
    "hispanic_origin_by_age",
    "spousal_age_gaps",
    "couple_sex_patterns",
]

# Part 2 tables (income/employment — 14 tables)
PART2_TABLES = [
    "employment_by_age",
    "education_by_age",
    "disability_by_age",
    "social_security",
    "retirement_income",
    "interest_and_dividend_income",
    "other_income_by_employment_status",
    "public_assistance_income",
    "homeownership_rates",
    "property_taxes",
    "mortgage_interest",
    "bls_occupation_wages",
    "education_occupation_probabilities",
    "age_income_adjustments",
    "occupation_self_employment_probability",
]


class DistributionLoader:
    """
    Loads distribution tables from SQLite or PostgreSQL.

    Usage:
        # Auto-detect SQLite in data/ directory
        loader = DistributionLoader()

        # Explicit SQLite path
        loader = DistributionLoader("sqlite:///data/distributions_hi_2022.sqlite")

        # PostgreSQL
        loader = DistributionLoader("postgresql://user:pass@host/db")
    """

    def __init__(self, connection_string: Optional[str] = None):
        # TODO: Implement
        # 1. If connection_string provided, use it
        # 2. If DATABASE_URL env var set, use that
        # 3. Otherwise, scan data/ for .sqlite files
        # 4. Raise ValueError with helpful message if nothing found
        pass

    def load_part1_tables(self, state: str, year: int) -> Dict[str, pd.DataFrame]:
        """Load only Part 1 distribution tables."""
        # TODO: Implement
        pass

    def load_part2_tables(self, state: str, year: int) -> Dict[str, pd.DataFrame]:
        """Load only Part 2 distribution tables."""
        # TODO: Implement
        pass

    def load_all_tables(self, state: str, year: int) -> Dict[str, pd.DataFrame]:
        """Load all distribution tables."""
        # TODO: Implement
        pass

    def list_available_states(self) -> Dict[str, List[int]]:
        """Scan database for available state/year combinations."""
        # TODO: Implement
        pass
