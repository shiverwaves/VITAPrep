"""Tests for generator/pipeline.py — Sprint 3, Step 3.3.

End-to-end Part 1 generation tests using in-memory distribution tables.
These verify that the pipeline correctly wires DemographicsGenerator and
ChildGenerator together without needing the real SQLite database.
"""

import numpy as np
import pandas as pd
import pytest
from unittest.mock import patch, MagicMock

from generator.pipeline import HouseholdGenerator
from generator.demographics import DemographicsGenerator
from generator.children import ChildGenerator
from generator.models import (
    Household,
    Person,
    RelationshipType,
    PATTERN_METADATA,
)
from generator.sampler import set_random_seed


# =========================================================================
# Fixture helpers — lightweight distribution tables
# =========================================================================

def _make_household_patterns() -> pd.DataFrame:
    """Household pattern distribution for sampling."""
    return pd.DataFrame([
        {"pattern": "married_couple_with_children", "weight": 30},
        {"pattern": "single_parent", "weight": 15},
        {"pattern": "married_couple_no_children", "weight": 20},
        {"pattern": "single_adult", "weight": 15},
        {"pattern": "blended_family", "weight": 5},
        {"pattern": "multigenerational", "weight": 5},
        {"pattern": "unmarried_partners", "weight": 5},
        {"pattern": "other", "weight": 5},
    ])


