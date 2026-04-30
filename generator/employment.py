"""
Employment generator — Part 2 of VITA intake.

Populates employment-related fields on adult Person objects:
employment_status, education, occupation_code, occupation_title,
and has_disability.  Reads from Part 2 distribution tables extracted
by extraction/extract_part2.py.

Called after demographics (Sprint 3) and PII (Sprint 4) have run.
"""

import logging
from typing import Dict, List, Optional

import numpy as np
import pandas as pd

from .models import Household, Person
from .sampler import weighted_sample

logger = logging.getLogger(__name__)

# Age bracket helper (mirrors extract_part2._age_to_bracket)
_AGE_BRACKETS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]


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


class EmploymentGenerator:
    """Assigns employment attributes to adult household members.

    Required distribution tables:
        employment_by_age, education_by_age, disability_by_age

    Optional tables (used for occupation assignment):
        education_occupation_probabilities, occupation_wages
    """

    _REQUIRED_TABLES = [
        "employment_by_age",
        "education_by_age",
        "disability_by_age",
    ]

    _OPTIONAL_TABLES = [
        "education_occupation_probabilities",
        "occupation_wages",
    ]

    # Fallback distributions when tables are missing
    _DEFAULT_EMPLOYMENT = {"employed": 0.60, "unemployed": 0.05, "not_in_labor_force": 0.35}
    _DEFAULT_EDUCATION = {
        "less_than_hs": 0.10, "high_school": 0.27, "some_college": 0.20,
        "associates": 0.08, "bachelors": 0.22, "masters": 0.09,
        "professional": 0.02, "doctorate": 0.02,
    }
    _DEFAULT_DISABILITY_RATE = 0.13

    # Occupation group → human-readable title (fallback when no table)
    _OCCUPATION_TITLES = {
        "management": "Management",
        "business_financial": "Business and Financial Operations",
        "computer_math": "Computer and Mathematical",
        "architecture_engineering": "Architecture and Engineering",
        "science": "Life, Physical, and Social Science",
        "community_social": "Community and Social Service",
        "legal": "Legal",
        "education": "Education, Training, and Library",
        "arts_media": "Arts, Design, Entertainment, Sports, and Media",
        "healthcare_practitioner": "Healthcare Practitioners and Technical",
        "healthcare_support": "Healthcare Support",
        "protective_service": "Protective Service",
        "food_service": "Food Preparation and Serving",
        "maintenance_grounds": "Building and Grounds Maintenance",
        "personal_care": "Personal Care and Service",
        "sales": "Sales and Related",
        "office_admin": "Office and Administrative Support",
        "farming": "Farming, Fishing, and Forestry",
        "construction": "Construction and Extraction",
        "repair": "Installation, Maintenance, and Repair",
        "production": "Production",
        "transportation": "Transportation and Material Moving",
        "military": "Military Specific",
    }

    def __init__(self, distributions: Dict[str, pd.DataFrame]) -> None:
        self.distributions = distributions
        self._validate_tables()

    def _validate_tables(self) -> None:
        missing = [t for t in self._REQUIRED_TABLES if t not in self.distributions]
        if missing:
            logger.warning("Missing employment tables (will use defaults): %s", missing)

        missing_opt = [t for t in self._OPTIONAL_TABLES if t not in self.distributions]
        if missing_opt:
            logger.debug("Missing optional employment tables: %s", missing_opt)

    def overlay(self, household: Household) -> None:
        """Populate employment fields on all adult members in place.

        Args:
            household: Household with demographics already populated.
        """
        for person in household.members:
            if not person.is_adult():
                self._assign_child_defaults(person)
                continue

            person.employment_status = self._sample_employment_status(person)
            person.education = self._sample_education(person)
            person.has_disability = self._sample_disability(person)

            if person.employment_status == "employed":
                occ_group, occ_title = self._sample_occupation(person)
                person.occupation_code = occ_group
                person.occupation_title = occ_title
            else:
                person.occupation_code = None
                person.occupation_title = None

        employed = [p for p in household.members if p.employment_status == "employed"]
        logger.info(
            "Employment overlay: %d/%d adults employed",
            len(employed),
            len(household.get_adults()),
        )

    def _assign_child_defaults(self, person: Person) -> None:
        person.employment_status = "not_in_labor_force"
        person.education = "less_than_hs"
        person.occupation_code = None
        person.occupation_title = None

    def _sample_employment_status(self, person: Person) -> str:
        """Sample employment status from age-specific distribution."""
        bracket = _age_to_bracket(person.age)
        table = self.distributions.get("employment_by_age")

        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                sampled = weighted_sample(rows, "weight")
                return str(sampled.iloc[0]["employment_status"])

        # Fallback: age-adjusted defaults
        if person.age >= 67:
            probs = {"employed": 0.20, "unemployed": 0.02, "not_in_labor_force": 0.78}
        elif person.age >= 62:
            probs = {"employed": 0.45, "unemployed": 0.03, "not_in_labor_force": 0.52}
        elif person.age <= 19:
            probs = {"employed": 0.30, "unemployed": 0.08, "not_in_labor_force": 0.62}
        else:
            probs = self._DEFAULT_EMPLOYMENT

        statuses = list(probs.keys())
        weights = list(probs.values())
        return str(np.random.choice(statuses, p=weights))

    def _sample_education(self, person: Person) -> str:
        """Sample education level from age-specific distribution."""
        bracket = _age_to_bracket(person.age)
        table = self.distributions.get("education_by_age")

        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                sampled = weighted_sample(rows, "weight")
                return str(sampled.iloc[0]["education_level"])

        # Fallback: age-adjusted
        if person.age <= 19:
            return str(np.random.choice(
                ["less_than_hs", "high_school"],
                p=[0.6, 0.4],
            ))
        elif person.age <= 24:
            return str(np.random.choice(
                ["high_school", "some_college", "associates", "bachelors"],
                p=[0.30, 0.40, 0.15, 0.15],
            ))

        levels = list(self._DEFAULT_EDUCATION.keys())
        weights = list(self._DEFAULT_EDUCATION.values())
        return str(np.random.choice(levels, p=weights))

    def _sample_disability(self, person: Person) -> bool:
        """Sample disability status from age-specific distribution."""
        bracket = _age_to_bracket(person.age)
        table = self.distributions.get("disability_by_age")

        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            disabled_rows = rows[rows["has_disability"] == 1]
            if not rows.empty and not disabled_rows.empty:
                rate = float(disabled_rows["proportion"].iloc[0])
                return bool(np.random.random() < rate)

        # Fallback: age-adjusted rate
        if person.age >= 75:
            rate = 0.35
        elif person.age >= 65:
            rate = 0.25
        elif person.age >= 55:
            rate = 0.18
        else:
            rate = self._DEFAULT_DISABILITY_RATE
        return bool(np.random.random() < rate)

    def _sample_occupation(self, person: Person) -> tuple:
        """Sample occupation group for an employed person.

        Uses education_occupation_probabilities to find likely occupations
        given the person's education level.

        Returns:
            Tuple of (occupation_group, occupation_title).
        """
        table = self.distributions.get("education_occupation_probabilities")

        if table is not None and not table.empty:
            rows = table[table["education_level"] == person.education]
            if not rows.empty:
                sampled = weighted_sample(rows, "weight")
                group = str(sampled.iloc[0]["occupation_group"])
                title = self._OCCUPATION_TITLES.get(group, group.replace("_", " ").title())
                return group, title

        # Fallback: education-weighted random occupation
        group = self._fallback_occupation(person.education)
        title = self._OCCUPATION_TITLES.get(group, group.replace("_", " ").title())
        return group, title

    def _fallback_occupation(self, education: str) -> str:
        """Pick a plausible occupation group based on education level."""
        if education in ("doctorate", "professional"):
            options = ["healthcare_practitioner", "legal", "science", "education", "management"]
        elif education == "masters":
            options = ["management", "education", "healthcare_practitioner", "business_financial", "computer_math"]
        elif education == "bachelors":
            options = ["management", "business_financial", "computer_math", "sales", "education", "office_admin"]
        elif education in ("associates", "some_college"):
            options = ["office_admin", "sales", "healthcare_support", "production", "construction", "personal_care"]
        elif education == "high_school":
            options = ["sales", "office_admin", "food_service", "transportation", "production", "construction"]
        else:
            options = ["food_service", "construction", "maintenance_grounds", "transportation", "farming", "production"]
        return str(np.random.choice(options))
