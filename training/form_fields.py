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
# Part II — Income (Page 2 new template)
# =========================================================================
# Constants for the new IRS-faithful Page 2 mockup. The legacy
# INCOME_*_AMOUNT pairs above remain for back-compat with the old
# render path; the new template uses three columns:
#   - Client column: 14 primary Y checkboxes + 4 sub-questions
#   - Volunteer column: per-row entries with count / amount / Y/N pairs
#   - Notes column: 14 free-form per-row notes (ungraded)
#
# Naming follows the input ``name`` attributes in
# ``docs/mockups/13614c_page2.html`` so the populator and grader can
# cross-reference them directly.

# --- Client column primary checkboxes (one per row) ---------------------
# Row 1 (wages) reuses the existing ``INCOME_WAGES`` constant.
INCOME_TIPS = "income.tips"
# Row 3 (retirement / 1099-R) reuses ``INCOME_RETIREMENT``.
INCOME_DISABILITY = "income.disability"
INCOME_SS = "income.ss"
INCOME_UNEMPLOYMENT = "income.unemployment"
INCOME_STATE_REFUND = "income.state_refund"
# Row 8 combines interest + dividends into one client checkbox; the
# legacy ``INCOME_INTEREST`` / ``INCOME_DIVIDENDS`` constants stay
# available for callers that still split them.
INCOME_INTEREST_DIVIDENDS = "income.interest_dividends"
INCOME_STOCK_SALE = "income.stock_sale"
INCOME_ALIMONY = "income.alimony"
INCOME_RENTAL = "income.rental"
INCOME_PERSONAL_PROPERTY_RENTAL = "income.personal_property_rental"
# Row 12 (self-employment) reuses ``INCOME_SELF_EMPLOYMENT``.
INCOME_GAMBLING = "income.gambling"
INCOME_OTHER = "income.other"

# --- Client column sub-questions ----------------------------------------
# Row 1: free-form text noting jobs when there are more than five W-2s.
INCOME_WAGES_JOBS = "income.wages.jobs"
# Row 9: prior-year capital loss Y/N pair.
INCOME_STOCK_SALE_PRIOR_LOSS_YES = "income.stock_sale.prior_loss.yes"
INCOME_STOCK_SALE_PRIOR_LOSS_NO = "income.stock_sale.prior_loss.no"
# Row 11: rented out personal residence Y/N pair.
INCOME_RENTAL_SHORT_PERSONAL_RESIDENCE_YES = "income.rental.short_personal_residence.yes"
INCOME_RENTAL_SHORT_PERSONAL_RESIDENCE_NO = "income.rental.short_personal_residence.no"
# Row 12: prior-year self-employment loss Y/N pair.
INCOME_SELF_EMPLOYMENT_PRIOR_LOSS_YES = "income.self_employment.prior_loss.yes"
INCOME_SELF_EMPLOYMENT_PRIOR_LOSS_NO = "income.self_employment.prior_loss.no"

