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
    Form1098T,
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
        disabled = [n for n in notes if n.category == "dependent"
                    and "disability" in n.question]
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

    def test_hard_drops_employment_dependents_contact(self) -> None:
        notes = generate_boilerplate(_single_adult(), "hard")
        categories = {n.category for n in notes}
        # Hard drops employment, dependents, contact
        assert "employment" not in categories
        assert "dependent" not in categories
        assert "contact" not in categories
        # Keeps citizenship, filing, and Page 2-3 ground truth (income, expenses)
        assert "citizenship" in categories
        assert "filing" in categories

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


# =========================================================================
# 6. Passive income notes (Subset 2)
# =========================================================================


class TestPassiveIncomeNotes:

    def test_no_passive_income_all_negative(self) -> None:
        hh = _single_adult()
        hh.members[0].wage_income = 0  # remove wage so everything is negative
        notes = generate_boilerplate(hh, "easy")
        # Passive income questions: retirement, SS, interest/div, other
        passive_questions = [n for n in notes if n.category == "income"
                            and any(kw in n.question for kw in
                                    ("retirement", "Social Security",
                                     "interest or dividend", "other money"))]
        assert len(passive_questions) == 4
        assert all(n.answer == "No" for n in passive_questions)

    def test_retirement_income_positive(self) -> None:
        hh = _single_adult()
        hh.members[0].retirement_income = 15000
        notes = generate_boilerplate(hh, "easy")
        ret = [n for n in notes if "retirement" in n.question]
        assert ret[0].answer == "Yes"
        assert ret[1].answer == "$15,000"

    def test_social_security_positive(self) -> None:
        hh = _single_adult()
        hh.members[0].social_security_income = 18000
        notes = generate_boilerplate(hh, "easy")
        ss = [n for n in notes if "Social Security" in n.question]
        assert ss[0].answer == "Yes"
        assert ss[1].answer == "$18,000"

    def test_interest_and_dividends_positive(self) -> None:
        hh = _single_adult()
        hh.members[0].interest_income = 500
        hh.members[0].dividend_income = 200
        notes = generate_boilerplate(hh, "easy")
        inv = [n for n in notes if "interest" in n.question and "dividend" in n.question]
        assert len(inv) == 2
        assert inv[0].answer == "Yes"
        assert inv[1].answer == "$700"

    def test_other_income_always_no(self) -> None:
        hh = _single_adult()
        hh.members[0].retirement_income = 10000
        hh.members[0].social_security_income = 5000
        notes = generate_boilerplate(hh, "easy")
        other = [n for n in notes if "other money" in n.question]
        assert len(other) == 1
        assert other[0].answer == "No"

    def test_multiple_members_aggregated(self) -> None:
        hh = _married_with_kids()
        hh.members[0].retirement_income = 10000
        hh.members[1].retirement_income = 8000
        notes = generate_boilerplate(hh, "easy")
        ret = [n for n in notes if "retirement" in n.question]
        assert ret[0].answer == "Yes"
        assert ret[1].answer == "$18,000"

    def test_passive_income_not_gated_by_difficulty(self) -> None:
        hh = _single_adult()
        hh.members[0].social_security_income = 12000
        for diff in ("easy", "medium", "hard"):
            notes = generate_boilerplate(hh, diff)
            ss = [n for n in notes if "Social Security" in n.question]
            assert ss[0].answer == "Yes"


# =========================================================================
# 7. Wage and SE income notes (Subset 1)
# =========================================================================


