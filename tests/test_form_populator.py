"""Tests for the form populator — Sprint 6 Step 2.

Validates:
- build_field_values() maps household data to correct field names/values
- populate_form() produces a valid filled PDF
- pypdf can read back the filled values (round-trip)
- Edge cases: no spouse, no dependents, multiple dependents, overrides
"""

from datetime import date
from pathlib import Path
from typing import Dict

import pytest
from pypdf import PdfReader

from generator.models import (
    Address,
    FilingStatus,
    Household,
    Person,
    RelationshipType,
)
from training.form_fields import (
    ADDR_CITY,
    ADDR_STATE,
    ADDR_STREET,
    ADDR_ZIP,
    CLAIMED_AS_DEPENDENT,
    FILING_STATUS,
    FS_HOH,
    FS_MFJ,
    FS_SINGLE,
    NOT_CLAIMED_AS_DEPENDENT,
    NOT_PRIOR_YEAR_DEPENDENT,
    PRIOR_YEAR_DEPENDENT,
    SPOUSE_DOB,
    SPOUSE_FIRST_NAME,
    SPOUSE_LAST_NAME,
    SPOUSE_SSN,
    YOU_DOB,
    YOU_EMAIL,
    YOU_FIRST_NAME,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_PHONE,
    YOU_SSN,
    YOU_US_CITIZEN,
    dep_field,
    DEP_DOB,
    DEP_FIRST_NAME,
    DEP_LAST_NAME,
    DEP_MONTHS,
    DEP_RELATIONSHIP,
    DEP_US_CITIZEN,
    DEP_STUDENT,
    MAX_DEPENDENTS,
)
from training.form_populator import (
    build_field_values,
    populate_form,
    _format_date,
    _middle_initial,
    _relationship_label,
    _get_dependents,
)

# =========================================================================
# Fixtures
# =========================================================================

TEMPLATE_PATH = (
    Path(__file__).resolve().parent.parent
    / "training" / "templates" / "form_13614c_p1.pdf"
)


@pytest.fixture
def single_adult_household() -> Household:
    """Single adult, no spouse, no dependents."""
    return Household(
        household_id="hh-single",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=Address(
            street="123 Aloha St",
            apt="4B",
            city="Honolulu",
            state="HI",
            zip_code="96816",
        ),
        members=[
            Person(
                person_id="p-001",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30,
                sex="F",
                race="asian",
                legal_first_name="Jane",
                legal_middle_name="Marie",
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                phone="(808) 555-1234",
                email="jane.doe@example.com",
                occupation_title="Teacher",
            ),
        ],
    )


@pytest.fixture
def married_household() -> Household:
    """Married couple with two children."""
    return Household(
        household_id="hh-married",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
        address=Address(
            street="456 Palm Dr",
            city="Kailua",
            state="HI",
            zip_code="96734",
        ),
        members=[
            Person(
                person_id="p-010",
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
                email="john.smith@example.com",
            ),
            Person(
                person_id="p-011",
                relationship=RelationshipType.SPOUSE,
                age=38,
                sex="F",
                race="white",
                legal_first_name="Mary",
                legal_middle_name="Ann",
                legal_last_name="Smith",
                ssn="900-22-2222",
                dob=date(1984, 7, 22),
                phone="(808) 555-8888",
            ),
            Person(
                person_id="p-012",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=10,
                sex="M",
                race="white",
                legal_first_name="Jake",
                legal_middle_name="",
                legal_last_name="Smith",
                ssn="900-33-3333",
                dob=date(2012, 1, 5),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
                is_full_time_student=False,
            ),
            Person(
                person_id="p-013",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=15,
                sex="F",
                race="white",
                legal_first_name="Emma",
                legal_middle_name="Rose",
                legal_last_name="Smith",
                ssn="900-44-4444",
                dob=date(2007, 9, 18),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
                is_full_time_student=True,
            ),
        ],
    )


