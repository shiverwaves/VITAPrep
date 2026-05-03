"""Tests for build_p1_field_values (Phase 1B extend).

Focused on the new Page 1 populator that drives the Jinja partial:
- Returns a mixed dict (strings for text inputs, bools for checkboxes).
- Status trios fire correctly (filer / spouse / no logic).
- Marital section reflects household state.
- Volunteer columns are intentionally absent.
- Dependent rows use full_legal_name() and one-letter Y/N text values.
- Player-input-only fields are not pre-filled.

Existing fixtures from tests/test_form_populator.py provide the
households; we re-import them here rather than duplicating.
"""

from datetime import date
from typing import Dict

import pytest

from generator.models import (
    Address,
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
    DEP_DISABLED,
    DEP_DOB,
    DEP_IPPIN,
    DEP_MARITAL_EOY,
    DEP_NAME,
    DEP_RESIDENT,
    DEP_STUDENT,
    DEP_US_CITIZEN,
    DEP_VOL_HOME_COST,
    DEP_VOL_INCOME_UNDER,
    DEP_VOL_QC_OTHER,
    DEP_VOL_SELF_SUPPORT,
    DEP_VOL_SUPPORT,
    ELECTION_NO,
    ELECTION_YOU,
    FILER_DIGITAL_ASSETS,
    FILER_DISABLED,
    FILER_IPPIN,
    FILER_LEGALLY_BLIND,
    FILER_ON_VISA,
    LANG_PREF_LANGUAGE,
    LANG_PREF_NO,
    MARITAL_DIVORCE_DATE,
    MARITAL_DIVORCED,
    MARITAL_LIVED_APART_NO,
    MARITAL_LIVED_APART_YES,
    MARITAL_MARRIED,
    MARITAL_MARRIED_EOY_YES,
    MARITAL_NEVER_MARRIED,
    MARITAL_SEPARATION_DATE,
    MARITAL_SPOUSE_DEATH_YEAR,
    MARITAL_WIDOWED,
    NOT_CLAIMED_AS_DEPENDENT,
    PAYMENT_BANK,
    REFUND_DIRECT_DEPOSIT,
    SPOUSE_DOB,
    SPOUSE_FIRST_NAME,
    SPOUSE_LAST_NAME,
    SPOUSE_PHONE,
    SPOUSE_US_CITIZEN,
    STATUS_BLIND_NO,
    STATUS_CITIZEN_NO,
    STATUS_DIGITAL_NO,
    TWO_STATES_NO,
    TWO_STATES_YES,
    YOU_DOB,
    YOU_EMAIL,
    YOU_FIRST_NAME,
    YOU_LAST_NAME,
    YOU_MIDDLE_INITIAL,
    YOU_PHONE,
    YOU_US_CITIZEN,
    dep_field,
)
from training.form_populator import build_p1_field_values


# =========================================================================
# Fixtures (mirror the patterns in tests/test_form_populator.py)
# =========================================================================


@pytest.fixture
def single_household() -> Household:
    return Household(
        household_id="hh-s1",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=Address(
            street="100 Aloha St", city="Honolulu",
            state="HI", zip_code="96816",
        ),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30,
                legal_first_name="Jane",
                legal_middle_name="Marie",
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                phone="(808) 555-1234",
                email="jane@example.com",
                occupation_title="Engineer",
            ),
        ],
    )


@pytest.fixture
def married_with_kids() -> Household:
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
                legal_first_name="John",
                legal_middle_name="Robert",
                legal_last_name="Smith",
                ssn="900-11-1111",
                dob=date(1982, 3, 10),
                phone="(808) 555-9999",
                email="john@example.com",
                occupation_title="Cook",
            ),
            Person(
                person_id="p-11",
                relationship=RelationshipType.SPOUSE,
                age=38,
                legal_first_name="Mary",
                legal_middle_name="Lynn",
                legal_last_name="Smith",
                ssn="900-22-2222",
                dob=date(1984, 7, 22),
                phone="(808) 555-8888",
                occupation_title="Cashier",
            ),
            Person(
                person_id="p-12",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=10,
                legal_first_name="Jake",
                legal_last_name="Smith",
                dob=date(2012, 1, 5),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
            ),
        ],
    )