class TestWageAndSENotes:

    def test_no_wage_income_negative(self) -> None:
        hh = _single_adult()
        hh.members[0].wage_income = 0
        notes = generate_boilerplate(hh, "easy")
        wage = [n for n in notes if "wages" in n.question.lower()]
        assert wage[0].answer == "No"

    def test_wage_income_positive_with_job_count(self) -> None:
        from generator.models import W2
        hh = _single_adult()
        hh.members[0].wage_income = 40000
        hh.members[0].w2s = [
            W2(wages=25000, federal_tax_withheld=3000,
               social_security_wages=25000, social_security_tax=1550,
               medicare_wages=25000, medicare_tax=362, state="HI",
               state_wages=25000, state_tax=800),
            W2(wages=15000, federal_tax_withheld=1500,
               social_security_wages=15000, social_security_tax=930,
               medicare_wages=15000, medicare_tax=217, state="HI",
               state_wages=15000, state_tax=400),
        ]
        notes = generate_boilerplate(hh, "easy")
        wage = [n for n in notes if "wages" in n.question.lower()]
        assert wage[0].answer == "Yes"
        jobs = [n for n in notes if "How many jobs" in n.question]
        assert jobs[0].answer == "2"

    def test_disability_w2_not_counted_as_wages(self) -> None:
        from generator.models import W2
        hh = _single_adult()
        hh.members[0].wage_income = 20000
        hh.members[0].disability_income_source = "w2"
        hh.members[0].w2s = [
            W2(wages=20000, federal_tax_withheld=2000,
               social_security_wages=20000, social_security_tax=1240,
               medicare_wages=20000, medicare_tax=290, state="HI",
               state_wages=20000, state_tax=500),
        ]
        notes = generate_boilerplate(hh, "easy")
        wage = [n for n in notes if "wages" in n.question.lower()]
        assert wage[0].answer == "No"

    def test_no_se_income_negative(self) -> None:
        hh = _single_adult()
        notes = generate_boilerplate(hh, "easy")
        se = [n for n in notes if "self-employment" in n.question.lower()]
        assert se[0].answer == "No"

    def test_se_income_positive_with_occupation(self) -> None:
        hh = _single_adult()
        hh.members[0].self_employment_income = 30000
        hh.members[0].occupation_title = "Carpenter"
        notes = generate_boilerplate(hh, "easy")
        se = [n for n in notes if "self-employment" in n.question.lower()]
        assert se[0].answer == "Yes"
        occ = [n for n in notes if "What kind of work" in n.question]
        assert occ[0].answer == "Carpenter"

    def test_disability_positive(self) -> None:
        hh = _single_adult()
        hh.members[0].disability_income_source = "w2"
        notes = generate_boilerplate(hh, "easy")
        dis = [n for n in notes if "disability" in n.question.lower()]
        assert dis[0].answer == "Yes"
        assert dis[1].answer == "W-2"

    def test_disability_1099r(self) -> None:
        hh = _single_adult()
        hh.members[0].disability_income_source = "1099r"
        notes = generate_boilerplate(hh, "easy")
        dis = [n for n in notes if "disability" in n.question.lower()]
        assert dis[0].answer == "Yes"
        assert dis[1].answer == "1099-R"

    def test_no_disability_negative(self) -> None:
        hh = _single_adult()
        notes = generate_boilerplate(hh, "easy")
        dis = [n for n in notes if "disability" in n.question.lower()]
        assert dis[0].answer == "No"


# =========================================================================
# 8. Schedule A notes (Subset 3)
# =========================================================================


