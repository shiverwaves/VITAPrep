"""Obfuscation renderer — converts fired templates into interview notes.

Maps scenario difficulty to a subtlety level, then calls each fired
template's render() method to produce InterviewNote objects. The result
is stored on scenario.interview_notes alongside (not replacing) the
existing client_facts path.

Subtlety mapping (MVP — single global level per scenario):
  easy   → obvious   (states facts directly)
  medium → moderate  (requires inference)
  hard   → subtle    (requires significant inference)

The obfuscation layer preserves truth — it can introduce ambiguity
but never contradictions. A competent reader must be able to reconstruct
ground truth from interview notes plus documents.
"""

import logging
from typing import Any, Dict, List

from .analyzer.types import FiredTemplate, InterviewNote

logger = logging.getLogger(__name__)

DIFFICULTY_TO_SUBTLETY = {
    "easy": "obvious",
    "medium": "moderate",
    "hard": "subtle",
}


def obfuscate(
    narrative_slots: Dict[str, List[FiredTemplate]],
    scenario: Any,
    difficulty: str,
) -> List[InterviewNote]:
    """Render fired templates into interview notes at the appropriate subtlety.

    Args:
        narrative_slots: Raw output from ScenarioAnalyzer.analyze().
            Maps slot_name to list of FiredTemplate objects.
        scenario: The Scenario object (passed to template render methods).
        difficulty: Scenario difficulty ("easy", "medium", "hard").

    Returns:
        List of InterviewNote objects, ordered by slot then instance.
    """
    subtlety = DIFFICULTY_TO_SUBTLETY.get(difficulty, "obvious")
    notes: List[InterviewNote] = []

    for slot_name, fired_list in narrative_slots.items():
        for ft in fired_list:
            note = ft.template.render(scenario, ft.instance, subtlety)
            notes.append(note)

    logger.info(
        "Obfuscated %d notes at subtlety=%s from %d slot(s)",
        len(notes), subtlety, len(narrative_slots),
    )
    return notes
