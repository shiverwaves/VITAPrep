"""Dependency predicates — qualifying child and qualifying relative tests.

These return structured results (not just booleans) so the grader and
slot layer can inspect *why* a test passed or failed.

Stub-tier simplifications noted in docstrings.
"""

from dataclasses import dataclass
from typing import Any


@dataclass
class ResidencyTestResult:
    """Structured result from qualifying_child_residency_test."""
    passed: bool
    months_in_home: int
    required_months: int = 7  # more than half = at least 7
    temporary_absence_applied: bool = False
    reason: str = ""


@dataclass
class QualifyingRelativeResult:
    """Structured result from qualifying_relative_test."""
    passed: bool
    relationship_test: bool = False
    gross_income_test: bool = False
    support_test: bool = False
    not_qualifying_child_test: bool = False
    reason: str = ""


# IRC §152(d)(2) — gross income threshold for qualifying relative.
# Indexed annually. Source: IRS Revenue Procedure 2021-45.
_QUALIFYING_RELATIVE_INCOME_THRESHOLD = {
    2022: 4400,
}

# Relationships that satisfy the qualifying-relative relationship test
# per IRC §152(d)(2)(A)-(H).
_QR_QUALIFYING_RELATIONSHIPS = {
    "biological_child", "adopted_child", "stepchild", "grandchild",
    "parent", "sibling", "other_relative",
}


def qualifying_child_residency_test(child: Any, year: int) -> ResidencyTestResult:
    """Test whether a child meets the residency requirement for qualifying child.

    The child must have the same principal place of abode as the taxpayer for
    more than half the tax year (> 6 months). IRC §152(c)(1)(B).

    STUB: Core "more than half the year" test using months_in_home. Temporary
    absence exceptions (school, illness, military, kidnapping per IRC
    §152(c)(1)(B)(ii)) are deferred — we don't generate those scenarios yet.

    Args:
        child: A Person object with months_in_home attribute.
        year: Tax year (reserved for future year-specific rules).

    Returns:
        ResidencyTestResult with pass/fail and detail.
    """
    months = child.months_in_home
    passed = months > 6

    if passed:
        reason = f"Child lived with taxpayer {months} months (> 6 required)"
    else:
        reason = f"Child lived with taxpayer {months} months (need > 6)"

    return ResidencyTestResult(
        passed=passed,
        months_in_home=months,
        reason=reason,
    )


def qualifying_relative_test(
    person: Any, household: Any, year: int = 2022,
) -> QualifyingRelativeResult:
    """Test whether a person qualifies as a qualifying relative dependent.

    Four-part test per IRC §152(d):
    1. Relationship or member-of-household-all-year
    2. Gross income under threshold
    3. Support (taxpayer provided more than half)
    4. Not a qualifying child of another taxpayer

    STUB: Implements relationship test and gross income test. Support test
    is stubbed as True (we don't generate support data). The "not a QC of
    another" test is stubbed as True (we don't model multi-household claims).

    Args:
        person: The Person being evaluated as a potential qualifying relative.
        household: The Household object.
        year: Tax year for gross income threshold lookup.

    Returns:
        QualifyingRelativeResult with per-sub-test pass/fail and detail.
    """
    relationship_val = person.relationship
    if hasattr(relationship_val, "value"):
        relationship_val = relationship_val.value

    relationship_ok = relationship_val in _QR_QUALIFYING_RELATIONSHIPS
    threshold = _QUALIFYING_RELATIVE_INCOME_THRESHOLD.get(year, 4400)
    gross_income_ok = person.total_income() < threshold
    support_ok = True  # STUB: no support data available
    not_qc_ok = True  # STUB: no multi-household modeling

    passed = relationship_ok and gross_income_ok and support_ok and not_qc_ok

    reasons = []
    if not relationship_ok:
        reasons.append(f"relationship '{relationship_val}' not qualifying")
    if not gross_income_ok:
        reasons.append(
            f"gross income ${person.total_income():,} >= ${threshold:,} threshold"
        )

    return QualifyingRelativeResult(
        passed=passed,
        relationship_test=relationship_ok,
        gross_income_test=gross_income_ok,
        support_test=support_ok,
        not_qualifying_child_test=not_qc_ok,
        reason="; ".join(reasons) if reasons else "All tests passed",
    )