# --- Volunteer column entries -------------------------------------------
# Row 1 — wages
VOL_INCOME_W2 = "vol.income.w2"
VOL_INCOME_W2_COUNT = "vol.income.w2.count"
# Row 2 — tips (no count/amount entry; just the checkbox)
VOL_INCOME_TIPS = "vol.income.tips"
# Row 3 — retirement (1099-R + QCD amount)
VOL_INCOME_1099R = "vol.income.1099r"
VOL_INCOME_1099R_COUNT = "vol.income.1099r.count"
VOL_INCOME_QCD = "vol.income.qcd"
VOL_INCOME_QCD_AMOUNT = "vol.income.qcd.amount"
# Row 4 — disability
VOL_INCOME_DISABILITY = "vol.income.disability"
VOL_INCOME_DISABILITY_COUNT = "vol.income.disability.count"
# Row 5 — Social Security (SSA-1099)
VOL_INCOME_SSA = "vol.income.ssa"
VOL_INCOME_SSA_COUNT = "vol.income.ssa.count"
# Row 6 — unemployment (1099-G)
VOL_INCOME_1099G = "vol.income.1099g"
VOL_INCOME_1099G_COUNT = "vol.income.1099g.count"
# Row 7 — state refund + itemized-last-year Y/N
VOL_INCOME_STATE_REFUND = "vol.income.state_refund"
VOL_INCOME_STATE_REFUND_AMOUNT = "vol.income.state_refund.amount"
VOL_INCOME_ITEMIZED_LAST_YEAR = "vol.income.itemized_last_year"
VOL_INCOME_ITEMIZED_LAST_YEAR_YES = "vol.income.itemized_last_year.yes"
VOL_INCOME_ITEMIZED_LAST_YEAR_NO = "vol.income.itemized_last_year.no"
# Row 8 — interest + dividends (1099-INT, 1099-DIV)
VOL_INCOME_1099INT = "vol.income.1099int"
VOL_INCOME_1099INT_COUNT = "vol.income.1099int.count"
VOL_INCOME_1099DIV = "vol.income.1099div"
VOL_INCOME_1099DIV_COUNT = "vol.income.1099div.count"
# Row 9 — stock sale (1099-B + capital-loss carryover Y/N)
VOL_INCOME_1099B = "vol.income.1099b"
VOL_INCOME_1099B_COUNT = "vol.income.1099b.count"
VOL_INCOME_CAPITAL_LOSS_CARRYOVER = "vol.income.capital_loss_carryover"
VOL_INCOME_CAPITAL_LOSS_CARRYOVER_YES = "vol.income.capital_loss_carryover.yes"
VOL_INCOME_CAPITAL_LOSS_CARRYOVER_NO = "vol.income.capital_loss_carryover.no"
# Row 10 — alimony (received + spouse-excluded Y/N)
VOL_INCOME_ALIMONY = "vol.income.alimony"
VOL_INCOME_ALIMONY_AMOUNT = "vol.income.alimony.amount"
VOL_INCOME_ALIMONY_EXCLUDED = "vol.income.alimony_excluded"
VOL_INCOME_ALIMONY_EXCLUDED_YES = "vol.income.alimony_excluded.yes"
VOL_INCOME_ALIMONY_EXCLUDED_NO = "vol.income.alimony_excluded.no"
# Row 11 — rental (real + personal property — shared row)
VOL_INCOME_RENTAL = "vol.income.rental"
VOL_INCOME_RENTAL_EXPENSE = "vol.income.rental_expense"
VOL_INCOME_RENTAL_EXPENSE_AMOUNT = "vol.income.rental_expense.amount"
# Row 13 — gambling (W-2G)
VOL_INCOME_W2G = "vol.income.w2g"
VOL_INCOME_W2G_COUNT = "vol.income.w2g.count"
# Row 12 — self-employment (Schedule C + 1099 family + Schedule C expenses)
VOL_INCOME_SCHEDULE_C = "vol.income.schedule_c"
VOL_INCOME_1099MISC = "vol.income.1099misc"
VOL_INCOME_1099MISC_COUNT = "vol.income.1099misc.count"
VOL_INCOME_1099NEC = "vol.income.1099nec"
VOL_INCOME_1099NEC_COUNT = "vol.income.1099nec.count"
VOL_INCOME_1099K = "vol.income.1099k"
VOL_INCOME_1099K_COUNT = "vol.income.1099k.count"
VOL_INCOME_OTHER_REPORTED_ELSEWHERE = "vol.income.other_reported_elsewhere"
VOL_INCOME_SCHEDULE_C_EXPENSES = "vol.income.schedule_c_expenses"
VOL_INCOME_SCHEDULE_C_EXPENSES_AMOUNT = "vol.income.schedule_c_expenses.amount"
# Row 14 — other
VOL_INCOME_OTHER = "vol.income.other"

