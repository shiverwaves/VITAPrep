"""State income tax computation — dispatch by state code.

Currently only Hawaii is implemented. See docs/BUILD_PLAN.md § "Future:
State Tax Generalization" for the multi-state expansion plan.
"""

from .hawaii import compute_hawaii_tax


_STATE_DISPATCH = {
    "HI": compute_hawaii_tax,
}


def compute_state_income_tax(
    income: int, filing_status: str, state: str, year: int,
) -> int:
    """Compute state income tax.

    Args:
        income: Taxable income in dollars.
        filing_status: One of the FilingStatus enum values.
        state: Two-letter state code (e.g. "HI").
        year: Tax year (reserved for future multi-year bracket support).

    Returns:
        State income tax in dollars.

    Raises:
        ValueError: If the state is not supported.
    """
    compute_fn = _STATE_DISPATCH.get(state)
    if compute_fn is None:
        raise ValueError(
            f"State '{state}' is not supported. "
            f"Available: {sorted(_STATE_DISPATCH.keys())}"
        )
    return compute_fn(income, filing_status)
