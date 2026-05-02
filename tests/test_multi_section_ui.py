"""Tests for Sprint 10: multi-section encounter UI.

Covers:
- Part II income form renders with correct field names and pre-fill
- Part II submission parses income fields and grades correctly
- Section nav links appear on both form pages
- Landing page shows per-section grade status cards
- Verify mode pre-fills income fields with injected errors
- Part I submission grades only Part I fields (not income)
- Section-aware grade storage and retrieval
"""

from datetime import date

import pytest
from fastapi.testclient import TestClient

from api.main import app
from generator.models import (
    Address,
    Employer,
    Form1099INT,
    Household,
    Person,
    RelationshipType,
    W2,
)
from training.form_fields import (
    EXPENSE_CHARITABLE,
    EXPENSE_DEDUCTION_TYPE,
    EXPENSE_MORTGAGE_INTEREST,
    INCOME_DIVIDENDS,
    INCOME_RETIREMENT,
    INCOME_SELF_EMPLOYMENT,
    INCOME_SOCIAL_SECURITY,
    INCOME_WAGES,
    INCOME_WAGES_AMOUNT,
    INCOME_INTEREST,
    INCOME_INTEREST_AMOUNT,
    INCOME_TOTAL,
    PART1_FIELDS,
    PART2_FIELDS,
    PART3_FIELDS,
    ALL_FIELDS,
)
from training.grader import build_form_answers


def _gt_dict(hh: Household) -> dict:
    """Build a minimal ground_truth dict from a Household for testing."""
    return {"form_answers": build_form_answers(hh), "schema_version": 1}


# =========================================================================
# Helpers
# =========================================================================

def _make_household() -> Household:
    """Single worker with W-2 wages + 1099-INT interest."""
    primary = Person(
        person_id="p-10d-01",
        relationship=RelationshipType.HOUSEHOLDER,
        age=30, sex="F", race="white",
        legal_first_name="Dana",
        legal_middle_name="K",
        legal_last_name="Reyes",
        ssn="900-55-6666",
        dob=date(1994, 6, 10),
        phone="(808) 555-0099",
        email="dana@example.com",
        id_type="drivers_license",
        id_state="HI",
        id_number="H9999999",
        id_expiry=date(2028, 12, 31),
        id_address=Address(
            street="42 Palm Ave", city="Honolulu",
            state="HI", zip_code="96815",
        ),
        employment_status="employed",
        wage_income=45000,
        interest_income=350,
        w2s=[
            W2(
                employer=Employer(
                    name="Island Tech",
                    ein="99-1234567",
                    address=Address(
                        street="100 Tech Blvd", city="Honolulu",
                        state="HI", zip_code="96813",
                    ),
                ),
                wages=45000,
                federal_tax_withheld=5400,
                social_security_wages=45000,
                social_security_tax=2790,
                medicare_wages=45000,
                medicare_tax=652,
                state="HI",
                state_wages=45000,
                state_tax=1800,
            ),
        ],
        form_1099_ints=[
            Form1099INT(
                payer_name="First Hawaiian Bank",
                payer_tin="99-8765432",
                interest_income=350,
            ),
        ],
    )
    return Household(
        household_id="hh-10d-001",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=Address(
            street="42 Palm Ave", city="Honolulu",
            state="HI", zip_code="96815",
        ),
        members=[primary],
    )


def _create_scenario(client, mode="encounter", difficulty="easy"):
    """Create a scenario via the API and return the scenario_id."""
    resp = client.post(
        "/api/v1/scenarios",
        json={"mode": mode, "difficulty": difficulty, "seed": 42},
    )
    assert resp.status_code == 201
    return resp.json()["scenario_id"]


# =========================================================================
# Part II form rendering
# =========================================================================