# --- Notes column (one per row, free-form, ungraded) --------------------
INCOME_NOTE_WAGES = "income.note.wages"
INCOME_NOTE_TIPS = "income.note.tips"
INCOME_NOTE_RETIREMENT = "income.note.retirement"
INCOME_NOTE_DISABILITY = "income.note.disability"
INCOME_NOTE_SS = "income.note.ss"
INCOME_NOTE_UNEMPLOYMENT = "income.note.unemployment"
INCOME_NOTE_STATE_REFUND = "income.note.state_refund"
INCOME_NOTE_INTEREST_DIVIDENDS = "income.note.interest_dividends"
INCOME_NOTE_STOCK_SALE = "income.note.stock_sale"
INCOME_NOTE_ALIMONY = "income.note.alimony"
INCOME_NOTE_RENTAL = "income.note.rental"
INCOME_NOTE_SELF_EMPLOYMENT = "income.note.self_employment"
INCOME_NOTE_GAMBLING = "income.note.gambling"
INCOME_NOTE_OTHER = "income.note.other"

# --- Aggregations -------------------------------------------------------
# Client-column primary checkboxes for Page 2 (one per row).
P2_CLIENT_CHECKBOX_FIELDS: List[str] = [
    INCOME_WAGES,
    INCOME_TIPS,
    INCOME_RETIREMENT,
    INCOME_DISABILITY,
    INCOME_SS,
    INCOME_UNEMPLOYMENT,
    INCOME_STATE_REFUND,
    INCOME_INTEREST_DIVIDENDS,
    INCOME_STOCK_SALE,
    INCOME_ALIMONY,
    INCOME_RENTAL,
    INCOME_PERSONAL_PROPERTY_RENTAL,
    INCOME_SELF_EMPLOYMENT,
    INCOME_GAMBLING,
    INCOME_OTHER,
]

# Client-column sub-question Y/N checkbox pairs for Page 2.
P2_CLIENT_SUBQ_FIELDS: List[str] = [
    INCOME_STOCK_SALE_PRIOR_LOSS_YES,
    INCOME_STOCK_SALE_PRIOR_LOSS_NO,
    INCOME_RENTAL_SHORT_PERSONAL_RESIDENCE_YES,
    INCOME_RENTAL_SHORT_PERSONAL_RESIDENCE_NO,
    INCOME_SELF_EMPLOYMENT_PRIOR_LOSS_YES,
    INCOME_SELF_EMPLOYMENT_PRIOR_LOSS_NO,
]

# Volunteer-column primary checkbox fields for Page 2.
P2_VOL_CHECKBOX_FIELDS: List[str] = [
    VOL_INCOME_W2,
    VOL_INCOME_TIPS,
    VOL_INCOME_1099R,
    VOL_INCOME_QCD,
    VOL_INCOME_DISABILITY,
    VOL_INCOME_SSA,
    VOL_INCOME_1099G,
    VOL_INCOME_STATE_REFUND,
    VOL_INCOME_ITEMIZED_LAST_YEAR,
    VOL_INCOME_ITEMIZED_LAST_YEAR_YES,
    VOL_INCOME_ITEMIZED_LAST_YEAR_NO,
    VOL_INCOME_1099INT,
    VOL_INCOME_1099DIV,
    VOL_INCOME_1099B,
    VOL_INCOME_CAPITAL_LOSS_CARRYOVER,
    VOL_INCOME_CAPITAL_LOSS_CARRYOVER_YES,
    VOL_INCOME_CAPITAL_LOSS_CARRYOVER_NO,
    VOL_INCOME_ALIMONY,
    VOL_INCOME_ALIMONY_EXCLUDED,
    VOL_INCOME_ALIMONY_EXCLUDED_YES,
    VOL_INCOME_ALIMONY_EXCLUDED_NO,
    VOL_INCOME_RENTAL,
    VOL_INCOME_RENTAL_EXPENSE,
    VOL_INCOME_W2G,
    VOL_INCOME_SCHEDULE_C,
    VOL_INCOME_1099MISC,
    VOL_INCOME_1099NEC,
    VOL_INCOME_1099K,
    VOL_INCOME_OTHER_REPORTED_ELSEWHERE,
    VOL_INCOME_SCHEDULE_C_EXPENSES,
    VOL_INCOME_OTHER,
]

