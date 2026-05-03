"""Tests for build_p3_field_values (Phase 4-G).

Unit tests for the Page 3 populator. Mirrors the structure of
tests/test_form_populator_p2.py: build a Household, call the
populator, assert the returned dict.

Coverage:
- Return-shape contract (bools for checkboxes, strings for counts).
- Each modeled expense row: medical, mortgage + 1098, taxes,
  charitable, child care, educator, IRA, student loan + 1098-E.
- Standard / itemized deduction toggle.
- Empty-expense household leaves rows unchecked + counts blank.
- Unmodeled rows (alimony, retirement_contrib, all 12 events) stay
  blank for the player to fill in.
- Notes column is never pre-filled.
"""

from __future__ import annotations

from datetime import date

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
)
from training.form_fields import (
    EVENT_BROUGHT_PRIOR_RETURN,
    EVENT_DEBT_CANCELLED,
    EVENT_DISASTER_LOSS,
    EVENT_EDUCATION,
    EVENT_ENERGY_HOME,
    EVENT_HSA,
    EVENT_MARKETPLACE,
    EVENT_OTHER_PURCHASE,
    EVENT_SELL_HOME,
    EXPENSE_ALIMONY_PAID,
    EXPENSE_CHARITABLE,
    EXPENSE_CHILD_CARE,
    EXPENSE_EDUCATOR,
    EXPENSE_MEDICAL,
    EXPENSE_MORTGAGE_INTEREST,
    EXPENSE_RETIREMENT_CONTRIB,
    EXPENSE_STUDENT_LOAN,
    EXPENSE_TAXES_NEW,
    P3_NOTE_FIELDS,
    VOL_EVENT_1095A,
    VOL_EVENT_1099A,
    VOL_EVENT_HSA_CONTRIBUTIONS,
    VOL_EXPENSE_1098,
    VOL_EXPENSE_1098_COUNT,
    VOL_EXPENSE_1098E,
    VOL_EXPENSE_CHILD_CARE_CREDIT,
    VOL_EXPENSE_EDUCATOR,
    VOL_EXPENSE_EDUCATOR_AMOUNT,
    VOL_EXPENSE_IRA,
    VOL_EXPENSE_ITEMIZED_DEDUCTION,
    VOL_EXPENSE_STANDARD_DEDUCTION,
)
from training.form_populator import build_p3_field_values


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def empty_household() -> Household:
    """Single filer with no expenses; defaults to standard deduction."""
    return Household(
        household_id="hh-empty",
        state="HI", year=2024, pattern="single_adult",
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
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1994, 5, 15),
            ),
        ],
        uses_standard_deduction=True,
    )


@pytest.fixture
def itemizer_household() -> Household:
    """Household with mortgage + property tax + charitable, itemizing."""
    return Household(
        household_id="hh-it",
        state="HI", year=2024, pattern="single_adult",
        members=[
            Person(
                person_id="p-it",
                relationship=RelationshipType.HOUSEHOLDER,
                age=42,
                legal_first_name="Ivy",
                legal_last_name="Tax",
                ssn="900-77-7777",
                dob=date(1982, 1, 1),
                educator_expenses=300,
                ira_contributions=4000,
                student_loan_interest=900,
            ),
        ],
        mortgage_interest=12000,
        property_taxes=4500,
        state_income_tax=2000,
        medical_expenses=1500,
        charitable_contributions=2200,
        child_care_expenses=3000,
        uses_standard_deduction=False,
    )


# =========================================================================
# Return-shape contract
# =========================================================================


class TestReturnShape:

    def test_checkboxes_are_booleans(self, itemizer_household: Household) -> None:
        p3 = build_p3_field_values(itemizer_household)
        assert isinstance(p3[EXPENSE_MORTGAGE_INTEREST], bool)
        assert isinstance(p3[VOL_EXPENSE_1098], bool)
        assert isinstance(p3[VOL_EXPENSE_STANDARD_DEDUCTION], bool)

    def test_counts_and_amounts_are_strings(
        self, itemizer_household: Household,
    ) -> None:
        p3 = build_p3_field_values(itemizer_household)
        assert isinstance(p3[VOL_EXPENSE_1098_COUNT], str)
        assert isinstance(p3[VOL_EXPENSE_EDUCATOR_AMOUNT], str)


# =========================================================================
# Empty-expense household
# =========================================================================


class TestEmptyHousehold:

    def test_all_modeled_checkboxes_false(
        self, empty_household: Household,
    ) -> None:
        p3 = build_p3_field_values(empty_household)
        assert p3[EXPENSE_MEDICAL] is False
        assert p3[EXPENSE_MORTGAGE_INTEREST] is False
        assert p3[EXPENSE_TAXES_NEW] is False
        assert p3[EXPENSE_CHARITABLE] is False
        assert p3[EXPENSE_CHILD_CARE] is False
        assert p3[EXPENSE_EDUCATOR] is False
        assert p3[EXPENSE_STUDENT_LOAN] is False
        assert p3[VOL_EXPENSE_1098] is False
        assert p3[VOL_EXPENSE_1098E] is False
        assert p3[VOL_EXPENSE_CHILD_CARE_CREDIT] is False
        assert p3[VOL_EXPENSE_EDUCATOR] is False
        assert p3[VOL_EXPENSE_IRA] is False

    def test_default_to_standard_deduction(
        self, empty_household: Household,
    ) -> None:
        p3 = build_p3_field_values(empty_household)
        assert p3[VOL_EXPENSE_STANDARD_DEDUCTION] is True
        assert p3[VOL_EXPENSE_ITEMIZED_DEDUCTION] is False

    def test_count_and_amount_fields_blank(
        self, empty_household: Household,
    ) -> None:
        p3 = build_p3_field_values(empty_household)
        assert p3[VOL_EXPENSE_1098_COUNT] == ""
        assert p3[VOL_EXPENSE_EDUCATOR_AMOUNT] == ""


