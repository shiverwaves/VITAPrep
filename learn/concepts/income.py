"""Concepts: self_employment_threshold, social_security_taxability.

Income concepts that test whether the student recognizes situations
requiring additional forms or computations.
"""

from typing import Any

from learn.concepts.base import Concept, GenerationHints
from tax_core.predicates.income import (
    compute_taxable_ss,
    requires_schedule_se,
)


class SelfEmploymentThresholdConcept(Concept):
    """Fires when any household member has SE income >= $400.

    Tests IRC §1401/§1402: net SE earnings of $400+ trigger Schedule SE.
    The most common Part 2 mistake — new preparers see freelance income
    as ordinary income and miss Schedule SE entirely.
    """
    name = "self_employment_threshold"

    def generation_hints(self) -> GenerationHints:
        return GenerationHints(
            force_self_employment=True,
        )

    def matches(self, scenario: Any) -> bool:
        hh = scenario.household
        if hh is None:
            return False
        for member in hh.members:
            if requires_schedule_se(member):
                return True
        return False


class SocialSecurityTaxabilityConcept(Concept):
    """Fires when a filer has taxable Social Security benefits.

    Tests IRC §86: SS becomes partially taxable when provisional income
    exceeds base amounts. Common, counterintuitive, and missed — new
    preparers either tax SS fully or not at all.
    """
    name = "social_security_taxability"

    def generation_hints(self) -> GenerationHints:
        return GenerationHints(
            force_ss_recipient=True,
            min_other_income=15000,
        )

    def matches(self, scenario: Any) -> bool:
        hh = scenario.household
        gt = scenario.ground_truth
        if hh is None or gt is None:
            return False

        filing_status = gt.get("filing_status", "")
        if not filing_status:
            return False

        for member in hh.members:
            if member.social_security_income <= 0:
                continue
            taxable = compute_taxable_ss(member, filing_status, hh.year)
            if taxable > 0:
                return True
        return False
