"""
Grader — compares student submissions to ground truth.

Mode 1 (intake): Field-by-field comparison of submitted form values against
    the pre-computed form_answers stored in GroundTruth.
Mode 2 (verify): Compare flagged errors vs injected error manifest.
"""

import logging
from typing import Dict, List, Optional

from generator.models import (
    GradingResult,
    Household,
    InjectedError,
    Person,
    RelationshipType,
)
from tax_core.ground_truth import GroundTruth
from training.form_fields import (
    ADDR_CITY,
    ADDR_STATE,
    ADDR_STREET,
    ADDR_ZIP,
    ADDR_APT,
    CLAIMED_AS_DEPENDENT,
    DEDUCTION_TYPE_ITEMIZED,
    DEDUCTION_TYPE_STANDARD,
    DEP_DISABLED,
    DEP_DOB,
    DEP_NAME,
    DEP_MONTHS,
    DEP_RELATIONSHIP,
    DEP_SINGLE_OR_MARRIED,
    DEP_STUDENT,
    DEP_US_CITIZEN,
    DEP_VOL_HOME_COST,
    DEP_VOL_INCOME_UNDER,
    DEP_VOL_SUPPORT,
    UNGRADED_FIELDS,
    EXPENSE_CHARITABLE,
    EXPENSE_CHARITABLE_AMOUNT,
    EXPENSE_CHILD_CARE,
    EXPENSE_CHILD_CARE_AMOUNT,
    EXPENSE_DEDUCTION_TYPE,
    EXPENSE_EDUCATION,
    EXPENSE_EDUCATION_AMOUNT,
    EXPENSE_EDUCATOR,
    EXPENSE_EDUCATOR_AMOUNT,
    EXPENSE_IRA,
    EXPENSE_IRA_AMOUNT,
    EXPENSE_MEDICAL,
    EXPENSE_MORTGAGE_INTEREST,
    EXPENSE_MORTGAGE_INTEREST_AMOUNT,
    EXPENSE_PROPERTY_TAXES,
    EXPENSE_PROPERTY_TAXES_AMOUNT,
    EXPENSE_STUDENT_LOAN,
    EXPENSE_STUDENT_LOAN_AMOUNT,
    FILING_STATUS,
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
    MAX_DEPENDENTS,
    NOT_CLAIMED_AS_DEPENDENT,
    SPOUSE_DOB,
    SPOUSE_FIRST_NAME,
    SPOUSE_LAST_NAME,
    SPOUSE_MIDDLE_INITIAL,
    SPOUSE_SSN,
    YOU_DOB,
    YOU_EMAIL,
    YOU_FIRST_NAME,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_PHONE,
    YOU_SSN,
    YOU_US_CITIZEN,
    dep_field,
)

logger = logging.getLogger(__name__)

# Stored ground_truth keys that exist only in the pre-Phase-1B namespace.
# Detecting any of these in a stored answer key means the scenario hasn't
# been migrated to the new ``filer.*`` / ``dep.{i}.name`` namespace and
# would silently zero-score Page 1. Run scripts/migrate_p1_field_names.py.
_PRE_RENAME_KEY_INDICATORS: frozenset = frozenset({
    "you.first_name",
    "you.last_name",
    "dep.0.first_name",
    "dep.0.last_name",
    "additional.claimed_as_dep",
    "additional.not_claimed_as_dep",
})


def _check_form_answers_migrated(form_answers: Dict[str, str]) -> None:
    """Refuse to grade a stored answer key that uses the old namespace.

    Pre-Phase-1B scenarios have ``ground_truth.form_answers`` keyed by
    ``you.*`` / split-name dependents / ``additional.*``. After 1B the
    grader compares against the new namespace; without migration every
    Page 1 field would silently fail to match. Fail loud instead.
    """
    legacy = _PRE_RENAME_KEY_INDICATORS & form_answers.keys()
    if legacy:
        sample = ", ".join(sorted(legacy)[:3])
        raise ValueError(
            "Stored scenario uses pre-Phase-1B field names "
            f"(saw {sample}). Run scripts/migrate_p1_field_names.py "
            "to regenerate ground_truth before grading."
        )


