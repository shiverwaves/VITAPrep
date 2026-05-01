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
Best-effort biases passed to the generator to increase the likelihood
of a concept firing. Each field is optional; unset fields leave the
generator's default behavior unchanged. Fields are flat and per-concept
(Option A from BUILD_PLAN). If flat hints become unwieldy, refactor to
named trait bundles (Option B).
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any, List, Optional, Tuple


@dataclass
class GenerationHints:
    """Best-effort biases passed to the generator.

    Each concept populates only the fields it needs. The engine merges
    hints from all requested concepts before passing to the generator.
    """
    preferred_patterns: List[str] = field(default_factory=list)

    child_months_in_home_range: Optional[Tuple[int, int]] = None

    force_self_employment: bool = False

    force_ss_recipient: bool = False
    min_other_income: Optional[int] = None

    max_wage_income: Optional[int] = None

    force_homeowner: bool = False

    force_full_time_student: bool = False


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

        Override to bias the generator toward scenarios that exercise
        this concept. The engine merges hints from all requested
        concepts before passing to the generator.
        """
        return GenerationHints()
