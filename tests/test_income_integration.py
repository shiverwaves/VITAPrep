"""End-to-end integration tests for Part 2 (Income) gameplay loop.

Validates the full pipeline:
1. Build a household with PII + employment + income data
2. Render all applicable income documents (W-2, 1099s, SSA-1099)
3. Verify income fields populated on the intake form
4. Inject income errors → grade → verify feedback

No mocks — these exercise the real DocumentRenderer, form_populator,
ErrorInjector, and Grader with hand-built households that have known
income data.
"""

from datetime import date

import pytest

from generator.models import (
    Address,
    Employer,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Household,
    Person,
    RelationshipType,
    SSA1099,
    W2,
)
from training.document_renderer import DocumentRenderer
from training.error_injector import ErrorInjector
from training.form_populator import build_field_values
from training.grader import Grader


# =========================================================================
# Helpers
# =========================================================================

def _employer(name: str = "Acme Corp", ein: str = "12-3456789") -> Employer:
    return Employer(
        name=name, ein=ein,
        address=Address(
            street="500 Business Pkwy", city="Honolulu",
            state="HI", zip_code="96813",
        ),
    )


def _make_single_worker() -> Household:
    """Single adult with W-2 wage income only."""
    return Household(
        household_id="hh-int-001",
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
                age=30, sex="F", race="white",
                legal_first_name="Alice",
                legal_middle_name="Mae",
                legal_last_name="Smith",
                ssn="900-11-2222",
                dob=date(1992, 3, 15),
                phone="(808) 555-0001",
                email="alice@example.com",
                id_type="drivers_license",
                id_state="HI",
                id_number="H1111111",
                id_expiry=date(2029, 1, 1),
                id_address=Address(
                    street="100 Main St", city="Honolulu",
                    state="HI", zip_code="96816",
                ),
                employment_status="employed",
                occupation_title="Software Developer",
                wage_income=55000,
                w2s=[W2(
                    employer=_employer(),
                    wages=55000,
                    federal_tax_withheld=8000,
                    social_security_wages=55000,
                    social_security_tax=3410,
                    medicare_wages=55000,
                    medicare_tax=798,
                    state="HI",
                    state_wages=55000,
                    state_tax=2750,
                    control_number="W2-001",
                )],
            ),
        ],
    )


def _make_married_diverse_income() -> Household:
    """Married couple with diverse income: wages, interest, dividends,
    retirement (1099-R), social security, and self-employment."""
    householder = Person(
        person_id="p-10",
        relationship=RelationshipType.HOUSEHOLDER,
        age=62, sex="M", race="white",
        legal_first_name="Robert",
        legal_middle_name="James",
        legal_last_name="Wilson",
        ssn="900-22-3333",
        dob=date(1960, 7, 4),
        phone="(808) 555-0010",
        email="robert@example.com",
        id_type="drivers_license",
        id_state="HI",
        id_number="H2222222",
        id_expiry=date(2028, 12, 31),
        id_address=Address(
            street="200 Palm Ave", city="Kailua",
            state="HI", zip_code="96734",
        ),
        employment_status="employed",
        occupation_title="Accountant",
        wage_income=72000,
        interest_income=1500,
        dividend_income=3200,
        retirement_income=12000,
        w2s=[W2(
            employer=_employer("Pacific Accounting LLC", "98-7654321"),
            wages=72000,
            federal_tax_withheld=11000,
            social_security_wages=72000,
            social_security_tax=4464,
            medicare_wages=72000,
            medicare_tax=1044,
            state="HI",
            state_wages=72000,
            state_tax=3600,
            control_number="W2-010",
        )],
        form_1099_ints=[Form1099INT(
            payer_name="First Hawaiian Bank",
            payer_tin="99-1111111",
            interest_income=1500,
        )],
        form_1099_divs=[Form1099DIV(
            payer_name="Vanguard Funds",
            payer_tin="99-2222222",
            ordinary_dividends=3200,
            qualified_dividends=2800,
        )],
        form_1099_rs=[Form1099R(
            payer_name="Hawaii State Pension Fund",
            payer_tin="99-3333333",
            gross_distribution=12000,
            taxable_amount=12000,
            federal_tax_withheld=1800,
            distribution_code="7",
        )],
    )

    spouse = Person(
        person_id="p-11",
        relationship=RelationshipType.SPOUSE,
        age=66, sex="F", race="white",
        legal_first_name="Margaret",
        legal_middle_name="Ellen",
        legal_last_name="Wilson",
        ssn="900-33-4444",
        dob=date(1956, 11, 20),
        phone="(808) 555-0011",
        email="margaret@example.com",
        id_type="state_id",
        id_state="HI",
        id_number="S3333333",
        id_expiry=date(2027, 6, 15),
        id_address=Address(
            street="200 Palm Ave", city="Kailua",
            state="HI", zip_code="96734",
        ),
        social_security_income=18000,
        self_employment_income=8000,
        interest_income=500,
        ssa_1099=SSA1099(
            total_benefits=18000,
            benefits_repaid=0,
            net_benefits=18000,
        ),
        form_1099_necs=[Form1099NEC(
            payer_name="Island Crafts Co",
            payer_tin="99-4444444",
            nonemployee_compensation=8000,
        )],
        form_1099_ints=[Form1099INT(
            payer_name="Bank of Hawaii",
            payer_tin="99-5555555",
            interest_income=500,
        )],
    )

    child = Person(
        person_id="p-12",
        relationship=RelationshipType.BIOLOGICAL_CHILD,
        age=14, sex="M", race="white",
        legal_first_name="Tommy",
        legal_last_name="Wilson",
        ssn="900-44-5555",
        dob=date(2008, 4, 10),
        is_dependent=True,
        can_be_claimed=True,
        months_in_home=12,
        interest_income=50,
        form_1099_ints=[Form1099INT(
            payer_name="Kids Savings Bank",
            payer_tin="99-6666666",
            interest_income=50,
        )],
    )

    return Household(
        household_id="hh-int-002",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
        address=Address(
            street="200 Palm Ave", city="Kailua",
            state="HI", zip_code="96734",
        ),
        members=[householder, spouse, child],
    )


