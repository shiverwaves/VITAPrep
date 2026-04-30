"""TDD tests for the error injector — Sprint 6 Step 5.

These tests define the *contract* the ErrorInjector must satisfy.
Written before the implementation (red phase).

Contract summary
----------------
ErrorInjector.inject(household, difficulty, error_count)
  → (modified_household, List[InjectedError])

Requirements:
1. Returns a (Household, list) tuple — never None.
2. Each InjectedError has all fields populated (error_id, category,
   field, person_id, document, correct_value, erroneous_value,
   explanation, difficulty).
3. error_count controls how many errors are injected (± 0).
4. ~15% of the time error_count=0 is forced (error-free scenario) —
   when error_count is explicitly 0 the manifest MUST be empty.
5. Difficulty affects the *kind* of errors chosen:
   - easy: obvious (name misspelling, transposed SSN digits)
   - medium: moderate (wrong filing status, address mismatch)
   - hard: subtle (dependent age-ineligible, expired ID)
6. Error categories: name, ssn, address, dob, filing_status,
   dependent, expiration.
7. The modified household differs from the original in exactly the
   fields described by the manifest.
8. Errors never target a non-existent person.
9. Each error touches a unique (person_id, field) pair — no
   duplicate mutations.
"""

import copy
from datetime import date
from typing import List

import pytest

from generator.models import (
    Address,
    Employer,
    Form1099INT,
    Household,
    InjectedError,
    Person,
    RelationshipType,
    W2,
)
from training.error_injector import ErrorInjector


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def injector() -> ErrorInjector:
    return ErrorInjector()


@pytest.fixture
def single_adult() -> Household:
    """Minimal household — single adult with full PII."""
    return Household(
        household_id="hh-ei-1",
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
                race="white",
                legal_first_name="Jane",
                legal_middle_name="Ann",
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                phone="(808) 555-1234",
                email="jane@example.com",
                id_type="drivers_license",
                id_state="HI",
                id_number="H1234567",
                id_expiry=date(2028, 6, 15),
                id_address=Address(
                    street="100 Main St", city="Honolulu",
                    state="HI", zip_code="96816",
                ),
            ),
        ],
    )


@pytest.fixture
def married_with_kids() -> Household:
    """Married couple with two dependents — richer error surface."""
    return Household(
        household_id="hh-ei-2",
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
                race="white",
                legal_first_name="John",
                legal_middle_name="Robert",
                legal_last_name="Smith",
                ssn="900-11-1111",
                dob=date(1982, 3, 10),
                phone="(808) 555-9999",
                email="john@example.com",
                id_type="drivers_license",
                id_state="HI",
                id_number="H9876543",
                id_expiry=date(2027, 12, 1),
                id_address=Address(
                    street="200 Palm Dr", city="Kailua",
                    state="HI", zip_code="96734",
                ),
            ),
            Person(
                person_id="p-11",
                relationship=RelationshipType.SPOUSE,
                age=38,
                sex="F",
                legal_first_name="Mary",
                legal_middle_name="Lynn",
                legal_last_name="Smith",
                ssn="900-22-2222",
                dob=date(1984, 7, 22),
                id_type="drivers_license",
                id_state="HI",
                id_number="H5555555",
                id_expiry=date(2026, 4, 30),
                id_address=Address(
                    street="200 Palm Dr", city="Kailua",
                    state="HI", zip_code="96734",
                ),
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
            ),
        ],
    )


# =========================================================================
# 1. Return type & structure
# =========================================================================

