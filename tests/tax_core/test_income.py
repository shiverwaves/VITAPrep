"""Tests for tax_core.predicates.income predicates.

8 predicates tested:
- total_income (exact)
- total_self_employment_income (exact)
- requires_schedule_se (exact)
- filing_threshold_for (careful)
- filing_threshold_for_person (careful)
- compute_provisional_income (careful)
- ss_taxability_thresholds (careful)
- compute_taxable_ss (careful — IRS Pub 915 worksheet)
"""

import pytest
from types import SimpleNamespace

from tax_core.predicates.income import (
    total_income,
    total_self_employment_income,
    requires_schedule_se,
    filing_threshold_for,
    filing_threshold_for_person,
    compute_provisional_income,
    ss_taxability_thresholds,
    compute_taxable_ss,
)


def _person(**kwargs):
    defaults = {
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
    return SimpleNamespace(**defaults)


# ── total_income ──────────────────────────────────────────────────────

class TestTotalIncome:
    def test_all_zeros(self):
        assert total_income(_person()) == 0

    def test_wage_only(self):
        assert total_income(_person(wage_income=50000)) == 50000

    def test_all_sources(self):
        p = _person(
            wage_income=30000,
            self_employment_income=5000,
            social_security_income=12000,
            retirement_income=8000,
            interest_income=500,
            dividend_income=300,
            other_income=200,
            public_assistance_income=1000,
        )
        assert total_income(p) == 57000

    def test_public_assistance_included_via_getattr(self):
        """public_assistance_income uses getattr with default 0."""
        p = _person(wage_income=10000)
        del p.public_assistance_income
        assert total_income(p) == 10000


# ── total_self_employment_income ──────────────────────────────────────

class TestTotalSelfEmploymentIncome:
    def test_returns_se_field(self):
        p = _person(self_employment_income=8500)
        assert total_self_employment_income(p) == 8500

    def test_zero_when_none(self):
        assert total_self_employment_income(_person()) == 0


# ── requires_schedule_se ──────────────────────────────────────────────

class TestRequiresScheduleSE:
    def test_exactly_400_requires_se(self):
        """Boundary: >= $400 triggers Schedule SE."""
        assert requires_schedule_se(_person(self_employment_income=400)) is True

    def test_399_does_not_require_se(self):
        assert requires_schedule_se(_person(self_employment_income=399)) is False

    def test_0_does_not_require_se(self):
        assert requires_schedule_se(_person(self_employment_income=0)) is False

    def test_large_amount_requires_se(self):
        assert requires_schedule_se(_person(self_employment_income=100000)) is True


# ── filing_threshold_for ──────────────────────────────────────────────

class TestFilingThresholdFor:
    def test_single_2022(self):
        assert filing_threshold_for("single", 2022) == 12950

    def test_hoh_2022(self):
        assert filing_threshold_for("head_of_household", 2022) == 19400

    def test_mfj_2022(self):
        assert filing_threshold_for("married_filing_jointly", 2022) == 25900

    def test_mfs_2022(self):
        assert filing_threshold_for("married_filing_separately", 2022) == 5

    def test_qss_2022(self):
        assert filing_threshold_for("qualifying_surviving_spouse", 2022) == 25900

    def test_unknown_year_raises(self):
        with pytest.raises(KeyError):
            filing_threshold_for("single", 2099)

    def test_unknown_status_raises(self):
        with pytest.raises(KeyError):
            filing_threshold_for("invalid_status", 2022)


# ── filing_threshold_for_person ───────────────────────────────────────

class TestFilingThresholdForPerson:
    def test_single_not_elderly(self):
        assert filing_threshold_for_person("single", 2022, is_elderly=False) == 12950

    def test_single_elderly(self):
        assert filing_threshold_for_person("single", 2022, is_elderly=True) == 12950 + 1750

    def test_mfj_elderly(self):
        assert filing_threshold_for_person(
            "married_filing_jointly", 2022, is_elderly=True,
        ) == 25900 + 1400

    def test_hoh_elderly(self):
        assert filing_threshold_for_person(
            "head_of_household", 2022, is_elderly=True,
        ) == 19400 + 1750

    def test_mfs_elderly(self):
        assert filing_threshold_for_person(
            "married_filing_separately", 2022, is_elderly=True,
        ) == 5 + 1400


# ── compute_provisional_income ────────────────────────────────────────

class TestComputeProvisionalIncome:
    def test_no_ss_returns_non_ss_total(self):
        p = _person(wage_income=30000, interest_income=500)
        assert compute_provisional_income(p) == 30500

    def test_ss_adds_half(self):
        p = _person(wage_income=20000, social_security_income=18000)
        assert compute_provisional_income(p) == 20000 + 9000

    def test_only_ss(self):
        p = _person(social_security_income=24000)
        assert compute_provisional_income(p) == 12000

    def test_odd_ss_truncates(self):
        """Half of odd SS uses integer division (floor)."""
        p = _person(social_security_income=25001)
        assert compute_provisional_income(p) == 12500

    def test_all_non_ss_sources(self):
        p = _person(
            wage_income=10000,
            self_employment_income=5000,
            retirement_income=3000,
            interest_income=1000,
            dividend_income=500,
            other_income=200,
            social_security_income=12000,
        )
        expected = (10000 + 5000 + 3000 + 1000 + 500 + 200) + 6000
        assert compute_provisional_income(p) == expected

    def test_public_assistance_excluded(self):
        """Public assistance is NOT included in provisional income."""
        p = _person(
            wage_income=10000,
            public_assistance_income=5000,
            social_security_income=0,
        )
        assert compute_provisional_income(p) == 10000


# ── ss_taxability_thresholds ──────────────────────────────────────────

class TestSSTaxabilityThresholds:
    def test_single_thresholds(self):
        assert ss_taxability_thresholds("single", 2022) == (25000, 34000)

    def test_mfj_thresholds(self):
        assert ss_taxability_thresholds("married_filing_jointly", 2022) == (32000, 44000)

    def test_mfs_thresholds_zero(self):
        """MFS living with spouse: both thresholds are 0."""
        assert ss_taxability_thresholds("married_filing_separately", 2022) == (0, 0)

    def test_hoh_same_as_single(self):
        assert ss_taxability_thresholds("head_of_household", 2022) == (25000, 34000)

    def test_qss_same_as_mfj(self):
        assert ss_taxability_thresholds("qualifying_surviving_spouse", 2022) == (32000, 44000)


# ── compute_taxable_ss ────────────────────────────────────────────────
# Tested against IRS Publication 915 Worksheet 1 logic.

class TestComputeTaxableSS:
    def test_no_ss_returns_zero(self):
        p = _person(wage_income=50000, social_security_income=0)
        assert compute_taxable_ss(p, "single", 2022) == 0

    def test_below_lower_threshold_returns_zero(self):
        """Single, provisional income <= $25,000 → $0 taxable."""
        p = _person(wage_income=15000, social_security_income=18000)
        # provisional = 15000 + 9000 = 24000, below 25000
        assert compute_taxable_ss(p, "single", 2022) == 0

    def test_at_lower_threshold_returns_zero(self):
        """Boundary: provisional exactly at lower threshold → $0 taxable."""
        p = _person(wage_income=16000, social_security_income=18000)
        # provisional = 16000 + 9000 = 25000, exactly at threshold
        assert compute_taxable_ss(p, "single", 2022) == 0

    def test_tier1_basic(self):
        """Single, provisional between $25,000 and $34,000 → tier 1 only."""
        p = _person(wage_income=20000, social_security_income=12000)
        # provisional = 20000 + 6000 = 26000
        # excess_over_lower = 26000 - 25000 = 1000
        # tier1 = min(6000, 1000 // 2) = min(6000, 500) = 500
        assert compute_taxable_ss(p, "single", 2022) == 500

    def test_tier1_capped_at_half_ss(self):
        """Tier 1 can't exceed 50% of SS benefits."""
        p = _person(wage_income=25000, social_security_income=4000)
        # provisional = 25000 + 2000 = 27000
        # excess_over_lower = 27000 - 25000 = 2000
        # tier1 = min(2000, 2000 // 2) = min(2000, 1000) = 1000
        # But half_ss = 2000, so tier1 = min(2000, 1000) = 1000
        assert compute_taxable_ss(p, "single", 2022) == 1000

    def test_at_upper_threshold(self):
        """Single, provisional at upper threshold → still tier 1 only."""
        p = _person(wage_income=22000, social_security_income=24000)
        # provisional = 22000 + 12000 = 34000, exactly at upper
        # excess_over_lower = 34000 - 25000 = 9000
        # tier1 = min(12000, 9000 // 2) = min(12000, 4500) = 4500
        assert compute_taxable_ss(p, "single", 2022) == 4500

    def test_tier2_basic(self):
        """Single, provisional > $34,000 → tier 2."""
        p = _person(wage_income=30000, social_security_income=18000)
        # provisional = 30000 + 9000 = 39000
        # excess_over_lower = 39000 - 25000 = 14000
        # tier1_taxable = min(9000, 14000 // 2) = min(9000, 7000) = 7000
        # tier1_cap = min(7000, (34000 - 25000) // 2) = min(7000, 4500) = 4500
        # excess_over_upper = 39000 - 34000 = 5000
        # tier2_addition = int(5000 * 0.85) = 4250
        # max_taxable = int(18000 * 0.85) = 15300
        # result = min(4500 + 4250, 15300) = min(8750, 15300) = 8750
        assert compute_taxable_ss(p, "single", 2022) == 8750

    def test_tier2_capped_at_85_percent(self):
        """Taxable SS can never exceed 85% of total benefits."""
        p = _person(wage_income=100000, social_security_income=12000)
        # provisional = 100000 + 6000 = 106000
        # max_taxable = int(12000 * 0.85) = 10200
        result = compute_taxable_ss(p, "single", 2022)
        assert result == int(12000 * 0.85)
        assert result == 10200

    def test_mfj_thresholds_higher(self):
        """MFJ uses $32,000/$44,000 thresholds."""
        p = _person(wage_income=25000, social_security_income=12000)
        # provisional = 25000 + 6000 = 31000, below MFJ lower (32000)
        assert compute_taxable_ss(p, "married_filing_jointly", 2022) == 0

    def test_mfj_tier1(self):
        """MFJ with provisional between $32,000 and $44,000."""
        p = _person(wage_income=30000, social_security_income=12000)
        # provisional = 30000 + 6000 = 36000
        # excess_over_lower = 36000 - 32000 = 4000
        # tier1 = min(6000, 4000 // 2) = min(6000, 2000) = 2000
        assert compute_taxable_ss(p, "married_filing_jointly", 2022) == 2000

    def test_mfs_immediate_85_percent(self):
        """MFS: thresholds are (0, 0), so up to 85% taxable immediately."""
        p = _person(wage_income=20000, social_security_income=12000)
        # provisional = 20000 + 6000 = 26000
        # lower = 0, upper = 0
        # Since provisional > upper:
        #   tier1_taxable = min(6000, 26000 // 2) = min(6000, 13000) = 6000
        #   tier1_cap = min(6000, (0 - 0) // 2) = min(6000, 0) = 0
        #   excess_over_upper = 26000 - 0 = 26000
        #   tier2_addition = int(26000 * 0.85) = 22100
        #   max_taxable = int(12000 * 0.85) = 10200
        #   result = min(0 + 22100, 10200) = 10200
        assert compute_taxable_ss(p, "married_filing_separately", 2022) == 10200

    def test_mfs_low_income_still_85_percent(self):
        """MFS with very low other income still uses 85% ceiling."""
        p = _person(wage_income=1000, social_security_income=20000)
        # provisional = 1000 + 10000 = 11000
        # lower = 0, upper = 0
        # tier1_cap = 0
        # excess_over_upper = 11000
        # tier2_addition = int(11000 * 0.85) = 9350
        # max_taxable = int(20000 * 0.85) = 17000
        # result = min(0 + 9350, 17000) = 9350
        assert compute_taxable_ss(p, "married_filing_separately", 2022) == 9350

    def test_zero_ss_with_high_income(self):
        p = _person(wage_income=200000, social_security_income=0)
        assert compute_taxable_ss(p, "single", 2022) == 0

    def test_negative_ss_returns_zero(self):
        """Edge case: negative SS (repayment exceeds benefits)."""
        p = _person(wage_income=50000, social_security_income=-1000)
        assert compute_taxable_ss(p, "single", 2022) == 0

    def test_pub915_worked_example_single(self):
        """Worked example: single filer, moderate income + SS.

        Single, wage $28,000, SS $14,000.
        provisional = 28000 + 7000 = 35000
        lower = 25000, upper = 34000
        excess_over_lower = 10000
        tier1_taxable = min(7000, 5000) = 5000
        Since provisional > upper:
          tier1_cap = min(5000, (34000-25000)//2) = min(5000, 4500) = 4500
          excess_over_upper = 35000 - 34000 = 1000
          tier2_addition = int(1000 * 0.85) = 850
          max_taxable = int(14000 * 0.85) = 11900
          result = min(4500 + 850, 11900) = 5350
        """
        p = _person(wage_income=28000, social_security_income=14000)
        assert compute_taxable_ss(p, "single", 2022) == 5350

    def test_pub915_worked_example_mfj_high(self):
        """Worked example: MFJ, high income, SS should hit 85% cap.

        MFJ, wage $80,000, SS $20,000.
        provisional = 80000 + 10000 = 90000
        lower = 32000, upper = 44000
        excess_over_lower = 58000
        tier1_taxable = min(10000, 29000) = 10000
        tier1_cap = min(10000, (44000-32000)//2) = min(10000, 6000) = 6000
        excess_over_upper = 90000 - 44000 = 46000
        tier2_addition = int(46000 * 0.85) = 39100
        max_taxable = int(20000 * 0.85) = 17000
        result = min(6000 + 39100, 17000) = 17000
        """
        p = _person(wage_income=80000, social_security_income=20000)
        assert compute_taxable_ss(p, "married_filing_jointly", 2022) == 17000
