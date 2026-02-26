"""
Household generation pipeline — orchestrates generation by VITA section.

Usage:
    generator = HouseholdGenerator("HI", 2022)
    household = generator.generate_part1()              # Demographics + PII
    household = generator.generate_part2(household)     # + Employment + Income (future)
    household = generator.generate_full(household)      # Everything (future)
"""

import logging
from typing import Optional

from .models import Household
from .db import DistributionLoader
from .demographics import DemographicsGenerator
from .children import ChildGenerator
from .pii import PIIGenerator

logger = logging.getLogger(__name__)


class HouseholdGenerator:
    """
    Main entry point for household generation.

    Loads distribution tables and delegates to section-specific generators.
    """

    def __init__(self, state: str, year: int, connection_string: Optional[str] = None):
        """
        Args:
            state: Two-letter state code (e.g., "HI")
            year: PUMS data year (e.g., 2022)
            connection_string: Database URL. If None, auto-detects SQLite in data/.
        """
        self.state = state.upper()
        self.year = year

        # Load distribution tables
        self.db = DistributionLoader(connection_string)
        self.distributions = self.db.load_part1_tables(self.state, self.year)

        # Initialize generators
        self.demographics = DemographicsGenerator(self.distributions)
        self.children = ChildGenerator(self.distributions)
        self.pii = PIIGenerator(tax_year=self.year)

        logger.info(f"Initialized generator for {self.state} ({self.year})")

    def generate_part1(
        self,
        pattern: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Household:
        """
        Generate a household with Part 1 data: structure, demographics, and PII.

        Args:
            pattern: Specific household pattern (e.g., "married_couple_with_children").
                     If None, randomly samples from distribution.
            seed: Random seed for reproducibility.

        Returns:
            Household with members populated (demographics + PII, no income/expenses)
        """
        # TODO: Implement
        # 1. Select pattern (Stage 1)
        # 2. Generate adults (demographics.py)
        # 3. Generate children (children.py)
        # 4. Overlay PII (pii.py)
        pass
