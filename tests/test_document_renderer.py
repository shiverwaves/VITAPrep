"""Tests for training/document_renderer.py — Sprint 5.

Tests the DocumentRenderer class, templates, and Jinja2 rendering.
WeasyPrint tests are skipped if the library is not installed.
"""

import re
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from generator.models import Address, Household, Person, RelationshipType

# Import the module — renderer class and helpers
from training.document_renderer import (
    DocumentRenderer,
    _estimate_issue_date,
    _format_date,
    _STATE_NAMES,
)


# =========================================================================
# Check if WeasyPrint is available
# =========================================================================

try:
    import weasyprint  # noqa: F401
    HAS_WEASYPRINT = True
except ImportError:
    HAS_WEASYPRINT = False

skip_without_weasyprint = pytest.mark.skipif(
    not HAS_WEASYPRINT,
    reason="WeasyPrint not installed",
)


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def output_dir(tmp_path: Path) -> Path:
    """Temporary directory for rendered output."""
    d = tmp_path / "docs"
    d.mkdir()
    return d


@pytest.fixture
def renderer(output_dir: Path) -> DocumentRenderer:
    """DocumentRenderer pointing at a temp directory."""
    return DocumentRenderer(output_dir=str(output_dir))


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
# Helper function tests (no WeasyPrint needed)
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
# Jinja2 template rendering (HTML output, no WeasyPrint)
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
        # Name rendered as-is; CSS text-transform uppercases visually
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
        # Name rendered as-is; CSS text-transform uppercases visually
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
# DocumentRenderer methods (mock WeasyPrint)
# =========================================================================

class TestRendererWithMockedWeasyPrint:
    """Test the renderer class by mocking the WeasyPrint HTML-to-PDF step."""

    def _mock_render(self, renderer):
        """Patch _render_html_to_pdf to write a dummy file."""
        def fake_render(html, out_path):
            out_path.parent.mkdir(parents=True, exist_ok=True)
            out_path.write_text("FAKE_PDF")
        return patch.object(renderer, "_render_html_to_pdf", side_effect=fake_render)

    def test_render_ssn_card(self, renderer, adult_with_dl, output_dir) -> None:
        with self._mock_render(renderer):
            path = renderer.render_ssn_card(adult_with_dl)
        assert path.exists()
        assert path.name == "ssn_p-1.pdf"
        assert path.parent == output_dir

    def test_render_drivers_license(self, renderer, adult_with_dl, output_dir) -> None:
        with self._mock_render(renderer):
            path = renderer.render_drivers_license(adult_with_dl)
        assert path.exists()
        assert path.name == "dl_p-1.pdf"

    def test_render_state_id(self, renderer, adult_with_state_id, output_dir) -> None:
        with self._mock_render(renderer):
            path = renderer.render_state_id(adult_with_state_id)
        assert path.exists()
        assert path.name == "sid_p-2.pdf"

    def test_render_photo_id_dispatches_to_dl(self, renderer, adult_with_dl) -> None:
        with self._mock_render(renderer):
            path = renderer.render_photo_id(adult_with_dl)
        assert path is not None
        assert "dl_" in path.name

    def test_render_photo_id_dispatches_to_state_id(self, renderer, adult_with_state_id) -> None:
        with self._mock_render(renderer):
            path = renderer.render_photo_id(adult_with_state_id)
        assert path is not None
        assert "sid_" in path.name

    def test_render_photo_id_returns_none_for_no_id(self, renderer, child) -> None:
        path = renderer.render_photo_id(child)
        assert path is None

    def test_render_household_documents(self, renderer, sample_household, output_dir) -> None:
        with self._mock_render(renderer):
            paths = renderer.render_household_documents(sample_household)

        # 3 SSN cards (all members) + 2 photo IDs (2 adults)
        assert len(paths) == 5
        assert "ssn_p-1" in paths
        assert "ssn_p-2" in paths
        assert "ssn_p-3" in paths
        assert "id_p-1" in paths   # DL
        assert "id_p-2" in paths   # State ID

    def test_render_household_documents_files_exist(
        self, renderer, sample_household, output_dir,
    ) -> None:
        with self._mock_render(renderer):
            paths = renderer.render_household_documents(sample_household)
        for label, path in paths.items():
            assert path.exists(), f"{label}: {path} does not exist"

    def test_future_stubs_raise(self, renderer, sample_household, adult_with_dl) -> None:
        with pytest.raises(NotImplementedError):
            renderer.render_intake_form(sample_household)
        with pytest.raises(NotImplementedError):
            renderer.render_w2(adult_with_dl)
        with pytest.raises(NotImplementedError):
            renderer.render_1040_header(sample_household)


# =========================================================================
# Full rendering (requires WeasyPrint)
# =========================================================================

@skip_without_weasyprint
class TestFullRendering:
    """End-to-end rendering tests that produce real PDF files."""

    def test_ssn_card_pdf_created(self, renderer, adult_with_dl, output_dir) -> None:
        path = renderer.render_ssn_card(adult_with_dl)
        assert path.exists()
        assert path.suffix == ".pdf"
        # PDF files start with %PDF
        data = path.read_bytes()
        assert data[:5] == b"%PDF-"

    def test_dl_pdf_created(self, renderer, adult_with_dl, output_dir) -> None:
        path = renderer.render_drivers_license(adult_with_dl)
        assert path.exists()
        data = path.read_bytes()
        assert data[:5] == b"%PDF-"

    def test_state_id_pdf_created(self, renderer, adult_with_state_id, output_dir) -> None:
        path = renderer.render_state_id(adult_with_state_id)
        assert path.exists()
        data = path.read_bytes()
        assert data[:5] == b"%PDF-"

    def test_household_all_pdfs(self, renderer, sample_household, output_dir) -> None:
        paths = renderer.render_household_documents(sample_household)
        for label, path in paths.items():
            assert path.exists(), f"{label} missing"
            data = path.read_bytes()
            assert data[:5] == b"%PDF-", f"{label} is not a valid PDF"
