"""
Form field name constants for the 13614-C.

These constants define the contract between:
- form_populator.py (builds field values for the answer key)
- the HTML intake form (uses these names as input field IDs)
- grader.py (compares submitted values against the answer key)

Field names use dot-separated namespaces matching form sections:
    section.subsection.field_name

Part I: Sections A–F (personal information)
Part II: Income (wages, interest, dividends, SS, retirement, SE)
Part III: Expenses, deductions & credits (mortgage, taxes, charitable, etc.)
"""

from typing import Dict, List

# =========================================================================
# Section A: About You
# =========================================================================

# Identifiers stay YOU_* (no import churn); wire-format values are filer.*.
# Aligns with the new Form 13614-C Page 1 mockup.
YOU_FIRST_NAME = "filer.first_name"
YOU_MIDDLE_INITIAL = "filer.middle_initial"
YOU_LAST_NAME = "filer.last_name"
YOU_DOB = "filer.dob"
YOU_SSN = "filer.ssn"
YOU_JOB_TITLE = "filer.job_title"
YOU_US_CITIZEN = "filer.us_citizen"  # checkbox: yes
YOU_NOT_US_CITIZEN = "filer.not_us_citizen"  # checkbox: no
YOU_PHONE = "filer.phone"
YOU_EMAIL = "filer.email"

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


# Dependent sub-field names (used with dep_field()).
# Page 1 of the new template uses a single combined name field per row
# (``dep.{i}.name``); the prior split into first/last is gone.
DEP_NAME = "name"
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

# Form 13614-C "Can anyone else claim you" row (Page 1, Section 5).
CLAIMED_AS_DEPENDENT = "claimable.yes"  # checkbox: yes
NOT_CLAIMED_AS_DEPENDENT = "claimable.no"  # checkbox: no
PRIOR_YEAR_DEPENDENT = "claimable.prior_year_yes"  # checkbox: yes
NOT_PRIOR_YEAR_DEPENDENT = "claimable.prior_year_no"  # checkbox: no

# =========================================================================
# Part II — Income
# =========================================================================
# Form 13614-C Part II asks yes/no for each income source, then the
# taxpayer lists amounts from their documents (W-2, 1099, SSA-1099).
# For each source we define:
#   - A checkbox field (did you receive this type?)
#   - An amount field (total from all documents of that type)

# Wages, salaries, tips (from W-2s)
INCOME_WAGES = "income.wages"
INCOME_WAGES_AMOUNT = "income.wages.amount"

# Interest income (from 1099-INT)
INCOME_INTEREST = "income.interest"
INCOME_INTEREST_AMOUNT = "income.interest.amount"

# Dividend income (from 1099-DIV)
INCOME_DIVIDENDS = "income.dividends"
INCOME_DIVIDENDS_AMOUNT = "income.dividends.amount"

# Social Security benefits (from SSA-1099)
INCOME_SOCIAL_SECURITY = "income.social_security"
INCOME_SOCIAL_SECURITY_AMOUNT = "income.social_security.amount"

# Pensions and annuities (from 1099-R)
INCOME_RETIREMENT = "income.retirement"
INCOME_RETIREMENT_AMOUNT = "income.retirement.amount"

# Self-employment income (from 1099-NEC)
INCOME_SELF_EMPLOYMENT = "income.self_employment"
INCOME_SELF_EMPLOYMENT_AMOUNT = "income.self_employment.amount"

# Aggregate total (all sources)
INCOME_TOTAL = "income.total"

# All income checkbox fields
INCOME_CHECKBOX_FIELDS: List[str] = [
    INCOME_WAGES,
    INCOME_INTEREST,
    INCOME_DIVIDENDS,
    INCOME_SOCIAL_SECURITY,
    INCOME_RETIREMENT,
    INCOME_SELF_EMPLOYMENT,
]

# All income amount fields
INCOME_AMOUNT_FIELDS: List[str] = [
    INCOME_WAGES_AMOUNT,
    INCOME_INTEREST_AMOUNT,
    INCOME_DIVIDENDS_AMOUNT,
    INCOME_SOCIAL_SECURITY_AMOUNT,
    INCOME_RETIREMENT_AMOUNT,
    INCOME_SELF_EMPLOYMENT_AMOUNT,
    INCOME_TOTAL,
]

# =========================================================================
# Part III — Expenses, Deductions & Credits
# =========================================================================
# Form 13614-C Part III (Page 3) has a two-column layout: client questions
# on the left, volunteer-completed fields on the right.  We model it the
# same way as Part II: checkbox + amount pairs.  Client questions are
# conveyed through scenario interview notes; the volunteer fields here
# are what the student fills in and the grader scores.