_DEPENDENT_RELATIONSHIPS: Dict[str, str] = {
    "biological_child": "Son/Daughter",
    "adopted_child": "Son/Daughter",
    "stepchild": "Stepchild",
    "grandchild": "Grandchild",
    "sibling": "Sibling",
    "parent": "Parent",
    "other_relative": "Other",
}


# =========================================================================
# Answer key extraction
# =========================================================================

def _format_dob(person: Person) -> str:
    """Format a Person's DOB as MM/DD/YYYY for form comparison."""
    if person.dob is None:
        return ""
    return person.dob.strftime("%m/%d/%Y")


def _middle_initial(person: Person) -> str:
    """Extract first letter of middle name, or empty string."""
    if person.legal_middle_name:
        return person.legal_middle_name[0].upper()
    return ""


def build_form_answers(household: Household) -> Dict[str, str]:
    """Build expected form field values from a Household.

    Called once at scenario generation time; the result is stored in
    GroundTruth.form_answers. The grader reads from the stored dict
    and never recomputes.

    Args:
        household: The original (unmodified) Household.

    Returns:
        Dict mapping form field names to expected string values.
    """
    key: Dict[str, str] = {}
    householder = household.get_householder()
    if not householder:
        return key

    # Section A: About You
    key[YOU_FIRST_NAME] = householder.legal_first_name
    key[YOU_MIDDLE_INITIAL] = _middle_initial(householder)
    key[YOU_LAST_NAME] = householder.legal_last_name
    key[YOU_DOB] = _format_dob(householder)
    key[YOU_SSN] = householder.ssn
    key[YOU_US_CITIZEN] = "Yes"

    # Section B: Address
    addr = household.address
    if addr:
        key[ADDR_STREET] = addr.street
        key[ADDR_CITY] = addr.city
        key[ADDR_STATE] = addr.state
        key[ADDR_ZIP] = addr.zip_code

    # Section C: Spouse
    spouse = household.get_spouse()
    if spouse:
        key[SPOUSE_FIRST_NAME] = spouse.legal_first_name
        key[SPOUSE_MIDDLE_INITIAL] = _middle_initial(spouse)
        key[SPOUSE_LAST_NAME] = spouse.legal_last_name
        key[SPOUSE_DOB] = _format_dob(spouse)
        key[SPOUSE_SSN] = spouse.ssn

    # Section D: Filing status
    key[FILING_STATUS] = household.derive_filing_status().value

    # Section E: Dependents
    dependents = [
        p for p in household.members
        if p.is_dependent or p.can_be_claimed
    ]
    dependents.sort(key=lambda p: p.age, reverse=True)
    for i, dep in enumerate(dependents[:MAX_DEPENDENTS]):
        key[dep_field(i, DEP_NAME)] = dep.full_legal_name()
        key[dep_field(i, DEP_DOB)] = _format_dob(dep)
        rel = dep.relationship
        rel_val = rel.value if isinstance(rel, RelationshipType) else str(rel)
        key[dep_field(i, DEP_RELATIONSHIP)] = _DEPENDENT_RELATIONSHIPS.get(
            rel_val, "Other"
        )
        key[dep_field(i, DEP_MONTHS)] = str(dep.months_in_home)
        key[dep_field(i, DEP_US_CITIZEN)] = "Yes"
        key[dep_field(i, DEP_STUDENT)] = "Yes" if dep.is_full_time_student else "No"
        key[dep_field(i, DEP_DISABLED)] = "Yes" if dep.has_disability else "No"

        # Volunteer columns (Page 1 Section 11) — three scored, two
        # left ungraded (vol_qc_other, vol_self_support; see
        # UNGRADED_FIELDS in form_fields.py). _values_match treats
        # "Y" / "Yes" as equivalent so either convention is accepted.
        income_under = (
            dep.total_income() < 5200
            if hasattr(dep, "total_income") else True
        )
        key[dep_field(i, DEP_VOL_INCOME_UNDER)] = "Yes" if income_under else "No"
        key[dep_field(i, DEP_VOL_SUPPORT)] = (
            "Yes" if dep.months_in_home >= 6 else "No"
        )
        # Home-cost question is "did taxpayer(s) pay >50% of home cost
        # for this person?" — assume yes when the dependent lived in
        # the household. Refine when we model multi-supporter cases.
        key[dep_field(i, DEP_VOL_HOME_COST)] = (
            "Yes" if dep.months_in_home >= 6 else "No"
        )

    # Section F: Additional questions
    if householder.can_be_claimed:
        key[CLAIMED_AS_DEPENDENT] = "Yes"
    else:
        key[NOT_CLAIMED_AS_DEPENDENT] = "Yes"

    # Part II: Income
    _build_income_key(key, household)

    # Part III: Expenses
    _build_expense_key(key, household)

    return key


