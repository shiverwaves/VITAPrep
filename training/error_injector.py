"""
Error injector — seeds deliberate discrepancies for verification exercises.

Takes a Household with PII and introduces errors between documents and/or
the intake form. Returns the modified data plus a manifest of injected errors
(used as the answer key).

Error categories: name, ssn, address, dob, filing_status, dependent, expiration
~15% of scenarios should be error-free to test student confidence.

See docs/VITA_FORM_FIELDS.md for field-level error examples.
"""

import logging
from typing import List, Tuple

from generator.models import Household, InjectedError

logger = logging.getLogger(__name__)


class ErrorInjector:
    """Seeds discrepancies between documents for verification exercises."""

    def inject(
        self,
        household: Household,
        difficulty: str = "medium",
        error_count: int = 3,
    ) -> Tuple[Household, List[InjectedError]]:
        """
        Inject errors into a household's PII/documents.

        Args:
            household: Household with PII populated
            difficulty: "easy", "medium", or "hard"
            error_count: Target number of errors to inject

        Returns:
            Tuple of (modified household, list of injected errors for answer key)
        """
        # TODO: Implement
        pass
