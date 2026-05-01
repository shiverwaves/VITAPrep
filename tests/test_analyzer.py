"""Tests for the scenario analyzer — Restructure C1 Phase 1.

Validates:
- Types are importable and constructable.
- ScenarioAnalyzer with no slots returns empty dict (no-op).
- ScenarioAnalyzer fires slots and selects templates correctly.
- Unrescuable raised when a fired instance has no matching template.
- Slot evaluation constraint: slots cannot read lifecycle fields.
- Import graph: intake/analyzer/ imports only from generator/ models.
- Pipeline integration: exercise engine works with the no-op analyzer.
"""

import ast
from datetime import date
from pathlib import Path
from typing import Any, List
from unittest.mock import MagicMock, patch

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
    Scenario,
)
from intake.analyzer.types import (
    FiredTemplate,
    InterviewNote,
    NarrativeTemplate,
    Slot,
    Unrescuable,
)
from intake.analyzer.analyzer import MAX_REROLL_ATTEMPTS, ScenarioAnalyzer


# =========================================================================
# Test helpers
# =========================================================================

def _make_scenario() -> Scenario:
    """Minimal scenario with one householder."""
    hh = Household(
        household_id="hh-test",
        state="HI",
        year=2022,
        pattern="single_adult",
        address=Address(
            street="100 Main St", city="Honolulu",
            state="HI", zip_code="96816",
        ),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=30,
                sex="F",
                legal_first_name="Jane",
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1992, 5, 15),
            ),
        ],
    )
    return Scenario(
        scenario_id="sc-test",
        mode="intake",
        difficulty="easy",
        household=hh,
    )


class AlwaysFiresSlot(Slot):
    """Test slot that fires for every household member."""
    name = "always_fires"

    def fires_for(self, scenario: Any) -> list:
        return list(scenario.household.members)

    def templates(self) -> List[NarrativeTemplate]:
        return [AlwaysMatchesTemplate()]


class NeverFiresSlot(Slot):
    """Test slot that never fires."""
    name = "never_fires"

    def fires_for(self, scenario: Any) -> list:
        return []

    def templates(self) -> List[NarrativeTemplate]:
        return []


class NoTemplateMatchSlot(Slot):
    """Test slot that fires but has no matching templates."""
    name = "no_template_match"

    def fires_for(self, scenario: Any) -> list:
        return list(scenario.household.members)

    def templates(self) -> List[NarrativeTemplate]:
        return [NeverMatchesTemplate()]


class AlwaysMatchesTemplate(NarrativeTemplate):
    def requirements(self, scenario: Any, instance: Any) -> bool:
        return True

    def render(
        self, scenario: Any, instance: Any, subtlety: str,
    ) -> InterviewNote:
        return InterviewNote(
            category="test",
            question="Test question?",
            answer="Test answer.",
            source_slot="always_fires",
        )


class NeverMatchesTemplate(NarrativeTemplate):
    def requirements(self, scenario: Any, instance: Any) -> bool:
        return False

    def render(
        self, scenario: Any, instance: Any, subtlety: str,
    ) -> InterviewNote:
        raise AssertionError("Should not be called")


class SelectiveTemplate(NarrativeTemplate):
    """Only matches persons under age 18."""
    def requirements(self, scenario: Any, instance: Any) -> bool:
        return hasattr(instance, "age") and instance.age < 18

    def render(
        self, scenario: Any, instance: Any, subtlety: str,
    ) -> InterviewNote:
        return InterviewNote(
            category="dependent",
            question=f"About {instance.legal_first_name}?",
            answer="They're a minor.",
            source_slot="selective",
        )


# =========================================================================
# 1. Types are importable and constructable
# =========================================================================

class TestTypes:

    def test_interview_note_fields(self) -> None:
        note = InterviewNote(
            category="filing",
            question="What is your filing status?",
            answer="Single",
            source_slot="test_slot",
        )
        assert note.category == "filing"
        assert note.source_slot == "test_slot"

    def test_interview_note_source_slot_defaults_none(self) -> None:
        note = InterviewNote(category="c", question="q", answer="a")
        assert note.source_slot is None

    def test_fired_template_fields(self) -> None:
        template = AlwaysMatchesTemplate()
        ft = FiredTemplate(
            slot_name="test", instance="person_obj", template=template,
        )
        assert ft.slot_name == "test"
        assert ft.template is template

    def test_unrescuable_is_exception(self) -> None:
        with pytest.raises(Unrescuable):
            raise Unrescuable("test")


# =========================================================================
# 2. ScenarioAnalyzer — no-op stub
# =========================================================================

class TestAnalyzerNoOp:

    def test_no_slots_returns_empty(self) -> None:
        analyzer = ScenarioAnalyzer()
        result = analyzer.analyze(_make_scenario())
        assert result == {}

    def test_never_fires_slot_returns_empty(self) -> None:
        analyzer = ScenarioAnalyzer()
        analyzer.register(NeverFiresSlot())
        result = analyzer.analyze(_make_scenario())
        assert result == {}


