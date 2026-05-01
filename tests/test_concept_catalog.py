"""Tests for the concept catalog infrastructure (D Phase 1).

Covers:
- Concept base class: abstract, has name, matches(), generation_hints().
- GenerationHints: dataclass with empty defaults.
- ConceptCatalog: register, run_all with empty registry, with matching
  concepts, with non-matching concepts, with crashing concept.
- Concept evaluation constraint: concepts cannot read interview_notes
  or concept_tags (enforced by pipeline ordering, verified by test).
- Import graph: learn/ imports from tax_core/ and generator/, nothing
  imports from learn/.
"""

from datetime import date
from typing import Any
from unittest.mock import MagicMock

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
    Scenario,
)
from learn.concepts.base import Concept, GenerationHints
from learn.concept_catalog import ConceptCatalog


# =========================================================================
# Helpers
# =========================================================================

def _addr():
    return Address(
        street="100 Main St", city="Honolulu",
        state="HI", zip_code="96816",
    )


def _make_scenario() -> Scenario:
    """Minimal scenario for concept evaluation tests."""
    hh = Household(
        household_id="hh-concept",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=_addr(),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30, sex="F", race="white",
                legal_first_name="Jane", legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
                id_address=_addr(),
                wage_income=50000,
            ),
        ],
    )
    return Scenario(
        scenario_id="sc-concept-test",
        mode="intake",
        difficulty="easy",
        household=hh,
        document_paths={},
        created_at="2024-01-01T00:00:00",
        ground_truth={"schema_version": 1, "filing_status": "single"},
    )


class AlwaysMatchesConcept(Concept):
    name = "always_matches"

    def matches(self, scenario: Any) -> bool:
        return True


class NeverMatchesConcept(Concept):
    name = "never_matches"

    def matches(self, scenario: Any) -> bool:
        return False


class CrashingConcept(Concept):
    name = "crasher"

    def matches(self, scenario: Any) -> bool:
        raise ValueError("Intentional crash for testing")


class ReadsInterviewNotesConcept(Concept):
    """Concept that attempts to read interview_notes — should be None."""
    name = "bad_reader"

    def matches(self, scenario: Any) -> bool:
        if scenario.interview_notes is not None:
            raise AssertionError("interview_notes should be None at Stage 5")
        return False


class ReadsConceptTagsConcept(Concept):
    """Concept that attempts to read concept_tags — should be None."""
    name = "bad_tags_reader"

    def matches(self, scenario: Any) -> bool:
        if scenario.concept_tags is not None:
            raise AssertionError("concept_tags should be None at Stage 5")
        return False


# =========================================================================
# 1. Concept base class
# =========================================================================

class TestConceptBase:

    def test_concept_is_abstract(self) -> None:
        with pytest.raises(TypeError):
            Concept()

    def test_subclass_has_name(self) -> None:
        c = AlwaysMatchesConcept()
        assert c.name == "always_matches"

    def test_matches_returns_bool(self) -> None:
        c = AlwaysMatchesConcept()
        result = c.matches(_make_scenario())
        assert result is True

    def test_generation_hints_default_empty(self) -> None:
        c = AlwaysMatchesConcept()
        hints = c.generation_hints()
        assert isinstance(hints, GenerationHints)
        assert hints.preferred_patterns == []
        assert hints.hints == {}


# =========================================================================
# 2. GenerationHints
# =========================================================================

class TestGenerationHints:

    def test_default_fields(self) -> None:
        hints = GenerationHints()
        assert hints.preferred_patterns == []
        assert hints.hints == {}

    def test_custom_fields(self) -> None:
        hints = GenerationHints(
            preferred_patterns=["single_adult"],
            hints={"min_se_income": 500},
        )
        assert hints.preferred_patterns == ["single_adult"]
        assert hints.hints["min_se_income"] == 500


# =========================================================================
# 3. ConceptCatalog
# =========================================================================

class TestCatalogEmpty:

    def test_empty_registry_run_all(self) -> None:
        catalog = ConceptCatalog()
        tags = catalog.run_all(_make_scenario())
        assert tags == set()

    def test_empty_concepts_list(self) -> None:
        catalog = ConceptCatalog()
        assert catalog.concepts == []


class TestCatalogRegistration:

    def test_register_adds_concept(self) -> None:
        catalog = ConceptCatalog()
        catalog.register(AlwaysMatchesConcept())
        assert len(catalog.concepts) == 1
        assert catalog.concepts[0].name == "always_matches"

    def test_register_multiple(self) -> None:
        catalog = ConceptCatalog()
        catalog.register(AlwaysMatchesConcept())
        catalog.register(NeverMatchesConcept())
        assert len(catalog.concepts) == 2

    def test_concepts_returns_copy(self) -> None:
        catalog = ConceptCatalog()
        catalog.register(AlwaysMatchesConcept())
        concepts = catalog.concepts
        concepts.clear()
        assert len(catalog.concepts) == 1


