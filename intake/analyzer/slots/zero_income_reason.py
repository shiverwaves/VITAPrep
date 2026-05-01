"""Slot: zero_income_reason — fires when a filer has zero total income.

Covers the VITA scenario where a taxpayer reports no income. The
volunteer needs to understand why (student, stay-at-home parent,
between jobs) to correctly complete the return.

Only fires for filers (householder and spouse), not dependents —
a child with zero income is expected and needs no narrative cover.
"""

from typing import Any, List

from intake.analyzer.types import InterviewNote, NarrativeTemplate, Slot


class ZeroIncomeReasonSlot(Slot):
    """Fires for each filer (householder/spouse) with zero total income."""
    name = "zero_income_reason"

    def fires_for(self, scenario: Any) -> list:
        hh = scenario.household
        if hh is None:
            return []
        filers = []
        householder = hh.get_householder()
        if householder:
            filers.append(householder)
        spouse = hh.get_spouse()
        if spouse:
            filers.append(spouse)
        return [p for p in filers if p.total_income() == 0]

    def templates(self) -> List[NarrativeTemplate]:
        return [
            StayAtHomeParentTemplate(),
            FullTimeStudentTemplate(),
            BetweenJobsTemplate(),
        ]


class StayAtHomeParentTemplate(NarrativeTemplate):
    """Married household where one spouse stays home with children."""

    def requirements(self, scenario: Any, person: Any) -> bool:
        hh = scenario.household
        return (
            hh.is_married()
            and len(hh.get_dependents()) > 0
        )

    def render(
        self, scenario: Any, person: Any, subtlety: str,
    ) -> InterviewNote:
        name = person.legal_first_name
        kid_count = len(scenario.household.get_dependents())

        if subtlety == "obvious":
            question = f"Did {name} have any income this year?"
            answer = (
                f"No, I stayed home with the "
                f"{'kids' if kid_count > 1 else 'kid'} this year."
            )
        elif subtlety == "moderate":
            question = f"What does {name} do for work?"
            answer = (
                f"I'm home with the little "
                f"{'ones' if kid_count > 1 else 'one'} right now."
            )
        else:
            question = "Tell me about your household's work situation."
            answer = "Only one of us is working at the moment."

        return InterviewNote(
            category="income",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )


class FullTimeStudentTemplate(NarrativeTemplate):
    """Person is a full-time student with no income."""

    def requirements(self, scenario: Any, person: Any) -> bool:
        return person.is_full_time_student

    def render(
        self, scenario: Any, person: Any, subtlety: str,
    ) -> InterviewNote:
        name = person.legal_first_name

        if subtlety == "obvious":
            question = f"Did {name} earn any income this year?"
            answer = "No, I'm a full-time student. I didn't work."
        elif subtlety == "moderate":
            question = f"What's {name}'s current situation?"
            answer = "I'm in school full-time. Focused on that."
        else:
            question = "Any income sources we should know about?"
            answer = "Not really — I've been busy with classes."

        return InterviewNote(
            category="income",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )


class BetweenJobsTemplate(NarrativeTemplate):
    """Fallback — person has no income for unspecified reasons."""

    def requirements(self, scenario: Any, person: Any) -> bool:
        return True

    def render(
        self, scenario: Any, person: Any, subtlety: str,
    ) -> InterviewNote:
        name = person.legal_first_name

        if subtlety == "obvious":
            question = f"Did {name} have any income this year?"
            answer = "No, I was between jobs all year."
        elif subtlety == "moderate":
            question = f"What was {name}'s employment situation?"
            answer = "I wasn't working this past year."
        else:
            question = "Walk me through your year income-wise."
            answer = "It was a quiet year."

        return InterviewNote(
            category="income",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )
