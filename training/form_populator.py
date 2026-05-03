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
from typing import Any, Dict, List, Optional

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
    DEP_DISABLED,
    DEP_DOB,
    DEP_IPPIN,
    DEP_MARITAL_EOY,
    DEP_MONTHS,
    DEP_NAME,
    DEP_RELATIONSHIP,
    DEP_RESIDENT,
    DEP_SINGLE_OR_MARRIED,
    DEP_STUDENT,
    DEP_US_CITIZEN,
    FILER_DIGITAL_ASSETS,
    FILER_DISABLED,
    FILER_FULL_TIME_STUDENT,
    FILER_IPPIN,
    FILER_LEGALLY_BLIND,
    FILER_ON_VISA,
    FILING_STATUS,
    FS_HOH,
    FS_MFJ,
    FS_MFS,
    FS_QSS,
    FS_SINGLE,
    INCOME_DIVIDENDS,
    INCOME_DIVIDENDS_AMOUNT,
    INCOME_INTEREST,
    INCOME_INTEREST_AMOUNT,
    INCOME_INTEREST_DIVIDENDS,
    INCOME_OTHER,
    INCOME_RETIREMENT,
    INCOME_RETIREMENT_AMOUNT,
    INCOME_SELF_EMPLOYMENT,
    INCOME_SELF_EMPLOYMENT_AMOUNT,
    INCOME_SOCIAL_SECURITY,
    INCOME_SOCIAL_SECURITY_AMOUNT,
    INCOME_SS,
    INCOME_TOTAL,
    INCOME_WAGES,
    INCOME_WAGES_AMOUNT,
    VOL_INCOME_1099B,
    VOL_INCOME_1099DIV,
    VOL_INCOME_1099DIV_COUNT,
    VOL_INCOME_1099G,
    VOL_INCOME_1099INT,
    VOL_INCOME_1099INT_COUNT,
    VOL_INCOME_1099K,
    VOL_INCOME_1099MISC,
    VOL_INCOME_1099NEC,
    VOL_INCOME_1099NEC_COUNT,
    VOL_INCOME_1099R,
    VOL_INCOME_1099R_COUNT,
    VOL_INCOME_SCHEDULE_C,
    VOL_INCOME_SSA,
    VOL_INCOME_SSA_COUNT,
    VOL_INCOME_W2,
    VOL_INCOME_W2_COUNT,
    MARITAL_DIVORCE_DATE,
    MARITAL_DIVORCED,
    MARITAL_LIVED_APART_NO,
    MARITAL_LIVED_APART_YES,
    MARITAL_MARRIED,
    MARITAL_MARRIED_EOY_NO,
    MARITAL_MARRIED_EOY_YES,
    MARITAL_NEVER_MARRIED,
    MARITAL_SEPARATED,
    MARITAL_SEPARATION_DATE,
    MARITAL_SPOUSE_DEATH_YEAR,
    MARITAL_WIDOWED,
    MAX_DEPENDENTS,
    NOT_CLAIMED_AS_DEPENDENT,
    NOT_PRIOR_YEAR_DEPENDENT,
    SPOUSE_DIGITAL_ASSETS,
    SPOUSE_DISABLED,
    SPOUSE_DOB,
    SPOUSE_FIRST_NAME,
    SPOUSE_FULL_TIME_STUDENT,
    SPOUSE_IPPIN,
    SPOUSE_JOB_TITLE,
    SPOUSE_LAST_NAME,
    SPOUSE_LEGALLY_BLIND,
    SPOUSE_MIDDLE_INITIAL,
    SPOUSE_ON_VISA,
    SPOUSE_PHONE,
    SPOUSE_SSN,
    SPOUSE_US_CITIZEN,
    STATUS_BLIND_NO,
    STATUS_CITIZEN_NO,
    STATUS_DIGITAL_NO,
    STATUS_DISABLED_NO,
    STATUS_IPPIN_NO,
    STATUS_STUDENT_NO,
    STATUS_VISA_NO,
    TWO_STATES_NO,
    TWO_STATES_YES,
    YOU_DOB,
    YOU_EMAIL,
    YOU_FIRST_NAME,
    YOU_JOB_TITLE,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_PHONE,
    YOU_SSN,
    YOU_US_CITIZEN,
    EXPENSE_MORTGAGE_INTEREST,
    EXPENSE_MORTGAGE_INTEREST_AMOUNT,
    EXPENSE_PROPERTY_TAXES,
    EXPENSE_PROPERTY_TAXES_AMOUNT,
    EXPENSE_MEDICAL,
    EXPENSE_CHARITABLE,
    EXPENSE_CHARITABLE_AMOUNT,
    EXPENSE_DEDUCTION_TYPE,
    EXPENSE_STUDENT_LOAN,
    EXPENSE_STUDENT_LOAN_AMOUNT,
    EXPENSE_CHILD_CARE,
    EXPENSE_CHILD_CARE_AMOUNT,
    EXPENSE_EDUCATOR,
    EXPENSE_EDUCATOR_AMOUNT,
    EXPENSE_IRA,
    EXPENSE_IRA_AMOUNT,
    EXPENSE_EDUCATION,
    EXPENSE_EDUCATION_AMOUNT,
    DEDUCTION_TYPE_STANDARD,
    DEDUCTION_TYPE_ITEMIZED,
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


