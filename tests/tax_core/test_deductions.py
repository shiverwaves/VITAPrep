"""Tests for tax_core.predicates.deductions predicates.

4 predicates tested (all exact-tier):
- compute_salt
- compute_medical_deduction
- compute_itemized_total
- should_itemize
"""

import pytest

from tax_core.predicates.deductions import (
    compute_salt,
    compute_medical_deduction,
    compute_itemized_total,
    should_itemize,
)


# ── compute_salt ──────────────────────────────────────────────────────

class TestComputeSalt:
    def test_under_cap(self):
        assert compute_salt(3000, 4000, 2022) == 7000

    def test_at_cap(self):
        assert compute_salt(6000, 4000, 2022) == 10000

    def test_over_cap(self):
        """SALT capped at $10,000 for 2022."""
        assert compute_salt(8000, 5000, 2022) == 10000

    def test_zero_inputs(self):
        assert compute_salt(0, 0, 2022) == 0

    def test_only_state_tax(self):
        assert compute_salt(7000, 0, 2022) == 7000

    def test_only_property_tax(self):
        assert compute_salt(0, 9000, 2022) == 9000

    def test_way_over_cap(self):
        assert compute_salt(50000, 30000, 2022) == 10000


# ── compute_medical_deduction ─────────────────────────────────────────

class TestComputeMedicalDeduction:
    def test_expenses_below_floor(self):
        """Medical expenses under 7.5% of AGI → $0."""
        assert compute_medical_deduction(3000, 50000) == 0

    def test_expenses_at_floor(self):
        """Exactly at the 7.5% floor → $0."""
        assert compute_medical_deduction(3750, 50000) == 0

    def test_expenses_above_floor(self):
        """Only the amount over the 7.5% floor is deductible."""
        assert compute_medical_deduction(5000, 50000) == 1250

    def test_zero_agi(self):
        """With $0 AGI, all medical expenses are deductible."""
        assert compute_medical_deduction(5000, 0) == 5000

    def test_zero_expenses(self):
        assert compute_medical_deduction(0, 50000) == 0

    def test_large_agi_small_expenses(self):
        assert compute_medical_deduction(1000, 100000) == 0


# ── compute_itemized_total ────────────────────────────────────────────

class TestComputeItemizedTotal:
    def test_all_categories(self):
        assert compute_itemized_total(10000, 5000, 2000, 3000) == 20000

    def test_all_zeros(self):
        assert compute_itemized_total(0, 0, 0, 0) == 0

    def test_single_category(self):
        assert compute_itemized_total(8000, 0, 0, 0) == 8000


# ── should_itemize ────────────────────────────────────────────────────

class TestShouldItemize:
    def test_itemized_above_standard_deduction_single(self):
        """Single standard deduction = $12,950 for 2022."""
        assert should_itemize(13000, "single", 2022) is True

    def test_itemized_below_standard_deduction_single(self):
        assert should_itemize(12000, "single", 2022) is False

    def test_itemized_equal_to_standard_deduction(self):
        """Boundary: equal to standard deduction → do NOT itemize."""
        assert should_itemize(12950, "single", 2022) is False

    def test_itemized_one_above_standard_deduction(self):
        assert should_itemize(12951, "single", 2022) is True

    def test_mfj_higher_threshold(self):
        """MFJ standard deduction = $25,900 for 2022."""
        assert should_itemize(25000, "married_filing_jointly", 2022) is False
        assert should_itemize(26000, "married_filing_jointly", 2022) is True

    def test_hoh_threshold(self):
        """HoH standard deduction = $19,400 for 2022."""
        assert should_itemize(19400, "head_of_household", 2022) is False
        assert should_itemize(19401, "head_of_household", 2022) is True
