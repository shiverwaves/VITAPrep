"""Boilerplate renderer — produces factual InterviewNote objects from household fields.

Renders the structured, non-narrative facts that the student needs to
complete the intake form: citizenship, contact info, employment, filing
status, claimed-as-dependent, and dependent details (months in home,
student status, disability, citizenship).

These notes have ``source_slot=None`` because they are direct field reads,
not narrative explanations from the analyzer.  They are merged with
slot-rendered notes in the exercise engine to form the complete
``scenario.interview_notes`` list.

Difficulty filtering (matching the old client_profile.py behavior):
  easy   → all facts
  medium → required facts only (drops optional contact info)
  hard   → citizenship + filing only (student must ask for everything else)
"""

import logging
from typing import List, Optional

from generator.models import FilingStatus, Household, Person
from intake.analyzer.types import InterviewNote
from training.form_fields import MAX_DEPENDENTS

logger = logging.getLogger(__name__)

_FILING_STATUS_LABELS = {
    FilingStatus.SINGLE: "Single",
    FilingStatus.MARRIED_FILING_JOINTLY: "Married Filing Jointly",
    FilingStatus.MARRIED_FILING_SEPARATELY: "Married Filing Separately",
    FilingStatus.HEAD_OF_HOUSEHOLD: "Head of Household",
    FilingStatus.QUALIFYING_SURVIVING_SPOUSE: "Qualifying Surviving Spouse",
}


def generate_boilerplate(
    household: Household,
    difficulty: str,
) -> List[InterviewNote]:
    """Generate boilerplate interview notes filtered by difficulty.

    Args:
        household: Household with PII fully populated.
        difficulty: One of "easy", "medium", "hard".

    Returns:
        List of InterviewNote objects for factual household data.
    """
    householder = household.get_householder()
    if not householder:
        logger.warning("No householder found — returning empty boilerplate")
        return []

    spouse = household.get_spouse()
    notes: List[InterviewNote] = []

    notes.append(_citizenship_note(householder, is_primary=True))
    if spouse:
        notes.append(_citizenship_note(spouse, is_primary=False))

    notes.append(_filing_status_note(household))
    notes.append(_claimed_as_dependent_note(householder))

    if difficulty != "hard":
        notes.extend(_employment_notes(householder, spouse))

        dependents = sorted(
            household.get_dependents(),
            key=lambda p: p.age,
            reverse=True,
        )
        notes.extend(_dependent_notes(dependents))

    if difficulty == "easy":
        notes.extend(_contact_notes(householder))

    logger.info(
        "Generated %d boilerplate notes at difficulty=%s for household %s",
        len(notes), difficulty, household.household_id,
    )
    return notes


def _citizenship_note(person: Person, is_primary: bool) -> InterviewNote:
    who = "you" if is_primary else "your spouse"
    return InterviewNote(
        category="citizenship",
        question=f"Are {who} a U.S. citizen?",
        answer="Yes",
    )


def _filing_status_note(household: Household) -> InterviewNote:
    status = household.derive_filing_status()
    label = _FILING_STATUS_LABELS.get(status, status.value)
    return InterviewNote(
        category="filing",
        question="What is your filing status for this tax year?",
        answer=label,
    )


def _claimed_as_dependent_note(person: Person) -> InterviewNote:
    return InterviewNote(
        category="filing",
        question="Can anyone claim you as a dependent on their tax return?",
        answer="Yes" if person.can_be_claimed else "No",
    )


def _contact_notes(person: Person) -> List[InterviewNote]:
    notes: List[InterviewNote] = []
    if person.phone:
        notes.append(InterviewNote(
            category="contact",
            question="What is your daytime phone number?",
            answer=person.phone,
        ))
    if person.email:
        notes.append(InterviewNote(
            category="contact",
            question="What is your email address?",
            answer=person.email,
        ))
    return notes


def _employment_notes(
    householder: Person,
    spouse: Optional[Person],
) -> List[InterviewNote]:
    notes: List[InterviewNote] = []
    if householder.occupation_title:
        notes.append(InterviewNote(
            category="employment",
            question="What is your job title or occupation?",
            answer=householder.occupation_title,
        ))
    if spouse and spouse.occupation_title:
        notes.append(InterviewNote(
            category="employment",
            question="What is your spouse's job title or occupation?",
            answer=spouse.occupation_title,
        ))
    return notes


def _dependent_notes(dependents: List[Person]) -> List[InterviewNote]:
    notes: List[InterviewNote] = []
    for dep in dependents[:MAX_DEPENDENTS]:
        name = f"{dep.legal_first_name} {dep.legal_last_name}".strip()
        if not name:
            name = "your dependent"

        notes.append(InterviewNote(
            category="dependent",
            question=f"How many months did {name} live in your home this year?",
            answer=str(dep.months_in_home),
        ))

        if dep.is_full_time_student:
            notes.append(InterviewNote(
                category="dependent",
                question=f"Is {name} a full-time student?",
                answer="Yes",
            ))

        if dep.has_disability:
            notes.append(InterviewNote(
                category="dependent",
                question=f"Does {name} have a permanent disability?",
                answer="Yes",
            ))

        notes.append(InterviewNote(
            category="dependent",
            question=f"Is {name} a U.S. citizen?",
            answer="Yes",
        ))

    return notes
