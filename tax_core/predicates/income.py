"""Income predicates — total income, self-employment threshold, filing
threshold, and Social Security taxability.

Exact-tier predicates are arithmetic. Careful-tier predicates (SS taxability)
encode the IRS Publication 915 worksheet faithfully.
"""

from typing import Any, Dict, Tuple


# =============================================================================
# Filing threshold — IRS Publication 501, Table 1 (2022)
# =============================================================================

# IRC §6012. Gross income filing requirements by status and age.
# Under-65 thresholds shown; 65+ adds $1,400 (single/HoH) or $1,400 per
# spouse 65+ (MFJ). We store under-65 values; the accessor adds the
# age adjustment.
_FILING_THRESHOLD: Dict[int, Dict[str, int]] = {
    2022: {
        "single": 12950,
        "head_of_household": 19400,
        "married_filing_jointly": 25900,
        "married_filing_separately": 5,
        "qualifying_surviving_spouse": 25900,
    },
}

# Additional amount for age 65+. IRC §63(f).
_ELDERLY_ADDITIONAL: Dict[int, Dict[str, int]] = {
    2022: {
        "single": 1750,
        "head_of_household": 1750,
        "married_filing_jointly": 1400,
        "married_filing_separately": 1400,
        "qualifying_surviving_spouse": 1400,
    },
}


# =============================================================================
# Social Security taxability — IRS Publication 915, Worksheet 1 (2022)
# =============================================================================

# IRC §86. Base amounts for provisional income test.
# These have not changed since 1993 (not indexed).
_SS_BASE_AMOUNTS: Dict[int, Dict[str, Tuple[int, int]]] = {
    2022: {
        "single": (25000, 34000),
        "head_of_household": (25000, 34000),
        "married_filing_jointly": (32000, 44000),
        "qualifying_surviving_spouse": (32000, 44000),
        "married_filing_separately": (0, 0),
    },
}


# =============================================================================
# Exact-tier predicates
# =============================================================================

def total_income(person: Any) -> int:
    """Sum of all income fields for a person.

    Args:
        person: A Person object with income fields.

    Returns:
        Total gross income in dollars.
    """
    return (
        person.wage_income
        + person.self_employment_income
        + person.social_security_income
        + person.retirement_income
        + person.interest_income
        + person.dividend_income
        + person.other_income
        + getattr(person, "public_assistance_income", 0)
    )


def total_self_employment_income(person: Any) -> int:
    """Sum of self-employment income (1099-NEC amounts).

    Args:
        person: A Person object.

    Returns:
        Total self-employment income in dollars.
    """
    return person.self_employment_income


def requires_schedule_se(person: Any) -> bool:
    """Whether the person must file Schedule SE.

    Net SE earnings of $400+ trigger Schedule SE. IRC §1402(a).

    Args:
        person: A Person object.

    Returns:
        True if SE income >= $400.
    """
    return total_self_employment_income(person) >= 400


# =============================================================================
# Careful-tier predicates
# =============================================================================

def filing_threshold_for(status: str, year: int) -> int:
    """Return the gross income filing threshold for a status and year.

    Source: IRS Publication 501, Table 1. Does not include the elderly
    additional amount — call with is_elderly=True for that adjustment
    (see filing_threshold_for_person).

    Args:
        status: Filing status string.
        year: Tax year.

    Returns:
        Filing threshold in dollars.

    Raises:
        KeyError: If year or status not in table.
    """
    return _FILING_THRESHOLD[year][status]


def filing_threshold_for_person(
    status: str, year: int, is_elderly: bool = False,
) -> int:
    """Filing threshold with age adjustment.

    Args:
        status: Filing status string.
        year: Tax year.
        is_elderly: Whether the filer (or either spouse for MFJ) is 65+.

    Returns:
        Adjusted filing threshold.
    """
    base = _FILING_THRESHOLD[year][status]
    if is_elderly:
        base += _ELDERLY_ADDITIONAL[year][status]
    return base


def compute_provisional_income(person: Any) -> int:
    """Compute provisional income for Social Security taxability.

    Provisional income = AGI + tax-exempt interest + half of SS benefits.
    IRC §86(b)(2).

    Known gap: We don't generate tax-exempt interest. For current scenarios
    this simplifies to (total non-SS income) + (SS / 2). When tax-exempt
    interest is added to the model, add it here.

    Args:
        person: A Person object with income fields.

    Returns:
        Provisional income in dollars.
    """
    non_ss_income = (
        person.wage_income
        + person.self_employment_income
        + person.retirement_income
        + person.interest_income
        + person.dividend_income
        + person.other_income
    )
    half_ss = person.social_security_income // 2
    return non_ss_income + half_ss


def ss_taxability_thresholds(
    filing_status: str, year: int,
) -> Tuple[int, int]:
    """Return the two-tier base amounts for SS taxability.

    Args:
        filing_status: Filing status string.
        year: Tax year.

    Returns:
        (lower_threshold, upper_threshold). For MFS living with spouse,
        both are 0, making up to 85% taxable immediately.
    """
    return _SS_BASE_AMOUNTS[year][filing_status]


def compute_taxable_ss(
    person: Any, filing_status: str, year: int = 2022,
) -> int:
    """Compute the taxable portion of Social Security benefits.

    Encodes the IRS Publication 915 Worksheet 1 (simplified). The two-tier
    calculation:
    - If provisional income <= lower threshold: $0 taxable.
    - If lower < provisional <= upper: taxable = min(50% of SS, 50% of excess
      over lower threshold).
    - If provisional > upper: taxable = min(85% of SS, $4500/$6000 + 85% of
      excess over upper threshold).

    The MFS-living-with-spouse edge case uses (0, 0) thresholds, making up
    to 85% immediately taxable. IRC §86(c)(2).

    Args:
        person: A Person with social_security_income and other income fields.
        filing_status: Filing status string.
        year: Tax year.

    Returns:
        Taxable Social Security amount in dollars.
    """
    ss_benefits = person.social_security_income
    if ss_benefits <= 0:
        return 0

    half_ss = ss_benefits // 2
    provisional = compute_provisional_income(person)
    lower, upper = ss_taxability_thresholds(filing_status, year)

    if provisional <= lower:
        return 0

    # Tier 1: up to 50% of benefits
    excess_over_lower = provisional - lower
    tier1_taxable = min(half_ss, excess_over_lower // 2)

    if provisional <= upper:
        return tier1_taxable

    # Tier 2: up to 85% of benefits
    # The "base amount" for tier 2 is the smaller of:
    #   - tier1 amount (which maxes at 50% of SS = half_ss)
    #   - $4,500 (single/HoH) or $6,000 (MFJ)
    # In practice for our scenarios, tier1_taxable is capped at half_ss,
    # and the Pub 915 worksheet uses: min(tier1_taxable, half of (upper - lower))
    tier1_cap = min(tier1_taxable, (upper - lower) // 2)

    excess_over_upper = provisional - upper
    tier2_addition = int(excess_over_upper * 0.85)

    max_taxable = int(ss_benefits * 0.85)
    return min(tier1_cap + tier2_addition, max_taxable)