class TestIncomeFormRender:
    """Test that the Part II income form renders with correct fields."""

    def test_income_form_has_field_names(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/income")
            assert resp.status_code == 200
            html = resp.text
            assert f'name="{INCOME_WAGES}"' in html
            assert f'name="{INCOME_WAGES_AMOUNT}"' in html
            assert f'name="{INCOME_INTEREST}"' in html
            assert f'name="{INCOME_INTEREST_AMOUNT}"' in html
            assert f'name="{INCOME_TOTAL}"' in html

    def test_income_form_has_submit_action(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/income")
            assert f"/submit/income" in resp.text

    def test_income_form_has_section_nav(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/income")
            html = resp.text
            assert "section-nav" in html
            assert "Part I" in html
            assert "Part II" in html

    def test_income_form_part2_active(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/income")
            html = resp.text
            assert '/form/income" class="active"' in html


# =========================================================================
# Part I form rendering
# =========================================================================

class TestIntakeFormNav:
    """Test that the Part I form has section navigation."""

    def test_encounter_form_has_section_nav(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form")
            html = resp.text
            assert "section-nav" in html
            assert "Part I" in html
            assert "Part II" in html

    def test_encounter_form_part1_active(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form")
            html = resp.text
            assert '/form" class="active"' in html


# =========================================================================
# Part II submission and grading
# =========================================================================

class TestIncomeSubmission:
    """Test Part II submission grades only income fields."""

    def test_submit_income_returns_results(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.post(
                f"/scenarios/{sid}/submit/income",
                data={INCOME_WAGES: "Yes", INCOME_WAGES_AMOUNT: "45000"},
            )
            assert resp.status_code == 200
            assert "Grading Results" in resp.text
            assert "Part II" in resp.text

    def test_submit_income_grades_only_income_fields(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.post(
                f"/scenarios/{sid}/submit/income",
                data={INCOME_WAGES: "Yes", INCOME_WAGES_AMOUNT: "45000"},
            )
            html = resp.text
            # Should not contain Part I field names in feedback
            assert "you.first_name" not in html
            assert "addr.street" not in html


# =========================================================================
# Part I submission scoped to Part I
# =========================================================================

class TestIntakeSubmissionScoped:
    """Test Part I submission grades only Part I fields, not income."""

    def test_submit_encounter_excludes_income(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.post(
                f"/scenarios/{sid}/submit",
                data={"you.first_name": "Test", "you.last_name": "User"},
            )
            assert resp.status_code == 200
            html = resp.text
            # Should not contain income field names in feedback
            assert "income.wages" not in html
            assert "income.total" not in html

    def test_submit_encounter_shows_part1_label(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.post(
                f"/scenarios/{sid}/submit",
                data={"you.first_name": "Test"},
            )
            assert "Part I" in resp.text


# =========================================================================
# Landing page per-section grades
# =========================================================================

class TestLandingPageGrades:
    """Test that the landing page shows per-section grade cards."""

    def test_landing_shows_form_cards(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}")
            html = resp.text
            assert "form-card" in html
            assert "Part I" in html
            assert "Part II" in html

    def test_ungraded_shows_pending(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}")
            assert "Not yet submitted" in resp.text

    def test_graded_encounter_shows_score(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            # Submit Part I
            client.post(
                f"/scenarios/{sid}/submit",
                data={"you.first_name": "Test"},
            )
            resp = client.get(f"/scenarios/{sid}")
            html = resp.text
            assert "section-score" in html
            # Part I should show a score, Part II still pending
            assert "Not yet submitted" in html

    def test_all_graded_no_pending(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            # Submit all three sections
            client.post(
                f"/scenarios/{sid}/submit",
                data={"you.first_name": "Test"},
            )
            client.post(
                f"/scenarios/{sid}/submit/income",
                data={INCOME_WAGES: "Yes"},
            )
            client.post(
                f"/scenarios/{sid}/submit/expenses",
                data={EXPENSE_DEDUCTION_TYPE: "standard"},
            )
            resp = client.get(f"/scenarios/{sid}")
            html = resp.text
            # All sections graded, no pending labels
            assert "Not yet submitted" not in html


# =========================================================================
# Verify mode pre-fill
# =========================================================================

class TestVerifyModeIncome:
    """Test verify mode pre-fills income fields."""

    def test_verify_prefills_income_form(self):
        with TestClient(app) as client:
            sid = _create_scenario(client, mode="verify")
            resp = client.get(f"/scenarios/{sid}/form/income")
            html = resp.text
            # Verify mode should have pre-filled values (checked checkboxes
            # or non-empty amount inputs)
            assert "checked" in html or 'value="' in html

    def test_verify_prefills_encounter_form(self):
        with TestClient(app) as client:
            sid = _create_scenario(client, mode="verify")
            resp = client.get(f"/scenarios/{sid}/form")
            html = resp.text
            # Should have pre-filled name values
            assert 'value="' in html


# =========================================================================
# Field list integrity
# =========================================================================

class TestFieldLists:
    """Test that PART1_FIELDS + PART2_FIELDS + PART3_FIELDS == ALL_FIELDS."""

    def test_partition_covers_all(self):
        assert set(PART1_FIELDS + PART2_FIELDS + PART3_FIELDS) == set(ALL_FIELDS)

    def test_no_overlap_p1_p2(self):
        overlap = set(PART1_FIELDS) & set(PART2_FIELDS)
        assert overlap == set()

    def test_no_overlap_p1_p3(self):
        overlap = set(PART1_FIELDS) & set(PART3_FIELDS)
        assert overlap == set()

    def test_no_overlap_p2_p3(self):
        overlap = set(PART2_FIELDS) & set(PART3_FIELDS)
        assert overlap == set()

    def test_part1_has_personal_fields(self):
        assert "you.first_name" in PART1_FIELDS
        assert "you.ssn" in PART1_FIELDS
        assert "filing_status" in PART1_FIELDS

    def test_part2_has_income_fields(self):
        assert INCOME_WAGES in PART2_FIELDS
        assert INCOME_WAGES_AMOUNT in PART2_FIELDS
        assert INCOME_TOTAL in PART2_FIELDS

    def test_part3_has_expense_fields(self):
        assert EXPENSE_MORTGAGE_INTEREST in PART3_FIELDS
        assert EXPENSE_CHARITABLE in PART3_FIELDS
        assert EXPENSE_DEDUCTION_TYPE in PART3_FIELDS

    def test_part1_excludes_income(self):
        assert INCOME_WAGES not in PART1_FIELDS
        assert INCOME_TOTAL not in PART1_FIELDS

    def test_part2_excludes_personal(self):
        assert "you.first_name" not in PART2_FIELDS
        assert "filing_status" not in PART2_FIELDS

    def test_part3_excludes_personal_and_income(self):
        assert "you.first_name" not in PART3_FIELDS
        assert INCOME_WAGES not in PART3_FIELDS


# =========================================================================
# Section-aware grade storage
# =========================================================================

class TestSectionGradeStorage:
    """Test that grades are stored and retrieved per-section."""

    def test_section_grades_separate(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            # Grade all three sections
            client.post(
                f"/scenarios/{sid}/submit",
                data={"you.first_name": "Test"},
            )
            client.post(
                f"/scenarios/{sid}/submit/income",
                data={INCOME_WAGES: "Yes"},
            )
            client.post(
                f"/scenarios/{sid}/submit/expenses",
                data={EXPENSE_DEDUCTION_TYPE: "standard"},
            )
            # Check section grades via landing page
            resp = client.get(f"/scenarios/{sid}")
            html = resp.text
            # All sections should show scores
            assert "Not yet submitted" not in html

    def test_results_page_section_param(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            client.post(
                f"/scenarios/{sid}/submit/income",
                data={INCOME_WAGES: "Yes"},
            )
            resp = client.get(f"/scenarios/{sid}/results?section=income")
            assert resp.status_code == 200
            assert "Part II" in resp.text

    def test_results_page_missing_section_404(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/results?section=income")
            assert resp.status_code == 404


# =========================================================================
# Part III form rendering
# =========================================================================

class TestExpenseFormRender:
    """Test that the Part III expense form renders correctly."""

    def test_expense_form_renders(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/expenses")
            assert resp.status_code == 200

    def test_expense_form_has_field_names(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/expenses")
            html = resp.text
            assert f'name="{EXPENSE_MORTGAGE_INTEREST}"' in html
            assert f'name="{EXPENSE_CHARITABLE}"' in html
            assert f'name="{EXPENSE_DEDUCTION_TYPE}"' in html

    def test_expense_form_has_submit_action(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/expenses")
            assert "/submit/expenses" in resp.text

    def test_expense_form_has_section_nav(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/expenses")
            html = resp.text
            assert "section-nav" in html
            assert "Part I" in html
            assert "Part II" in html
            assert "Part III" in html

    def test_expense_form_part3_active(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/expenses")
            html = resp.text
            assert '/form/expenses" class="active"' in html

    def test_expense_form_has_deduction_radios(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form/expenses")
            html = resp.text
            assert 'value="standard"' in html
            assert 'value="itemized"' in html


# =========================================================================
# Part III submission and grading
# =========================================================================

class TestExpenseSubmission:
    """Test Part III submission grades only expense fields."""

    def test_submit_expenses_returns_results(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.post(
                f"/scenarios/{sid}/submit/expenses",
                data={EXPENSE_DEDUCTION_TYPE: "standard"},
            )
            assert resp.status_code == 200
            assert "Grading Results" in resp.text
            assert "Part III" in resp.text

    def test_submit_expenses_grades_only_expense_fields(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.post(
                f"/scenarios/{sid}/submit/expenses",
                data={EXPENSE_DEDUCTION_TYPE: "standard"},
            )
            html = resp.text
            assert "you.first_name" not in html
            assert "income.wages" not in html

    def test_expense_grade_stored_as_section(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            client.post(
                f"/scenarios/{sid}/submit/expenses",
                data={EXPENSE_DEDUCTION_TYPE: "standard"},
            )
            resp = client.get(f"/scenarios/{sid}/results?section=expenses")
            assert resp.status_code == 200
            assert "Part III" in resp.text


# =========================================================================
# Landing page with all three sections
# =========================================================================

class TestLandingPageAllSections:
    """Test landing page shows all three section cards."""

    def test_landing_shows_part3_card(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}")
            html = resp.text
            assert "Part III" in html

    def test_all_three_graded_no_pending(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            client.post(
                f"/scenarios/{sid}/submit",
                data={"you.first_name": "Test"},
            )
            client.post(
                f"/scenarios/{sid}/submit/income",
                data={INCOME_WAGES: "Yes"},
            )
            client.post(
                f"/scenarios/{sid}/submit/expenses",
                data={EXPENSE_DEDUCTION_TYPE: "standard"},
            )
            resp = client.get(f"/scenarios/{sid}")
            assert "Not yet submitted" not in resp.text

    def test_section_nav_has_part3(self):
        with TestClient(app) as client:
            sid = _create_scenario(client)
            resp = client.get(f"/scenarios/{sid}/form")
            html = resp.text
            assert "Part III" in html


# =========================================================================
# Verify mode Part III
# =========================================================================

class TestVerifyModeExpenses:
    """Test verify mode pre-fills expense fields."""

    def test_verify_prefills_expense_form(self):
        with TestClient(app) as client:
            sid = _create_scenario(client, mode="verify")
            resp = client.get(f"/scenarios/{sid}/form/expenses")
            html = resp.text
            assert "checked" in html or 'value="' in html


# =========================================================================
# Grader fields filter
# =========================================================================

class TestGraderFieldsFilter:
    """Test that the grader respects the fields filter."""

    def test_grade_part1_only(self):
        from training.grader import Grader
        hh = _make_household()
        grader = Grader()

        full_result = grader.grade_encounter({}, _gt_dict(hh))
        part1_result = grader.grade_encounter({}, _gt_dict(hh), fields=PART1_FIELDS)

        # Part 1 result should have fewer fields than full
        assert part1_result.max_score < full_result.max_score
        # No income fields in Part 1 feedback
        p1_fields = {fb["field"] for fb in part1_result.field_feedback}
        assert not any(f.startswith("income.") for f in p1_fields)

    def test_grade_part2_only(self):
        from training.grader import Grader
        hh = _make_household()
        grader = Grader()

        part2_result = grader.grade_encounter({}, _gt_dict(hh), fields=PART2_FIELDS)
        p2_fields = {fb["field"] for fb in part2_result.field_feedback}
        assert all(f.startswith("income.") for f in p2_fields)

    def test_grade_part2_correct_submission(self):
        from training.grader import Grader
        hh = _make_household()
        grader = Grader()

        submission = {
            INCOME_WAGES: "Yes",
            INCOME_WAGES_AMOUNT: "45000",
            INCOME_INTEREST: "Yes",
            INCOME_INTEREST_AMOUNT: "350",
            INCOME_DIVIDENDS: "No",
            INCOME_SOCIAL_SECURITY: "No",
            INCOME_RETIREMENT: "No",
            INCOME_SELF_EMPLOYMENT: "No",
            INCOME_TOTAL: "45350",
        }
        result = grader.grade_encounter(submission, _gt_dict(hh), fields=PART2_FIELDS)
        assert result.accuracy == 1.0

    def test_grade_part3_only(self):
        from training.grader import Grader
        hh = _make_household()
        # Give the household some expenses
        hh.mortgage_interest = 8000
        hh.property_taxes = 3000
        hh.charitable_contributions = 1000
        hh.uses_standard_deduction = True
        grader = Grader()

        part3_result = grader.grade_encounter({}, _gt_dict(hh), fields=PART3_FIELDS)
        p3_fields = {fb["field"] for fb in part3_result.field_feedback}
        assert all(f.startswith("expense.") for f in p3_fields)
        # Should not have personal or income fields
        assert not any(f.startswith("you.") for f in p3_fields)
        assert not any(f.startswith("income.") for f in p3_fields)

    def test_grade_part3_excludes_from_part1(self):
        from training.grader import Grader
        hh = _make_household()
        hh.mortgage_interest = 5000
        hh.uses_standard_deduction = True
        grader = Grader()

        part1_result = grader.grade_encounter({}, _gt_dict(hh), fields=PART1_FIELDS)
        p1_fields = {fb["field"] for fb in part1_result.field_feedback}
        assert not any(f.startswith("expense.") for f in p1_fields)

    def test_grade_part3_deduction_type(self):
        from training.grader import Grader
        hh = _make_household()
        hh.uses_standard_deduction = True
        grader = Grader()

        submission = {EXPENSE_DEDUCTION_TYPE: "standard"}
        result = grader.grade_encounter(submission, _gt_dict(hh), fields=PART3_FIELDS)
        deduction_fb = [
            fb for fb in result.field_feedback
            if fb["field"] == EXPENSE_DEDUCTION_TYPE
        ]
        assert len(deduction_fb) == 1
        assert deduction_fb[0]["status"] == "correct"