# =========================================================================
# 3. ScenarioAnalyzer — slot firing and template selection
# =========================================================================

class TestAnalyzerFiring:

    def test_always_fires_slot(self) -> None:
        analyzer = ScenarioAnalyzer()
        analyzer.register(AlwaysFiresSlot())
        result = analyzer.analyze(_make_scenario())
        assert "always_fires" in result
        assert len(result["always_fires"]) == 1

    def test_fired_template_structure(self) -> None:
        analyzer = ScenarioAnalyzer()
        analyzer.register(AlwaysFiresSlot())
        result = analyzer.analyze(_make_scenario())
        ft = result["always_fires"][0]
        assert isinstance(ft, FiredTemplate)
        assert ft.slot_name == "always_fires"
        assert isinstance(ft.template, AlwaysMatchesTemplate)

    def test_multiple_slots(self) -> None:
        analyzer = ScenarioAnalyzer()
        analyzer.register(AlwaysFiresSlot())
        analyzer.register(NeverFiresSlot())
        result = analyzer.analyze(_make_scenario())
        assert "always_fires" in result
        assert "never_fires" not in result

    def test_unrescuable_on_no_match(self) -> None:
        analyzer = ScenarioAnalyzer()
        analyzer.register(NoTemplateMatchSlot())
        with pytest.raises(Unrescuable, match="no template matched"):
            analyzer.analyze(_make_scenario())

    def test_template_priority_order(self) -> None:
        """First matching template wins."""
        class PrioritySlot(Slot):
            name = "priority"
            def fires_for(self, scenario):
                return list(scenario.household.members)
            def templates(self):
                return [NeverMatchesTemplate(), AlwaysMatchesTemplate()]

        analyzer = ScenarioAnalyzer()
        analyzer.register(PrioritySlot())
        result = analyzer.analyze(_make_scenario())
        assert isinstance(result["priority"][0].template, AlwaysMatchesTemplate)

    def test_selective_template_with_child(self) -> None:
        """Template that only matches children fires for children."""
        class ChildSlot(Slot):
            name = "child_slot"
            def fires_for(self, scenario):
                return [p for p in scenario.household.members if p.age < 18]
            def templates(self):
                return [SelectiveTemplate()]

        hh = Household(
            household_id="hh-t2", state="HI", year=2022,
            pattern="single_parent",
            address=Address(
                street="1 St", city="Honolulu",
                state="HI", zip_code="96816",
            ),
            members=[
                Person(
                    person_id="p-a", age=35, sex="F",
                    relationship=RelationshipType.HOUSEHOLDER,
                    legal_first_name="Mom", legal_last_name="Test",
                    ssn="900-11-1111", dob=date(1987, 1, 1),
                ),
                Person(
                    person_id="p-c", age=8, sex="M",
                    relationship=RelationshipType.BIOLOGICAL_CHILD,
                    legal_first_name="Kid", legal_last_name="Test",
                    ssn="900-22-2222", dob=date(2014, 6, 1),
                    is_dependent=True, months_in_home=12,
                ),
            ],
        )
        scenario = Scenario(
            scenario_id="sc-t2", mode="intake", difficulty="easy",
            household=hh,
        )
        analyzer = ScenarioAnalyzer()
        analyzer.register(ChildSlot())
        result = analyzer.analyze(scenario)
        assert len(result["child_slot"]) == 1
        assert result["child_slot"][0].instance.person_id == "p-c"


# =========================================================================
# 4. Slot evaluation constraint
# =========================================================================

class TestSlotEvaluationConstraint:

    def test_lifecycle_fields_are_none_during_analysis(self) -> None:
        """Slots receive a scenario with lifecycle fields as None."""
        seen_scenario = {}

        class InspectorSlot(Slot):
            name = "inspector"
            def fires_for(self, scenario):
                seen_scenario["ground_truth"] = scenario.ground_truth
                seen_scenario["concept_tags"] = scenario.concept_tags
                seen_scenario["interview_notes"] = scenario.interview_notes
                return []
            def templates(self):
                return []

        scenario = _make_scenario()
        analyzer = ScenarioAnalyzer()
        analyzer.register(InspectorSlot())
        analyzer.analyze(scenario)

        assert seen_scenario["ground_truth"] is None
        assert seen_scenario["concept_tags"] is None
        assert seen_scenario["interview_notes"] is None


# =========================================================================
# 5. Import graph: intake/analyzer/ must not import tax_core or training
# =========================================================================

ANALYZER_ROOT = Path(__file__).resolve().parent.parent / "intake" / "analyzer"
FORBIDDEN_FOR_ANALYZER = ("tax_core", "training", "api", "learn")


