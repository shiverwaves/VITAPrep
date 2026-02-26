"""Tests for generator/models.py — Sprint 1."""
from generator.models import (
    Person, Household, Address, FilingUnit,
    RelationshipType, FilingStatus, PATTERN_METADATA,
)


def test_person_creation():
    p = Person(person_id="p1", age=30, sex="F", race="white")
    assert p.is_adult()
    assert not p.is_child()
    assert not p.is_senior()


def test_person_full_legal_name():
    p = Person(
        legal_first_name="James",
        legal_middle_name="Keoni",
        legal_last_name="Nakamura",
        suffix="Jr.",
    )
    assert p.full_legal_name() == "James Keoni Nakamura Jr."


def test_person_to_dict():
    p = Person(person_id="p1", age=30, sex="M")
    d = p.to_dict()
    assert d["person_id"] == "p1"
    assert d["age"] == 30
    assert d["is_adult"] is True


def test_household_helpers():
    householder = Person(person_id="h1", relationship=RelationshipType.HOUSEHOLDER, age=40)
    spouse = Person(person_id="s1", relationship=RelationshipType.SPOUSE, age=38)
    child = Person(person_id="c1", relationship=RelationshipType.BIOLOGICAL_CHILD, age=10)

    hh = Household(
        household_id="hh1",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
        members=[householder, spouse, child],
    )
    assert len(hh.get_adults()) == 2
    assert len(hh.get_children()) == 1
    assert hh.get_householder() == householder
    assert hh.get_spouse() == spouse
    assert hh.is_married()
    assert hh.derive_filing_status() == FilingStatus.MARRIED_FILING_JOINTLY


def test_household_single_hoh():
    parent = Person(person_id="h1", relationship=RelationshipType.HOUSEHOLDER, age=30)
    child = Person(person_id="c1", relationship=RelationshipType.BIOLOGICAL_CHILD, age=5)
    hh = Household(members=[parent, child])
    assert not hh.is_married()
    assert hh.derive_filing_status() == FilingStatus.HEAD_OF_HOUSEHOLD


def test_address_one_line():
    addr = Address(street="123 Main St", apt="Apt 4", city="Honolulu", state="HI", zip_code="96816")
    assert addr.one_line() == "123 Main St, Apt 4, Honolulu, HI 96816"


def test_pattern_metadata_complete():
    expected = [
        "married_couple_no_children", "married_couple_with_children",
        "single_parent", "single_adult", "blended_family",
        "multigenerational", "unmarried_partners", "other",
    ]
    for pattern in expected:
        assert pattern in PATTERN_METADATA
