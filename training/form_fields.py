"""
Form field name constants for the 13614-C Part I.

These constants define the contract between:
- form_populator.py (builds field values for the answer key)
- the HTML intake form (uses these names as input field IDs)
- grader.py (compares submitted values against the answer key)

Field names use dot-separated namespaces matching form sections:
    section.subsection.field_name
"""

from typing import Dict, List

# =========================================================================
# Section A: About You
# =========================================================================

YOU_FIRST_NAME = "you.first_name"
YOU_MIDDLE_INITIAL = "you.middle_initial"
YOU_LAST_NAME = "you.last_name"
YOU_DOB = "you.dob"
YOU_SSN = "you.ssn"
YOU_JOB_TITLE = "you.job_title"
YOU_US_CITIZEN = "you.us_citizen"  # checkbox: yes
YOU_NOT_US_CITIZEN = "you.not_us_citizen"  # checkbox: no
YOU_PHONE = "you.phone"
YOU_EMAIL = "you.email"

# =========================================================================
# Section B: Mailing Address
# =========================================================================

ADDR_STREET = "addr.street"
ADDR_APT = "addr.apt"
ADDR_CITY = "addr.city"
ADDR_STATE = "addr.state"
ADDR_ZIP = "addr.zip"

# =========================================================================
# Section C: About Your Spouse
# =========================================================================

SPOUSE_FIRST_NAME = "spouse.first_name"
SPOUSE_MIDDLE_INITIAL = "spouse.middle_initial"
SPOUSE_LAST_NAME = "spouse.last_name"
SPOUSE_DOB = "spouse.dob"
SPOUSE_SSN = "spouse.ssn"
SPOUSE_JOB_TITLE = "spouse.job_title"

# =========================================================================
# Section D: Filing Status (radio group)
# =========================================================================

FILING_STATUS = "filing_status"

# Radio button choice values (used as the export value in the PDF)
FS_SINGLE = "single"
FS_MFJ = "married_filing_jointly"
FS_MFS = "married_filing_separately"
FS_HOH = "head_of_household"
FS_QSS = "qualifying_surviving_spouse"

FILING_STATUS_CHOICES = [FS_SINGLE, FS_MFJ, FS_MFS, FS_HOH, FS_QSS]

# =========================================================================
# Section E: Dependents (up to 4 rows)
# =========================================================================


def dep_field(index: int, field_name: str) -> str:
    """Generate a dependent field name for row *index* (0-based).

    Args:
        index: Dependent row number (0–3).
        field_name: One of first_name, last_name, dob, relationship,
                    months, single_or_married, us_citizen, student, disabled.

    Returns:
        Dot-separated field name, e.g. ``dep.0.first_name``.
    """
    return f"dep.{index}.{field_name}"


# Dependent sub-field names (used with dep_field())
DEP_FIRST_NAME = "first_name"
DEP_LAST_NAME = "last_name"
DEP_DOB = "dob"
DEP_RELATIONSHIP = "relationship"
DEP_MONTHS = "months"
DEP_SINGLE_OR_MARRIED = "single_or_married"  # radio: S / M
DEP_US_CITIZEN = "us_citizen"  # checkbox
DEP_STUDENT = "student"  # checkbox
DEP_DISABLED = "disabled"  # checkbox

MAX_DEPENDENTS = 4

# =========================================================================
# Section F: Additional Questions
# =========================================================================

CLAIMED_AS_DEPENDENT = "additional.claimed_as_dep"  # checkbox: yes
NOT_CLAIMED_AS_DEPENDENT = "additional.not_claimed_as_dep"  # checkbox: no
PRIOR_YEAR_DEPENDENT = "additional.prior_year_dep"  # checkbox: yes
NOT_PRIOR_YEAR_DEPENDENT = "additional.not_prior_year_dep"  # checkbox: no

# =========================================================================
# Helpers — enumerate all fields
# =========================================================================

# All text fields (for iteration / validation)
TEXT_FIELDS: List[str] = [
    YOU_FIRST_NAME, YOU_MIDDLE_INITIAL, YOU_LAST_NAME,
    YOU_DOB, YOU_SSN, YOU_JOB_TITLE, YOU_PHONE, YOU_EMAIL,
    ADDR_STREET, ADDR_APT, ADDR_CITY, ADDR_STATE, ADDR_ZIP,
    SPOUSE_FIRST_NAME, SPOUSE_MIDDLE_INITIAL, SPOUSE_LAST_NAME,
    SPOUSE_DOB, SPOUSE_SSN, SPOUSE_JOB_TITLE,
]

# Add dependent text fields for each row
for _i in range(MAX_DEPENDENTS):
    for _sub in (DEP_FIRST_NAME, DEP_LAST_NAME, DEP_DOB,
                 DEP_RELATIONSHIP, DEP_MONTHS):
        TEXT_FIELDS.append(dep_field(_i, _sub))

# All checkbox fields
CHECKBOX_FIELDS: List[str] = [
    YOU_US_CITIZEN, YOU_NOT_US_CITIZEN,
    CLAIMED_AS_DEPENDENT, NOT_CLAIMED_AS_DEPENDENT,
    PRIOR_YEAR_DEPENDENT, NOT_PRIOR_YEAR_DEPENDENT,
]

for _i in range(MAX_DEPENDENTS):
    for _sub in (DEP_US_CITIZEN, DEP_STUDENT, DEP_DISABLED):
        CHECKBOX_FIELDS.append(dep_field(_i, _sub))
    # single/married radio per dependent
    CHECKBOX_FIELDS.append(dep_field(_i, DEP_SINGLE_OR_MARRIED))

# All field names combined
ALL_FIELDS: List[str] = TEXT_FIELDS + CHECKBOX_FIELDS + [FILING_STATUS]
