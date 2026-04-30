"""
Expense generator — Part 3 of VITA intake.

Assigns realistic expenses to households for tax deduction/credit scenarios:
- Itemized deductions (property taxes, mortgage interest, medical, charitable)
- Above-the-line deductions (student loan interest, educator expenses, IRA)
- Credit-related expenses (child care, education)
- Standard vs itemized deduction determination

Uses distribution tables from extract_part3 (homeownership_rates, property_taxes,
mortgage_costs) when available, with income-based fallbacks.

Ported from HouseholdRNG/generator/expense_generator.py.
"""

import logging
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

import random

from faker import Faker

from .models import (
    EmploymentStatus,
    Form1098,
    Form1098E,
    Form1098T,
    Household,
    Person,
)

_fake = Faker()

logger = logging.getLogger(__name__)


# =============================================================================
# HAWAII STATE TAX BRACKETS (2022)
# =============================================================================

HAWAII_TAX_BRACKETS_SINGLE: List[Tuple[int, float]] = [
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

HAWAII_TAX_BRACKETS_MFJ: List[Tuple[int, float]] = [
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

# 2022 standard deductions
STANDARD_DEDUCTION = {
    "single": 12950,
    "married_filing_jointly": 25900,
    "married_filing_separately": 12950,
    "head_of_household": 19400,
    "qualifying_surviving_spouse": 25900,
}

# Expense caps (2022 values)
IRA_CONTRIBUTION_LIMIT = 6000
IRA_CONTRIBUTION_LIMIT_50_PLUS = 7000
STUDENT_LOAN_INTEREST_LIMIT = 2500
EDUCATOR_EXPENSE_LIMIT = 300
SALT_CAP = 10000

# Mortgage interest fraction by age bracket — estimates the share of
# monthly payment going to interest vs principal based on typical loan
# maturity.  Younger = earlier in loan = more interest.
INTEREST_FRACTION_BY_AGE: Dict[str, float] = {
    "<25": 0.80,
    "25-34": 0.75,
    "35-44": 0.65,
    "45-54": 0.50,
    "55-64": 0.35,
    "65+": 0.25,
}

# Lender and institution names for expense document rendering
_MORTGAGE_LENDERS = [
    "First Hawaiian Bank", "Bank of Hawaii", "American Savings Bank",
    "Wells Fargo Home Mortgage", "Chase Home Lending",
    "Bank of America Home Loans", "US Bank Home Mortgage",
    "Rocket Mortgage", "PennyMac Loan Services",
]

_STUDENT_LOAN_SERVICERS = [
    "Nelnet", "MOHELA", "Aidvantage", "EdFinancial",
    "Great Lakes Educational Loan Services",
    "Navient", "FedLoan Servicing",
]

_UNIVERSITIES = [
    "University of Hawaii at Manoa", "Hawaii Pacific University",
    "Chaminade University", "Brigham Young University-Hawaii",
    "University of Hawaii at Hilo", "Kapiolani Community College",
    "Leeward Community College", "University of Phoenix",
    "Western Governors University",
]


def _generate_ein() -> str:
    prefix = random.randint(10, 99)
    suffix = random.randint(0, 9_999_999)
    return f"{prefix:02d}-{suffix:07d}"


class ExpenseGenerator:
    """Assigns expenses to household members for tax purposes.

    Uses distribution tables for housing costs when available, with
    demographic/income-based fallbacks for all categories.
    """

    def __init__(
        self,
        distributions: Dict[str, pd.DataFrame],
        state: str = "HI",
    ) -> None:
        self.distributions = distributions
        self.state = state.upper()
        self._log_available_tables()

    def _log_available_tables(self) -> None:
        expense_tables = [
            "homeownership_rates",
            "property_taxes",
            "mortgage_costs",
        ]
        available = [t for t in expense_tables if t in self.distributions]
        missing = [t for t in expense_tables if t not in self.distributions]
        logger.info("Expense tables available: %s", available)
        if missing:
            logger.info("Expense tables missing (will use fallbacks): %s", missing)

    def overlay(self, household: Household) -> None:
        """Assign all expense types to household.

        Args:
            household: Household with income from Part 2.
        """
        income = household.total_household_income()
        logger.info(
            "Expense generation starting for household %s, income=$%s",
            household.household_id, f"{income:,}",
        )

        self._assign_housing_expenses(household)
        self._assign_state_income_tax(household)
        self._assign_medical_expenses(household)
        self._assign_charitable_contributions(household)
        self._assign_above_line_deductions(household)
        self._assign_credit_expenses(household)
        self._calculate_totals(household)
        self._create_expense_documents(household)

        logger.info(
            "Expense generation complete: itemized=$%s, above_line=$%s, "
            "uses_standard=%s",
            f"{household.total_itemized_deductions:,}",
            f"{household.total_above_line_deductions:,}",
            household.uses_standard_deduction,
        )

    # =========================================================================
    # 1. HOUSING EXPENSES
    # =========================================================================

    def _assign_housing_expenses(self, household: Household) -> None:
        household.is_homeowner = self._determine_homeownership(household)

        if not household.is_homeowner:
            household.property_taxes = 0
            household.mortgage_interest = 0
            logger.debug("  Not a homeowner — no housing deductions")
            return

        household.property_taxes = self._sample_property_taxes(household)
        household.mortgage_interest = self._sample_mortgage_interest(household)
        logger.debug(
            "  Housing: property_taxes=$%d, mortgage_interest=$%d",
            household.property_taxes, household.mortgage_interest,
        )

    def _determine_homeownership(self, household: Household) -> bool:
        householder = household.get_householder()
        if not householder:
            return False

        age = householder.age
        income = household.total_household_income()

        dist = self.distributions.get("homeownership_rates")
        if dist is not None and len(dist) > 0:
            return self._sample_homeownership_from_data(age, income, dist)

        return self._estimate_homeownership(age, income)

    def _sample_homeownership_from_data(
        self, age: int, income: int, dist: pd.DataFrame,
    ) -> bool:
        age_bracket = self._age_to_bracket(age)
        income_bracket = self._income_to_bracket(income)

        filtered = dist[
            (dist["age_bracket"] == age_bracket)
            & (dist["income_bracket"] == income_bracket)
        ]
        if filtered.empty:
            filtered = dist[dist["income_bracket"] == income_bracket]
        if filtered.empty:
            filtered = dist[dist["age_bracket"] == age_bracket]
        if filtered.empty:
            filtered = dist

        if filtered.empty:
            return self._estimate_homeownership(age, income)

        owner_rows = filtered[
            filtered["tenure"].isin(["owner_with_mortgage", "owner_free_clear"])
        ]
        total_weight = filtered["weighted_count"].sum()
        owner_weight = owner_rows["weighted_count"].sum()

        if total_weight == 0:
            return False

        return float(np.random.random()) < (owner_weight / total_weight)

    def _estimate_homeownership(self, age: int, income: int) -> bool:
        if age < 25:
            base = 0.25
        elif age < 35:
            base = 0.37
        elif age < 45:
            base = 0.55
        elif age < 55:
            base = 0.65
        elif age < 65:
            base = 0.70
        else:
            base = 0.78

        if income < 25000:
            base *= 0.6
        elif income < 50000:
            base *= 0.8
        elif income < 100000:
            base *= 1.0
        elif income < 150000:
            base *= 1.1
        else:
            base *= 1.15

        if self.state == "HI":
            base *= 0.91

        return float(np.random.random()) < min(0.90, base)

    def _sample_property_taxes(self, household: Household) -> int:
        income = household.total_household_income()
        dist = self.distributions.get("property_taxes")

        if dist is not None and len(dist) > 0:
            bracket = self._income_to_bracket(income)
            filtered = dist[dist["income_bracket"] == bracket]
            if not filtered.empty:
                row = filtered.iloc[0]
                mean = float(row["mean_amount"])
                amount = int(np.random.normal(mean, mean * 0.25))
                return max(500, amount)

        if income < 50000:
            return int(np.random.uniform(1000, 2500))
        elif income < 100000:
            return int(np.random.uniform(2000, 4500))
        elif income < 200000:
            return int(np.random.uniform(3500, 7000))
        return int(np.random.uniform(5000, 12000))

    def _sample_mortgage_interest(self, household: Household) -> int:
        householder = household.get_householder()
        income = household.total_household_income()

        if householder and householder.age >= 65:
            if np.random.random() < 0.40:
                return 0

        dist = self.distributions.get("mortgage_costs")
        if dist is not None and len(dist) > 0:
            age = householder.age if householder else 40
            age_bracket = self._age_to_bracket(age)
            income_bracket = self._income_to_bracket(income)

            filtered = dist[
                (dist["income_bracket"] == income_bracket)
                & (dist["age_bracket"] == age_bracket)
            ]
            if filtered.empty:
                filtered = dist[dist["income_bracket"] == income_bracket]
            if filtered.empty:
                filtered = dist[dist["age_bracket"] == age_bracket]

            if not filtered.empty:
                row = filtered.iloc[0]
                monthly = float(row["mean_monthly"])
                monthly = max(0, int(np.random.normal(monthly, monthly * 0.20)))
                annual_payment = monthly * 12

                interest_frac = INTEREST_FRACTION_BY_AGE.get(age_bracket, 0.55)
                return int(annual_payment * interest_frac)

        # Fallback
        if income < 50000:
            return int(np.random.uniform(3000, 8000))
        elif income < 100000:
            return int(np.random.uniform(6000, 15000))
        elif income < 200000:
            return int(np.random.uniform(10000, 25000))
        return int(np.random.uniform(15000, 35000))

    # =========================================================================
    # 2. STATE INCOME TAX
    # =========================================================================

    def _assign_state_income_tax(self, household: Household) -> None:
        income = household.total_household_income()

        if household.pattern in (
            "married_couple_with_children",
            "married_couple_no_children",
        ):
            brackets = HAWAII_TAX_BRACKETS_MFJ
        else:
            brackets = HAWAII_TAX_BRACKETS_SINGLE

        household.state_income_tax = self._progressive_tax(income, brackets)
        logger.debug("  State tax: $%d", household.state_income_tax)

    @staticmethod
    def _progressive_tax(
        income: int, brackets: List[Tuple[int, float]],
    ) -> int:
        tax = 0.0
        prev = 0
        for bracket_max, rate in brackets:
            if income <= prev:
                break
            taxable = min(income, bracket_max) - prev
            tax += taxable * rate
            prev = bracket_max
        return int(tax)

    # =========================================================================
    # 3. MEDICAL EXPENSES
    # =========================================================================

    def _assign_medical_expenses(self, household: Household) -> None:
        has_elderly = any(m.age >= 65 for m in household.members)
        has_disabled = any(m.has_disability for m in household.members)
        member_count = len(household.members)

        prob = 0.10
        if has_elderly:
            prob += 0.25
        if has_disabled:
            prob += 0.20
        if member_count >= 4:
            prob += 0.10

        if np.random.random() >= prob:
            household.medical_expenses = 0
            return

        agi = household.total_household_income()
        floor = agi * 0.075
        excess = np.random.exponential(5000)
        household.medical_expenses = int(floor + excess)
        logger.debug("  Medical: $%d", household.medical_expenses)

    # =========================================================================
    # 4. CHARITABLE CONTRIBUTIONS
    # =========================================================================

    def _assign_charitable_contributions(self, household: Household) -> None:
        income = household.total_household_income()

        if np.random.random() >= 0.65:
            household.charitable_contributions = 0
            return

        if income < 30000:
            rate = float(np.random.uniform(0.005, 0.02))
        elif income < 75000:
            rate = float(np.random.uniform(0.01, 0.025))
        elif income < 150000:
            rate = float(np.random.uniform(0.015, 0.035))
        else:
            rate = float(np.random.uniform(0.02, 0.06))

        amount = int(income * rate)

        if np.random.random() < 0.05:
            amount = int(amount * np.random.uniform(1.5, 3.0))

        max_amount = int(income * 0.60)
        household.charitable_contributions = min(amount, max_amount)
        logger.debug("  Charitable: $%d", household.charitable_contributions)

    # =========================================================================
    # 5. ABOVE-THE-LINE DEDUCTIONS (per-person)
    # =========================================================================

    def _assign_above_line_deductions(self, household: Household) -> None:
        for person in household.members:
            if not person.is_adult():
                continue
            person.student_loan_interest = self._student_loan_interest(person)
            person.educator_expenses = self._educator_expenses(person)
            person.ira_contributions = self._ira_contributions(person)

    def _student_loan_interest(self, person: Person) -> int:
        if person.age < 22 or person.age > 50:
            return 0

        college = {
            "some_college", "associates", "bachelors",
            "masters", "doctorate", "professional",
        }
        if person.education not in college:
            return 0

        if person.education in ("masters", "doctorate", "professional"):
            prob, avg = 0.50, 1800
        elif person.education == "bachelors":
            prob, avg = 0.40, 1400
        else:
            prob, avg = 0.25, 800

        if person.age > 35:
            prob *= 0.6
        if person.age > 45:
            prob *= 0.5

        if np.random.random() >= prob:
            return 0

        interest = int(np.random.normal(avg, avg * 0.3))
        return min(max(0, interest), STUDENT_LOAN_INTEREST_LIMIT)

    def _educator_expenses(self, person: Person) -> int:
        if not person.occupation_code:
            return 0

        soc = str(person.occupation_code).replace("-", "")
        if not soc.startswith("25"):
            return 0

        if np.random.random() >= 0.70:
            return 0

        return int(np.random.uniform(150, EDUCATOR_EXPENSE_LIMIT))

    def _ira_contributions(self, person: Person) -> int:
        if person.employment_status != EmploymentStatus.EMPLOYED.value:
            return 0
        if person.age < 21 or person.age > 70:
            return 0

        if person.wage_income < 25000:
            prob = 0.05
        elif person.wage_income < 50000:
            prob = 0.10
        elif person.wage_income < 100000:
            prob = 0.18
        else:
            prob = 0.25

        if 35 <= person.age <= 55:
            prob *= 1.3

        if np.random.random() >= prob:
            return 0

        limit = (
            IRA_CONTRIBUTION_LIMIT_50_PLUS
            if person.age >= 50
            else IRA_CONTRIBUTION_LIMIT
        )

        if np.random.random() < 0.30:
            return limit
        return int(np.random.uniform(500, limit * 0.8))

    # =========================================================================
    # 6. CREDIT-RELATED EXPENSES
    # =========================================================================

    def _assign_credit_expenses(self, household: Household) -> None:
        household.child_care_expenses = self._child_care_expenses(household)
        household.education_expenses = self._education_expenses(household)

    def _child_care_expenses(self, household: Household) -> int:
        children_under_13 = [
            m for m in household.members
            if not m.is_adult() and m.age < 13
        ]
        if not children_under_13:
            return 0

        working_adults = [
            m for m in household.members
            if m.is_adult()
            and m.employment_status == EmploymentStatus.EMPLOYED.value
        ]
        if not working_adults:
            return 0

        if np.random.random() >= 0.65:
            return 0

        num_children = len(children_under_13)
        cost_per_child = int(np.random.uniform(8000, 15000))
        if num_children >= 2:
            cost_per_child = int(cost_per_child * 0.85)

        return min(cost_per_child * num_children, 16000)

    def _education_expenses(self, household: Household) -> int:
        students = []
        for m in household.members:
            if 18 <= m.age <= 24 and m.education in (
                "some_college", "associates", "bachelors",
            ):
                students.append("undergrad")
            elif 22 <= m.age <= 35 and m.education in (
                "masters", "doctorate", "professional",
            ):
                students.append("graduate")

        if not students:
            return 0

        if np.random.random() >= 0.60:
            return 0

        total = 0
        for stype in students:
            if stype == "undergrad":
                tuition = int(np.random.choice([
                    np.random.uniform(3000, 5000),
                    np.random.uniform(8000, 15000),
                ], p=[0.4, 0.6]))
            else:
                tuition = int(np.random.uniform(10000, 30000))
            total += tuition

        return total

    # =========================================================================
    # 7. TOTALS AND STANDARD VS ITEMIZED
    # =========================================================================

    def _calculate_totals(self, household: Household) -> None:
        income = household.total_household_income()

        # SALT: state income tax + property taxes, capped at $10K
        salt = min(
            household.state_income_tax + household.property_taxes,
            SALT_CAP,
        )

        # Medical: only the amount exceeding 7.5% of AGI is deductible
        medical_deductible = max(
            0, household.medical_expenses - int(income * 0.075),
        )

        household.total_itemized_deductions = (
            salt
            + household.mortgage_interest
            + medical_deductible
            + household.charitable_contributions
        )

        household.total_above_line_deductions = sum(
            p.student_loan_interest + p.educator_expenses + p.ira_contributions
            for p in household.members
        )

        filing_status = household.derive_filing_status().value
        standard = STANDARD_DEDUCTION.get(filing_status, 12950)
        household.uses_standard_deduction = (
            household.total_itemized_deductions <= standard
        )

        logger.debug(
            "  Totals: itemized=$%d, standard=$%d → %s",
            household.total_itemized_deductions,
            standard,
            "standard" if household.uses_standard_deduction else "itemized",
        )

    # =========================================================================
    # EXPENSE DOCUMENT CREATION
    # =========================================================================

    def _create_expense_documents(self, household: Household) -> None:
        """Create Form 1098, 1098-E, and 1098-T documents from assigned expenses."""
        householder = household.get_householder()
        if not householder:
            return

        # Form 1098 — Mortgage Interest Statement (issued to householder)
        if household.mortgage_interest > 0:
            principal = int(household.mortgage_interest / 0.04) if household.mortgage_interest > 0 else 0
            householder.form_1098s.append(Form1098(
                lender_name=random.choice(_MORTGAGE_LENDERS),
                lender_tin=_generate_ein(),
                mortgage_interest=household.mortgage_interest,
                outstanding_principal=principal,
                property_taxes=household.property_taxes,
            ))

        # Form 1098-E — Student Loan Interest (per-person)
        for person in household.members:
            if person.student_loan_interest > 0:
                person.form_1098_es.append(Form1098E(
                    lender_name=random.choice(_STUDENT_LOAN_SERVICERS),
                    lender_tin=_generate_ein(),
                    student_loan_interest=person.student_loan_interest,
                ))

        # Form 1098-T — Tuition Statement (issued to householder for household education)
        if household.education_expenses > 0:
            householder.form_1098_ts.append(Form1098T(
                institution_name=random.choice(_UNIVERSITIES),
                institution_tin=_generate_ein(),
                amounts_billed=household.education_expenses,
                student_ssn=householder.ssn,
            ))

    # =========================================================================
    # BRACKET HELPERS
    # =========================================================================

    @staticmethod
    def _age_to_bracket(age: int) -> str:
        if age < 25:
            return "<25"
        elif age < 35:
            return "25-34"
        elif age < 45:
            return "35-44"
        elif age < 55:
            return "45-54"
        elif age < 65:
            return "55-64"
        return "65+"

    @staticmethod
    def _income_to_bracket(income: int) -> str:
        if income < 25000:
            return "<$25K"
        elif income < 50000:
            return "$25-50K"
        elif income < 75000:
            return "$50-75K"
        elif income < 100000:
            return "$75-100K"
        elif income < 150000:
            return "$100-150K"
        return "$150K+"
