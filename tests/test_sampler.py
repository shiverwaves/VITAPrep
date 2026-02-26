"""Tests for generator/sampler.py — Sprint 1."""

import pandas as pd
import pytest

from generator.sampler import (
    get_age_bracket,
    match_age_bracket,
    parse_dollar_amount,
    sample_age_from_bracket,
    sample_from_bracket,
    set_random_seed,
    weighted_sample,
)


# ── set_random_seed ──────────────────────────────────────────────────────────

class TestSetRandomSeed:
    def test_deterministic_output(self):
        """Same seed produces same sequence."""
        set_random_seed(42)
        first = [sample_age_from_bracket("25-34") for _ in range(5)]
        set_random_seed(42)
        second = [sample_age_from_bracket("25-34") for _ in range(5)]
        assert first == second

    def test_none_seed_does_not_raise(self):
        set_random_seed(None)


# ── parse_dollar_amount ──────────────────────────────────────────────────────

class TestParseDollarAmount:
    @pytest.mark.parametrize("input_str, expected", [
        ("$25K", 25_000),
        ("$25,000", 25_000),
        ("$150K", 150_000),
        ("$150,000", 150_000),
        ("$0", 0),
        ("0", 0),
        ("25000", 25_000),
        ("$10k", 10_000),
        ("$1.5K", 1_500),
    ])
    def test_valid_formats(self, input_str, expected):
        assert parse_dollar_amount(input_str) == expected

    def test_empty_string_raises(self):
        with pytest.raises(ValueError):
            parse_dollar_amount("")

    def test_whitespace_handling(self):
        assert parse_dollar_amount("  $50K  ") == 50_000


# ── sample_from_bracket ─────────────────────────────────────────────────────

class TestSampleFromBracket:
    def test_range_dash(self):
        set_random_seed(1)
        for _ in range(50):
            val = sample_from_bracket("$25,000-$49,999")
            assert 25_000 <= val <= 49_999

    def test_range_k_suffix(self):
        set_random_seed(2)
        for _ in range(50):
            val = sample_from_bracket("$25K-$50K")
            assert 25_000 <= val <= 50_000

    def test_shorthand_k_range(self):
        """'$25-50K' where only the right side has the K."""
        set_random_seed(3)
        for _ in range(50):
            val = sample_from_bracket("$25-50K")
            assert 25_000 <= val <= 50_000

    def test_under_bracket(self):
        set_random_seed(4)
        for _ in range(50):
            val = sample_from_bracket("Under $10,000")
            assert 0 <= val < 10_000

    def test_over_bracket(self):
        set_random_seed(5)
        for _ in range(50):
            val = sample_from_bracket("$100,000+")
            assert val >= 100_000

    def test_single_value(self):
        assert sample_from_bracket("$50,000") == 50_000


# ── match_age_bracket ────────────────────────────────────────────────────────

class TestMatchAgeBracket:
    def test_range(self):
        assert match_age_bracket(30, "25-34") is True
        assert match_age_bracket(25, "25-34") is True
        assert match_age_bracket(34, "25-34") is True
        assert match_age_bracket(24, "25-34") is False
        assert match_age_bracket(35, "25-34") is False

    def test_under(self):
        assert match_age_bracket(10, "Under 18") is True
        assert match_age_bracket(17, "Under 18") is True
        assert match_age_bracket(18, "Under 18") is False

    def test_over(self):
        assert match_age_bracket(65, "65+") is True
        assert match_age_bracket(90, "65+") is True
        assert match_age_bracket(64, "65+") is False

    def test_single_number(self):
        assert match_age_bracket(5, "5") is True
        assert match_age_bracket(6, "5") is False

    def test_en_dash(self):
        """Brackets may use en-dash or em-dash."""
        assert match_age_bracket(30, "25–34") is True
        assert match_age_bracket(30, "25—34") is True


# ── get_age_bracket ──────────────────────────────────────────────────────────

class TestGetAgeBracket:
    BRACKETS = ["Under 18", "18-24", "25-34", "35-44", "45-54", "55-64", "65+"]

    def test_finds_matching_bracket(self):
        assert get_age_bracket(10, self.BRACKETS) == "Under 18"
        assert get_age_bracket(20, self.BRACKETS) == "18-24"
        assert get_age_bracket(30, self.BRACKETS) == "25-34"
        assert get_age_bracket(70, self.BRACKETS) == "65+"

    def test_boundary_values(self):
        assert get_age_bracket(17, self.BRACKETS) == "Under 18"
        assert get_age_bracket(18, self.BRACKETS) == "18-24"
        assert get_age_bracket(64, self.BRACKETS) == "55-64"
        assert get_age_bracket(65, self.BRACKETS) == "65+"

    def test_no_match_returns_none(self):
        assert get_age_bracket(30, ["Under 18", "65+"]) is None


# ── sample_age_from_bracket ──────────────────────────────────────────────────

class TestSampleAgeFromBracket:
    def test_range(self):
        set_random_seed(10)
        for _ in range(50):
            age = sample_age_from_bracket("25-34")
            assert 25 <= age <= 34

    def test_under(self):
        set_random_seed(11)
        for _ in range(50):
            age = sample_age_from_bracket("Under 18")
            assert 0 <= age <= 17

    def test_over(self):
        set_random_seed(12)
        for _ in range(50):
            age = sample_age_from_bracket("65+")
            assert 65 <= age <= 85

    def test_single_number(self):
        assert sample_age_from_bracket("30") == 30

    def test_invalid_raises(self):
        with pytest.raises(ValueError):
            sample_age_from_bracket("abc")


# ── weighted_sample ──────────────────────────────────────────────────────────

class TestWeightedSample:
    @pytest.fixture
    def distribution_df(self):
        return pd.DataFrame({
            "category": ["A", "B", "C"],
            "weight": [100, 200, 700],
        })

    def test_returns_correct_count(self, distribution_df):
        result = weighted_sample(distribution_df, "weight", n=5)
        assert len(result) == 5

    def test_returns_single_row_by_default(self, distribution_df):
        result = weighted_sample(distribution_df, "weight")
        assert len(result) == 1

    def test_respects_weights_over_many_samples(self, distribution_df):
        """Category C (weight 700/1000) should appear most often."""
        set_random_seed(42)
        result = weighted_sample(distribution_df, "weight", n=1000)
        counts = result["category"].value_counts()
        assert counts["C"] > counts["A"]
        assert counts["C"] > counts["B"]

    def test_missing_weight_column_raises(self, distribution_df):
        with pytest.raises(ValueError, match="not found"):
            weighted_sample(distribution_df, "nonexistent")

    def test_zero_weights_raises(self):
        df = pd.DataFrame({"x": [1, 2], "weight": [0, 0]})
        with pytest.raises(ValueError, match="sum to zero"):
            weighted_sample(df, "weight")

    def test_result_has_original_columns(self, distribution_df):
        result = weighted_sample(distribution_df, "weight", n=3)
        assert list(result.columns) == ["category", "weight"]
