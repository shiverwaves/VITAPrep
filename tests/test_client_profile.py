"""Tests for the client profile generator — Sprint 6 Step 3.

Validates:
- Correct facts generated for single adult, married, and HOH households
- Facts reference correct form field names
- Dependent facts include months, student, disability, citizenship
- Difficulty filtering works (easy/medium/hard)
- Edge cases: no householder, no dependents, many dependents
"""

from datetime import date
from typing import List

import pytest

from generator.models import (
    Address,
    ClientFact,
    Household,
    Person,
    RelationshipType,
)
from training.form_fields import (
    CLAIMED_AS_DEPENDENT,
    FILING_STATUS,
    NOT_CLAIMED_AS_DEPENDENT,
    YOU_EMAIL,
    YOU_PHONE,
    YOU_US_CITIZEN,
    YOU_JOB_TITLE,
    SPOUSE_JOB_TITLE,
    dep_field,
    DEP_MONTHS,
    DEP_STUDENT,
    DEP_DISABLED,
    DEP_US_CITIZEN,
)
from training.client_profile import (
    generate_client_profile,
    filter_by_difficulty,
    _citizenship_fact,
    _contact_facts,
    _employment_fact,
    _filing_status_fact,
    _claimed_as_dependent_fact,
    _dependent_facts,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def single_adult() -> Household:
    """Single adult, no dependents."""
    return Household(
        household_id="hh-s1",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=Address(
            street="100 Main St", city="Honolulu",
            state="HI", zip_code="96816",
        ),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30,
                sex="F",
                legal_first_name="Jane",
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                phone="(808) 555-1234",
                email="jane@example.com",
                occupation_title="Teacher",
            ),
        ],
    )


@pytest.fixture
def married_with_kids() -> Household:
    """Married couple with two children."""
    return Household(
        household_id="hh-m1",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
        address=Address(
            street="200 Palm Dr", city="Kailua",
            state="HI", zip_code="96734",
        ),
        members=[
            Person(
                person_id="p-10",
                relationship=RelationshipType.HOUSEHOLDER,
                age=40,
                sex="M",
                legal_first_name="John",
                legal_last_name="Smith",
                ssn="900-11-1111",
                dob=date(1982, 3, 10),
                phone="(808) 555-9999",
                email="john@example.com",
                occupation_title="Engineer",
            ),
            Person(
                person_id="p-11",
                relationship=RelationshipType.SPOUSE,
                age=38,
                sex="F",
                legal_first_name="Mary",
                legal_last_name="Smith",
                ssn="900-22-2222",
                dob=date(1984, 7, 22),
                occupation_title="Nurse",
            ),
            Person(
                person_id="p-12",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=15,
                sex="F",
                legal_first_name="Emma",
                legal_last_name="Smith",
                ssn="900-33-3333",
                dob=date(2007, 9, 18),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
                is_full_time_student=True,
            ),
            Person(
                person_id="p-13",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=10,
                sex="M",
                legal_first_name="Jake",
                legal_last_name="Smith",
                ssn="900-44-4444",
                dob=date(2012, 1, 5),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
                has_disability=True,
            ),
        ],
    )


@pytest.fixture
def single_parent() -> Household:
    """Single parent with one child — HOH."""
    return Household(
        household_id="hh-h1",
        state="HI",
        year=2022,
        pattern="single_parent",
        members=[
            Person(
                person_id="p-20",
                relationship=RelationshipType.HOUSEHOLDER,
                age=28,
                sex="F",
                legal_first_name="Leilani",
                legal_last_name="Kekoa",
                ssn="900-55-5555",
                dob=date(1994, 11, 3),
                phone="(808) 555-7777",
            ),
            Person(
                person_id="p-21",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=5,
                sex="M",
                legal_first_name="Kai",
                legal_last_name="Kekoa",
                ssn="900-66-6666",
                dob=date(2017, 4, 12),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=9,
            ),
        ],
    )


# =========================================================================
# Helper function tests
# =========================================================================

class TestCitizenshipFact:

    def test_primary_citizen(self) -> None:
        p = Person(person_id="p-01")
        fact = _citizenship_fact(p, is_primary=True)
        assert fact.category == "citizenship"
        assert "you" in fact.question
        assert fact.answer == "Yes"
        assert fact.form_field == YOU_US_CITIZEN
        assert fact.person_id == "p-01"

    def test_spouse_citizen(self) -> None:
        p = Person(person_id="p-02")
        fact = _citizenship_fact(p, is_primary=False)
        assert "spouse" in fact.question
        assert fact.person_id == "p-02"