def _make_race_by_age() -> pd.DataFrame:
    return pd.DataFrame([
        {"age_bracket": "18-24", "race": "white", "weight": 70},
        {"age_bracket": "18-24", "race": "asian", "weight": 30},
        {"age_bracket": "25-34", "race": "asian", "weight": 60},
        {"age_bracket": "25-34", "race": "white", "weight": 40},
        {"age_bracket": "35-44", "race": "asian", "weight": 50},
        {"age_bracket": "35-44", "race": "white", "weight": 30},
        {"age_bracket": "35-44", "race": "black", "weight": 20},
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
    return pd.DataFrame([
        {"age_gap": 2, "weight": 100},
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


def _make_children_by_parent_age() -> pd.DataFrame:
    return pd.DataFrame([
        {"parent_age_bracket": "25-29", "num_children": 1, "weight": 40},
        {"parent_age_bracket": "25-29", "num_children": 2, "weight": 30},
        {"parent_age_bracket": "30-34", "num_children": 1, "weight": 30},
        {"parent_age_bracket": "30-34", "num_children": 2, "weight": 40},
        {"parent_age_bracket": "35-39", "num_children": 1, "weight": 40},
        {"parent_age_bracket": "35-39", "num_children": 2, "weight": 30},
        {"parent_age_bracket": "40-44", "num_children": 1, "weight": 50},
        {"parent_age_bracket": "40-44", "num_children": 2, "weight": 30},
        {"parent_age_bracket": "45-54", "num_children": 1, "weight": 60},
        {"parent_age_bracket": "45-54", "num_children": 2, "weight": 20},
        {"parent_age_bracket": "55-64", "num_children": 1, "weight": 80},
        {"parent_age_bracket": "65+", "num_children": 1, "weight": 90},
    ])


def _make_child_age_distributions() -> pd.DataFrame:
    return pd.DataFrame([
        {"relationship": "grandchild", "age": 5, "weight": 30},
        {"relationship": "grandchild", "age": 8, "weight": 50},
        {"relationship": "grandchild", "age": 12, "weight": 20},
        {"relationship": "stepchild", "age": 6, "weight": 25},
        {"relationship": "stepchild", "age": 10, "weight": 50},
        {"relationship": "stepchild", "age": 15, "weight": 25},
    ])


def _make_stepchild_patterns() -> pd.DataFrame:
    return pd.DataFrame([
        {"has_bio_children": 0, "num_stepchildren": 1, "weight": 50},
        {"has_bio_children": 0, "num_stepchildren": 2, "weight": 40},
        {"has_bio_children": 0, "num_stepchildren": 3, "weight": 10},
    ])


def _all_distributions() -> dict:
    """Full Part 1 distribution tables for pipeline testing."""
    return {
        "household_patterns": _make_household_patterns(),
        "race_by_age": _make_race_by_age(),
        "race_distribution": _make_race_distribution(),
        "hispanic_origin_by_age": _make_hispanic_origin_by_age(),
        "spousal_age_gaps": _make_spousal_age_gaps(),
        "couple_sex_patterns": _make_couple_sex_patterns(),
        "multigenerational_patterns": _make_multigenerational_patterns(),
        "children_by_parent_age": _make_children_by_parent_age(),
        "child_age_distributions": _make_child_age_distributions(),
        "stepchild_patterns": _make_stepchild_patterns(),
    }


# =========================================================================
# Helper to build a HouseholdGenerator without touching the database
# =========================================================================

def _make_generator() -> HouseholdGenerator:
    """Build a HouseholdGenerator with mocked DB, using in-memory tables."""
    distributions = _all_distributions()

    with patch.object(
        HouseholdGenerator, "__init__", lambda self, *a, **kw: None
    ):
        gen = HouseholdGenerator.__new__(HouseholdGenerator)

    gen.state = "HI"
    gen.year = 2022
    gen.distributions = distributions
    gen.demographics = DemographicsGenerator(distributions)
    gen.children = ChildGenerator(distributions)
    return gen


@pytest.fixture
def gen() -> HouseholdGenerator:
    """Pipeline generator with mocked DB."""
    return _make_generator()


# =========================================================================
# Pattern selection
# =========================================================================

class TestSelectPattern:
    """Tests for _select_pattern."""

    def test_explicit_pattern(self, gen):
        hh = gen._select_pattern("single_adult")
        assert hh.pattern == "single_adult"
        assert hh.household_id  # UUID assigned
        assert hh.state == "HI"
        assert hh.year == 2022

    def test_explicit_pattern_sets_metadata(self, gen):
        hh = gen._select_pattern("married_couple_with_children")
        assert hh.expected_adults == 2
        assert hh.expected_children_range == (1, 5)
        assert hh.expected_complexity == "simple"

    def test_random_pattern_comes_from_table(self, gen):
        set_random_seed(42)
        patterns_seen = set()
        for _ in range(50):
            hh = gen._select_pattern(None)
            patterns_seen.add(hh.pattern)
            assert hh.pattern in PATTERN_METADATA
        # With 50 draws we should see more than one pattern
        assert len(patterns_seen) > 1

    def test_random_pattern_fallback_without_table(self, gen):
        gen.distributions.pop("household_patterns", None)
        set_random_seed(42)
        hh = gen._select_pattern(None)
        assert hh.pattern in PATTERN_METADATA

    def test_unknown_pattern_uses_other_metadata(self, gen):
        hh = gen._select_pattern("nonexistent_pattern")
        assert hh.pattern == "nonexistent_pattern"
        # Falls back to 'other' metadata
        assert hh.expected_complexity == "medium"


# =========================================================================
# End-to-end Part 1 generation
# =========================================================================

class TestGeneratePart1:
    """Integration tests for generate_part1."""

    def test_basic_generation(self, gen):
        hh = gen.generate_part1(pattern="married_couple_with_children", seed=42)
        assert isinstance(hh, Household)
        assert hh.pattern == "married_couple_with_children"
        assert len(hh.members) > 0

    def test_has_householder(self, gen):
        hh = gen.generate_part1(pattern="single_adult", seed=1)
        householder = hh.get_householder()
        assert householder is not None
        assert householder.relationship == RelationshipType.HOUSEHOLDER

    def test_single_adult_has_one_member(self, gen):
        hh = gen.generate_part1(pattern="single_adult", seed=10)
        assert len(hh.members) == 1
        assert hh.members[0].is_adult()
        assert len(hh.get_children()) == 0

    def test_married_couple_no_children(self, gen):
        hh = gen.generate_part1(pattern="married_couple_no_children", seed=20)
        adults = hh.get_adults()
        children = hh.get_children()
        assert len(adults) == 2
        assert len(children) == 0
        rels = {a.relationship for a in adults}
        assert RelationshipType.HOUSEHOLDER in rels
        assert RelationshipType.SPOUSE in rels

    def test_married_couple_with_children(self, gen):
        hh = gen.generate_part1(
            pattern="married_couple_with_children", seed=30,
        )
        adults = hh.get_adults()
        children = hh.get_children()
        assert len(adults) == 2
        assert len(children) >= 1
        rels = {a.relationship for a in adults}
        assert RelationshipType.HOUSEHOLDER in rels
        assert RelationshipType.SPOUSE in rels

    def test_single_parent(self, gen):
        hh = gen.generate_part1(pattern="single_parent", seed=40)
        adults = hh.get_adults()
        children = hh.get_children()
        assert len(adults) == 1
        assert len(children) >= 1
        assert adults[0].relationship == RelationshipType.HOUSEHOLDER

    def test_blended_family(self, gen):
        hh = gen.generate_part1(pattern="blended_family", seed=50)
        adults = hh.get_adults()
        children = hh.get_children()
        assert len(adults) == 2
        assert len(children) >= 2
        child_rels = {c.relationship for c in children}
        # Blended family must have at least one bio + one stepchild
        assert RelationshipType.BIOLOGICAL_CHILD in child_rels
        assert RelationshipType.STEPCHILD in child_rels

    def test_unmarried_partners(self, gen):
        hh = gen.generate_part1(pattern="unmarried_partners", seed=60)
        adults = hh.get_adults()
        assert len(adults) == 2
        rels = {a.relationship for a in adults}
        assert RelationshipType.HOUSEHOLDER in rels
        assert RelationshipType.UNMARRIED_PARTNER in rels

    def test_multigenerational(self, gen):
        hh = gen.generate_part1(pattern="multigenerational", seed=70)
        adults = hh.get_adults()
        assert len(adults) >= 2

    def test_seed_reproducibility(self, gen):
        hh1 = gen.generate_part1(pattern="married_couple_with_children", seed=99)
        hh2 = gen.generate_part1(pattern="married_couple_with_children", seed=99)
        assert len(hh1.members) == len(hh2.members)
        for m1, m2 in zip(hh1.members, hh2.members):
            assert m1.age == m2.age
            assert m1.sex == m2.sex
            assert m1.race == m2.race
            assert m1.relationship == m2.relationship

    def test_different_seeds_produce_different_results(self, gen):
        results = []
        for seed in range(5):
            hh = gen.generate_part1(pattern="married_couple_with_children", seed=seed)
            results.append(tuple(m.age for m in hh.members))
        # Not all should be identical
        assert len(set(results)) > 1


# =========================================================================
# Member validation across patterns
# =========================================================================

class TestMemberValidation:
    """Cross-cutting checks for generated members."""

    @pytest.mark.parametrize("pattern", list(PATTERN_METADATA.keys()))
    def test_all_patterns_produce_valid_household(self, gen, pattern):
        hh = gen.generate_part1(pattern=pattern, seed=42)
        assert isinstance(hh, Household)
        assert hh.household_id
        assert hh.state == "HI"
        assert hh.year == 2022
        assert hh.pattern == pattern
        # Must have at least one member
        assert len(hh.members) >= 1
        # Must have a householder
        assert hh.get_householder() is not None

    @pytest.mark.parametrize("pattern", list(PATTERN_METADATA.keys()))
    def test_all_members_have_demographics(self, gen, pattern):
        hh = gen.generate_part1(pattern=pattern, seed=42)
        for person in hh.members:
            assert person.person_id
            assert person.age >= 0
            assert person.sex in ("M", "F")
            assert person.race
            assert isinstance(person.hispanic_origin, bool)
            assert isinstance(person.relationship, RelationshipType)

    @pytest.mark.parametrize("pattern", list(PATTERN_METADATA.keys()))
    def test_adults_are_18_plus(self, gen, pattern):
        hh = gen.generate_part1(pattern=pattern, seed=42)
        for adult in hh.get_adults():
            assert adult.age >= 18

    @pytest.mark.parametrize("pattern", list(PATTERN_METADATA.keys()))
    def test_children_are_under_18(self, gen, pattern):
        hh = gen.generate_part1(pattern=pattern, seed=42)
        for child in hh.get_children():
            assert child.age < 18

    @pytest.mark.parametrize("pattern", list(PATTERN_METADATA.keys()))
    def test_no_pii_fields_populated(self, gen, pattern):
        """Part 1 should NOT populate PII — that's Sprint 4."""
        hh = gen.generate_part1(pattern=pattern, seed=42)
        for person in hh.members:
            assert person.legal_first_name == ""
            assert person.legal_last_name == ""
            assert person.ssn == ""
            assert person.dob is None


# =========================================================================
# Serialization
# =========================================================================

class TestSerialization:
    """Verify to_dict works on pipeline output."""

    def test_to_dict_runs(self, gen):
        hh = gen.generate_part1(pattern="married_couple_with_children", seed=42)
        d = hh.to_dict()
        assert isinstance(d, dict)
        assert d["pattern"] == "married_couple_with_children"
        assert d["state"] == "HI"
        assert isinstance(d["members"], list)
        assert len(d["members"]) > 0

    def test_to_dict_member_fields(self, gen):
        hh = gen.generate_part1(pattern="single_parent", seed=42)
        d = hh.to_dict()
        member = d["members"][0]
        assert "age" in member
        assert "sex" in member
        assert "race" in member
        assert "relationship" in member
        assert "person_id" in member