class TestScheduleANotes:

    def test_mortgage_positive(self) -> None:
        hh = _single_adult()
        hh.mortgage_interest = 12000
        notes = generate_boilerplate(hh, "easy")
        mort = [n for n in notes if "mortgage" in n.question.lower()]
        assert mort[0].answer == "Yes"
        assert mort[1].answer == "$12,000"

    def test_mortgage_negative(self) -> None:
        hh = _single_adult()
        hh.mortgage_interest = 0
        notes = generate_boilerplate(hh, "easy")
        mort = [n for n in notes if "mortgage" in n.question.lower()]
        assert mort[0].answer == "No"

    def test_taxes_positive_both(self) -> None:
        hh = _single_adult()
        hh.state_income_tax = 5000
        hh.property_taxes = 3000
        notes = generate_boilerplate(hh, "easy")
        tax = [n for n in notes if "taxes" in n.question.lower()
               and n.category == "expenses"]
        assert tax[0].answer == "Yes"
        assert "state income tax" in tax[1].answer
        assert "property taxes" in tax[1].answer

    def test_taxes_negative(self) -> None:
        hh = _single_adult()
        hh.state_income_tax = 0
        hh.property_taxes = 0
        notes = generate_boilerplate(hh, "easy")
        tax = [n for n in notes if "state, local, or property" in n.question]
        assert tax[0].answer == "No"

    def test_medical_bin_small(self) -> None:
        hh = _single_adult()
        hh.medical_expenses = 350
        notes = generate_boilerplate(hh, "easy")
        med = [n for n in notes if "medical" in n.question.lower()]
        assert med[0].answer == "Yes"
        assert med[1].answer == "a few hundred dollars"

    def test_medical_bin_medium(self) -> None:
        hh = _single_adult()
        hh.medical_expenses = 3500
        notes = generate_boilerplate(hh, "easy")
        med = [n for n in notes if "medical" in n.question.lower()]
        assert med[1].answer == "a few thousand dollars"

    def test_medical_bin_large(self) -> None:
        hh = _single_adult()
        hh.medical_expenses = 8000
        notes = generate_boilerplate(hh, "easy")
        med = [n for n in notes if "medical" in n.question.lower()]
        assert med[1].answer == "around ten thousand dollars"

    def test_medical_bin_very_large(self) -> None:
        hh = _single_adult()
        hh.medical_expenses = 25000
        notes = generate_boilerplate(hh, "easy")
        med = [n for n in notes if "medical" in n.question.lower()]
        assert med[1].answer == "$25,000"

    def test_charitable_positive(self) -> None:
        hh = _single_adult()
        hh.charitable_contributions = 2500
        notes = generate_boilerplate(hh, "easy")
        char = [n for n in notes if "charitable" in n.question.lower()]
        assert char[0].answer == "Yes"
        assert char[1].answer == "$2,500"

    def test_charitable_negative(self) -> None:
        hh = _single_adult()
        hh.charitable_contributions = 0
        notes = generate_boilerplate(hh, "easy")
        char = [n for n in notes if "charitable" in n.question.lower()]
        assert char[0].answer == "No"


# =========================================================================
# 9. Above-the-line notes (Subset 4)
# =========================================================================


class TestAboveLineNotes:

    def test_student_loan_positive(self) -> None:
        hh = _single_adult()
        hh.members[0].student_loan_interest = 1800
        notes = generate_boilerplate(hh, "easy")
        sl = [n for n in notes if "student loan" in n.question.lower()]
        assert sl[0].answer == "Yes"
        assert sl[1].answer == "$1,800"

    def test_student_loan_negative(self) -> None:
        hh = _single_adult()
        notes = generate_boilerplate(hh, "easy")
        sl = [n for n in notes if "student loan" in n.question.lower()]
        assert sl[0].answer == "No"

    def test_ira_traditional(self) -> None:
        hh = _single_adult()
        hh.members[0].ira_contributions = 5000
        hh.members[0].ira_type = "traditional"
        notes = generate_boilerplate(hh, "easy")
        ira = [n for n in notes if "ira" in n.question.lower()
               or "Traditional or Roth" in n.question]
        assert ira[0].answer == "Yes"
        assert ira[1].answer == "Traditional"

    def test_ira_roth(self) -> None:
        hh = _single_adult()
        hh.members[0].ira_contributions = 3000
        hh.members[0].ira_type = "roth"
        notes = generate_boilerplate(hh, "easy")
        ira = [n for n in notes if "Traditional or Roth" in n.question]
        assert ira[0].answer == "Roth"

    def test_ira_both(self) -> None:
        hh = _single_adult()
        hh.members[0].ira_contributions = 6000
        hh.members[0].ira_type = "both"
        notes = generate_boilerplate(hh, "easy")
        ira = [n for n in notes if "Traditional or Roth" in n.question]
        assert ira[0].answer == "Both"

    def test_ira_negative(self) -> None:
        hh = _single_adult()
        notes = generate_boilerplate(hh, "easy")
        ira = [n for n in notes if "retirement account" in n.question.lower()]
        assert ira[0].answer == "No"

    def test_educator_positive(self) -> None:
        hh = _single_adult()
        hh.members[0].educator_expenses = 250
        notes = generate_boilerplate(hh, "easy")
        edu = [n for n in notes if "educator" in n.question.lower()
               or "school supplies" in n.question.lower()]
        assert edu[0].answer == "Yes"
        assert edu[1].answer == "$250"

    def test_educator_negative(self) -> None:
        hh = _single_adult()
        notes = generate_boilerplate(hh, "easy")
        edu = [n for n in notes if "school supplies" in n.question.lower()]
        assert edu[0].answer == "No"


