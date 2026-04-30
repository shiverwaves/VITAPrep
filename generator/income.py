"""
Income generator — Part 2 of VITA intake.

Assigns income amounts and creates income document objects (W-2, 1099-INT,
1099-DIV, 1099-R, SSA-1099, 1099-NEC) for each adult Person.

Called after employment.py has populated employment_status, education,
and occupation_code on each Person.

Income types generated:
- Wage income → W-2 (1-2 per employed person)
- Self-employment income → 1099-NEC
- Interest income → 1099-INT
- Dividend income → 1099-DIV
- Social Security → SSA-1099
- Retirement distributions → 1099-R
"""

import logging
import random
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from faker import Faker

from .models import (
    Address,
    Employer,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Household,
    Person,
    SSA1099,
    W2,
)
from .sampler import sample_from_bracket, weighted_sample

logger = logging.getLogger(__name__)

_fake = Faker("en_US")

# Social Security wage base (2023 — adjust by tax year if needed)
_SS_WAGE_BASE = 160_200
_SS_TAX_RATE = 0.062
_MEDICARE_TAX_RATE = 0.0145

# Simplified effective federal tax rates by income bracket
_FED_TAX_BRACKETS = [
    (11_000, 0.10),
    (44_725, 0.12),
    (95_375, 0.22),
    (182_100, 0.24),
    (231_250, 0.32),
    (578_125, 0.35),
    (float("inf"), 0.37),
]

# Bank and brokerage names for 1099 payers
_BANK_NAMES = [
    "First Hawaiian Bank", "Bank of Hawaii", "American Savings Bank",
    "Chase Bank", "Wells Fargo Bank", "Bank of America",
    "US Bank", "Citibank", "Capital One", "Ally Bank",
    "Marcus by Goldman Sachs", "Discover Bank",
]

_BROKERAGE_NAMES = [
    "Charles Schwab", "Fidelity Investments", "Vanguard",
    "TD Ameritrade", "E*TRADE", "Merrill Lynch",
    "Morgan Stanley", "Edward Jones",
]

_RETIREMENT_PAYER_NAMES = [
    "Fidelity Investments", "Vanguard", "TIAA",
    "T. Rowe Price", "Principal Financial",
    "State of Hawaii ERS", "Federal Retirement Thrift",
    "MetLife", "Prudential Financial",
]

# Age bracket helper (same as employment.py)
def _age_to_bracket(age: int) -> str:
    if age < 18:
        return "Under 18"
    elif age <= 24:
        return "18-24"
    elif age <= 34:
        return "25-34"
    elif age <= 44:
        return "35-44"
    elif age <= 54:
        return "45-54"
    elif age <= 64:
        return "55-64"
    else:
        return "65+"


def _generate_ein() -> str:
    """Generate a random EIN in XX-XXXXXXX format."""
    prefix = random.randint(10, 99)
    suffix = random.randint(0, 9_999_999)
    return f"{prefix:02d}-{suffix:07d}"


def _generate_employer(state: str) -> Employer:
    """Generate a synthetic employer with Faker."""
    return Employer(
        name=_fake.company(),
        ein=_generate_ein(),
        address=Address(
            street=_fake.street_address(),
            city=_fake.city(),
            state=state,
            zip_code=_fake.zipcode_in_state(state_abbr=state),
        ),
    )


def _generate_payer_tin() -> str:
    """Generate a payer TIN in XX-XXXXXXX format."""
    return _generate_ein()


def _estimate_federal_tax(taxable_income: int) -> int:
    """Estimate federal income tax using simplified progressive brackets."""
    tax = 0
    prev_limit = 0
    for limit, rate in _FED_TAX_BRACKETS:
        if taxable_income <= prev_limit:
            break
        bracket_income = min(taxable_income, int(limit)) - prev_limit
        tax += bracket_income * rate
        prev_limit = int(limit)
    return int(tax)


def _compute_withholding(wages: int, state: str) -> Dict[str, int]:
    """Compute W-2 tax withholding amounts from gross wages."""
    ss_wages = min(wages, _SS_WAGE_BASE)
    return {
        "federal_tax_withheld": _estimate_federal_tax(wages),
        "social_security_wages": ss_wages,
        "social_security_tax": int(ss_wages * _SS_TAX_RATE),
        "medicare_wages": wages,
        "medicare_tax": int(wages * _MEDICARE_TAX_RATE),
        "state_wages": wages,
        "state_tax": int(wages * _get_state_tax_rate(state)),
    }


