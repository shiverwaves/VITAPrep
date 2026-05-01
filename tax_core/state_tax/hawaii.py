"""Hawaii state income tax brackets and computation.

Source: Hawaii Department of Taxation, 2022 individual income tax rates.
"""

from typing import List, Tuple


# 2022 brackets: list of (upper_bound, marginal_rate) pairs.
BRACKETS_SINGLE: List[Tuple[float, float]] = [
    (2400, 0.014),
    (4800, 0.032),
    (9600, 0.055),
    (14400, 0.064),
    (19200, 0.068),
    (24000, 0.072),
    (36000, 0.076),
    (48000, 0.079),
    (150000, 0.0825),
    (175000, 0.09),
    (200000, 0.10),
    (float("inf"), 0.11),
]

BRACKETS_MFJ: List[Tuple[float, float]] = [
    (4800, 0.014),
    (9600, 0.032),
    (19200, 0.055),
    (28800, 0.064),
    (38400, 0.068),
    (48000, 0.072),
    (72000, 0.076),
    (96000, 0.079),
    (300000, 0.0825),
    (350000, 0.09),
    (400000, 0.10),
    (float("inf"), 0.11),
]

_BRACKETS_BY_STATUS = {
    "single": BRACKETS_SINGLE,
    "head_of_household": BRACKETS_SINGLE,
    "married_filing_separately": BRACKETS_SINGLE,
    "married_filing_jointly": BRACKETS_MFJ,
    "qualifying_surviving_spouse": BRACKETS_MFJ,
}


def progressive_tax(income: int, brackets: List[Tuple[float, float]]) -> int:
    """Compute tax using progressive brackets.

    Args:
        income: Taxable income in dollars.
        brackets: List of (upper_bound, marginal_rate) pairs, ordered by bracket.

    Returns:
        Total tax in dollars (truncated to int).
    """
    tax = 0.0
    prev = 0
    for bracket_max, rate in brackets:
        if income <= prev:
            break
        taxable = min(income, bracket_max) - prev
        tax += taxable * rate
        prev = int(bracket_max) if bracket_max != float("inf") else prev
    return int(tax)


def compute_hawaii_tax(income: int, filing_status: str) -> int:
    """Compute Hawaii state income tax for a given income and filing status.

    Args:
        income: Taxable income in dollars.
        filing_status: One of the FilingStatus enum values.

    Returns:
        State income tax in dollars.

    Raises:
        KeyError: If filing_status is not recognized.
    """
    brackets = _BRACKETS_BY_STATUS[filing_status]
    return progressive_tax(income, brackets)
