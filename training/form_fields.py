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
SPOUSE_PHONE = "spouse.phone"

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
# (``dep.{i}.name``); the prior split into first/last is gone. The
# Y/N/S/M cells render as text inputs in the new template (one-letter
# values), not checkboxes — comments below reflect template reality.
DEP_NAME = "name"
DEP_DOB = "dob"
DEP_RELATIONSHIP = "relationship"
DEP_MONTHS = "months"
DEP_SINGLE_OR_MARRIED = "single_or_married"  # text: S / M (legacy alias)
DEP_MARITAL_EOY = "marital_eoy"              # text: S / M (template name)
DEP_US_CITIZEN = "us_citizen"                # text: Y / N
DEP_RESIDENT = "resident"                    # text: Y / N (US/Canada/Mexico)
DEP_STUDENT = "student"                      # text: Y / N
DEP_DISABLED = "disabled"                    # text: Y / N
DEP_IPPIN = "ippin"                          # text: Y / N

# Volunteer-completed columns on the dependents grid (Page 1, Section 11).
# These are the gray-shaded "to be completed by certified volunteer"
# columns; the player fills them. Three are scored against ground truth
# (income_under, support, home_cost); the other two are listed in
# UNGRADED_FIELDS and surfaced in the result UI as not-graded.
DEP_VOL_QC_OTHER = "vol_qc_other"
DEP_VOL_SELF_SUPPORT = "vol_self_support"
DEP_VOL_INCOME_UNDER = "vol_income_under"
DEP_VOL_SUPPORT = "vol_support"
DEP_VOL_HOME_COST = "vol_home_cost"

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
# Section 4 follow-up: did you live or work in two or more states?
# =========================================================================
TWO_STATES_YES = "two_states_yes"
TWO_STATES_NO = "two_states_no"

# =========================================================================
# Section 6: status checkboxes (You / Spouse / No trios)
# =========================================================================
# Each row is a trio: the filer field, the spouse field, and a single
# "no" field that means neither person checks the box. ``YOU_US_CITIZEN``
# already exists and stays as the filer-citizen checkbox; the rest of
# the row is added here.

# A U.S. citizen
SPOUSE_US_CITIZEN = "spouse.us_citizen"
STATUS_CITIZEN_NO = "citizen_no"

# In the U.S. on a visa
FILER_ON_VISA = "filer.on_visa"
SPOUSE_ON_VISA = "spouse.on_visa"
STATUS_VISA_NO = "visa_no"

# A full-time student
FILER_FULL_TIME_STUDENT = "filer.full_time_student"
SPOUSE_FULL_TIME_STUDENT = "spouse.full_time_student"
STATUS_STUDENT_NO = "student_no"

# Legally blind
FILER_LEGALLY_BLIND = "filer.legally_blind"
SPOUSE_LEGALLY_BLIND = "spouse.legally_blind"
STATUS_BLIND_NO = "blind_no"

# Totally and permanently disabled
FILER_DISABLED = "filer.disabled"
SPOUSE_DISABLED = "spouse.disabled"
STATUS_DISABLED_NO = "disabled_no"

# Issued an identity protection PIN (IPPIN)
FILER_IPPIN = "filer.ippin"
SPOUSE_IPPIN = "spouse.ippin"
STATUS_IPPIN_NO = "ippin_no"

# Owners or holders of any digital assets
FILER_DIGITAL_ASSETS = "filer.digital_assets"
SPOUSE_DIGITAL_ASSETS = "spouse.digital_assets"
STATUS_DIGITAL_NO = "digital_no"

# =========================================================================
# Section 7: refund / payment preferences
# =========================================================================
# All player-input only — nothing pre-fills, the grader doesn't score
# them in this version (taxpayer-decision fields, not derivable from
# the household).
REFUND_DIRECT_DEPOSIT = "refund.direct_deposit"
REFUND_CHECK = "refund.check"
REFUND_SPLIT = "refund.split"
REFUND_OTHER = "refund.other"

PAYMENT_BANK = "payment.bank"
PAYMENT_IRS_DIRECT = "payment.irs_direct"
PAYMENT_INSTALLMENT = "payment.installment"
PAYMENT_MAIL = "payment.mail"

# =========================================================================
# Section 8: language preference (You / Spouse / No)
# =========================================================================
LANG_PREF_YOU = "lang_pref_you"
LANG_PREF_SPOUSE = "lang_pref_spouse"
LANG_PREF_NO = "lang_pref_no"
LANG_PREF_LANGUAGE = "lang_pref_language"  # text: language name

# =========================================================================
# Section 9: Presidential Election Campaign Fund (You / Spouse / No)
# =========================================================================
ELECTION_YOU = "election.you"
ELECTION_SPOUSE = "election.spouse"
ELECTION_NO = "election.no"

