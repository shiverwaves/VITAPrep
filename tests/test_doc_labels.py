"""Tests for the document tab-label builder (Phase 2A).

Covers the four cases from the integration plan:

    Person-owned, single of its type     → "Maria's W-2"
    Person-owned, multiple of same type  → "Maria's W-2 (1 of 2)"
    Household-owned, with issuer         → "1098 — Bank of Hawaii"  (deferred)
    Household-owned, no issuer           → "1098"                   (deferred)

The two household-owned cases aren't reachable today because every
document on the data model lives on Person, not Household. They're kept
in the rule for forward compatibility but no test asserts them yet.
"""

from datetime import date

import pytest

from generator.models import (
    Address,
    Employer,
    Form1098,
    Form1098E,
    Form1098T,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    Household,
    Person,
    RelationshipType,
    SSA1099,
    W2,
)

from api.routes.scenarios import _build_doc_labels


def _w2(employer_name: str, wages: int) -> W2:
    return W2(
        employer=Employer(name=employer_name, ein="12-3456789"),
        wages=wages,
    )


def _person(
    person_id: str,
    first: str,
    last: str = "Smith",
    *,
    ssn: str = "",
    id_type: str = "",
    has_ssa_1099: bool = False,
    w2s=None,
    int_count: int = 0,
    div_count: int = 0,
    r_count: int = 0,
    nec_count: int = 0,
    f1098_count: int = 0,
    f1098e_count: int = 0,
    f1098t_count: int = 0,
) -> Person:
    return Person(
        person_id=person_id,
        relationship=RelationshipType.HOUSEHOLDER,
        legal_first_name=first,
        legal_last_name=last,
        ssn=ssn,
        id_type=id_type,
        ssa_1099=SSA1099(total_benefits=18000, net_benefits=18000)
            if has_ssa_1099 else None,
        w2s=list(w2s or []),
        form_1099_ints=[Form1099INT(payer_name="Bank", interest_income=100)
                        for _ in range(int_count)],
        form_1099_divs=[Form1099DIV(payer_name="Brokerage",
                                    ordinary_dividends=200)
                        for _ in range(div_count)],
        form_1099_rs=[Form1099R(payer_name="Pension",
                                gross_distribution=12000,
                                taxable_amount=12000,
                                distribution_code="7")
                      for _ in range(r_count)],
        form_1099_necs=[Form1099NEC(payer_name="Client",
                                    nonemployee_compensation=5000)
                        for _ in range(nec_count)],
        form_1098s=[Form1098(lender_name="Bank",
                             mortgage_interest=8000)
                    for _ in range(f1098_count)],
        form_1098_es=[Form1098E(lender_name="Loan Servicer",
                                student_loan_interest=500)
                      for _ in range(f1098e_count)],
        form_1098_ts=[Form1098T(institution_name="University",
                                amounts_billed=8000)
                      for _ in range(f1098t_count)],
    )


def _hh(*members: Person) -> Household:
    return Household(
        household_id="hh-test",
        state="HI",
        year=2022,
        pattern="single_adult",
        members=list(members),
        address=Address(street="1 Main", city="Honolulu",
                        state="HI", zip_code="96815"),
    )


# =========================================================================
# Empty / edge inputs
# =========================================================================


class TestEdgeCases:

    def test_none_household_returns_empty(self) -> None:
        assert _build_doc_labels(None) == {}

    def test_empty_household_returns_empty(self) -> None:
        hh = Household(household_id="hh", state="HI", year=2022,
                       pattern="x", members=[])
        assert _build_doc_labels(hh) == {}

    def test_person_with_no_docs_emits_nothing(self) -> None:
        p = _person("p-1", "Daniel")
        labels = _build_doc_labels(_hh(p))
        assert labels == {}

    def test_missing_first_name_falls_back(self) -> None:
        """Tab labels need *something* readable even without a first name."""
        p = _person("p-1", "", ssn="900-12-3456")
        labels = _build_doc_labels(_hh(p))
        assert labels["ssn_p-1"] == "Unknown's SSN Card"


# =========================================================================
# Single-instance per-person docs
# =========================================================================