def _build_income_key(key: Dict[str, str], household: Household) -> None:
    """Add income fields to the answer key from filers' income data."""
    filers = []
    householder = household.get_householder()
    spouse = household.get_spouse()
    if householder:
        filers.append(householder)
    if spouse:
        filers.append(spouse)

    total_wages = sum(p.wage_income for p in filers)
    total_interest = sum(p.interest_income for p in filers)
    total_dividends = sum(p.dividend_income for p in filers)
    total_ss = sum(p.social_security_income for p in filers)
    total_retirement = sum(p.retirement_income for p in filers)
    total_se = sum(p.self_employment_income for p in filers)

    if total_wages > 0:
        key[INCOME_WAGES] = "Yes"
        key[INCOME_WAGES_AMOUNT] = str(total_wages)
    else:
        key[INCOME_WAGES] = "No"

    if total_interest > 0:
        key[INCOME_INTEREST] = "Yes"
        key[INCOME_INTEREST_AMOUNT] = str(total_interest)
    else:
        key[INCOME_INTEREST] = "No"

    if total_dividends > 0:
        key[INCOME_DIVIDENDS] = "Yes"
        key[INCOME_DIVIDENDS_AMOUNT] = str(total_dividends)
    else:
        key[INCOME_DIVIDENDS] = "No"

    if total_ss > 0:
        key[INCOME_SOCIAL_SECURITY] = "Yes"
        key[INCOME_SOCIAL_SECURITY_AMOUNT] = str(total_ss)
    else:
        key[INCOME_SOCIAL_SECURITY] = "No"

    if total_retirement > 0:
        key[INCOME_RETIREMENT] = "Yes"
        key[INCOME_RETIREMENT_AMOUNT] = str(total_retirement)
    else:
        key[INCOME_RETIREMENT] = "No"

    if total_se > 0:
        key[INCOME_SELF_EMPLOYMENT] = "Yes"
        key[INCOME_SELF_EMPLOYMENT_AMOUNT] = str(total_se)
    else:
        key[INCOME_SELF_EMPLOYMENT] = "No"

    total = total_wages + total_interest + total_dividends + total_ss + total_retirement + total_se
    if total > 0:
        key[INCOME_TOTAL] = str(total)

    # New Page 2 namespace — written alongside the legacy keys above so
    # the encounter form (which posts the new-namespace inputs) can be
    # graded directly. Only the rows whose source data the household
    # model carries today get scored; the rest stay out of the answer
    # key so unmodeled rows don't penalize the player. Document counts
    # come from the per-person doc lists.
    w2_count = sum(len(p.w2s) for p in filers)
    int_count = sum(len(p.form_1099_ints) for p in filers)
    div_count = sum(len(p.form_1099_divs) for p in filers)
    r_count = sum(len(p.form_1099_rs) for p in filers)
    nec_count = sum(len(p.form_1099_necs) for p in filers)
    ssa_count = sum(1 for p in filers if p.ssa_1099 is not None)
    total_other = sum(p.other_income for p in filers)

    # Row 1: wages
    key[INCOME_WAGES] = "Yes" if total_wages > 0 else "No"
    key[VOL_INCOME_W2] = "Yes" if total_wages > 0 else "No"
    if w2_count:
        key[VOL_INCOME_W2_COUNT] = str(w2_count)

    # Row 3: retirement
    key[VOL_INCOME_1099R] = "Yes" if total_retirement > 0 else "No"
    if r_count:
        key[VOL_INCOME_1099R_COUNT] = str(r_count)

    # Row 5: Social Security
    key[INCOME_SS] = "Yes" if total_ss > 0 else "No"
    key[VOL_INCOME_SSA] = "Yes" if total_ss > 0 else "No"
    if ssa_count:
        key[VOL_INCOME_SSA_COUNT] = str(ssa_count)

    # Row 8: combined interest + dividends client checkbox; volunteer
    # column splits them across 1099-INT and 1099-DIV.
    has_int_div = total_interest > 0 or total_dividends > 0
    key[INCOME_INTEREST_DIVIDENDS] = "Yes" if has_int_div else "No"
    key[VOL_INCOME_1099INT] = "Yes" if total_interest > 0 else "No"
    key[VOL_INCOME_1099DIV] = "Yes" if total_dividends > 0 else "No"
    if int_count:
        key[VOL_INCOME_1099INT_COUNT] = str(int_count)
    if div_count:
        key[VOL_INCOME_1099DIV_COUNT] = str(div_count)

    # Row 12: self-employment
    key[VOL_INCOME_SCHEDULE_C] = "Yes" if total_se > 0 else "No"
    key[VOL_INCOME_1099NEC] = "Yes" if total_se > 0 and nec_count > 0 else "No"
    if nec_count:
        key[VOL_INCOME_1099NEC_COUNT] = str(nec_count)

    # Row 14: other money
    key[INCOME_OTHER] = "Yes" if total_other > 0 else "No"