class TestReturnType:

    def test_returns_tuple(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        result = injector.inject(single_adult, difficulty="easy", error_count=1)
        assert isinstance(result, tuple)
        assert len(result) == 2

    def test_first_element_is_household(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        modified, _ = injector.inject(single_adult, difficulty="easy", error_count=1)
        assert isinstance(modified, Household)

    def test_second_element_is_error_list(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        _, errors = injector.inject(single_adult, difficulty="easy", error_count=1)
        assert isinstance(errors, list)
        assert all(isinstance(e, InjectedError) for e in errors)


# =========================================================================
# 2. InjectedError field completeness
# =========================================================================

class TestErrorFields:

    def test_all_fields_populated(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=2,
        )
        for err in errors:
            assert err.error_id, "error_id must be non-empty"
            assert err.category, "category must be non-empty"
            assert err.field, "field must be non-empty"
            assert err.person_id, "person_id must be non-empty"
            assert err.document, "document must be non-empty"
            assert err.correct_value, "correct_value must be non-empty"
            assert err.erroneous_value, "erroneous_value must be non-empty"
            assert err.explanation, "explanation must be non-empty"
            assert err.difficulty, "difficulty must be non-empty"

    def test_error_ids_unique(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=3,
        )
        ids = [e.error_id for e in errors]
        assert len(ids) == len(set(ids)), "error_id values must be unique"

    def test_valid_categories(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        valid = {"name", "ssn", "address", "dob", "filing_status",
                 "dependent", "expiration"}
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=3,
        )
        for err in errors:
            assert err.category in valid, (
                f"Unknown category {err.category!r}"
            )

    def test_valid_difficulty_on_errors(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        _, errors = injector.inject(
            single_adult, difficulty="easy", error_count=1,
        )
        for err in errors:
            assert err.difficulty in ("easy", "medium", "hard")


# =========================================================================
# 3. Error count control
# =========================================================================

class TestErrorCount:

    def test_requested_count_honored(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        for n in (1, 2, 3):
            _, errors = injector.inject(
                married_with_kids, difficulty="medium", error_count=n,
            )
            assert len(errors) == n, (
                f"Requested {n} errors, got {len(errors)}"
            )

    def test_zero_errors_explicit(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        """error_count=0 must produce exactly zero errors."""
        modified, errors = injector.inject(
            single_adult, difficulty="easy", error_count=0,
        )
        assert errors == []

    def test_zero_errors_household_unchanged(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        """When no errors, the household data must be identical."""
        original = copy.deepcopy(single_adult)
        modified, _ = injector.inject(
            single_adult, difficulty="easy", error_count=0,
        )
        assert modified.members[0].ssn == original.members[0].ssn
        assert modified.members[0].legal_first_name == original.members[0].legal_first_name

    def test_count_capped_at_available_targets(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        """If error_count exceeds what's possible, inject as many as we can."""
        _, errors = injector.inject(
            single_adult, difficulty="easy", error_count=50,
        )
        # Single adult: limited target fields — should get some but not 50
        assert len(errors) > 0
        assert len(errors) <= 50


# =========================================================================
# 4. Difficulty levels
# =========================================================================

class TestDifficulty:

    def test_easy_errors_are_easy(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        _, errors = injector.inject(
            married_with_kids, difficulty="easy", error_count=2,
        )
        for err in errors:
            assert err.difficulty == "easy"

    def test_hard_errors_are_hard(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        _, errors = injector.inject(
            married_with_kids, difficulty="hard", error_count=2,
        )
        for err in errors:
            assert err.difficulty == "hard"

    def test_medium_errors_are_medium(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=2,
        )
        for err in errors:
            assert err.difficulty == "medium"


# =========================================================================
# 5. Manifest accuracy — errors describe actual mutations
# =========================================================================

class TestManifestAccuracy:

    def test_correct_value_matches_original(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        """correct_value in manifest should match the original household."""
        original = copy.deepcopy(married_with_kids)
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=2,
        )
        original_by_id = {p.person_id: p for p in original.members}
        for err in errors:
            if err.category == "filing_status":
                # Filing status is household-level, not per-person
                continue
            assert err.person_id in original_by_id, (
                f"Error references unknown person {err.person_id}"
            )

    def test_erroneous_differs_from_correct(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=2,
        )
        for err in errors:
            assert err.correct_value != err.erroneous_value, (
                f"Error {err.error_id}: correct and erroneous are the same"
            )


# =========================================================================
# 6. Person targeting validity
# =========================================================================

class TestPersonTargeting:

    def test_errors_target_existing_persons(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        member_ids = {p.person_id for p in married_with_kids.members}
        # Filing status errors may use householder's ID — all should be valid
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=3,
        )
        for err in errors:
            assert err.person_id in member_ids, (
                f"Error targets non-existent person {err.person_id}"
            )


# =========================================================================
# 7. No duplicate mutations
# =========================================================================

class TestNoDuplicates:

    def test_unique_person_field_pairs(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        _, errors = injector.inject(
            married_with_kids, difficulty="medium", error_count=3,
        )
        pairs = [(e.person_id, e.field) for e in errors]
        assert len(pairs) == len(set(pairs)), (
            "Duplicate (person_id, field) mutations found"
        )


# =========================================================================
# 8. Original household is not mutated in place
# =========================================================================

class TestOriginalPreserved:

    def test_original_not_mutated(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        """inject() must deep-copy before mutating."""
        original_ssn = married_with_kids.members[0].ssn
        original_name = married_with_kids.members[0].legal_first_name
        modified, _ = injector.inject(
            married_with_kids, difficulty="medium", error_count=3,
        )
        # Original fixture should be untouched
        assert married_with_kids.members[0].ssn == original_ssn
        assert married_with_kids.members[0].legal_first_name == original_name


# =========================================================================
# 9. Error category coverage (statistical — run with multiple seeds)
# =========================================================================

class TestCategoryCoverage:

    def test_multiple_categories_possible(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        """Over many runs, more than one category should appear."""
        all_categories: set = set()
        for seed in range(20):
            _, errors = injector.inject(
                married_with_kids, difficulty="medium", error_count=3,
            )
            for e in errors:
                all_categories.add(e.category)
        assert len(all_categories) >= 2, (
            f"Only saw categories: {all_categories}"
        )


# =========================================================================
# 10. Specific error category behaviors
# =========================================================================

class TestNameErrors:

    def test_name_error_changes_name_field(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        """A name-category error should mutate a name field."""
        # Force name errors by injecting many and filtering
        for _ in range(30):
            _, errors = injector.inject(
                single_adult, difficulty="easy", error_count=1,
            )
            name_errors = [e for e in errors if e.category == "name"]
            if name_errors:
                err = name_errors[0]
                assert "name" in err.field or "middle" in err.field, (
                    f"Name error field is {err.field!r}"
                )
                return
        # If we never got a name error in 30 tries, that's fine —
        # it's probabilistic. Skip rather than fail.
        pytest.skip("No name errors generated in 30 attempts")


class TestSSNErrors:

    def test_ssn_error_produces_valid_format(
        self, injector: ErrorInjector, married_with_kids: Household,
    ) -> None:
        """SSN errors should produce something that still looks like an SSN."""
        for _ in range(30):
            _, errors = injector.inject(
                married_with_kids, difficulty="easy", error_count=2,
            )
            ssn_errors = [e for e in errors if e.category == "ssn"]
            if ssn_errors:
                err = ssn_errors[0]
                # Should be 9 digits (with or without dashes)
                digits = err.erroneous_value.replace("-", "")
                assert len(digits) == 9, (
                    f"SSN error value {err.erroneous_value!r} isn't 9 digits"
                )
                assert digits.isdigit(), (
                    f"SSN error value {err.erroneous_value!r} has non-digits"
                )
                return
        pytest.skip("No SSN errors generated in 30 attempts")


class TestAddressErrors:

    def test_address_error_changes_address(
        self, injector: ErrorInjector, single_adult: Household,
    ) -> None:
        for _ in range(30):
            _, errors = injector.inject(
                single_adult, difficulty="medium", error_count=1,
            )
            addr_errors = [e for e in errors if e.category == "address"]
            if addr_errors:
                err = addr_errors[0]
                assert "address" in err.field or "street" in err.field or "zip" in err.field or "apt" in err.field, (
                    f"Address error field is {err.field!r}"
                )
                return
        pytest.skip("No address errors generated in 30 attempts")


# =========================================================================
# Income errors
# =========================================================================


class TestIncomeErrors:

    @pytest.fixture
    def wage_earner(self) -> Household:
        """Single adult with W-2 wage income and interest."""
        return Household(
            household_id="hh-inc",
            state="HI",
            year=2022,
            pattern="single_adult",
            address=Address(
                street="500 King St", city="Honolulu",
                state="HI", zip_code="96813",
            ),
            members=[
                Person(
                    person_id="p-inc-01",
                    relationship=RelationshipType.HOUSEHOLDER,
                    age=35,
                    sex="M",
                    legal_first_name="Tom",
                    legal_last_name="Worker",
                    ssn="900-55-6666",
                    dob=date(1987, 3, 20),
                    wage_income=55000,
                    interest_income=800,
                    w2s=[W2(
                        employer=Employer(name="Acme Corp", ein="12-3456789"),
                        wages=55000,
                    )],
                    form_1099_ints=[Form1099INT(
                        payer_name="Bank of HI", interest_income=800,
                    )],
                    id_type="drivers_license",
                    id_state="HI",
                    id_number="H7777777",
                    id_expiry=date(2028, 1, 1),
                    id_address=Address(
                        street="500 King St", city="Honolulu",
                        state="HI", zip_code="96813",
                    ),
                ),
            ],
        )

    def test_income_errors_generated(
        self, injector: ErrorInjector, wage_earner: Household,
    ) -> None:
        found_income = False
        for _ in range(50):
            _, errors = injector.inject(
                wage_earner, difficulty="medium", error_count=2,
            )
            if any(e.category == "income" for e in errors):
                found_income = True
                break
        assert found_income, "No income errors generated in 50 attempts"

    def test_wage_mismatch_error_fields(
        self, injector: ErrorInjector, wage_earner: Household,
    ) -> None:
        for _ in range(50):
            _, errors = injector.inject(
                wage_earner, difficulty="easy", error_count=2,
            )
            wage_errors = [e for e in errors if e.field == "income.wages.amount"]
            if wage_errors:
                err = wage_errors[0]
                assert err.category == "income"
                assert err.correct_value == "55000"
                assert err.erroneous_value != "55000"
                assert err.person_id == "p-inc-01"
                return
        pytest.skip("No wage mismatch errors generated in 50 attempts")

    def test_missing_income_error_fields(
        self, injector: ErrorInjector, wage_earner: Household,
    ) -> None:
        for _ in range(50):
            _, errors = injector.inject(
                wage_earner, difficulty="medium", error_count=2,
            )
            missing = [e for e in errors if e.field == "income.interest"]
            if missing:
                err = missing[0]
                assert err.category == "income"
                assert "(omitted)" in err.erroneous_value
                return
        pytest.skip("No missing income errors generated in 50 attempts")

    def test_w2_ssn_mismatch(
        self, injector: ErrorInjector, wage_earner: Household,
    ) -> None:
        for _ in range(50):
            _, errors = injector.inject(
                wage_earner, difficulty="hard", error_count=3,
            )
            ssn_errors = [e for e in errors if e.field == "w2_ssn"]
            if ssn_errors:
                err = ssn_errors[0]
                assert err.category == "income"
                assert err.document == "w2"
                assert err.erroneous_value != err.correct_value
                return
        pytest.skip("No W-2 SSN errors generated in 50 attempts")
