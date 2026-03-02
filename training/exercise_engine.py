"""
Exercise engine — orchestrates full scenario creation.

Pipeline: generate household → overlay PII → render documents → inject errors → package

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
from .document_renderer import DocumentRenderer
from .error_injector import ErrorInjector

logger = logging.getLogger(__name__)


class ExerciseEngine:
    """Orchestrates generation of complete training scenarios."""

    def __init__(self, state: str = "HI", year: int = 2022) -> None:
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
            Scenario with household, documents, errors, and client
            facts packaged together.
        """
        scenario_id = f"sc-{uuid.uuid4().hex[:12]}"

        # Stage 1: Generate household with demographics + PII
        household = self.generator.generate_with_pii(
            pattern=pattern, seed=seed,
        )

        # Stage 2: Render identity documents (SSN cards, DLs)
        raw_paths = self.renderer.render_household_documents(household)
        # Convert Path objects to strings for JSON serialisation
        document_paths = {k: str(v) for k, v in raw_paths.items()}

        # Stage 3: Inject errors (verify mode only)
        injected_errors = []
        if mode == "verify":
            household, injected_errors = self.error_injector.inject(
                household,
                difficulty=difficulty,
                error_count=error_count,
            )

        # Stage 4: Generate client profile (verbal facts)
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
            document_paths=document_paths,
            created_at=datetime.utcnow().isoformat(),
        )

        logger.info(
            "Generated scenario %s: mode=%s, difficulty=%s, "
            "members=%d, errors=%d, facts=%d, docs=%d",
            scenario_id, mode, difficulty,
            len(household.members),
            len(injected_errors),
            len(client_facts),
            len(document_paths),
        )
        return scenario
