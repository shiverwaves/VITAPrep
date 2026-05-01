"""Deduction predicates — SALT cap, medical floor, itemized vs standard.

These are the tax-rule computations extracted from ExpenseGenerator._calculate_totals().
The expense generator calls these functions; the assignment of results back to
the Household object stays in the generator.
"""

from typing import Any

from tax_core.thresholds import salt_cap, standard_deduction_for


def compute_salt(state_tax: int, property_tax: int, year: int) -> int:
    """Apply the SALT deduction cap. IRC §164(b)(6).

    Args:
        state_tax: State income tax paid.
        property_tax: Property taxes paid.
        year: Tax year.

    Returns:
        Deductible SALT amount (capped).
    """
    return min(state_tax + property_tax, salt_cap(year))


def compute_medical_deduction(medical_expenses: int, agi: int) -> int:
    """Compute deductible medical expenses above the 7.5% AGI floor. IRC §213.

    Args:
        medical_expenses: Total medical and dental expenses.
        agi: Adjusted gross income.

    Returns:
        Deductible amount (zero if expenses don't exceed the floor).
    """
    return max(0, medical_expenses - int(agi * 0.075))


def compute_itemized_total(
    salt: int,
    mortgage_interest: int,
    medical_deductible: int,
    charitable_contributions: int,
) -> int:
    """Aggregate Schedule A itemized deduction categories.

    Args:
        salt: Deductible SALT amount (after cap).
        mortgage_interest: Mortgage interest (Form 1098 Box 1).
        medical_deductible: Medical expenses above the 7.5% AGI floor.
        charitable_contributions: Charitable contributions.

    Returns:
        Total itemized deductions.
    """
    return salt + mortgage_interest + medical_deductible + charitable_contributions


def should_itemize(
    itemized_total: int, filing_status: str, year: int,
) -> bool:
    """Determine whether itemizing beats the standard deduction.

    Args:
        itemized_total: Total itemized deductions from compute_itemized_total().
        filing_status: Filing status string (e.g. "single").
        year: Tax year.

    Returns:
        True if itemized total exceeds the standard deduction.
    """
    standard = standard_deduction_for(filing_status, year)
    return itemized_total > standard
