"""Slot: dependent_residency — fires when a child lived in the home < 12 months.

Covers the VITA scenario where a dependent's residency is partial-year.
The volunteer must determine months in home to evaluate qualifying child
status (IRC §152(c)(1)(B) — must live with taxpayer for more than half
the year).

Three templates cover distinct situations:
- Shared custody (has_other_parent flag set by generator)
- Mid-year arrival (entered_household_during_year flag)
- Fallback for any partial-year residence without richer flags

NOTE: has_other_parent and entered_household_during_year are not yet
populated by the generator. Until the generator sets them, only the
fallback template fires. When the generator learns to populate these
fields, the specific templates will start firing automatically.
"""

from typing import Any, List

from intake.analyzer.types import InterviewNote, NarrativeTemplate, Slot


class DependentResidencySlot(Slot):
    """Fires for each dependent with 0 < months_in_home < 12."""
    name = "dependent_residency"

    def fires_for(self, scenario: Any) -> list:
        hh = scenario.household
        if hh is None:
            return []
        return [
            p for p in hh.get_dependents()
            if 0 < p.months_in_home < 12
        ]

    def templates(self) -> List[NarrativeTemplate]:
        return [
            SharedCustodyTemplate(),
            JoinedMidYearTemplate(),
            PartialYearFallbackTemplate(),
        ]


class SharedCustodyTemplate(NarrativeTemplate):
    """Child splits time between two parents — shared custody."""

    def requirements(self, scenario: Any, child: Any) -> bool:
        return (
            child.has_other_parent
            and 4 <= child.months_in_home <= 8
        )

    def render(
        self, scenario: Any, child: Any, subtlety: str,
    ) -> InterviewNote:
        name = child.legal_first_name
        months = child.months_in_home

        if subtlety == "obvious":
            question = (
                f"How many months did {name} live with you "
                f"in {scenario.household.year}?"
            )
            answer = (
                f"About {months} months — "
                f"{'she' if child.sex == 'F' else 'he'}'s "
                f"with {'her' if child.sex == 'F' else 'his'} "
                f"other parent the rest of the year."
            )
        elif subtlety == "moderate":
            question = f"Tell me about your living situation with {name}."
            answer = (
                f"We share custody. "
                f"{'She' if child.sex == 'F' else 'He'}'s with me "
                f"during the school year mostly."
            )
        else:
            question = f"Did {name} live with you all year?"
            answer = (
                f"On and off. "
                f"{'Her' if child.sex == 'F' else 'His'} "
                f"other parent and I trade off."
            )

        return InterviewNote(
            category="dependent",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )


class JoinedMidYearTemplate(NarrativeTemplate):
    """Child moved into the household partway through the year."""

    def requirements(self, scenario: Any, child: Any) -> bool:
        return (
            child.entered_household_during_year
            and child.months_in_home >= 6
        )

    def render(
        self, scenario: Any, child: Any, subtlety: str,
    ) -> InterviewNote:
        name = child.legal_first_name
        months = child.months_in_home

        if subtlety == "obvious":
            question = f"When did {name} start living with you?"
            answer = (
                f"{'She' if child.sex == 'F' else 'He'} moved in "
                f"partway through the year — about {months} months ago."
            )
        elif subtlety == "moderate":
            question = f"Has {name} been with you the whole year?"
            answer = (
                f"Not the whole year — "
                f"{'she' if child.sex == 'F' else 'he'} "
                f"came to live with us partway through."
            )
        else:
            question = f"Tell me about {name}'s living situation."
            answer = "It changed during the year."

        return InterviewNote(
            category="dependent",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )


class PartialYearFallbackTemplate(NarrativeTemplate):
    """Fallback — child lived in home < 12 months for unspecified reason.

    Always matches. Provides narrative cover until the generator
    populates the richer has_other_parent / entered_household_during_year
    flags that enable the specific templates above.
    """

    def requirements(self, scenario: Any, child: Any) -> bool:
        return True

    def render(
        self, scenario: Any, child: Any, subtlety: str,
    ) -> InterviewNote:
        name = child.legal_first_name
        months = child.months_in_home

        if subtlety == "obvious":
            question = (
                f"How many months did {name} live with you this year?"
            )
            answer = f"About {months} months."
        elif subtlety == "moderate":
            question = f"Did {name} live with you the whole year?"
            answer = f"Not the whole year — most of it though."
        else:
            question = f"Was {name} with you all year?"
            answer = "Not exactly."

        return InterviewNote(
            category="dependent",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )
