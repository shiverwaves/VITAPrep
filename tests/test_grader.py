"""TDD tests for the grader — Sprint 6 Step 5.

These tests define the *contract* the Grader must satisfy.
Written before the implementation (red phase).

Contract summary
----------------
Grader.grade_intake(submission: Dict, ground_truth: Household)
  → GradingResult

  - submission is a dict of {field_name: student_value} matching form_fields.py
  - Ground truth is the original Household (before error injection).
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
    YOU_FIRST_NAME,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_DOB,
    YOU_SSN,
    ADDR_STREET,
    ADDR_CITY,
    ADDR_STATE,
    ADDR_ZIP,
    SPOUSE_FIRST_NAME,
    SPOUSE_MIDDLE_INITIAL,
    SPOUSE_LAST_NAME,
    SPOUSE_DOB,
    SPOUSE_SSN,
    FILING_STATUS,
    dep_field,
    DEP_FIRST_NAME,
    DEP_LAST_NAME,
    DEP_DOB,
    DEP_RELATIONSHIP,
    DEP_MONTHS,
)
from training.grader import Grader


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
        YOU_FIRST_NAME: "Jane",
        YOU_MIDDLE_INITIAL: "A",
        YOU_LAST_NAME: "Doe",
        YOU_DOB: "05/15/1992",
        YOU_SSN: "900-12-3456",
        ADDR_STREET: "100 Main St",
        ADDR_CITY: "Honolulu",
        ADDR_STATE: "HI",
        ADDR_ZIP: "96816",
        FILING_STATUS: "single",
    }


def _perfect_married_submission() -> Dict[str, str]:
    """A submission that perfectly matches married_household."""
    return {
        YOU_FIRST_NAME: "John",
        YOU_MIDDLE_INITIAL: "R",
        YOU_LAST_NAME: "Smith",
        YOU_DOB: "03/10/1982",
        YOU_SSN: "900-11-1111",
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
        dep_field(0, DEP_FIRST_NAME): "Jake",
        dep_field(0, DEP_LAST_NAME): "Smith",
        dep_field(0, DEP_DOB): "01/05/2012",
        dep_field(0, DEP_RELATIONSHIP): "biological_child",
        dep_field(0, DEP_MONTHS): "12",
    }


# =========================================================================
# Mode 1: grade_intake — return type
# =========================================================================

class TestGradeIntakeReturnType:

    def test_returns_grading_result(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_single_submission(), single_household,
        )
        assert isinstance(result, GradingResult)

    def test_score_is_int(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_single_submission(), single_household,
        )
        assert isinstance(result.score, int)
        assert isinstance(result.max_score, int)

    def test_accuracy_is_float(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_single_submission(), single_household,
        )
        assert isinstance(result.accuracy, float)


# =========================================================================
# Mode 1: grade_intake — perfect submission
# =========================================================================

class TestGradeIntakePerfect:

    def test_perfect_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_single_submission(), single_household,
        )
        assert result.score == result.max_score
        assert result.score > 0

    def test_perfect_accuracy(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_single_submission(), single_household,
        )
        assert result.accuracy == 1.0

    def test_no_missed_or_false(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_single_submission(), single_household,
        )
        assert result.missed_flags == []
        assert result.false_flags == []

    def test_married_perfect_score(
        self, grader: Grader, married_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_married_submission(), married_household,
        )
        assert result.score == result.max_score
        assert result.accuracy == 1.0


# =========================================================================
# Mode 1: grade_intake — errors in submission
# =========================================================================

class TestGradeIntakeErrors:

    def test_wrong_name_reduces_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "Janet"  # Wrong
        result = grader.grade_intake(sub, single_household)
        assert result.score < result.max_score

    def test_wrong_ssn_reduces_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_SSN] = "900-12-3465"  # Transposed
        result = grader.grade_intake(sub, single_household)
        assert result.score < result.max_score

    def test_missing_field_reduces_score(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_MIDDLE_INITIAL] = ""  # Omitted
        result = grader.grade_intake(sub, single_household)
        assert result.score < result.max_score

    def test_all_wrong_gives_zero(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = {k: "WRONG" for k in _perfect_single_submission()}
        result = grader.grade_intake(sub, single_household)
        assert result.score == 0
        assert result.accuracy == 0.0

    def test_accuracy_partial(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_intake(sub, single_household)
        assert 0.0 < result.accuracy < 1.0


# =========================================================================
# Mode 1: grade_intake — field feedback
# =========================================================================

class TestGradeIntakeFieldFeedback:

    def test_feedback_per_field(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake(
            _perfect_single_submission(), single_household,
        )
        assert len(result.field_feedback) > 0

    def test_feedback_has_field_and_status(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_intake(sub, single_household)
        for fb in result.field_feedback:
            assert "field" in fb
            assert "status" in fb
            assert fb["status"] in ("correct", "incorrect")

    def test_wrong_field_marked_incorrect(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_intake(sub, single_household)
        name_fb = [fb for fb in result.field_feedback if fb["field"] == YOU_FIRST_NAME]
        assert len(name_fb) == 1
        assert name_fb[0]["status"] == "incorrect"

    def test_correct_field_marked_correct(
        self, grader: Grader, single_household: Household,
    ) -> None:
        sub = _perfect_single_submission()
        sub[YOU_FIRST_NAME] = "WRONG"
        result = grader.grade_intake(sub, single_household)
        last_fb = [fb for fb in result.field_feedback if fb["field"] == YOU_LAST_NAME]
        assert len(last_fb) == 1
        assert last_fb[0]["status"] == "correct"


# =========================================================================
# Mode 1: grade_intake — empty submission
# =========================================================================

class TestGradeIntakeEmpty:

    def test_empty_submission(
        self, grader: Grader, single_household: Household,
    ) -> None:
        result = grader.grade_intake({}, single_household)
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
                field="you.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
            InjectedError(
                error_id="err-2", category="ssn",
                field="you.ssn", person_id="p-01",
                document="intake_form", correct_value="900-12-3456",
                erroneous_value="900-12-3465", explanation="Transposed",
                difficulty="easy",
            ),
        ]
        flagged = [
            {"field": "you.first_name", "description": "Name is Janet not Jane"},
            {"field": "you.ssn", "description": "SSN digits transposed"},
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
                field="you.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
            InjectedError(
                error_id="err-2", category="ssn",
                field="you.ssn", person_id="p-01",
                document="intake_form", correct_value="900-12-3456",
                erroneous_value="900-12-3465", explanation="Transposed",
                difficulty="medium",
            ),
        ]
        flagged = [
            {"field": "you.first_name", "description": "Name wrong"},
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
                field="you.ssn", person_id="p-01",
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
            {"field": "you.ssn", "description": "I think SSN is wrong"},
        ]
        result = grader.grade_verification(flagged, actual)
        assert result.score == 0
        assert result.max_score == 0
        assert len(result.false_flags) == 1

    def test_mix_correct_and_false(self, grader: Grader) -> None:
        actual = [
            InjectedError(
                error_id="err-1", category="name",
                field="you.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
        ]
        flagged = [
            {"field": "you.first_name", "description": "Name wrong"},
            {"field": "you.dob", "description": "DOB looks off"},  # false
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
            {"field": "you.ssn", "description": "Looks wrong"},
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
                field="you.first_name", person_id="p-01",
                document="intake_form", correct_value="Jane",
                erroneous_value="Janet", explanation="Misspelled",
                difficulty="easy",
            ),
        ]
        result = grader.grade_verification([], actual)
        # Should have some feedback about the missed error
        assert len(result.feedback) > 0
