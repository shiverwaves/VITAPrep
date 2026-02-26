"""Tests for generator/demographics.py — Sprint 3, Step 3.1."""

import numpy as np
import pandas as pd
import pytest

from generator.demographics import DemographicsGenerator
from generator.models import (
    Household, Person, RelationshipType, PATTERN_METADATA,
)
from generator.sampler import set_random_seed


# =========================================================================
# Fixture helpers — lightweight distribution tables for deterministic tests
# =========================================================================

def _make_race_by_age() -> pd.DataFrame:
    """Minimal race_by_age table covering two brackets."""
    return pd.DataFrame([
        {"age_bracket": "25-34", "race": "asian", "weight": 60},
        {"age_bracket": "25-34", "race": "white", "weight": 40},
        {"age_bracket": "35-44", "race": "asian", "weight": 50},
        {"age_bracket": "35-44", "race": "white", "weight": 30},
        {"age_bracket": "35-44", "race": "black", "weight": 20},
        {"age_bracket": "18-24", "race": "white", "weight": 70},
        {"age_bracket": "18-24", "race": "asian", "weight": 30},
        {"age_bracket": "45-54", "race": "white", "weight": 50},
        {"age_bracket": "45-54", "race": "asian", "weight": 50},
        {"age_bracket": "55-64", "race": "white", "weight": 60},
        {"age_bracket": "55-64", "race": "asian", "weight": 40},
        {"age_bracket": "65+", "race": "white", "weight": 70},
        {"age_bracket": "65+", "race": "asian", "weight": 30},
    ])


def _make_race_distribution() -> pd.DataFrame:
    return pd.DataFrame([
        {"race": "asian", "weight": 500},
        {"race": "white", "weight": 300},
        {"race": "black", "weight": 100},
        {"race": "two_or_more", "weight": 100},
    ])


def _make_hispanic_origin_by_age() -> pd.DataFrame:
    return pd.DataFrame([
        {"age_bracket": "18-24", "is_hispanic": 0, "weight": 85},
        {"age_bracket": "18-24", "is_hispanic": 1, "weight": 15},
        {"age_bracket": "25-34", "is_hispanic": 0, "weight": 87},
        {"age_bracket": "25-34", "is_hispanic": 1, "weight": 13},
        {"age_bracket": "35-44", "is_hispanic": 0, "weight": 88},
        {"age_bracket": "35-44", "is_hispanic": 1, "weight": 12},
        {"age_bracket": "45-54", "is_hispanic": 0, "weight": 90},
        {"age_bracket": "45-54", "is_hispanic": 1, "weight": 10},
        {"age_bracket": "55-64", "is_hispanic": 0, "weight": 92},
        {"age_bracket": "55-64", "is_hispanic": 1, "weight": 8},
        {"age_bracket": "65+", "is_hispanic": 0, "weight": 95},
        {"age_bracket": "65+", "is_hispanic": 1, "weight": 5},
    ])


def _make_spousal_age_gaps() -> pd.DataFrame:
    """Single-row table to make spouse age deterministic."""
    return pd.DataFrame([
        {"age_gap": 2, "weight": 100},  # householder 2 years older
    ])


def _make_couple_sex_patterns() -> pd.DataFrame:
    return pd.DataFrame([
        {"couple_type": "opposite_sex", "householder_sex": "M",
         "partner_sex": "F", "relationship": "spouse", "weight": 500},
        {"couple_type": "opposite_sex", "householder_sex": "F",
         "partner_sex": "M", "relationship": "spouse", "weight": 400},
        {"couple_type": "same_sex", "householder_sex": "M",
         "partner_sex": "M", "relationship": "unmarried_partner", "weight": 50},
        {"couple_type": "same_sex", "householder_sex": "F",
         "partner_sex": "F", "relationship": "unmarried_partner", "weight": 50},
    ])


def _make_multigenerational_patterns() -> pd.DataFrame:
    return pd.DataFrame([
        {"pattern_detail": "children+grandchild", "num_generations": 3,
         "household_size": 5, "weight": 80},
        {"pattern_detail": "children+grandchild", "num_generations": 2,
         "household_size": 4, "weight": 20},
    ])


@pytest.fixture
def distributions() -> dict:
    """Full set of Part 1 distribution tables for testing."""
    return {
        "race_by_age": _make_race_by_age(),
        "race_distribution": _make_race_distribution(),
        "hispanic_origin_by_age": _make_hispanic_origin_by_age(),
        "spousal_age_gaps": _make_spousal_age_gaps(),
        "couple_sex_patterns": _make_couple_sex_patterns(),
        "multigenerational_patterns": _make_multigenerational_patterns(),
    }


