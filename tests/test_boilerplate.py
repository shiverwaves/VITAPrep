"""Tests for the boilerplate renderer (intake/boilerplate.py).

Covers:
- All boilerplate note categories (citizenship, filing, contact, employment, dependent).
- Difficulty filtering: easy=all, medium=drops contact, hard=citizenship+filing only.
- Edge cases: no householder, no spouse, no dependents, no occupation.
- Note structure: all notes have source_slot=None.
"""

from datetime import date

import pytest

from generator.models import (
    Address,
    FilingStatus,
    Household,
    Person,
    RelationshipType,
)
from intake.analyzer.types import InterviewNote
from intake.boilerplate import generate_boilerplate


# =========================================================================
# Helpers
# =========================================================================

def _addr():
    return Address(
        street="100 Main St", city="Honolulu",
        state="HI", zip_code="96816",
    )


def _single_adult() -> Household:
    return Household(
        household_id="hh-bp-1",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=_addr(),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30, sex="F", race="white",
                legal_first_name="Jane", legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                id_address=_addr(),
                phone="(808) 555-1234",
                email="jane@example.com",
                occupation_title="Cashier",
                wage_income=40000,
            ),
        ],
    )


def _married_with_kids() -> Household:
    return Household(
        household_id="hh-bp-2",
        state="HI",
        year=2022,
        pattern="married_with_children",
        address=_addr(),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=35, sex="M", race="white",
                legal_first_name="John", legal_last_name="Smith",
                ssn="900-11-1111",
                dob=date(1987, 3, 10),
                id_address=_addr(),
                phone="(808) 555-9999",
                email="john@example.com",
                occupation_title="Plumber",
                wage_income=55000,
            ),
            Person(
                person_id="p-02",
                relationship=RelationshipType.SPOUSE,
                age=33, sex="F", race="white",
                legal_first_name="Mary", legal_last_name="Smith",
                ssn="900-22-2222",
                dob=date(1989, 7, 20),
                id_address=_addr(),
                occupation_title="Nurse",
                wage_income=48000,
            ),
            Person(
                person_id="p-03",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=8, sex="M", race="white",
                legal_first_name="Tommy", legal_last_name="Smith",
                ssn="900-33-3333",
                dob=date(2014, 1, 15),
                id_address=_addr(),
                months_in_home=12,
                is_dependent=True,
                is_full_time_student=False,
            ),
            Person(
                person_id="p-04",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=19, sex="F", race="white",
                legal_first_name="Sarah", legal_last_name="Smith",
                ssn="900-44-4444",
                dob=date(2003, 9, 5),
                id_address=_addr(),
                months_in_home=12,
                is_dependent=True,
                is_full_time_student=True,
                has_disability=True,
            ),
        ],
    )


# =========================================================================
# 1. Basic structure
# =========================================================================