# =========================================================================
# Return-shape contract
# =========================================================================


class TestReturnShape:
    """build_p1_field_values returns mixed-type dict (strings / bools)."""

    def test_text_fields_are_strings(self, single_household: Household) -> None:
        p1 = build_p1_field_values(single_household)
        assert isinstance(p1[YOU_FIRST_NAME], str)
        assert isinstance(p1[ADDR_STREET], str)
        assert isinstance(p1[YOU_DOB], str)

    def test_checkboxes_are_booleans(self, single_household: Household) -> None:
        p1 = build_p1_field_values(single_household)
        assert isinstance(p1[YOU_US_CITIZEN], bool)
        assert isinstance(p1[STATUS_CITIZEN_NO], bool)
        assert isinstance(p1[MARITAL_NEVER_MARRIED], bool)


# =========================================================================
# Filer / spouse / address text fields
# =========================================================================


class TestFilerSpouseAddress:

    def test_filer_basic(self, single_household: Household) -> None:
        p1 = build_p1_field_values(single_household)
        assert p1[YOU_FIRST_NAME] == "Jane"
        assert p1[YOU_MIDDLE_INITIAL] == "M"
        assert p1[YOU_LAST_NAME] == "Doe"
        assert p1[YOU_DOB] == "05/15/1992"
        assert p1[YOU_PHONE] == "(808) 555-1234"
        assert p1[YOU_EMAIL] == "jane@example.com"

    def test_address(self, single_household: Household) -> None:
        p1 = build_p1_field_values(single_household)
        assert p1[ADDR_STREET] == "100 Aloha St"
        assert p1[ADDR_CITY] == "Honolulu"
        assert p1[ADDR_STATE] == "HI"
        assert p1[ADDR_ZIP] == "96816"

    def test_spouse_absent(self, single_household: Household) -> None:
        """Single adult: no spouse fields emitted at all."""
        p1 = build_p1_field_values(single_household)
        assert SPOUSE_FIRST_NAME not in p1
        assert SPOUSE_LAST_NAME not in p1
        assert SPOUSE_DOB not in p1
        assert SPOUSE_PHONE not in p1

    def test_spouse_present(self, married_with_kids: Household) -> None:
        p1 = build_p1_field_values(married_with_kids)
        assert p1[SPOUSE_FIRST_NAME] == "Mary"
        assert p1[SPOUSE_LAST_NAME] == "Smith"
        assert p1[SPOUSE_DOB] == "07/22/1984"
        assert p1[SPOUSE_PHONE] == "(808) 555-8888"


# =========================================================================
# Section 6: status trios
# =========================================================================


class TestStatusTrios:
    """Each status row has filer / spouse / no checkboxes; the "no" cell
    is checked iff neither person has the flag."""

    def test_default_citizens(self, married_with_kids: Household) -> None:
        """us_citizen defaults True on Person → both checked, no unchecked."""
        p1 = build_p1_field_values(married_with_kids)
        assert p1[YOU_US_CITIZEN] is True
        assert p1[SPOUSE_US_CITIZEN] is True
        assert p1[STATUS_CITIZEN_NO] is False

    def test_neither_legally_blind(self, married_with_kids: Household) -> None:
        """legally_blind defaults False → neither checked, no checked."""
        p1 = build_p1_field_values(married_with_kids)
        assert p1[FILER_LEGALLY_BLIND] is False
        assert p1[STATUS_BLIND_NO] is True

    def test_filer_only_disabled(self, married_with_kids: Household) -> None:
        """When only the filer has the flag, filer is checked; no is unchecked."""
        married_with_kids.get_householder().has_disability = True
        p1 = build_p1_field_values(married_with_kids)
        assert p1[FILER_DISABLED] is True
        assert "spouse.disabled" in p1
        assert p1["spouse.disabled"] is False
        # "no" must be unchecked because the filer DOES have it.
        assert p1["disabled_no"] is False

    def test_single_filer_no_spouse_branch(
        self, single_household: Household,
    ) -> None:
        """Single filer (no spouse): spouse_X always False; "no" is True
        when filer doesn't have the flag."""
        p1 = build_p1_field_values(single_household)
        # legally_blind defaults False on a single filer.
        assert p1[FILER_LEGALLY_BLIND] is False
        assert p1[STATUS_BLIND_NO] is True
        # us_citizen defaults True, so filer checked, no unchecked.
        assert p1[YOU_US_CITIZEN] is True
        assert p1[STATUS_CITIZEN_NO] is False

    def test_household_digital_assets(
        self, married_with_kids: Household,
    ) -> None:
        """has_digital_assets is a household-level flag; mirrored to
        filer + spouse cells when set."""
        married_with_kids.has_digital_assets = True
        p1 = build_p1_field_values(married_with_kids)
        assert p1[FILER_DIGITAL_ASSETS] is True
        assert p1[STATUS_DIGITAL_NO] is False


