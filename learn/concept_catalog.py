"""Concept catalog — registry and evaluator for tax-law concepts.

The catalog holds all registered concepts and evaluates them against
a scenario to produce ``concept_tags``. Pipeline position: Stage 5
(after ground truth, before obfuscation).

Exception-handling contract: a buggy concept must not blow up the
entire labeling pass. ``run_all`` wraps each ``matches()`` call in
a try/except, logs the failure with the concept name and exception,
treats it as "did not match," and continues.
"""

import logging
from typing import Any, List, Set

from .concepts.base import Concept

logger = logging.getLogger(__name__)


class ConceptCatalog:
    """Registry of tax-law concepts with fault-tolerant evaluation."""

    def __init__(self) -> None:
        self._concepts: List[Concept] = []

    def register(self, concept: Concept) -> None:
        """Add a concept to the catalog.

        Args:
            concept: A Concept instance to evaluate during labeling.
        """
        self._concepts.append(concept)
        logger.debug("Registered concept: %s", concept.name)

    @property
    def concepts(self) -> List[Concept]:
        """Return the registered concept list."""
        return list(self._concepts)

    def run_all(self, scenario: Any) -> Set[str]:
        """Evaluate all concepts against a scenario.

        Wraps each ``matches()`` call in a try/except so a single
        buggy concept cannot break the labeling pass.

        Args:
            scenario: Scenario with ground_truth and household populated.

        Returns:
            Set of concept names (tags) that matched.
        """
        tags: Set[str] = set()

        for concept in self._concepts:
            try:
                if concept.matches(scenario):
                    tags.add(concept.name)
            except Exception:
                logger.exception(
                    "Concept '%s' raised during matches(); treating as no-match",
                    concept.name,
                )

        logger.info(
            "Concept labeling complete: %d/%d concepts matched",
            len(tags), len(self._concepts),
        )
        return tags
