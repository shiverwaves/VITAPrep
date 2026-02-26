"""
PII generator — overlays synthetic personal identifying information onto households.

Takes a Household with demographics (age, sex, race) and populates:
- Legal names (Faker, culturally informed by race/hispanic_origin)
- SSNs (always 9XX-XX-XXXX test range)
- DOBs (calculated from age + tax year)
- Addresses (Faker, state-matched, consistent within household)
- ID document details (type, number, expiry)
- Phone and email

Name consistency rules:
- Spouse may have different last name (~30% maiden name probability)
- Biological children share parent's last name
- Stepchildren may have different last name
- Suffixes (Jr., III) when father/son share first name
"""

import logging
from typing import Dict

from .models import Household, Person, Address

logger = logging.getLogger(__name__)


class PIIGenerator:
    """
    Overlays synthetic PII onto a household's members.

    No distribution tables needed — uses Faker library.
    """

    def __init__(self, tax_year: int = 2024):
        self.tax_year = tax_year
        # TODO: Initialize Faker with appropriate locales

    def overlay(self, household: Household) -> Household:
        """
        Populate PII fields on all persons in a household. Modifies in place.

        Args:
            household: Household with demographics populated (from demographics.py)

        Returns:
            Same Household with PII fields filled in on each Person
        """
        # TODO: Implement
        # 1. Generate household address (shared by all members)
        # 2. For each member: generate name, SSN, DOB, ID details
        # 3. Apply family name consistency rules
        pass