class TestEducationAndCareNotes:

    def test_education_positive_primary_filer(self) -> None:
        hh = _single_adult()
        hh.education_expenses = 8000
        hh.members[0].form_1098_ts = [Form1098T(
            institution_name="U of Hawaii",
            institution_tin="99-1234567",
            amounts_billed=8000,
            student_ssn="900-12-3456",
        )]
        notes = generate_boilerplate(hh, "easy")
        edu = [n for n in notes if "educational classes" in n.question.lower()]
        assert edu[0].answer == "Yes"
        who = [n for n in notes if "Who took the classes" in n.question]
        assert who[0].answer == "Primary filer"

    def test_education_positive_spouse(self) -> None:
        hh = _single_adult()
        hh.education_expenses = 5000
        spouse = Person(
            person_id="p-02",
            relationship=RelationshipType.SPOUSE,
            age=28, sex="M", race="white",
            legal_first_name="John", legal_last_name="Doe",
            ssn="900-65-4321",
            dob=date(1994, 3, 10),
            id_address=_addr(),
        )
        spouse.form_1098_ts = [Form1098T(
            institution_name="UH Manoa",
            institution_tin="99-7654321",
            amounts_billed=5000,
            student_ssn="900-65-4321",
        )]
        hh.members.append(spouse)
        notes = generate_boilerplate(hh, "easy")
        who = [n for n in notes if "Who took the classes" in n.question]
        assert who[0].answer == "Spouse"

    def test_education_positive_dependent(self) -> None:
        hh = _single_adult()
        hh.education_expenses = 12000
        dep = Person(
            person_id="p-03",
            relationship=RelationshipType.BIOLOGICAL_CHILD,
            age=19, sex="F", race="white",
            legal_first_name="Sara", legal_last_name="Doe",
            ssn="900-99-8888",
            dob=date(2003, 7, 20),
            id_address=_addr(),
            is_dependent=True,
            is_full_time_student=True,
        )
        dep.form_1098_ts = [Form1098T(
            institution_name="Community College",
            institution_tin="99-1112222",
            amounts_billed=12000,
            student_ssn="900-99-8888",
        )]
        hh.members.append(dep)
        notes = generate_boilerplate(hh, "easy")
        who = [n for n in notes if "Who took the classes" in n.question]
        assert who[0].answer == "Sara Doe"

    def test_education_negative(self) -> None:
        hh = _single_adult()
        notes = generate_boilerplate(hh, "easy")
        edu = [n for n in notes if "educational classes" in n.question.lower()]
        assert len(edu) == 1
        assert edu[0].answer == "No"

    def test_child_care_positive(self) -> None:
        hh = _single_adult()
        hh.child_care_expenses = 9500
        notes = generate_boilerplate(hh, "easy")
        care = [n for n in notes if "child or dependent care" in n.question.lower()]
        assert care[0].answer == "Yes"
        amt = [n for n in notes if "child care expenses" in n.question.lower()]
        assert amt[0].answer == "$9,500"

    def test_child_care_negative(self) -> None:
        hh = _single_adult()
        notes = generate_boilerplate(hh, "easy")
        care = [n for n in notes if "child or dependent care" in n.question.lower()]
        assert len(care) == 1
        assert care[0].answer == "No"

    def test_category_is_credits(self) -> None:
        hh = _single_adult()
        hh.education_expenses = 5000
        hh.child_care_expenses = 8000
        hh.members[0].form_1098_ts = [Form1098T(
            institution_name="Test U",
            institution_tin="99-0000000",
            amounts_billed=5000,
        )]
        notes = generate_boilerplate(hh, "easy")
        credit_notes = [n for n in notes if n.category == "credits"]
        assert len(credit_notes) == 4  # edu yes + who + care yes + amount

    def test_not_gated_by_difficulty(self) -> None:
        hh = _single_adult()
        hh.education_expenses = 10000
        hh.child_care_expenses = 7000
        hh.members[0].form_1098_ts = [Form1098T(
            institution_name="Test U",
            institution_tin="99-0000000",
            amounts_billed=10000,
        )]
        for diff in ("easy", "medium", "hard"):
            notes = generate_boilerplate(hh, diff)
            credit_notes = [n for n in notes if n.category == "credits"]
            assert len(credit_notes) == 4, f"Expected 4 credit notes at {diff}"
