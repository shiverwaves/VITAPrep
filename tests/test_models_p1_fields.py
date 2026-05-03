"""Tests for Phase 1A model field additions.

The Person and Household dataclasses gained boolean and date fields
in commit c253bde to back the new 13614-C Page 1 status / marital /
two-states questions. These tests assert:

1. Defaults preserve existing scenario generation (additive change).
2. to_dict() includes the new fields.
3. The scenario_store round-trip preserves them.
"""

from datetime import date

import pytest

from generator.models import Address, Household, Person, RelationshipType
from training.scenario_store import (
    _deserialize_household,
    _serialize_household,
)


def _person(**overrides) -> Person:
    base = dict(
        person_id="p-1",
        relationship=RelationshipType.HOUSEHOLDER,
        legal_first_name="Test",
        legal_last_name="Person",
    )
    base.update(overrides)
    return Person(**base)


def _household(**overrides) -> Household:
    base = dict(
        household_id="hh-1",
        state="HI",
        year=2022,
        pattern="single_adult",
        members=[_person()],
        address=Address(street="1 Main", city="Honolulu",
                        state="HI", zip_code="96815"),
    )
    base.update(overrides)
    return Household(**base)


class TestPhase1ADefaults:

    def test_person_defaults(self) -> None:
        p = _person()
        assert p.us_citizen is True
        assert p.on_visa is False
        assert p.legally_blind is False
        assert p.has_ippin is False
        assert p.marital_history == ""

    def test_household_defaults(self) -> None:
        hh = _household()
        assert hh.lived_in_two_states is False
        assert hh.spouses_lived_apart_h2 is False
        assert hh.divorce_date is None
        assert hh.separation_date is None
        assert hh.spouse_death_year is None
        assert hh.has_digital_assets is False


class TestToDictIncludesNewFields:

    def test_person_to_dict(self) -> None:
        p = _person(
            us_citizen=False,
            on_visa=True,
            legally_blind=True,
            has_ippin=True,
            marital_history="widowed",
        )
        d = p.to_dict()
        assert d["us_citizen"] is False
        assert d["on_visa"] is True
        assert d["legally_blind"] is True
        assert d["has_ippin"] is True
        assert d["marital_history"] == "widowed"

    def test_household_to_dict(self) -> None:
        hh = _household(
            lived_in_two_states=True,
            spouses_lived_apart_h2=True,
            divorce_date=date(2024, 6, 15),
            separation_date=date(2023, 1, 1),
            spouse_death_year=2022,
            has_digital_assets=True,
        )
        d = hh.to_dict()
        assert d["lived_in_two_states"] is True
        assert d["spouses_lived_apart_h2"] is True
        assert d["divorce_date"] == "2024-06-15"
        assert d["separation_date"] == "2023-01-01"
        assert d["spouse_death_year"] == 2022
        assert d["has_digital_assets"] is True

    def test_household_to_dict_handles_none_dates(self) -> None:
        hh = _household()
        d = hh.to_dict()
        assert d["divorce_date"] is None
        assert d["separation_date"] is None
        assert d["spouse_death_year"] is None


class TestScenarioStoreRoundtrip:
    """The scenario_store serializes Household via dataclasses.asdict
    and deserializes via _deserialize_household — confirm the new
    fields survive a save / load cycle."""

    def test_person_fields_roundtrip(self) -> None:
        original = _household(members=[
            _person(
                us_citizen=False,
                on_visa=True,
                legally_blind=True,
                has_ippin=True,
                marital_history="divorced",
            ),
        ])
        blob = _serialize_household(original)
        restored = _deserialize_household(blob)

        p = restored.members[0]
        assert p.us_citizen is False
        assert p.on_visa is True
        assert p.legally_blind is True
        assert p.has_ippin is True
        assert p.marital_history == "divorced"

    def test_household_fields_roundtrip(self) -> None:
        original = _household(
            lived_in_two_states=True,
            spouses_lived_apart_h2=True,
            divorce_date=date(2024, 6, 15),
            separation_date=date(2023, 1, 1),
            spouse_death_year=2022,
            has_digital_assets=True,
        )
        blob = _serialize_household(original)
        restored = _deserialize_household(blob)

        assert restored.lived_in_two_states is True
        assert restored.spouses_lived_apart_h2 is True
        assert restored.divorce_date == date(2024, 6, 15)
        assert restored.separation_date == date(2023, 1, 1)
        assert restored.spouse_death_year == 2022
        assert restored.has_digital_assets is True

    def test_pre_phase1a_blob_loads_with_defaults(self) -> None:
        """A serialized household from before Phase 1A (without the new
        keys) must still deserialize cleanly, with defaults filled in."""
        import json
        # Use the real serializer so enum values render correctly, then
        # strip the keys that didn't exist before Phase 1A.
        full_blob = _serialize_household(_household())
        d = json.loads(full_blob)
        for k in (
            "lived_in_two_states", "spouses_lived_apart_h2",
            "divorce_date", "separation_date",
            "spouse_death_year", "has_digital_assets",
        ):
            d.pop(k, None)
        for member in d["members"]:
            for k in (
                "us_citizen", "on_visa", "legally_blind",
                "has_ippin", "marital_history",
            ):
                member.pop(k, None)

        restored = _deserialize_household(json.dumps(d))

        assert restored.lived_in_two_states is False
        assert restored.has_digital_assets is False
        assert restored.members[0].us_citizen is True
        assert restored.members[0].marital_history == ""
