"""TDD tests for the grader — Sprint 6 Step 5.

These tests define the *contract* the Grader must satisfy.
Written before the implementation (red phase).

Contract summary
----------------
Grader.grade_encounter(submission: Dict, ground_truth: dict)
  → GradingResult

  - submission is a dict of {field_name: student_value} matching form_fields.py
  - ground_truth is the GroundTruth dict (must contain 'form_answers' key).
  - Compares field-by-field. Correct iff student value matches ground truth.
  - GradingResult.score = number of correct fields
  - GradingResult.max_score = total graded fields
  - GradingResult.accuracy = score / max_score (0.0 if max_score is 0)
  - field_feedback has one entry per graded field

Grader.grade_verification(flagged_errors: List[Dict],
                          actual_errors: List[InjectedError])
  → GradingResult

  - flagged_errors is a list of dicts the student submitted, each with
    at least {"field": ..., "description": ...}
  - actual_errors is the InjectedError manifest from ErrorInjector.
  - Matching: a flagged error matches an actual error if it identifies
    the same field.
  - correct_flags: matched
  - missed_flags: actual errors not flagged
  - false_flags: student flags that don't match any actual error
  - score = len(correct_flags)
  - max_score = len(actual_errors)
  - accuracy = score / max_score (0.0 if max_score is 0)
"""

from datetime import date
from typing import Dict, List

import pytest

from generator.models import (
    Address,
    GradingResult,
    Household,
    InjectedError,
    Person,
    RelationshipType,
)
from training.form_fields import (
    CLAIMED_AS_DEPENDENT,
    DEP_DISABLED,
    DEP_DOB,
    DEP_NAME,
    DEP_MONTHS,
    DEP_RELATIONSHIP,
    DEP_STUDENT,
    DEP_US_CITIZEN,
    DEDUCTION_TYPE_ITEMIZED,
    DEDUCTION_TYPE_STANDARD,
    EXPENSE_CHARITABLE,
    EXPENSE_CHARITABLE_AMOUNT,
    EXPENSE_CHILD_CARE,
    EXPENSE_CHILD_CARE_AMOUNT,
    EXPENSE_DEDUCTION_TYPE,
    EXPENSE_EDUCATION,
    EXPENSE_EDUCATION_AMOUNT,
    EXPENSE_EDUCATOR,
    EXPENSE_EDUCATOR_AMOUNT,
    EXPENSE_IRA,
    EXPENSE_IRA_AMOUNT,
    EXPENSE_MEDICAL,
    EXPENSE_MORTGAGE_INTEREST,
    EXPENSE_MORTGAGE_INTEREST_AMOUNT,
    EXPENSE_PROPERTY_TAXES,
    EXPENSE_PROPERTY_TAXES_AMOUNT,
    EXPENSE_STUDENT_LOAN,
    EXPENSE_STUDENT_LOAN_AMOUNT,
    FILING_STATUS,
    INCOME_DIVIDENDS,
    INCOME_DIVIDENDS_AMOUNT,
    INCOME_INTEREST,
    INCOME_INTEREST_AMOUNT,
    INCOME_RETIREMENT,
    INCOME_SELF_EMPLOYMENT,
    INCOME_INTEREST_DIVIDENDS,
    INCOME_OTHER,
    INCOME_SOCIAL_SECURITY,
    INCOME_SS,
    INCOME_TOTAL,
    INCOME_WAGES,
    INCOME_WAGES_AMOUNT,
    EXPENSE_TAXES_NEW,
    VOL_EXPENSE_1098,
    VOL_EXPENSE_1098E,
    VOL_EXPENSE_CHILD_CARE_CREDIT,
    VOL_EXPENSE_EDUCATOR,
    VOL_EXPENSE_IRA,
    VOL_EXPENSE_ITEMIZED_DEDUCTION,
    VOL_EXPENSE_STANDARD_DEDUCTION,
    VOL_INCOME_1099DIV,
    VOL_INCOME_1099INT,
    VOL_INCOME_1099INT_COUNT,
    VOL_INCOME_1099NEC,
    VOL_INCOME_1099R,
    VOL_INCOME_SCHEDULE_C,
    VOL_INCOME_SSA,
    VOL_INCOME_W2,
    VOL_INCOME_W2_COUNT,
    NOT_CLAIMED_AS_DEPENDENT,
    ADDR_CITY,
    ADDR_STATE,
    ADDR_STREET,
    ADDR_ZIP,
    PART3_FIELDS,
    SPOUSE_DOB,
    SPOUSE_FIRST_NAME,
    SPOUSE_LAST_NAME,
    SPOUSE_MIDDLE_INITIAL,
    SPOUSE_SSN,
    YOU_DOB,
    YOU_FIRST_NAME,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_SSN,
    YOU_US_CITIZEN,
    dep_field,
)
from training.form_populator import build_field_values
from training.grader import Grader, build_form_answers


