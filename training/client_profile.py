"""
Client profile generator — produces verbal facts for VITA intake exercises.

In a real VITA intake, the volunteer has identity documents (SSN card, DL)
plus information the client states verbally. This module extracts the
verbal-only facts from a Household so the exercise engine can present
them alongside the rendered documents.

Facts are categorized by what they relate to:
- ``citizenship``: U.S. citizen yes/no
- ``contact``: phone number, email address
- ``employment``: job title / occupation
- ``filing``: filing status confirmation, claimed-as-dependent
- ``dependent``: months in home, student status, disability

Difficulty scaling (applied by the exercise engine, not here):
- Easy: all facts shown upfront in a summary card
- Medium: some facts omitted — student must notice gaps
- Hard: minimal facts — student must actively identify what to ask
"""

import logging
from typing import List, Optional

from generator.models import (
    ClientFact,
    FilingStatus,
    Household,
    Person,
    RelationshipType,
)
from training.form_fields import (
    CLAIMED_AS_DEPENDENT,
    FILING_STATUS,
    NOT_CLAIMED_AS_DEPENDENT,
    YOU_EMAIL,
    YOU_JOB_TITLE,
    YOU_NOT_US_CITIZEN,
    YOU_PHONE,
    YOU_US_CITIZEN,
    SPOUSE_JOB_TITLE,
    dep_field,
    DEP_MONTHS,
    DEP_STUDENT,
    DEP_DISABLED,
    DEP_US_CITIZEN,
    MAX_DEPENDENTS,
)

logger = logging.getLogger(__name__)

# Filing status enum → human-readable label
_FILING_STATUS_LABELS = {
    FilingStatus.SINGLE: "Single",
    FilingStatus.MARRIED_FILING_JOINTLY: "Married Filing Jointly",
    FilingStatus.MARRIED_FILING_SEPARATELY: "Married Filing Separately",
    FilingStatus.HEAD_OF_HOUSEHOLD: "Head of Household",
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: "Qualifying Surviving Spouse",
}


def _citizenship_fact(person: Person, is_primary: bool) -> ClientFact:
    """Generate the citizenship question/answer for a person."""
    who = "you" if is_primary else "your spouse"
    return ClientFact(
        category="citizenship",
        question=f"Are {who} a U.S. citizen?",
        answer="Yes",  # Default for most VITA scenarios
        form_field=YOU_US_CITIZEN if is_primary else "",
        person_id=person.person_id,
        required=True,
    )


def _contact_facts(person: Person) -> List[ClientFact]:
    """Generate phone and email facts for the householder."""
    facts: List[ClientFact] = []
    if person.phone:
        facts.append(ClientFact(
            category="contact",
            question="What is your daytime phone number?",
            answer=person.phone,
            form_field=YOU_PHONE,
            person_id=person.person_id,
            required=False,
        ))
    if person.email:
        facts.append(ClientFact(
            category="contact",
            question="What is your email address?",
            answer=person.email,
            form_field=YOU_EMAIL,
            person_id=person.person_id,
            required=False,
        ))
    return facts


def _employment_fact(
    person: Person, is_primary: bool,
) -> Optional[ClientFact]:
    """Generate job title fact if the person has an occupation."""
    title = person.occupation_title or ""
    if not title:
        return None
    who = "your" if is_primary else "your spouse's"
    return ClientFact(
        category="employment",
        question=f"What is {who} job title or occupation?",
        answer=title,
        form_field=YOU_JOB_TITLE if is_primary else SPOUSE_JOB_TITLE,
        person_id=person.person_id,
        required=True,
    )


def _filing_status_fact(household: Household) -> ClientFact:
    """Generate the filing status confirmation fact."""
    status = household.derive_filing_status()
    label = _FILING_STATUS_LABELS.get(status, status.value)
    return ClientFact(
        category="filing",
        question="What is your filing status for this tax year?",
        answer=label,
        form_field=FILING_STATUS,
        person_id=household.get_householder().person_id if household.get_householder() else "",
        required=True,
    )


