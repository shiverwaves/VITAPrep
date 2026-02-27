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
import random
from datetime import date, timedelta
from typing import Dict, List, Optional, Set

from faker import Faker

from .models import Address, Household, Person, RelationshipType

logger = logging.getLogger(__name__)

# Faker locale hints keyed by race / hispanic_origin.  We use these to
# bias first-name pools toward culturally plausible names while keeping
# the generation simple (Faker doesn't have per-race providers, but
# locale switching gives a reasonable approximation).
_LOCALE_MAP: Dict[str, str] = {
    "asian": "zh_CN",
    "native_hawaiian_pacific_islander": "en_US",
    "white": "en_US",
    "black": "en_US",
    "american_indian": "en_US",
    "alaska_native": "en_US",
    "american_indian_alaska_native": "en_US",
    "other": "en_US",
    "two_or_more": "en_US",
}

_HISPANIC_LOCALE = "es_MX"

# State-specific DL number formats.  Each format string uses '#' for a
# random digit and '?' for a random uppercase letter.
_DL_FORMATS: Dict[str, str] = {
    "HI": "H########",
    "CA": "?#######",
    "TX": "########",
    "NY": "### ### ###",
    "FL": "?###-###-##-###-#",
}
_DEFAULT_DL_FORMAT = "?########"

# Suffixes applied when a son shares the father's first name
_SUFFIXES = ["Jr.", "II", "III"]


