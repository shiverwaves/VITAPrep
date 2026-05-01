"""Filing status predicates.

Determines filing status from household composition and evaluates
Head of Household eligibility conditions. IRC §2(b).

Stub-tier predicates are noted in their docstrings. They match the
scenarios we currently generate; full rules require data we don't
yet produce.
"""

from typing import Any


def derive_filing_status(household: Any) -> str:
    """Derive filing status from household composition.

    STUB: married → MFJ, has children → HoH, else single. Does not handle
    MFS, QSS, or the full HoH qualifying-person test. Correct for current
    household patterns. IRC §1, §2.

    Args:
        household: A Household object with is_married() and get_children() methods.

    Returns:
        Filing status string matching FilingStatus enum values.
    """
    if household.is_married():
        return "married_filing_jointly"
    children = household.get_children()
    if children:
        return "head_of_household"
    return "single"


def is_unmarried(filer: Any, year: int) -> bool:
    """Test whether the filer is unmarried for filing status purposes.

    STUB: Returns True if no spouse is present in the household. Full rule
    (IRC §2(b)(1), (c)) also includes "considered unmarried" status: a
    married person who lived apart from their spouse for the last 6 months
    of the year and has a dependent child may file as HoH. We don't generate
    that data yet.

    Args:
        filer: A Person object. Must have a reference to household or the
            caller must check spouse presence before calling.
        year: Tax year (reserved for future year-specific rules).

    Returns:
        True if the filer is considered unmarried.
    """
    household = filer._household if hasattr(filer, "_household") else None
    if household is not None:
        return not household.is_married()
    return filer.relationship not in ("spouse",)


def paid_more_than_half_household_costs(filer: Any, household: Any) -> bool:
    """Test whether the filer paid more than half the cost of keeping up a home.

    STUB: Returns True for single-adult households (the only adult must have
    paid all costs). Returns False for multi-adult households where we can't
    determine cost allocation. IRC §2(b)(1)(A).

    Known gap: We don't generate cost-of-household data. When we do, this
    predicate should compare the filer's contribution to total household costs.

    Args:
        filer: The Person claiming HoH.
        household: The Household object.

    Returns:
        True if the filer is presumed to have paid more than half.
    """
    adults = household.get_adults()
    return len(adults) == 1


def has_qualifying_person_for_hoh(filer: Any, household: Any) -> bool:
    """Test whether the filer has a qualifying person for Head of Household.

    STUB: A qualifying person is either a qualifying child who lived with
    the filer more than half the year, or a qualifying relative who is a
    parent or specified relative. IRC §2(b)(1)(A)(i)-(ii).

    This stub checks for any dependent child with months_in_home > 6.
    Does not evaluate the full qualifying-relative path or the parent
    exception (parent need not live with filer if filer pays > half
    parent's household costs). Refine when hoh_qualifying_person concept
    is drilled.

    Args:
        filer: The Person claiming HoH.
        household: The Household object.

    Returns:
        True if a qualifying person exists.
    """
    for child in household.get_children():
        if child.months_in_home > 6:
            return True
    return False
