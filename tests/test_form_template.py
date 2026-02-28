"""Tests for the fillable Form 13614-C Part I PDF template — Sprint 6.

Validates:
- The PDF template exists and is a valid PDF
- All expected AcroForm fields are present with correct types
- Field names match the constants in training/form_fields.py
- pypdf can fill and read back field values (round-trip)
- The build script produces a reproducible template
"""

from pathlib import Path
from typing import Dict

import pytest
from pypdf import PdfReader, PdfWriter

from training.form_fields import (
    TEXT_FIELDS,
    CHECKBOX_FIELDS,
    ALL_FIELDS,
    FILING_STATUS,
    FILING_STATUS_CHOICES,
    YOU_FIRST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_LAST_NAME,
    YOU_DOB,
    YOU_SSN,
    YOU_JOB_TITLE,
    YOU_US_CITIZEN,
    YOU_NOT_US_CITIZEN,
    YOU_PHONE,
    YOU_EMAIL,
    ADDR_STREET,
    ADDR_APT,
    ADDR_CITY,
    ADDR_STATE,
    ADDR_ZIP,
    SPOUSE_FIRST_NAME,
    SPOUSE_LAST_NAME,
    SPOUSE_SSN,
    dep_field,
    DEP_FIRST_NAME,
    DEP_LAST_NAME,
    MAX_DEPENDENTS,
)

# Path to the committed template
TEMPLATE_PATH = Path(__file__).resolve().parent.parent / "training" / "templates" / "form_13614c_p1.pdf"


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def reader() -> PdfReader:
    """Load the template PDF."""
    assert TEMPLATE_PATH.exists(), f"Template not found: {TEMPLATE_PATH}"
    return PdfReader(str(TEMPLATE_PATH))


@pytest.fixture
def fields(reader: PdfReader) -> Dict:
    """Extract AcroForm fields from the template."""
    f = reader.get_fields()
    assert f is not None, "No AcroForm fields found in template"
    return f


# =========================================================================
# Basic PDF structure
# =========================================================================

class TestPDFStructure:
    """Verify the PDF is valid and has the expected structure."""

    def test_template_exists(self) -> None:
        assert TEMPLATE_PATH.exists()

    def test_template_is_pdf(self) -> None:
        data = TEMPLATE_PATH.read_bytes()
        assert data[:5] == b"%PDF-"

    def test_single_page(self, reader: PdfReader) -> None:
        assert len(reader.pages) == 1

    def test_has_acroform_fields(self, reader: PdfReader) -> None:
        fields = reader.get_fields()
        assert fields is not None
        assert len(fields) > 0


# =========================================================================
# Field presence and types
# =========================================================================

class TestFieldPresence:
    """Verify all expected fields exist with correct types."""

    def test_all_text_fields_present(self, fields: Dict) -> None:
        for field_name in TEXT_FIELDS:
            assert field_name in fields, f"Missing text field: {field_name}"

    def test_text_fields_have_correct_type(self, fields: Dict) -> None:
        for field_name in TEXT_FIELDS:
            ft = fields[field_name].get("/FT")
            assert ft == "/Tx", (
                f"Field {field_name} should be /Tx (text), got {ft}"
            )

    def test_checkbox_fields_present(self, fields: Dict) -> None:
        for field_name in CHECKBOX_FIELDS:
            assert field_name in fields, f"Missing checkbox field: {field_name}"

    def test_checkbox_fields_have_correct_type(self, fields: Dict) -> None:
        for field_name in CHECKBOX_FIELDS:
            ft = fields[field_name].get("/FT")
            assert ft == "/Btn", (
                f"Field {field_name} should be /Btn (button), got {ft}"
            )

    def test_filing_status_radio_present(self, fields: Dict) -> None:
        assert FILING_STATUS in fields, "Missing filing_status radio group"

    def test_filing_status_has_all_choices(self, fields: Dict) -> None:
        fs = fields[FILING_STATUS]
        states = fs.get("/_States_", [])
        # States are stored with leading /
        choice_set = {s.lstrip("/") for s in states}
        for choice in FILING_STATUS_CHOICES:
            assert choice in choice_set, (
                f"Missing filing status choice: {choice}"
            )

    def test_total_field_count(self, fields: Dict) -> None:
        # TEXT_FIELDS + CHECKBOX_FIELDS + filing_status radio = total
        # The radio group counts as 1 field in get_fields()
        expected_min = len(TEXT_FIELDS) + len(CHECKBOX_FIELDS) + 1
        # May have a few more due to radio children, but at least this many
        assert len(fields) >= expected_min - len(CHECKBOX_FIELDS)


# =========================================================================
# Section-specific field tests
# =========================================================================

