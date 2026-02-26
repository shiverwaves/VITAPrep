"""Shared test fixtures."""
import pytest
from generator.models import Person, Household, Address, RelationshipType


@pytest.fixture
def sample_person():
    """A basic adult person for testing."""
    return Person(
        person_id="test-001",
        relationship=RelationshipType.HOUSEHOLDER,
        age=35,
        sex="M",
        race="white",
    )


@pytest.fixture
def sample_household():
    """A basic married couple household for testing."""
    return Household(
        household_id="hh-001",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
    )
