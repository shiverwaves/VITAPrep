"""Tests for the scenario store — Sprint 6 Step 4.

Validates:
- Table creation on init
- Scenario save / get round-trips (including nested Household, errors, facts)
- List with filtering by mode and difficulty
- Delete cascades grades
- Grade save / get
- Progress history and summary stats
- Edge cases: empty DB, missing scenario, duplicate IDs
"""

import os
import sqlite3
import tempfile
from datetime import date
from pathlib import Path

import pytest

from generator.models import (
    Address,
    ClientFact,
    GradingResult,
    Household,
    InjectedError,
    Person,
    RelationshipType,
    Scenario,
)
from training.scenario_store import ScenarioStore


# =========================================================================
# Fixtures
# =========================================================================

@pytest.fixture
def store(tmp_path: Path) -> ScenarioStore:
    """Fresh in-memory-ish store in a temp directory."""
    db = str(tmp_path / "test_scenarios.sqlite")
    s = ScenarioStore(db_path=db)
    yield s
    s.close()


@pytest.fixture
def sample_household() -> Household:
    return Household(
        household_id="hh-001",
        state="HI",
        year=2022,
        pattern="married_couple_with_children",
        address=Address(
            street="100 Main St", apt="Apt 3",
            city="Honolulu", state="HI", zip_code="96816",
        ),
        members=[
            Person(
                person_id="p-01",
                relationship=RelationshipType.HOUSEHOLDER,
                age=40,
                sex="M",
                race="white",
                legal_first_name="John",
                legal_last_name="Smith",
                ssn="900-11-1111",
                dob=date(1982, 3, 10),
                phone="(808) 555-1234",
                email="john@example.com",
                id_type="drivers_license",
                id_state="HI",
                id_number="H1234567",
                id_expiry=date(2028, 6, 15),
                id_address=Address(
                    street="100 Main St", apt="Apt 3",
                    city="Honolulu", state="HI", zip_code="96816",
                ),
                occupation_title="Engineer",
                employment_status="employed",
                wage_income=75000,
            ),
            Person(
                person_id="p-02",
                relationship=RelationshipType.SPOUSE,
                age=38,
                sex="F",
                legal_first_name="Mary",
                legal_last_name="Smith",
                ssn="900-22-2222",
                dob=date(1984, 7, 22),
            ),
            Person(
                person_id="p-03",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=10,
                sex="M",
                legal_first_name="Jake",
                legal_last_name="Smith",
                ssn="900-33-3333",
                dob=date(2012, 1, 5),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
                is_full_time_student=False,
            ),
        ],
    )


@pytest.fixture
def sample_scenario(sample_household: Household) -> Scenario:
    return Scenario(
        scenario_id="sc-001",
        mode="verify",
        difficulty="medium",
        household=sample_household,
        injected_errors=[
            InjectedError(
                error_id="err-1",
                category="name",
                field="spouse_first_name",
                person_id="p-02",
                document="intake_form",
                correct_value="Mary",
                erroneous_value="Marie",
                explanation="First name misspelled on intake form",
                difficulty="easy",
            ),
        ],
        client_facts=[
            ClientFact(
                category="citizenship",
                question="Are you a U.S. citizen?",
                answer="Yes",
                form_field="you_us_citizen",
                person_id="p-01",
                required=True,
            ),
        ],
        document_paths={
            "ssn_primary": "/tmp/docs/ssn_primary.png",
            "dl_primary": "/tmp/docs/dl_primary.png",
        },
        created_at="2025-01-15T10:30:00",
    )


@pytest.fixture
def sample_grade() -> GradingResult:
    return GradingResult(
        score=8,
        max_score=10,
        accuracy=0.8,
        correct_flags=[{"error_id": "err-1", "field": "spouse_first_name"}],
        missed_flags=[{"error_id": "err-2", "field": "ssn"}],
        false_flags=[],
        feedback="Good work. You missed an SSN transposition.",
        field_feedback=[
            {"field": "spouse_first_name", "status": "correct"},
            {"field": "ssn", "status": "missed"},
        ],
    )


# =========================================================================
# Init & table creation
# =========================================================================