class TestBasicStructure:

    def test_all_notes_are_interview_notes(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        assert all(isinstance(n, InterviewNote) for n in notes)

    def test_all_source_slot_none(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        assert all(n.source_slot is None for n in notes)

    def test_returns_list(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        assert isinstance(notes, list)
        assert len(notes) > 0


# =========================================================================
# 2. Single adult — note categories
# =========================================================================

class TestSingleAdult:

    def test_citizenship_note(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        cit = [n for n in notes if n.category == "citizenship"]
        assert len(cit) == 1
        assert "U.S. citizen" in cit[0].question
        assert cit[0].answer == "Yes"

    def test_filing_status_note(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        filing = [n for n in notes if n.category == "filing"
                  and "filing status" in n.question]
        assert len(filing) == 1
        assert filing[0].answer == "Single"

    def test_claimed_as_dependent_note(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        dep = [n for n in notes if "claim you as a dependent" in n.question]
        assert len(dep) == 1
        assert dep[0].answer == "No"

    def test_contact_notes(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        contact = [n for n in notes if n.category == "contact"]
        assert len(contact) == 2
        phones = [n for n in contact if "phone" in n.question]
        emails = [n for n in contact if "email" in n.question]
        assert len(phones) == 1
        assert len(emails) == 1

    def test_employment_note(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        emp = [n for n in notes if n.category == "employment"]
        assert len(emp) == 1
        assert emp[0].answer == "Cashier"


# =========================================================================
# 3. Married with children
# =========================================================================

class TestMarriedWithKids:

    def test_spouse_citizenship(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "easy")
        cit = [n for n in notes if n.category == "citizenship"]
        assert len(cit) == 2

    def test_spouse_employment(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "easy")
        emp = [n for n in notes if n.category == "employment"]
        assert len(emp) == 2
        answers = {n.answer for n in emp}
        assert "Plumber" in answers
        assert "Nurse" in answers

    def test_dependent_months(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "easy")
        months = [n for n in notes if "months" in n.question]
        assert len(months) == 2

    def test_dependent_student(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "easy")
        student = [n for n in notes if "full-time student" in n.question]
        assert len(student) == 1
        assert "Sarah" in student[0].question

    def test_dependent_disability(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "easy")
        disabled = [n for n in notes if "disability" in n.question]
        assert len(disabled) == 1
        assert "Sarah" in disabled[0].question

    def test_dependent_citizenship(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "easy")
        dep_cit = [n for n in notes if n.category == "dependent"
                   and "citizen" in n.question]
        assert len(dep_cit) == 2

    def test_filing_status_mfj(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "easy")
        filing = [n for n in notes if "filing status" in n.question]
        assert filing[0].answer == "Married Filing Jointly"


# =========================================================================
# 4. Difficulty filtering
# =========================================================================

class TestDifficultyFiltering:

    def test_easy_includes_contact(self) -> None:
        notes = generate_boilerplate(_single_adult(), "easy")
        contact = [n for n in notes if n.category == "contact"]
        assert len(contact) > 0

    def test_medium_drops_contact(self) -> None:
        notes = generate_boilerplate(_single_adult(), "medium")
        contact = [n for n in notes if n.category == "contact"]
        assert len(contact) == 0

    def test_medium_keeps_employment(self) -> None:
        notes = generate_boilerplate(_single_adult(), "medium")
        emp = [n for n in notes if n.category == "employment"]
        assert len(emp) == 1

    def test_medium_keeps_dependents(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "medium")
        dep = [n for n in notes if n.category == "dependent"]
        assert len(dep) > 0

    def test_hard_only_citizenship_and_filing(self) -> None:
        notes = generate_boilerplate(_single_adult(), "hard")
        categories = {n.category for n in notes}
        assert categories <= {"citizenship", "filing"}

    def test_hard_no_employment(self) -> None:
        notes = generate_boilerplate(_single_adult(), "hard")
        emp = [n for n in notes if n.category == "employment"]
        assert len(emp) == 0

    def test_hard_no_dependents(self) -> None:
        notes = generate_boilerplate(_married_with_kids(), "hard")
        dep = [n for n in notes if n.category == "dependent"]
        assert len(dep) == 0

    def test_hard_no_contact(self) -> None:
        notes = generate_boilerplate(_single_adult(), "hard")
        contact = [n for n in notes if n.category == "contact"]
        assert len(contact) == 0

    def test_easy_more_notes_than_medium(self) -> None:
        easy = generate_boilerplate(_single_adult(), "easy")
        medium = generate_boilerplate(_single_adult(), "medium")
        assert len(easy) >= len(medium)

    def test_medium_more_notes_than_hard(self) -> None:
        medium = generate_boilerplate(_single_adult(), "medium")
        hard = generate_boilerplate(_single_adult(), "hard")
        assert len(medium) >= len(hard)


# =========================================================================
# 5. Edge cases
# =========================================================================

class TestEdgeCases:

    def test_no_occupation_no_employment_note(self) -> None:
        hh = _single_adult()
        hh.members[0].occupation_title = None
        notes = generate_boilerplate(hh, "easy")
        emp = [n for n in notes if n.category == "employment"]
        assert len(emp) == 0

    def test_no_phone_no_phone_note(self) -> None:
        hh = _single_adult()
        hh.members[0].phone = ""
        notes = generate_boilerplate(hh, "easy")
        phones = [n for n in notes if "phone" in n.question]
        assert len(phones) == 0

    def test_no_email_no_email_note(self) -> None:
        hh = _single_adult()
        hh.members[0].email = ""
        notes = generate_boilerplate(hh, "easy")
        emails = [n for n in notes if "email" in n.question]
        assert len(emails) == 0

    def test_empty_household_returns_empty(self) -> None:
        hh = Household(
            household_id="hh-empty",
            state="HI",
            year=2022,
            pattern="single_adult",
            address=_addr(),
            members=[],
        )
        notes = generate_boilerplate(hh, "easy")
        assert notes == []

    def test_can_be_claimed_yes(self) -> None:
        hh = _single_adult()
        hh.members[0].can_be_claimed = True
        notes = generate_boilerplate(hh, "easy")
        dep = [n for n in notes if "claim you" in n.question]
        assert dep[0].answer == "Yes"