# =========================================================================
# Section 5: claimable
# =========================================================================


class TestClaimable:

    def test_default_not_claimable(self, single_household: Household) -> None:
        p1 = build_p1_field_values(single_household)
        assert p1[CLAIMED_AS_DEPENDENT] is False
        assert p1[NOT_CLAIMED_AS_DEPENDENT] is True

    def test_can_be_claimed(self, single_household: Household) -> None:
        single_household.get_householder().can_be_claimed = True
        p1 = build_p1_field_values(single_household)
        assert p1[CLAIMED_AS_DEPENDENT] is True
        assert p1[NOT_CLAIMED_AS_DEPENDENT] is False


# =========================================================================
# Section 10: marital
# =========================================================================


class TestMarital:

    def test_single_never_married(self, single_household: Household) -> None:
        p1 = build_p1_field_values(single_household)
        assert p1[MARITAL_NEVER_MARRIED] is True
        assert p1[MARITAL_MARRIED] is False
        assert p1[MARITAL_DIVORCED] is False
        assert p1[MARITAL_WIDOWED] is False
        # EOY follow-ups don't apply when not married.
        assert p1[MARITAL_MARRIED_EOY_YES] is False
        assert p1[MARITAL_LIVED_APART_YES] is False
        assert p1[MARITAL_LIVED_APART_NO] is False

    def test_married(self, married_with_kids: Household) -> None:
        p1 = build_p1_field_values(married_with_kids)
        assert p1[MARITAL_MARRIED] is True
        assert p1[MARITAL_NEVER_MARRIED] is False
        assert p1[MARITAL_MARRIED_EOY_YES] is True
        # Default lived-apart-h2 is False → "no" checked, "yes" unchecked.
        assert p1[MARITAL_LIVED_APART_NO] is True
        assert p1[MARITAL_LIVED_APART_YES] is False

    def test_lived_apart_h2(self, married_with_kids: Household) -> None:
        married_with_kids.spouses_lived_apart_h2 = True
        p1 = build_p1_field_values(married_with_kids)
        assert p1[MARITAL_LIVED_APART_YES] is True
        assert p1[MARITAL_LIVED_APART_NO] is False

    def test_widowed_with_year(self, single_household: Household) -> None:
        single_household.get_householder().marital_history = "widowed"
        single_household.spouse_death_year = 2023
        p1 = build_p1_field_values(single_household)
        assert p1[MARITAL_WIDOWED] is True
        assert p1[MARITAL_NEVER_MARRIED] is False
        assert p1[MARITAL_SPOUSE_DEATH_YEAR] == "2023"

    def test_divorced_with_date(self, single_household: Household) -> None:
        single_household.get_householder().marital_history = "divorced"
        single_household.divorce_date = date(2024, 6, 15)
        p1 = build_p1_field_values(single_household)
        assert p1[MARITAL_DIVORCED] is True
        assert p1[MARITAL_DIVORCE_DATE] == "06/15/2024"


# =========================================================================
# Section 4 follow-up: two-states question
# =========================================================================


