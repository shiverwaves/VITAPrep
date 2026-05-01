"""Type system for the scenario analyzer.

Four types form the analyzer contract:

- Slot: detects situations needing narrative cover.
- NarrativeTemplate: a possible explanation for a fired slot instance.
- InterviewNote: a single player-visible interview note.
- FiredTemplate: binds a slot instance to its chosen template.

Plus one exception:

- Unrescuable: raised when a fired slot has zero matching templates,
  signaling the orchestrator to reroll.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any, List


class Unrescuable(Exception):
    """A scenario cannot be given coherent narrative cover.

    Raised by the analyzer when a fired slot instance has zero matching
    templates. The orchestrator catches this and retries with a new seed.
    """


@dataclass
class InterviewNote:
    """A single interview note shown to the player.

    Args:
        category: Topic bucket ("filing", "dependent", "income", etc.).
        question: What the volunteer would ask.
        answer: What the client said.
        source_slot: Debug field tracing to the slot that produced this
            note. None for boilerplate notes not produced by a slot.
    """
    category: str
    question: str
    answer: str
    source_slot: str | None = None


class NarrativeTemplate(ABC):
    """A possible narrative explanation for a fired slot instance.

    Each template has a predicate (requirements) that checks whether
    the template plausibly applies, and a renderer that produces the
    interview note at a given subtlety level.
    """

    @abstractmethod
    def requirements(self, scenario: Any, instance: Any) -> bool:
        """Whether this template can plausibly apply to this instance.

        Args:
            scenario: The Scenario object.
            instance: The triggering object (person, document, etc.).

        Returns:
            True if the template's narrative fits this instance.
        """

    @abstractmethod
    def render(
        self, scenario: Any, instance: Any, subtlety: str,
    ) -> InterviewNote:
        """Produce the InterviewNote for the player.

        Args:
            scenario: The Scenario object.
            instance: The triggering object.
            subtlety: One of "obvious", "moderate", "subtle".

        Returns:
            An InterviewNote with category, question, and answer.
        """


class Slot(ABC):
    """Detects situations in a generated scenario that need narrative cover.

    Slots run at Stage 3 (analysis). They have access to
    scenario.household and scenario.document_paths only.

    Slots MUST NOT read ground_truth, concept_tags, or interview_notes.
    Those fields do not exist yet at Stage 3 and are None. This
    constraint is enforced by ordering, documented here, and verified
    by test.
    """
    name: str = ""

    @abstractmethod
    def fires_for(self, scenario: Any) -> list:
        """Return triggering instances or [] if the slot does not fire.

        Args:
            scenario: The Scenario object (household populated,
                lifecycle fields are None).

        Returns:
            List of triggering objects (people, documents, etc.).
            Empty list means the slot does not fire for this scenario.
        """

    @abstractmethod
    def templates(self) -> List[NarrativeTemplate]:
        """Return candidate templates, evaluated at analysis time.

        Returns:
            List of NarrativeTemplate instances.
        """


@dataclass
class FiredTemplate:
    """Binds a slot instance to its chosen template.

    Stored in scenario.narrative_slots as
    dict[slot_name, list[FiredTemplate]].

    Args:
        slot_name: Name of the slot that fired.
        instance: The triggering object (person, document, etc.).
        template: The selected NarrativeTemplate.
    """
    slot_name: str
    instance: Any
    template: NarrativeTemplate