@pytest.fixture
def gen(distributions) -> DemographicsGenerator:
    """DemographicsGenerator instance with test distributions."""
    return DemographicsGenerator(distributions)


def _household(pattern: str) -> Household:
    """Create a bare household with the given pattern."""
    return Household(
        household_id="test-hh",
        state="HI",
        year=2022,
        pattern=pattern,
    )


# =========================================================================
# Initialization tests
# =========================================================================


class TestInit:
    def test_accepts_full_distributions(self, distributions):
        gen = DemographicsGenerator(distributions)
        assert gen.distributions is distributions

    def test_warns_on_missing_required_tables(self, caplog):
        DemographicsGenerator({})
        assert "Missing required demographics tables" in caplog.text

    def test_no_warning_when_all_required_present(self, distributions, caplog):
        import logging
        with caplog.at_level(logging.WARNING):
            DemographicsGenerator(distributions)
        assert "Missing required" not in caplog.text


# =========================================================================
# Adult count
# =========================================================================


class TestDetermineAdultCount:
    def test_single_adult_returns_one(self, gen):
        meta = PATTERN_METADATA["single_adult"]
        assert gen._determine_adult_count("single_adult", meta) == 1

    def test_married_couple_returns_two(self, gen):
        meta = PATTERN_METADATA["married_couple_with_children"]
        assert gen._determine_adult_count("married_couple_with_children", meta) == 2

    def test_multigenerational_returns_within_range(self, gen):
        meta = PATTERN_METADATA["multigenerational"]
        np.random.seed(42)
        counts = {gen._determine_adult_count("multigenerational", meta) for _ in range(100)}
        expected_range = meta["expected_adults"]
        for c in counts:
            assert expected_range[0] <= c <= expected_range[1]


# =========================================================================
# Relationship assignment
# =========================================================================


class TestAssignRelationships:
    def test_single_adult(self, gen):
        hh = _household("single_adult")
        rels = gen._assign_relationships("single_adult", 1, hh)
        assert rels == [RelationshipType.HOUSEHOLDER]

    def test_single_parent(self, gen):
        hh = _household("single_parent")
        rels = gen._assign_relationships("single_parent", 1, hh)
        assert rels == [RelationshipType.HOUSEHOLDER]

    def test_married_couple(self, gen):
        hh = _household("married_couple_no_children")
        rels = gen._assign_relationships("married_couple_no_children", 2, hh)
        assert rels == [RelationshipType.HOUSEHOLDER, RelationshipType.SPOUSE]

    def test_blended_family(self, gen):
        hh = _household("blended_family")
        rels = gen._assign_relationships("blended_family", 2, hh)
        assert rels == [RelationshipType.HOUSEHOLDER, RelationshipType.SPOUSE]

    def test_unmarried_partners(self, gen):
        hh = _household("unmarried_partners")
        rels = gen._assign_relationships("unmarried_partners", 2, hh)
        assert rels == [
            RelationshipType.HOUSEHOLDER,
            RelationshipType.UNMARRIED_PARTNER,
        ]

    def test_other_pattern_fills_with_other_relative(self, gen):
        hh = _household("other")
        rels = gen._assign_relationships("other", 3, hh)
        assert rels[0] == RelationshipType.HOUSEHOLDER
        assert all(r == RelationshipType.OTHER_RELATIVE for r in rels[1:])

    def test_multigenerational_includes_parent_for_3gen(self, gen):
        """With 3+ generations sampled, PARENT should appear."""
        np.random.seed(0)
        hh = _household("multigenerational")
        # Our fixture has 80% weight on num_generations=3
        rels_seen = set()
        for _ in range(20):
            rels = gen._assign_relationships("multigenerational", 3, hh)
            for r in rels:
                rels_seen.add(r)
        assert RelationshipType.HOUSEHOLDER in rels_seen
        # With 80% being 3-gen, PARENT should appear in most runs
        assert RelationshipType.PARENT in rels_seen


# =========================================================================
# Age sampling
# =========================================================================


