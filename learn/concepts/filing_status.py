"""Concepts: hoh_qualifying_person, refundable_credit_only_filer.

Filing-status concepts that test whether the student recognizes
non-obvious filing situations.
"""

from typing import Any

from learn.concepts.base import Concept
from tax_core.predicates.credits import qualifies_for_actc, qualifies_for_eitc
from tax_core.predicates.filing_status import has_qualifying_person_for_hoh
from tax_core.predicates.income import filing_threshold_for, total_income


class HoHQualifyingPersonConcept(Concept):
    """Fires when the filer qualifies for Head of Household status.

    Tests IRC §2(b): unmarried, paid >50% household costs, and has a
    qualifying person. The most-blown call at VITA sites — preparers
    default to "single" for unmarried clients, missing HoH eligibility.
    """
    name = "hoh_qualifying_person"

    def matches(self, scenario: Any) -> bool:
        hh = scenario.household
        if hh is None:
            return False
        householder = hh.get_householder()
        if householder is None:
            return False
        if hh.is_married():
            return False
        return has_qualifying_person_for_hoh(householder, hh)


class RefundableCreditOnlyFilerConcept(Concept):
    """Fires when a filer is below filing threshold but credit-eligible.

    Tests the scenario where a taxpayer isn't required to file but
    should file to claim refundable credits (EITC, ACTC). The student
    must recognize that "below filing threshold" doesn't mean "can't file."
    """
    name = "refundable_credit_only_filer"

    def matches(self, scenario: Any) -> bool:
        hh = scenario.household
        gt = scenario.ground_truth
        if hh is None or gt is None:
            return False

        householder = hh.get_householder()
        if householder is None:
            return False

        filing_status = gt.get("filing_status", "")
        if not filing_status:
            return False

        income = total_income(householder)
        threshold = filing_threshold_for(filing_status, hh.year)

        if income >= threshold:
            return False

        return (
            qualifies_for_eitc(householder, hh, hh.year)
            or qualifies_for_actc(householder, hh, hh.year)
        )