class TestTwoStates:

    def test_default_no(self, single_household: Household) -> None:
        p1 = build_p1_field_values(single_household)
        assert p1[TWO_STATES_NO] is True
        assert p1[TWO_STATES_YES] is False

    def test_lived_in_two(self, single_household: Household) -> None:
        single_household.lived_in_two_states = True
        p1 = build_p1_field_values(single_household)
        assert p1[TWO_STATES_YES] is True
        assert p1[TWO_STATES_NO] is False


# =========================================================================
# Player-input fields are NOT pre-filled
# =========================================================================


class TestPlayerInputNotPrefilled:
    """Refund / payment / language / election checkboxes are
    taxpayer-decision fields with no household-derivable answer.
    They must NOT appear in the populator's output."""

    def test_refund_options_absent(self, married_with_kids: Household) -> None:
        p1 = build_p1_field_values(married_with_kids)
        assert REFUND_DIRECT_DEPOSIT not in p1

    def test_payment_options_absent(
        self, married_with_kids: Household,
    ) -> None:
        p1 = build_p1_field_values(married_with_kids)
        assert PAYMENT_BANK not in p1

    def test_language_pref_absent(
        self, married_with_kids: Household,
    ) -> None:
        p1 = build_p1_field_values(married_with_kids)
        assert LANG_PREF_LANGUAGE not in p1
        assert LANG_PREF_NO not in p1

    def test_election_absent(self, married_with_kids: Household) -> None:
        p1 = build_p1_field_values(married_with_kids)
        assert ELECTION_YOU not in p1
        assert ELECTION_NO not in p1


# =========================================================================
# Section 11: dependents
# =========================================================================


class TestDependents:

    def test_dep_uses_full_legal_name(
        self, married_with_kids: Household,
    ) -> None:
        """dep.{i}.name carries full_legal_name(), not split first/last."""
        p1 = build_p1_field_values(married_with_kids)
        assert p1[dep_field(0, DEP_NAME)] == "Jake Smith"

    def test_dep_basic_text_cells(
        self, married_with_kids: Household,
    ) -> None:
        p1 = build_p1_field_values(married_with_kids)
        assert p1[dep_field(0, DEP_DOB)] == "01/05/2012"
        assert p1[dep_field(0, "relationship")] == "Son/Daughter"
        assert p1[dep_field(0, "months")] == "12"

    def test_dep_yn_uses_one_letter(
        self, married_with_kids: Household,
    ) -> None:
        """The new template's Y/N text columns use one-letter values
        to match the column hints."""
        p1 = build_p1_field_values(married_with_kids)
        assert p1[dep_field(0, DEP_US_CITIZEN)] == "Y"
        assert p1[dep_field(0, DEP_RESIDENT)] == "Y"
        # Jake is not a full-time student → blank, not "N".
        assert p1[dep_field(0, DEP_STUDENT)] == ""

    def test_dep_marital_eoy_default_s(
        self, married_with_kids: Household,
    ) -> None:
        """Children are S (single) by default."""
        p1 = build_p1_field_values(married_with_kids)
        assert p1[dep_field(0, DEP_MARITAL_EOY)] == "S"

    def test_volunteer_columns_not_emitted(
        self, married_with_kids: Household,
    ) -> None:
        """All five vol_* columns are player-input — populator skips them."""
        p1 = build_p1_field_values(married_with_kids)
        for col in (
            DEP_VOL_QC_OTHER,
            DEP_VOL_SELF_SUPPORT,
            DEP_VOL_INCOME_UNDER,
            DEP_VOL_SUPPORT,
            DEP_VOL_HOME_COST,
        ):
            assert dep_field(0, col) not in p1, (
                f"{col} should not be pre-filled — it's a volunteer column"
            )

    def test_unused_dep_slots_have_no_keys(
        self, single_household: Household,
    ) -> None:
        """Single household has no dependents → no dep.0.* keys."""
        p1 = build_p1_field_values(single_household)
        for i in range(4):
            assert dep_field(i, DEP_NAME) not in p1
