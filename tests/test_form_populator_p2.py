"""Tests for build_p2_field_values (Phase 3-G).

Unit tests for the Page 2 populator. Mirrors the structure of
tests/test_form_populator_p1.py: build a Household, call the
populator, assert the returned dict.

Coverage:
- Return-shape contract (bools for checkboxes, strings for counts).
- Each modeled income row: wages, retirement, SS, interest+dividends,
  self-employment, other.
- Empty-income households leave the corresponding rows unchecked
  and don't emit count entries.
- Spouse income aggregates with filer income.
- Notes / sub-question Y/N pairs / unmodeled rows are absent
  (player-input only).
"""

from __future__ import annotations

from datetime import date
from typing import Dict

import pytest

from generator.models import (
    Address,
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
from training.form_fields import (
    INCOME_DIVIDENDS,
    INCOME_INTEREST,
    INCOME_INTEREST_DIVIDENDS,
    INCOME_OTHER,
    INCOME_RETIREMENT,
    INCOME_SELF_EMPLOYMENT,
    INCOME_SOCIAL_SECURITY,
    INCOME_SS,
    INCOME_TIPS,
    INCOME_WAGES,
    INCOME_WAGES_JOBS,
    P2_NOTE_FIELDS,
    VOL_INCOME_1099B,
    VOL_INCOME_1099DIV,
    VOL_INCOME_1099DIV_COUNT,
    VOL_INCOME_1099G,
    VOL_INCOME_1099INT,
    VOL_INCOME_1099INT_COUNT,
    VOL_INCOME_1099K,
    VOL_INCOME_1099MISC,
    VOL_INCOME_1099NEC,
    VOL_INCOME_1099NEC_COUNT,
    VOL_INCOME_1099R,
    VOL_INCOME_1099R_COUNT,
    VOL_INCOME_QCD,
    VOL_INCOME_SCHEDULE_C,
    VOL_INCOME_SSA,
    VOL_INCOME_SSA_COUNT,
    VOL_INCOME_W2,
    VOL_INCOME_W2_COUNT,
)
from training.form_populator import build_p2_field_values


# =========================================================================
# Fixtures
# =========================================================================


@pytest.fixture
def empty_household() -> Household:
    """Single filer with no income (all rows should be unchecked)."""
    return Household(
        household_id="hh-empty",
        state="HI",
        year=2024,
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
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1994, 5, 15),
            ),
        ],
    )


@pytest.fixture
def wage_earner() -> Household:
    """Single filer with W-2 wages (one job)."""
    return Household(
        household_id="hh-w",
        state="HI",
        year=2024,
        pattern="single_adult",
        members=[
            Person(
                person_id="p-w",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30,
                legal_first_name="Tom",
                legal_last_name="Worker",
                ssn="900-77-8888",
                dob=date(1994, 6, 1),
                wage_income=55000,
                w2s=[W2(wages=55000)],
            ),
        ],
    )


@pytest.fixture
def diverse_income_couple() -> Household:
    """Married couple with W-2 wages, 1099-INT, 1099-DIV, 1099-R, SSA, NEC."""
    return Household(
        household_id="hh-div",
        state="HI",
        year=2024,
        pattern="married",
        members=[
            Person(
                person_id="p-h",
                relationship=RelationshipType.HOUSEHOLDER,
                age=65,
                legal_first_name="Hank",
                legal_last_name="Senior",
                ssn="900-10-0001",
                dob=date(1959, 1, 1),
                wage_income=20000,
                interest_income=300,
                dividend_income=500,
                retirement_income=15000,
                social_security_income=18000,
                self_employment_income=4000,
                w2s=[W2(wages=20000)],
                form_1099_ints=[Form1099INT(interest_income=300)],
                form_1099_divs=[Form1099DIV(ordinary_dividends=500)],
                form_1099_rs=[Form1099R(gross_distribution=15000)],
                ssa_1099=SSA1099(net_benefits=18000),
                form_1099_necs=[Form1099NEC(nonemployee_compensation=4000)],
            ),
            Person(
                person_id="p-s",
                relationship=RelationshipType.SPOUSE,
                age=63,
                legal_first_name="Sue",
                legal_last_name="Senior",
                ssn="900-10-0002",
                dob=date(1961, 4, 4),
                wage_income=30000,
                w2s=[W2(wages=30000)],
            ),
        ],
    )