# =========================================================================
# Section 10: marital status
# =========================================================================
MARITAL_NEVER_MARRIED = "marital.never_married"
MARITAL_MARRIED = "marital.married"
MARITAL_MARRIED_EOY_YES = "marital.married_eoy"
MARITAL_MARRIED_EOY_NO = "marital.married_eoy_no"
MARITAL_LIVED_APART_YES = "marital.lived_apart_yes"
MARITAL_LIVED_APART_NO = "marital.lived_apart_no"
MARITAL_DIVORCED = "marital.divorced"
MARITAL_SEPARATED = "marital.separated"
MARITAL_WIDOWED = "marital.widowed"
MARITAL_DIVORCE_DATE = "marital.divorce_date"
MARITAL_SEPARATION_DATE = "marital.separation_date"
MARITAL_SPOUSE_DEATH_YEAR = "marital.spouse_death_year"

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
    SPOUSE_DOB, SPOUSE_JOB_TITLE, SPOUSE_PHONE,
    LANG_PREF_LANGUAGE,
    MARITAL_DIVORCE_DATE, MARITAL_SEPARATION_DATE,
    MARITAL_SPOUSE_DEATH_YEAR,
]

# Dependent text fields per row. The Y/N/S/M cells render as text
# inputs in the new template (one-letter values), so they live here
# rather than in CHECKBOX_FIELDS.
for _i in range(MAX_DEPENDENTS):
    for _sub in (
        DEP_NAME, DEP_DOB, DEP_RELATIONSHIP, DEP_MONTHS,
        DEP_MARITAL_EOY,
        DEP_US_CITIZEN, DEP_RESIDENT, DEP_STUDENT,
        DEP_DISABLED, DEP_IPPIN,
        DEP_VOL_QC_OTHER, DEP_VOL_SELF_SUPPORT,
        DEP_VOL_INCOME_UNDER, DEP_VOL_SUPPORT, DEP_VOL_HOME_COST,
    ):
        TEXT_FIELDS.append(dep_field(_i, _sub))

# All checkbox fields (booleans in the form: checked / unchecked).
CHECKBOX_FIELDS: List[str] = [
    # Section 4 follow-up
    TWO_STATES_YES, TWO_STATES_NO,
    # Section 5 (Can anyone else claim you)
    CLAIMED_AS_DEPENDENT, NOT_CLAIMED_AS_DEPENDENT,
    PRIOR_YEAR_DEPENDENT, NOT_PRIOR_YEAR_DEPENDENT,
    # Section 6 status trios
    YOU_US_CITIZEN, SPOUSE_US_CITIZEN, STATUS_CITIZEN_NO,
    FILER_ON_VISA, SPOUSE_ON_VISA, STATUS_VISA_NO,
    FILER_FULL_TIME_STUDENT, SPOUSE_FULL_TIME_STUDENT, STATUS_STUDENT_NO,
    FILER_LEGALLY_BLIND, SPOUSE_LEGALLY_BLIND, STATUS_BLIND_NO,
    FILER_DISABLED, SPOUSE_DISABLED, STATUS_DISABLED_NO,
    FILER_IPPIN, SPOUSE_IPPIN, STATUS_IPPIN_NO,
    FILER_DIGITAL_ASSETS, SPOUSE_DIGITAL_ASSETS, STATUS_DIGITAL_NO,
    # Section 7 refund / payment options
    REFUND_DIRECT_DEPOSIT, REFUND_CHECK, REFUND_SPLIT, REFUND_OTHER,
    PAYMENT_BANK, PAYMENT_IRS_DIRECT,
    PAYMENT_INSTALLMENT, PAYMENT_MAIL,
    # Section 8 language preference
    LANG_PREF_YOU, LANG_PREF_SPOUSE, LANG_PREF_NO,
    # Section 9 Presidential Election Campaign Fund
    ELECTION_YOU, ELECTION_SPOUSE, ELECTION_NO,
    # Section 10 marital status (rows 1 and 3 are checkboxes;
    # rows 2 and 4 are date / year text inputs handled above).
    MARITAL_NEVER_MARRIED, MARITAL_MARRIED,
    MARITAL_MARRIED_EOY_YES, MARITAL_MARRIED_EOY_NO,
    MARITAL_LIVED_APART_YES, MARITAL_LIVED_APART_NO,
    MARITAL_DIVORCED, MARITAL_SEPARATED, MARITAL_WIDOWED,
    # Legacy filer-not-citizen flag (kept for back-compat; the new
    # template uses STATUS_CITIZEN_NO instead).
    YOU_NOT_US_CITIZEN,
]

# Per-dependent radio (single/married) — legacy alias for the new
# DEP_MARITAL_EOY text field, kept so existing callers don't break.
for _i in range(MAX_DEPENDENTS):
    CHECKBOX_FIELDS.append(dep_field(_i, DEP_SINGLE_OR_MARRIED))

# Volunteer columns the grader does NOT score in this version. The
# form still renders them; the result UI surfaces them with a
# "Not graded in this version" label so players don't form a wrong
# mental model from silent passes.
UNGRADED_FIELDS: List[str] = []
for _i in range(MAX_DEPENDENTS):
    UNGRADED_FIELDS.append(dep_field(_i, DEP_VOL_QC_OTHER))
    UNGRADED_FIELDS.append(dep_field(_i, DEP_VOL_SELF_SUPPORT))

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
