"""
Database connection and distribution table loading.

Loads PUMS/BLS distribution tables from SQLite (default) or PostgreSQL.
Auto-detects SQLite files in data/ directory if no connection string is provided.

Reference: HouseholdRNG/generator/database.py — simplify and add SQLite auto-detect.
"""

import os
import logging
import re
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from sqlalchemy import create_engine, inspect
from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Project root (one level up from generator/)
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = PROJECT_ROOT / "data"

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
    """Loads distribution tables from SQLite or PostgreSQL.

    Connection resolution order:
        1. Explicit connection_string parameter
        2. DATABASE_URL environment variable
        3. Auto-detect SQLite files in data/ directory

    Usage:
        # Auto-detect SQLite in data/ directory
        loader = DistributionLoader()

        # Explicit SQLite path
        loader = DistributionLoader("sqlite:///data/distributions_hi_2022.sqlite")

        # PostgreSQL
        loader = DistributionLoader("postgresql://user:pass@host/db")
    """

    def __init__(self, connection_string: Optional[str] = None) -> None:
        """Initialize the distribution loader.

        Args:
            connection_string: SQLAlchemy connection string. If None,
                falls back to DATABASE_URL env var, then auto-detect
                in data/ directory.

        Raises:
            ValueError: If an explicit connection string is provided
                but the engine cannot be created.
        """
        self._connection_string: Optional[str] = (
            connection_string or os.environ.get("DATABASE_URL")
        )
        self._data_dir: Path = DATA_DIR
        self._engines: Dict[str, Engine] = {}

        if self._connection_string:
            self._engines["explicit"] = create_engine(self._connection_string)
            logger.info(
                "DistributionLoader initialized with explicit connection"
            )

    def _get_engine(
        self,
        state: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Engine:
        """Get a SQLAlchemy engine, auto-detecting SQLite file if needed.

        Args:
            state: Two-letter state abbreviation (required for auto-detect).
            year: ACS data year (required for auto-detect).

        Returns:
            SQLAlchemy Engine connected to the distribution database.

        Raises:
            FileNotFoundError: If no matching SQLite file is found.
            ValueError: If state/year not provided and no explicit connection.
        """
        if "explicit" in self._engines:
            return self._engines["explicit"]

        if not state or not year:
            raise ValueError(
                "state and year are required when no connection string "
                "is provided. Pass them to load_*_tables() or provide "
                "a connection string to DistributionLoader()."
            )

        key = f"{state.lower()}_{year}"
        if key in self._engines:
            return self._engines[key]

        path = self._data_dir / f"distributions_{key}.sqlite"
        if not path.exists():
            # Try finding any file for this state (different year)
            candidates = sorted(
                self._data_dir.glob(f"distributions_{state.lower()}_*.sqlite")
            )
            if candidates:
                path = candidates[-1]  # Use most recent
                logger.info(
                    "Requested %s %d, using %s", state.upper(), year, path.name
                )
            else:
                raise FileNotFoundError(
                    f"No distribution database found for {state.upper()} "
                    f"{year}.\nExpected: {path}\n"
                    f"Run: python -m extraction.extract_part1 "
                    f"--state {state.upper()} --year {year}"
                )

        engine = create_engine(f"sqlite:///{path}")
        self._engines[key] = engine
        logger.info("Connected to %s", path.name)
        return engine

    def _load_tables(
        self,
        table_names: List[str],
        state: Optional[str] = None,
        year: Optional[int] = None,
    ) -> Dict[str, pd.DataFrame]:
        """Load specific tables as DataFrames.

        Args:
            table_names: List of table names to load.
            state: Two-letter state abbreviation.
            year: ACS data year.

        Returns:
            Dict mapping table name to DataFrame. Missing tables are
            logged as warnings and omitted from the result.
        """
        engine = self._get_engine(state, year)
        available = set(inspect(engine).get_table_names())
        result: Dict[str, pd.DataFrame] = {}

        for name in table_names:
            if name in available:
                result[name] = pd.read_sql_table(name, engine)
                logger.debug("Loaded %s: %d rows", name, len(result[name]))
            else:
                logger.warning(
                    "Table '%s' not found in database (available: %s)",
                    name,
                    ", ".join(sorted(available)),
                )

        loaded = len(result)
        expected = len(table_names)
        if loaded < expected:
            logger.warning(
                "Loaded %d/%d tables (%d missing)",
                loaded,
                expected,
                expected - loaded,
            )
        else:
            logger.info("Loaded all %d tables", loaded)

        return result

    def load_part1_tables(
        self, state: str, year: int
    ) -> Dict[str, pd.DataFrame]:
        """Load only Part 1 distribution tables (12 tables).

        These cover personal information: household patterns, demographics,
        race, relationships, and couple composition.

        Args:
            state: Two-letter state abbreviation.
            year: ACS data year.

        Returns:
            Dict mapping table name to DataFrame.
        """
        logger.info("Loading Part 1 tables for %s %d...", state.upper(), year)
        return self._load_tables(PART1_TABLES, state, year)

    def load_part2_tables(
        self, state: str, year: int
    ) -> Dict[str, pd.DataFrame]:
        """Load only Part 2 distribution tables (14 tables).

        These cover income and employment: occupation, wages, benefits,
        homeownership, and tax-related items.

        Args:
            state: Two-letter state abbreviation.
            year: ACS data year.

        Returns:
            Dict mapping table name to DataFrame.
        """
        logger.info("Loading Part 2 tables for %s %d...", state.upper(), year)
        return self._load_tables(PART2_TABLES, state, year)

    def load_all_tables(
        self, state: str, year: int
    ) -> Dict[str, pd.DataFrame]:
        """Load all distribution tables (Part 1 + Part 2).

        Args:
            state: Two-letter state abbreviation.
            year: ACS data year.

        Returns:
            Dict mapping table name to DataFrame.
        """
        logger.info(
            "Loading all distribution tables for %s %d...",
            state.upper(),
            year,
        )
        return self._load_tables(PART1_TABLES + PART2_TABLES, state, year)

    def list_available_states(self) -> Dict[str, List[int]]:
        """Scan for available state/year combinations.

        For SQLite auto-detect mode, scans the data/ directory for
        distribution files. For explicit connections, inspects the
        connected database.

        Returns:
            Dict mapping state abbreviation (uppercase) to list of
            available years, e.g. {"HI": [2022], "CA": [2021, 2022]}.
        """
        result: Dict[str, List[int]] = {}

        if "explicit" in self._engines:
            # Try to parse state/year from the connection string filename
            if self._connection_string and "sqlite" in self._connection_string:
                match = re.search(
                    r"distributions_([a-z]{2})_(\d{4})",
                    self._connection_string,
                )
                if match:
                    state = match.group(1).upper()
                    year = int(match.group(2))
                    result[state] = [year]
            # For PostgreSQL or unrecognized SQLite, check if tables exist
            if not result:
                engine = self._engines["explicit"]
                tables = inspect(engine).get_table_names()
                if tables:
                    result["UNKNOWN"] = [0]
            return result

        # Auto-detect: scan data/ directory
        if not self._data_dir.exists():
            return result

        pattern = re.compile(r"distributions_([a-z]{2})_(\d{4})\.sqlite")
        for path in sorted(self._data_dir.glob("distributions_*.sqlite")):
            match = pattern.match(path.name)
            if match:
                state = match.group(1).upper()
                year = int(match.group(2))
                if state not in result:
                    result[state] = []
                result[state].append(year)

        # Sort years for each state
        for state in result:
            result[state].sort()

        if result:
            logger.info("Available distributions: %s", result)
        else:
            logger.warning(
                "No distribution databases found in %s", self._data_dir
            )

        return result

    def close(self) -> None:
        """Dispose all cached engines."""
        for key, engine in self._engines.items():
            engine.dispose()
            logger.debug("Disposed engine: %s", key)
        self._engines.clear()

    def __del__(self) -> None:
        self.close()
