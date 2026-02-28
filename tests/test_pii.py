"""Tests for generator/pii.py — Sprint 4.

Verifies that PIIGenerator correctly overlays names, SSNs, DOBs,
addresses, ID documents, phone, and email onto a household produced
by the Part 1 pipeline.
"""

import re
from datetime import date

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
)
from generator.pii import PIIGenerator


# =========================================================================
# Fixture helpers
# =========================================================================

def _make_single_adult_household() -> Household:
    """Single adult, no children."""
    return Household(
        household_id="hh-single",
        state="HI",
        year=2022,
        pattern="single_adult",
        members=[
            Person(
                person_id="p-1",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30,
                sex="M",
                race="white",
            ),
        ],
    )


def _make_married_couple_household() -> Household:
    """Married couple with two biological children."""
    return Household(
        household_id="hh-married",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
        members=[
            Person(
                person_id="p-1",
                relationship=RelationshipType.HOUSEHOLDER,
                age=40,
                sex="M",
                race="asian",
                hispanic_origin=False,
            ),
            Person(
                person_id="p-2",
                relationship=RelationshipType.SPOUSE,
                age=38,
                sex="F",
                race="asian",
                hispanic_origin=False,
            ),
            Person(
                person_id="p-3",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=10,
                sex="M",
                race="asian",
                is_dependent=True,
                can_be_claimed=True,
            ),
            Person(
                person_id="p-4",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=7,
                sex="F",
                race="asian",
                is_dependent=True,
                can_be_claimed=True,
            ),
        ],
    )


def _make_blended_family_household() -> Household:
    """Married couple with biological child + stepchild."""
    return Household(
        household_id="hh-blended",
        state="CA",
        year=2022,
        pattern="blended_family",
        members=[
            Person(
                person_id="p-1",
                relationship=RelationshipType.HOUSEHOLDER,
                age=42,
                sex="M",
                race="white",
            ),
            Person(
                person_id="p-2",
                relationship=RelationshipType.SPOUSE,
                age=39,
                sex="F",
                race="white",
            ),
            Person(
                person_id="p-3",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=12,
                sex="F",
                race="white",
                is_dependent=True,
            ),
            Person(
                person_id="p-4",
                relationship=RelationshipType.STEPCHILD,
                age=14,
                sex="M",
                race="white",
                is_dependent=True,
            ),
        ],
    )


def _make_hispanic_household() -> Household:
    """Single parent with Hispanic origin."""
    return Household(
        household_id="hh-hispanic",
        state="TX",
        year=2022,
        pattern="single_parent",
        members=[
            Person(
                person_id="p-1",
                relationship=RelationshipType.HOUSEHOLDER,
                age=35,
                sex="F",
                race="white",
                hispanic_origin=True,
            ),
            Person(
                person_id="p-2",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=8,
                sex="M",
                race="two_or_more",
                hispanic_origin=True,
                is_dependent=True,
            ),
        ],
    )


@pytest.fixture
def pii_gen() -> PIIGenerator:
    return PIIGenerator(tax_year=2024)


# =========================================================================
# Household address
# =========================================================================

class TestHouseholdAddress:
    """The overlay must set a shared household address."""

    def test_address_populated(self, pii_gen: PIIGenerator) -> None:
        hh = _make_single_adult_household()
        pii_gen.overlay(hh)
        assert hh.address is not None
        assert hh.address.street != ""
        assert hh.address.city != ""
        assert hh.address.state == "HI"
        assert hh.address.zip_code != ""

    def test_address_state_matches_household(self, pii_gen: PIIGenerator) -> None:
        hh = _make_hispanic_household()
        pii_gen.overlay(hh)
        assert hh.address is not None
        assert hh.address.state == "TX"


# =========================================================================
# Names
# =========================================================================