def _build_expense_key(key: Dict[str, str], household: Household) -> None:
    """Add expense/deduction fields to the answer key."""
    # Itemized deduction items
    if household.mortgage_interest > 0:
        key[EXPENSE_MORTGAGE_INTEREST] = "Yes"
        key[EXPENSE_MORTGAGE_INTEREST_AMOUNT] = str(household.mortgage_interest)
    else:
        key[EXPENSE_MORTGAGE_INTEREST] = "No"

    if household.property_taxes > 0:
        key[EXPENSE_PROPERTY_TAXES] = "Yes"
        key[EXPENSE_PROPERTY_TAXES_AMOUNT] = str(household.property_taxes)
    else:
        key[EXPENSE_PROPERTY_TAXES] = "No"

    if household.medical_expenses > 0:
        key[EXPENSE_MEDICAL] = "Yes"
    else:
        key[EXPENSE_MEDICAL] = "No"

    if household.charitable_contributions > 0:
        key[EXPENSE_CHARITABLE] = "Yes"
        key[EXPENSE_CHARITABLE_AMOUNT] = str(household.charitable_contributions)
    else:
        key[EXPENSE_CHARITABLE] = "No"

    # Standard vs itemized
    key[EXPENSE_DEDUCTION_TYPE] = (
        DEDUCTION_TYPE_STANDARD
        if household.uses_standard_deduction
        else DEDUCTION_TYPE_ITEMIZED
    )

    # Above-the-line deductions (summed across filers)
    filers = []
    householder = household.get_householder()
    spouse = household.get_spouse()
    if householder:
        filers.append(householder)
    if spouse:
        filers.append(spouse)

    total_student_loan = sum(p.student_loan_interest for p in filers)
    if total_student_loan > 0:
        key[EXPENSE_STUDENT_LOAN] = "Yes"
        key[EXPENSE_STUDENT_LOAN_AMOUNT] = str(total_student_loan)
    else:
        key[EXPENSE_STUDENT_LOAN] = "No"

    total_educator = sum(p.educator_expenses for p in filers)
    if total_educator > 0:
        key[EXPENSE_EDUCATOR] = "Yes"
        key[EXPENSE_EDUCATOR_AMOUNT] = str(total_educator)
    else:
        key[EXPENSE_EDUCATOR] = "No"

    total_ira = sum(p.ira_contributions for p in filers)
    if total_ira > 0:
        key[EXPENSE_IRA] = "Yes"
        key[EXPENSE_IRA_AMOUNT] = str(total_ira)
    else:
        key[EXPENSE_IRA] = "No"

    # Credit-related expenses
    if household.child_care_expenses > 0:
        key[EXPENSE_CHILD_CARE] = "Yes"
        key[EXPENSE_CHILD_CARE_AMOUNT] = str(household.child_care_expenses)
    else:
        key[EXPENSE_CHILD_CARE] = "No"

    if household.education_expenses > 0:
        key[EXPENSE_EDUCATION] = "Yes"
        key[EXPENSE_EDUCATION_AMOUNT] = str(household.education_expenses)
    else:
        key[EXPENSE_EDUCATION] = "No"