class PIIGenerator:
    """Overlays synthetic PII onto a household's members.

    No distribution tables needed — uses the Faker library.
    """

    def __init__(self, tax_year: int = 2024) -> None:
        self.tax_year = tax_year
        self._fake = Faker("en_US")
        self._locale_fakers: Dict[str, Faker] = {}
        self._used_ssns: Set[str] = set()

    # =================================================================
    # Public API
    # =================================================================

    def overlay(self, household: Household) -> Household:
        """Populate PII fields on all persons in a household. Modifies in place.

        Args:
            household: Household with demographics populated (from demographics.py).

        Returns:
            Same Household with PII fields filled in on each Person.
        """
        self._used_ssns.clear()

        # 1. Household address (shared by all members)
        household.address = self._generate_address(household.state)

        # 2. Assign last names using family-consistency rules
        self._assign_family_names(household)

        # 3. Per-member PII
        for person in household.members:
            self._generate_person_pii(person, household)

        logger.info(
            "Overlaid PII on %d members (household %s)",
            len(household.members),
            household.household_id,
        )
        return household

    # =================================================================
    # Address generation
    # =================================================================

    def _generate_address(self, state: str) -> Address:
        """Generate a plausible address for the given state."""
        fake = self._fake
        street = fake.street_address()
        city = fake.city()
        zip_code = fake.zipcode()

        # ~20% chance of an apartment number
        apt: Optional[str] = None
        if random.random() < 0.20:
            apt = f"Apt {random.randint(1, 999)}"

        return Address(
            street=street,
            apt=apt,
            city=city,
            state=state.upper(),
            zip_code=zip_code,
        )

    # =================================================================
    # Family name assignment
    # =================================================================

    def _assign_family_names(self, household: Household) -> None:
        """Assign last names with family-consistency rules.

        Rules:
        - Householder gets a random last name.
        - Spouse: ~30% chance of a different (maiden) last name.
        - Unmarried partner: always different last name.
        - Biological / adopted children: share householder's last name.
        - Stepchildren: share spouse's last name (if different) or get a
          random last name.
        - Grandchildren: share householder's last name.
        - Parent: householder may share the parent's last name.
        - Others: random last name.
        """
        householder = household.get_householder()
        spouse = household.get_spouse()

        # Determine base family last name
        householder_last = self._fake.last_name()
        spouse_last = householder_last  # default: same

        if spouse is not None:
            if random.random() < 0.30:
                # Different (maiden) last name for spouse
                spouse_last = self._fake.last_name()
                # Avoid accidental collision
                while spouse_last == householder_last:
                    spouse_last = self._fake.last_name()

        # Assign to each member
        for person in household.members:
            if person.relationship == RelationshipType.HOUSEHOLDER:
                person.legal_last_name = householder_last

            elif person.relationship == RelationshipType.SPOUSE:
                person.legal_last_name = spouse_last

            elif person.relationship == RelationshipType.UNMARRIED_PARTNER:
                person.legal_last_name = self._fake.last_name()

            elif person.relationship in (
                RelationshipType.BIOLOGICAL_CHILD,
                RelationshipType.ADOPTED_CHILD,
                RelationshipType.GRANDCHILD,
            ):
                person.legal_last_name = householder_last

            elif person.relationship == RelationshipType.STEPCHILD:
                # Stepchildren carry the spouse's last name when it
                # differs, otherwise get a random one to signal the
                # blended-family scenario.
                if spouse_last != householder_last:
                    person.legal_last_name = spouse_last
                else:
                    person.legal_last_name = self._fake.last_name()

            elif person.relationship == RelationshipType.PARENT:
                # Householder may share parent's last name
                person.legal_last_name = householder_last

            else:
                person.legal_last_name = self._fake.last_name()

    # =================================================================
    # Per-person PII
    # =================================================================

    def _generate_person_pii(
        self, person: Person, household: Household,
    ) -> None:
        """Fill remaining PII fields on a single Person."""
        # First / middle name
        locale_fake = self._get_locale_faker(person)
        if person.sex == "F":
            person.legal_first_name = locale_fake.first_name_female()
            person.legal_middle_name = locale_fake.first_name_female()
        else:
            person.legal_first_name = locale_fake.first_name_male()
            person.legal_middle_name = locale_fake.first_name_male()

        # Suffix: if male child shares father's first name
        self._maybe_add_suffix(person, household)

        # SSN
        person.ssn = self._generate_ssn()

        # DOB
        person.dob = self._generate_dob(person.age)

        # Phone (adults only)
        if person.is_adult():
            person.phone = self._generate_phone()

        # Email (primary filer only)
        if person.relationship == RelationshipType.HOUSEHOLDER:
            person.email = self._fake.email()

        # ID document details (adults only)
        if person.is_adult():
            self._generate_id_document(person, household)

    # =================================================================
    # Name helpers
    # =================================================================

    def _get_locale_faker(self, person: Person) -> Faker:
        """Return a Faker instance with a locale hinted by demographics."""
        if person.hispanic_origin:
            locale = _HISPANIC_LOCALE
        else:
            locale = _LOCALE_MAP.get(person.race, "en_US")

        if locale not in self._locale_fakers:
            self._locale_fakers[locale] = Faker(locale)
        return self._locale_fakers[locale]

    def _maybe_add_suffix(
        self, person: Person, household: Household,
    ) -> None:
        """Add Jr./III suffix when a male child shares the father's first name."""
        if person.sex != "M" or person.is_adult():
            return

        householder = household.get_householder()
        if householder is None or householder.sex != "M":
            return

        # ~8% chance of matching father's first name
        if random.random() < 0.08:
            person.legal_first_name = householder.legal_first_name
            person.suffix = random.choice(_SUFFIXES)

    # =================================================================
    # SSN
    # =================================================================

    def _generate_ssn(self) -> str:
        """Generate a unique SSN in the 9XX-XX-XXXX test range."""
        for _ in range(1000):
            area = random.randint(900, 999)
            group = random.randint(0, 99)
            serial = random.randint(0, 9999)
            ssn = f"{area:03d}-{group:02d}-{serial:04d}"
            if ssn not in self._used_ssns:
                self._used_ssns.add(ssn)
                return ssn
        # Extremely unlikely fallback
        raise RuntimeError("Could not generate unique SSN after 1000 attempts")

    # =================================================================
    # DOB
    # =================================================================

    def _generate_dob(self, age: int) -> date:
        """Calculate a DOB from age and tax_year.

        The person is *age* years old at some point during the tax year.
        We pick a random month/day within the plausible birth-year
        window.
        """
        # The person could have been born in (tax_year - age) or
        # (tax_year - age - 1) depending on whether their birthday has
        # passed by Dec 31 of the tax year.
        birth_year_early = self.tax_year - age - 1
        birth_year_late = self.tax_year - age

        earliest = date(birth_year_early, 1, 2)
        latest = date(birth_year_late, 12, 31)

        delta = (latest - earliest).days
        if delta <= 0:
            return date(birth_year_late, 6, 15)

        random_day = random.randint(0, delta)
        return earliest + timedelta(days=random_day)

    # =================================================================
    # Phone
    # =================================================================

    @staticmethod
    def _generate_phone() -> str:
        """Generate a realistic-looking US phone number."""
        area = random.randint(200, 999)
        exchange = random.randint(200, 999)
        subscriber = random.randint(0, 9999)
        return f"({area:03d}) {exchange:03d}-{subscriber:04d}"

    # =================================================================
    # ID documents
    # =================================================================

    def _generate_id_document(
        self, person: Person, household: Household,
    ) -> None:
        """Generate driver's license / state ID details for an adult."""
        person.id_type = "drivers_license"
        person.id_state = household.state

        # DL number in state-specific format
        fmt = _DL_FORMATS.get(household.state, _DEFAULT_DL_FORMAT)
        person.id_number = self._format_id_number(fmt)

        # Expiry: issued 0-7 years ago, valid for 4-8 years
        years_ago = random.randint(0, 7)
        validity = random.randint(4, 8)
        issue_year = self.tax_year - years_ago
        expiry_year = issue_year + validity
        person.id_expiry = date(expiry_year, random.randint(1, 12), random.randint(1, 28))

        # ~15% "just moved" scenario: ID shows a different (old) address
        if random.random() < 0.15:
            person.id_address = self._generate_address(household.state)
        else:
            person.id_address = household.address

    @staticmethod
    def _format_id_number(fmt: str) -> str:
        """Expand a format string: '#' → digit, '?' → uppercase letter."""
        result: List[str] = []
        for ch in fmt:
            if ch == "#":
                result.append(str(random.randint(0, 9)))
            elif ch == "?":
                result.append(chr(random.randint(65, 90)))  # A-Z
            else:
                result.append(ch)
        return "".join(result)
