"""Concept: qualifying_child_residency.

Fires when a scenario contains a dependent with partial-year residency,
exercising IRC §152(c)(1)(B) — the "more than half the year" rule.

A child at exactly 6 months fails the residency test. A child at 7+
months passes. The concept fires when the scenario has at least one
child in the boundary zone (0 < months < 12), forcing the student to
evaluate the rule rather than assuming full-year residency.
"""

from typing import Any

from learn.concepts.base import Concept


class QualifyingChildResidencyConcept(Concept):
    """Fires when a dependent has partial-year residency."""
    name = "qualifying_child_residency"

    def matches(self, scenario: Any) -> bool:
        hh = scenario.household
        if hh is None:
            return False
        for dep in hh.get_dependents():
            if 0 < dep.months_in_home < 12:
                return True
        return False