# =========================================================================
# Grader
# =========================================================================

class Grader:
    """Grades student submissions against scenario answer keys."""

    def grade_encounter(
        self,
        submission: Dict[str, str],
        ground_truth: dict,
        fields: Optional[List[str]] = None,
    ) -> GradingResult:
        """Grade a student's encounter form fill (Mode 1).

        Compares each submitted field against the pre-computed
        form_answers from GroundTruth.

        Args:
            submission: Dict of {field_name: student_value}.
            ground_truth: The GroundTruth dict (scenario.ground_truth).
                Must contain 'form_answers' key.
            fields: If provided, only grade these field names.
                Useful for section-scoped grading (e.g. Part I only).

        Returns:
            GradingResult with per-field feedback.

        Raises:
            ValueError: If ground_truth is missing or has no form_answers.
        """
        if ground_truth is None:
            raise ValueError(
                "Cannot grade: scenario has no ground_truth. "
                "Regenerate the scenario."
            )
        answer_key = dict(ground_truth.get("form_answers", {}))
        _check_form_answers_migrated(answer_key)
        if fields is not None:
            allowed = set(fields)
            answer_key = {k: v for k, v in answer_key.items() if k in allowed}
        max_score = len(answer_key)
        score = 0
        field_feedback: List[dict] = []

        for field_name, expected in answer_key.items():
            student_val = submission.get(field_name, "")
            if _values_match(student_val, expected):
                score += 1
                field_feedback.append({
                    "field": field_name,
                    "status": "correct",
                })
            else:
                field_feedback.append({
                    "field": field_name,
                    "status": "incorrect",
                    "expected": expected,
                    "submitted": student_val,
                })

        # Surface UNGRADED_FIELDS the player filled in. These don't
        # affect the score, but the result UI shows them with a
        # "Not graded in this version" label so players know their
        # answer wasn't checked (rather than silently passing).
        scoped = set(fields) if fields is not None else None
        for field_name in UNGRADED_FIELDS:
            if scoped is not None and field_name not in scoped:
                continue
            student_val = submission.get(field_name, "")
            if not student_val:
                # Player left it blank — no need to clutter the
                # results UI.
                continue
            field_feedback.append({
                "field": field_name,
                "status": "ungraded",
                "submitted": student_val,
            })

        accuracy = score / max_score if max_score > 0 else 0.0

        if accuracy == 1.0:
            feedback = "Perfect score — all fields match the source documents."
        elif accuracy >= 0.8:
            wrong = max_score - score
            feedback = (
                f"Good work. {wrong} field(s) need correction. "
                "Review the feedback below."
            )
        elif accuracy >= 0.5:
            feedback = (
                "Several fields are incorrect. Carefully cross-reference "
                "each field against the source documents."
            )
        else:
            feedback = (
                "Most fields are incorrect. Take your time to read each "
                "document carefully before filling in the form."
            )

        logger.info(
            "Graded intake: %d/%d (%.0f%%)", score, max_score, accuracy * 100,
        )

        return GradingResult(
            score=score,
            max_score=max_score,
            accuracy=accuracy,
            feedback=feedback,
            field_feedback=field_feedback,
        )

    def grade_verification(
        self,
        flagged_errors: List[Dict],
        actual_errors: List[InjectedError],
    ) -> GradingResult:
        """Grade a student's error identification (Mode 2).

        Matches flagged errors to the injected error manifest by field
        name.  A flag is correct if its ``field`` matches an actual
        error's ``field``.

        Args:
            flagged_errors: Student-submitted list of dicts, each with
                at least ``{"field": ..., "description": ...}``.
            actual_errors: The InjectedError manifest (answer key).

        Returns:
            GradingResult with correct/missed/false flag breakdowns.
        """
        max_score = len(actual_errors)

        # Index actual errors by field for matching
        unmatched_actual = {e.field: e for e in actual_errors}
        correct_flags: List[dict] = []
        false_flags: List[dict] = []

        for flag in flagged_errors:
            flag_field = flag.get("field", "")
            if flag_field in unmatched_actual:
                matched = unmatched_actual.pop(flag_field)
                correct_flags.append({
                    "field": flag_field,
                    "error_id": matched.error_id,
                    "description": flag.get("description", ""),
                })
            else:
                false_flags.append({
                    "field": flag_field,
                    "description": flag.get("description", ""),
                })

        # Anything left in unmatched_actual was missed
        missed_flags: List[dict] = []
        for field, err in unmatched_actual.items():
            missed_flags.append({
                "field": field,
                "error_id": err.error_id,
                "category": err.category,
                "explanation": err.explanation,
                "correct_value": err.correct_value,
                "erroneous_value": err.erroneous_value,
            })

        score = len(correct_flags)
        accuracy = score / max_score if max_score > 0 else 0.0

        # Build feedback
        if max_score == 0 and not false_flags:
            feedback = "This scenario had no errors, and you correctly identified none."
        elif max_score == 0 and false_flags:
            feedback = (
                "This scenario had no errors, but you flagged "
                f"{len(false_flags)} field(s). Be careful not to flag "
                "clean documents."
            )
        elif score == max_score and not false_flags:
            feedback = "Perfect — you found all errors with no false flags."
        elif score == max_score:
            feedback = (
                f"You found all {max_score} error(s), but also flagged "
                f"{len(false_flags)} field(s) that were correct."
            )
        elif missed_flags:
            feedback = (
                f"You found {score} of {max_score} error(s). "
                f"You missed: {', '.join(m['field'] for m in missed_flags)}."
            )
        else:
            feedback = f"Score: {score}/{max_score}."

        if false_flags and max_score > 0:
            feedback += (
                f" {len(false_flags)} false flag(s) — review documents "
                "more carefully before flagging."
            )

        logger.info(
            "Graded verification: %d/%d correct, %d missed, %d false",
            score, max_score, len(missed_flags), len(false_flags),
        )

        return GradingResult(
            score=score,
            max_score=max_score,
            accuracy=accuracy,
            correct_flags=correct_flags,
            missed_flags=missed_flags,
            false_flags=false_flags,
            feedback=feedback,
        )


