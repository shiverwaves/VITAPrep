"""Tests for tax_core.predicates.dependency predicates.

2 predicates tested:
- qualifying_child_residency_test (stub)
- qualifying_relative_test (stub)
"""

import pytest
from types import SimpleNamespace

from tax_core.predicates.dependency import (
    qualifying_child_residency_test,
    qualifying_relative_test,
    ResidencyTestResult,
    QualifyingRelativeResult,
)


def _person(**kwargs):
    defaults = {
        "age": 10,
        "months_in_home": 12,
        "relationship": "biological_child",
        "wage_income": 0,
        "self_employment_income": 0,
        "social_security_income": 0,
        "retirement_income": 0,
        "interest_income": 0,
        "dividend_income": 0,
        "other_income": 0,
        "public_assistance_income": 0,
    }
    defaults.update(kwargs)
    p = SimpleNamespace(**defaults)
    p.total_income = lambda: (
        p.wage_income + p.self_employment_income + p.social_security_income
        + p.retirement_income + p.interest_income + p.dividend_income
        + p.other_income + p.public_assistance_income
    )
    p.is_adult = lambda: p.age >= 18
    p.is_child = lambda: p.age < 18
    return p


def _household(adults=None, children=None):
    adults = adults or []
    children = children or []
    members = adults + children
    return SimpleNamespace(
        members=members,
        get_children=lambda: children,
        get_adults=lambda: adults,
    )


# ── qualifying_child_residency_test ───────────────────────────────────

class TestQualifyingChildResidencyTest:
    def test_12_months_passes(self):
        child = _person(months_in_home=12)
        result = qualifying_child_residency_test(child, 2022)
        assert result.passed is True
        assert result.months_in_home == 12

    def test_7_months_passes(self):
        child = _person(months_in_home=7)
        result = qualifying_child_residency_test(child, 2022)
        assert result.passed is True
        assert result.months_in_home == 7

    def test_exactly_6_months_fails(self):
        """Boundary: > 6 months required, so 6 exactly fails."""
        child = _person(months_in_home=6)
        result = qualifying_child_residency_test(child, 2022)
        assert result.passed is False
        assert result.months_in_home == 6
        assert "need > 6" in result.reason

    def test_0_months_fails(self):
        child = _person(months_in_home=0)
        result = qualifying_child_residency_test(child, 2022)
        assert result.passed is False

    def test_result_has_required_months(self):
        child = _person(months_in_home=12)
        result = qualifying_child_residency_test(child, 2022)
        assert result.required_months == 7

    def test_temporary_absence_not_applied(self):
        """Stub: temporary absence exceptions are not implemented yet."""
        child = _person(months_in_home=12)
        result = qualifying_child_residency_test(child, 2022)
        assert result.temporary_absence_applied is False

    def test_returns_residency_test_result(self):
        child = _person(months_in_home=8)
        result = qualifying_child_residency_test(child, 2022)
        assert isinstance(result, ResidencyTestResult)


# ── qualifying_relative_test ──────────────────────────────────────────

class TestQualifyingRelativeTest:
    def test_parent_under_threshold_passes(self):
        parent = _person(
            age=70, relationship="parent", wage_income=3000,
        )
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert result.passed is True
        assert result.relationship_test is True
        assert result.gross_income_test is True
        assert result.reason == "All tests passed"

    def test_sibling_under_threshold_passes(self):
        sibling = _person(age=25, relationship="sibling", wage_income=4000)
        hh = _household(adults=[sibling])
        result = qualifying_relative_test(sibling, hh, 2022)
        assert result.passed is True

    def test_income_at_threshold_fails(self):
        """Boundary: gross income must be < $4,400, not <=."""
        parent = _person(age=70, relationship="parent", wage_income=4400)
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert result.passed is False
        assert result.gross_income_test is False

    def test_income_one_below_threshold_passes(self):
        parent = _person(age=70, relationship="parent", wage_income=4399)
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert result.passed is True
        assert result.gross_income_test is True

    def test_non_qualifying_relationship_fails(self):
        roommate = _person(
            age=30, relationship="roommate", wage_income=0,
        )
        hh = _household(adults=[roommate])
        result = qualifying_relative_test(roommate, hh, 2022)
        assert result.passed is False
        assert result.relationship_test is False
        assert "not qualifying" in result.reason

    def test_enum_relationship_value_extracted(self):
        """Relationship may be an enum with .value attribute."""
        from types import SimpleNamespace
        parent = _person(age=70, wage_income=2000)
        parent.relationship = SimpleNamespace(value="parent")
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert result.passed is True
        assert result.relationship_test is True

    def test_support_test_stubbed_true(self):
        parent = _person(age=70, relationship="parent", wage_income=0)
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert result.support_test is True

    def test_not_qualifying_child_test_stubbed_true(self):
        parent = _person(age=70, relationship="parent", wage_income=0)
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert result.not_qualifying_child_test is True

    def test_returns_qualifying_relative_result(self):
        parent = _person(age=70, relationship="parent", wage_income=0)
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert isinstance(result, QualifyingRelativeResult)

    def test_multiple_income_sources_summed(self):
        """Gross income includes all income types."""
        parent = _person(
            age=70,
            relationship="parent",
            wage_income=2000,
            interest_income=2000,
            dividend_income=500,
        )
        hh = _household(adults=[parent])
        result = qualifying_relative_test(parent, hh, 2022)
        assert result.passed is False
        assert result.gross_income_test is False
