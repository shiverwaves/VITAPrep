"""
Child generator — Part 1 of VITA intake.

Generates child household members based on parent demographics and PUMS distributions.

Reference: HouseholdRNG/generator/child_generator.py — port mostly as-is.

Required distribution tables:
- children_by_parent_age
- child_age_distributions
- adult_child_ages
- stepchild_patterns
"""

import logging
from typing import Dict, List

import pandas as pd

from .models import Household, Person

logger = logging.getLogger(__name__)


class ChildGenerator:
    """
    Generates child members for a household.

    Port from HouseholdRNG/generator/child_generator.py.
    This module maps cleanly to VITA Part 1 and needs minimal changes.
    """

    def __init__(self, distributions: Dict[str, pd.DataFrame]):
        self.distributions = distributions

    def generate_children(self, household: Household) -> List[Person]:
        """
        Generate child members based on household pattern and parent demographics.

        Args:
            household: Household with adult members already populated

        Returns:
            List of child Person objects (age, sex, race, relationship, months_in_home)
        """
        # TODO: Implement — port from HouseholdRNG/generator/child_generator.py
        pass
