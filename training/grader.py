"""
Grader — compares student submissions to ground truth.

Mode 1 (intake): Field-by-field comparison of student-filled form vs ground truth.
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
from training.form_fields import (
    ADDR_CITY,
    ADDR_STATE,
    ADDR_STREET,
    ADDR_ZIP,
    ADDR_APT,
    CLAIMED_AS_DEPENDENT,
    DEP_DOB,
    DEP_FIRST_NAME,
    DEP_LAST_NAME,
    DEP_MONTHS,
    DEP_RELATIONSHIP,
    FILING_STATUS,
    INCOME_DIVIDENDS,
    INCOME_DIVIDENDS_AMOUNT,
    INCOME_INTEREST,
    INCOME_INTEREST_AMOUNT,
    INCOME_RETIREMENT,
    INCOME_RETIREMENT_AMOUNT,
    INCOME_SELF_EMPLOYMENT,
    INCOME_SELF_EMPLOYMENT_AMOUNT,
    INCOME_SOCIAL_SECURITY,
    INCOME_SOCIAL_SECURITY_AMOUNT,
    INCOME_TOTAL,
    INCOME_WAGES,
    INCOME_WAGES_AMOUNT,
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
    dep_field,
)

logger = logging.getLogger(__name__)


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


def _build_answer_key(household: Household) -> Dict[str, str]:
    """Build the expected form field values from ground truth.

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
        key[dep_field(i, DEP_FIRST_NAME)] = dep.legal_first_name
        key[dep_field(i, DEP_LAST_NAME)] = dep.legal_last_name
        key[dep_field(i, DEP_DOB)] = _format_dob(dep)
        rel = dep.relationship
        key[dep_field(i, DEP_RELATIONSHIP)] = (
            rel.value if isinstance(rel, RelationshipType) else str(rel)
        )
        key[dep_field(i, DEP_MONTHS)] = str(dep.months_in_home)

    # Part II: Income
    _build_income_key(key, household)

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
    if total_interest > 0:
        key[INCOME_INTEREST] = "Yes"
        key[INCOME_INTEREST_AMOUNT] = str(total_interest)
    if total_dividends > 0:
        key[INCOME_DIVIDENDS] = "Yes"
        key[INCOME_DIVIDENDS_AMOUNT] = str(total_dividends)
    if total_ss > 0:
        key[INCOME_SOCIAL_SECURITY] = "Yes"
        key[INCOME_SOCIAL_SECURITY_AMOUNT] = str(total_ss)
    if total_retirement > 0:
        key[INCOME_RETIREMENT] = "Yes"
        key[INCOME_RETIREMENT_AMOUNT] = str(total_retirement)
    if total_se > 0:
        key[INCOME_SELF_EMPLOYMENT] = "Yes"
        key[INCOME_SELF_EMPLOYMENT_AMOUNT] = str(total_se)

    total = total_wages + total_interest + total_dividends + total_ss + total_retirement + total_se
    if total > 0:
        key[INCOME_TOTAL] = str(total)


# =========================================================================
# Grader
# =========================================================================

class Grader:
    """Grades student submissions against scenario answer keys."""

    def grade_intake(
        self, submission: Dict[str, str], ground_truth: Household,
    ) -> GradingResult:
        """Grade a student's intake form fill (Mode 1).

        Compares each submitted field against the answer key derived
        from the ground-truth Household.

        Args:
            submission: Dict of {field_name: student_value}.
            ground_truth: The original Household (before any error
                injection).

        Returns:
            GradingResult with per-field feedback.
        """
        answer_key = _build_answer_key(ground_truth)
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

    return False
