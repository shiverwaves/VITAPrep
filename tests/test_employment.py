"""Tests for generator.employment — employment attribute assignment."""

import numpy as np
import pandas as pd
import pytest

from generator.employment import EmploymentGenerator, _age_to_bracket
from generator.models import Household, Person, RelationshipType


# ── Fixtures ───────────────────────────────────────────────────────────


def _make_person(age: int, relationship: RelationshipType = RelationshipType.HOUSEHOLDER) -> Person:
    return Person(person_id=f"p-{age}", age=age, sex="M", relationship=relationship)


def _make_household(*ages: int) -> Household:
    members = []
    for i, age in enumerate(ages):
        rel = RelationshipType.HOUSEHOLDER if i == 0 else RelationshipType.SPOUSE
        if age < 18:
            rel = RelationshipType.BIOLOGICAL_CHILD
        members.append(_make_person(age, rel))
    return Household(household_id="hh-test", members=members)


def _make_distributions() -> dict:
    """Build synthetic Part 2 distribution tables."""
    employment = pd.DataFrame([
        {"age_bracket": "25-34", "employment_status": "employed", "weight": 700},
        {"age_bracket": "25-34", "employment_status": "unemployed", "weight": 50},
        {"age_bracket": "25-34", "employment_status": "not_in_labor_force", "weight": 250},
        {"age_bracket": "65+", "employment_status": "employed", "weight": 200},
        {"age_bracket": "65+", "employment_status": "not_in_labor_force", "weight": 800},
    ])

    education = pd.DataFrame([
        {"age_bracket": "25-34", "education_level": "bachelors", "weight": 400},
        {"age_bracket": "25-34", "education_level": "high_school", "weight": 300},
        {"age_bracket": "25-34", "education_level": "masters", "weight": 200},
        {"age_bracket": "25-34", "education_level": "some_college", "weight": 100},
        {"age_bracket": "65+", "education_level": "high_school", "weight": 500},
        {"age_bracket": "65+", "education_level": "bachelors", "weight": 300},
        {"age_bracket": "65+", "education_level": "masters", "weight": 200},
    ])

    disability = pd.DataFrame([
        {"age_bracket": "25-34", "has_disability": 0, "weight": 900, "proportion": 0.90},
        {"age_bracket": "25-34", "has_disability": 1, "weight": 100, "proportion": 0.10},
        {"age_bracket": "65+", "has_disability": 0, "weight": 700, "proportion": 0.70},
        {"age_bracket": "65+", "has_disability": 1, "weight": 300, "proportion": 0.30},
    ])

    edu_occ = pd.DataFrame([
        {"education_level": "bachelors", "occupation_group": "management", "weight": 300},
        {"education_level": "bachelors", "occupation_group": "computer_math", "weight": 200},
        {"education_level": "bachelors", "occupation_group": "sales", "weight": 150},
        {"education_level": "high_school", "occupation_group": "sales", "weight": 250},
        {"education_level": "high_school", "occupation_group": "construction", "weight": 200},
        {"education_level": "high_school", "occupation_group": "office_admin", "weight": 150},
        {"education_level": "masters", "occupation_group": "management", "weight": 400},
        {"education_level": "masters", "occupation_group": "education", "weight": 300},
    ])

    return {
        "employment_by_age": employment,
        "education_by_age": education,
        "disability_by_age": disability,
        "education_occupation_probabilities": edu_occ,
    }


@pytest.fixture
def gen() -> EmploymentGenerator:
    return EmploymentGenerator(_make_distributions())


@pytest.fixture
def gen_no_tables() -> EmploymentGenerator:
    return EmploymentGenerator({})


# ── Tests ──────────────────────────────────────────────────────────────


class TestAgeToBracket:
    def test_child(self) -> None:
        assert _age_to_bracket(10) == "Under 18"

    def test_young_adult(self) -> None:
        assert _age_to_bracket(22) == "18-24"

    def test_senior(self) -> None:
        assert _age_to_bracket(70) == "65+"


class TestOverlay:
    def test_adults_get_employment(self, gen: EmploymentGenerator) -> None:
        hh = _make_household(30, 28)
        gen.overlay(hh)
        for p in hh.members:
            assert p.employment_status in ("employed", "unemployed", "not_in_labor_force")
            assert p.education != ""

    def test_children_get_defaults(self, gen: EmploymentGenerator) -> None:
        hh = _make_household(35, 10)
        gen.overlay(hh)
        child = hh.members[1]
        assert child.employment_status == "not_in_labor_force"
        assert child.education == "less_than_hs"
        assert child.occupation_code is None

    def test_employed_gets_occupation(self, gen: EmploymentGenerator) -> None:
        np.random.seed(42)
        hh = _make_household(30)
        # Run multiple times to get at least one employed person
        for _ in range(20):
            gen.overlay(hh)
            if hh.members[0].employment_status == "employed":
                break
        if hh.members[0].employment_status == "employed":
            assert hh.members[0].occupation_code is not None
            assert hh.members[0].occupation_title is not None

    def test_unemployed_no_occupation(self, gen: EmploymentGenerator) -> None:
        np.random.seed(0)
        hh = _make_household(30)
        for _ in range(50):
            gen.overlay(hh)
            if hh.members[0].employment_status != "employed":
                break
        if hh.members[0].employment_status != "employed":
            assert hh.members[0].occupation_code is None

    def test_senior_higher_nilf(self, gen: EmploymentGenerator) -> None:
        np.random.seed(42)
        nilf_count = 0
        n = 100
        for _ in range(n):
            hh = _make_household(70)
            gen.overlay(hh)
            if hh.members[0].employment_status == "not_in_labor_force":
                nilf_count += 1
        assert nilf_count > n * 0.5

    def test_senior_higher_disability(self, gen: EmploymentGenerator) -> None:
        np.random.seed(42)
        disabled_count = 0
        n = 200
        for _ in range(n):
            hh = _make_household(70)
            gen.overlay(hh)
            if hh.members[0].has_disability:
                disabled_count += 1
        assert disabled_count > n * 0.15


class TestFallbacks:
    def test_no_tables_still_works(self, gen_no_tables: EmploymentGenerator) -> None:
        hh = _make_household(30, 65)
        gen_no_tables.overlay(hh)
        for p in hh.members:
            assert p.employment_status in ("employed", "unemployed", "not_in_labor_force")
            assert p.education != ""

    def test_fallback_occupation_by_education(self, gen_no_tables: EmploymentGenerator) -> None:
        np.random.seed(42)
        hh = _make_household(30)
        for _ in range(20):
            gen_no_tables.overlay(hh)
            if hh.members[0].employment_status == "employed":
                break
        if hh.members[0].employment_status == "employed":
            assert hh.members[0].occupation_code is not None


class TestOccupationSampling:
    def test_education_influences_occupation(self, gen: EmploymentGenerator) -> None:
        np.random.seed(42)
        occupations = set()
        for _ in range(50):
            p = _make_person(35)
            p.employment_status = "employed"
            p.education = "masters"
            _, _ = gen._sample_occupation(p)
            occupations.add(gen._sample_occupation(p)[0])
        # Masters should mostly get management/education/etc., not food_service
        assert "management" in occupations or "education" in occupations

    def test_occupation_title_populated(self, gen: EmploymentGenerator) -> None:
        p = _make_person(35)
        p.employment_status = "employed"
        p.education = "bachelors"
        group, title = gen._sample_occupation(p)
        assert group != ""
        assert title != ""
        assert "_" not in title  # Title should be human-readable