# =========================================================================
# 1. Document rendering — all income documents produce valid HTML
# =========================================================================

class TestDocumentRendering:

    @pytest.fixture
    def renderer(self) -> DocumentRenderer:
        return DocumentRenderer()

    def test_render_w2(self, renderer: DocumentRenderer) -> None:
        hh = _make_single_worker()
        person = hh.members[0]
        html = renderer.render_w2_html(person, person.w2s[0])
        assert "Acme Corp" in html
        assert "$55,000.00" in html
        assert "900-11-2222" in html
        assert "watermark" in html

    def test_render_1099_int(self, renderer: DocumentRenderer) -> None:
        hh = _make_married_diverse_income()
        person = hh.members[0]  # Robert
        html = renderer.render_1099_int_html(person, person.form_1099_ints[0])
        assert "First Hawaiian Bank" in html
        assert "$1,500.00" in html
        assert "Robert" in html

    def test_render_1099_div(self, renderer: DocumentRenderer) -> None:
        hh = _make_married_diverse_income()
        person = hh.members[0]
        html = renderer.render_1099_div_html(person, person.form_1099_divs[0])
        assert "Vanguard Funds" in html
        assert "$3,200.00" in html
        assert "$2,800.00" in html

    def test_render_1099_r(self, renderer: DocumentRenderer) -> None:
        hh = _make_married_diverse_income()
        person = hh.members[0]
        html = renderer.render_1099_r_html(person, person.form_1099_rs[0])
        assert "Hawaii State Pension Fund" in html
        assert "$12,000.00" in html
        assert "7" in html  # distribution code

    def test_render_ssa_1099(self, renderer: DocumentRenderer) -> None:
        hh = _make_married_diverse_income()
        spouse = hh.members[1]  # Margaret
        html = renderer.render_ssa_1099_html(spouse, spouse.ssa_1099)
        assert "Margaret" in html
        assert "$18,000.00" in html

    def test_render_1099_nec(self, renderer: DocumentRenderer) -> None:
        hh = _make_married_diverse_income()
        spouse = hh.members[1]
        html = renderer.render_1099_nec_html(spouse, spouse.form_1099_necs[0])
        assert "Island Crafts Co" in html
        assert "$8,000.00" in html

    def test_render_all_documents_for_household(
        self, renderer: DocumentRenderer,
    ) -> None:
        """Every income document in the household renders without error."""
        hh = _make_married_diverse_income()
        rendered = []
        for person in hh.members:
            for w2 in person.w2s:
                rendered.append(renderer.render_w2_html(person, w2))
            for f in person.form_1099_ints:
                rendered.append(renderer.render_1099_int_html(person, f))
            for f in person.form_1099_divs:
                rendered.append(renderer.render_1099_div_html(person, f))
            for f in person.form_1099_rs:
                rendered.append(renderer.render_1099_r_html(person, f))
            if person.ssa_1099:
                rendered.append(
                    renderer.render_ssa_1099_html(person, person.ssa_1099)
                )
            for f in person.form_1099_necs:
                rendered.append(renderer.render_1099_nec_html(person, f))
        assert len(rendered) == 8  # 1 W-2 + 3 INT + 1 DIV + 1 R + 1 SSA + 1 NEC
        assert all("watermark" in h for h in rendered)

    def test_dependent_documents_render(
        self, renderer: DocumentRenderer,
    ) -> None:
        """Dependent's 1099-INT renders, but is NOT on intake form."""
        hh = _make_married_diverse_income()
        child = hh.members[2]
        html = renderer.render_1099_int_html(child, child.form_1099_ints[0])
        assert "Kids Savings Bank" in html
        assert "$50.00" in html


