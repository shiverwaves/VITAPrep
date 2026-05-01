"""Year-indexed tax thresholds and constants.

Each threshold is a dict keyed by tax year. Accessor functions provide
the interface — callers never read the dicts directly.

Sources cited per constant. All values are nominal (not inflation-adjusted
across years; each year's entry is the published value for that year).
"""

from typing import Dict


# IRC §63(c) — standard deduction by filing status.
# Source: IRS Revenue Procedure 2021-45 (2022 values).
_STANDARD_DEDUCTION: Dict[int, Dict[str, int]] = {
    2022: {
        "single": 12950,
        "married_filing_jointly": 25900,
        "married_filing_separately": 12950,
        "head_of_household": 19400,
        "qualifying_surviving_spouse": 25900,
    },
}

# IRC §164(b)(6) — state and local tax deduction cap (TCJA 2017).
_SALT_CAP: Dict[int, int] = {
    2022: 10000,
}

# IRC §219(b)(5)(A) — traditional IRA contribution limit.
_IRA_CONTRIBUTION_LIMIT: Dict[int, int] = {
    2022: 6000,
}

# IRC §219(b)(5)(B) — catch-up contribution for age 50+.
_IRA_CONTRIBUTION_LIMIT_50_PLUS: Dict[int, int] = {
    2022: 7000,
}

# IRC §221(b)(1) — student loan interest deduction cap.
_STUDENT_LOAN_INTEREST_LIMIT: Dict[int, int] = {
    2022: 2500,
}

# IRC §62(a)(2)(D) — educator expense deduction cap.
_EDUCATOR_EXPENSE_LIMIT: Dict[int, int] = {
    2022: 300,
}


def standard_deduction_for(filing_status: str, year: int) -> int:
    """Return the standard deduction amount for a filing status and tax year.

    Args:
        filing_status: One of the FilingStatus enum values (e.g. "single").
        year: Tax year.

    Returns:
        Standard deduction amount in dollars.

    Raises:
        KeyError: If the year or filing status is not in the table.
    """
    return _STANDARD_DEDUCTION[year][filing_status]


def salt_cap(year: int) -> int:
    """Return the SALT deduction cap for a tax year. IRC §164(b)(6)."""
    return _SALT_CAP[year]


def ira_contribution_limit(age: int, year: int) -> int:
    """Return the IRA contribution limit, accounting for catch-up at 50+."""
    if age >= 50:
        return _IRA_CONTRIBUTION_LIMIT_50_PLUS[year]
    return _IRA_CONTRIBUTION_LIMIT[year]


def student_loan_interest_limit(year: int) -> int:
    """Return the student loan interest deduction cap. IRC §221(b)(1)."""
    return _STUDENT_LOAN_INTEREST_LIMIT[year]


def educator_expense_limit(year: int) -> int:
    """Return the educator expense deduction cap. IRC §62(a)(2)(D)."""
    return _EDUCATOR_EXPENSE_LIMIT[year]