# Itemized deductions
EXPENSE_MORTGAGE_INTEREST = "expense.mortgage_interest"
EXPENSE_MORTGAGE_INTEREST_AMOUNT = "expense.mortgage_interest.amount"

EXPENSE_PROPERTY_TAXES = "expense.property_taxes"
EXPENSE_PROPERTY_TAXES_AMOUNT = "expense.property_taxes.amount"

EXPENSE_MEDICAL = "expense.medical"

EXPENSE_CHARITABLE = "expense.charitable"
EXPENSE_CHARITABLE_AMOUNT = "expense.charitable.amount"

# Standard vs Itemized (radio: "standard" / "itemized")
EXPENSE_DEDUCTION_TYPE = "expense.deduction_type"

DEDUCTION_TYPE_STANDARD = "standard"
DEDUCTION_TYPE_ITEMIZED = "itemized"
DEDUCTION_TYPE_CHOICES = [DEDUCTION_TYPE_STANDARD, DEDUCTION_TYPE_ITEMIZED]

# Above-the-line deductions
EXPENSE_STUDENT_LOAN = "expense.student_loan"
EXPENSE_STUDENT_LOAN_AMOUNT = "expense.student_loan.amount"

EXPENSE_CHILD_CARE = "expense.child_care"
EXPENSE_CHILD_CARE_AMOUNT = "expense.child_care.amount"

EXPENSE_EDUCATOR = "expense.educator"
EXPENSE_EDUCATOR_AMOUNT = "expense.educator.amount"

EXPENSE_IRA = "expense.ira"
EXPENSE_IRA_AMOUNT = "expense.ira.amount"

# Education credits
EXPENSE_EDUCATION = "expense.education"
EXPENSE_EDUCATION_AMOUNT = "expense.education.amount"

# All expense checkbox fields
EXPENSE_CHECKBOX_FIELDS: List[str] = [
    EXPENSE_MORTGAGE_INTEREST,
    EXPENSE_PROPERTY_TAXES,
    EXPENSE_MEDICAL,
    EXPENSE_CHARITABLE,
    EXPENSE_STUDENT_LOAN,
    EXPENSE_CHILD_CARE,
    EXPENSE_EDUCATOR,
    EXPENSE_IRA,
    EXPENSE_EDUCATION,
]

# All expense amount fields
EXPENSE_AMOUNT_FIELDS: List[str] = [
    EXPENSE_MORTGAGE_INTEREST_AMOUNT,
    EXPENSE_PROPERTY_TAXES_AMOUNT,
    EXPENSE_CHARITABLE_AMOUNT,
    EXPENSE_STUDENT_LOAN_AMOUNT,
    EXPENSE_CHILD_CARE_AMOUNT,
    EXPENSE_EDUCATOR_AMOUNT,
    EXPENSE_IRA_AMOUNT,
    EXPENSE_EDUCATION_AMOUNT,
]

# =========================================================================
# Helpers — enumerate all fields
# =========================================================================

# All text fields (for iteration / validation).
# YOU_SSN / SPOUSE_SSN are intentionally absent: Page 1 of the new
# 13614-C template does not have SSN inputs (SSN appears on a later
# page). The constants are kept so legacy code that still references
# them by identifier doesn't break.
TEXT_FIELDS: List[str] = [
    YOU_FIRST_NAME, YOU_MIDDLE_INITIAL, YOU_LAST_NAME,
    YOU_DOB, YOU_JOB_TITLE, YOU_PHONE, YOU_EMAIL,
    ADDR_STREET, ADDR_APT, ADDR_CITY, ADDR_STATE, ADDR_ZIP,
    SPOUSE_FIRST_NAME, SPOUSE_MIDDLE_INITIAL, SPOUSE_LAST_NAME,
    SPOUSE_DOB, SPOUSE_JOB_TITLE,
]

# Add dependent text fields for each row
for _i in range(MAX_DEPENDENTS):
    for _sub in (DEP_NAME, DEP_DOB, DEP_RELATIONSHIP, DEP_MONTHS):
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

# Part I fields only (Sections A–F: personal info, address, spouse, dependents)
PART1_FIELDS: List[str] = TEXT_FIELDS + CHECKBOX_FIELDS + [FILING_STATUS]

# Part II fields only (income checkboxes + amounts)
PART2_FIELDS: List[str] = INCOME_CHECKBOX_FIELDS + INCOME_AMOUNT_FIELDS

# Part III fields only (expense checkboxes + amounts + deduction type)
PART3_FIELDS: List[str] = (
    EXPENSE_CHECKBOX_FIELDS + EXPENSE_AMOUNT_FIELDS + [EXPENSE_DEDUCTION_TYPE]
)

# All field names combined
ALL_FIELDS: List[str] = PART1_FIELDS + PART2_FIELDS + PART3_FIELDS