class TestSinglePerPerson:

    def test_ssn_card_label(self) -> None:
        p = _person("p-1", "Maria", ssn="900-12-3456")
        labels = _build_doc_labels(_hh(p))
        assert labels["ssn_p-1"] == "Maria's SSN Card"

    def test_drivers_license_label(self) -> None:
        p = _person("p-1", "Daniel", id_type="drivers_license")
        labels = _build_doc_labels(_hh(p))
        assert labels["id_p-1"] == "Daniel's Driver's License"

    def test_state_id_label(self) -> None:
        p = _person("p-1", "Sofia", id_type="state_id")
        labels = _build_doc_labels(_hh(p))
        assert labels["id_p-1"] == "Sofia's State ID"

    def test_unknown_id_type_falls_back(self) -> None:
        p = _person("p-1", "Sam", id_type="passport")
        labels = _build_doc_labels(_hh(p))
        assert labels["id_p-1"] == "Sam's ID"

    def test_ssa_1099_label(self) -> None:
        p = _person("p-1", "Bob", has_ssa_1099=True)
        labels = _build_doc_labels(_hh(p))
        assert labels["ssa1099_p-1"] == "Bob's SSA-1099"


# =========================================================================
# Multi-instance docs — single occurrence (no disambiguator)
# =========================================================================