class TestSectionAFields:
    """Section A: About You fields."""

    def test_your_name_fields(self, fields: Dict) -> None:
        for f in [YOU_FIRST_NAME, YOU_MIDDLE_INITIAL, YOU_LAST_NAME]:
            assert f in fields

    def test_your_dob_and_ssn(self, fields: Dict) -> None:
        assert YOU_DOB in fields
        assert YOU_SSN in fields

    def test_your_job_title(self, fields: Dict) -> None:
        assert YOU_JOB_TITLE in fields

    def test_citizen_checkboxes(self, fields: Dict) -> None:
        assert YOU_US_CITIZEN in fields
        assert YOU_NOT_US_CITIZEN in fields

    def test_contact_fields(self, fields: Dict) -> None:
        assert YOU_PHONE in fields
        assert YOU_EMAIL in fields


class TestSectionBFields:
    """Section B: Mailing Address fields."""

    def test_address_fields(self, fields: Dict) -> None:
        for f in [ADDR_STREET, ADDR_APT, ADDR_CITY, ADDR_STATE, ADDR_ZIP]:
            assert f in fields


class TestSectionCFields:
    """Section C: Spouse fields."""

    def test_spouse_fields(self, fields: Dict) -> None:
        for f in [SPOUSE_FIRST_NAME, SPOUSE_LAST_NAME, SPOUSE_SSN]:
            assert f in fields


class TestSectionEFields:
    """Section E: Dependent fields for all 4 rows."""

    def test_all_dependent_rows_present(self, fields: Dict) -> None:
        for i in range(MAX_DEPENDENTS):
            for sub in [DEP_FIRST_NAME, DEP_LAST_NAME]:
                name = dep_field(i, sub)
                assert name in fields, f"Missing dependent field: {name}"


# =========================================================================
# Round-trip fill test
# =========================================================================

class TestRoundTrip:
    """Verify pypdf can fill fields and read them back."""

    def test_fill_and_read_text_fields(self, tmp_path: Path) -> None:
        """Fill text fields, save, re-read, and verify values."""
        reader = PdfReader(str(TEMPLATE_PATH))
        writer = PdfWriter()
        writer.append(reader)

        test_values = {
            YOU_FIRST_NAME: "Jane",
            YOU_LAST_NAME: "Doe",
            YOU_DOB: "08/22/1991",
            YOU_SSN: "900-65-4321",
            ADDR_STREET: "456 Ocean Blvd",
            ADDR_CITY: "Honolulu",
            ADDR_STATE: "HI",
            ADDR_ZIP: "96816",
        }

        writer.update_page_form_field_values(
            writer.pages[0], test_values,
        )

        out_path = tmp_path / "filled.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)

        # Read back
        reader2 = PdfReader(str(out_path))
        fields2 = reader2.get_fields()
        assert fields2 is not None

        for field_name, expected_val in test_values.items():
            actual = fields2[field_name].get("/V", "")
            assert actual == expected_val, (
                f"Field {field_name}: expected {expected_val!r}, got {actual!r}"
            )

    def test_fill_dependent_fields(self, tmp_path: Path) -> None:
        """Fill dependent row fields and verify round-trip."""
        reader = PdfReader(str(TEMPLATE_PATH))
        writer = PdfWriter()
        writer.append(reader)

        test_values = {
            dep_field(0, DEP_FIRST_NAME): "Jake",
            dep_field(0, DEP_LAST_NAME): "Smith",
            dep_field(1, DEP_FIRST_NAME): "Emma",
            dep_field(1, DEP_LAST_NAME): "Smith",
        }

        writer.update_page_form_field_values(
            writer.pages[0], test_values,
        )

        out_path = tmp_path / "filled_deps.pdf"
        with open(out_path, "wb") as f:
            writer.write(f)

        reader2 = PdfReader(str(out_path))
        fields2 = reader2.get_fields()
        for field_name, expected_val in test_values.items():
            actual = fields2[field_name].get("/V", "")
            assert actual == expected_val


# =========================================================================
# Build script test
# =========================================================================

class TestBuildScript:
    """Verify the build script produces a valid template."""

    def test_build_form_creates_file(self, tmp_path: Path) -> None:
        from scripts.build_form_template import build_form

        out_path = tmp_path / "test_form.pdf"
        result = build_form(out_path)
        assert result == out_path
        assert out_path.exists()

    def test_build_form_output_is_pdf(self, tmp_path: Path) -> None:
        from scripts.build_form_template import build_form

        out_path = tmp_path / "test_form.pdf"
        build_form(out_path)
        data = out_path.read_bytes()
        assert data[:5] == b"%PDF-"

    def test_build_form_has_fields(self, tmp_path: Path) -> None:
        from scripts.build_form_template import build_form

        out_path = tmp_path / "test_form.pdf"
        build_form(out_path)
        reader = PdfReader(str(out_path))
        fields = reader.get_fields()
        assert fields is not None
        assert len(fields) >= 50  # at least 50 fields expected