@pytest.fixture
def single_parent_household() -> Household:
    """Single parent with one child — HOH filing status."""
    return Household(
        household_id="hh-hoh",
        state="HI",
        year=2022,
        pattern="single_parent",
        address=Address(
            street="789 Sunset Blvd",
            city="Waipahu",
            state="HI",
            zip_code="96797",
        ),
        members=[
            Person(
                person_id="p-020",
                relationship=RelationshipType.HOUSEHOLDER,
                age=28,
                sex="F",
                race="native_hawaiian_pacific_islander",
                legal_first_name="Leilani",
                legal_middle_name="",
                legal_last_name="Kekoa",
                ssn="900-55-5555",
                dob=date(1994, 11, 3),
                phone="(808) 555-7777",
                email="leilani@example.com",
            ),
            Person(
                person_id="p-021",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=5,
                sex="M",
                race="native_hawaiian_pacific_islander",
                legal_first_name="Kai",
                legal_middle_name="",
                legal_last_name="Kekoa",
                ssn="900-66-6666",
                dob=date(2017, 4, 12),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
            ),
        ],
    )


# =========================================================================
# Helper function tests
# =========================================================================

class TestHelpers:
    """Test utility functions."""

    def test_format_date(self) -> None:
        assert _format_date(date(1992, 5, 15)) == "05/15/1992"

    def test_format_date_none(self) -> None:
        assert _format_date(None) == ""

    def test_format_date_single_digit_month(self) -> None:
        assert _format_date(date(2000, 1, 3)) == "01/03/2000"

    def test_middle_initial(self) -> None:
        assert _middle_initial("Robert") == "R"

    def test_middle_initial_empty(self) -> None:
        assert _middle_initial("") == ""

    def test_middle_initial_lowercase(self) -> None:
        assert _middle_initial("ann") == "A"

    def test_relationship_label_bio_child(self) -> None:
        p = Person(relationship=RelationshipType.BIOLOGICAL_CHILD)
        assert _relationship_label(p) == "Son/Daughter"

    def test_relationship_label_stepchild(self) -> None:
        p = Person(relationship=RelationshipType.STEPCHILD)
        assert _relationship_label(p) == "Stepchild"

    def test_relationship_label_grandchild(self) -> None:
        p = Person(relationship=RelationshipType.GRANDCHILD)
        assert _relationship_label(p) == "Grandchild"

    def test_relationship_label_unknown(self) -> None:
        p = Person(relationship=RelationshipType.ROOMMATE)
        assert _relationship_label(p) == "Other"


class TestGetDependents:
    """Test dependent extraction and ordering."""

    def test_no_dependents(self, single_adult_household: Household) -> None:
        deps = _get_dependents(single_adult_household)
        assert deps == []

    def test_dependents_sorted_by_age(self, married_household: Household) -> None:
        deps = _get_dependents(married_household)
        assert len(deps) == 2
        # Oldest first
        assert deps[0].legal_first_name == "Emma"  # age 15
        assert deps[1].legal_first_name == "Jake"  # age 10

    def test_capped_at_max_dependents(self) -> None:
        hh = Household(
            household_id="hh-many",
            state="HI",
            year=2022,
            pattern="other",
            members=[
                Person(
                    person_id=f"p-{i}",
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    age=i + 1,
                    is_dependent=True,
                    can_be_claimed=True,
                )
                for i in range(6)
            ],
        )
        deps = _get_dependents(hh)
        assert len(deps) == MAX_DEPENDENTS


# =========================================================================
# build_field_values tests
# =========================================================================

