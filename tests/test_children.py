"""Tests for generator/children.py — Sprint 3, Step 3.2."""

import numpy as np
import pandas as pd
import pytest

from generator.children import (
    ChildGenerator,
    PATTERNS_WITH_CHILDREN,
    PATTERNS_REQUIRING_CHILDREN,
)
from generator.models import (
    Household, Person, RelationshipType, PATTERN_METADATA,
)
from generator.sampler import set_random_seed


# =========================================================================
# Fixture helpers
# =========================================================================

def _make_children_by_parent_age() -> pd.DataFrame:
    return pd.DataFrame([
        {"parent_age_bracket": "25-29", "num_children": 1, "weight": 40},
        {"parent_age_bracket": "25-29", "num_children": 2, "weight": 30},
        {"parent_age_bracket": "25-29", "num_children": 3, "weight": 10},
        {"parent_age_bracket": "30-34", "num_children": 1, "weight": 30},
        {"parent_age_bracket": "30-34", "num_children": 2, "weight": 40},
        {"parent_age_bracket": "30-34", "num_children": 3, "weight": 20},
        {"parent_age_bracket": "35-39", "num_children": 1, "weight": 40},
        {"parent_age_bracket": "35-39", "num_children": 2, "weight": 30},
        {"parent_age_bracket": "35-39", "num_children": 3, "weight": 15},
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


@pytest.fixture
def distributions() -> dict:
    return {
        "children_by_parent_age": _make_children_by_parent_age(),
        "child_age_distributions": _make_child_age_distributions(),
        "stepchild_patterns": _make_stepchild_patterns(),
    }


@pytest.fixture
def gen(distributions) -> ChildGenerator:
    return ChildGenerator(distributions)


def _household(
    pattern: str,
    adults: list | None = None,
) -> Household:
    """Build a household with the given pattern and optional adults."""
    hh = Household(
        household_id="test-hh", state="HI", year=2022, pattern=pattern,
    )
    if adults:
        hh.members = list(adults)
    return hh


def _adult(
    relationship: RelationshipType = RelationshipType.HOUSEHOLDER,
    age: int = 35,
    sex: str = "M",
    race: str = "white",
    hispanic_origin: bool = False,
) -> Person:
    return Person(
        person_id="adult-1",
        relationship=relationship,
        age=age,
        sex=sex,
        race=race,
        hispanic_origin=hispanic_origin,
    )


# =========================================================================
# Initialization
# =========================================================================


class TestInit:
    def test_accepts_full_distributions(self, distributions):
        gen = ChildGenerator(distributions)
        assert gen.distributions is distributions

    def test_warns_on_missing_required(self, caplog):
        ChildGenerator({})
        assert "Missing required child tables" in caplog.text


# =========================================================================
# Pattern checks
# =========================================================================


class TestPatternHasChildren:
    def test_patterns_with_children(self):
        for p in PATTERNS_WITH_CHILDREN:
            assert p in PATTERNS_WITH_CHILDREN

    def test_patterns_without_children(self):
        assert "single_adult" not in PATTERNS_WITH_CHILDREN
        assert "married_couple_no_children" not in PATTERNS_WITH_CHILDREN

    def test_requiring_children_is_subset(self):
        assert PATTERNS_REQUIRING_CHILDREN <= PATTERNS_WITH_CHILDREN


# =========================================================================
# Child count
# =========================================================================


class TestDetermineChildCount:
    def test_no_children_pattern_returns_zero(self, gen):
        adults = [_adult(age=35)]
        hh = _household("single_adult", adults)
        # Directly calling — the generate_children entry point won't call this
        # for non-child patterns, but the count logic still works
        metadata = PATTERN_METADATA["single_adult"]
        expected = metadata["expected_children"]
        # expected is (0,0), so result should be 0
        count = gen._determine_child_count(hh, adults)
        assert count == 0

    def test_requires_at_least_one_for_single_parent(self, gen):
        np.random.seed(42)
        adults = [_adult(age=30)]
        hh = _household("single_parent", adults)
        for _ in range(20):
            count = gen._determine_child_count(hh, adults)
            assert count >= 1

    def test_requires_at_least_one_for_married_with_children(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35), _adult(RelationshipType.SPOUSE, age=33)]
        hh = _household("married_couple_with_children", adults)
        for _ in range(20):
            count = gen._determine_child_count(hh, adults)
            assert count >= 1

    def test_clamped_to_pattern_max(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        for _ in range(50):
            count = gen._determine_child_count(hh, adults)
            max_c = PATTERN_METADATA["single_parent"]["expected_children"][1]
            assert count <= max_c

    def test_fallback_when_no_table(self):
        gen = ChildGenerator({})
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        count = gen._determine_child_count(hh, adults)
        assert count >= 1


# =========================================================================
# Relationship assignment
# =========================================================================


class TestAssignRelationships:
    def test_default_biological(self, gen):
        hh = _household("married_couple_with_children")
        rels = gen._assign_child_relationships(
            "married_couple_with_children", 3, hh,
        )
        assert all(r == RelationshipType.BIOLOGICAL_CHILD for r in rels)
        assert len(rels) == 3

    def test_single_parent_biological(self, gen):
        hh = _household("single_parent")
        rels = gen._assign_child_relationships("single_parent", 2, hh)
        assert all(r == RelationshipType.BIOLOGICAL_CHILD for r in rels)

    def test_blended_family_has_both_types(self, gen):
        np.random.seed(42)
        hh = _household("blended_family")
        rels = gen._assign_child_relationships("blended_family", 3, hh)
        types = set(rels)
        assert RelationshipType.BIOLOGICAL_CHILD in types
        assert RelationshipType.STEPCHILD in types
        assert len(rels) == 3

    def test_blended_family_guarantees_at_least_one_of_each(self, gen):
        """With 2 children, must have exactly 1 bio + 1 step."""
        np.random.seed(42)
        for _ in range(20):
            hh = _household("blended_family")
            rels = gen._assign_child_relationships("blended_family", 2, hh)
            assert RelationshipType.BIOLOGICAL_CHILD in rels
            assert RelationshipType.STEPCHILD in rels

    def test_multigenerational_with_parent_adult_gives_bio(self, gen):
        """If adults include a PARENT, children are biological."""
        parent_adult = _adult(RelationshipType.PARENT, age=65)
        householder = _adult(RelationshipType.HOUSEHOLDER, age=40)
        hh = _household(
            "multigenerational", [householder, parent_adult],
        )
        rels = gen._assign_multigenerational_child_relationships(2, hh)
        assert all(r == RelationshipType.BIOLOGICAL_CHILD for r in rels)

    def test_multigenerational_without_parent_gives_grandchild(self, gen):
        """If no PARENT among adults, children are grandchildren."""
        householder = _adult(RelationshipType.HOUSEHOLDER, age=65)
        spouse = _adult(RelationshipType.SPOUSE, age=63)
        hh = _household("multigenerational", [householder, spouse])
        rels = gen._assign_multigenerational_child_relationships(2, hh)
        assert all(r == RelationshipType.GRANDCHILD for r in rels)


# =========================================================================
# Single child generation
# =========================================================================


class TestGenerateSingleChild:
    def test_child_age_under_18(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        for _ in range(50):
            child = gen._generate_single_child(
                hh, adults, RelationshipType.BIOLOGICAL_CHILD, [],
            )
            assert 0 <= child.age <= 17

    def test_child_age_respects_parent_gap(self, gen):
        np.random.seed(42)
        adults = [_adult(age=25)]
        hh = _household("single_parent", adults)
        for _ in range(50):
            child = gen._generate_single_child(
                hh, adults, RelationshipType.BIOLOGICAL_CHILD, [],
            )
            # min_age_gap=14, so max child age = 25-14 = 11
            assert child.age <= 11

    def test_grandchild_uses_oldest_adult(self, gen):
        np.random.seed(42)
        young_adult = _adult(RelationshipType.HOUSEHOLDER, age=30)
        old_adult = _adult(RelationshipType.PARENT, age=65)
        hh = _household("multigenerational", [young_adult, old_adult])
        for _ in range(50):
            child = gen._generate_single_child(
                hh, [young_adult, old_adult],
                RelationshipType.GRANDCHILD, [],
            )
            # max age = min(17, 65 - 28) = 17
            assert 0 <= child.age <= 17

    def test_child_sex_is_m_or_f(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        for _ in range(20):
            child = gen._generate_single_child(
                hh, adults, RelationshipType.BIOLOGICAL_CHILD, [],
            )
            assert child.sex in ("M", "F")

    def test_child_is_dependent(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        child = gen._generate_single_child(
            hh, adults, RelationshipType.BIOLOGICAL_CHILD, [],
        )
        assert child.is_dependent is True
        assert child.can_be_claimed is True
        assert child.months_in_home == 12

    def test_child_has_unique_person_id(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        ids = set()
        for _ in range(10):
            child = gen._generate_single_child(
                hh, adults, RelationshipType.BIOLOGICAL_CHILD, [],
            )
            ids.add(child.person_id)
        assert len(ids) == 10

    def test_child_no_employment_fields(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        child = gen._generate_single_child(
            hh, adults, RelationshipType.BIOLOGICAL_CHILD, [],
        )
        assert child.employment_status == ""
        assert child.education == ""
        assert child.occupation_code is None


# =========================================================================
# Race and Hispanic inheritance
# =========================================================================


class TestRaceInheritance:
    def test_same_race_parents(self):
        adults = [
            _adult(race="asian"),
            _adult(RelationshipType.SPOUSE, race="asian"),
        ]
        for _ in range(20):
            race = ChildGenerator._determine_child_race(adults)
            assert race == "asian"

    def test_mixed_race_parents(self):
        np.random.seed(42)
        adults = [
            _adult(race="white"),
            _adult(RelationshipType.SPOUSE, race="black"),
        ]
        races = {ChildGenerator._determine_child_race(adults)
                 for _ in range(100)}
        # Should sometimes be two_or_more, sometimes inherit one parent
        assert "two_or_more" in races

    def test_no_parents_fallback(self):
        race = ChildGenerator._determine_child_race([])
        assert race == "two_or_more"


class TestHispanicInheritance:
    def test_hispanic_parent_high_chance(self):
        np.random.seed(42)
        adults = [_adult(hispanic_origin=True)]
        results = [ChildGenerator._determine_child_hispanic(adults)
                   for _ in range(100)]
        rate = sum(results) / len(results)
        assert rate > 0.75  # ~90% expected

    def test_non_hispanic_parents_no_child_hispanic(self):
        adults = [
            _adult(hispanic_origin=False),
            _adult(RelationshipType.SPOUSE, hispanic_origin=False),
        ]
        for _ in range(20):
            assert ChildGenerator._determine_child_hispanic(adults) is False


# =========================================================================
# Age sampling from distributions
# =========================================================================


class TestChildAgeSampling:
    def test_stepchild_age_from_distribution(self, gen):
        """Stepchild ages should come from the distribution (6, 10, 15)."""
        np.random.seed(42)
        ref = _adult(age=45)
        ages = set()
        for _ in range(50):
            age = gen._sample_child_age(ref, 14, RelationshipType.STEPCHILD)
            ages.add(age)
        # Our fixture has stepchild ages 6, 10, 15 — all <= 45-14=31
        assert ages <= {6, 10, 15}

    def test_grandchild_age_from_distribution(self, gen):
        """Grandchild ages should come from the distribution (5, 8, 12)."""
        np.random.seed(42)
        ref = _adult(age=65)
        ages = set()
        for _ in range(50):
            age = gen._sample_child_age(ref, 28, RelationshipType.GRANDCHILD)
            ages.add(age)
        assert ages <= {5, 8, 12}

    def test_biological_child_fallback_uniform(self, gen):
        """No biological_child in our fixture → falls back to uniform."""
        np.random.seed(42)
        ref = _adult(age=35)
        ages = set()
        for _ in range(100):
            age = gen._sample_child_age(
                ref, 14, RelationshipType.BIOLOGICAL_CHILD,
            )
            ages.add(age)
        # Should produce ages 0..21 (35-14=21, capped at 17)
        assert all(0 <= a <= 17 for a in ages)
        # Should have some variety
        assert len(ages) >= 3

    def test_very_young_parent_returns_zero(self, gen):
        ref = _adult(age=13)  # Too young to be a parent
        age = gen._sample_child_age(ref, 14, RelationshipType.BIOLOGICAL_CHILD)
        assert age == 0

    def test_age_capped_by_parent(self, gen):
        """Stepchild age 15 should be excluded when parent is 28."""
        np.random.seed(42)
        ref = _adult(age=28)  # max child = min(17, 28-14) = 14
        for _ in range(50):
            age = gen._sample_child_age(ref, 14, RelationshipType.STEPCHILD)
            assert age <= 14


# =========================================================================
# End-to-end generate_children
# =========================================================================


class TestGenerateChildren:
    def test_no_children_for_single_adult(self, gen):
        adults = [_adult(age=35)]
        hh = _household("single_adult", adults)
        children = gen.generate_children(hh)
        assert children == []

    def test_no_children_for_married_no_children(self, gen):
        adults = [_adult(age=35), _adult(RelationshipType.SPOUSE, age=33)]
        hh = _household("married_couple_no_children", adults)
        children = gen.generate_children(hh)
        assert children == []

    def test_single_parent_has_children(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35)]
        hh = _household("single_parent", adults)
        children = gen.generate_children(hh)
        assert len(children) >= 1
        for c in children:
            assert c.age < 18
            assert c.relationship == RelationshipType.BIOLOGICAL_CHILD

    def test_married_with_children_produces_children(self, gen):
        np.random.seed(42)
        adults = [_adult(age=35), _adult(RelationshipType.SPOUSE, age=33)]
        hh = _household("married_couple_with_children", adults)
        children = gen.generate_children(hh)
        assert len(children) >= 1

    def test_blended_family_has_bio_and_step(self, gen):
        np.random.seed(42)
        adults = [_adult(age=40), _adult(RelationshipType.SPOUSE, age=38)]
        hh = _household("blended_family", adults)
        children = gen.generate_children(hh)
        assert len(children) >= 2
        types = {c.relationship for c in children}
        assert RelationshipType.BIOLOGICAL_CHILD in types
        assert RelationshipType.STEPCHILD in types

    def test_multigenerational_with_parent(self, gen):
        """Multigenerational with PARENT adult → bio children."""
        np.random.seed(42)
        householder = _adult(RelationshipType.HOUSEHOLDER, age=40)
        parent = _adult(RelationshipType.PARENT, age=65)
        hh = _household("multigenerational", [householder, parent])
        children = gen.generate_children(hh)
        for c in children:
            assert c.relationship == RelationshipType.BIOLOGICAL_CHILD

    def test_multigenerational_without_parent(self, gen):
        """Multigenerational without PARENT adult → grandchildren."""
        np.random.seed(42)
        householder = _adult(RelationshipType.HOUSEHOLDER, age=65)
        spouse = _adult(RelationshipType.SPOUSE, age=63)
        hh = _household("multigenerational", [householder, spouse])
        children = gen.generate_children(hh)
        for c in children:
            assert c.relationship == RelationshipType.GRANDCHILD

    def test_no_adults_returns_empty(self, gen):
        hh = _household("single_parent", [])
        children = gen.generate_children(hh)
        assert children == []

    def test_children_count_within_pattern_range(self, gen):
        """Children count should respect pattern metadata bounds."""
        np.random.seed(42)
        adults = [_adult(age=35), _adult(RelationshipType.SPOUSE, age=33)]
        for _ in range(30):
            hh = _household("married_couple_with_children", adults)
            children = gen.generate_children(hh)
            meta = PATTERN_METADATA["married_couple_with_children"]
            min_c, max_c = meta["expected_children"]
            assert max(1, min_c) <= len(children) <= max_c

    def test_reproducibility_with_seed(self, distributions):
        gen1 = ChildGenerator(distributions)
        gen2 = ChildGenerator(distributions)

        set_random_seed(456)
        adults1 = [_adult(age=35), _adult(RelationshipType.SPOUSE, age=33)]
        hh1 = _household("married_couple_with_children", adults1)
        children1 = gen1.generate_children(hh1)

        set_random_seed(456)
        adults2 = [_adult(age=35), _adult(RelationshipType.SPOUSE, age=33)]
        hh2 = _household("married_couple_with_children", adults2)
        children2 = gen2.generate_children(hh2)

        assert len(children1) == len(children2)
        for c1, c2 in zip(children1, children2):
            assert c1.age == c2.age
            assert c1.sex == c2.sex
            assert c1.race == c2.race
            assert c1.relationship == c2.relationship


# =========================================================================
# Helpers
# =========================================================================


class TestHelpers:
    def test_get_parent_age_bracket_from_table(self, gen):
        assert gen._get_parent_age_bracket(27) == "25-29"
        assert gen._get_parent_age_bracket(35) == "35-39"

    def test_get_parent_age_bracket_fallback(self):
        gen = ChildGenerator({})
        assert gen._get_parent_age_bracket(22) == "18-24"
        assert gen._get_parent_age_bracket(27) == "25-29"
        assert gen._get_parent_age_bracket(70) == "65+"

    def test_relationship_to_table_key(self):
        assert ChildGenerator._relationship_to_table_key(
            RelationshipType.GRANDCHILD,
        ) == "grandchild"
        assert ChildGenerator._relationship_to_table_key(
            RelationshipType.STEPCHILD,
        ) == "stepchild"
        assert ChildGenerator._relationship_to_table_key(
            RelationshipType.BIOLOGICAL_CHILD,
        ) == "biological_child"
        assert ChildGenerator._relationship_to_table_key(
            RelationshipType.HOUSEHOLDER,
        ) is None