def _yn(flag: bool) -> str:
    """Render a one-letter Y/N value for a dependent text cell."""
    return "Y" if flag else "N"


def _yn_or_blank(flag: bool) -> str:
    """Render Y when true, blank when false (template style for some cells)."""
    return "Y" if flag else ""


def build_p1_field_values(household: Household) -> Dict[str, Any]:
    """Build a dict of {field_name: value} for the new Page 1 template.

    Returns a mixed-type dict:
    - **strings** for text inputs (names, dates, addresses, dependent
      Y/N text cells).
    - **booleans** for checkboxes (True == checked).

    Different shape from :func:`build_field_values` (the legacy answer-key
    builder), which emits strings everywhere. The new template's Jinja
    partial reads booleans for checkboxes (``{% if p1.get('X') %}checked
    {% endif %}``) and strings for text fields (``value="{{ p1.get('X',
    '') }}"``); a string in a checkbox slot would always render as
    ``checked`` regardless of value.

    Player-input-only fields (refund/payment/language/election checkboxes,
    the volunteer columns, the two-states question) are intentionally
    *not* emitted — they default to unchecked / blank for the player to
    fill in.

    Args:
        household: Household with PII fully populated.

    Returns:
        Dict keyed by the new template's input names, ready to pass into
        the Jinja partial as ``p1=build_p1_field_values(scenario.household)``.
    """
    p1: Dict[str, Any] = {}
    filer = household.get_householder()
    spouse = household.get_spouse()
    has_spouse = spouse is not None

    # =================================================================
    # Section 4: Filer / Spouse personal info, address, contact.
    # =================================================================
    if filer:
        p1[YOU_FIRST_NAME] = filer.legal_first_name
        p1[YOU_MIDDLE_INITIAL] = _middle_initial(filer.legal_middle_name)
        p1[YOU_LAST_NAME] = filer.legal_last_name
        p1[YOU_DOB] = _format_date(filer.dob)
        p1[YOU_JOB_TITLE] = filer.occupation_title or ""
        p1[YOU_PHONE] = filer.phone
        p1[YOU_EMAIL] = filer.email

    if has_spouse:
        p1[SPOUSE_FIRST_NAME] = spouse.legal_first_name
        p1[SPOUSE_MIDDLE_INITIAL] = _middle_initial(spouse.legal_middle_name)
        p1[SPOUSE_LAST_NAME] = spouse.legal_last_name
        p1[SPOUSE_DOB] = _format_date(spouse.dob)
        p1[SPOUSE_JOB_TITLE] = spouse.occupation_title or ""
        p1[SPOUSE_PHONE] = spouse.phone

    if household.address:
        addr = household.address
        p1[ADDR_STREET] = addr.street
        p1[ADDR_APT] = addr.apt or ""
        p1[ADDR_CITY] = addr.city
        p1[ADDR_STATE] = addr.state
        p1[ADDR_ZIP] = addr.zip_code

    # Two-states follow-up question — drive off the household flag
    # (defaults to False, so two_states_no checks by default).
    p1[TWO_STATES_YES] = household.lived_in_two_states
    p1[TWO_STATES_NO] = not household.lived_in_two_states

    # =================================================================
    # Section 5: Can anyone else claim you?
    # =================================================================
    can_be_claimed = bool(filer and filer.can_be_claimed)
    p1[CLAIMED_AS_DEPENDENT] = can_be_claimed
    p1[NOT_CLAIMED_AS_DEPENDENT] = not can_be_claimed

    # =================================================================
    # Section 6: Status checkboxes (You / Spouse / No trios).
    # The "no" cell is checked when neither person has the flag.
    # =================================================================
    def _trio(filer_field: str, spouse_field: str, no_field: str,
              filer_flag: bool, spouse_flag: bool) -> None:
        p1[filer_field] = filer_flag
        p1[spouse_field] = has_spouse and spouse_flag
        p1[no_field] = (not filer_flag) and not (has_spouse and spouse_flag)

    f_citizen = bool(filer and filer.us_citizen)
    s_citizen = bool(spouse and spouse.us_citizen)
    _trio(YOU_US_CITIZEN, SPOUSE_US_CITIZEN, STATUS_CITIZEN_NO,
          f_citizen, s_citizen)

    _trio(FILER_ON_VISA, SPOUSE_ON_VISA, STATUS_VISA_NO,
          bool(filer and filer.on_visa),
          bool(spouse and spouse.on_visa))

    _trio(FILER_FULL_TIME_STUDENT, SPOUSE_FULL_TIME_STUDENT, STATUS_STUDENT_NO,
          bool(filer and filer.is_full_time_student),
          bool(spouse and spouse.is_full_time_student))

    _trio(FILER_LEGALLY_BLIND, SPOUSE_LEGALLY_BLIND, STATUS_BLIND_NO,
          bool(filer and filer.legally_blind),
          bool(spouse and spouse.legally_blind))

    _trio(FILER_DISABLED, SPOUSE_DISABLED, STATUS_DISABLED_NO,
          bool(filer and filer.has_disability),
          bool(spouse and spouse.has_disability))

    _trio(FILER_IPPIN, SPOUSE_IPPIN, STATUS_IPPIN_NO,
          bool(filer and filer.has_ippin),
          bool(spouse and spouse.has_ippin))

    # Digital assets is a household-level flag (the question is "owners
    # or holders of any digital assets"); attribute it to the filer
    # primarily, mirror to spouse when present and the household has
    # the flag.
    digital = household.has_digital_assets
    _trio(FILER_DIGITAL_ASSETS, SPOUSE_DIGITAL_ASSETS, STATUS_DIGITAL_NO,
          digital, digital)

    # =================================================================
    # Section 7: Refund / payment preferences.
    # Section 8: Language preference.
    # Section 9: Presidential Election Campaign Fund.
    # All player-input only — leave blank.
    # =================================================================

    # =================================================================
    # Section 10: Marital status.
    # Drives off household.is_married() and the filer's marital_history
    # (added in Phase 1A). For most generated scenarios, marital_history
    # is "" and we infer never-married vs married from is_married().
    # =================================================================
    is_married = household.is_married()
    history = (filer.marital_history if filer else "").lower()

    p1[MARITAL_MARRIED] = is_married
    p1[MARITAL_NEVER_MARRIED] = (not is_married) and history in ("", "never")
    p1[MARITAL_DIVORCED] = history == "divorced"
    p1[MARITAL_SEPARATED] = history == "separated"
    p1[MARITAL_WIDOWED] = history == "widowed"

    # End-of-year follow-ups apply only when married. Default: still
    # married on Dec 31, did not live apart for the last six months.
    p1[MARITAL_MARRIED_EOY_YES] = is_married
    p1[MARITAL_MARRIED_EOY_NO] = False
    p1[MARITAL_LIVED_APART_YES] = is_married and household.spouses_lived_apart_h2
    p1[MARITAL_LIVED_APART_NO] = is_married and not household.spouses_lived_apart_h2

    p1[MARITAL_DIVORCE_DATE] = (
        household.divorce_date.strftime("%m/%d/%Y")
        if household.divorce_date else ""
    )
    p1[MARITAL_SEPARATION_DATE] = (
        household.separation_date.strftime("%m/%d/%Y")
        if household.separation_date else ""
    )
    p1[MARITAL_SPOUSE_DEATH_YEAR] = (
        str(household.spouse_death_year)
        if household.spouse_death_year else ""
    )

    # =================================================================
    # Section 11: Dependents grid — client column only.
    # The five "vol_*" volunteer columns are NOT emitted; the player
    # fills them. Y/N/S/M cells render as text inputs with one-letter
    # values to match the template hints.
    # =================================================================
    for i, dep in enumerate(_get_dependents(household)):
        p1[dep_field(i, DEP_NAME)] = dep.full_legal_name()
        p1[dep_field(i, DEP_DOB)] = _format_date(dep.dob)
        p1[dep_field(i, DEP_RELATIONSHIP)] = _relationship_label(dep)
        p1[dep_field(i, DEP_MONTHS)] = str(dep.months_in_home)
        # Children are S; adult dependents could be M but the model
        # doesn't distinguish today, so default S.
        p1[dep_field(i, DEP_MARITAL_EOY)] = "S"
        p1[dep_field(i, DEP_US_CITIZEN)] = _yn(dep.us_citizen)
        # Resident of US/Canada/Mexico — model has no field, default Y.
        p1[dep_field(i, DEP_RESIDENT)] = "Y"
        p1[dep_field(i, DEP_STUDENT)] = _yn_or_blank(dep.is_full_time_student)
        p1[dep_field(i, DEP_DISABLED)] = _yn_or_blank(dep.has_disability)
        p1[dep_field(i, DEP_IPPIN)] = _yn_or_blank(dep.has_ippin)

    return p1


