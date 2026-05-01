"""Scenario analyzer — evaluates slots and selects narrative templates.

The analyzer is the gatekeeper for narrative coherence. It walks the
slot catalog, finds triggering instances, and picks templates whose
requirements match. If any fired instance has zero matching templates,
the scenario is unrescuable and triggers a reroll.

Pipeline position: generate → **analyze** → ground truth → serve.
Running before ground truth means unrescuable scenarios never pay
the cost of compute_ground_truth.
"""

import logging
from typing import Any, Dict, List

from .types import FiredTemplate, Slot, Unrescuable

logger = logging.getLogger(__name__)

MAX_REROLL_ATTEMPTS = 10


class ScenarioAnalyzer:
    """Evaluates slots against a scenario and populates narrative_slots."""

    def __init__(self) -> None:
        self._slots: List[Slot] = []

    def register(self, slot: Slot) -> None:
        """Add a slot to the catalog.

        Args:
            slot: A Slot instance to evaluate during analysis.
        """
        self._slots.append(slot)
        logger.debug("Registered slot: %s", slot.name)

    @property
    def slots(self) -> List[Slot]:
        """Return the registered slot catalog."""
        return list(self._slots)

    def analyze(self, scenario: Any) -> Dict[str, List[FiredTemplate]]:
        """Run all registered slots against the scenario.

        For each slot that fires, evaluates templates in order and picks
        the first whose requirements() returns True. If a fired instance
        has zero matching templates, raises Unrescuable.

        Args:
            scenario: Scenario with household populated. Lifecycle fields
                (ground_truth, concept_tags, interview_notes) are None.

        Returns:
            Dict mapping slot_name to list of FiredTemplate. Empty dict
            if no slots fire (valid — not every scenario needs narrative
            cover for every slot).

        Raises:
            Unrescuable: If a fired slot instance has zero matching
                templates.
        """
        narrative_slots: Dict[str, List[FiredTemplate]] = {}

        for slot in self._slots:
            instances = slot.fires_for(scenario)
            if not instances:
                continue

            fired: List[FiredTemplate] = []
            templates = slot.templates()

            for instance in instances:
                matched = None
                for template in templates:
                    if template.requirements(scenario, instance):
                        matched = template
                        break

                if matched is None:
                    raise Unrescuable(
                        f"Slot '{slot.name}' fired for instance "
                        f"{instance!r} but no template matched."
                    )

                fired.append(FiredTemplate(
                    slot_name=slot.name,
                    instance=instance,
                    template=matched,
                ))

            narrative_slots[slot.name] = fired
            logger.debug(
                "Slot '%s' fired %d instance(s)", slot.name, len(fired),
            )

        logger.info(
            "Analysis complete: %d slot(s) fired",
            len(narrative_slots),
        )
        return narrative_slots
