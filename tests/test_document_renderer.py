"""Tests for training/document_renderer.py.

Tests the DocumentRenderer class, Jinja2 templates, and HTML rendering.
"""

import re
from datetime import date
from pathlib import Path

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

# Import the module — renderer class and helpers
from training.document_renderer import (
    DocumentRenderer,
    _estimate_issue_date,
    _format_date,
    _format_dollars,
    _STATE_NAMES,
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def renderer(tmp_path: Path) -> DocumentRenderer:
    """DocumentRenderer instance."""
    return DocumentRenderer(output_dir=str(tmp_path / "docs"))


@pytest.fixture
def adult_with_dl() -> Person:
    """An adult with a driver's license."""
    return Person(
        person_id="p-1",
        relationship=RelationshipType.HOUSEHOLDER,
        age=35,
        sex="M",
        race="white",
        legal_first_name="John",
        legal_middle_name="Robert",
        legal_last_name="Smith",
        suffix="",
        ssn="900-12-3456",
        dob=date(1989, 5, 15),
        phone="(808) 555-1234",
        email="john.smith@example.com",
        id_type="drivers_license",
        id_state="HI",
        id_number="H12345678",
        id_expiry=date(2028, 3, 15),
        id_address=Address(
            street="123 Kalakaua Ave",
            apt="Apt 4B",
            city="Honolulu",
            state="HI",
            zip_code="96815",
        ),
    )


@pytest.fixture
def adult_with_state_id() -> Person:
    """An adult with a state-issued identification card."""
    return Person(
        person_id="p-2",
        relationship=RelationshipType.SPOUSE,
        age=33,
        sex="F",
        race="asian",
        legal_first_name="Jane",
        legal_middle_name="Marie",
        legal_last_name="Smith",
        suffix="",
        ssn="900-65-4321",
        dob=date(1991, 8, 22),
        phone="(808) 555-5678",
        email="",
        id_type="state_id",
        id_state="HI",
        id_number="H87654321",
        id_expiry=date(2027, 11, 1),
        id_address=Address(
            street="123 Kalakaua Ave",
            apt="Apt 4B",
            city="Honolulu",
            state="HI",
            zip_code="96815",
        ),
    )


@pytest.fixture
def child() -> Person:
    """A child with no ID document."""
    return Person(
        person_id="p-3",
        relationship=RelationshipType.BIOLOGICAL_CHILD,
        age=10,
        sex="M",
        race="white",
        legal_first_name="Jake",
        legal_middle_name="Thomas",
        legal_last_name="Smith",
        ssn="900-99-0001",
        dob=date(2014, 2, 28),
        id_type="",
    )


@pytest.fixture
def sample_household(adult_with_dl, adult_with_state_id, child) -> Household:
    """A household with all member types for rendering tests."""
    return Household(
        household_id="hh-test",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
        members=[adult_with_dl, adult_with_state_id, child],
        address=Address(
            street="123 Kalakaua Ave",
            apt="Apt 4B",
            city="Honolulu",
            state="HI",
            zip_code="96815",
        ),
    )


# =========================================================================
# Helper function tests
# =========================================================================

class TestHelpers:
    """Tests for module-level helper functions."""

    def test_format_date(self) -> None:
        assert _format_date(date(2028, 3, 15)) == "03/15/2028"

    def test_format_date_none(self) -> None:
        assert _format_date(None) == ""

    def test_format_date_single_digit_month(self) -> None:
        assert _format_date(date(2025, 1, 5)) == "01/05/2025"

    def test_estimate_issue_date(self) -> None:
        issue = _estimate_issue_date(date(2028, 3, 15))
        assert issue == date(2020, 3, 15)

    def test_estimate_issue_date_none(self) -> None:
        assert _estimate_issue_date(None) is None

    def test_state_names_dict_has_all_states(self) -> None:
        assert len(_STATE_NAMES) >= 51  # 50 states + DC
        assert _STATE_NAMES["HI"] == "Hawaii"
        assert _STATE_NAMES["CA"] == "California"
        assert _STATE_NAMES["DC"] == "District of Columbia"


# =========================================================================
# Jinja2 template rendering (HTML output)
# =========================================================================

class TestTemplateRendering:
    """Verify that templates produce correct HTML content."""

    def test_ssn_card_html_contains_ssn(self, renderer, adult_with_dl) -> None:
        template = renderer._env.get_template("ssn_card.html")
        html = template.render(
            ssn=adult_with_dl.ssn,
            full_name=adult_with_dl.full_legal_name(),
        )
        assert "900-12-3456" in html
        # Name is rendered as-is; CSS text-transform uppercases it visually
        assert "John Robert Smith" in html
        # Watermark text is in CSS ::after content, so check for the div
        assert 'class="watermark"' in html

    def test_ssn_card_html_watermark(self, renderer, adult_with_dl) -> None:
        template = renderer._env.get_template("ssn_card.html")
        html = template.render(
            ssn=adult_with_dl.ssn,
            full_name=adult_with_dl.full_legal_name(),
        )
        assert 'class="watermark"' in html

    def test_dl_html_contains_fields(self, renderer, adult_with_dl) -> None:
        template = renderer._env.get_template("drivers_license.html")
        html = template.render(
            state_name="Hawaii",
            id_number="H12345678",
            dl_class="3",
            expiry_formatted="03/15/2028",
            issue_formatted="03/15/2020",
            first_name="John",
            middle_name="Robert",
            middle_initial="R",
            last_name="Smith",
            suffix="",
            address_street="123 Kalakaua Ave",
            address_apt="Apt 4B",
            address_city="Honolulu",
            address_state="HI",
            address_zip="96815",
            dob_formatted="05/15/1989",
            sex="M",
            expired=False,
        )
        assert "Hawaii" in html
        assert "Driver License" in html
        assert "H12345678" in html
        assert "Smith" in html
        assert "John" in html
        assert "Honolulu" in html
        assert "05/15/1989" in html

    def test_dl_html_expired_stamp(self, renderer) -> None:
        template = renderer._env.get_template("drivers_license.html")
        html = template.render(
            state_name="Hawaii",
            id_number="H12345678",
            dl_class="3",
            expiry_formatted="01/01/2020",
            issue_formatted="01/01/2012",
            first_name="Old",
            middle_name="",
            middle_initial="",
            last_name="Timer",
            suffix="",
            address_street="1 St",
            address_apt="",
            address_city="Hilo",
            address_state="HI",
            address_zip="96720",
            dob_formatted="01/01/1950",
            sex="M",
            expired=True,
        )
        assert "EXPIRED" in html
        assert "dl-expired-stamp" in html

    def test_dl_html_no_expired_stamp_when_valid(self, renderer) -> None:
        template = renderer._env.get_template("drivers_license.html")
        html = template.render(
            state_name="Hawaii",
            id_number="H12345678",
            dl_class="3",
            expiry_formatted="01/01/2030",
            issue_formatted="01/01/2022",
            first_name="Valid",
            middle_name="",
            middle_initial="",
            last_name="Person",
            suffix="",
            address_street="1 St",
            address_apt="",
            address_city="Hilo",
            address_state="HI",
            address_zip="96720",
            dob_formatted="01/01/1990",
            sex="F",
            expired=False,
        )
        # The CSS class exists in <style> but the stamp div should not render
        assert ">EXPIRED<" not in html

    def test_state_id_html_contains_fields(self, renderer, adult_with_state_id) -> None:
        template = renderer._env.get_template("state_id.html")
        html = template.render(
            state_name="Hawaii",
            id_number="H87654321",
            expiry_formatted="11/01/2027",
            issue_formatted="11/01/2019",
            first_name="Jane",
            middle_name="Marie",
            middle_initial="M",
            last_name="Smith",
            suffix="",
            address_street="123 Kalakaua Ave",
            address_apt="Apt 4B",
            address_city="Honolulu",
            address_state="HI",
            address_zip="96815",
            dob_formatted="08/22/1991",
            sex="F",
            expired=False,
        )
        assert "Hawaii" in html
        assert "Identification Card" in html
        assert "H87654321" in html
        assert "Smith" in html
        assert "Jane" in html
        assert "Driver License" not in html

    def test_state_id_html_expired_stamp(self, renderer) -> None:
        template = renderer._env.get_template("state_id.html")
        html = template.render(
            state_name="Hawaii",
            id_number="H00000001",
            expiry_formatted="01/01/2020",
            issue_formatted="01/01/2012",
            first_name="Expired",
            middle_name="",
            middle_initial="",
            last_name="Person",
            suffix="",
            address_street="1 St",
            address_apt="",
            address_city="Hilo",
            address_state="HI",
            address_zip="96720",
            dob_formatted="01/01/1960",
            sex="F",
            expired=True,
        )
        assert "EXPIRED" in html
        assert "id-expired-stamp" in html


# =========================================================================
# DocumentRenderer HTML methods
# =========================================================================

class TestRendererHTMLMethods:
    """Test the renderer's HTML rendering methods."""

    def test_render_ssn_card_html(self, renderer, adult_with_dl) -> None:
        html = renderer.render_ssn_card_html(adult_with_dl)
        assert "900-12-3456" in html
        assert "John Robert Smith" in html

    def test_render_photo_id_html_dl(self, renderer, adult_with_dl) -> None:
        html = renderer.render_photo_id_html(adult_with_dl)
        assert html is not None
        assert "Driver License" in html
        assert "H12345678" in html
        assert "Smith" in html

    def test_render_photo_id_html_state_id(self, renderer, adult_with_state_id) -> None:
        html = renderer.render_photo_id_html(adult_with_state_id)
        assert html is not None
        assert "Identification Card" in html
        assert "H87654321" in html

    def test_render_photo_id_html_no_id(self, renderer, child) -> None:
        html = renderer.render_photo_id_html(child)
        assert html is None

    def test_render_id_card_html_expired(self, renderer) -> None:
        person = Person(
            person_id="p-exp",
            id_type="drivers_license",
            id_state="HI",
            id_number="H00000001",
            id_expiry=date(2020, 1, 1),
            legal_first_name="Old",
            legal_last_name="Timer",
            id_address=Address(street="1 St", city="Hilo", state="HI", zip_code="96720"),
        )
        html = renderer.render_photo_id_html(person)
        assert html is not None
        assert "EXPIRED" in html


# =========================================================================
# Dollar formatting
# =========================================================================


class TestFormatDollars:
    def test_positive_amount(self) -> None:
        assert _format_dollars(50000) == "$50,000.00"

    def test_zero_returns_empty(self) -> None:
        assert _format_dollars(0) == ""

    def test_large_amount(self) -> None:
        assert _format_dollars(160200) == "$160,200.00"

    def test_small_amount(self) -> None:
        assert _format_dollars(42) == "$42.00"


# =========================================================================
# Income document rendering — W-2
# =========================================================================


class TestW2Rendering:
    @pytest.fixture
    def sample_w2(self) -> W2:
        return W2(
            employer=Employer(
                name="Acme Corp",
                ein="12-3456789",
                address=Address(
                    street="100 Main St", city="Honolulu", state="HI", zip_code="96801"
                ),
            ),
            wages=55000,
            federal_tax_withheld=6200,
            social_security_wages=55000,
            social_security_tax=3410,
            medicare_wages=55000,
            medicare_tax=798,
            state="HI",
            state_wages=55000,
            state_tax=2800,
            control_number="W2-001",
            box_12=[("D", 5000)],
        )

    def test_w2_contains_employer(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "Acme Corp" in html
        assert "12-3456789" in html

    def test_w2_contains_employee(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "John Robert Smith" in html
        assert "900-12-3456" in html

    def test_w2_contains_wages(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "$55,000.00" in html
        assert "$6,200.00" in html

    def test_w2_contains_fica(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "$3,410.00" in html
        assert "$798.00" in html

    def test_w2_contains_state(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "HI" in html
        assert "$2,800.00" in html

    def test_w2_has_watermark(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert 'class="watermark"' in html

    def test_w2_contains_title(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "Form W-2" in html
        assert "Wage and Tax Statement" in html

    def test_w2_contains_box_12(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "D" in html
        assert "$5,000.00" in html

    def test_w2_employer_address(self, renderer, adult_with_dl, sample_w2) -> None:
        html = renderer.render_w2_html(adult_with_dl, sample_w2)
        assert "100 Main St" in html
        assert "Honolulu" in html


# =========================================================================
# Income document rendering — 1099-INT
# =========================================================================


class TestForm1099INTRendering:
    @pytest.fixture
    def sample_1099_int(self) -> Form1099INT:
        return Form1099INT(
            payer_name="First Hawaiian Bank",
            payer_tin="99-1234567",
            interest_income=850,
            us_savings_bond_interest=0,
            federal_tax_withheld=0,
        )

    def test_contains_payer(self, renderer, adult_with_dl, sample_1099_int) -> None:
        html = renderer.render_1099_int_html(adult_with_dl, sample_1099_int)
        assert "First Hawaiian Bank" in html
        assert "99-1234567" in html

    def test_contains_recipient(self, renderer, adult_with_dl, sample_1099_int) -> None:
        html = renderer.render_1099_int_html(adult_with_dl, sample_1099_int)
        assert "John Robert Smith" in html
        assert "900-12-3456" in html

    def test_contains_interest(self, renderer, adult_with_dl, sample_1099_int) -> None:
        html = renderer.render_1099_int_html(adult_with_dl, sample_1099_int)
        assert "$850.00" in html

    def test_has_watermark(self, renderer, adult_with_dl, sample_1099_int) -> None:
        html = renderer.render_1099_int_html(adult_with_dl, sample_1099_int)
        assert 'class="watermark"' in html

    def test_contains_title(self, renderer, adult_with_dl, sample_1099_int) -> None:
        html = renderer.render_1099_int_html(adult_with_dl, sample_1099_int)
        assert "1099-INT" in html
        assert "Interest Income" in html


# =========================================================================
# Income document rendering — 1099-DIV
# =========================================================================


class TestForm1099DIVRendering:
    @pytest.fixture
    def sample_1099_div(self) -> Form1099DIV:
        return Form1099DIV(
            payer_name="Vanguard Funds",
            payer_tin="23-7654321",
            ordinary_dividends=1200,
            qualified_dividends=900,
            capital_gain_distributions=300,
            federal_tax_withheld=0,
        )

    def test_contains_payer(self, renderer, adult_with_dl, sample_1099_div) -> None:
        html = renderer.render_1099_div_html(adult_with_dl, sample_1099_div)
        assert "Vanguard Funds" in html
        assert "23-7654321" in html

    def test_contains_dividends(self, renderer, adult_with_dl, sample_1099_div) -> None:
        html = renderer.render_1099_div_html(adult_with_dl, sample_1099_div)
        assert "$1,200.00" in html
        assert "$900.00" in html
        assert "$300.00" in html

    def test_contains_title(self, renderer, adult_with_dl, sample_1099_div) -> None:
        html = renderer.render_1099_div_html(adult_with_dl, sample_1099_div)
        assert "1099-DIV" in html
        assert "Dividends" in html

    def test_has_watermark(self, renderer, adult_with_dl, sample_1099_div) -> None:
        html = renderer.render_1099_div_html(adult_with_dl, sample_1099_div)
        assert 'class="watermark"' in html


# =========================================================================
# Income document rendering — 1099-R
# =========================================================================


class TestForm1099RRendering:
    @pytest.fixture
    def sample_1099_r(self) -> Form1099R:
        return Form1099R(
            payer_name="Hawaii State Pension Fund",
            payer_tin="99-8765432",
            gross_distribution=18000,
            taxable_amount=18000,
            federal_tax_withheld=2700,
            distribution_code="7",
        )

    def test_contains_payer(self, renderer, adult_with_dl, sample_1099_r) -> None:
        html = renderer.render_1099_r_html(adult_with_dl, sample_1099_r)
        assert "Hawaii State Pension Fund" in html
        assert "99-8765432" in html

    def test_contains_distribution(self, renderer, adult_with_dl, sample_1099_r) -> None:
        html = renderer.render_1099_r_html(adult_with_dl, sample_1099_r)
        assert "$18,000.00" in html
        assert "$2,700.00" in html

    def test_contains_code(self, renderer, adult_with_dl, sample_1099_r) -> None:
        html = renderer.render_1099_r_html(adult_with_dl, sample_1099_r)
        assert ">7<" in html

    def test_contains_title(self, renderer, adult_with_dl, sample_1099_r) -> None:
        html = renderer.render_1099_r_html(adult_with_dl, sample_1099_r)
        assert "1099-R" in html
        assert "Pensions" in html

    def test_has_watermark(self, renderer, adult_with_dl, sample_1099_r) -> None:
        html = renderer.render_1099_r_html(adult_with_dl, sample_1099_r)
        assert 'class="watermark"' in html


# =========================================================================
# Income document rendering — SSA-1099
# =========================================================================


class TestSSA1099Rendering:
    @pytest.fixture
    def sample_ssa_1099(self) -> SSA1099:
        return SSA1099(
            total_benefits=16800,
            benefits_repaid=0,
            net_benefits=16800,
        )

    def test_contains_recipient(self, renderer, adult_with_dl, sample_ssa_1099) -> None:
        html = renderer.render_ssa_1099_html(adult_with_dl, sample_ssa_1099)
        assert "John Robert Smith" in html
        assert "900-12-3456" in html

    def test_contains_benefits(self, renderer, adult_with_dl, sample_ssa_1099) -> None:
        html = renderer.render_ssa_1099_html(adult_with_dl, sample_ssa_1099)
        assert "$16,800.00" in html

    def test_contains_title(self, renderer, adult_with_dl, sample_ssa_1099) -> None:
        html = renderer.render_ssa_1099_html(adult_with_dl, sample_ssa_1099)
        assert "SSA-1099" in html
        assert "Social Security" in html

    def test_has_watermark(self, renderer, adult_with_dl, sample_ssa_1099) -> None:
        html = renderer.render_ssa_1099_html(adult_with_dl, sample_ssa_1099)
        assert 'class="watermark"' in html

    def test_ssa_subtitle(self, renderer, adult_with_dl, sample_ssa_1099) -> None:
        html = renderer.render_ssa_1099_html(adult_with_dl, sample_ssa_1099)
        assert "Social Security Administration" in html


# =========================================================================
# Income document rendering — 1099-NEC
# =========================================================================


class TestForm1099NECRendering:
    @pytest.fixture
    def sample_1099_nec(self) -> Form1099NEC:
        return Form1099NEC(
            payer_name="Island Consulting LLC",
            payer_tin="99-1112222",
            nonemployee_compensation=32000,
            federal_tax_withheld=0,
        )

    def test_contains_payer(self, renderer, adult_with_dl, sample_1099_nec) -> None:
        html = renderer.render_1099_nec_html(adult_with_dl, sample_1099_nec)
        assert "Island Consulting LLC" in html
        assert "99-1112222" in html

    def test_contains_compensation(self, renderer, adult_with_dl, sample_1099_nec) -> None:
        html = renderer.render_1099_nec_html(adult_with_dl, sample_1099_nec)
        assert "$32,000.00" in html

    def test_contains_title(self, renderer, adult_with_dl, sample_1099_nec) -> None:
        html = renderer.render_1099_nec_html(adult_with_dl, sample_1099_nec)
        assert "1099-NEC" in html
        assert "Nonemployee Compensation" in html

    def test_has_watermark(self, renderer, adult_with_dl, sample_1099_nec) -> None:
        html = renderer.render_1099_nec_html(adult_with_dl, sample_1099_nec)
        assert 'class="watermark"' in html