def _all_checkbox_nos() -> Dict[str, str]:
    """All income and expense checkbox fields set to 'No'.

    Covers both the legacy Part II / Part III namespace and the new
    Page 2 namespace populated by the grader's _build_income_key.
    """
    return {
        INCOME_WAGES: "No",
        INCOME_INTEREST: "No",
        INCOME_DIVIDENDS: "No",
        INCOME_SOCIAL_SECURITY: "No",
        INCOME_RETIREMENT: "No",
        INCOME_SELF_EMPLOYMENT: "No",
        # New Page 2 namespace defaults (negative answers when no
        # corresponding household income exists).
        INCOME_SS: "No",
        INCOME_INTEREST_DIVIDENDS: "No",
        INCOME_OTHER: "No",
        VOL_INCOME_W2: "No",
        VOL_INCOME_1099R: "No",
        VOL_INCOME_SSA: "No",
        VOL_INCOME_1099INT: "No",
        VOL_INCOME_1099DIV: "No",
        VOL_INCOME_SCHEDULE_C: "No",
        VOL_INCOME_1099NEC: "No",
        EXPENSE_MORTGAGE_INTEREST: "No",
        EXPENSE_PROPERTY_TAXES: "No",
        EXPENSE_MEDICAL: "No",
        EXPENSE_CHARITABLE: "No",
        EXPENSE_STUDENT_LOAN: "No",
        EXPENSE_EDUCATOR: "No",
        EXPENSE_IRA: "No",
        EXPENSE_CHILD_CARE: "No",
        EXPENSE_EDUCATION: "No",
        # Page 3 new namespace defaults — written by the grader's
        # extended _build_expense_key. Standard deduction defaults
        # to "Yes" since the legacy household model defaults
        # uses_standard_deduction=True.
        EXPENSE_TAXES_NEW: "No",
        VOL_EXPENSE_1098: "No",
        VOL_EXPENSE_1098E: "No",
        VOL_EXPENSE_CHILD_CARE_CREDIT: "No",
        VOL_EXPENSE_EDUCATOR: "No",
        VOL_EXPENSE_IRA: "No",
        VOL_EXPENSE_STANDARD_DEDUCTION: "Yes",
        VOL_EXPENSE_ITEMIZED_DEDUCTION: "No",
    }


def _gt_dict(household: Household) -> dict:
    """Build a minimal ground_truth dict from a Household for testing."""
    return {"form_answers": build_form_answers(household), "schema_version": 1}


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def grader() -> Grader:
    return Grader()


@pytest.fixture
def single_household() -> Household:
    return Household(
        household_id="hh-g1",
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
                legal_middle_name="Ann",
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
            ),
        ],
    )


@pytest.fixture
def married_household() -> Household:
    return Household(
        household_id="hh-g2",
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
                legal_middle_name="Robert",
                legal_last_name="Smith",
                ssn="900-11-1111",
                dob=date(1982, 3, 10),
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
            ),
            Person(
                person_id="p-12",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=10,
                sex="M",
                legal_first_name="Jake",
                legal_last_name="Smith",
                ssn="900-33-3333",
                dob=date(2012, 1, 5),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
            ),
        ],
    )


