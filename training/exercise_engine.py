"""
Exercise engine — orchestrates full scenario creation.

Pipeline: generate household → overlay PII → render documents → inject errors → package

Modes:
- "intake": Student gets source docs, fills blank 13614-C Part I
- "verify": Student gets pre-filled 13614-C + source docs, finds discrepancies
- "crosscheck": Student verifies 1040 against source docs (future)
"""

import logging
from typing import Optional

from generator.models import Scenario
from generator.pipeline import HouseholdGenerator
from .document_renderer import DocumentRenderer
from .error_injector import ErrorInjector

logger = logging.getLogger(__name__)


class ExerciseEngine:
    """Orchestrates generation of complete training scenarios."""

    def __init__(self, state: str = "HI", year: int = 2022):
        self.generator = HouseholdGenerator(state, year)
        self.renderer = DocumentRenderer()
        self.error_injector = ErrorInjector()

    def generate_scenario(
        self,
        mode: str = "intake",
        difficulty: str = "easy",
        error_count: int = 3,
        pattern: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Scenario:
        """
        Generate a complete training scenario.

        Args:
            mode: "intake", "verify", or "crosscheck"
            difficulty: "easy", "medium", "hard"
            error_count: Number of errors to inject (verify mode only)
            pattern: Specific household pattern or None for random
            seed: Random seed for reproducibility

        Returns:
            Scenario with household, documents, and answer key
        """
        # TODO: Implement
        pass