def _values_match(submitted: str, expected: str) -> bool:
    """Compare form values with normalization.

    Handles common formatting differences: leading/trailing whitespace,
    case insensitivity for text fields, dash variations in SSNs.

    Args:
        submitted: What the student entered.
        expected: The ground-truth value.

    Returns:
        True if the values are considered equivalent.
    """
    s = submitted.strip()
    e = expected.strip()

    # Yes/No equivalence sets — also catch the HTML form-post "on"
    # default that checkboxes without an explicit value= post as
    # their submitted value when checked. Unchecked checkboxes are
    # absent from form_data; the submit handler is responsible for
    # translating them to "No" before grading, which keeps the
    # grader's match logic strict (a literal empty submission is
    # not equivalent to "No").
    yes_set = {"y", "yes", "on", "true"}
    no_set = {"n", "no", "false"}

    if not s and not e:
        return True
    if not s or not e:
        return False

    # Exact match
    if s == e:
        return True

    # Case-insensitive match (for names, cities, states)
    if s.lower() == e.lower():
        return True

    # SSN: normalize dashes
    s_digits = s.replace("-", "").replace(" ", "")
    e_digits = e.replace("-", "").replace(" ", "")
    if len(s_digits) == 9 and s_digits.isdigit() and s_digits == e_digits:
        return True

    # Numeric: allow small rounding differences for income amounts
    s_clean = s.replace(",", "").replace("$", "").strip()
    e_clean = e.replace(",", "").replace("$", "").strip()
    try:
        s_num = float(s_clean)
        e_num = float(e_clean)
        if abs(s_num - e_num) <= 1.0:
            return True
    except ValueError:
        pass

    # Y / Yes equivalence (and N / No). The new Page 1 template's
    # volunteer columns hint at one-letter answers; the legacy answer
    # key emits "Yes" / "No". Treat both conventions as equivalent so
    # a player who keeps the pre-filled "Y" isn't marked wrong against
    # an expected "Yes". Also handles "on" (HTML default checkbox
    # post value) ↔ "Yes" so checkboxes posting from the new
    # Page 1 / Page 2 templates grade against a "Yes" answer key.
    sl, el = s.lower(), e.lower()
    if sl in yes_set and el in yes_set:
        return True
    if sl in no_set and el in no_set:
        return True

    return False