class TestBuildFieldValues:
    """Test the household → field value mapping."""

    def test_single_adult_section_a(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert vals[YOU_FIRST_NAME] == "Jane"
        assert vals[YOU_MIDDLE_INITIAL] == "M"
        assert vals[YOU_LAST_NAME] == "Doe"
        assert vals[YOU_DOB] == "05/15/1992"
        assert vals[YOU_SSN] == "900-12-3456"
        assert vals[YOU_PHONE] == "(808) 555-1234"
        assert vals[YOU_EMAIL] == "jane.doe@example.com"
        assert vals[YOU_US_CITIZEN] == "Yes"

    def test_single_adult_section_b(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert vals[ADDR_STREET] == "123 Aloha St"
        assert vals[ADDR_CITY] == "Honolulu"
        assert vals[ADDR_STATE] == "HI"
        assert vals[ADDR_ZIP] == "96816"

    def test_single_adult_no_spouse(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert SPOUSE_FIRST_NAME not in vals
        assert SPOUSE_SSN not in vals

    def test_single_adult_filing_status(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert vals[FILING_STATUS] == FS_SINGLE

    def test_single_adult_no_dependents(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert dep_field(0, DEP_FIRST_NAME) not in vals

    def test_married_spouse_fields(
        self, married_household: Household,
    ) -> None:
        vals = build_field_values(married_household)
        assert vals[SPOUSE_FIRST_NAME] == "Mary"
        assert vals[SPOUSE_LAST_NAME] == "Smith"
        assert vals[SPOUSE_DOB] == "07/22/1984"
        assert vals[SPOUSE_SSN] == "900-22-2222"

    def test_married_filing_jointly(
        self, married_household: Household,
    ) -> None:
        vals = build_field_values(married_household)
        assert vals[FILING_STATUS] == FS_MFJ

    def test_dependents_populated(
        self, married_household: Household,
    ) -> None:
        vals = build_field_values(married_household)
        # First row = Emma (older)
        assert vals[dep_field(0, DEP_FIRST_NAME)] == "Emma"
        assert vals[dep_field(0, DEP_LAST_NAME)] == "Smith"
        assert vals[dep_field(0, DEP_DOB)] == "09/18/2007"
        assert vals[dep_field(0, DEP_RELATIONSHIP)] == "Son/Daughter"
        assert vals[dep_field(0, DEP_MONTHS)] == "12"
        assert vals[dep_field(0, DEP_US_CITIZEN)] == "Yes"
        assert vals[dep_field(0, DEP_STUDENT)] == "Yes"

        # Second row = Jake (younger)
        assert vals[dep_field(1, DEP_FIRST_NAME)] == "Jake"
        assert vals[dep_field(1, DEP_STUDENT)] == ""

    def test_hoh_filing_status(
        self, single_parent_household: Household,
    ) -> None:
        vals = build_field_values(single_parent_household)
        assert vals[FILING_STATUS] == FS_HOH

    def test_not_claimed_as_dependent(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert NOT_CLAIMED_AS_DEPENDENT in vals
        assert CLAIMED_AS_DEPENDENT not in vals

    def test_claimed_as_dependent(self) -> None:
        hh = Household(
            household_id="hh-dep",
            state="HI",
            year=2022,
            pattern="single_adult",
            members=[
                Person(
                    person_id="p-099",
                    relationship=RelationshipType.HOUSEHOLDER,
                    age=20,
                    can_be_claimed=True,
                    legal_first_name="Young",
                    legal_last_name="Adult",
                    ssn="900-99-9999",
                ),
            ],
        )
        vals = build_field_values(hh)
        assert vals[CLAIMED_AS_DEPENDENT] == "Yes"
        assert NOT_CLAIMED_AS_DEPENDENT not in vals

    def test_prior_year_default_no(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert vals[NOT_PRIOR_YEAR_DEPENDENT] == "Yes"
        assert PRIOR_YEAR_DEPENDENT not in vals

    def test_no_address(self) -> None:
        hh = Household(
            household_id="hh-noaddr",
            state="HI",
            year=2022,
            pattern="single_adult",
            members=[
                Person(
                    person_id="p-100",
                    relationship=RelationshipType.HOUSEHOLDER,
                    age=25,
                    legal_first_name="Test",
                    legal_last_name="Person",
                    ssn="900-00-0000",
                ),
            ],
        )
        vals = build_field_values(hh)
        assert ADDR_STREET not in vals

    def test_job_title_from_occupation(
        self, single_adult_household: Household,
    ) -> None:
        vals = build_field_values(single_adult_household)
        assert vals.get("you.job_title") == "Teacher"

    def test_apt_empty_when_none(self, married_household: Household) -> None:
        vals = build_field_values(married_household)
        assert vals.get("addr.apt") == ""


# =========================================================================
# populate_form PDF round-trip tests
# =========================================================================

class TestPopulateForm:
    """Test populate_form() end-to-end with PDF round-trip."""

    def test_creates_file(
        self, tmp_path: Path, single_adult_household: Household,
    ) -> None:
        out = tmp_path / "filled.pdf"
        result = populate_form(single_adult_household, out)
        assert result == out
        assert out.exists()

    def test_output_is_pdf(
        self, tmp_path: Path, single_adult_household: Household,
    ) -> None:
        out = tmp_path / "filled.pdf"
        populate_form(single_adult_household, out)
        assert out.read_bytes()[:5] == b"%PDF-"

    def test_roundtrip_text_fields(
        self, tmp_path: Path, single_adult_household: Household,
    ) -> None:
        out = tmp_path / "filled.pdf"
        populate_form(single_adult_household, out)

        reader = PdfReader(str(out))
        fields = reader.get_fields()
        assert fields is not None

        assert fields[YOU_FIRST_NAME].get("/V") == "Jane"
        assert fields[YOU_LAST_NAME].get("/V") == "Doe"
        assert fields[YOU_DOB].get("/V") == "05/15/1992"
        assert fields[YOU_SSN].get("/V") == "900-12-3456"
        assert fields[ADDR_STREET].get("/V") == "123 Aloha St"
        assert fields[ADDR_CITY].get("/V") == "Honolulu"

    def test_roundtrip_spouse_fields(
        self, tmp_path: Path, married_household: Household,
    ) -> None:
        out = tmp_path / "filled.pdf"
        populate_form(married_household, out)

        reader = PdfReader(str(out))
        fields = reader.get_fields()
        assert fields[SPOUSE_FIRST_NAME].get("/V") == "Mary"
        assert fields[SPOUSE_SSN].get("/V") == "900-22-2222"

    def test_roundtrip_dependent_fields(
        self, tmp_path: Path, married_household: Household,
    ) -> None:
        out = tmp_path / "filled.pdf"
        populate_form(married_household, out)

        reader = PdfReader(str(out))
        fields = reader.get_fields()
        # First dependent row = Emma (older)
        assert fields[dep_field(0, DEP_FIRST_NAME)].get("/V") == "Emma"
        assert fields[dep_field(1, DEP_FIRST_NAME)].get("/V") == "Jake"

    def test_field_overrides(
        self, tmp_path: Path, single_adult_household: Household,
    ) -> None:
        out = tmp_path / "override.pdf"
        populate_form(
            single_adult_household, out,
            field_overrides={YOU_FIRST_NAME: "WRONG_NAME"},
        )

        reader = PdfReader(str(out))
        fields = reader.get_fields()
        assert fields[YOU_FIRST_NAME].get("/V") == "WRONG_NAME"

    def test_creates_parent_dirs(
        self, tmp_path: Path, single_adult_household: Household,
    ) -> None:
        out = tmp_path / "deep" / "nested" / "dir" / "form.pdf"
        populate_form(single_adult_household, out)
        assert out.exists()

    def test_missing_template_raises(
        self, tmp_path: Path, single_adult_household: Household,
    ) -> None:
        out = tmp_path / "form.pdf"
        with pytest.raises(FileNotFoundError, match="Template not found"):
            populate_form(
                single_adult_household, out,
                template_path=Path("/nonexistent/template.pdf"),
            )
