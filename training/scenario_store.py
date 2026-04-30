"""
Scenario store — SQLite persistence for generated scenarios, submissions, and grades.

Database: data/scenarios.sqlite (created at runtime, gitignored)

Tables
------
scenarios
    One row per generated exercise. The household and injected errors are
    stored as JSON blobs so the full object graph round-trips without a
    complex relational schema.

grades
    One row per student submission / grading result, linked to a scenario.

The store is intentionally simple — it's for a single-user training app,
not a multi-tenant system.  Reads/writes go through plain sqlite3 (no ORM)
for minimal dependencies and transparency.
"""

import json
import logging
import os
import sqlite3
from dataclasses import asdict
from datetime import date, datetime
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional

from generator.models import (
    Address,
    ClientFact,
    Employer,
    Form1099DIV,
    Form1099INT,
    Form1099NEC,
    Form1099R,
    GradingResult,
    Household,
    InjectedError,
    Person,
    RelationshipType,
    SSA1099,
    Scenario,
    W2,
)

logger = logging.getLogger(__name__)

# =========================================================================
# SQL DDL
# =========================================================================

_CREATE_SCENARIOS = """\
CREATE TABLE IF NOT EXISTS scenarios (
    scenario_id   TEXT PRIMARY KEY,
    mode          TEXT NOT NULL,
    difficulty    TEXT NOT NULL,
    state         TEXT NOT NULL DEFAULT '',
    pattern       TEXT NOT NULL DEFAULT '',
    household     TEXT NOT NULL,          -- JSON blob
    injected_errors TEXT NOT NULL DEFAULT '[]',  -- JSON array
    client_facts  TEXT NOT NULL DEFAULT '[]',    -- JSON array
    document_paths TEXT NOT NULL DEFAULT '{}',   -- JSON object
    created_at    TEXT NOT NULL
);
"""

_CREATE_GRADES = """\
CREATE TABLE IF NOT EXISTS grades (
    grade_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    scenario_id   TEXT NOT NULL REFERENCES scenarios(scenario_id),
    section       TEXT NOT NULL DEFAULT '',      -- 'intake', 'income', or '' (legacy)
    score         INTEGER NOT NULL,
    max_score     INTEGER NOT NULL,
    accuracy      REAL NOT NULL,
    correct_flags TEXT NOT NULL DEFAULT '[]',    -- JSON array
    missed_flags  TEXT NOT NULL DEFAULT '[]',    -- JSON array
    false_flags   TEXT NOT NULL DEFAULT '[]',    -- JSON array
    feedback      TEXT NOT NULL DEFAULT '',
    field_feedback TEXT NOT NULL DEFAULT '[]',   -- JSON array
    graded_at     TEXT NOT NULL
);
"""


# =========================================================================
# JSON helpers (date-aware serialisation / deserialisation)
# =========================================================================