# =========================================================================
# 2. Intake form population — income fields from household data
# =========================================================================

class TestIntakePopulation:

    def test_single_worker_wage_fields(self) -> None:
        hh = _make_single_worker()
        values = build_field_values(hh)
        assert values["income.wages"] == "Yes"
        assert values["income.wages.amount"] == "55000"
        assert values["income.total"] == "55000"

    def test_single_worker_no_other_income(self) -> None:
        hh = _make_single_worker()
        values = build_field_values(hh)
        assert "income.interest" not in values
        assert "income.dividends" not in values
        assert "income.social_security" not in values
        assert "income.retirement" not in values
        assert "income.self_employment" not in values

    def test_married_all_income_types(self) -> None:
        hh = _make_married_diverse_income()
        values = build_field_values(hh)

        assert values["income.wages"] == "Yes"
        assert values["income.wages.amount"] == "72000"

        assert values["income.interest"] == "Yes"
        assert values["income.interest.amount"] == "2000"  # 1500 + 500

        assert values["income.dividends"] == "Yes"
        assert values["income.dividends.amount"] == "3200"

        assert values["income.social_security"] == "Yes"
        assert values["income.social_security.amount"] == "18000"

        assert values["income.retirement"] == "Yes"
        assert values["income.retirement.amount"] == "12000"

        assert values["income.self_employment"] == "Yes"
        assert values["income.self_employment.amount"] == "8000"

    def test_married_total_excludes_dependent(self) -> None:
        """Dependent's income ($50 interest) must NOT appear in totals."""
        hh = _make_married_diverse_income()
        values = build_field_values(hh)
        expected_total = 72000 + 2000 + 3200 + 18000 + 12000 + 8000
        assert values["income.total"] == str(expected_total)

    def test_intake_p2_html_render(self) -> None:
        """Form 13614-C Part II renders with populated values."""
        hh = _make_married_diverse_income()
        values = build_field_values(hh)
        renderer = DocumentRenderer()
        html = renderer.render_intake_p2_html(hh, values)
        assert "income" in html.lower()
        assert "watermark" in html


# =========================================================================
# 3. Error injection — income errors are valid and detectable
# =========================================================================

class TestIncomeErrorInjection:

    def test_wage_mismatch_injected(self) -> None:
        """Wage mismatch error changes the income amount."""
        hh = _make_single_worker()
        injector = ErrorInjector()
        _, errors = injector.inject(hh, difficulty="easy", error_count=10)
        income_errors = [e for e in errors if e.category == "income"]
        if income_errors:
            for err in income_errors:
                assert err.correct_value != err.erroneous_value

    def test_married_household_income_errors(self) -> None:
        """Diverse-income household can produce income-category errors."""
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        _, errors = injector.inject(hh, difficulty="medium", error_count=15)
        income_errors = [e for e in errors if e.category == "income"]
        assert len(income_errors) >= 1
        fields_hit = {e.field for e in income_errors}
        assert len(fields_hit) >= 1

    def test_error_free_scenario(self) -> None:
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        _, errors = injector.inject(hh, difficulty="easy", error_count=0)
        assert errors == []

    def test_injected_errors_have_person_ids(self) -> None:
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        _, errors = injector.inject(hh, difficulty="easy", error_count=5)
        for err in errors:
            assert err.person_id


# =========================================================================
# 4. Grading — intake mode with income fields
# =========================================================================

class TestIntakeGrading:

    def test_perfect_intake_score(self) -> None:
        """Submitting exact answer key gets 100%."""
        hh = _make_married_diverse_income()
        values = build_field_values(hh)
        grader = Grader()
        result = grader.grade_intake(values, hh)
        assert result.accuracy == 1.0
        assert result.score == result.max_score
        assert "Perfect" in result.feedback

    def test_wrong_wage_amount(self) -> None:
        """Incorrect wage amount is flagged."""
        hh = _make_single_worker()
        values = build_field_values(hh)
        values["income.wages.amount"] = "99999"
        grader = Grader()
        result = grader.grade_intake(values, hh)
        assert result.accuracy < 1.0
        wrong = [f for f in result.field_feedback if f["status"] == "incorrect"]
        wrong_fields = {f["field"] for f in wrong}
        assert "income.wages.amount" in wrong_fields

    def test_missing_income_source(self) -> None:
        """Omitting an income checkbox is caught."""
        hh = _make_married_diverse_income()
        values = build_field_values(hh)
        del values["income.interest"]
        del values["income.interest.amount"]
        grader = Grader()
        result = grader.grade_intake(values, hh)
        assert result.accuracy < 1.0
        wrong_fields = {
            f["field"] for f in result.field_feedback
            if f["status"] == "incorrect"
        }
        assert "income.interest" in wrong_fields
        assert "income.interest.amount" in wrong_fields

    def test_numeric_tolerance(self) -> None:
        """$55,000 matches '55000' (formatting difference)."""
        hh = _make_single_worker()
        values = build_field_values(hh)
        values["income.wages.amount"] = "$55,000"
        grader = Grader()
        result = grader.grade_intake(values, hh)
        assert result.accuracy == 1.0

    def test_empty_submission_scores_zero(self) -> None:
        hh = _make_single_worker()
        grader = Grader()
        result = grader.grade_intake({}, hh)
        assert result.score == 0
        assert result.accuracy == 0.0


