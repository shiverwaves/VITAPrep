"""Slot: address_mismatch — fires when an ID address differs from household address.

Covers the common VITA scenario where a client's driver's license or
state ID shows a previous address. The volunteer must notice the
discrepancy and confirm which address is current.
"""

from typing import Any, List

from intake.analyzer.types import InterviewNote, NarrativeTemplate, Slot


class AddressMismatchSlot(Slot):
    """Fires for each person whose ID address differs from household address."""
    name = "address_mismatch"

    def fires_for(self, scenario: Any) -> list:
        hh = scenario.household
        if hh is None or hh.address is None:
            return []
        hh_addr = hh.address
        result = []
        for person in hh.members:
            if person.id_address is None:
                continue
            if person.id_address.one_line() != hh_addr.one_line():
                result.append(person)
        return result

    def templates(self) -> List[NarrativeTemplate]:
        return [
            RecentMoveTemplate(),
            SameAreaNewStreetTemplate(),
            GenericAddressUpdateTemplate(),
        ]


class RecentMoveTemplate(NarrativeTemplate):
    """Person moved from a different city or state — ID not yet updated."""

    def requirements(self, scenario: Any, person: Any) -> bool:
        hh_addr = scenario.household.address
        id_addr = person.id_address
        return (
            id_addr.city != hh_addr.city
            or id_addr.state != hh_addr.state
        )

    def render(
        self, scenario: Any, person: Any, subtlety: str,
    ) -> InterviewNote:
        name = person.legal_first_name
        old_city = person.id_address.city
        new_city = scenario.household.address.city

        if subtlety == "obvious":
            question = f"Your ID shows {old_city} — is that still your address?"
            answer = (
                f"No, I moved to {new_city} last year. "
                f"I haven't updated my ID yet."
            )
        elif subtlety == "moderate":
            question = "Has your address changed recently?"
            answer = (
                f"Yeah, we moved from {old_city}. "
                f"Still need to go to the DMV."
            )
        else:
            question = "Is everything on your ID current?"
            answer = "The address is old — we're somewhere else now."

        return InterviewNote(
            category="address",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )


class SameAreaNewStreetTemplate(NarrativeTemplate):
    """Same city/state but different street — local move."""

    def requirements(self, scenario: Any, person: Any) -> bool:
        hh_addr = scenario.household.address
        id_addr = person.id_address
        return (
            id_addr.city == hh_addr.city
            and id_addr.state == hh_addr.state
            and id_addr.street != hh_addr.street
        )

    def render(
        self, scenario: Any, person: Any, subtlety: str,
    ) -> InterviewNote:
        name = person.legal_first_name
        new_street = scenario.household.address.street

        if subtlety == "obvious":
            question = (
                f"Your ID shows a different street address. "
                f"Do you live at {new_street} now?"
            )
            answer = (
                f"Yes, we moved to {new_street} earlier this year. "
                f"Same city though."
            )
        elif subtlety == "moderate":
            question = "Did you move this past year?"
            answer = "Just across town. New place, same area."
        else:
            question = "Is your ID up to date?"
            answer = "Mostly — the address is a little off."

        return InterviewNote(
            category="address",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )


class GenericAddressUpdateTemplate(NarrativeTemplate):
    """Fallback — addresses differ but no specific pattern matched."""

    def requirements(self, scenario: Any, person: Any) -> bool:
        return True

    def render(
        self, scenario: Any, person: Any, subtlety: str,
    ) -> InterviewNote:
        if subtlety == "obvious":
            question = "The address on your ID doesn't match what you gave us."
            answer = "Right, I need to update that. Use my current address."
        elif subtlety == "moderate":
            question = "Can you confirm your current mailing address?"
            answer = "It's different from what's on my license."
        else:
            question = "Anything on your documents that might be outdated?"
            answer = "Hmm, maybe the address."

        return InterviewNote(
            category="address",
            question=question,
            answer=answer,
            source_slot=self.__class__.__name__,
        )