class TestInit:

    def test_creates_db_file(self, tmp_path: Path) -> None:
        db = str(tmp_path / "new.sqlite")
        store = ScenarioStore(db_path=db)
        assert os.path.exists(db)
        store.close()

    def test_creates_parent_dirs(self, tmp_path: Path) -> None:
        db = str(tmp_path / "sub" / "dir" / "db.sqlite")
        store = ScenarioStore(db_path=db)
        assert os.path.exists(db)
        store.close()

    def test_tables_exist(self, store: ScenarioStore) -> None:
        cur = store._conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name",
        )
        tables = {row["name"] for row in cur}
        assert "scenarios" in tables
        assert "grades" in tables

    def test_idempotent_init(self, tmp_path: Path) -> None:
        db = str(tmp_path / "idem.sqlite")
        s1 = ScenarioStore(db_path=db)
        s1.close()
        s2 = ScenarioStore(db_path=db)  # Should not crash
        s2.close()


# =========================================================================
# Scenario CRUD
# =========================================================================

class TestSaveAndGet:

    def test_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        assert got.scenario_id == "sc-001"
        assert got.mode == "verify"
        assert got.difficulty == "medium"
        assert got.created_at == "2025-01-15T10:30:00"

    def test_household_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        hh = got.household
        assert hh is not None
        assert hh.household_id == "hh-001"
        assert hh.state == "HI"
        assert hh.pattern == "married_couple_with_children"
        assert len(hh.members) == 3

    def test_person_fields_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        primary = got.household.members[0]
        assert primary.person_id == "p-01"
        assert primary.legal_first_name == "John"
        assert primary.ssn == "900-11-1111"
        assert primary.dob == date(1982, 3, 10)
        assert primary.wage_income == 75000
        assert primary.id_type == "drivers_license"
        assert primary.id_expiry == date(2028, 6, 15)

    def test_address_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        addr = got.household.address
        assert addr is not None
        assert addr.street == "100 Main St"
        assert addr.apt == "Apt 3"
        assert addr.zip_code == "96816"

    def test_id_address_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        id_addr = got.household.members[0].id_address
        assert id_addr is not None
        assert id_addr.street == "100 Main St"

    def test_injected_errors_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        assert len(got.injected_errors) == 1
        err = got.injected_errors[0]
        assert err.error_id == "err-1"
        assert err.category == "name"
        assert err.correct_value == "Mary"
        assert err.erroneous_value == "Marie"

    def test_client_facts_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        assert len(got.client_facts) == 1
        fact = got.client_facts[0]
        assert fact.category == "citizenship"
        assert fact.answer == "Yes"
        assert fact.required is True

    def test_document_paths_round_trip(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        got = store.get_scenario("sc-001")
        assert got is not None
        assert got.document_paths["ssn_primary"] == "/tmp/docs/ssn_primary.png"
        assert got.document_paths["dl_primary"] == "/tmp/docs/dl_primary.png"

    def test_get_missing_returns_none(self, store: ScenarioStore) -> None:
        assert store.get_scenario("nonexistent") is None

    def test_duplicate_id_raises(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        with pytest.raises(sqlite3.IntegrityError):
            store.save_scenario(sample_scenario)

    def test_save_returns_id(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        result = store.save_scenario(sample_scenario)
        assert result == "sc-001"

    def test_auto_created_at(self, store: ScenarioStore) -> None:
        sc = Scenario(
            scenario_id="sc-auto",
            mode="intake",
            difficulty="easy",
        )
        store.save_scenario(sc)
        got = store.get_scenario("sc-auto")
        assert got is not None
        assert got.created_at  # Should be auto-populated


class TestListScenarios:

    def _make_scenario(self, sid: str, mode: str, diff: str) -> Scenario:
        return Scenario(
            scenario_id=sid, mode=mode, difficulty=diff,
            created_at=f"2025-01-{int(sid.split('-')[1]):02d}T00:00:00",
        )

    def test_list_empty(self, store: ScenarioStore) -> None:
        assert store.list_scenarios() == []

    def test_list_all(self, store: ScenarioStore) -> None:
        for i in range(5):
            store.save_scenario(
                self._make_scenario(f"sc-{i}", "intake", "easy"),
            )
        result = store.list_scenarios()
        assert len(result) == 5

    def test_list_with_limit(self, store: ScenarioStore) -> None:
        for i in range(5):
            store.save_scenario(
                self._make_scenario(f"sc-{i}", "intake", "easy"),
            )
        result = store.list_scenarios(limit=3)
        assert len(result) == 3

    def test_list_with_offset(self, store: ScenarioStore) -> None:
        for i in range(5):
            store.save_scenario(
                self._make_scenario(f"sc-{i}", "intake", "easy"),
            )
        result = store.list_scenarios(limit=50, offset=3)
        assert len(result) == 2

    def test_filter_by_mode(self, store: ScenarioStore) -> None:
        store.save_scenario(self._make_scenario("sc-1", "intake", "easy"))
        store.save_scenario(self._make_scenario("sc-2", "verify", "easy"))
        store.save_scenario(self._make_scenario("sc-3", "intake", "hard"))
        result = store.list_scenarios(mode="intake")
        assert len(result) == 2
        assert all(s.mode == "intake" for s in result)

    def test_filter_by_difficulty(self, store: ScenarioStore) -> None:
        store.save_scenario(self._make_scenario("sc-1", "intake", "easy"))
        store.save_scenario(self._make_scenario("sc-2", "verify", "hard"))
        store.save_scenario(self._make_scenario("sc-3", "intake", "hard"))
        result = store.list_scenarios(difficulty="hard")
        assert len(result) == 2
        assert all(s.difficulty == "hard" for s in result)

    def test_filter_combined(self, store: ScenarioStore) -> None:
        store.save_scenario(self._make_scenario("sc-1", "intake", "easy"))
        store.save_scenario(self._make_scenario("sc-2", "verify", "hard"))
        store.save_scenario(self._make_scenario("sc-3", "intake", "hard"))
        result = store.list_scenarios(mode="intake", difficulty="hard")
        assert len(result) == 1
        assert result[0].scenario_id == "sc-3"

    def test_newest_first(self, store: ScenarioStore) -> None:
        store.save_scenario(self._make_scenario("sc-1", "intake", "easy"))
        store.save_scenario(self._make_scenario("sc-5", "intake", "easy"))
        store.save_scenario(self._make_scenario("sc-3", "intake", "easy"))
        result = store.list_scenarios()
        ids = [s.scenario_id for s in result]
        # sc-5 has latest date (Jan 5), sc-3 next (Jan 3), sc-1 last (Jan 1)
        assert ids == ["sc-5", "sc-3", "sc-1"]


class TestDeleteScenario:

    def test_delete_existing(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        assert store.delete_scenario("sc-001") is True
        assert store.get_scenario("sc-001") is None

    def test_delete_nonexistent(self, store: ScenarioStore) -> None:
        assert store.delete_scenario("nope") is False

    def test_delete_cascades_grades(
        self, store: ScenarioStore,
        sample_scenario: Scenario,
        sample_grade: GradingResult,
    ) -> None:
        store.save_scenario(sample_scenario)
        store.save_grade("sc-001", sample_grade)
        store.delete_scenario("sc-001")
        # Grade should be gone too
        assert store.get_grades("sc-001") == []


class TestCountScenarios:

    def test_empty(self, store: ScenarioStore) -> None:
        assert store.count_scenarios() == 0

    def test_after_inserts(
        self, store: ScenarioStore, sample_scenario: Scenario,
    ) -> None:
        store.save_scenario(sample_scenario)
        assert store.count_scenarios() == 1


# =========================================================================
# Grades
# =========================================================================

class TestGrades:

    def test_save_and_get(
        self, store: ScenarioStore,
        sample_scenario: Scenario,
        sample_grade: GradingResult,
    ) -> None:
        store.save_scenario(sample_scenario)
        grade_id = store.save_grade("sc-001", sample_grade)
        assert grade_id > 0
        grades = store.get_grades("sc-001")
        assert len(grades) == 1
        g = grades[0]
        assert g.score == 8
        assert g.max_score == 10
        assert g.accuracy == 0.8
        assert len(g.correct_flags) == 1
        assert len(g.missed_flags) == 1
        assert g.feedback == "Good work. You missed an SSN transposition."
        assert len(g.field_feedback) == 2

    def test_multiple_grades_per_scenario(
        self, store: ScenarioStore,
        sample_scenario: Scenario,
        sample_grade: GradingResult,
    ) -> None:
        store.save_scenario(sample_scenario)
        store.save_grade("sc-001", sample_grade)
        # Second attempt
        better = GradingResult(score=10, max_score=10, accuracy=1.0)
        store.save_grade("sc-001", better)
        grades = store.get_grades("sc-001")
        assert len(grades) == 2

    def test_grade_for_missing_scenario_raises(
        self, store: ScenarioStore, sample_grade: GradingResult,
    ) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            store.save_grade("nonexistent", sample_grade)

    def test_get_grades_empty(self, store: ScenarioStore) -> None:
        assert store.get_grades("sc-001") == []


# =========================================================================
# Progress & Stats
# =========================================================================

class TestProgress:

    def test_empty_progress(self, store: ScenarioStore) -> None:
        assert store.get_progress() == []

    def test_progress_after_grading(
        self, store: ScenarioStore,
        sample_scenario: Scenario,
        sample_grade: GradingResult,
    ) -> None:
        store.save_scenario(sample_scenario)
        store.save_grade("sc-001", sample_grade)
        progress = store.get_progress()
        assert len(progress) == 1
        row = progress[0]
        assert row["scenario_id"] == "sc-001"
        assert row["mode"] == "verify"
        assert row["difficulty"] == "medium"
        assert row["score"] == 8
        assert row["max_score"] == 10
        assert row["accuracy"] == 0.8

    def test_progress_includes_pattern(
        self, store: ScenarioStore,
        sample_scenario: Scenario,
        sample_grade: GradingResult,
    ) -> None:
        store.save_scenario(sample_scenario)
        store.save_grade("sc-001", sample_grade)
        progress = store.get_progress()
        assert progress[0]["pattern"] == "married_couple_with_children"


class TestSummaryStats:

    def test_empty_stats(self, store: ScenarioStore) -> None:
        stats = store.get_summary_stats()
        assert stats["total_scenarios"] == 0
        assert stats["total_graded"] == 0
        assert stats["average_accuracy"] == 0.0

    def test_stats_with_data(self, store: ScenarioStore) -> None:
        sc1 = Scenario(
            scenario_id="sc-1", mode="intake", difficulty="easy",
        )
        sc2 = Scenario(
            scenario_id="sc-2", mode="verify", difficulty="hard",
        )
        store.save_scenario(sc1)
        store.save_scenario(sc2)
        store.save_grade("sc-1", GradingResult(
            score=9, max_score=10, accuracy=0.9,
        ))
        store.save_grade("sc-2", GradingResult(
            score=7, max_score=10, accuracy=0.7,
        ))

        stats = store.get_summary_stats()
        assert stats["total_scenarios"] == 2
        assert stats["total_graded"] == 2
        assert stats["average_accuracy"] == 0.8

        assert "easy" in stats["by_difficulty"]
        assert stats["by_difficulty"]["easy"]["count"] == 1
        assert stats["by_difficulty"]["easy"]["average_accuracy"] == 0.9

        assert "intake" in stats["by_mode"]
        assert stats["by_mode"]["intake"]["count"] == 1


# =========================================================================
# Relationship type round-trip
# =========================================================================

class TestRelationshipRoundTrip:

    def test_all_relationship_types(self, store: ScenarioStore) -> None:
        """Verify every RelationshipType survives serialisation."""
        members = []
        for i, rt in enumerate(RelationshipType):
            members.append(Person(
                person_id=f"p-{i}",
                relationship=rt,
                age=30 + i,
            ))
        hh = Household(
            household_id="hh-rt",
            state="HI",
            year=2022,
            pattern="other",
            members=members,
        )
        sc = Scenario(scenario_id="sc-rt", mode="intake", difficulty="easy", household=hh)
        store.save_scenario(sc)

        got = store.get_scenario("sc-rt")
        assert got is not None
        for orig, loaded in zip(members, got.household.members):
            assert loaded.relationship == orig.relationship