def _perfect_single_submission() -> Dict[str, str]:
    """A submission that perfectly matches single_household."""
    return {
        **_all_checkbox_nos(),
        YOU_FIRST_NAME: "Jane",
        YOU_MIDDLE_INITIAL: "A",
        YOU_LAST_NAME: "Doe",
        YOU_DOB: "05/15/1992",
        YOU_SSN: "900-12-3456",
        YOU_US_CITIZEN: "Yes",
        ADDR_STREET: "100 Main St",
        ADDR_CITY: "Honolulu",
        ADDR_STATE: "HI",
        ADDR_ZIP: "96816",
        FILING_STATUS: "single",
        NOT_CLAIMED_AS_DEPENDENT: "Yes",
        EXPENSE_DEDUCTION_TYPE: DEDUCTION_TYPE_STANDARD,
    }


def _perfect_married_submission() -> Dict[str, str]:
    """A submission that perfectly matches married_household."""
    return {
        **_all_checkbox_nos(),
        YOU_FIRST_NAME: "John",
        YOU_MIDDLE_INITIAL: "R",
        YOU_LAST_NAME: "Smith",
        YOU_DOB: "03/10/1982",
        YOU_SSN: "900-11-1111",
        YOU_US_CITIZEN: "Yes",
        ADDR_STREET: "200 Palm Dr",
        ADDR_CITY: "Kailua",
        ADDR_STATE: "HI",
        ADDR_ZIP: "96734",
        SPOUSE_FIRST_NAME: "Mary",
        SPOUSE_MIDDLE_INITIAL: "L",
        SPOUSE_LAST_NAME: "Smith",
        SPOUSE_DOB: "07/22/1984",
        SPOUSE_SSN: "900-22-2222",
        FILING_STATUS: "married_filing_jointly",
        NOT_CLAIMED_AS_DEPENDENT: "Yes",
        dep_field(0, DEP_NAME): "Jake Smith",
        dep_field(0, DEP_DOB): "01/05/2012",
        dep_field(0, DEP_RELATIONSHIP): "Son/Daughter",
        dep_field(0, DEP_MONTHS): "12",
        dep_field(0, DEP_US_CITIZEN): "Yes",
        dep_field(0, DEP_STUDENT): "No",
        dep_field(0, DEP_DISABLED): "No",
        # Volunteer columns scored in this version. Jake earns no
        # income, lived in the home all year → all three Yes.
        "dep.0.vol_income_under": "Yes",
        "dep.0.vol_support": "Yes",
        "dep.0.vol_home_cost": "Yes",
        EXPENSE_DEDUCTION_TYPE: DEDUCTION_TYPE_STANDARD,
    }


# =========================================================================
# Mode 1: grade_encounter — return type
# =========================================================================

class TestGradeIntakeReturnType:

    def test_returns_grading_result(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_single_submission(), _gt_dict(single_household),
        )
        assert isinstance(result, GradingResult)

    def test_score_is_int(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_single_submission(), _gt_dict(single_household),
        )
        assert isinstance(result.score, int)
        assert isinstance(result.max_score, int)

    def test_accuracy_is_float(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_single_submission(), _gt_dict(single_household),
        )
        assert isinstance(result.accuracy, float)


# =========================================================================
# Mode 1: grade_encounter — perfect submission
# =========================================================================

class TestGradeIntakePerfect:

    def test_perfect_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_single_submission(), _gt_dict(single_household),
        )
        assert result.score == result.max_score
        assert result.score > 0

    def test_perfect_accuracy(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_single_submission(), _gt_dict(single_household),
        )
        assert result.accuracy == 1.0

    def test_no_missed_or_false(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_single_submission(), _gt_dict(single_household),
        )
        assert result.missed_flags == []
        assert result.false_flags == []

    def test_married_perfect_score(
        self, grader: Grader, married_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_married_submission(), _gt_dict(married_household),
        )
        assert result.score == result.max_score
        assert result.accuracy == 1.0