# =========================================================================
# Itemizer household
# =========================================================================


class TestItemizerHousehold:

    def test_itemize_section_checked(
        self, itemizer_household: Household,
    ) -> None:
        p3 = build_p3_field_values(itemizer_household)
        assert p3[EXPENSE_MEDICAL] is True
        assert p3[EXPENSE_MORTGAGE_INTEREST] is True
        assert p3[EXPENSE_TAXES_NEW] is True  # property + state income
        assert p3[EXPENSE_CHARITABLE] is True

    def test_1098_count_for_mortgage(
        self, itemizer_household: Household,
    ) -> None:
        p3 = build_p3_field_values(itemizer_household)
        assert p3[VOL_EXPENSE_1098] is True
        # Single 1098 per household when mortgage interest is present.
        assert p3[VOL_EXPENSE_1098_COUNT] == "1"

    def test_itemized_deduction_selected(
        self, itemizer_household: Household,
    ) -> None:
        p3 = build_p3_field_values(itemizer_household)
        assert p3[VOL_EXPENSE_STANDARD_DEDUCTION] is False
        assert p3[VOL_EXPENSE_ITEMIZED_DEDUCTION] is True

    def test_other_expenses_section(
        self, itemizer_household: Household,
    ) -> None:
        p3 = build_p3_field_values(itemizer_household)
        assert p3[EXPENSE_CHILD_CARE] is True
        assert p3[VOL_EXPENSE_CHILD_CARE_CREDIT] is True
        assert p3[EXPENSE_EDUCATOR] is True
        assert p3[VOL_EXPENSE_EDUCATOR] is True
        assert p3[VOL_EXPENSE_EDUCATOR_AMOUNT] == "300"
        assert p3[VOL_EXPENSE_IRA] is True
        assert p3[EXPENSE_STUDENT_LOAN] is True
        assert p3[VOL_EXPENSE_1098E] is True

    def test_taxes_fires_on_state_income_alone(self) -> None:
        """EXPENSE_TAXES_NEW is True when state_income_tax is non-zero
        even if property_taxes is zero (the new template's "taxes" row
        covers state income, local, real estate, sales — broader than
        the legacy property-only EXPENSE_PROPERTY_TAXES)."""
        hh = Household(
            household_id="hh-state-only",
            state="HI", year=2024, pattern="single_adult",
            members=[
                Person(
                    person_id="p", relationship=RelationshipType.HOUSEHOLDER,
                    age=30, legal_first_name="A", legal_last_name="B",
                    ssn="900-00-0001", dob=date(1994, 1, 1),
                ),
            ],
            state_income_tax=1500,
            uses_standard_deduction=True,
        )
        p3 = build_p3_field_values(hh)
        assert p3[EXPENSE_TAXES_NEW] is True


# =========================================================================
# Player-input-only fields (not pre-filled)
# =========================================================================


class TestPlayerInputNotPrefilled:

    def test_notes_column_absent(
        self, itemizer_household: Household,
    ) -> None:
        """All 18 free-form notes are ungraded; the populator never
        emits values for them."""
        p3 = build_p3_field_values(itemizer_household)
        for name in P3_NOTE_FIELDS:
            assert name not in p3, f"{name} should be player-input only"

    def test_unmodeled_rows_absent(
        self, itemizer_household: Household,
    ) -> None:
        """Alimony and retirement_contrib aren't fully modeled; the
        client checkboxes are never pre-filled."""
        p3 = build_p3_field_values(itemizer_household)
        assert EXPENSE_ALIMONY_PAID not in p3
        # retirement_contrib explicitly emitted as False (IRS form
        # excludes IRA, which is the only retirement source modeled).
        assert p3[EXPENSE_RETIREMENT_CONTRIB] is False

    def test_event_section_absent(
        self, itemizer_household: Household,
    ) -> None:
        """All 12 Tax Related Events client checkboxes + their volunteer
        follow-ups are unmodeled and stay blank."""
        p3 = build_p3_field_values(itemizer_household)
        for name in (
            EVENT_BROUGHT_PRIOR_RETURN,
            EVENT_EDUCATION,
            EVENT_HSA,
            EVENT_MARKETPLACE,
            EVENT_SELL_HOME,
            EVENT_OTHER_PURCHASE,
            EVENT_DEBT_CANCELLED,
            EVENT_DISASTER_LOSS,
            EVENT_ENERGY_HOME,
            VOL_EVENT_1095A,
            VOL_EVENT_1099A,
            VOL_EVENT_HSA_CONTRIBUTIONS,
        ):
            assert name not in p3, f"{name} should be player-input only"
