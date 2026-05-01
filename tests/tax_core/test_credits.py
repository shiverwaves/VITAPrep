"""Tests for tax_core.predicates.credits predicates.

2 predicates tested (both stub-tier):
- qualifies_for_eitc
- qualifies_for_actc
"""

import pytest
from types import SimpleNamespace

from tax_core.predicates.credits import (
    qualifies_for_eitc,
    qualifies_for_actc,
)


def _person(**kwargs):
    defaults = {
        "wage_income": 0,
        "self_employment_income": 0,
    }
    defaults.update(kwargs)
    return SimpleNamespace(**defaults)


def _child(**kwargs):
    defaults = {"age": 10}
    defaults.update(kwargs)
    p = SimpleNamespace(**defaults)
    p.is_child = lambda: p.age < 18
    p.is_adult = lambda: p.age >= 18
    return p


def _household(adults=None, children=None):
    children = children or []
    adults = adults or []
    members = adults + children
    return SimpleNamespace(
        members=members,
        get_children=lambda: children,
        get_adults=lambda: adults,
    )


# ── qualifies_for_eitc ───────────────────────────────────────────────

class TestQualifiesForEITC:
    def test_earned_income_with_child(self):
        filer = _person(wage_income=25000)
        hh = _household([filer], [_child()])
        assert qualifies_for_eitc(filer, hh, 2022) is True

    def test_se_income_counts_as_earned(self):
        filer = _person(self_employment_income=15000)
        hh = _household([filer], [_child()])
        assert qualifies_for_eitc(filer, hh, 2022) is True

    def test_zero_earned_income_fails(self):
        filer = _person(wage_income=0, self_employment_income=0)
        hh = _household([filer], [_child()])
        assert qualifies_for_eitc(filer, hh, 2022) is False

    def test_no_children_fails(self):
        """Stub: childless-worker EITC path not implemented."""
        filer = _person(wage_income=25000)
        hh = _household([filer])
        assert qualifies_for_eitc(filer, hh, 2022) is False

    def test_one_dollar_earned_income_with_child(self):
        """Boundary: even $1 of earned income qualifies (stub)."""
        filer = _person(wage_income=1)
        hh = _household([filer], [_child()])
        assert qualifies_for_eitc(filer, hh, 2022) is True

    def test_combined_wage_and_se(self):
        filer = _person(wage_income=5000, self_employment_income=3000)
        hh = _household([filer], [_child()])
        assert qualifies_for_eitc(filer, hh, 2022) is True


# ── qualifies_for_actc ───────────────────────────────────────────────

class TestQualifiesForACTC:
    def test_earned_income_above_2500_with_child_under_17(self):
        filer = _person(wage_income=30000)
        hh = _household([filer], [_child(age=10)])
        assert qualifies_for_actc(filer, hh, 2022) is True

    def test_earned_income_exactly_2500_fails(self):
        """Boundary: earned income must be > $2,500, not >=."""
        filer = _person(wage_income=2500)
        hh = _household([filer], [_child(age=10)])
        assert qualifies_for_actc(filer, hh, 2022) is False

    def test_earned_income_2501_passes(self):
        filer = _person(wage_income=2501)
        hh = _household([filer], [_child(age=10)])
        assert qualifies_for_actc(filer, hh, 2022) is True

    def test_se_income_counts(self):
        filer = _person(self_employment_income=5000)
        hh = _household([filer], [_child(age=5)])
        assert qualifies_for_actc(filer, hh, 2022) is True

    def test_child_age_17_fails(self):
        """Child must be under 17 (not 17+)."""
        filer = _person(wage_income=30000)
        hh = _household([filer], [_child(age=17)])
        assert qualifies_for_actc(filer, hh, 2022) is False

    def test_child_age_16_passes(self):
        filer = _person(wage_income=30000)
        hh = _household([filer], [_child(age=16)])
        assert qualifies_for_actc(filer, hh, 2022) is True

    def test_no_children_fails(self):
        filer = _person(wage_income=30000)
        hh = _household([filer])
        assert qualifies_for_actc(filer, hh, 2022) is False

    def test_zero_earned_income_fails(self):
        filer = _person()
        hh = _household([filer], [_child(age=10)])
        assert qualifies_for_actc(filer, hh, 2022) is False

    def test_multiple_children_one_under_17(self):
        filer = _person(wage_income=30000)
        hh = _household([filer], [_child(age=17), _child(age=15)])
        assert qualifies_for_actc(filer, hh, 2022) is True
