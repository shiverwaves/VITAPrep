"""
Exercise engine — orchestrates full scenario creation.

Pipeline: generate household → overlay PII → inject errors → package

Documents are rendered on-demand by the API layer (HTML served directly
to the browser), not pre-generated at scenario creation time.

Modes:
- "intake": Student gets source docs, fills blank 13614-C Part I
- "verify": Student gets pre-filled 13614-C + source docs, finds discrepancies
- "crosscheck": Student verifies 1040 against source docs (future)
"""

import logging
import uuid
from datetime import datetime
from typing import Optional

from generator.models import Scenario
from generator.pipeline import HouseholdGenerator
from .client_profile import filter_by_difficulty, generate_client_profile
from .error_injector import ErrorInjector

logger = logging.getLogger(__name__)


class ExerciseEngine:
    """Orchestrates generation of complete training scenarios."""

    def __init__(self, state: str = "HI", year: int = 2022) -> None:
        self.generator = HouseholdGenerator(state, year)
        self.error_injector = ErrorInjector()

    def generate_scenario(
        self,
        mode: str = "intake",
        difficulty: str = "easy",
        error_count: int = 3,
        pattern: Optional[str] = None,
        seed: Optional[int] = None,
    ) -> Scenario:
        """Generate a complete training scenario.

        Args:
            mode: "intake" (fill blank form), "verify" (find errors),
                or "crosscheck" (future).
            difficulty: "easy", "medium", or "hard".
            error_count: Number of errors to inject (verify mode).
                Ignored for intake mode.
            pattern: Specific household pattern or None for random.
            seed: Random seed for reproducibility.

        Returns:
            Scenario with household, errors, and client facts
            packaged together.
        """
        scenario_id = f"sc-{uuid.uuid4().hex[:12]}"

        # Stage 1: Generate household with demographics + PII
        household = self.generator.generate_with_pii(
            pattern=pattern, seed=seed,
        )

        # Stage 2: Inject errors (verify mode only)
        injected_errors = []
        if mode == "verify":
            household, injected_errors = self.error_injector.inject(
                household,
                difficulty=difficulty,
                error_count=error_count,
            )

        # Stage 3: Generate client profile (verbal facts)
        all_facts = generate_client_profile(household)
        client_facts = filter_by_difficulty(all_facts, difficulty)

        # Package
        scenario = Scenario(
            scenario_id=scenario_id,
            mode=mode,
            difficulty=difficulty,
            household=household,
            injected_errors=injected_errors,
            client_facts=client_facts,
            document_paths={},
            created_at=datetime.utcnow().isoformat(),
        )

        logger.info(
            "Generated scenario %s: mode=%s, difficulty=%s, "
            "members=%d, errors=%d, facts=%d",
            scenario_id, mode, difficulty,
            len(household.members),
            len(injected_errors),
            len(client_facts),
        )
        return scenario
