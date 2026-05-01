"""Filing status predicates.

Determines filing status from household composition. The simplified logic
here (married → MFJ, has children → HoH, else single) is correct for the
household patterns we currently generate. See BUILD_PLAN.md Restructure A
Phase 2 for the stub-tier refinements (is_unmarried, HoH qualifying person).
"""

from typing import Any


def derive_filing_status(household: Any) -> str:
    """Derive filing status from household composition.

    Args:
        household: A Household object with is_married() and get_children() methods.

    Returns:
        Filing status string matching FilingStatus enum values:
        "single", "married_filing_jointly", "head_of_household", etc.
    """
    if household.is_married():
        return "married_filing_jointly"
    children = household.get_children()
    if children:
        return "head_of_household"
    return "single"
