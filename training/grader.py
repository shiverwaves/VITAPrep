"""
Grader — compares student submissions to ground truth.

Mode 1 (intake): Field-by-field comparison of student-filled form vs ground truth.
Mode 2 (verify): Compare flagged errors vs injected error manifest.
"""

import logging
from typing import Dict, List

from generator.models import Household, InjectedError, GradingResult

logger = logging.getLogger(__name__)


class Grader:
    """Grades student submissions against scenario answer keys."""

    def grade_intake(
        self, submission: Dict, ground_truth: Household
    ) -> GradingResult:
        """Grade a student's intake form fill (Mode 1)."""
        # TODO: Implement
        pass

    def grade_verification(
        self,
        flagged_errors: List[Dict],
        actual_errors: List[InjectedError],
    ) -> GradingResult:
        """Grade a student's error identification (Mode 2)."""
        # TODO: Implement
        pass