# =========================================================================
# 5. Verification grading — injected income errors
# =========================================================================

class TestVerificationGrading:

    def test_find_all_injected_errors(self) -> None:
        """Student who flags every injected error gets perfect score.

        Uses error_count=1 to avoid duplicate-field collisions in the
        grader's field-based matching (two people can produce the same
        field key, e.g. both get 'street_address').
        """
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        _, errors = injector.inject(hh, difficulty="easy", error_count=1)
        if not errors:
            pytest.skip("No errors injected (unlikely)")

        flagged = [
            {"field": e.field, "description": f"Found: {e.explanation}"}
            for e in errors
        ]
        grader = Grader()
        result = grader.grade_verification(flagged, errors)
        assert result.score == result.max_score
        assert result.accuracy == 1.0

    def test_miss_all_errors(self) -> None:
        """Submitting nothing against injected errors scores 0."""
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        _, errors = injector.inject(hh, difficulty="easy", error_count=2)
        if not errors:
            pytest.skip("No errors injected")

        grader = Grader()
        result = grader.grade_verification([], errors)
        assert result.score == 0
        assert len(result.missed_flags) == len(errors)

    def test_false_flag_penalty(self) -> None:
        """Flagging a non-existent error produces a false flag."""
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        _, errors = injector.inject(hh, difficulty="easy", error_count=0)

        flagged = [{"field": "income.wages", "description": "looks wrong"}]
        grader = Grader()
        result = grader.grade_verification(flagged, errors)
        assert len(result.false_flags) == 1


# =========================================================================
# 6. Full pipeline: generate → render → populate → inject → grade
# =========================================================================

class TestFullPipeline:

    def test_end_to_end_intake(self) -> None:
        """Complete intake flow: build → render → populate → grade."""
        hh = _make_married_diverse_income()
        renderer = DocumentRenderer()

        docs = []
        for person in hh.members:
            docs.append(renderer.render_ssn_card_html(person))
            for w2 in person.w2s:
                docs.append(renderer.render_w2_html(person, w2))
            for f in person.form_1099_ints:
                docs.append(renderer.render_1099_int_html(person, f))
            for f in person.form_1099_divs:
                docs.append(renderer.render_1099_div_html(person, f))
            for f in person.form_1099_rs:
                docs.append(renderer.render_1099_r_html(person, f))
            if person.ssa_1099:
                docs.append(renderer.render_ssa_1099_html(person, person.ssa_1099))
            for f in person.form_1099_necs:
                docs.append(renderer.render_1099_nec_html(person, f))
        assert len(docs) >= 3

        answer = build_field_values(hh)
        assert "income.wages" in answer
        assert "income.total" in answer

        grader = Grader()
        result = grader.grade_intake(answer, hh)
        assert result.accuracy == 1.0

    def test_end_to_end_verify(self) -> None:
        """Complete verify flow: build → inject → grade flagged errors."""
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        modified_hh, errors = injector.inject(
            hh, difficulty="medium", error_count=3,
        )

        assert modified_hh.household_id == hh.household_id
        if errors:
            flagged = [
                {"field": e.field, "description": e.explanation}
                for e in errors
            ]
            grader = Grader()
            result = grader.grade_verification(flagged, errors)
            assert result.accuracy == 1.0
            assert result.score == len(errors)

    def test_end_to_end_with_documents_and_grading(self) -> None:
        """Full loop: render docs from modified household, grade intake."""
        hh = _make_married_diverse_income()
        injector = ErrorInjector()
        modified_hh, errors = injector.inject(
            hh, difficulty="easy", error_count=2,
        )

        renderer = DocumentRenderer()
        for person in modified_hh.members:
            for w2 in person.w2s:
                html = renderer.render_w2_html(person, w2)
                assert len(html) > 0
            for f in person.form_1099_ints:
                html = renderer.render_1099_int_html(person, f)
                assert len(html) > 0

        correct_values = build_field_values(hh)
        grader = Grader()
        result = grader.grade_intake(correct_values, hh)
        assert result.accuracy == 1.0