# =========================================================================
# Mode 1: grade_encounter — errors in submission
# =========================================================================

class TestGradeIntakeErrors:

    def test_wrong_name_reduces_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "Janet"  # Wrong
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        assert result.score < result.max_score

    def test_wrong_ssn_reduces_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_SSN] = "900-12-3465"  # Transposed
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        assert result.score < result.max_score

    def test_missing_field_reduces_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_MIDDLE_INITIAL] = ""  # Omitted
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        assert result.score < result.max_score

    def test_all_wrong_gives_zero(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = {k: "WRONG" for k in _perfect_single_submission()}
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        assert result.score == 0
        assert result.accuracy == 0.0

    def test_accuracy_partial(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        assert 0.0 < result.accuracy < 1.0


# =========================================================================
# Mode 1: grade_encounter — field feedback
# =========================================================================

class TestGradeIntakeFieldFeedback:

    def test_feedback_per_field(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter(
            _perfect_single_submission(), _gt_dict(single_household),
        )
        assert len(result.field_feedback) > 0

    def test_feedback_has_field_and_status(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        for fb in result.field_feedback:
            assert "field" in fb
            assert "status" in fb
            assert fb["status"] in ("correct", "incorrect")

    def test_wrong_field_marked_incorrect(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        name_fb = [fb for fb in result.field_feedback if fb["field"] == YOU_FIRST_NAME]
        assert len(name_fb) == 1
        assert name_fb[0]["status"] == "incorrect"

    def test_correct_field_marked_correct(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_encounter(sub, _gt_dict(single_household))
        last_fb = [fb for fb in result.field_feedback if fb["field"] == YOU_LAST_NAME]
        assert len(last_fb) == 1
        assert last_fb[0]["status"] == "correct"


# =========================================================================
# Mode 1: grade_encounter — empty submission
# =========================================================================

class TestGradeIntakeEmpty:

    def test_empty_submission(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_encounter({}, _gt_dict(single_household))
        assert result.score == 0
        assert result.max_score > 0
        assert result.accuracy == 0.0


# =========================================================================
# Mode 2: grade_verification — return type
# =========================================================================

class TestGradeVerificationReturnType:

    def test_returns_grading_result(self, grader: Grader) -> None:
        result = grader.grade_verification([], [])
        assert isinstance(result, GradingResult)


# =========================================================================
# Mode 2: grade_verification — perfect detection
# =========================================================================

class TestGradeVerificationPerfect:

    def test_all_errors_found(self, grader: Grader) -> None:
        actual = [
            InjectedError(
                error_id="err-1", category="name",
                field="filer.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
            InjectedError(
                error_id="err-2", category="ssn",
                field="filer.ssn", person_id="p-01",
                document="intake_form", correct_value="900-12-3456",
                erroneous_value="900-12-3465", explanation="Transposed",
                difficulty="easy",
            ),
        ]
        flagged = [
            {"field": "filer.first_name", "description": "Name is Janet not Jane"},
            {"field": "filer.ssn", "description": "SSN digits transposed"},
        ]
        result = grader.grade_verification(flagged, actual)
        assert result.score == 2
        assert result.max_score == 2
        assert result.accuracy == 1.0
        assert len(result.correct_flags) == 2
        assert result.missed_flags == []
        assert result.false_flags == []


# =========================================================================
# Mode 2: grade_verification — partial detection
# =========================================================================

class TestGradeVerificationPartial:

    def test_one_found_one_missed(self, grader: Grader) -> None:
        actual = [
            InjectedError(
                error_id="err-1", category="name",
                field="filer.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
            InjectedError(
                error_id="err-2", category="ssn",
                field="filer.ssn", person_id="p-01",
                document="intake_form", correct_value="900-12-3456",
                erroneous_value="900-12-3465", explanation="Transposed",
                difficulty="medium",
            ),
        ]
        flagged = [
            {"field": "filer.first_name", "description": "Name wrong"},
        ]
        result = grader.grade_verification(flagged, actual)
        assert result.score == 1
        assert result.max_score == 2
        assert result.accuracy == 0.5
        assert len(result.correct_flags) == 1
        assert len(result.missed_flags) == 1

    def test_missed_flag_contains_error_info(self, grader: Grader) -> None:
        actual = [
            InjectedError(
                error_id="err-1", category="ssn",
                field="filer.ssn", person_id="p-01",
                document="intake_form", correct_value="900-12-3456",
                erroneous_value="900-12-3465", explanation="Transposed",
                difficulty="medium",
            ),
        ]
        result = grader.grade_verification([], actual)
        assert len(result.missed_flags) == 1
        missed = result.missed_flags[0]
        assert "field" in missed


# =========================================================================
# Mode 2: grade_verification — false flags
# =========================================================================

class TestGradeVerificationFalseFlags:

    def test_false_flag_counted(self, grader: Grader) -> None:
        actual: List[InjectedError] = []  # Error-free scenario
        flagged = [
            {"field": "filer.ssn", "description": "I think SSN is wrong"},
        ]
        result = grader.grade_verification(flagged, actual)
        assert result.score == 0
        assert result.max_score == 0
        assert len(result.false_flags) == 1

    def test_mix_correct_and_false(self, grader: Grader) -> None:
        actual = [
            InjectedError(
                error_id="err-1", category="name",
                field="filer.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
        ]
        flagged = [
            {"field": "filer.first_name", "description": "Name wrong"},
            {"field": "filer.dob", "description": "DOB looks off"},  # false
        ]
        result = grader.grade_verification(flagged, actual)
        assert len(result.correct_flags) == 1
        assert len(result.false_flags) == 1


# =========================================================================
# Mode 2: grade_verification — error-free scenario
# =========================================================================

class TestGradeVerificationErrorFree:

    def test_no_errors_no_flags_perfect(self, grader: Grader) -> None:
        """Student correctly flags nothing on a clean scenario."""
        result = grader.grade_verification([], [])
        assert result.score == 0
        assert result.max_score == 0
        # No errors to find, no false flags — accuracy should be 1.0
        # (or 0.0 by convention when max_score=0; either is acceptable)
        assert result.accuracy in (0.0, 1.0)

    def test_no_errors_student_flags_something(self, grader: Grader) -> None:
        """Student incorrectly flags an error on a clean scenario."""
        flagged = [
            {"field": "filer.ssn", "description": "Looks wrong"},
        ]
        result = grader.grade_verification(flagged, [])
        assert len(result.false_flags) == 1


# =========================================================================
# Mode 2: grade_verification — feedback
# =========================================================================

class TestGradeVerificationFeedback:

    def test_feedback_is_string(self, grader: Grader) -> None:
        result = grader.grade_verification([], [])
        assert isinstance(result.feedback, str)

    def test_nonzero_errors_produce_feedback(self, grader: Grader) -> None:
        actual = [
            InjectedError(
                error_id="err-1", category="name",
                field="filer.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
        ]
        result = grader.grade_verification([], actual)
        # Should have some feedback about the missed error
        assert len(result.feedback) > 0


# =========================================================================
# Mode 1: grade_encounter — income fields
# =========================================================================


class TestGradeIntakeIncome:

    @pytest.fixture
    def income_household(self) -> Household:
        return Household(
            household_id="hh-g-inc",
            state="HI",
            year=2022,
            pattern="single_adult",
            address=Address(
                street="100 Main St", city="Honolulu",
                state="HI", zip_code="96816",
            ),
            members=[
                Person(
                    person_id="p-inc",
                    relationship=RelationshipType.HOUSEHOLDER,
                    age=35,
                    sex="M",
                    legal_first_name="Tom",
                    legal_middle_name="A",
                    legal_last_name="Worker",
                    ssn="900-77-8888",
                    dob=date(1987, 6, 1),
                    wage_income=55000,
                    interest_income=800,
                ),
            ],
        )

    def test_income_fields_in_answer_key(
        self, grader: Grader, income_household: Household,
    ) -> None:
        sub = {
            **_all_checkbox_nos(),
            YOU_FIRST_NAME: "Tom",
            YOU_MIDDLE_INITIAL: "A",
            YOU_LAST_NAME: "Worker",
            YOU_DOB: "06/01/1987",
            YOU_SSN: "900-77-8888",
            YOU_US_CITIZEN: "Yes",
            ADDR_STREET: "100 Main St",
            ADDR_CITY: "Honolulu",
            ADDR_STATE: "HI",
            ADDR_ZIP: "96816",
            FILING_STATUS: "single",
            NOT_CLAIMED_AS_DEPENDENT: "Yes",
            INCOME_WAGES: "Yes",
            INCOME_WAGES_AMOUNT: "55000",
            INCOME_INTEREST: "Yes",
            INCOME_INTEREST_AMOUNT: "800",
            INCOME_TOTAL: "55800",
            # New Page 2 namespace overrides — Tom has wages and
            # interest, so the W-2 / 1099-INT volunteer rows expect
            # "Yes" plus document counts; interest_dividends is the
            # combined client checkbox.
            VOL_INCOME_W2: "Yes",
            VOL_INCOME_W2_COUNT: "0",
            INCOME_INTEREST_DIVIDENDS: "Yes",
            VOL_INCOME_1099INT: "Yes",
            VOL_INCOME_1099INT_COUNT: "0",
            EXPENSE_DEDUCTION_TYPE: DEDUCTION_TYPE_STANDARD,
        }
        result = grader.grade_encounter(sub, _gt_dict(income_household))
        assert result.accuracy == 1.0

    def test_wrong_wage_amount_reduces_score(
        self, grader: Grader, income_household: Household,
    ) -> None:
        sub = {
            YOU_FIRST_NAME: "Tom",
            YOU_MIDDLE_INITIAL: "A",
            YOU_LAST_NAME: "Worker",
            YOU_DOB: "06/01/1987",
            YOU_SSN: "900-77-8888",
            ADDR_STREET: "100 Main St",
            ADDR_CITY: "Honolulu",
            ADDR_STATE: "HI",
            ADDR_ZIP: "96816",
            FILING_STATUS: "single",
            INCOME_WAGES: "Yes",
            INCOME_WAGES_AMOUNT: "56000",
            INCOME_INTEREST: "Yes",
            INCOME_INTEREST_AMOUNT: "800",
            INCOME_TOTAL: "56800",
        }
        result = grader.grade_encounter(sub, _gt_dict(income_household))
        assert result.score < result.max_score

    def test_missing_income_source_reduces_score(
        self, grader: Grader, income_household: Household,
    ) -> None:
        sub = {
            YOU_FIRST_NAME: "Tom",
            YOU_MIDDLE_INITIAL: "A",
            YOU_LAST_NAME: "Worker",
            YOU_DOB: "06/01/1987",
            YOU_SSN: "900-77-8888",
            ADDR_STREET: "100 Main St",
            ADDR_CITY: "Honolulu",
            ADDR_STATE: "HI",
            ADDR_ZIP: "96816",
            FILING_STATUS: "single",
            INCOME_WAGES: "Yes",
            INCOME_WAGES_AMOUNT: "55000",
            # Missing interest entirely
            INCOME_TOTAL: "55000",
        }
        result = grader.grade_encounter(sub, _gt_dict(income_household))
        assert result.score < result.max_score

    def test_numeric_tolerance(
        self, grader: Grader, income_household: Household,
    ) -> None:
        sub = {
            **_all_checkbox_nos(),
            YOU_FIRST_NAME: "Tom",
            YOU_MIDDLE_INITIAL: "A",
            YOU_LAST_NAME: "Worker",
            YOU_DOB: "06/01/1987",
            YOU_SSN: "900-77-8888",
            YOU_US_CITIZEN: "Yes",
            ADDR_STREET: "100 Main St",
            ADDR_CITY: "Honolulu",
            ADDR_STATE: "HI",
            ADDR_ZIP: "96816",
            FILING_STATUS: "single",
            NOT_CLAIMED_AS_DEPENDENT: "Yes",
            INCOME_WAGES: "Yes",
            INCOME_WAGES_AMOUNT: "$55,000",
            INCOME_INTEREST: "Yes",
            INCOME_INTEREST_AMOUNT: "800",
            INCOME_TOTAL: "55800",
            VOL_INCOME_W2: "Yes",
            INCOME_INTEREST_DIVIDENDS: "Yes",
            VOL_INCOME_1099INT: "Yes",
            EXPENSE_DEDUCTION_TYPE: DEDUCTION_TYPE_STANDARD,
        }
        result = grader.grade_encounter(sub, _gt_dict(income_household))
        assert result.accuracy == 1.0


# =========================================================================
# Mode 1: grade_encounter — expense fields (Part III)
# =========================================================================

class TestGradeExpenses:
    """Test grading of Part III expense fields."""

    @pytest.fixture
    def expense_household(self) -> Household:
        """Household with mortgage, charitable, and student loan expenses."""
        p = Person(
            person_id="p-exp-1",
            relationship=RelationshipType.HOUSEHOLDER,
            age=40, sex="M", race="white",
            legal_first_name="Alex",
            legal_middle_name="J",
            legal_last_name="Builder",
            ssn="900-44-5555",
            dob=date(1982, 3, 20),
            wage_income=85000,
            student_loan_interest=1200,
        )
        hh = Household(
            household_id="hh-exp",
            state="HI", year=2022,
            pattern="single_adult",
            address=Address(
                street="50 Oak Rd", city="Honolulu",
                state="HI", zip_code="96816",
            ),
            members=[p],
            mortgage_interest=9000,
            property_taxes=3500,
            charitable_contributions=2000,
            uses_standard_deduction=False,
        )
        return hh

    def test_perfect_expense_score(
        self, grader: Grader, expense_household: Household,
    ) -> None:
        # Build the perfect submission off the populator so the new
        # Page 3 namespace defaults (vol.expense.*, expense.taxes)
        # come along for free.
        sub = build_field_values(expense_household)
        result = grader.grade_encounter(sub, _gt_dict(expense_household), fields=PART3_FIELDS)
        assert result.accuracy == 1.0

    def test_wrong_deduction_type(
        self, grader: Grader, expense_household: Household,
    ) -> None:
        sub = {
            EXPENSE_MORTGAGE_INTEREST: "Yes",
            EXPENSE_MORTGAGE_INTEREST_AMOUNT: "9000",
            EXPENSE_PROPERTY_TAXES: "Yes",
            EXPENSE_PROPERTY_TAXES_AMOUNT: "3500",
            EXPENSE_CHARITABLE: "Yes",
            EXPENSE_CHARITABLE_AMOUNT: "2000",
            EXPENSE_STUDENT_LOAN: "Yes",
            EXPENSE_STUDENT_LOAN_AMOUNT: "1200",
            EXPENSE_DEDUCTION_TYPE: DEDUCTION_TYPE_STANDARD,
        }
        result = grader.grade_encounter(sub, _gt_dict(expense_household), fields=PART3_FIELDS)
        assert result.accuracy < 1.0
        wrong = {fb["field"] for fb in result.field_feedback if fb["status"] == "incorrect"}
        assert EXPENSE_DEDUCTION_TYPE in wrong

    def test_standard_deduction_correct(self, grader: Grader) -> None:
        hh = Household(
            household_id="hh-std",
            state="HI", year=2022,
            pattern="single_adult",
            address=Address(
                street="1 Elm St", city="Honolulu",
                state="HI", zip_code="96815",
            ),
            members=[Person(
                person_id="p-std",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30, sex="F", race="white",
                legal_first_name="Pat",
                legal_last_name="Simple",
                ssn="900-66-7777",
                dob=date(1992, 1, 1),
            )],
            uses_standard_deduction=True,
        )
        sub = build_field_values(hh)
        result = grader.grade_encounter(sub, _gt_dict(hh), fields=PART3_FIELDS)
        assert result.accuracy == 1.0

    def test_missing_expense_reduces_score(
        self, grader: Grader, expense_household: Household,
    ) -> None:
        sub = {
            EXPENSE_DEDUCTION_TYPE: DEDUCTION_TYPE_ITEMIZED,
        }
        result = grader.grade_encounter(sub, _gt_dict(expense_household), fields=PART3_FIELDS)
        assert result.score < result.max_score
        wrong_fields = {fb["field"] for fb in result.field_feedback if fb["status"] == "incorrect"}
        assert EXPENSE_MORTGAGE_INTEREST in wrong_fields

    def test_expense_amount_tolerance(
        self, grader: Grader, expense_household: Household,
    ) -> None:
        # Override the legacy amount fields with $-formatted values to
        # exercise the grader's numeric-tolerance normalization.
        sub = build_field_values(expense_household)
        sub.update({
            EXPENSE_MORTGAGE_INTEREST_AMOUNT: "$9,000",
            EXPENSE_PROPERTY_TAXES_AMOUNT: "$3,500",
            EXPENSE_CHARITABLE_AMOUNT: "$2,000",
            EXPENSE_STUDENT_LOAN_AMOUNT: "$1,200",
        })
        result = grader.grade_encounter(sub, _gt_dict(expense_household), fields=PART3_FIELDS)
        assert result.accuracy == 1.0

    def test_above_line_deductions_graded(self, grader: Grader) -> None:
        p = Person(
            person_id="p-abl",
            relationship=RelationshipType.HOUSEHOLDER,
            age=35, sex="F", race="white",
            legal_first_name="Edu",
            legal_last_name="Cator",
            ssn="900-88-9999",
            dob=date(1987, 7, 7),
            educator_expenses=250,
            ira_contributions=3000,
        )
        hh = Household(
            household_id="hh-abl",
            state="HI", year=2022,
            pattern="single_adult",
            address=Address(
                street="2 School Ln", city="Kailua",
                state="HI", zip_code="96734",
            ),
            members=[p],
            uses_standard_deduction=True,
        )
        sub = build_field_values(hh)
        result = grader.grade_encounter(sub, _gt_dict(hh), fields=PART3_FIELDS)
        assert result.accuracy == 1.0

    def test_credit_expenses_graded(self, grader: Grader) -> None:
        hh = Household(
            household_id="hh-cr",
            state="HI", year=2022,
            pattern="single_parent",
            address=Address(
                street="3 Care Way", city="Honolulu",
                state="HI", zip_code="96815",
            ),
            members=[Person(
                person_id="p-cr",
                relationship=RelationshipType.HOUSEHOLDER,
                age=32, sex="F", race="white",
                legal_first_name="Care",
                legal_last_name="Giver",
                ssn="900-11-3333",
                dob=date(1990, 4, 4),
            )],
            child_care_expenses=5000,
            education_expenses=8000,
            uses_standard_deduction=True,
        )
        sub = build_field_values(hh)
        result = grader.grade_encounter(sub, _gt_dict(hh), fields=PART3_FIELDS)
        assert result.accuracy == 1.0

    def test_empty_expense_submission_scores_zero(
        self, grader: Grader, expense_household: Household,
    ) -> None:
        result = grader.grade_encounter({}, _gt_dict(expense_household), fields=PART3_FIELDS)
        assert result.score == 0
        assert result.accuracy == 0.0


# =========================================================================
# Mode 1: grade_encounter — ground_truth validation
# =========================================================================

class TestGradeIntakeGroundTruthValidation:

    def test_none_ground_truth_raises(self, grader: Grader) -> None:
        with pytest.raises(ValueError, match="no ground_truth"):
            grader.grade_encounter({"filer.first_name": "Jane"}, None)

    def test_missing_form_answers_grades_zero(self, grader: Grader) -> None:
        gt = {"schema_version": 1}
        result = grader.grade_encounter({"filer.first_name": "Jane"}, gt)
        assert result.max_score == 0
