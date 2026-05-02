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

    # Page 2-3 boilerplate: income and expenses (not gated by difficulty)
    notes.extend(_wage_and_se_notes(household))
    notes.extend(_passive_income_notes(household))

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


# =========================================================================
# Page 2 — Income (Subset 1: Wage and self-employment)
# =========================================================================


def _wage_and_se_notes(household: Household) -> List[InterviewNote]:
    notes: List[InterviewNote] = []

    # Wages (W-2)
    wage_members = [m for m in household.members if m.wage_income > 0
                    and m.disability_income_source != "w2"]
    if wage_members:
        w2_count = sum(len(m.w2s) for m in wage_members)
        notes.append(InterviewNote(
            category="income",
            question="Did you receive wages as a part-time or full-time employee?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="income",
            question="How many jobs?",
            answer=str(w2_count),
        ))
    else:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive wages as a part-time or full-time employee?",
            answer="No",
        ))

    # Self-employment (1099-NEC)
    se_members = [m for m in household.members if m.self_employment_income > 0]
    if se_members:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive self-employment payments?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="income",
            question="What kind of work?",
            answer=se_members[0].occupation_title or "Self-employed",
        ))
    else:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive self-employment payments?",
            answer="No",
        ))

    # Disability benefits (W-2 or 1099-R)
    disability_members = [m for m in household.members
                          if m.disability_income_source is not None]
    if disability_members:
        source = disability_members[0].disability_income_source
        notes.append(InterviewNote(
            category="income",
            question="Did you receive disability benefits?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="income",
            question="Disability income reported on which form?",
            answer="W-2" if source == "w2" else "1099-R",
        ))
    else:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive disability benefits?",
            answer="No",
        ))

    return notes


# =========================================================================
# Page 2 — Income (Subset 2: Passive income)
# =========================================================================


def _passive_income_notes(household: Household) -> List[InterviewNote]:
    notes: List[InterviewNote] = []

    # Retirement income (1099-R)
    ret_members = [m for m in household.members if m.retirement_income > 0]
    if ret_members:
        total = sum(m.retirement_income for m in ret_members)
        notes.append(InterviewNote(
            category="income",
            question="Did you receive income from a retirement account, pension, or annuity?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="income",
            question="How much retirement income, roughly?",
            answer=f"${total:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive income from a retirement account, pension, or annuity?",
            answer="No",
        ))

    # Social Security (SSA-1099)
    ss_members = [m for m in household.members if m.social_security_income > 0]
    if ss_members:
        total = sum(m.social_security_income for m in ss_members)
        notes.append(InterviewNote(
            category="income",
            question="Did you receive Social Security or Railroad Retirement benefits?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="income",
            question="How much in Social Security benefits, roughly?",
            answer=f"${total:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive Social Security or Railroad Retirement benefits?",
            answer="No",
        ))

    # Interest and dividends (1099-INT, 1099-DIV)
    int_total = sum(m.interest_income for m in household.members)
    div_total = sum(m.dividend_income for m in household.members)
    inv_total = int_total + div_total
    if inv_total > 0:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive any interest or dividend income?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="income",
            question="How much in interest and dividends, roughly?",
            answer=f"${inv_total:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="income",
            question="Did you receive any interest or dividend income?",
            answer="No",
        ))

    # Other income (catch-all — permanent No pending generator expansion)
    notes.append(InterviewNote(
        category="income",
        question="Did you receive any other money not already mentioned?",
        answer="No",
    ))

    return notes