class TestAgeSampling:
    def test_householder_age_within_bounds_single_adult(self, gen):
        np.random.seed(7)
        for _ in range(50):
            age = gen._sample_householder_age("single_adult")
            assert 18 <= age <= 85

    def test_householder_age_within_bounds_single_parent(self, gen):
        np.random.seed(7)
        for _ in range(50):
            age = gen._sample_householder_age("single_parent")
            assert 20 <= age <= 65

    def test_householder_age_within_bounds_married_children(self, gen):
        np.random.seed(7)
        for _ in range(50):
            age = gen._sample_householder_age("married_couple_with_children")
            assert 22 <= age <= 55

    def test_spouse_age_deterministic_gap(self, gen):
        """With age_gap=2 (only row), spouse = householder - 2."""
        householder = Person(person_id="h", age=40, sex="M")
        age = gen._sample_spouse_age(householder)
        assert age == 38  # 40 - 2

    def test_spouse_age_clamped_to_18(self, gen):
        householder = Person(person_id="h", age=19, sex="M")
        age = gen._sample_spouse_age(householder)
        assert age >= 18

    def test_partner_age_deterministic_gap(self, gen):
        householder = Person(person_id="h", age=35, sex="F")
        age = gen._sample_partner_age(householder)
        assert age == 33  # 35 - 2

    def test_parent_age_older_than_householder(self, gen):
        np.random.seed(42)
        householder = Person(person_id="h", age=40, sex="M")
        for _ in range(50):
            age = gen._sample_parent_age(householder)
            assert age >= 58  # at least 18 years older
            assert age <= 95

    def test_general_adult_age_valid_range(self, gen):
        np.random.seed(42)
        for _ in range(50):
            age = gen._sample_general_adult_age()
            assert 0 <= age <= 120  # wide but sane

    def test_spouse_age_no_householder_fallback(self, gen):
        """Without a householder, falls back to general adult age."""
        np.random.seed(42)
        age = gen._sample_spouse_age(None)
        assert 0 <= age <= 120

    def test_householder_age_no_distribution_fallback(self):
        """With empty distributions, falls back to uniform."""
        gen = DemographicsGenerator({})
        np.random.seed(42)
        age = gen._sample_householder_age("single_adult")
        assert 18 <= age <= 85


# =========================================================================
# Sex sampling
# =========================================================================


class TestSexSampling:
    def test_sex_is_m_or_f(self, gen):
        np.random.seed(42)
        hh = _household("single_adult")
        adults = gen.generate_adults(hh)
        assert all(a.sex in ("M", "F") for a in adults)

    def test_married_couple_sex_from_distribution(self, gen):
        """With weighted couple_sex_patterns, most couples are opposite-sex."""
        np.random.seed(1)
        opposite_count = 0
        for _ in range(50):
            hh = _household("married_couple_no_children")
            adults = gen.generate_adults(hh)
            householder, spouse = adults[0], adults[1]
            if householder.sex != spouse.sex:
                opposite_count += 1
        # 900/1000 weight is opposite-sex for spouse
        assert opposite_count > 30

    def test_other_relationship_sex_random(self, gen):
        """Non-couple relationships should still produce M or F."""
        np.random.seed(42)
        hh = _household("other")
        hh_meta = PATTERN_METADATA["other"]
        # Force 3 adults to test OTHER_RELATIVE
        adults = gen.generate_adults(Household(
            household_id="test", state="HI", year=2022, pattern="other",
            expected_adults=3,
        ))
        for a in adults:
            assert a.sex in ("M", "F")


# =========================================================================
# Race sampling
# =========================================================================


class TestRaceSampling:
    def test_race_from_age_bracket(self, gen):
        """Race should come from race_by_age when bracket matches."""
        np.random.seed(42)
        races = {gen._sample_race(30) for _ in range(50)}
        # Our 25-34 bracket has asian (60) and white (40)
        assert races <= {"asian", "white"}

    def test_race_fallback_to_overall(self):
        """If race_by_age is missing, falls back to race_distribution."""
        dist = {"race_distribution": _make_race_distribution()}
        gen = DemographicsGenerator(dist)
        np.random.seed(42)
        races = {gen._sample_race(30) for _ in range(100)}
        # Should sample from the overall distribution
        assert len(races) >= 2

    def test_race_fallback_to_white(self):
        """If no tables at all, falls back to 'white'."""
        gen = DemographicsGenerator({})
        assert gen._sample_race(30) == "white"


# =========================================================================
# Hispanic origin
# =========================================================================


class TestHispanicOrigin:
    def test_hispanic_origin_boolean(self, gen):
        np.random.seed(42)
        result = gen._sample_hispanic_origin(30)
        assert isinstance(result, bool)

    def test_hispanic_rates_plausible(self, gen):
        """Bracket 25-34 has 13% Hispanic — expect roughly that rate."""
        np.random.seed(0)
        results = [gen._sample_hispanic_origin(30) for _ in range(500)]
        rate = sum(results) / len(results)
        assert 0.05 < rate < 0.30  # generous bounds for small sample

    def test_hispanic_fallback_no_tables(self):
        gen = DemographicsGenerator({})
        np.random.seed(42)
        result = gen._sample_hispanic_origin(30)
        assert isinstance(result, bool)