# Volunteer-column count / amount / sub text fields for Page 2.
P2_VOL_TEXT_FIELDS: List[str] = [
    VOL_INCOME_W2_COUNT,
    VOL_INCOME_1099R_COUNT,
    VOL_INCOME_QCD_AMOUNT,
    VOL_INCOME_DISABILITY_COUNT,
    VOL_INCOME_SSA_COUNT,
    VOL_INCOME_1099G_COUNT,
    VOL_INCOME_STATE_REFUND_AMOUNT,
    VOL_INCOME_1099INT_COUNT,
    VOL_INCOME_1099DIV_COUNT,
    VOL_INCOME_1099B_COUNT,
    VOL_INCOME_ALIMONY_AMOUNT,
    VOL_INCOME_RENTAL_EXPENSE_AMOUNT,
    VOL_INCOME_W2G_COUNT,
    VOL_INCOME_1099MISC_COUNT,
    VOL_INCOME_1099NEC_COUNT,
    VOL_INCOME_1099K_COUNT,
    VOL_INCOME_SCHEDULE_C_EXPENSES_AMOUNT,
    INCOME_WAGES_JOBS,
]

# Notes column (free-form text, one per row).
P2_NOTE_FIELDS: List[str] = [
    INCOME_NOTE_WAGES,
    INCOME_NOTE_TIPS,
    INCOME_NOTE_RETIREMENT,
    INCOME_NOTE_DISABILITY,
    INCOME_NOTE_SS,
    INCOME_NOTE_UNEMPLOYMENT,
    INCOME_NOTE_STATE_REFUND,
    INCOME_NOTE_INTEREST_DIVIDENDS,
    INCOME_NOTE_STOCK_SALE,
    INCOME_NOTE_ALIMONY,
    INCOME_NOTE_RENTAL,
    INCOME_NOTE_SELF_EMPLOYMENT,
    INCOME_NOTE_GAMBLING,
    INCOME_NOTE_OTHER,
]

# All Page 2 fields (used by the submit handler to enumerate which
# inputs to harvest from the form post).
P2_ALL_FIELDS: List[str] = (
    P2_CLIENT_CHECKBOX_FIELDS
    + P2_CLIENT_SUBQ_FIELDS
    + P2_VOL_CHECKBOX_FIELDS
    + P2_VOL_TEXT_FIELDS
    + P2_NOTE_FIELDS
)

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
# Part III — Expenses & Tax Related Events (Page 3 new template)
# =========================================================================
# Constants for the new IRS-faithful Page 3 mockup. The legacy
# EXPENSE_*_AMOUNT pairs above remain for back-compat with the old
# render path; the new template uses three columns and three sections:
#   - Itemize section: medical, mortgage interest, taxes, charitable.
#   - Other Expenses section: child care, educator, alimony, retirement,
#     student loan.
#   - Tax Related Events section: 12 yes/no events plus volunteer
#     follow-ups.
#
# Naming follows the input ``name`` attributes in
# ``docs/mockups/13614c_page3.html`` so the populator and grader can
# cross-reference them directly.

# --- Section 1: Itemize — client column ---------------------------------
# Reuses the legacy EXPENSE_MEDICAL / EXPENSE_MORTGAGE_INTEREST /
# EXPENSE_CHARITABLE constants. Note: the new template's "taxes"
# row maps to EXPENSE_TAXES_NEW (broader: state income tax + property
# tax + sales tax), distinct from EXPENSE_PROPERTY_TAXES (legacy,
# property only).
EXPENSE_TAXES_NEW = "expense.taxes"

# --- Section 2: Other Expenses — client column --------------------------
# Reuses EXPENSE_CHILD_CARE / EXPENSE_EDUCATOR / EXPENSE_STUDENT_LOAN.
EXPENSE_ALIMONY_PAID = "expense.alimony_paid"
EXPENSE_RETIREMENT_CONTRIB = "expense.retirement_contrib"

# --- Section 3: Tax Related Events — client column ----------------------
EVENT_BROUGHT_PRIOR_RETURN = "event.brought_prior_return"
EVENT_ESTIMATED_PAYMENTS = "event.estimated_payments"
EVENT_EDUCATION = "event.education"
EVENT_ENERGY_HOME = "event.energy_home"
EVENT_HSA = "event.hsa"
EVENT_MARKETPLACE = "event.marketplace"
EVENT_SELL_HOME = "event.sell_home"
EVENT_OTHER_PURCHASE = "event.other_purchase"
EVENT_DEBT_CANCELLED = "event.debt_cancelled"
EVENT_DISASTER_LOSS = "event.disaster_loss"
EVENT_IRS_LETTER = "event.irs_letter"
EVENT_CREDIT_DISALLOWED = "event.credit_disallowed"