# =========================================================================
# Return-shape contract
# =========================================================================


class TestReturnShape:

    def test_checkboxes_are_booleans(self, wage_earner: Household) -> None:
        p2 = build_p2_field_values(wage_earner)
        assert isinstance(p2[INCOME_WAGES], bool)
        assert isinstance(p2[VOL_INCOME_W2], bool)

    def test_counts_are_strings(self, wage_earner: Household) -> None:
        p2 = build_p2_field_values(wage_earner)
        assert isinstance(p2[VOL_INCOME_W2_COUNT], str)


# =========================================================================
# Empty-income household
# =========================================================================


class TestEmptyHousehold:

    def test_all_modeled_checkboxes_false(
        self, empty_household: Household,
    ) -> None:
        p2 = build_p2_field_values(empty_household)
        assert p2[INCOME_WAGES] is False
        assert p2[INCOME_RETIREMENT] is False
        assert p2[INCOME_SS] is False
        assert p2[INCOME_INTEREST_DIVIDENDS] is False
        assert p2[INCOME_SELF_EMPLOYMENT] is False
        assert p2[INCOME_OTHER] is False
        assert p2[VOL_INCOME_W2] is False
        assert p2[VOL_INCOME_1099R] is False
        assert p2[VOL_INCOME_SSA] is False
        assert p2[VOL_INCOME_1099INT] is False
        assert p2[VOL_INCOME_1099DIV] is False
        assert p2[VOL_INCOME_SCHEDULE_C] is False
        assert p2[VOL_INCOME_1099NEC] is False

    def test_count_fields_are_blank(
        self, empty_household: Household,
    ) -> None:
        p2 = build_p2_field_values(empty_household)
        # Counts are emitted as "" when the underlying count is zero.
        assert p2[VOL_INCOME_W2_COUNT] == ""
        assert p2[VOL_INCOME_1099R_COUNT] == ""
        assert p2[VOL_INCOME_SSA_COUNT] == ""
        assert p2[VOL_INCOME_1099INT_COUNT] == ""
        assert p2[VOL_INCOME_1099DIV_COUNT] == ""
        assert p2[VOL_INCOME_1099NEC_COUNT] == ""


# =========================================================================
# Single wage earner
# =========================================================================


class TestWageEarner:

    def test_wages_checked(self, wage_earner: Household) -> None:
        p2 = build_p2_field_values(wage_earner)
        assert p2[INCOME_WAGES] is True
        assert p2[VOL_INCOME_W2] is True

    def test_w2_count(self, wage_earner: Household) -> None:
        p2 = build_p2_field_values(wage_earner)
        assert p2[VOL_INCOME_W2_COUNT] == "1"

    def test_no_other_income(self, wage_earner: Household) -> None:
        p2 = build_p2_field_values(wage_earner)
        assert p2[INCOME_RETIREMENT] is False
        assert p2[INCOME_SS] is False
        assert p2[INCOME_INTEREST_DIVIDENDS] is False
        assert p2[INCOME_SELF_EMPLOYMENT] is False


# =========================================================================
# Diverse income (married couple)
# =========================================================================


