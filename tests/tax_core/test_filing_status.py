"""Tests for tax_core.predicates.filing_status predicates.

4 predicates tested:
- derive_filing_status (stub)
- is_unmarried (stub)
- paid_more_than_half_household_costs (stub)
- has_qualifying_person_for_hoh (stub)
"""

import pytest
from types import SimpleNamespace

from tax_core.predicates.filing_status import (
    derive_filing_status,
    is_unmarried,
    paid_more_than_half_household_costs,
    has_qualifying_person_for_hoh,
)


def _household(adults, children=None):
    """Build a minimal household-like object for testing."""
    children = children or []
    members = adults + children
    has_spouse = any(
        getattr(p, "relationship", None) in ("spouse",)
        or (hasattr(p, "relationship") and hasattr(p.relationship, "value")
            and p.relationship.value == "spouse")
        for p in members
    )
    return SimpleNamespace(
        members=members,
        is_married=lambda: has_spouse,
        get_children=lambda: children,
        get_adults=lambda: adults,
    )


def _adult(**kwargs):
    defaults = {"age": 35, "relationship": "householder"}
    defaults.update(kwargs)
    p = SimpleNamespace(**defaults)
    p.is_adult = lambda: p.age >= 18
    p.is_child = lambda: p.age < 18
    return p


def _child(**kwargs):
    defaults = {"age": 10, "relationship": "biological_child", "months_in_home": 12}
    defaults.update(kwargs)
    p = SimpleNamespace(**defaults)
    p.is_adult = lambda: p.age >= 18
    p.is_child = lambda: p.age < 18
    return p


# ── derive_filing_status ──────────────────────────────────────────────

class TestDeriveFilingStatus:
    def test_married_couple_returns_mfj(self):
        hh = _household(
            [_adult(), _adult(relationship="spouse")],
        )
        assert derive_filing_status(hh) == "married_filing_jointly"

    def test_single_with_children_returns_hoh(self):
        hh = _household([_adult()], [_child()])
        assert derive_filing_status(hh) == "head_of_household"

    def test_single_no_children_returns_single(self):
        hh = _household([_adult()])
        assert derive_filing_status(hh) == "single"

    def test_married_with_children_returns_mfj(self):
        hh = _household(
            [_adult(), _adult(relationship="spouse")],
            [_child(), _child()],
        )
        assert derive_filing_status(hh) == "married_filing_jointly"


# ── is_unmarried ──────────────────────────────────────────────────────

class TestIsUnmarried:
    def test_single_person_is_unmarried(self):
        filer = _adult()
        filer._household = _household([filer])
        assert is_unmarried(filer, 2022) is True

    def test_married_person_is_not_unmarried(self):
        spouse = _adult(relationship="spouse")
        filer = _adult()
        filer._household = _household([filer, spouse])
        assert is_unmarried(filer, 2022) is False

    def test_no_household_ref_uses_relationship(self):
        filer = _adult(relationship="householder")
        assert is_unmarried(filer, 2022) is True

    def test_spouse_relationship_without_household(self):
        filer = _adult(relationship="spouse")
        assert is_unmarried(filer, 2022) is False


# ── paid_more_than_half_household_costs ───────────────────────────────

class TestPaidMoreThanHalf:
    def test_single_adult_returns_true(self):
        filer = _adult()
        hh = _household([filer])
        assert paid_more_than_half_household_costs(filer, hh) is True

    def test_two_adults_returns_false(self):
        filer = _adult()
        other = _adult(relationship="roommate")
        hh = _household([filer, other])
        assert paid_more_than_half_household_costs(filer, hh) is False

    def test_single_adult_with_children_returns_true(self):
        filer = _adult()
        hh = _household([filer], [_child()])
        assert paid_more_than_half_household_costs(filer, hh) is True


# ── has_qualifying_person_for_hoh ─────────────────────────────────────

class TestHasQualifyingPersonForHoH:
    def test_child_with_12_months_qualifies(self):
        filer = _adult()
        hh = _household([filer], [_child(months_in_home=12)])
        assert has_qualifying_person_for_hoh(filer, hh) is True

    def test_child_with_7_months_qualifies(self):
        filer = _adult()
        hh = _household([filer], [_child(months_in_home=7)])
        assert has_qualifying_person_for_hoh(filer, hh) is True

    def test_child_with_exactly_6_months_fails(self):
        """Boundary: exactly 6 months is NOT more than half the year."""
        filer = _adult()
        hh = _household([filer], [_child(months_in_home=6)])
        assert has_qualifying_person_for_hoh(filer, hh) is False

    def test_child_with_0_months_fails(self):
        filer = _adult()
        hh = _household([filer], [_child(months_in_home=0)])
        assert has_qualifying_person_for_hoh(filer, hh) is False

    def test_no_children_fails(self):
        filer = _adult()
        hh = _household([filer])
        assert has_qualifying_person_for_hoh(filer, hh) is False

    def test_multiple_children_one_qualifies(self):
        filer = _adult()
        hh = _household(
            [filer],
            [_child(months_in_home=3), _child(months_in_home=8)],
        )
        assert has_qualifying_person_for_hoh(filer, hh) is True