class TestContactFacts:

    def test_phone_and_email(self) -> None:
        p = Person(
            person_id="p-01",
            phone="(808) 555-1234",
            email="test@example.com",
        )
        facts = _contact_facts(p)
        assert len(facts) == 2
        phones = [f for f in facts if f.form_field == YOU_PHONE]
        emails = [f for f in facts if f.form_field == YOU_EMAIL]
        assert len(phones) == 1
        assert phones[0].answer == "(808) 555-1234"
        assert len(emails) == 1
        assert emails[0].answer == "test@example.com"

    def test_no_contact_info(self) -> None:
        p = Person(person_id="p-01")
        facts = _contact_facts(p)
        assert facts == []

    def test_phone_only(self) -> None:
        p = Person(person_id="p-01", phone="555-0000")
        facts = _contact_facts(p)
        assert len(facts) == 1
        assert facts[0].form_field == YOU_PHONE

    def test_contact_not_required(self) -> None:
        p = Person(person_id="p-01", phone="555-0000", email="a@b.com")
        facts = _contact_facts(p)
        assert all(not f.required for f in facts)


class TestEmploymentFact:

    def test_has_job(self) -> None:
        p = Person(person_id="p-01", occupation_title="Teacher")
        fact = _employment_fact(p, is_primary=True)
        assert fact is not None
        assert fact.answer == "Teacher"
        assert fact.form_field == YOU_JOB_TITLE

    def test_spouse_job(self) -> None:
        p = Person(person_id="p-02", occupation_title="Nurse")
        fact = _employment_fact(p, is_primary=False)
        assert fact is not None
        assert fact.form_field == SPOUSE_JOB_TITLE
        assert "spouse" in fact.question

    def test_no_job(self) -> None:
        p = Person(person_id="p-01")
        fact = _employment_fact(p, is_primary=True)
        assert fact is None


class TestFilingStatusFact:

    def test_single(self, single_adult: Household) -> None:
        fact = _filing_status_fact(single_adult)
        assert fact.category == "filing"
        assert fact.answer == "Single"
        assert fact.form_field == FILING_STATUS

    def test_married(self, married_with_kids: Household) -> None:
        fact = _filing_status_fact(married_with_kids)
        assert fact.answer == "Married Filing Jointly"

    def test_hoh(self, single_parent: Household) -> None:
        fact = _filing_status_fact(single_parent)
        assert fact.answer == "Head of Household"


class TestClaimedAsDependentFact:

    def test_not_claimed(self) -> None:
        p = Person(person_id="p-01", can_be_claimed=False)
        fact = _claimed_as_dependent_fact(p)
        assert fact.answer == "No"
        assert fact.form_field == NOT_CLAIMED_AS_DEPENDENT

    def test_claimed(self) -> None:
        p = Person(person_id="p-01", can_be_claimed=True)
        fact = _claimed_as_dependent_fact(p)
        assert fact.answer == "Yes"
        assert fact.form_field == CLAIMED_AS_DEPENDENT


class TestDependentFacts:

    def test_basic_dependent(self) -> None:
        dep = Person(
            person_id="p-d1",
            legal_first_name="Jake",
            legal_last_name="Smith",
            months_in_home=12,
        )
        facts = _dependent_facts([dep])
        months_facts = [f for f in facts if "months" in f.question]
        assert len(months_facts) == 1
        assert months_facts[0].answer == "12"
        assert months_facts[0].form_field == dep_field(0, DEP_MONTHS)

    def test_student_dependent(self) -> None:
        dep = Person(
            person_id="p-d1",
            legal_first_name="Emma",
            legal_last_name="Smith",
            months_in_home=12,
            is_full_time_student=True,
        )
        facts = _dependent_facts([dep])
        student_facts = [f for f in facts if "student" in f.question.lower()]
        assert len(student_facts) == 1
        assert student_facts[0].answer == "Yes"
        assert student_facts[0].form_field == dep_field(0, DEP_STUDENT)

    def test_disabled_dependent(self) -> None:
        dep = Person(
            person_id="p-d1",
            legal_first_name="Sam",
            legal_last_name="Jones",
            months_in_home=12,
            has_disability=True,
        )
        facts = _dependent_facts([dep])
        disabled_facts = [f for f in facts if "disability" in f.question.lower()]
        assert len(disabled_facts) == 1
        assert disabled_facts[0].form_field == dep_field(0, DEP_DISABLED)

    def test_citizen_fact_per_dependent(self) -> None:
        dep = Person(
            person_id="p-d1",
            legal_first_name="Kai",
            legal_last_name="Kekoa",
            months_in_home=12,
        )
        facts = _dependent_facts([dep])
        citizen_facts = [f for f in facts if "citizen" in f.question.lower()]
        assert len(citizen_facts) == 1
        assert citizen_facts[0].form_field == dep_field(0, DEP_US_CITIZEN)

    def test_multiple_dependents_correct_indices(self) -> None:
        deps = [
            Person(person_id=f"p-d{i}", legal_first_name=f"Child{i}",
                   legal_last_name="Test", months_in_home=12)
            for i in range(3)
        ]
        facts = _dependent_facts(deps)
        months_facts = [f for f in facts if "months" in f.question]
        assert len(months_facts) == 3
        assert months_facts[0].form_field == dep_field(0, DEP_MONTHS)
        assert months_facts[1].form_field == dep_field(1, DEP_MONTHS)
        assert months_facts[2].form_field == dep_field(2, DEP_MONTHS)

    def test_capped_at_max_dependents(self) -> None:
        deps = [
            Person(person_id=f"p-d{i}", legal_first_name=f"Child{i}",
                   legal_last_name="Test", months_in_home=12)
            for i in range(6)
        ]
        facts = _dependent_facts(deps)
        months_facts = [f for f in facts if "months" in f.question]
        assert len(months_facts) == 4  # MAX_DEPENDENTS

    def test_dependent_name_in_question(self) -> None:
        dep = Person(
            person_id="p-d1",
            legal_first_name="Kai",
            legal_last_name="Kekoa",
            months_in_home=12,
        )
        facts = _dependent_facts([dep])
        assert any("Kai Kekoa" in f.question for f in facts)