class _DateEncoder(json.JSONEncoder):
    """Encode ``date``, ``datetime``, and ``Enum`` objects."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (date, datetime)):
            return o.isoformat()
        if isinstance(o, Enum):
            return o.value
        return super().default(o)


def _serialize_household(household: Household) -> str:
    """Convert a Household to a JSON string.

    Uses ``dataclasses.asdict`` instead of ``to_dict`` so that all
    fields (including per-person income, expenses, and dependent flags)
    are captured.  Enum values are stored as their ``.value`` strings.
    """
    raw = asdict(household)
    return json.dumps(raw, cls=_DateEncoder)


def _serialize_errors(errors: List[InjectedError]) -> str:
    return json.dumps([asdict(e) for e in errors], cls=_DateEncoder)


def _serialize_facts(facts: List[ClientFact]) -> str:
    return json.dumps([asdict(f) for f in facts], cls=_DateEncoder)


def _serialize_doc_paths(paths: dict) -> str:
    return json.dumps(paths)


def _deserialize_employer(d: dict) -> Employer:
    """Rebuild an Employer from its dict."""
    addr = d.get("address")
    return Employer(
        name=d.get("name", ""),
        ein=d.get("ein", ""),
        address=Address(**addr) if addr else None,
    )


def _deserialize_w2(d: dict) -> W2:
    """Rebuild a W2 from its dict."""
    emp = d.get("employer")
    box_12_raw = d.get("box_12", [])
    box_12 = []
    for item in box_12_raw:
        if isinstance(item, dict):
            box_12.append((item["code"], item["amount"]))
        else:
            box_12.append((item[0], item[1]))
    return W2(
        employer=_deserialize_employer(emp) if emp else None,
        wages=d.get("wages", 0),
        federal_tax_withheld=d.get("federal_tax_withheld", 0),
        social_security_wages=d.get("social_security_wages", 0),
        social_security_tax=d.get("social_security_tax", 0),
        medicare_wages=d.get("medicare_wages", 0),
        medicare_tax=d.get("medicare_tax", 0),
        box_12=box_12,
        state=d.get("state", ""),
        state_wages=d.get("state_wages", 0),
        state_tax=d.get("state_tax", 0),
        control_number=d.get("control_number", ""),
    )


def _deserialize_person(d: dict) -> Person:
    """Rebuild a Person from its dict representation."""
    id_addr = d.get("id_address")

    # Income documents
    w2s = [_deserialize_w2(w) for w in d.get("w2s", [])]
    form_1099_ints = [Form1099INT(**f) for f in d.get("form_1099_ints", [])]
    form_1099_divs = [Form1099DIV(**f) for f in d.get("form_1099_divs", [])]
    form_1099_rs = [Form1099R(**f) for f in d.get("form_1099_rs", [])]
    ssa_raw = d.get("ssa_1099")
    ssa_1099 = SSA1099(**ssa_raw) if ssa_raw else None
    form_1099_necs = [Form1099NEC(**f) for f in d.get("form_1099_necs", [])]

    return Person(
        person_id=d.get("person_id", ""),
        relationship=RelationshipType(d["relationship"]) if d.get("relationship") else RelationshipType.HOUSEHOLDER,
        age=d.get("age", 0),
        sex=d.get("sex", ""),
        race=d.get("race", ""),
        hispanic_origin=d.get("hispanic_origin", False),
        legal_first_name=d.get("legal_first_name", ""),
        legal_middle_name=d.get("legal_middle_name", ""),
        legal_last_name=d.get("legal_last_name", ""),
        suffix=d.get("suffix", ""),
        ssn=d.get("ssn", ""),
        dob=date.fromisoformat(d["dob"]) if d.get("dob") else None,
        phone=d.get("phone", ""),
        email=d.get("email", ""),
        id_type=d.get("id_type", ""),
        id_state=d.get("id_state", ""),
        id_number=d.get("id_number", ""),
        id_expiry=date.fromisoformat(d["id_expiry"]) if d.get("id_expiry") else None,
        id_address=Address(**id_addr) if id_addr else None,
        is_dependent=d.get("is_dependent", False),
        can_be_claimed=d.get("can_be_claimed", False),
        months_in_home=d.get("months_in_home", 12),
        is_full_time_student=d.get("is_full_time_student", False),
        employment_status=d.get("employment_status", ""),
        education=d.get("education", ""),
        occupation_code=d.get("occupation_code"),
        occupation_title=d.get("occupation_title"),
        has_disability=d.get("has_disability", False),
        wage_income=d.get("wage_income", 0),
        self_employment_income=d.get("self_employment_income", 0),
        social_security_income=d.get("social_security_income", 0),
        retirement_income=d.get("retirement_income", 0),
        interest_income=d.get("interest_income", 0),
        dividend_income=d.get("dividend_income", 0),
        other_income=d.get("other_income", 0),
        public_assistance_income=d.get("public_assistance_income", 0),
        student_loan_interest=d.get("student_loan_interest", 0),
        educator_expenses=d.get("educator_expenses", 0),
        ira_contributions=d.get("ira_contributions", 0),
        w2s=w2s,
        form_1099_ints=form_1099_ints,
        form_1099_divs=form_1099_divs,
        form_1099_rs=form_1099_rs,
        ssa_1099=ssa_1099,
        form_1099_necs=form_1099_necs,
    )


def _deserialize_household(blob: str) -> Household:
    """Rebuild a Household from its JSON string (asdict format)."""
    d = json.loads(blob)
    addr = d.get("address")
    members = [_deserialize_person(m) for m in d.get("members", [])]
    return Household(
        household_id=d.get("household_id", ""),
        state=d.get("state", ""),
        year=d.get("year", 0),
        pattern=d.get("pattern", ""),
        members=members,
        address=Address(**addr) if addr else None,
        expected_adults=d.get("expected_adults"),
        expected_children_range=tuple(d["expected_children_range"]) if d.get("expected_children_range") else None,
        expected_complexity=d.get("expected_complexity"),
        property_taxes=d.get("property_taxes", 0),
        mortgage_interest=d.get("mortgage_interest", 0),
        state_income_tax=d.get("state_income_tax", 0),
        medical_expenses=d.get("medical_expenses", 0),
        charitable_contributions=d.get("charitable_contributions", 0),
        child_care_expenses=d.get("child_care_expenses", 0),
        education_expenses=d.get("education_expenses", 0),
    )


def _deserialize_errors(blob: str) -> List[InjectedError]:
    items = json.loads(blob)
    return [InjectedError(**item) for item in items]


def _deserialize_facts(blob: str) -> List[ClientFact]:
    items = json.loads(blob)
    return [ClientFact(**item) for item in items]


def _deserialize_grade(row: sqlite3.Row) -> GradingResult:
    return GradingResult(
        score=row["score"],
        max_score=row["max_score"],
        accuracy=row["accuracy"],
        correct_flags=json.loads(row["correct_flags"]),
        missed_flags=json.loads(row["missed_flags"]),
        false_flags=json.loads(row["false_flags"]),
        feedback=row["feedback"],
        field_feedback=json.loads(row["field_feedback"]),
    )


def _grade_section(row: sqlite3.Row) -> str:
    """Extract the section tag from a grade row."""
    try:
        return row["section"] or ""
    except (IndexError, KeyError):
        return ""


# =========================================================================
# ScenarioStore
# =========================================================================

class ScenarioStore:
    """CRUD for scenarios, submissions, and grades.

    Args:
        db_path: Path to the SQLite file. Created if it doesn't exist.
    """

    def __init__(self, db_path: str = "data/scenarios.sqlite") -> None:
        self._db_path = db_path
        os.makedirs(os.path.dirname(db_path) or ".", exist_ok=True)
        self._conn = sqlite3.connect(db_path)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL;")
        self._conn.execute("PRAGMA foreign_keys=ON;")
        self._create_tables()
        logger.info("ScenarioStore initialised at %s", db_path)

    # ------------------------------------------------------------------
    # Schema
    # ------------------------------------------------------------------

    def _create_tables(self) -> None:
        self._conn.execute(_CREATE_SCENARIOS)
        self._conn.execute(_CREATE_GRADES)
        self._migrate_grades_section()
        self._conn.commit()

    def _migrate_grades_section(self) -> None:
        """Add 'section' column to grades if it doesn't exist yet."""
        cols = [
            row[1]
            for row in self._conn.execute("PRAGMA table_info(grades)").fetchall()
        ]
        if "section" not in cols:
            self._conn.execute(
                "ALTER TABLE grades ADD COLUMN section TEXT NOT NULL DEFAULT ''"
            )

    # ------------------------------------------------------------------
    # Scenarios
    # ------------------------------------------------------------------

    def save_scenario(self, scenario: Scenario) -> str:
        """Persist a Scenario. Returns the scenario_id.

        Args:
            scenario: A fully-populated Scenario object.

        Returns:
            The scenario_id (same as ``scenario.scenario_id``).

        Raises:
            sqlite3.IntegrityError: If a scenario with the same ID
                already exists.
        """
        now = scenario.created_at or datetime.utcnow().isoformat()
        hh = scenario.household
        self._conn.execute(
            """\
            INSERT INTO scenarios
                (scenario_id, mode, difficulty, state, pattern,
                 household, injected_errors, client_facts,
                 document_paths, created_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario.scenario_id,
                scenario.mode,
                scenario.difficulty,
                hh.state if hh else "",
                hh.pattern if hh else "",
                _serialize_household(hh) if hh else "{}",
                _serialize_errors(scenario.injected_errors),
                _serialize_facts(scenario.client_facts),
                _serialize_doc_paths(scenario.document_paths),
                now,
            ),
        )
        self._conn.commit()
        logger.info("Saved scenario %s", scenario.scenario_id)
        return scenario.scenario_id

    def get_scenario(self, scenario_id: str) -> Optional[Scenario]:
        """Load a Scenario by ID.

        Args:
            scenario_id: The unique scenario identifier.

        Returns:
            Reconstructed Scenario, or ``None`` if not found.
        """
        row = self._conn.execute(
            "SELECT * FROM scenarios WHERE scenario_id = ?",
            (scenario_id,),
        ).fetchone()
        if row is None:
            return None
        return self._row_to_scenario(row)

    def list_scenarios(
        self,
        limit: int = 50,
        offset: int = 0,
        mode: Optional[str] = None,
        difficulty: Optional[str] = None,
    ) -> List[Scenario]:
        """List scenarios with optional filtering.

        Args:
            limit: Max results.
            offset: Pagination offset.
            mode: Filter by exercise mode.
            difficulty: Filter by difficulty.

        Returns:
            List of Scenario objects, newest first.
        """
        clauses: List[str] = []
        params: List[Any] = []
        if mode:
            clauses.append("mode = ?")
            params.append(mode)
        if difficulty:
            clauses.append("difficulty = ?")
            params.append(difficulty)

        where = ""
        if clauses:
            where = "WHERE " + " AND ".join(clauses)

        sql = f"SELECT * FROM scenarios {where} ORDER BY created_at DESC LIMIT ? OFFSET ?"
        params.extend([limit, offset])

        rows = self._conn.execute(sql, params).fetchall()
        return [self._row_to_scenario(r) for r in rows]

    def delete_scenario(self, scenario_id: str) -> bool:
        """Delete a scenario and its associated grades.

        Args:
            scenario_id: The scenario to delete.

        Returns:
            True if a scenario was deleted, False if not found.
        """
        self._conn.execute(
            "DELETE FROM grades WHERE scenario_id = ?", (scenario_id,),
        )
        cursor = self._conn.execute(
            "DELETE FROM scenarios WHERE scenario_id = ?", (scenario_id,),
        )
        self._conn.commit()
        deleted = cursor.rowcount > 0
        if deleted:
            logger.info("Deleted scenario %s", scenario_id)
        return deleted

    def count_scenarios(self) -> int:
        """Return the total number of stored scenarios."""
        row = self._conn.execute("SELECT COUNT(*) FROM scenarios").fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Grades
    # ------------------------------------------------------------------

    def save_grade(
        self,
        scenario_id: str,
        result: GradingResult,
        section: str = "",
    ) -> int:
        """Save a grading result linked to a scenario.

        Args:
            scenario_id: The scenario that was graded.
            result: Grading output from the Grader.
            section: Form section tag (e.g. "intake", "income").

        Returns:
            The auto-incremented grade_id.

        Raises:
            sqlite3.IntegrityError: If scenario_id doesn't exist.
        """
        now = datetime.utcnow().isoformat()
        cursor = self._conn.execute(
            """\
            INSERT INTO grades
                (scenario_id, section, score, max_score, accuracy,
                 correct_flags, missed_flags, false_flags,
                 feedback, field_feedback, graded_at)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                scenario_id,
                section,
                result.score,
                result.max_score,
                result.accuracy,
                json.dumps(result.correct_flags),
                json.dumps(result.missed_flags),
                json.dumps(result.false_flags),
                result.feedback,
                json.dumps(result.field_feedback),
                now,
            ),
        )
        self._conn.commit()
        grade_id = cursor.lastrowid or 0
        logger.info(
            "Saved grade %d for scenario %s [%s] (score=%d/%d)",
            grade_id, scenario_id, section or "all", result.score, result.max_score,
        )
        return grade_id

    def get_grades(self, scenario_id: str) -> List[GradingResult]:
        """Get all grading results for a scenario.

        Args:
            scenario_id: The scenario to look up.

        Returns:
            List of GradingResult objects, oldest first.
        """
        rows = self._conn.execute(
            "SELECT * FROM grades WHERE scenario_id = ? ORDER BY graded_at",
            (scenario_id,),
        ).fetchall()
        return [_deserialize_grade(r) for r in rows]

    def get_section_grades(
        self, scenario_id: str,
    ) -> Dict[str, GradingResult]:
        """Get the most recent grade per section for a scenario.

        Args:
            scenario_id: The scenario to look up.

        Returns:
            Dict mapping section name to the latest GradingResult
            for that section. Keys are "intake", "income", or ""
            (legacy unsectioned grades).
        """
        rows = self._conn.execute(
            """\
            SELECT * FROM grades
            WHERE scenario_id = ?
            ORDER BY graded_at
            """,
            (scenario_id,),
        ).fetchall()
        by_section: Dict[str, GradingResult] = {}
        for row in rows:
            section = _grade_section(row)
            by_section[section] = _deserialize_grade(row)
        return by_section

    def get_progress(self) -> List[dict]:
        """Get student progress: one summary dict per graded scenario.

        Returns:
            List of dicts with keys: scenario_id, mode, difficulty,
            pattern, score, max_score, accuracy, graded_at.
            Ordered newest first.
        """
        rows = self._conn.execute(
            """\
            SELECT
                s.scenario_id,
                s.mode,
                s.difficulty,
                s.pattern,
                g.score,
                g.max_score,
                g.accuracy,
                g.graded_at
            FROM grades g
            JOIN scenarios s ON g.scenario_id = s.scenario_id
            ORDER BY g.graded_at DESC
            """,
        ).fetchall()
        return [dict(r) for r in rows]

    def get_summary_stats(self) -> Dict[str, Any]:
        """Aggregate stats across all graded scenarios.

        Returns:
            Dict with total_scenarios, total_graded, average_accuracy,
            by_difficulty (dict), and by_mode (dict).
        """
        total = self.count_scenarios()

        row = self._conn.execute(
            "SELECT COUNT(*), AVG(accuracy) FROM grades",
        ).fetchone()
        total_graded = row[0] or 0
        avg_accuracy = round(row[1] or 0.0, 2)

        by_difficulty: Dict[str, dict] = {}
        for r in self._conn.execute(
            """\
            SELECT s.difficulty, COUNT(*) as n, AVG(g.accuracy) as avg_acc
            FROM grades g JOIN scenarios s ON g.scenario_id = s.scenario_id
            GROUP BY s.difficulty
            """,
        ):
            by_difficulty[r["difficulty"]] = {
                "count": r["n"],
                "average_accuracy": round(r["avg_acc"], 2),
            }

        by_mode: Dict[str, dict] = {}
        for r in self._conn.execute(
            """\
            SELECT s.mode, COUNT(*) as n, AVG(g.accuracy) as avg_acc
            FROM grades g JOIN scenarios s ON g.scenario_id = s.scenario_id
            GROUP BY s.mode
            """,
        ):
            by_mode[r["mode"]] = {
                "count": r["n"],
                "average_accuracy": round(r["avg_acc"], 2),
            }

        return {
            "total_scenarios": total,
            "total_graded": total_graded,
            "average_accuracy": avg_accuracy,
            "by_difficulty": by_difficulty,
            "by_mode": by_mode,
        }

    # ------------------------------------------------------------------
    # Cleanup
    # ------------------------------------------------------------------

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()
        logger.info("ScenarioStore closed")

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _row_to_scenario(row: sqlite3.Row) -> Scenario:
        hh_blob = row["household"]
        household = _deserialize_household(hh_blob) if hh_blob != "{}" else None
        return Scenario(
            scenario_id=row["scenario_id"],
            mode=row["mode"],
            difficulty=row["difficulty"],
            household=household,
            injected_errors=_deserialize_errors(row["injected_errors"]),
            client_facts=_deserialize_facts(row["client_facts"]),
            document_paths=json.loads(row["document_paths"]),
            created_at=row["created_at"],
        )