# --- Section 1: Itemize — volunteer column ------------------------------
VOL_EXPENSE_ITEMIZED_DEDUCTION = "vol.expense.itemized_deduction"
VOL_EXPENSE_STANDARD_DEDUCTION = "vol.expense.standard_deduction"
VOL_EXPENSE_1098 = "vol.expense.1098"
VOL_EXPENSE_1098_COUNT = "vol.expense.1098.count"

# --- Section 2: Other Expenses — volunteer column -----------------------
VOL_EXPENSE_CHILD_CARE_CREDIT = "vol.expense.child_care_credit"
VOL_EXPENSE_EDUCATOR = "vol.expense.educator"
VOL_EXPENSE_EDUCATOR_AMOUNT = "vol.expense.educator.amount"
VOL_EXPENSE_ALIMONY_PAID = "vol.expense.alimony_paid"
VOL_EXPENSE_ALIMONY_PAID_AMOUNT = "vol.expense.alimony_paid.amount"
VOL_EXPENSE_ALIMONY_ADJUSTMENT_YES = "vol.expense.alimony_adjustment.yes"
VOL_EXPENSE_ALIMONY_ADJUSTMENT_NO = "vol.expense.alimony_adjustment.no"
VOL_EXPENSE_IRA = "vol.expense.ira"
VOL_EXPENSE_1098E = "vol.expense.1098e"

# --- Section 3: Tax Related Events — volunteer column -------------------
VOL_EVENT_PRIOR_RETURN_AVAILABLE = "vol.event.prior_return_available"
VOL_EVENT_PRIOR_REFUND_APPLIED = "vol.event.prior_refund_applied"
VOL_EVENT_PRIOR_REFUND_APPLIED_AMOUNT = "vol.event.prior_refund_applied.amount"
VOL_EVENT_ESTIMATED_PAYMENTS = "vol.event.estimated_payments"
VOL_EVENT_ESTIMATED_PAYMENTS_AMOUNT = "vol.event.estimated_payments.amount"
VOL_EVENT_EDUCATION_CREDIT = "vol.event.education_credit"
VOL_EVENT_TAXABLE_SCHOLARSHIP = "vol.event.taxable_scholarship"
VOL_EVENT_1098T = "vol.event.1098t"
VOL_EVENT_ENERGY_CREDIT = "vol.event.energy_credit"
VOL_EVENT_HSA_CONTRIBUTIONS = "vol.event.hsa_contributions"
VOL_EVENT_HSA_DISTRIBUTIONS = "vol.event.hsa_distributions"
VOL_EVENT_1095A = "vol.event.1095a"
VOL_EVENT_1099A = "vol.event.1099a"
VOL_EVENT_1099S = "vol.event.1099s"
VOL_EVENT_1099C = "vol.event.1099c"
VOL_EVENT_DISASTER_RELIEF_IMPACTS = "vol.event.disaster_relief_impacts"
VOL_EVENT_LITC_REFERRAL = "vol.event.litc_referral"
VOL_EVENT_CREDIT_DISALLOWED = "vol.event.credit_disallowed"
VOL_EVENT_CREDIT_DISALLOWED_YEAR = "vol.event.credit_disallowed.year"
VOL_EVENT_CREDIT_DISALLOWED_REASON = "vol.event.credit_disallowed.reason"
VOL_EVENT_OTHER_PURCHASE_VIN = "vol.event.other_purchase.vin"

