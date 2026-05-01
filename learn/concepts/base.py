"""Base class for tax-law concepts and generation hints.

A Concept identifies whether a scenario exercises a specific tax-law
feature. Concepts evaluate at Stage 5 (after ground truth) and produce
tags stored in ``scenario.concept_tags``.

Concept evaluation constraint
-----------------------------
Concepts can read ``scenario.ground_truth``, ``scenario.household``,
and ``scenario.document_paths``. They MUST NOT read
``scenario.interview_notes`` (not yet populated at Stage 5) or
``scenario.concept_tags`` (that's what they're producing). This
constraint is enforced by pipeline ordering and verified by test.

GenerationHints
---------------
A placeholder for Restructure E. Concepts return empty hints in D;
E will populate them to bias the generator toward scenarios that
exercise specific concepts.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass
class GenerationHints:
    """Best-effort biases passed to the generator.

    Empty in Restructure D. Restructure E will add fields like
    preferred patterns, income ranges, and household compositions
    that increase the likelihood of a concept firing.
    """
    preferred_patterns: List[str] = field(default_factory=list)
    hints: Dict[str, Any] = field(default_factory=dict)


class Concept(ABC):
    """A tax-law feature that a scenario may exercise.

    Subclasses implement ``matches()`` to evaluate whether a scenario
    exercises this concept. The concept name becomes a tag in
    ``scenario.concept_tags``.

    Concepts run at Stage 5 (after ground truth). They have access to
    ``scenario.ground_truth``, ``scenario.household``, and
    ``scenario.document_paths``.

    Concepts MUST NOT read ``scenario.interview_notes`` or
    ``scenario.concept_tags``. Those fields do not exist yet at
    Stage 5 and are None.
    """
    name: str = ""

    @abstractmethod
    def matches(self, scenario: Any) -> bool:
        """Evaluate whether this concept is exercised by the scenario.

        Args:
            scenario: Scenario with ground_truth and household populated.

        Returns:
            True if the scenario exercises this tax-law concept.
        """

    def generation_hints(self) -> GenerationHints:
        """Return generation hints for targeting this concept.

        Returns empty hints in Restructure D. Override in E to bias
        the generator toward scenarios that exercise this concept.
        """
        return GenerationHints()