class TestSingleInstanceOfMultiType:
    """One W-2 / 1099-X / 1098-X gets `{Person}'s {Type}` with no
    `(1 of 1)` disambiguator."""

    def test_one_w2_no_disambiguator(self) -> None:
        p = _person("p-1", "Maria", w2s=[_w2("Acme Corp", 50000)])
        labels = _build_doc_labels(_hh(p))
        assert labels["w2_p-1_0"] == "Maria's W-2"
        # No "(1 of 1)" appended.
        assert "(1 of" not in labels["w2_p-1_0"]

    def test_one_1099_int(self) -> None:
        p = _person("p-1", "Bob", int_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["1099int_p-1_0"] == "Bob's 1099-INT"

    def test_one_1099_div(self) -> None:
        p = _person("p-1", "Bob", div_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["1099div_p-1_0"] == "Bob's 1099-DIV"

    def test_one_1099_r(self) -> None:
        p = _person("p-1", "Bob", r_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["1099r_p-1_0"] == "Bob's 1099-R"

    def test_one_1099_nec(self) -> None:
        p = _person("p-1", "Bob", nec_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["1099nec_p-1_0"] == "Bob's 1099-NEC"

    def test_one_1098(self) -> None:
        p = _person("p-1", "Daniel", f1098_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["1098_p-1_0"] == "Daniel's 1098"

    def test_one_1098e(self) -> None:
        p = _person("p-1", "Sam", f1098e_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["1098e_p-1_0"] == "Sam's 1098-E"

    def test_one_1098t(self) -> None:
        p = _person("p-1", "Emma", f1098t_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["1098t_p-1_0"] == "Emma's 1098-T"


# =========================================================================
# Multi-instance docs — duplicates trigger "(n of total)"
# =========================================================================


class TestMultipleOfSameType:

    def test_two_w2s_get_disambiguator(self) -> None:
        p = _person(
            "p-1", "Maria",
            w2s=[_w2("Acme Corp", 30000), _w2("Beta Inc", 20000)],
        )
        labels = _build_doc_labels(_hh(p))
        assert labels["w2_p-1_0"] == "Maria's W-2 (1 of 2)"
        assert labels["w2_p-1_1"] == "Maria's W-2 (2 of 2)"

    def test_three_w2s(self) -> None:
        p = _person(
            "p-1", "John",
            w2s=[
                _w2("Co A", 10000),
                _w2("Co B", 15000),
                _w2("Co C", 20000),
            ],
        )
        labels = _build_doc_labels(_hh(p))
        assert labels["w2_p-1_0"] == "John's W-2 (1 of 3)"
        assert labels["w2_p-1_1"] == "John's W-2 (2 of 3)"
        assert labels["w2_p-1_2"] == "John's W-2 (3 of 3)"

    def test_two_1099_ints_get_disambiguator(self) -> None:
        p = _person("p-1", "Bob", int_count=2)
        labels = _build_doc_labels(_hh(p))
        assert labels["1099int_p-1_0"] == "Bob's 1099-INT (1 of 2)"
        assert labels["1099int_p-1_1"] == "Bob's 1099-INT (2 of 2)"


# =========================================================================
# Mixed types per person — disambiguator scoped to (person, type)
# =========================================================================


class TestDisambiguatorScope:
    """Maria with one W-2 and one 1099-INT should get bare labels for
    both — disambiguation only kicks in when the *same person* has
    multiple of the *same type*."""

    def test_one_each_no_disambiguator(self) -> None:
        p = _person("p-1", "Maria",
                    w2s=[_w2("Acme", 30000)],
                    int_count=1)
        labels = _build_doc_labels(_hh(p))
        assert labels["w2_p-1_0"] == "Maria's W-2"
        assert labels["1099int_p-1_0"] == "Maria's 1099-INT"

    def test_two_w2s_one_int(self) -> None:
        p = _person(
            "p-1", "Maria",
            w2s=[_w2("Acme", 30000), _w2("Beta", 20000)],
            int_count=1,
        )
        labels = _build_doc_labels(_hh(p))
        assert labels["w2_p-1_0"] == "Maria's W-2 (1 of 2)"
        assert labels["w2_p-1_1"] == "Maria's W-2 (2 of 2)"
        assert labels["1099int_p-1_0"] == "Maria's 1099-INT"


# =========================================================================
# Multi-person — same first name does not collide; doc_ids stay distinct
# =========================================================================


class TestMultiplePeople:

    def test_two_people_each_with_one_w2(self) -> None:
        john = _person("p-1", "John",
                       w2s=[_w2("Acme", 30000)])
        mary = _person("p-2", "Mary",
                       w2s=[_w2("Beta", 25000)])
        labels = _build_doc_labels(_hh(john, mary))
        assert labels["w2_p-1_0"] == "John's W-2"
        assert labels["w2_p-2_0"] == "Mary's W-2"

    def test_disambiguator_scoped_per_person(self) -> None:
        """John has two W-2s, Mary has one — each has its own bucket."""
        john = _person(
            "p-1", "John",
            w2s=[_w2("Co A", 30000), _w2("Co B", 15000)],
        )
        mary = _person("p-2", "Mary",
                       w2s=[_w2("Co C", 25000)])
        labels = _build_doc_labels(_hh(john, mary))
        assert labels["w2_p-1_0"] == "John's W-2 (1 of 2)"
        assert labels["w2_p-1_1"] == "John's W-2 (2 of 2)"
        # Mary's single W-2 has no disambiguator.
        assert labels["w2_p-2_0"] == "Mary's W-2"


# =========================================================================
# Coverage: doc_labels keys match the doc_urls keys built by page_exercise
# =========================================================================


class TestKeysMatchDocUrls:
    """A scenario rendered through page_exercise has both doc_urls and
    doc_labels — they must be keyed identically so the renderer can
    look up labels by the same id it uses for URLs."""

    def test_keys_align_for_typical_household(self) -> None:
        # Mirrors the doc_urls construction in page_exercise.
        p = _person(
            "p-1", "Maria",
            ssn="900-12-3456", id_type="drivers_license",
            has_ssa_1099=True,
            w2s=[_w2("Acme", 30000)],
            int_count=2, div_count=1, r_count=1, nec_count=1,
            f1098_count=1, f1098e_count=1, f1098t_count=1,
        )
        hh = _hh(p)

        # Reproduce the doc_urls key construction inline.
        expected_keys = {
            "ssn_p-1",
            "id_p-1",
            "ssa1099_p-1",
            "w2_p-1_0",
            "1099int_p-1_0", "1099int_p-1_1",
            "1099div_p-1_0",
            "1099r_p-1_0",
            "1099nec_p-1_0",
            "1098_p-1_0",
            "1098e_p-1_0",
            "1098t_p-1_0",
        }
        labels = _build_doc_labels(hh)
        assert set(labels) == expected_keys