# --- Notes column (one per row, free-form, ungraded) --------------------
EXPENSE_NOTE_ITEMIZE = "expense.note.itemize"
EXPENSE_NOTE_CHILD_CARE = "expense.note.child_care"
EXPENSE_NOTE_EDUCATOR = "expense.note.educator"
EXPENSE_NOTE_ALIMONY_PAID = "expense.note.alimony_paid"
EXPENSE_NOTE_RETIREMENT_CONTRIB = "expense.note.retirement_contrib"
EXPENSE_NOTE_STUDENT_LOAN = "expense.note.student_loan"
EVENT_NOTE_BROUGHT_PRIOR_RETURN = "event.note.brought_prior_return"
EVENT_NOTE_ESTIMATED_PAYMENTS = "event.note.estimated_payments"
EVENT_NOTE_EDUCATION = "event.note.education"
EVENT_NOTE_ENERGY_HOME = "event.note.energy_home"
EVENT_NOTE_HSA = "event.note.hsa"
EVENT_NOTE_MARKETPLACE = "event.note.marketplace"
EVENT_NOTE_SELL_HOME = "event.note.sell_home"
EVENT_NOTE_OTHER_PURCHASE = "event.note.other_purchase"
EVENT_NOTE_DEBT_CANCELLED = "event.note.debt_cancelled"
EVENT_NOTE_DISASTER_LOSS = "event.note.disaster_loss"
EVENT_NOTE_IRS_LETTER = "event.note.irs_letter"
EVENT_NOTE_CREDIT_DISALLOWED = "event.note.credit_disallowed"

# --- Aggregations -------------------------------------------------------
# Client-column primary checkboxes for Page 3 (one per row across all
# three sections).
P3_CLIENT_CHECKBOX_FIELDS: List[str] = [
    # Itemize
    EXPENSE_MEDICAL,
    EXPENSE_MORTGAGE_INTEREST,
    EXPENSE_TAXES_NEW,
    EXPENSE_CHARITABLE,
    # Other Expenses
    EXPENSE_CHILD_CARE,
    EXPENSE_EDUCATOR,
    EXPENSE_ALIMONY_PAID,
    EXPENSE_RETIREMENT_CONTRIB,
    EXPENSE_STUDENT_LOAN,
    # Tax Related Events
    EVENT_BROUGHT_PRIOR_RETURN,
    EVENT_ESTIMATED_PAYMENTS,
    EVENT_EDUCATION,
    EVENT_ENERGY_HOME,
    EVENT_HSA,
    EVENT_MARKETPLACE,
    EVENT_SELL_HOME,
    EVENT_OTHER_PURCHASE,
    EVENT_DEBT_CANCELLED,
    EVENT_DISASTER_LOSS,
    EVENT_IRS_LETTER,
    EVENT_CREDIT_DISALLOWED,
]

# Volunteer-column primary checkbox fields for Page 3.
P3_VOL_CHECKBOX_FIELDS: List[str] = [
    VOL_EXPENSE_ITEMIZED_DEDUCTION,
    VOL_EXPENSE_STANDARD_DEDUCTION,
    VOL_EXPENSE_1098,
    VOL_EXPENSE_CHILD_CARE_CREDIT,
    VOL_EXPENSE_EDUCATOR,
    VOL_EXPENSE_ALIMONY_PAID,
    VOL_EXPENSE_ALIMONY_ADJUSTMENT_YES,
    VOL_EXPENSE_ALIMONY_ADJUSTMENT_NO,
    VOL_EXPENSE_IRA,
    VOL_EXPENSE_1098E,
    VOL_EVENT_PRIOR_RETURN_AVAILABLE,
    VOL_EVENT_PRIOR_REFUND_APPLIED,
    VOL_EVENT_ESTIMATED_PAYMENTS,
    VOL_EVENT_EDUCATION_CREDIT,
    VOL_EVENT_TAXABLE_SCHOLARSHIP,
    VOL_EVENT_1098T,
    VOL_EVENT_ENERGY_CREDIT,
    VOL_EVENT_HSA_CONTRIBUTIONS,
    VOL_EVENT_HSA_DISTRIBUTIONS,
    VOL_EVENT_1095A,
    VOL_EVENT_1099A,
    VOL_EVENT_1099S,
    VOL_EVENT_1099C,
    VOL_EVENT_DISASTER_RELIEF_IMPACTS,
    VOL_EVENT_LITC_REFERRAL,
    VOL_EVENT_CREDIT_DISALLOWED,
]

