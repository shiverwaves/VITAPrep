"""Credit predicates — EITC and ACTC eligibility stubs.

These are explicitly stub-tier predicates. Full EITC rules are complex
(earned income tables, investment income test, AGI phase-outs by filing
status and number of qualifying children). Full implementation is
deferred to the eitc_qualifying_child_rules concept (Restructure D).

Stub simplifications are documented per-function with the IRC section
governing the full rule.
"""

from typing import Any


# IRC §32(c)(2) — earned income must be > 0 for EITC.
# Full EITC also requires: AGI below threshold (varies by # of QC),
# investment income <= $10,300 (2022), valid SSN, not MFS, not a QC
# of another taxpayer, and the earned-income / AGI tables.

def qualifies_for_eitc(person: Any, household: Any, year: int = 2022) -> bool:
    """Test basic EITC eligibility.

    STUB: Checks earned income > 0 and presence of a qualifying child.
    Does not implement the full EITC rules: AGI phase-out tables,
    investment income limit ($10,300 for 2022), valid SSN requirement,
    MFS disqualification, or the childless-worker EITC path.
    IRC §32.

    Full implementation deferred to concept ``eitc_qualifying_child_rules``
    in Restructure D.

    Args:
        person: The filer (Person object with income fields).
        household: The Household object.
        year: Tax year (reserved for year-specific thresholds).

    Returns:
        True if the filer has earned income and a qualifying child.
    """
    earned_income = person.wage_income + person.self_employment_income
    if earned_income <= 0:
        return False

    children = household.get_children()
    return len(children) > 0


def qualifies_for_actc(person: Any, household: Any, year: int = 2022) -> bool:
    """Test basic Additional Child Tax Credit eligibility.

    STUB: Checks earned income > $2,500 (the refundable CTC threshold)
    and presence of a qualifying child under 17. Does not implement
    the full computation: 15% of earned income above $2,500, capped
    at $1,500 per qualifying child (2022). IRC §24(d), §24(h).

    Args:
        person: The filer (Person object with income fields).
        household: The Household object.
        year: Tax year (reserved for year-specific thresholds).

    Returns:
        True if earned income exceeds $2,500 and a child under 17 exists.
    """
    earned_income = person.wage_income + person.self_employment_income
    if earned_income <= 2500:
        return False

    for child in household.get_children():
        if child.age < 17:
            return True
    return False
