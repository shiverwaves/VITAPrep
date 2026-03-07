"""
Form field value builder — maps household data to 13614-C field names.

Produces a dict of ``{field_name: value}`` from a Household, used by:
1. The interactive HTML form (pre-filling in verify mode).
2. The grader (answer key via ``build_field_values``).

The field name constants from ``training.form_fields`` are the shared
contract between this module, the HTML form, and the grader.
"""

import logging
from datetime import date
from typing import Dict, List, Optional

from generator.models import (
    FilingStatus,
    Household,
    Person,
    RelationshipType,
)
from training.form_fields import (
    ADDR_APT,
    ADDR_CITY,
    ADDR_STATE,
    ADDR_STREET,
    ADDR_ZIP,
    CLAIMED_AS_DEPENDENT,
    DEP_DOB,
    DEP_FIRST_NAME,
    DEP_LAST_NAME,
    DEP_MONTHS,
    DEP_RELATIONSHIP,
    DEP_SINGLE_OR_MARRIED,
    DEP_STUDENT,
    DEP_US_CITIZEN,
    DEP_DISABLED,
    FILING_STATUS,
    FS_HOH,
    FS_MFJ,
    FS_MFS,
    FS_QSS,
    FS_SINGLE,
    MAX_DEPENDENTS,
    NOT_CLAIMED_AS_DEPENDENT,
    NOT_PRIOR_YEAR_DEPENDENT,
    SPOUSE_DOB,
    SPOUSE_FIRST_NAME,
    SPOUSE_JOB_TITLE,
    SPOUSE_LAST_NAME,
    SPOUSE_MIDDLE_INITIAL,
    SPOUSE_SSN,
    YOU_DOB,
    YOU_EMAIL,
    YOU_FIRST_NAME,
    YOU_JOB_TITLE,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_PHONE,
    YOU_SSN,
    YOU_US_CITIZEN,
    dep_field,
)

logger = logging.getLogger(__name__)

# Mapping from FilingStatus enum to form radio button values
_FILING_STATUS_MAP: Dict[FilingStatus, str] = {
    FilingStatus.SINGLE: FS_SINGLE,
    FilingStatus.MARRIED_FILING_JOINTLY: FS_MFJ,
    FilingStatus.MARRIED_FILING_SEPARATELY: FS_MFS,
    FilingStatus.HEAD_OF_HOUSEHOLD: FS_HOH,
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: FS_QSS,
}

# Relationship types that qualify as VITA dependents
_DEPENDENT_RELATIONSHIPS: Dict[RelationshipType, str] = {
    RelationshipType.BIOLOGICAL_CHILD: "Son/Daughter",
    RelationshipType.ADOPTED_CHILD: "Son/Daughter",
    RelationshipType.STEPCHILD: "Stepchild",
    RelationshipType.GRANDCHILD: "Grandchild",
    RelationshipType.SIBLING: "Sibling",
    RelationshipType.PARENT: "Parent",
    RelationshipType.OTHER_RELATIVE: "Other",
}


def _format_date(d: Optional[date]) -> str:
    """Format a date as MM/DD/YYYY for the intake form, or empty string."""
    if d is None:
        return ""
    return d.strftime("%m/%d/%Y")


def _middle_initial(name: str) -> str:
    """Extract just the first letter of a middle name, or empty string."""
    if not name:
        return ""
    return name[0].upper()


def _relationship_label(person: Person) -> str:
    """Human-readable relationship label for the dependent section."""
    rel = person.relationship
    if isinstance(rel, str):
        try:
            rel = RelationshipType(rel)
        except ValueError:
            return rel
    return _DEPENDENT_RELATIONSHIPS.get(rel, "Other")


def _get_dependents(household: Household) -> List[Person]:
    """Return dependents sorted by age descending (oldest first), capped at 4."""
    deps = [
        p for p in household.members
        if p.is_dependent or p.can_be_claimed
    ]
    deps.sort(key=lambda p: p.age, reverse=True)
    return deps[:MAX_DEPENDENTS]