# Volunteer-column count / amount / sub text fields for Page 3.
P3_VOL_TEXT_FIELDS: List[str] = [
    VOL_EXPENSE_1098_COUNT,
    VOL_EXPENSE_EDUCATOR_AMOUNT,
    VOL_EXPENSE_ALIMONY_PAID_AMOUNT,
    VOL_EVENT_PRIOR_REFUND_APPLIED_AMOUNT,
    VOL_EVENT_ESTIMATED_PAYMENTS_AMOUNT,
    VOL_EVENT_CREDIT_DISALLOWED_YEAR,
    VOL_EVENT_CREDIT_DISALLOWED_REASON,
    VOL_EVENT_OTHER_PURCHASE_VIN,
]

# Notes column for Page 3 (free-form text, one per row).
P3_NOTE_FIELDS: List[str] = [
    EXPENSE_NOTE_ITEMIZE,
    EXPENSE_NOTE_CHILD_CARE,
    EXPENSE_NOTE_EDUCATOR,
    EXPENSE_NOTE_ALIMONY_PAID,
    EXPENSE_NOTE_RETIREMENT_CONTRIB,
    EXPENSE_NOTE_STUDENT_LOAN,
    EVENT_NOTE_BROUGHT_PRIOR_RETURN,
    EVENT_NOTE_ESTIMATED_PAYMENTS,
    EVENT_NOTE_EDUCATION,
    EVENT_NOTE_ENERGY_HOME,
    EVENT_NOTE_HSA,
    EVENT_NOTE_MARKETPLACE,
    EVENT_NOTE_SELL_HOME,
    EVENT_NOTE_OTHER_PURCHASE,
    EVENT_NOTE_DEBT_CANCELLED,
    EVENT_NOTE_DISASTER_LOSS,
    EVENT_NOTE_IRS_LETTER,
    EVENT_NOTE_CREDIT_DISALLOWED,
]

# All Page 3 fields (used by the submit handler to enumerate which
# inputs to harvest from the form post).
P3_ALL_FIELDS: List[str] = (
    P3_CLIENT_CHECKBOX_FIELDS
    + P3_VOL_CHECKBOX_FIELDS
    + P3_VOL_TEXT_FIELDS
    + P3_NOTE_FIELDS
)

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

# Page 2 — notes column is free-form (no ground truth), and the
# sub-question Y/N pairs aren't modeled in the household generator yet
# (prior-year capital loss, short-term residence rental, prior-year
# self-employment loss, alimony spouse-excluded, capital-loss carryover,
# itemized-last-year). They render so the form is complete; they're
# surfaced as ungraded until the model catches up.
# Page 3 — notes column is free-form (no ground truth). The bulk of
# the volunteer-side and event-side fields aren't modeled in the
# household generator yet (HSA, 1095-A marketplace, 1099-A/S/C, prior
# refund applied, education credit, energy credit, disaster relief,
# etc.). They render so the form is complete; they're surfaced as
# ungraded until the model catches up.
UNGRADED_FIELDS.extend(P3_NOTE_FIELDS)
UNGRADED_FIELDS.extend([
    EXPENSE_ALIMONY_PAID,
    EXPENSE_RETIREMENT_CONTRIB,
    # Section 3 client checkboxes — no ground truth in the model yet.
    EVENT_BROUGHT_PRIOR_RETURN,
    EVENT_ESTIMATED_PAYMENTS,
    EVENT_EDUCATION,
    EVENT_ENERGY_HOME,
    EVENT_HSA,
    EVENT_MARKETPLACE,
    EVENT_SELL_HOME,
    EVENT_OTHER_PURCHASE,
    EVENT_DEBT_CANCELLED,
    EVENT_DISASTER_LOSS,
    EVENT_IRS_LETTER,
    EVENT_CREDIT_DISALLOWED,
    # Volunteer-side rows for unmodeled topics.
    VOL_EXPENSE_ALIMONY_PAID,
    VOL_EXPENSE_ALIMONY_PAID_AMOUNT,
    VOL_EXPENSE_ALIMONY_ADJUSTMENT_YES,
    VOL_EXPENSE_ALIMONY_ADJUSTMENT_NO,
    VOL_EVENT_PRIOR_RETURN_AVAILABLE,
    VOL_EVENT_PRIOR_REFUND_APPLIED,
    VOL_EVENT_PRIOR_REFUND_APPLIED_AMOUNT,
    VOL_EVENT_ESTIMATED_PAYMENTS,
    VOL_EVENT_ESTIMATED_PAYMENTS_AMOUNT,
    VOL_EVENT_EDUCATION_CREDIT,
    VOL_EVENT_TAXABLE_SCHOLARSHIP,
    VOL_EVENT_1098T,
    VOL_EVENT_ENERGY_CREDIT,
    VOL_EVENT_HSA_CONTRIBUTIONS,
    VOL_EVENT_HSA_DISTRIBUTIONS,
    VOL_EVENT_1095A,
    VOL_EVENT_1099A,
    VOL_EVENT_1099S,
    VOL_EVENT_1099C,
    VOL_EVENT_DISASTER_RELIEF_IMPACTS,
    VOL_EVENT_LITC_REFERRAL,
    VOL_EVENT_CREDIT_DISALLOWED,
    VOL_EVENT_CREDIT_DISALLOWED_YEAR,
    VOL_EVENT_CREDIT_DISALLOWED_REASON,
    VOL_EVENT_OTHER_PURCHASE_VIN,
])