class TestDiverseIncome:

    def test_combined_w2_count_across_filers(
        self, diverse_income_couple: Household,
    ) -> None:
        p2 = build_p2_field_values(diverse_income_couple)
        # Two W-2s total: one filer + one spouse.
        assert p2[VOL_INCOME_W2_COUNT] == "2"

    def test_retirement_with_1099r(
        self, diverse_income_couple: Household,
    ) -> None:
        p2 = build_p2_field_values(diverse_income_couple)
        assert p2[INCOME_RETIREMENT] is True
        assert p2[VOL_INCOME_1099R] is True
        assert p2[VOL_INCOME_1099R_COUNT] == "1"

    def test_social_security_with_ssa(
        self, diverse_income_couple: Household,
    ) -> None:
        p2 = build_p2_field_values(diverse_income_couple)
        assert p2[INCOME_SS] is True
        assert p2[VOL_INCOME_SSA] is True
        assert p2[VOL_INCOME_SSA_COUNT] == "1"

    def test_interest_dividends_combined(
        self, diverse_income_couple: Household,
    ) -> None:
        p2 = build_p2_field_values(diverse_income_couple)
        # Combined client checkbox fires when either side is non-zero.
        assert p2[INCOME_INTEREST_DIVIDENDS] is True
        # Volunteer column splits: both 1099-INT and 1099-DIV.
        assert p2[VOL_INCOME_1099INT] is True
        assert p2[VOL_INCOME_1099DIV] is True
        assert p2[VOL_INCOME_1099INT_COUNT] == "1"
        assert p2[VOL_INCOME_1099DIV_COUNT] == "1"

    def test_self_employment_with_1099nec(
        self, diverse_income_couple: Household,
    ) -> None:
        p2 = build_p2_field_values(diverse_income_couple)
        assert p2[INCOME_SELF_EMPLOYMENT] is True
        assert p2[VOL_INCOME_SCHEDULE_C] is True
        assert p2[VOL_INCOME_1099NEC] is True
        assert p2[VOL_INCOME_1099NEC_COUNT] == "1"

    def test_legacy_namespace_synced(
        self, diverse_income_couple: Household,
    ) -> None:
        """The combined client checkbox INCOME_INTEREST_DIVIDENDS has
        legacy split flags INCOME_INTEREST / INCOME_DIVIDENDS that
        callers reading the old namespace still depend on."""
        p2 = build_p2_field_values(diverse_income_couple)
        assert p2[INCOME_INTEREST] is True
        assert p2[INCOME_DIVIDENDS] is True
        assert p2[INCOME_SOCIAL_SECURITY] is True


# =========================================================================
# Player-input-only fields (not pre-filled)
# =========================================================================


class TestPlayerInputNotPrefilled:

    def test_notes_column_absent(self, wage_earner: Household) -> None:
        """All 14 free-form notes are ungraded; the populator never
        emits values for them."""
        p2 = build_p2_field_values(wage_earner)
        for name in P2_NOTE_FIELDS:
            assert name not in p2, f"{name} should be player-input only"

    def test_subq_pairs_absent(self, wage_earner: Household) -> None:
        """Sub-question Y/N pairs aren't in the model yet; the populator
        leaves them blank for the player."""
        p2 = build_p2_field_values(wage_earner)
        assert "income.stock_sale.prior_loss.yes" not in p2
        assert "income.rental.short_personal_residence.no" not in p2
        assert "income.self_employment.prior_loss.yes" not in p2

    def test_jobs_field_absent(self, wage_earner: Household) -> None:
        """The 'how many jobs' free-text input on row 1 is player-only."""
        p2 = build_p2_field_values(wage_earner)
        assert INCOME_WAGES_JOBS not in p2

    def test_unmodeled_income_rows_absent(
        self, wage_earner: Household,
    ) -> None:
        """Tips, unemployment, state refund, alimony, rental, gambling
        aren't modeled. The populator leaves those client-column
        checkboxes blank (absent → unchecked in the rendered template)."""
        p2 = build_p2_field_values(wage_earner)
        # Unmodeled client checkboxes are absent (default unchecked).
        assert INCOME_TIPS not in p2
        assert "income.unemployment" not in p2
        assert "income.state_refund" not in p2
        assert "income.alimony" not in p2
        assert "income.rental" not in p2
        assert "income.gambling" not in p2
        # Unmodeled QCD volunteer entry: absent.
        assert VOL_INCOME_QCD not in p2

    def test_unmodeled_volunteer_entries_explicitly_false(
        self, wage_earner: Household,
    ) -> None:
        """A handful of volunteer-column rows for unmodeled income
        types are explicitly emitted as False so the form renders an
        unchecked checkbox rather than no value at all (1099-B,
        1099-G, 1099-MISC, 1099-K)."""
        p2 = build_p2_field_values(wage_earner)
        assert p2[VOL_INCOME_1099B] is False
        assert p2[VOL_INCOME_1099G] is False
        assert p2[VOL_INCOME_1099MISC] is False
        assert p2[VOL_INCOME_1099K] is False
