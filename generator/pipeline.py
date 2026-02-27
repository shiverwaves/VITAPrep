"""
Household generation pipeline — orchestrates generation by VITA section.

Usage:
    generator = HouseholdGenerator("HI", 2022)
    household = generator.generate_part1()              # Demographics only
    household = generator.generate_part2(household)     # + Employment + Income (future)
    household = generator.generate_full(household)      # Everything (future)
"""

import logging
import uuid
from typing import Optional

import numpy as np

from .models import Household, PATTERN_METADATA
from .db import DistributionLoader
from .demographics import DemographicsGenerator
from .children import ChildGenerator
from .pii import PIIGenerator
from .sampler import weighted_sample, set_random_seed

logger = logging.getLogger(__name__)


class HouseholdGenerator:
    """Main entry point for household generation.

    Loads distribution tables and delegates to section-specific generators.
    Each ``generate_part*`` method populates additional fields on the
    Household incrementally so generators can be composed.
    """

    def __init__(
        self,
        state: str,
        year: int,
        connection_string: Optional[str] = None,
    ) -> None:
        """Initialize with distribution data for a state/year.

        Args:
            state: Two-letter state code (e.g., "HI").
            year: PUMS data year (e.g., 2022).
            connection_string: Database URL. If None, auto-detects
                SQLite in data/.
        """
        self.state = state.upper()
        self.year = year

        # Load distribution tables
        self.db = DistributionLoader(connection_string)
        self.distributions = self.db.load_part1_tables(self.state, self.year)

        # Initialize Part 1 generators
        self.demographics = DemographicsGenerator(self.distributions)
        self.children = ChildGenerator(self.distributions)
        self.pii = PIIGenerator(tax_year=self.year)

        logger.info("Initialized generator for %s (%d)", self.state, self.year)

    def _select_pattern(self, pattern: Optional[str] = None) -> Household:
        """Select a household pattern and create the initial Household.

        If *pattern* is provided, uses it directly. Otherwise samples
        from the ``household_patterns`` distribution table, falling
        back to a uniform random choice over ``PATTERN_METADATA`` keys.

        Args:
            pattern: Specific pattern name, or None to sample.

        Returns:
            A new Household with pattern and metadata fields set.
        """
        if pattern is not None:
            chosen = pattern
        else:
            hp_df = self.distributions.get("household_patterns")
            if hp_df is not None and len(hp_df) > 0:
                row = weighted_sample(hp_df, "weight").iloc[0]
                chosen = str(row["pattern"])
            else:
                chosen = str(np.random.choice(list(PATTERN_METADATA.keys())))

        metadata = PATTERN_METADATA.get(chosen, PATTERN_METADATA["other"])

        expected_adults = metadata.get("expected_adults")
        if isinstance(expected_adults, tuple):
            expected_adults = expected_adults[0]

        household = Household(
            household_id=str(uuid.uuid4()),
            state=self.state,
            year=self.year,
            pattern=chosen,
            expected_adults=expected_adults,
            expected_children_range=metadata.get("expected_children"),
            expected_complexity=metadata.get("complexity"),
        )

        logger.debug("Selected pattern: %s", chosen)
        return household

    def generate_part1(
        self,
        pattern: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Household:
        """Generate a household with Part 1 data: structure and demographics.

        This covers personal information for the VITA intake form —
        household composition, age, sex, race, and relationships.
        PII (names, SSNs, DOBs) is NOT applied here; call the PII
        generator separately when that stage is implemented.

        Args:
            pattern: Specific household pattern (e.g.,
                "married_couple_with_children"). If None, randomly
                samples from the distribution.
            seed: Random seed for reproducibility.

        Returns:
            Household with members populated (demographics only,
            no PII or income).
        """
        if seed is not None:
            set_random_seed(seed)

        # Stage 1: Select pattern
        household = self._select_pattern(pattern)

        # Stage 2: Generate adults
        adults = self.demographics.generate_adults(household)
        household.members = adults

        # Stage 3: Generate children
        children = self.children.generate_children(household)
        household.members.extend(children)

        logger.info(
            "Generated Part 1 household: pattern=%s, adults=%d, children=%d",
            household.pattern,
            len(household.get_adults()),
            len(household.get_children()),
        )
        return household

    def generate_with_pii(
        self,
        pattern: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Household:
        """Generate a household with demographics AND PII overlay.

        Runs :meth:`generate_part1` then applies the PII generator to
        populate names, SSNs, DOBs, addresses, and ID details.

        Args:
            pattern: Specific household pattern (e.g.,
                "married_couple_with_children"). If None, randomly
                samples from the distribution.
            seed: Random seed for reproducibility.

        Returns:
            Household with members fully populated (demographics + PII).
        """
        household = self.generate_part1(pattern=pattern, seed=seed)
        self.pii.overlay(household)

        logger.info(
            "Generated household with PII: pattern=%s, members=%d",
            household.pattern,
            len(household.members),
        )
        return household
