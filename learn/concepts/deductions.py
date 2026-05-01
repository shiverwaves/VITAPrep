"""Concept: standard_vs_itemized.

Tests whether the student evaluates the standard-vs-itemized deduction
choice correctly.
"""

from typing import Any

from learn.concepts.base import Concept


class StandardVsItemizedConcept(Concept):
    """Fires when itemizing beats the standard deduction.

    Reads from ground_truth.deduction_type rather than recomputing —
    ground truth already ran the comparison at Stage 4. The concept
    fires when the scenario requires the student to recognize that
    itemizing produces a larger deduction.
    """
    name = "standard_vs_itemized"

    def matches(self, scenario: Any) -> bool:
        gt = scenario.ground_truth
        if gt is None:
            return False
        return gt.get("deduction_type") == "itemized"