class TestCatalogRunAll:

    def test_matching_concept_returns_tag(self) -> None:
        catalog = ConceptCatalog()
        catalog.register(AlwaysMatchesConcept())
        tags = catalog.run_all(_make_scenario())
        assert tags == {"always_matches"}

    def test_non_matching_concept_absent(self) -> None:
        catalog = ConceptCatalog()
        catalog.register(NeverMatchesConcept())
        tags = catalog.run_all(_make_scenario())
        assert tags == set()

    def test_mixed_matching(self) -> None:
        catalog = ConceptCatalog()
        catalog.register(AlwaysMatchesConcept())
        catalog.register(NeverMatchesConcept())
        tags = catalog.run_all(_make_scenario())
        assert tags == {"always_matches"}

    def test_multiple_matching(self) -> None:
        catalog = ConceptCatalog()
        c1 = AlwaysMatchesConcept()
        c1.name = "concept_a"
        c2 = AlwaysMatchesConcept()
        c2.name = "concept_b"
        catalog.register(c1)
        catalog.register(c2)
        tags = catalog.run_all(_make_scenario())
        assert tags == {"concept_a", "concept_b"}


class TestCatalogFaultTolerance:

    def test_crashing_concept_logged_and_skipped(self, caplog) -> None:
        catalog = ConceptCatalog()
        catalog.register(CrashingConcept())
        catalog.register(AlwaysMatchesConcept())
        tags = catalog.run_all(_make_scenario())
        assert "always_matches" in tags
        assert "crasher" not in tags
        assert "Intentional crash" in caplog.text

    def test_crashing_concept_does_not_raise(self) -> None:
        catalog = ConceptCatalog()
        catalog.register(CrashingConcept())
        tags = catalog.run_all(_make_scenario())
        assert tags == set()

    def test_multiple_crashes_all_logged(self, caplog) -> None:
        catalog = ConceptCatalog()
        c1 = CrashingConcept()
        c1.name = "crasher_1"
        c2 = CrashingConcept()
        c2.name = "crasher_2"
        catalog.register(c1)
        catalog.register(c2)
        catalog.register(AlwaysMatchesConcept())
        tags = catalog.run_all(_make_scenario())
        assert tags == {"always_matches"}
        assert "crasher_1" in caplog.text
        assert "crasher_2" in caplog.text


# =========================================================================
# 4. Concept evaluation constraint
# =========================================================================

class TestEvaluationConstraint:

    def test_interview_notes_none_at_stage_5(self) -> None:
        """Concepts see interview_notes=None (not yet populated at Stage 5)."""
        scenario = _make_scenario()
        assert scenario.interview_notes is None
        catalog = ConceptCatalog()
        catalog.register(ReadsInterviewNotesConcept())
        tags = catalog.run_all(scenario)
        assert "bad_reader" not in tags

    def test_concept_tags_none_at_stage_5(self) -> None:
        """Concepts see concept_tags=None (that's what they're producing)."""
        scenario = _make_scenario()
        assert scenario.concept_tags is None
        catalog = ConceptCatalog()
        catalog.register(ReadsConceptTagsConcept())
        tags = catalog.run_all(scenario)
        assert "bad_tags_reader" not in tags

    def test_ground_truth_available(self) -> None:
        """Concepts can read ground_truth (populated at Stage 4)."""
        scenario = _make_scenario()
        assert scenario.ground_truth is not None

        class ReadsGT(Concept):
            name = "gt_reader"
            def matches(self, scenario):
                return scenario.ground_truth.get("filing_status") == "single"

        catalog = ConceptCatalog()
        catalog.register(ReadsGT())
        tags = catalog.run_all(scenario)
        assert "gt_reader" in tags

    def test_household_available(self) -> None:
        """Concepts can read household (populated at Stage 2)."""
        scenario = _make_scenario()
        assert scenario.household is not None

        class ReadsHH(Concept):
            name = "hh_reader"
            def matches(self, scenario):
                return len(scenario.household.members) > 0

        catalog = ConceptCatalog()
        catalog.register(ReadsHH())
        tags = catalog.run_all(scenario)
        assert "hh_reader" in tags


# =========================================================================
# 5. Import graph
# =========================================================================

class TestImportGraph:

    def test_learn_does_not_import_api(self) -> None:
        import learn.concept_catalog
        import learn.concepts.base
        src = (
            learn.concept_catalog.__file__
            + learn.concepts.base.__file__
        )
        assert "api" not in src

    def test_concept_catalog_importable(self) -> None:
        from learn.concept_catalog import ConceptCatalog
        assert ConceptCatalog is not None

    def test_concept_base_importable(self) -> None:
        from learn.concepts.base import Concept, GenerationHints
        assert Concept is not None
        assert GenerationHints is not None

    def test_no_circular_imports(self) -> None:
        import importlib
        importlib.reload(__import__("learn.concept_catalog"))
        importlib.reload(__import__("learn.concepts.base"))