# =========================================================================
# Full profile generation tests
# =========================================================================

class TestGenerateClientProfile:

    def test_single_adult_fact_count(self, single_adult: Household) -> None:
        facts = generate_client_profile(single_adult)
        # citizenship + phone + email + job + filing status + claimed_as_dep
        assert len(facts) == 6

    def test_single_adult_categories(self, single_adult: Household) -> None:
        facts = generate_client_profile(single_adult)
        categories = {f.category for f in facts}
        assert "citizenship" in categories
        assert "contact" in categories
        assert "employment" in categories
        assert "filing" in categories

    def test_married_includes_spouse_facts(
        self, married_with_kids: Household,
    ) -> None:
        facts = generate_client_profile(married_with_kids)
        spouse_facts = [f for f in facts if f.person_id == "p-11"]
        assert len(spouse_facts) >= 2  # citizenship + job

    def test_married_includes_dependent_facts(
        self, married_with_kids: Household,
    ) -> None:
        facts = generate_client_profile(married_with_kids)
        dep_facts = [f for f in facts if f.category == "dependent"]
        # 2 deps × (months + citizen) + student for Emma + disabled for Jake
        assert len(dep_facts) >= 6

    def test_student_flag_present(
        self, married_with_kids: Household,
    ) -> None:
        facts = generate_client_profile(married_with_kids)
        student_facts = [
            f for f in facts
            if "student" in f.question.lower() and f.person_id == "p-12"
        ]
        assert len(student_facts) == 1

    def test_disabled_flag_present(
        self, married_with_kids: Household,
    ) -> None:
        facts = generate_client_profile(married_with_kids)
        disabled_facts = [
            f for f in facts
            if "disability" in f.question.lower() and f.person_id == "p-13"
        ]
        assert len(disabled_facts) == 1

    def test_hoh_filing_status(self, single_parent: Household) -> None:
        facts = generate_client_profile(single_parent)
        fs_facts = [f for f in facts if f.form_field == FILING_STATUS]
        assert len(fs_facts) == 1
        assert fs_facts[0].answer == "Head of Household"

    def test_partial_months(self, single_parent: Household) -> None:
        facts = generate_client_profile(single_parent)
        months_facts = [f for f in facts if "months" in f.question]
        assert len(months_facts) == 1
        assert months_facts[0].answer == "9"

    def test_no_householder_returns_empty(self) -> None:
        hh = Household(
            household_id="hh-empty",
            state="HI",
            year=2022,
            pattern="other",
            members=[],
        )
        facts = generate_client_profile(hh)
        assert facts == []

    def test_all_facts_have_person_id(
        self, married_with_kids: Household,
    ) -> None:
        facts = generate_client_profile(married_with_kids)
        for f in facts:
            assert f.person_id, f"Fact missing person_id: {f.question}"

    def test_all_facts_have_category(
        self, married_with_kids: Household,
    ) -> None:
        facts = generate_client_profile(married_with_kids)
        for f in facts:
            assert f.category, f"Fact missing category: {f.question}"


# =========================================================================
# Difficulty filtering tests
# =========================================================================

class TestFilterByDifficulty:

    def test_easy_returns_all(self, single_adult: Household) -> None:
        facts = generate_client_profile(single_adult)
        filtered = filter_by_difficulty(facts, "easy")
        assert len(filtered) == len(facts)

    def test_medium_drops_optional(self, single_adult: Household) -> None:
        facts = generate_client_profile(single_adult)
        filtered = filter_by_difficulty(facts, "medium")
        # Phone and email are not required, should be dropped
        assert len(filtered) < len(facts)
        assert all(f.required for f in filtered)

    def test_hard_minimal_facts(self, single_adult: Household) -> None:
        facts = generate_client_profile(single_adult)
        filtered = filter_by_difficulty(facts, "hard")
        categories = {f.category for f in filtered}
        assert categories <= {"citizenship", "filing"}
        assert len(filtered) < len(filter_by_difficulty(facts, "medium"))

    def test_hard_with_dependents(
        self, married_with_kids: Household,
    ) -> None:
        facts = generate_client_profile(married_with_kids)
        filtered = filter_by_difficulty(facts, "hard")
        # Should only have citizenship and filing facts
        assert all(f.category in ("citizenship", "filing") for f in filtered)

    def test_unknown_difficulty_returns_all(
        self, single_adult: Household,
    ) -> None:
        facts = generate_client_profile(single_adult)
        filtered = filter_by_difficulty(facts, "unknown_level")
        assert len(filtered) == len(facts)