def build_p2_field_values(household: Household) -> Dict[str, Any]:
    """Build a dict of {field_name: value} for the new Page 2 template.

    Same shape as :func:`build_p1_field_values`: booleans for checkboxes,
    strings for text inputs (counts, amounts). Only the rows whose
    underlying data is actually modeled today get populated; the rest
    (tips, separate disability $, unemployment, state refund, stock
    sale, alimony, rental, gambling) are left out so the player fills
    them in. Notes-column fields are always blank (free-form, ungraded).

    Income is aggregated across the filer + spouse — dependents' income
    doesn't roll up onto Part II of the joint return.

    Args:
        household: Household with income documents populated.

    Returns:
        Dict keyed by Page 2 input names, ready to pass into the Jinja
        partial as ``p2=build_p2_field_values(scenario.household)``.
    """
    p2: Dict[str, Any] = {}

    filers: List[Person] = []
    filer = household.get_householder()
    spouse = household.get_spouse()
    if filer:
        filers.append(filer)
    if spouse:
        filers.append(spouse)

    # ---- Aggregate amounts and document counts across filers ----------
    total_wages = sum(p.wage_income for p in filers)
    total_interest = sum(p.interest_income for p in filers)
    total_dividends = sum(p.dividend_income for p in filers)
    total_ss = sum(p.social_security_income for p in filers)
    total_retirement = sum(p.retirement_income for p in filers)
    total_se = sum(p.self_employment_income for p in filers)
    total_other = sum(p.other_income for p in filers)

    w2_count = sum(len(p.w2s) for p in filers)
    int_count = sum(len(p.form_1099_ints) for p in filers)
    div_count = sum(len(p.form_1099_divs) for p in filers)
    r_count = sum(len(p.form_1099_rs) for p in filers)
    nec_count = sum(len(p.form_1099_necs) for p in filers)
    ssa_count = sum(1 for p in filers if p.ssa_1099 is not None)

    # ---- Row 1: wages -------------------------------------------------
    has_wages = total_wages > 0
    p2[INCOME_WAGES] = has_wages
    p2[VOL_INCOME_W2] = has_wages
    p2[VOL_INCOME_W2_COUNT] = str(w2_count) if w2_count else ""

    # ---- Row 3: retirement (1099-R) -----------------------------------
    has_retirement = total_retirement > 0
    p2[INCOME_RETIREMENT] = has_retirement
    p2[VOL_INCOME_1099R] = has_retirement
    p2[VOL_INCOME_1099R_COUNT] = str(r_count) if r_count else ""

    # ---- Row 5: Social Security (SSA-1099) ----------------------------
    has_ss = total_ss > 0
    p2[INCOME_SS] = has_ss
    p2[VOL_INCOME_SSA] = has_ss
    p2[VOL_INCOME_SSA_COUNT] = str(ssa_count) if ssa_count else ""

    # ---- Row 8: interest + dividends (combined client checkbox) -------
    has_int_div = total_interest > 0 or total_dividends > 0
    p2[INCOME_INTEREST_DIVIDENDS] = has_int_div
    # Keep the legacy split flags in sync so callers reading either
    # namespace see the same answer key.
    p2[INCOME_INTEREST] = total_interest > 0
    p2[INCOME_DIVIDENDS] = total_dividends > 0
    p2[VOL_INCOME_1099INT] = total_interest > 0
    p2[VOL_INCOME_1099INT_COUNT] = str(int_count) if int_count else ""
    p2[VOL_INCOME_1099DIV] = total_dividends > 0
    p2[VOL_INCOME_1099DIV_COUNT] = str(div_count) if div_count else ""

    # ---- Row 9: stock sale (1099-B) ----------------------------------
    # No 1099-B model yet; leave the volunteer 1099-B checkbox alone
    # (player input). Listed here for completeness so future model work
    # has an obvious place to land.
    p2[VOL_INCOME_1099B] = False

    # ---- Row 12: self-employment (Schedule C + 1099-NEC family) -------
    has_se = total_se > 0
    p2[INCOME_SELF_EMPLOYMENT] = has_se
    p2[VOL_INCOME_SCHEDULE_C] = has_se
    p2[VOL_INCOME_1099NEC] = has_se and nec_count > 0
    p2[VOL_INCOME_1099NEC_COUNT] = str(nec_count) if nec_count else ""
    # 1099-MISC and 1099-K aren't modeled; leave unchecked.
    p2[VOL_INCOME_1099MISC] = False
    p2[VOL_INCOME_1099K] = False

    # ---- Row 6: unemployment (1099-G) — not modeled, leave unchecked --
    p2[VOL_INCOME_1099G] = False

    # ---- Row 14: other ------------------------------------------------
    p2[INCOME_OTHER] = total_other > 0

    # Legacy SOCIAL_SECURITY identifier kept in sync for callers that
    # still read it (the new template's INCOME_SS supersedes it).
    p2[INCOME_SOCIAL_SECURITY] = has_ss

    # Optional aggregate total (legacy field; kept for callers/grader
    # paths that read it).
    grand_total = (
        total_wages + total_interest + total_dividends
        + total_ss + total_retirement + total_se + total_other
    )
    if grand_total > 0:
        p2[INCOME_TOTAL] = str(grand_total)

    # Volunteer count/amount fields whose source isn't modeled (tips,
    # disability $, state refund $, alimony $, rental $, etc.) and the
    # 14 free-form notes are intentionally not emitted — they default
    # to blank in the template so the player fills them in.

    return p2


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
        values[dep_field(i, DEP_NAME)] = dep.full_legal_name()
        values[dep_field(i, DEP_DOB)] = _format_date(dep.dob)
        values[dep_field(i, DEP_RELATIONSHIP)] = _relationship_label(dep)
        values[dep_field(i, DEP_MONTHS)] = str(dep.months_in_home)
        # Children are single by default
        values[dep_field(i, DEP_SINGLE_OR_MARRIED)] = "Yes"
        # US citizen — default true for most VITA scenarios
        values[dep_field(i, DEP_US_CITIZEN)] = "Yes"
        values[dep_field(i, DEP_STUDENT)] = (
            "Yes" if dep.is_full_time_student else "No"
        )
        values[dep_field(i, DEP_DISABLED)] = (
            "Yes" if dep.has_disability else "No"
        )
        # Volunteer columns scored in this version (Page 1 Section 11).
        # Mirror the rules in grader.build_form_answers so this
        # populator's output stays a valid "perfect submission" against
        # the answer key. The two ungraded columns
        # (vol_qc_other, vol_self_support) are intentionally not
        # emitted — they live in UNGRADED_FIELDS.
        income_under = (
            dep.total_income() < 5200
            if hasattr(dep, "total_income") else True
        )
        values[dep_field(i, "vol_income_under")] = (
            "Yes" if income_under else "No"
        )
        values[dep_field(i, "vol_support")] = (
            "Yes" if dep.months_in_home >= 6 else "No"
        )
        values[dep_field(i, "vol_home_cost")] = (
            "Yes" if dep.months_in_home >= 6 else "No"
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

    # =================================================================
    # Part II: Income
    # =================================================================
    _populate_income_fields(values, household)

    # =================================================================
    # Part III: Expenses, Deductions & Credits
    # =================================================================
    _populate_expense_fields(values, household)

    return values


def _populate_income_fields(
    values: Dict[str, str], household: Household
) -> None:
    """Populate Part II income fields from all household members' documents.

    Sums income across the primary filer and spouse (the two people
    whose income appears on the joint return). Dependents' income is
    not included on the 13614-C Part II.

    Args:
        values: Field dict to populate (mutated in place).
        household: Household with income documents populated.
    """
    filers = []
    householder = household.get_householder()
    spouse = household.get_spouse()
    if householder:
        filers.append(householder)
    if spouse:
        filers.append(spouse)

    total_wages = 0
    total_interest = 0
    total_dividends = 0
    total_ss = 0
    total_retirement = 0
    total_se = 0

    for person in filers:
        total_wages += person.wage_income
        total_interest += person.interest_income
        total_dividends += person.dividend_income
        total_ss += person.social_security_income
        total_retirement += person.retirement_income
        total_se += person.self_employment_income

    if total_wages > 0:
        values[INCOME_WAGES] = "Yes"
        values[INCOME_WAGES_AMOUNT] = str(total_wages)
    else:
        values[INCOME_WAGES] = "No"

    if total_interest > 0:
        values[INCOME_INTEREST] = "Yes"
        values[INCOME_INTEREST_AMOUNT] = str(total_interest)
    else:
        values[INCOME_INTEREST] = "No"

    if total_dividends > 0:
        values[INCOME_DIVIDENDS] = "Yes"
        values[INCOME_DIVIDENDS_AMOUNT] = str(total_dividends)
    else:
        values[INCOME_DIVIDENDS] = "No"

    if total_ss > 0:
        values[INCOME_SOCIAL_SECURITY] = "Yes"
        values[INCOME_SOCIAL_SECURITY_AMOUNT] = str(total_ss)
    else:
        values[INCOME_SOCIAL_SECURITY] = "No"

    if total_retirement > 0:
        values[INCOME_RETIREMENT] = "Yes"
        values[INCOME_RETIREMENT_AMOUNT] = str(total_retirement)
    else:
        values[INCOME_RETIREMENT] = "No"

    if total_se > 0:
        values[INCOME_SELF_EMPLOYMENT] = "Yes"
        values[INCOME_SELF_EMPLOYMENT_AMOUNT] = str(total_se)
    else:
        values[INCOME_SELF_EMPLOYMENT] = "No"

    total = total_wages + total_interest + total_dividends + total_ss + total_retirement + total_se
    if total > 0:
        values[INCOME_TOTAL] = str(total)

    # Mirror the grader's new Page 2 namespace entries so a submission
    # built from this populator (used as a "perfect submission" in
    # tests) still grades 100% against the extended answer key.
    w2_count = sum(len(p.w2s) for p in filers)
    int_count = sum(len(p.form_1099_ints) for p in filers)
    div_count = sum(len(p.form_1099_divs) for p in filers)
    r_count = sum(len(p.form_1099_rs) for p in filers)
    nec_count = sum(len(p.form_1099_necs) for p in filers)
    ssa_count = sum(1 for p in filers if p.ssa_1099 is not None)
    total_other = sum(p.other_income for p in filers)

    from training.form_fields import (
        INCOME_INTEREST_DIVIDENDS,
        INCOME_OTHER,
        INCOME_SS,
        VOL_INCOME_1099DIV,
        VOL_INCOME_1099DIV_COUNT,
        VOL_INCOME_1099INT,
        VOL_INCOME_1099INT_COUNT,
        VOL_INCOME_1099NEC,
        VOL_INCOME_1099NEC_COUNT,
        VOL_INCOME_1099R,
        VOL_INCOME_1099R_COUNT,
        VOL_INCOME_SCHEDULE_C,
        VOL_INCOME_SSA,
        VOL_INCOME_SSA_COUNT,
        VOL_INCOME_W2,
        VOL_INCOME_W2_COUNT,
    )
    values[INCOME_WAGES] = "Yes" if total_wages > 0 else "No"
    values[VOL_INCOME_W2] = "Yes" if total_wages > 0 else "No"
    if w2_count:
        values[VOL_INCOME_W2_COUNT] = str(w2_count)
    values[VOL_INCOME_1099R] = "Yes" if total_retirement > 0 else "No"
    if r_count:
        values[VOL_INCOME_1099R_COUNT] = str(r_count)
    values[INCOME_SS] = "Yes" if total_ss > 0 else "No"
    values[VOL_INCOME_SSA] = "Yes" if total_ss > 0 else "No"
    if ssa_count:
        values[VOL_INCOME_SSA_COUNT] = str(ssa_count)
    has_int_div = total_interest > 0 or total_dividends > 0
    values[INCOME_INTEREST_DIVIDENDS] = "Yes" if has_int_div else "No"
    values[VOL_INCOME_1099INT] = "Yes" if total_interest > 0 else "No"
    values[VOL_INCOME_1099DIV] = "Yes" if total_dividends > 0 else "No"
    if int_count:
        values[VOL_INCOME_1099INT_COUNT] = str(int_count)
    if div_count:
        values[VOL_INCOME_1099DIV_COUNT] = str(div_count)
    values[VOL_INCOME_SCHEDULE_C] = "Yes" if total_se > 0 else "No"
    values[VOL_INCOME_1099NEC] = "Yes" if (total_se > 0 and nec_count > 0) else "No"
    if nec_count:
        values[VOL_INCOME_1099NEC_COUNT] = str(nec_count)
    values[INCOME_OTHER] = "Yes" if total_other > 0 else "No"


def _populate_expense_fields(
    values: Dict[str, str], household: Household,
) -> None:
    """Populate Part III expense/deduction fields from household data.

    Args:
        values: Field dict to populate (mutated in place).
        household: Household with expense data populated.
    """
    if household.mortgage_interest > 0:
        values[EXPENSE_MORTGAGE_INTEREST] = "Yes"
        values[EXPENSE_MORTGAGE_INTEREST_AMOUNT] = str(household.mortgage_interest)
    else:
        values[EXPENSE_MORTGAGE_INTEREST] = "No"

    if household.property_taxes > 0:
        values[EXPENSE_PROPERTY_TAXES] = "Yes"
        values[EXPENSE_PROPERTY_TAXES_AMOUNT] = str(household.property_taxes)
    else:
        values[EXPENSE_PROPERTY_TAXES] = "No"

    if household.medical_expenses > 0:
        values[EXPENSE_MEDICAL] = "Yes"
    else:
        values[EXPENSE_MEDICAL] = "No"

    if household.charitable_contributions > 0:
        values[EXPENSE_CHARITABLE] = "Yes"
        values[EXPENSE_CHARITABLE_AMOUNT] = str(household.charitable_contributions)
    else:
        values[EXPENSE_CHARITABLE] = "No"

    values[EXPENSE_DEDUCTION_TYPE] = (
        DEDUCTION_TYPE_STANDARD
        if household.uses_standard_deduction
        else DEDUCTION_TYPE_ITEMIZED
    )

    filers = []
    householder = household.get_householder()
    spouse = household.get_spouse()
    if householder:
        filers.append(householder)
    if spouse:
        filers.append(spouse)

    total_student_loan = sum(p.student_loan_interest for p in filers)
    if total_student_loan > 0:
        values[EXPENSE_STUDENT_LOAN] = "Yes"
        values[EXPENSE_STUDENT_LOAN_AMOUNT] = str(total_student_loan)
    else:
        values[EXPENSE_STUDENT_LOAN] = "No"

    total_educator = sum(p.educator_expenses for p in filers)
    if total_educator > 0:
        values[EXPENSE_EDUCATOR] = "Yes"
        values[EXPENSE_EDUCATOR_AMOUNT] = str(total_educator)
    else:
        values[EXPENSE_EDUCATOR] = "No"

    total_ira = sum(p.ira_contributions for p in filers)
    if total_ira > 0:
        values[EXPENSE_IRA] = "Yes"
        values[EXPENSE_IRA_AMOUNT] = str(total_ira)
    else:
        values[EXPENSE_IRA] = "No"

    if household.child_care_expenses > 0:
        values[EXPENSE_CHILD_CARE] = "Yes"
        values[EXPENSE_CHILD_CARE_AMOUNT] = str(household.child_care_expenses)
    else:
        values[EXPENSE_CHILD_CARE] = "No"

    if household.education_expenses > 0:
        values[EXPENSE_EDUCATION] = "Yes"
        values[EXPENSE_EDUCATION_AMOUNT] = str(household.education_expenses)
    else:
        values[EXPENSE_EDUCATION] = "No"
