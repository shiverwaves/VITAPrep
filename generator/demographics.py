"""
Demographics generator — Part 1 of VITA intake.

Generates adult household members with demographic attributes:
age, sex, race, hispanic origin, and household relationships.

Does NOT handle employment, education, occupation, or disability.
Those move to employment.py for Part 2.

Reference: HouseholdRNG/generator/adult_generator.py
Port the demographic-related functions, leave employment-related ones for employment.py.
"""

import logging
from typing import Dict, List, Optional

import pandas as pd

from .models import Household, Person, RelationshipType, PATTERN_METADATA

logger = logging.getLogger(__name__)


class DemographicsGenerator:
    """
    Generates adult household members with demographics only.

    Required distribution tables:
    - household_patterns (for pattern selection)
    - race_distribution, race_by_age, hispanic_origin_by_age
    - spousal_age_gaps, couple_sex_patterns

    Port from HouseholdRNG/generator/adult_generator.py:
    - generate_adults()
    - _determine_adult_count()
    - _assign_relationships()
    - _generate_single_adult() (without employment/education)
    - _sample_age() and all age helpers
    - _sample_sex()
    - _sample_race()
    - _sample_hispanic_origin()

    Do NOT port:
    - _sample_employment_status() → goes to employment.py
    - _sample_education() → goes to employment.py
    - _sample_disability() → goes to employment.py
    - _sample_occupation() → goes to employment.py
    """

    def __init__(self, distributions: Dict[str, pd.DataFrame]):
        self.distributions = distributions
        # TODO: Validate required tables are present

    def generate_adults(self, household: Household) -> List[Person]:
        """
        Generate adult members for a household based on its pattern.

        Args:
            household: Household with pattern set (from pipeline Stage 1)

        Returns:
            List of Person objects with demographics populated
            (age, sex, race, hispanic_origin, relationship)
        """
        # TODO: Implement — port from HouseholdRNG/generator/adult_generator.py
        pass
