"""Tests for scripts/migrate_p1_field_names.py (Phase 1F).

The migration script regenerates ground_truth.form_answers for every
stored scenario by re-running build_form_answers over the row's
household. After Phase 1B (the rename), this is the load-bearing
mechanism that flips stored answer keys from the legacy ``you.*`` /
split-name dependent namespace to the new ``filer.*`` / single
``dep.{i}.name`` namespace.

Tests:
1. Empty / missing database is a no-op (exit 0, 0 rows changed).
2. Migrating a stored scenario refreshes its form_answers to match
   the current populator's output.
3. Re-running the script is idempotent (zero changes the second time).
4. --dry-run does not modify the database.
5. Scenarios with NULL ground_truth or empty households are skipped.
"""

from __future__ import annotations

import importlib.util
import json
from datetime import date
from pathlib import Path

import pytest

from generator.models import (
    Address,
    Household,
    Person,
    RelationshipType,
)
from generator.models import Scenario
from training.grader import build_form_answers
from training.scenario_store import ScenarioStore


# Load the migration script as a module so we can call its functions
# directly (it lives outside the package tree).
_SCRIPT = (
    Path(__file__).resolve().parent.parent
    / "scripts" / "migrate_p1_field_names.py"
)
_spec = importlib.util.spec_from_file_location(
    "migrate_p1_field_names", _SCRIPT,
)
migrate_module = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(migrate_module)


def _make_household() -> Household:
    return Household(
        household_id="hh-mig",
        state="HI",
        year=2022,
        pattern="married_couple",
        address=Address(street="1 Main", city="Honolulu",
                        state="HI", zip_code="96815"),
        members=[
            Person(
                person_id="p-1",
                relationship=RelationshipType.HOUSEHOLDER,
                age=40,
                legal_first_name="Jane",
                legal_last_name="Doe",
                ssn="900-12-3456",
                dob=date(1985, 4, 12),
            ),
            Person(
                person_id="p-2",
                relationship=RelationshipType.BIOLOGICAL_CHILD,
                age=10,
                legal_first_name="Sam",
                legal_last_name="Doe",
                ssn="900-12-9999",
                dob=date(2014, 8, 22),
                is_dependent=True,
                can_be_claimed=True,
                months_in_home=12,
            ),
        ],
    )


def _save_scenario_with_legacy_gt(
    store: ScenarioStore, scenario_id: str, legacy_keys: dict,
) -> None:
    """Save a scenario whose ground_truth uses the OLD namespace.

    Simulates a pre-1B stored scenario for the migration to clean up.
    """
    hh = _make_household()
    scenario = Scenario(
        scenario_id=scenario_id,
        mode="encounter",
        difficulty="easy",
        household=hh,
        injected_errors=[],
        client_facts=[],
        document_paths={},
        ground_truth={"form_answers": legacy_keys, "schema_version": 1},
        interview_notes=None,
        concept_tags=None,
    )
    store.save_scenario(scenario)


@pytest.fixture
def empty_db(tmp_path: Path) -> Path:
    """Return a path to a non-existent SQLite file (so migrate sees no DB)."""
    return tmp_path / "scenarios.sqlite"


@pytest.fixture
def populated_db(tmp_path: Path) -> Path:
    db = tmp_path / "scenarios.sqlite"
    store = ScenarioStore(db_path=str(db))
    legacy = {
        "you.first_name": "Janet",      # OLD namespace
        "you.last_name": "Doe",
        "you.dob": "04/12/1985",
        "dep.0.first_name": "Sam",       # OLD split-name shape
        "dep.0.last_name": "Doe",
    }
    _save_scenario_with_legacy_gt(store, "sc-mig-001", legacy)
    store.close()
    return db


class TestMigrateEmptyDB:

    def test_missing_file_is_noop(self, empty_db: Path) -> None:
        """No database → 0 changes, no exception."""
        assert not empty_db.exists()
        changed = migrate_module.migrate(empty_db, dry_run=False)
        assert changed == 0

    def test_empty_table_is_noop(self, tmp_path: Path) -> None:
        db = tmp_path / "scenarios.sqlite"
        store = ScenarioStore(db_path=str(db))
        store.close()  # creates schema with no rows
        assert db.exists()
        changed = migrate_module.migrate(db, dry_run=False)
        assert changed == 0


class TestMigrateRefreshes:

    def test_legacy_form_answers_get_replaced(
        self, populated_db: Path,
    ) -> None:
        """The migration replaces ground_truth.form_answers with whatever
        build_form_answers emits today."""
        changed = migrate_module.migrate(populated_db, dry_run=False)
        assert changed == 1

        store = ScenarioStore(db_path=str(populated_db))
        try:
            scenario = store.get_scenario("sc-mig-001")
            fa = scenario.ground_truth["form_answers"]

            # New namespace keys present.
            assert "filer.first_name" in fa
            assert fa["filer.first_name"] == "Jane"
            # Old namespace keys gone.
            assert "you.first_name" not in fa
            assert "dep.0.first_name" not in fa
            # Single combined dep name.
            assert "dep.0.name" in fa
            assert fa["dep.0.name"] == "Sam Doe"

            # Sanity: the rewritten dict matches the current populator.
            expected = build_form_answers(scenario.household)
            assert fa == expected
        finally:
            store.close()


class TestIdempotent:

    def test_second_run_changes_nothing(self, populated_db: Path) -> None:
        first = migrate_module.migrate(populated_db, dry_run=False)
        assert first == 1
        second = migrate_module.migrate(populated_db, dry_run=False)
        assert second == 0


class TestDryRun:

    def test_dry_run_does_not_write(self, populated_db: Path) -> None:
        store = ScenarioStore(db_path=str(populated_db))
        try:
            before = store.get_scenario("sc-mig-001").ground_truth
        finally:
            store.close()

        changed = migrate_module.migrate(populated_db, dry_run=True)
        # dry_run still reports the row as "would change".
        assert changed == 1

        store = ScenarioStore(db_path=str(populated_db))
        try:
            after = store.get_scenario("sc-mig-001").ground_truth
        finally:
            store.close()
        assert before == after, "dry_run must not modify the database"


class TestSkipUnpopulatedRows:

    def test_scenario_without_ground_truth_is_skipped(
        self, tmp_path: Path,
    ) -> None:
        """A row with NULL ground_truth (e.g. an in-flight scenario)
        is left alone by the migration."""
        db = tmp_path / "scenarios.sqlite"
        store = ScenarioStore(db_path=str(db))
        hh = _make_household()
        scenario = Scenario(
            scenario_id="sc-noGT",
            mode="encounter",
            difficulty="easy",
            household=hh,
            injected_errors=[],
            client_facts=[],
            document_paths={},
            ground_truth=None,  # No ground truth
            interview_notes=None,
            concept_tags=None,
        )
        store.save_scenario(scenario)
        store.close()

        changed = migrate_module.migrate(db, dry_run=False)
        assert changed == 0