# =========================================================================
# End-to-end generate_adults
# =========================================================================


class TestGenerateAdults:
    @pytest.mark.parametrize("pattern", list(PATTERN_METADATA.keys()))
    def test_all_patterns_produce_adults(self, gen, pattern):
        """Every supported pattern should produce at least one adult."""
        np.random.seed(42)
        hh = _household(pattern)
        adults = gen.generate_adults(hh)
        assert len(adults) >= 1

    def test_single_adult_produces_one(self, gen):
        np.random.seed(42)
        hh = _household("single_adult")
        adults = gen.generate_adults(hh)
        assert len(adults) == 1
        assert adults[0].relationship == RelationshipType.HOUSEHOLDER

    def test_married_couple_produces_two(self, gen):
        np.random.seed(42)
        hh = _household("married_couple_no_children")
        adults = gen.generate_adults(hh)
        assert len(adults) == 2
        assert adults[0].relationship == RelationshipType.HOUSEHOLDER
        assert adults[1].relationship == RelationshipType.SPOUSE

    def test_adults_have_all_demographic_fields(self, gen):
        np.random.seed(42)
        hh = _household("married_couple_with_children")
        adults = gen.generate_adults(hh)
        for adult in adults:
            assert adult.person_id  # non-empty UUID
            assert adult.age >= 18
            assert adult.sex in ("M", "F")
            assert adult.race  # non-empty
            assert isinstance(adult.hispanic_origin, bool)
            assert isinstance(adult.relationship, RelationshipType)

    def test_adults_have_no_employment_fields(self, gen):
        """Demographics generator should NOT populate employment fields."""
        np.random.seed(42)
        hh = _household("married_couple_with_children")
        adults = gen.generate_adults(hh)
        for adult in adults:
            assert adult.employment_status == ""
            assert adult.education == ""
            assert adult.occupation_code is None
            assert adult.occupation_title is None

    def test_adults_have_no_pii_fields(self, gen):
        """Demographics generator should NOT populate PII fields."""
        np.random.seed(42)
        hh = _household("single_adult")
        adults = gen.generate_adults(hh)
        for adult in adults:
            assert adult.legal_first_name == ""
            assert adult.ssn == ""
            assert adult.dob is None

    def test_unique_person_ids(self, gen):
        np.random.seed(42)
        hh = _household("married_couple_with_children")
        adults = gen.generate_adults(hh)
        ids = [a.person_id for a in adults]
        assert len(ids) == len(set(ids))

    def test_reproducibility_with_seed(self, distributions):
        """Same seed should produce identical adults."""
        gen1 = DemographicsGenerator(distributions)
        gen2 = DemographicsGenerator(distributions)

        set_random_seed(123)
        hh1 = _household("married_couple_with_children")
        adults1 = gen1.generate_adults(hh1)

        set_random_seed(123)
        hh2 = _household("married_couple_with_children")
        adults2 = gen2.generate_adults(hh2)

        for a1, a2 in zip(adults1, adults2):
            assert a1.age == a2.age
            assert a1.sex == a2.sex
            assert a1.race == a2.race
            assert a1.hispanic_origin == a2.hispanic_origin

    def test_unmarried_partners_produces_two(self, gen):
        np.random.seed(42)
        hh = _household("unmarried_partners")
        adults = gen.generate_adults(hh)
        assert len(adults) == 2
        assert adults[0].relationship == RelationshipType.HOUSEHOLDER
        assert adults[1].relationship == RelationshipType.UNMARRIED_PARTNER


# =========================================================================
# Helper methods
# =========================================================================


class TestHelpers:
    def test_bracket_overlaps_range_basic(self):
        assert DemographicsGenerator._bracket_overlaps_range("25-34", 20, 30)
        assert DemographicsGenerator._bracket_overlaps_range("25-34", 25, 34)
        assert not DemographicsGenerator._bracket_overlaps_range("25-34", 35, 40)

    def test_bracket_overlaps_range_plus(self):
        assert DemographicsGenerator._bracket_overlaps_range("65+", 60, 70)
        assert DemographicsGenerator._bracket_overlaps_range("65+", 80, 90)
        assert not DemographicsGenerator._bracket_overlaps_range("65+", 50, 64)

    def test_bracket_overlaps_range_single(self):
        assert DemographicsGenerator._bracket_overlaps_range("30", 25, 35)
        assert not DemographicsGenerator._bracket_overlaps_range("30", 31, 40)

    def test_bracket_overlaps_range_unparseable(self):
        """Unparseable brackets are included (safe fallback)."""
        assert DemographicsGenerator._bracket_overlaps_range("unknown", 20, 30)
