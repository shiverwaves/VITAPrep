"""Return-level tax computation functions.

Each function is small, calls existing tax_core predicates and thresholds,
and returns a single computation result. The orchestrator
(compute_ground_truth in ground_truth.py) calls these in order.

The computation layer orchestrates; the predicate layer decides.
"""

from dataclasses import dataclass, field
from typing import Any, Dict, List, Tuple

from tax_core.ground_truth import PersonClassification
from tax_core.predicates.credits import qualifies_for_actc, qualifies_for_eitc
from tax_core.predicates.deductions import (
    compute_itemized_total,
    compute_medical_deduction,
    compute_salt,
    should_itemize,
)
from tax_core.predicates.dependency import (
    qualifying_child_residency_test,
    qualifying_relative_test,
)
from tax_core.predicates.filing_status import derive_filing_status
from tax_core.predicates.income import (
    compute_taxable_ss,
    requires_schedule_se,
    total_income,
)
from tax_core.thresholds import (
    actc_max_per_child,
    ctc_amount,
    ctc_phaseout_threshold,
    educator_expense_limit,
    federal_brackets,
    ira_contribution_limit,
    se_income_factor,
    se_tax_rate,
    standard_deduction_for,
    student_loan_interest_limit,
)


@dataclass
class DeductionResult:
    """Result of the standard-vs-itemized deduction choice."""
    deduction_type: str  # "standard" or "itemized"
    amount: int
    standard_deduction: int
    itemized_total: int


@dataclass
class CreditResult:
    """Result of credit computation, splitting refundable vs nonrefundable."""
    nonrefundable_total: int = 0
    refundable_total: int = 0
    details: Dict[str, int] = field(default_factory=dict)
    # e.g. {"ctc": 4000, "actc": 0, "eitc": 0}


def classify_persons(
    household: Any, filing_status: str, year: int = 2022,
) -> Dict[str, PersonClassification]:
    """Classify each household member's role on the return.

    Primary filer = householder. Spouse = spouse. Children get dependency
    tests (residency for qualifying child, then qualifying relative as
    fallback). Returns dict keyed by person_id.

    Args:
        household: Household object.
        filing_status: Filing status string.
        year: Tax year.

    Returns:
        Dict mapping person_id to PersonClassification.
    """
    classifications: Dict[str, PersonClassification] = {}

    for person in household.members:
        rel = person.relationship
        if hasattr(rel, "value"):
            rel = rel.value

        if rel == "householder":
            classifications[person.person_id] = PersonClassification(
                person_id=person.person_id,
                role="primary",
                dependency_type="none",
                credit_eligibility={},
            )
        elif rel == "spouse":
            classifications[person.person_id] = PersonClassification(
                person_id=person.person_id,
                role="spouse",
                dependency_type="none",
                credit_eligibility={},
            )
        else:
            dep_type = "none"
            credit_elig: Dict[str, bool] = {}

            if person.age < 19 or (
                person.age < 24 and getattr(person, "is_full_time_student", False)
            ):
                res = qualifying_child_residency_test(person, year)
                if res.passed:
                    dep_type = "qualifying_child"
                    credit_elig["ctc"] = person.age < 17
                    credit_elig["eitc_qualifying_child"] = True
            if dep_type == "none":
                qr = qualifying_relative_test(person, household, year)
                if qr.passed:
                    dep_type = "qualifying_relative"

            classifications[person.person_id] = PersonClassification(
                person_id=person.person_id,
                role="dependent" if dep_type != "none" else "other",
                dependency_type=dep_type,
                credit_eligibility=credit_elig,
            )

    return classifications


def compute_se_tax(person: Any, year: int = 2022) -> int:
    """Compute self-employment tax for a person. IRC §1401.

    SE tax = 15.3% of (92.35% of net SE income).
    Only applies if SE income >= $400 (checked via requires_schedule_se).

    Args:
        person: Person object with self_employment_income.
        year: Tax year.

    Returns:
        SE tax amount in dollars.
    """
    if not requires_schedule_se(person):
        return 0
    se_income = person.self_employment_income
    taxable_se = int(se_income * se_income_factor(year))
    return int(taxable_se * se_tax_rate(year))


def compute_agi(household: Any, year: int = 2022) -> int:
    """Compute adjusted gross income. IRC §62.

    AGI = gross income - above-the-line deductions.
    Above-the-line deductions include: student loan interest, educator
    expenses, IRA contributions, and the deductible half of SE tax.

    Args:
        household: Household object with members.
        year: Tax year.

    Returns:
        AGI in dollars.
    """
    gross = 0
    above_line = 0

    for person in household.members:
        gross += total_income(person)

        above_line += min(
            person.student_loan_interest,
            student_loan_interest_limit(year),
        )
        above_line += min(
            person.educator_expenses,
            educator_expense_limit(year),
        )
        above_line += min(
            person.ira_contributions,
            ira_contribution_limit(person.age, year),
        )
        above_line += compute_se_tax(person, year) // 2

    return gross - above_line