class TestNames:
    """Name generation and family-consistency rules."""

    def test_all_members_have_names(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            assert person.legal_first_name != "", f"{person.person_id} missing first name"
            assert person.legal_last_name != "", f"{person.person_id} missing last name"

    def test_biological_children_share_householder_last_name(
        self, pii_gen: PIIGenerator,
    ) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        householder = hh.get_householder()
        for person in hh.members:
            if person.relationship == RelationshipType.BIOLOGICAL_CHILD:
                assert person.legal_last_name == householder.legal_last_name

    def test_stepchild_last_name_logic(self, pii_gen: PIIGenerator) -> None:
        """Stepchildren get spouse's last name when different, else random."""
        hh = _make_blended_family_household()
        pii_gen.overlay(hh)
        householder = hh.get_householder()
        spouse = hh.get_spouse()
        stepchild = next(
            p for p in hh.members
            if p.relationship == RelationshipType.STEPCHILD
        )
        if spouse.legal_last_name != householder.legal_last_name:
            assert stepchild.legal_last_name == spouse.legal_last_name
        else:
            # Random last name — just ensure it's populated
            assert stepchild.legal_last_name != ""

    def test_middle_name_populated(self, pii_gen: PIIGenerator) -> None:
        hh = _make_single_adult_household()
        pii_gen.overlay(hh)
        assert hh.members[0].legal_middle_name != ""

    def test_full_legal_name_method(self, pii_gen: PIIGenerator) -> None:
        hh = _make_single_adult_household()
        pii_gen.overlay(hh)
        person = hh.members[0]
        full = person.full_legal_name()
        assert person.legal_first_name in full
        assert person.legal_last_name in full


# =========================================================================
# SSNs
# =========================================================================

class TestSSN:
    """SSNs must be in the 9XX-XX-XXXX test range and unique."""

    _SSN_PATTERN = re.compile(r"^9\d{2}-\d{2}-\d{4}$")

    def test_ssn_format(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            assert self._SSN_PATTERN.match(person.ssn), (
                f"{person.person_id} SSN '{person.ssn}' not in 9XX-XX-XXXX format"
            )

    def test_ssns_unique_within_household(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        ssns = [p.ssn for p in hh.members]
        assert len(ssns) == len(set(ssns)), "Duplicate SSNs in household"

    def test_ssn_test_range(self, pii_gen: PIIGenerator) -> None:
        hh = _make_single_adult_household()
        pii_gen.overlay(hh)
        area = int(hh.members[0].ssn.split("-")[0])
        assert 900 <= area <= 999


# =========================================================================
# DOBs
# =========================================================================

class TestDOB:
    """DOBs must be consistent with person age and tax year."""

    def test_dob_populated(self, pii_gen: PIIGenerator) -> None:
        hh = _make_single_adult_household()
        pii_gen.overlay(hh)
        assert hh.members[0].dob is not None

    def test_dob_consistent_with_age(self, pii_gen: PIIGenerator) -> None:
        """Age calculated from DOB should match the person's stated age
        at some point during the tax year."""
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            assert person.dob is not None
            # On Dec 31 of the tax year
            end_of_year = date(pii_gen.tax_year, 12, 31)
            age_at_eoy = (
                end_of_year.year - person.dob.year
                - (
                    (end_of_year.month, end_of_year.day)
                    < (person.dob.month, person.dob.day)
                )
            )
            # On Jan 1 of the tax year
            start_of_year = date(pii_gen.tax_year, 1, 1)
            age_at_soy = (
                start_of_year.year - person.dob.year
                - (
                    (start_of_year.month, start_of_year.day)
                    < (person.dob.month, person.dob.day)
                )
            )
            assert age_at_soy <= person.age <= age_at_eoy + 1, (
                f"{person.person_id}: age={person.age}, dob={person.dob}, "
                f"age_at_soy={age_at_soy}, age_at_eoy={age_at_eoy}"
            )


# =========================================================================
# Phone & Email
# =========================================================================

class TestPhoneEmail:
    """Phone for adults, email for householder only."""

    def test_adults_have_phone(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            if person.is_adult():
                assert person.phone != "", f"{person.person_id} missing phone"

    def test_children_no_phone(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            if person.is_child():
                assert person.phone == "", f"Child {person.person_id} has phone"

    def test_householder_has_email(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        householder = hh.get_householder()
        assert householder.email != ""
        assert "@" in householder.email

    def test_non_householder_no_email(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            if person.relationship != RelationshipType.HOUSEHOLDER:
                assert person.email == ""


# =========================================================================
# ID documents
# =========================================================================

class TestIDDocuments:
    """Adults get a photo ID (DL or state ID); children get nothing."""

    def test_adults_have_photo_id(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            if person.is_adult():
                assert person.id_type in ("drivers_license", "state_id")
                assert person.id_state == "HI"
                assert person.id_number != ""
                assert person.id_expiry is not None
                assert person.id_address is not None

    def test_children_no_id(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        for person in hh.members:
            if person.is_child():
                assert person.id_type == ""

    def test_id_state_matches_household(self, pii_gen: PIIGenerator) -> None:
        hh = _make_hispanic_household()
        pii_gen.overlay(hh)
        householder = hh.get_householder()
        assert householder.id_state == "TX"

    def test_hi_dl_format(self, pii_gen: PIIGenerator) -> None:
        """Hawaii DL format: H followed by 8 digits."""
        hh = _make_single_adult_household()
        pii_gen.overlay(hh)
        dl = hh.members[0].id_number
        assert re.match(r"^H\d{8}$", dl), f"HI DL format mismatch: {dl}"

    def test_ca_dl_format(self, pii_gen: PIIGenerator) -> None:
        """California DL format: letter followed by 7 digits."""
        hh = _make_blended_family_household()
        pii_gen.overlay(hh)
        householder = hh.get_householder()
        dl = householder.id_number
        assert re.match(r"^[A-Z]\d{7}$", dl), f"CA DL format mismatch: {dl}"


# =========================================================================
# Integration: full overlay
# =========================================================================

class TestFullOverlay:
    """End-to-end overlay on various household patterns."""

    def test_overlay_returns_same_household(self, pii_gen: PIIGenerator) -> None:
        hh = _make_married_couple_household()
        result = pii_gen.overlay(hh)
        assert result is hh

    def test_overlay_idempotent_member_count(self, pii_gen: PIIGenerator) -> None:
        """Overlay should not add or remove members."""
        hh = _make_married_couple_household()
        original_count = len(hh.members)
        pii_gen.overlay(hh)
        assert len(hh.members) == original_count

    def test_overlay_all_patterns(self, pii_gen: PIIGenerator) -> None:
        """Smoke test: overlay works on all fixture patterns without error."""
        factories = [
            _make_single_adult_household,
            _make_married_couple_household,
            _make_blended_family_household,
            _make_hispanic_household,
        ]
        for factory in factories:
            hh = factory()
            pii_gen.overlay(hh)
            for person in hh.members:
                assert person.legal_first_name != ""
                assert person.legal_last_name != ""
                assert person.ssn != ""
                assert person.dob is not None

    def test_to_dict_after_overlay(self, pii_gen: PIIGenerator) -> None:
        """Household.to_dict() should work cleanly after PII overlay."""
        hh = _make_married_couple_household()
        pii_gen.overlay(hh)
        d = hh.to_dict()
        assert d["address"] is not None
        assert d["address"]["state"] == "HI"
        assert len(d["members"]) == 4
        for m in d["members"]:
            assert m["legal_first_name"] != ""
            assert m["ssn"] != ""
