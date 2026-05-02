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

from generator.models import FilingStatus, Household, Person, RelationshipType
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
    notes.extend(_schedule_a_notes(household))
    notes.extend(_above_line_notes(household))
    notes.extend(_education_and_care_notes(household))

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
    householder = household.get_householder()
    spouse = household.get_spouse()
    filers = [f for f in (householder, spouse) if f is not None]

    for filer in filers:
        who = "you" if filer.relationship == RelationshipType.HOUSEHOLDER else "your spouse"
        label = "You" if filer.relationship == RelationshipType.HOUSEHOLDER else "Spouse"

        # Wages (W-2)
        has_wages = (filer.wage_income > 0
                     and filer.disability_income_source != "w2")
        if has_wages:
            w2_count = len(filer.w2s)
            notes.append(InterviewNote(
                category="income",
                question=f"Did {who} receive wages as an employee?",
                answer="Yes",
            ))
            notes.append(InterviewNote(
                category="income",
                question=f"How many W-2s? ({label})",
                answer=str(w2_count),
            ))
        else:
            notes.append(InterviewNote(
                category="income",
                question=f"Did {who} receive wages as an employee?",
                answer="No",
            ))

        # Self-employment (1099-NEC)
        if filer.self_employment_income > 0:
            notes.append(InterviewNote(
                category="income",
                question=f"Did {who} receive self-employment income?",
                answer="Yes",
            ))
            notes.append(InterviewNote(
                category="income",
                question=f"What kind of work? ({label})",
                answer=filer.occupation_title or "Self-employed",
            ))
        else:
            notes.append(InterviewNote(
                category="income",
                question=f"Did {who} receive self-employment income?",
                answer="No",
            ))

        # Disability benefits (W-2 or 1099-R)
        if filer.disability_income_source is not None:
            source = filer.disability_income_source
            notes.append(InterviewNote(
                category="income",
                question=f"Did {who} receive disability benefits?",
                answer="Yes",
            ))
            notes.append(InterviewNote(
                category="income",
                question=f"Disability form? ({label})",
                answer="W-2" if source == "w2" else "1099-R",
            ))
        else:
            notes.append(InterviewNote(
                category="income",
                question=f"Did {who} receive disability benefits?",
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


# =========================================================================
# Page 3 — Expenses (Subset 3: Schedule A items)
# =========================================================================



def _schedule_a_notes(household: Household) -> List[InterviewNote]:
    notes: List[InterviewNote] = []

    # Mortgage interest (Form 1098)
    if household.mortgage_interest > 0:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay mortgage interest on your home?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="expenses",
            question="How much mortgage interest, roughly?",
            answer=f"${household.mortgage_interest:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay mortgage interest on your home?",
            answer="No",
        ))

    # Taxes paid (state, local, property)
    tax_total = household.state_income_tax + household.property_taxes
    if tax_total > 0:
        kinds = []
        if household.state_income_tax > 0:
            kinds.append("state income tax")
        if household.property_taxes > 0:
            kinds.append("property taxes")
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay state, local, or property taxes?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="expenses",
            question="What kinds of taxes?",
            answer=", ".join(kinds),
        ))
    else:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay state, local, or property taxes?",
            answer="No",
        ))

    # Medical expenses (always positive after always-generate change)
    if household.medical_expenses > 0:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you have medical, dental, or prescription expenses?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="expenses",
            question="How much in medical expenses, roughly?",
            answer=f"${household.medical_expenses:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you have medical, dental, or prescription expenses?",
            answer="No",
        ))

    # Charitable contributions
    if household.charitable_contributions > 0:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you make any charitable contributions?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="expenses",
            question="How much in charitable contributions, roughly?",
            answer=f"${household.charitable_contributions:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you make any charitable contributions?",
            answer="No",
        ))

    return notes


# =========================================================================
# Page 3 — Expenses (Subset 4: Above-the-line deductions)
# =========================================================================


def _above_line_notes(household: Household) -> List[InterviewNote]:
    notes: List[InterviewNote] = []

    # Student loan interest (Form 1098-E)
    sl_total = sum(m.student_loan_interest for m in household.members)
    if sl_total > 0:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay student loan interest?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="expenses",
            question="How much student loan interest, roughly?",
            answer=f"${sl_total:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay student loan interest?",
            answer="No",
        ))

    # IRA contributions
    ira_members = [m for m in household.members if m.ira_contributions > 0]
    if ira_members:
        total = sum(m.ira_contributions for m in ira_members)
        ira_type = ira_members[0].ira_type or "traditional"
        notes.append(InterviewNote(
            category="expenses",
            question="Did you contribute to a retirement account (IRA)?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="expenses",
            question="Traditional or Roth?",
            answer=ira_type.capitalize(),
        ))
    else:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you contribute to a retirement account (IRA)?",
            answer="No",
        ))

    # Educator expenses
    edu_total = sum(m.educator_expenses for m in household.members)
    if edu_total > 0:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay for school supplies as an educator?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="expenses",
            question="How much in educator expenses, roughly?",
            answer=f"${edu_total:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="expenses",
            question="Did you pay for school supplies as an educator?",
            answer="No",
        ))

    return notes


# =========================================================================
# Page 3 — Credits (Subset 5: Education and child care)
# =========================================================================


def _education_and_care_notes(household: Household) -> List[InterviewNote]:
    notes: List[InterviewNote] = []

    # Education expenses (Form 1098-T)
    if household.education_expenses > 0:
        recipient = _education_recipient(household)
        notes.append(InterviewNote(
            category="credits",
            question="Did you pay for educational classes (college, technical school, or job-related)?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="credits",
            question="Who took the classes?",
            answer=recipient,
        ))
    else:
        notes.append(InterviewNote(
            category="credits",
            question="Did you pay for educational classes (college, technical school, or job-related)?",
            answer="No",
        ))

    # Child and dependent care
    if household.child_care_expenses > 0:
        notes.append(InterviewNote(
            category="credits",
            question="Did you pay for child or dependent care?",
            answer="Yes",
        ))
        notes.append(InterviewNote(
            category="credits",
            question="How much in child care expenses, roughly?",
            answer=f"${household.child_care_expenses:,}",
        ))
    else:
        notes.append(InterviewNote(
            category="credits",
            question="Did you pay for child or dependent care?",
            answer="No",
        ))

    return notes


def _education_recipient(household: Household) -> str:
    for m in household.members:
        if m.form_1098_ts:
            if m.relationship == RelationshipType.HOUSEHOLDER:
                return "Primary filer"
            elif m.relationship == RelationshipType.SPOUSE:
                return "Spouse"
            else:
                name = f"{m.legal_first_name} {m.legal_last_name}".strip()
                return name or "Dependent"
    return "Primary filer"