def choose_deduction(
    household: Any, filing_status: str, agi: int, year: int = 2022,
) -> DeductionResult:
    """Choose between standard and itemized deductions.

    Delegates to existing predicates from Restructure A.

    Args:
        household: Household object.
        filing_status: Filing status string.
        agi: Adjusted gross income (for medical deduction floor).
        year: Tax year.

    Returns:
        DeductionResult with chosen type and amount.
    """
    salt = compute_salt(household.state_income_tax, household.property_taxes, year)
    medical = compute_medical_deduction(household.medical_expenses, agi)
    itemized = compute_itemized_total(
        salt, household.mortgage_interest, medical, household.charitable_contributions,
    )
    standard = standard_deduction_for(filing_status, year)

    if should_itemize(itemized, filing_status, year):
        return DeductionResult(
            deduction_type="itemized",
            amount=itemized,
            standard_deduction=standard,
            itemized_total=itemized,
        )
    return DeductionResult(
        deduction_type="standard",
        amount=standard,
        standard_deduction=standard,
        itemized_total=itemized,
    )


def compute_federal_tax(
    taxable_income: int, filing_status: str, year: int = 2022,
) -> int:
    """Compute federal income tax using progressive brackets. IRC §1.

    Args:
        taxable_income: Taxable income after deductions.
        filing_status: Filing status string.
        year: Tax year.

    Returns:
        Federal income tax in dollars.
    """
    if taxable_income <= 0:
        return 0
    brackets = federal_brackets(filing_status, year)
    tax = 0
    prev_bound = 0
    for upper_bound, rate in brackets:
        if taxable_income <= prev_bound:
            break
        taxable_in_bracket = min(taxable_income, upper_bound) - prev_bound
        tax += int(taxable_in_bracket * rate)
        prev_bound = upper_bound
    return tax


def compute_credits(
    household: Any,
    classifications: Dict[str, PersonClassification],
    filing_status: str,
    agi: int,
    tax_before_credits: int,
    year: int = 2022,
) -> CreditResult:
    """Compute tax credits (CTC, ACTC, EITC stub).

    CTC: $2,000 per qualifying child under 17. Nonrefundable up to tax
    liability. Phases out at $50 per $1,000 over AGI threshold.
    ACTC: Refundable portion, up to $1,500 per child (2022).
    EITC: Stub — returns 0 (full tables deferred).

    Args:
        household: Household object.
        classifications: Person classifications from classify_persons.
        filing_status: Filing status string.
        agi: AGI for phase-out calculation.
        tax_before_credits: Tax before credits (caps nonrefundable).
        year: Tax year.

    Returns:
        CreditResult with nonrefundable/refundable split and details.
    """
    ctc_children = sum(
        1 for pc in classifications.values()
        if pc.credit_eligibility.get("ctc", False)
    )
    per_child = ctc_amount(year)
    raw_ctc = ctc_children * per_child

    phaseout_threshold = ctc_phaseout_threshold(filing_status, year)
    if agi > phaseout_threshold:
        excess_thousands = (agi - phaseout_threshold + 999) // 1000
        reduction = excess_thousands * 50
        raw_ctc = max(0, raw_ctc - reduction)

    nonrefundable_ctc = min(raw_ctc, tax_before_credits)

    actc = 0
    remaining_ctc = raw_ctc - nonrefundable_ctc
    if remaining_ctc > 0 and ctc_children > 0:
        filer = household.get_householder()
        if filer and qualifies_for_actc(filer, household, year):
            earned = filer.wage_income + filer.self_employment_income
            spouse = household.get_spouse()
            if spouse:
                earned += spouse.wage_income + spouse.self_employment_income
            refundable_calc = int((max(0, earned - 2500)) * 0.15)
            max_actc = ctc_children * actc_max_per_child(year)
            actc = min(remaining_ctc, refundable_calc, max_actc)

    eitc = 0

    return CreditResult(
        nonrefundable_total=nonrefundable_ctc,
        refundable_total=actc + eitc,
        details={
            "ctc": nonrefundable_ctc,
            "actc": actc,
            "eitc": eitc,
        },
    )


def total_payments(household: Any) -> int:
    """Sum all federal tax withholding from W-2s and 1099s.

    Reads Box 2 from W-2s and Box 4 from 1099-INT, 1099-DIV, 1099-R,
    1099-NEC for every person in the household.

    Args:
        household: Household object with members.

    Returns:
        Total federal tax withheld in dollars.
    """
    total = 0
    for person in household.members:
        for w2 in person.w2s:
            total += w2.federal_tax_withheld
        for f in person.form_1099_ints:
            total += f.federal_tax_withheld
        for f in person.form_1099_divs:
            total += f.federal_tax_withheld
        for f in person.form_1099_rs:
            total += f.federal_tax_withheld
        for f in person.form_1099_necs:
            total += f.federal_tax_withheld
    return total
