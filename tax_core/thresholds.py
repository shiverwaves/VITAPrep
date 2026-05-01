"""Year-indexed tax thresholds and constants.

Each threshold is a dict keyed by tax year. Accessor functions provide
the interface — callers never read the dicts directly.

Sources cited per constant. All values are nominal (not inflation-adjusted
across years; each year's entry is the published value for that year).
"""

from typing import Dict, List, Tuple


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

# IRC §1 — federal income tax brackets by filing status.
# Source: IRS Revenue Procedure 2021-45 (2022 values).
# Each bracket is (upper_bound, rate). The last bracket has no upper bound
# (represented as None → we use a sentinel of 10**18).
_FEDERAL_BRACKETS: Dict[int, Dict[str, List[Tuple[int, float]]]] = {
    2022: {
        "single": [
            (10275, 0.10),
            (41775, 0.12),
            (89075, 0.22),
            (170050, 0.24),
            (215950, 0.32),
            (539900, 0.35),
            (10**18, 0.37),
        ],
        "married_filing_jointly": [
            (20550, 0.10),
            (83550, 0.12),
            (178150, 0.22),
            (340100, 0.24),
            (431900, 0.32),
            (647850, 0.35),
            (10**18, 0.37),
        ],
        "married_filing_separately": [
            (10275, 0.10),
            (41775, 0.12),
            (89075, 0.22),
            (170050, 0.24),
            (215950, 0.32),
            (323925, 0.35),
            (10**18, 0.37),
        ],
        "head_of_household": [
            (14650, 0.10),
            (55900, 0.12),
            (89050, 0.22),
            (170050, 0.24),
            (215950, 0.32),
            (539900, 0.35),
            (10**18, 0.37),
        ],
        "qualifying_surviving_spouse": [
            (20550, 0.10),
            (83550, 0.12),
            (178150, 0.22),
            (340100, 0.24),
            (431900, 0.32),
            (647850, 0.35),
            (10**18, 0.37),
        ],
    },
}

# IRC §24(d)(1) — child tax credit amount per qualifying child.
_CTC_AMOUNT: Dict[int, int] = {
    2022: 2000,
}

# IRC §24(h)(3) — CTC AGI phase-out thresholds.
# Credit reduces by $50 per $1,000 of AGI over the threshold.
_CTC_PHASEOUT: Dict[int, Dict[str, int]] = {
    2022: {
        "single": 200000,
        "head_of_household": 200000,
        "married_filing_jointly": 400000,
        "married_filing_separately": 200000,
        "qualifying_surviving_spouse": 400000,
    },
}

# IRC §24(h)(4) — maximum refundable CTC (ACTC) per child.
_ACTC_MAX_PER_CHILD: Dict[int, int] = {
    2022: 1500,
}

# IRC §1401 — self-employment tax rates.
_SE_TAX_RATE: Dict[int, float] = {
    2022: 0.153,  # 12.4% SS + 2.9% Medicare
}
_SE_INCOME_FACTOR: Dict[int, float] = {
    2022: 0.9235,  # 92.35% of net SE income is subject to SE tax
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


def federal_brackets(filing_status: str, year: int) -> List[Tuple[int, float]]:
    """Return the federal income tax brackets for a filing status and year.

    Each bracket is (upper_bound, marginal_rate). The final bracket uses
    a sentinel upper bound (10**18).

    Args:
        filing_status: Filing status string.
        year: Tax year.

    Returns:
        List of (upper_bound, rate) tuples, ordered by bracket.
    """
    return _FEDERAL_BRACKETS[year][filing_status]


def ctc_amount(year: int) -> int:
    """Return the child tax credit amount per qualifying child. IRC §24."""
    return _CTC_AMOUNT[year]


def ctc_phaseout_threshold(filing_status: str, year: int) -> int:
    """Return the AGI threshold where CTC begins to phase out. IRC §24(h)(3)."""
    return _CTC_PHASEOUT[year][filing_status]


def actc_max_per_child(year: int) -> int:
    """Return the maximum refundable CTC (ACTC) per child. IRC §24(h)(4)."""
    return _ACTC_MAX_PER_CHILD[year]


def se_tax_rate(year: int) -> float:
    """Return the self-employment tax rate. IRC §1401."""
    return _SE_TAX_RATE[year]


def se_income_factor(year: int) -> float:
    """Return the factor applied to net SE income before SE tax. IRC §1402(a)."""
    return _SE_INCOME_FACTOR[year]