def _collect_imports(filepath: Path) -> list[tuple[str, int]]:
    source = filepath.read_text()
    tree = ast.parse(source, filename=str(filepath))
    imports = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, node.lineno))
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.append((node.module, node.lineno))
    return imports


def test_analyzer_does_not_import_forbidden_layers():
    """intake/analyzer/ must not import from tax_core, training, api, or learn."""
    if not ANALYZER_ROOT.exists():
        return

    violations = []
    for pyfile in ANALYZER_ROOT.rglob("*.py"):
        for module_name, lineno in _collect_imports(pyfile):
            top_level = module_name.split(".")[0]
            if top_level in FORBIDDEN_FOR_ANALYZER:
                rel = pyfile.relative_to(ANALYZER_ROOT.parent.parent)
                violations.append(f"  {rel}:{lineno} imports '{module_name}'")

    assert not violations, (
        "intake/analyzer/ must not import from upper layers:\n"
        + "\n".join(violations)
    )


# =========================================================================
# 6. Pipeline integration — engine works with no-op analyzer
# =========================================================================

class TestPipelineIntegration:

    @pytest.fixture
    def engine(self):
        from training.exercise_engine import ExerciseEngine
        with patch("training.exercise_engine.HouseholdGenerator") as MockGen:
            mock_gen = MockGen.return_value
            mock_gen.generate_with_pii.return_value = Household(
                household_id="hh-pipe",
                state="HI",
                year=2022,
                pattern="single_adult",
                address=Address(
                    street="1 St", city="Honolulu",
                    state="HI", zip_code="96816",
                ),
                members=[
                    Person(
                        person_id="p-pipe",
                        relationship=RelationshipType.HOUSEHOLDER,
                        age=30, sex="F",
                        legal_first_name="Pipe", legal_last_name="Test",
                        ssn="900-99-8888", dob=date(1992, 1, 1),
                        phone="(808) 555-0000",
                        email="pipe@test.com",
                        id_type="drivers_license",
                        id_state="HI",
                        id_number="H9999999",
                        id_expiry=date(2028, 1, 1),
                        id_address=Address(
                            street="1 St", city="Honolulu",
                            state="HI", zip_code="96816",
                        ),
                    ),
                ],
            )
            mock_gen.year = 2022

            eng = ExerciseEngine.__new__(ExerciseEngine)
            eng.generator = mock_gen
            eng.error_injector = MagicMock()
            eng.error_injector.inject.side_effect = (
                lambda hh, **kw: (hh, [])
            )
            eng.analyzer = ScenarioAnalyzer()

            from learn.concept_catalog import ConceptCatalog
            from learn.concepts.deductions import StandardVsItemizedConcept
            from learn.concepts.dependency import QualifyingChildResidencyConcept
            from learn.concepts.filing_status import (
                HoHQualifyingPersonConcept,
                RefundableCreditOnlyFilerConcept,
            )
            from learn.concepts.income import (
                SelfEmploymentThresholdConcept,
                SocialSecurityTaxabilityConcept,
            )
            eng.concept_catalog = ConceptCatalog()
            eng.concept_catalog.register(QualifyingChildResidencyConcept())
            eng.concept_catalog.register(HoHQualifyingPersonConcept())
            eng.concept_catalog.register(RefundableCreditOnlyFilerConcept())
            eng.concept_catalog.register(SelfEmploymentThresholdConcept())
            eng.concept_catalog.register(SocialSecurityTaxabilityConcept())
            eng.concept_catalog.register(StandardVsItemizedConcept())

            yield eng

    def test_scenario_generated_with_ground_truth(self, engine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.ground_truth is not None
        assert result.ground_truth["schema_version"] == 1

    def test_narrative_slots_none_when_no_slots(self, engine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.narrative_slots is None

    def test_interview_notes_populated(self, engine) -> None:
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result.interview_notes is not None
        assert len(result.interview_notes) > 0

    def test_retry_on_unrescuable(self, engine) -> None:
        call_count = {"n": 0}
        original_analyze = engine.analyzer.analyze

        def flaky_analyze(scenario):
            call_count["n"] += 1
            if call_count["n"] < 3:
                raise Unrescuable("test reroll")
            return original_analyze(scenario)

        engine.analyzer.analyze = flaky_analyze
        result = engine.generate_scenario(mode="intake", difficulty="easy")
        assert result is not None
        assert call_count["n"] == 3

    def test_max_retries_exceeded_raises(self, engine) -> None:
        engine.analyzer.analyze = MagicMock(
            side_effect=Unrescuable("always fails"),
        )
        with pytest.raises(Unrescuable, match="Failed to generate"):
            engine.generate_scenario(mode="intake", difficulty="easy")
        assert engine.analyzer.analyze.call_count == MAX_REROLL_ATTEMPTS