UNGRADED_FIELDS.extend(P2_NOTE_FIELDS)
UNGRADED_FIELDS.extend([
    INCOME_WAGES_JOBS,
    INCOME_STOCK_SALE_PRIOR_LOSS_YES,
    INCOME_STOCK_SALE_PRIOR_LOSS_NO,
    INCOME_RENTAL_SHORT_PERSONAL_RESIDENCE_YES,
    INCOME_RENTAL_SHORT_PERSONAL_RESIDENCE_NO,
    INCOME_SELF_EMPLOYMENT_PRIOR_LOSS_YES,
    INCOME_SELF_EMPLOYMENT_PRIOR_LOSS_NO,
    VOL_INCOME_ITEMIZED_LAST_YEAR,
    VOL_INCOME_ITEMIZED_LAST_YEAR_YES,
    VOL_INCOME_ITEMIZED_LAST_YEAR_NO,
    VOL_INCOME_CAPITAL_LOSS_CARRYOVER,
    VOL_INCOME_CAPITAL_LOSS_CARRYOVER_YES,
    VOL_INCOME_CAPITAL_LOSS_CARRYOVER_NO,
    VOL_INCOME_ALIMONY_EXCLUDED,
    VOL_INCOME_ALIMONY_EXCLUDED_YES,
    VOL_INCOME_ALIMONY_EXCLUDED_NO,
    VOL_INCOME_OTHER_REPORTED_ELSEWHERE,
])

# Part I fields only (Sections A–F: personal info, address, spouse, dependents)
PART1_FIELDS: List[str] = TEXT_FIELDS + CHECKBOX_FIELDS + [FILING_STATUS]

# Part II fields only. Includes both the legacy INCOME_*_AMOUNT pairs
# (still referenced by old render paths and grader logic) and the
# Page 2 new-template namespace; deduplicated via dict.fromkeys to
# preserve order while dropping shared identifiers (e.g. INCOME_WAGES).
PART2_FIELDS: List[str] = list(dict.fromkeys(
    INCOME_CHECKBOX_FIELDS + INCOME_AMOUNT_FIELDS + P2_ALL_FIELDS
))

# Part III fields only. Includes both the legacy EXPENSE_*_AMOUNT pairs
# (still referenced by old render paths and grader logic) and the
# Page 3 new-template namespace (expense.* + event.* + vol.expense.* +
# vol.event.*); deduplicated via dict.fromkeys to preserve order while
# dropping shared identifiers (e.g. EXPENSE_MEDICAL).
PART3_FIELDS: List[str] = list(dict.fromkeys(
    EXPENSE_CHECKBOX_FIELDS
    + EXPENSE_AMOUNT_FIELDS
    + [EXPENSE_DEDUCTION_TYPE]
    + P3_ALL_FIELDS
))

# All field names combined
ALL_FIELDS: List[str] = PART1_FIELDS + PART2_FIELDS + PART3_FIELDS