def _claimed_as_dependent_fact(person: Person) -> ClientFact:
    """Generate the 'can anyone claim you as a dependent' fact."""
    claimed = person.can_be_claimed
    return ClientFact(
        category="filing",
        question="Can anyone claim you as a dependent on their tax return?",
        answer="Yes" if claimed else "No",
        form_field=CLAIMED_AS_DEPENDENT if claimed else NOT_CLAIMED_AS_DEPENDENT,
        person_id=person.person_id,
        required=True,
    )


def _dependent_facts(
    dependents: List[Person],
) -> List[ClientFact]:
    """Generate verbal facts for each dependent (up to 4)."""
    facts: List[ClientFact] = []
    for i, dep in enumerate(dependents[:MAX_DEPENDENTS]):
        name = f"{dep.legal_first_name} {dep.legal_last_name}".strip()
        if not name:
            name = f"dependent {i + 1}"

        facts.append(ClientFact(
            category="dependent",
            question=f"How many months did {name} live in your home this year?",
            answer=str(dep.months_in_home),
            form_field=dep_field(i, DEP_MONTHS),
            person_id=dep.person_id,
            required=True,
        ))

        if dep.is_full_time_student:
            facts.append(ClientFact(
                category="dependent",
                question=f"Is {name} a full-time student?",
                answer="Yes",
                form_field=dep_field(i, DEP_STUDENT),
                person_id=dep.person_id,
                required=True,
            ))

        if dep.has_disability:
            facts.append(ClientFact(
                category="dependent",
                question=f"Does {name} have a permanent disability?",
                answer="Yes",
                form_field=dep_field(i, DEP_DISABLED),
                person_id=dep.person_id,
                required=True,
            ))

        # US citizen for dependents — verbal fact
        facts.append(ClientFact(
            category="dependent",
            question=f"Is {name} a U.S. citizen?",
            answer="Yes",
            form_field=dep_field(i, DEP_US_CITIZEN),
            person_id=dep.person_id,
            required=True,
        ))

    return facts


def generate_client_profile(household: Household) -> List[ClientFact]:
    """Generate all verbal facts for a household.

    These are facts the student must obtain from the "client" because
    they do not appear on any identity document.

    Args:
        household: Household with PII fully populated.

    Returns:
        List of ClientFact objects ordered by form section.
    """
    facts: List[ClientFact] = []
    householder = household.get_householder()
    spouse = household.get_spouse()

    if not householder:
        logger.warning("No householder found — returning empty profile")
        return facts

    # Section A: citizenship, contact, employment
    facts.append(_citizenship_fact(householder, is_primary=True))
    facts.extend(_contact_facts(householder))
    job = _employment_fact(householder, is_primary=True)
    if job:
        facts.append(job)

    # Section C: spouse employment and citizenship
    if spouse:
        facts.append(_citizenship_fact(spouse, is_primary=False))
        spouse_job = _employment_fact(spouse, is_primary=False)
        if spouse_job:
            facts.append(spouse_job)

    # Section D: filing status
    facts.append(_filing_status_fact(household))

    # Section E: dependent verbal facts
    dependents = [
        p for p in household.members
        if p.is_dependent or p.can_be_claimed
    ]
    dependents.sort(key=lambda p: p.age, reverse=True)
    facts.extend(_dependent_facts(dependents))

    # Section F: claimed as dependent
    facts.append(_claimed_as_dependent_fact(householder))

    logger.info(
        "Generated %d client facts for household %s",
        len(facts), household.household_id,
    )
    return facts


def filter_by_difficulty(
    facts: List[ClientFact], difficulty: str,
) -> List[ClientFact]:
    """Filter facts by difficulty level.

    Args:
        facts: Full list of client facts.
        difficulty: One of "easy", "medium", "hard".

    Returns:
        Filtered list. Easy = all facts. Medium = required only.
        Hard = minimal (citizenship + filing status only).
    """
    if difficulty == "easy":
        return list(facts)

    if difficulty == "medium":
        return [f for f in facts if f.required]

    if difficulty == "hard":
        # Only the facts the student absolutely must ask about —
        # citizenship and filing status. Everything else they need
        # to figure out is missing and ask for it.
        return [
            f for f in facts
            if f.category in ("citizenship", "filing")
        ]

    logger.warning("Unknown difficulty %r, returning all facts", difficulty)
    return list(facts)