def build_field_values(household: Household) -> Dict[str, str]:
    """Build a dict mapping form field names to their string values.

    This is the core mapping logic used by the HTML form (pre-fill in
    verify mode) and the grader (answer key generation).

    Args:
        household: Household with PII fully populated.

    Returns:
        Dict of ``{field_name: value}`` for every field that should be
        filled. Empty/unused fields are omitted.
    """
    values: Dict[str, str] = {}
    householder = household.get_householder()
    spouse = household.get_spouse()

    # =================================================================
    # Section A: About You (the householder / primary filer)
    # =================================================================
    if householder:
        values[YOU_FIRST_NAME] = householder.legal_first_name
        values[YOU_MIDDLE_INITIAL] = _middle_initial(householder.legal_middle_name)
        values[YOU_LAST_NAME] = householder.legal_last_name
        values[YOU_DOB] = _format_date(householder.dob)
        values[YOU_SSN] = householder.ssn
        values[YOU_JOB_TITLE] = householder.occupation_title or ""
        values[YOU_PHONE] = householder.phone
        values[YOU_EMAIL] = householder.email

        # Citizenship — default to US citizen (true for most VITA scenarios)
        values[YOU_US_CITIZEN] = "Yes"

    # =================================================================
    # Section B: Mailing Address
    # =================================================================
    if household.address:
        addr = household.address
        values[ADDR_STREET] = addr.street
        values[ADDR_APT] = addr.apt or ""
        values[ADDR_CITY] = addr.city
        values[ADDR_STATE] = addr.state
        values[ADDR_ZIP] = addr.zip_code

    # =================================================================
    # Section C: About Your Spouse
    # =================================================================
    if spouse:
        values[SPOUSE_FIRST_NAME] = spouse.legal_first_name
        values[SPOUSE_MIDDLE_INITIAL] = _middle_initial(spouse.legal_middle_name)
        values[SPOUSE_LAST_NAME] = spouse.legal_last_name
        values[SPOUSE_DOB] = _format_date(spouse.dob)
        values[SPOUSE_SSN] = spouse.ssn
        values[SPOUSE_JOB_TITLE] = spouse.occupation_title or ""

    # =================================================================
    # Section D: Filing Status
    # =================================================================
    filing_status = household.derive_filing_status()
    pdf_val = _FILING_STATUS_MAP.get(filing_status)
    if pdf_val:
        values[FILING_STATUS] = pdf_val

    # =================================================================
    # Section E: Dependents
    # =================================================================
    dependents = _get_dependents(household)
    for i, dep in enumerate(dependents):
        values[dep_field(i, DEP_FIRST_NAME)] = dep.legal_first_name
        values[dep_field(i, DEP_LAST_NAME)] = dep.legal_last_name
        values[dep_field(i, DEP_DOB)] = _format_date(dep.dob)
        values[dep_field(i, DEP_RELATIONSHIP)] = _relationship_label(dep)
        values[dep_field(i, DEP_MONTHS)] = str(dep.months_in_home)
        # Children are single by default
        values[dep_field(i, DEP_SINGLE_OR_MARRIED)] = "Yes"
        # US citizen — default true for most VITA scenarios
        values[dep_field(i, DEP_US_CITIZEN)] = "Yes"
        values[dep_field(i, DEP_STUDENT)] = (
            "Yes" if dep.is_full_time_student else ""
        )
        values[dep_field(i, DEP_DISABLED)] = (
            "Yes" if dep.has_disability else ""
        )

    # =================================================================
    # Section F: Additional Questions
    # =================================================================
    if householder and householder.can_be_claimed:
        values[CLAIMED_AS_DEPENDENT] = "Yes"
    else:
        values[NOT_CLAIMED_AS_DEPENDENT] = "Yes"

    # Prior year dependent — default No (simplest case)
    values[NOT_PRIOR_YEAR_DEPENDENT] = "Yes"

    return values