def _get_state_tax_rate(state: str) -> float:
    """Simplified state income tax rate."""
    no_income_tax = {"AK", "FL", "NV", "NH", "SD", "TN", "TX", "WA", "WY"}
    if state in no_income_tax:
        return 0.0
    rates = {
        "HI": 0.065, "CA": 0.073, "NY": 0.055, "NJ": 0.054,
        "OR": 0.068, "MN": 0.061, "IL": 0.0495, "MA": 0.05,
    }
    return rates.get(state, 0.045)


class IncomeGenerator:
    """Assigns income amounts and creates income document objects.

    Required distribution tables (all optional — fallbacks used if missing):
        occupation_wages, age_income_adjustments, social_security,
        retirement_income, interest_and_dividend_income,
        other_income_by_employment_status, public_assistance_income,
        occupation_self_employment_rates
    """

    def __init__(
        self,
        distributions: Dict[str, pd.DataFrame],
        tax_year: int = 2024,
    ) -> None:
        self.distributions = distributions
        self.tax_year = tax_year

    def overlay(self, household: Household) -> None:
        """Populate income fields and create document objects for all adults.

        Args:
            household: Household with employment attributes already set.
        """
        state = household.state or "HI"

        for person in household.members:
            if not person.is_adult():
                continue

            if person.employment_status == "employed":
                self._assign_wage_income(person, state)

            self._assign_investment_income(person)
            self._assign_social_security(person)
            self._assign_retirement_income(person)
            self._assign_other_income(person)

        total = household.total_household_income()
        logger.info(
            "Income overlay: household total $%s, %d members with income",
            f"{total:,}",
            sum(1 for p in household.members if p.total_income() > 0),
        )

    # =================================================================
    # Wage income → W-2 / 1099-NEC
    # =================================================================

    def _assign_wage_income(self, person: Person, state: str) -> None:
        """Assign wage income and create W-2 or 1099-NEC documents."""
        base_wage = self._sample_occupation_wage(person)
        adjusted_wage = self._apply_age_adjustment(base_wage, person.age)

        # Check for self-employment
        if self._is_self_employed(person):
            self._create_1099_nec(person, adjusted_wage, state)
            return

        # Determine number of W-2s (85% have 1, 15% have 2)
        if adjusted_wage > 20_000 and random.random() < 0.15:
            split = random.uniform(0.3, 0.7)
            wages = [int(adjusted_wage * split), int(adjusted_wage * (1 - split))]
        else:
            wages = [adjusted_wage]

        total_wages = 0
        for w in wages:
            w2 = self._create_w2(person, w, state)
            person.w2s.append(w2)
            total_wages += w

        person.wage_income = total_wages

    def _sample_occupation_wage(self, person: Person) -> int:
        """Sample a wage from occupation-specific distribution."""
        table = self.distributions.get("occupation_wages")

        if table is not None and not table.empty and person.occupation_code:
            rows = table[table["occupation_group"] == person.occupation_code]
            if not rows.empty:
                row = rows.iloc[0]
                p25 = int(row["p25_wage"])
                p75 = int(row["p75_wage"])
                median = int(row["median_wage"])
                # Sample around median with spread
                wage = int(np.random.normal(median, (p75 - p25) / 2.5))
                return max(wage, int(p25 * 0.5))

        # Fallback: education-based wage estimate
        return self._fallback_wage(person.education)

    def _fallback_wage(self, education: str) -> int:
        """Estimate wage based on education level when no table available."""
        ranges = {
            "less_than_hs": (18_000, 32_000),
            "high_school": (22_000, 42_000),
            "some_college": (25_000, 50_000),
            "associates": (28_000, 55_000),
            "bachelors": (35_000, 80_000),
            "masters": (45_000, 100_000),
            "professional": (60_000, 150_000),
            "doctorate": (55_000, 130_000),
        }
        low, high = ranges.get(education, (25_000, 50_000))
        return random.randint(low, high)

    def _apply_age_adjustment(self, base_wage: int, age: int) -> int:
        """Scale wage by age-based adjustment factor."""
        table = self.distributions.get("age_income_adjustments")
        bracket = _age_to_bracket(age)

        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                factor = float(rows.iloc[0]["adjustment_factor"])
                return max(int(base_wage * factor), 10_000)

        # Fallback: simple age curve
        if age <= 24:
            factor = 0.60
        elif age <= 34:
            factor = 0.85
        elif age <= 54:
            factor = 1.10
        elif age <= 64:
            factor = 1.05
        else:
            factor = 0.80
        return max(int(base_wage * factor), 10_000)

    def _is_self_employed(self, person: Person) -> bool:
        """Check if person should be self-employed based on occupation."""
        table = self.distributions.get("occupation_self_employment_rates")

        if table is not None and not table.empty and person.occupation_code:
            rows = table[table["occupation_group"] == person.occupation_code]
            if not rows.empty:
                rate = float(rows.iloc[0]["se_rate"])
                return bool(random.random() < rate)

        return bool(random.random() < 0.10)

    def _create_w2(self, person: Person, wages: int, state: str) -> W2:
        """Create a W-2 document object with computed withholding."""
        employer = _generate_employer(state)
        wh = _compute_withholding(wages, state)

        # ~20% chance of 401(k) contribution (Box 12, code D)
        box_12: List[Tuple[str, int]] = []
        if wages > 30_000 and random.random() < 0.20:
            contrib_rate = random.uniform(0.03, 0.10)
            contrib = min(int(wages * contrib_rate), 22_500)
            box_12.append(("D", contrib))

        return W2(
            employer=employer,
            wages=wages,
            federal_tax_withheld=wh["federal_tax_withheld"],
            social_security_wages=wh["social_security_wages"],
            social_security_tax=wh["social_security_tax"],
            medicare_wages=wh["medicare_wages"],
            medicare_tax=wh["medicare_tax"],
            box_12=box_12,
            state=state,
            state_wages=wh["state_wages"],
            state_tax=wh["state_tax"],
            control_number=f"{random.randint(10000, 99999)}",
        )

    def _create_1099_nec(self, person: Person, amount: int, state: str) -> None:
        """Create a 1099-NEC for self-employment income."""
        person.self_employment_income = amount
        person.form_1099_necs.append(Form1099NEC(
            payer_name=_fake.company(),
            payer_tin=_generate_payer_tin(),
            nonemployee_compensation=amount,
            federal_tax_withheld=0,
        ))

    # =================================================================
    # Investment income → 1099-INT / 1099-DIV
    # =================================================================

    def _assign_investment_income(self, person: Person) -> None:
        """Assign interest and dividend income based on age distribution."""
        bracket = _age_to_bracket(person.age)
        table = self.distributions.get("interest_and_dividend_income")

        has_investment = False
        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                proportion = float(rows.iloc[0]["has_inv_proportion"])
                has_investment = random.random() < proportion
        else:
            # Fallback: age-correlated probability
            if person.age >= 65:
                has_investment = random.random() < 0.40
            elif person.age >= 45:
                has_investment = random.random() < 0.25
            elif person.age >= 30:
                has_investment = random.random() < 0.15
            else:
                has_investment = random.random() < 0.05

        if not has_investment:
            return

        # Sample total investment amount from distribution
        total_inv = self._sample_investment_amount(bracket, table)
        if total_inv <= 0:
            return

        # Split between interest and dividends
        # ~60% of people with investment income have interest, ~40% dividends, some both
        roll = random.random()
        if roll < 0.35:
            self._create_1099_int(person, total_inv)
        elif roll < 0.60:
            self._create_1099_div(person, total_inv)
        else:
            int_share = random.uniform(0.3, 0.7)
            self._create_1099_int(person, int(total_inv * int_share))
            self._create_1099_div(person, int(total_inv * (1 - int_share)))

    def _sample_investment_amount(
        self, bracket: str, table: Optional[pd.DataFrame]
    ) -> int:
        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                sampled = weighted_sample(rows, "weight")
                income_bracket = str(sampled.iloc[0]["income_bracket"])
                return sample_from_bracket(income_bracket)

        return random.randint(100, 5_000)

    def _create_1099_int(self, person: Person, amount: int) -> None:
        person.interest_income = amount
        person.form_1099_ints.append(Form1099INT(
            payer_name=random.choice(_BANK_NAMES),
            payer_tin=_generate_payer_tin(),
            interest_income=amount,
        ))

    def _create_1099_div(self, person: Person, amount: int) -> None:
        qualified = int(amount * random.uniform(0.5, 0.9))
        person.dividend_income = amount
        person.form_1099_divs.append(Form1099DIV(
            payer_name=random.choice(_BROKERAGE_NAMES),
            payer_tin=_generate_payer_tin(),
            ordinary_dividends=amount,
            qualified_dividends=qualified,
        ))

    # =================================================================
    # Social Security → SSA-1099
    # =================================================================

    def _assign_social_security(self, person: Person) -> None:
        """Assign Social Security benefits for eligible persons (62+)."""
        if person.age < 62:
            return

        bracket = _age_to_bracket(person.age)
        table = self.distributions.get("social_security")

        has_ss = False
        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                proportion = float(rows.iloc[0]["has_ss_proportion"])
                has_ss = random.random() < proportion
        else:
            if person.age >= 67:
                has_ss = random.random() < 0.90
            elif person.age >= 65:
                has_ss = random.random() < 0.80
            else:
                has_ss = random.random() < 0.40

        if not has_ss:
            return

        amount = self._sample_ss_amount(bracket, table)
        if amount <= 0:
            return

        person.social_security_income = amount
        person.ssa_1099 = SSA1099(
            total_benefits=amount,
            benefits_repaid=0,
            net_benefits=amount,
        )

    def _sample_ss_amount(
        self, bracket: str, table: Optional[pd.DataFrame]
    ) -> int:
        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                sampled = weighted_sample(rows, "weight")
                income_bracket = str(sampled.iloc[0]["income_bracket"])
                return sample_from_bracket(income_bracket)

        return random.randint(8_000, 28_000)

    # =================================================================
    # Retirement income → 1099-R
    # =================================================================

    def _assign_retirement_income(self, person: Person) -> None:
        """Assign retirement distribution income for eligible persons (55+)."""
        if person.age < 55:
            return

        bracket = _age_to_bracket(person.age)
        table = self.distributions.get("retirement_income")

        has_ret = False
        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                proportion = float(rows.iloc[0]["has_ret_proportion"])
                has_ret = random.random() < proportion
        else:
            if person.age >= 72:
                has_ret = random.random() < 0.50
            elif person.age >= 65:
                has_ret = random.random() < 0.35
            else:
                has_ret = random.random() < 0.15

        if not has_ret:
            return

        amount = self._sample_retirement_amount(bracket, table)
        if amount <= 0:
            return

        # Distribution code
        if person.age >= 59:
            code = "7"  # Normal distribution
        elif person.has_disability:
            code = "3"  # Disability
        else:
            code = "1"  # Early distribution

        taxable = int(amount * random.uniform(0.85, 1.0))
        fed_withheld = int(taxable * random.uniform(0.10, 0.20))

        person.retirement_income = amount
        person.form_1099_rs.append(Form1099R(
            payer_name=random.choice(_RETIREMENT_PAYER_NAMES),
            payer_tin=_generate_payer_tin(),
            gross_distribution=amount,
            taxable_amount=taxable,
            federal_tax_withheld=fed_withheld,
            distribution_code=code,
        ))

    def _sample_retirement_amount(
        self, bracket: str, table: Optional[pd.DataFrame]
    ) -> int:
        if table is not None and not table.empty:
            rows = table[table["age_bracket"] == bracket]
            if not rows.empty:
                sampled = weighted_sample(rows, "weight")
                income_bracket = str(sampled.iloc[0]["income_bracket"])
                return sample_from_bracket(income_bracket)

        return random.randint(5_000, 35_000)

    # =================================================================
    # Other income
    # =================================================================

    def _assign_other_income(self, person: Person) -> None:
        """Assign other income (unemployment, misc) at low probability."""
        table = self.distributions.get("other_income_by_employment_status")

        has_other = False
        if table is not None and not table.empty:
            rows = table[table["employment_status"] == person.employment_status]
            if not rows.empty:
                total_weight = float(rows["weight"].sum())
                # Use a low base rate — other income is uncommon
                has_other = random.random() < min(total_weight / 100_000, 0.10)
        else:
            has_other = random.random() < 0.05

        if not has_other:
            return

        if table is not None and not table.empty:
            rows = table[table["employment_status"] == person.employment_status]
            if not rows.empty:
                sampled = weighted_sample(rows, "weight")
                income_bracket = str(sampled.iloc[0]["income_bracket"])
                amount = sample_from_bracket(income_bracket)
            else:
                amount = random.randint(500, 8_000)
        else:
            amount = random.randint(500, 8_000)

        person.other_income = amount
