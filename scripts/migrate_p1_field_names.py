#!/usr/bin/env python3
"""
Migrate stored scenarios' ground_truth.form_answers to the new Page 1
field-name namespace.

Background
----------
docs/PAGE1_INTEGRATION_PLAN.md Phase 1B renames the wire-format field names
used by the 13614-C answer key (e.g. ``you.first_name`` → ``filer.first_name``,
single ``dep.0.name`` instead of split ``dep.0.first_name`` /
``dep.0.last_name``). Stored scenarios in ``data/scenarios.sqlite`` have
``ground_truth.form_answers`` keyed by the old names; without migration, the
grader (which reads PART1_FIELDS at runtime) would silently zero every Page 1
score because the keys won't match.

This script regenerates ``ground_truth.form_answers`` for every stored
scenario by re-running ``training.grader.build_form_answers`` over the row's
household. Whatever names the populator currently emits become the new answer
key.

Sequencing
----------
- **Pre-1B (script lands first):** populator still emits old names; running
  the script is a no-op rewrite (old names → old names with same values).
- **Post-1B (rename has landed):** populator emits new names; running the
  script flips stored answer keys to new names.

Idempotent: re-running produces identical output. Safe to invoke multiple
times.

Usage
-----
    python scripts/migrate_p1_field_names.py                    # apply
    python scripts/migrate_p1_field_names.py --dry-run          # preview
    python scripts/migrate_p1_field_names.py --db path/to.db    # custom path

Exit codes: 0 on success; non-zero on any per-row failure (errors logged).
"""

from __future__ import annotations

import argparse
import json
import logging
import sqlite3
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT))

from training.scenario_store import _DateEncoder, _deserialize_household  # noqa: E402
from training.grader import build_form_answers  # noqa: E402

DEFAULT_DB = REPO_ROOT / "data" / "scenarios.sqlite"

logger = logging.getLogger("migrate_p1_field_names")


def _migrate_row(row: sqlite3.Row) -> tuple[str, dict | None]:
    """Compute the new ground_truth dict for one scenario row.

    Returns (scenario_id, new_ground_truth_dict). ``new_ground_truth_dict``
    is None when the row has no household or no ground_truth — we leave
    those rows alone.
    """
    scenario_id = row["scenario_id"]
    hh_blob = row["household"]
    gt_blob = row["ground_truth"]

    if not hh_blob or hh_blob == "{}":
        return scenario_id, None
    if not gt_blob:
        return scenario_id, None

    household = _deserialize_household(hh_blob)
    fresh_form_answers = build_form_answers(household)

    gt = json.loads(gt_blob)
    gt["form_answers"] = fresh_form_answers
    return scenario_id, gt


def migrate(db_path: Path, dry_run: bool) -> int:
    """Walk every scenarios row and refresh form_answers.

    Returns the number of rows actually changed (or that would be changed
    in dry-run mode).
    """
    if not db_path.exists():
        logger.info("No database at %s — nothing to migrate.", db_path)
        return 0

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        rows = conn.execute(
            "SELECT scenario_id, household, ground_truth FROM scenarios"
        ).fetchall()
        if not rows:
            logger.info("scenarios table is empty — nothing to migrate.")
            return 0

        changed = 0
        for row in rows:
            try:
                scenario_id, new_gt = _migrate_row(row)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    "Skipping %s: %s", row["scenario_id"], exc,
                )
                continue
            if new_gt is None:
                continue

            old_form_answers = json.loads(row["ground_truth"]).get(
                "form_answers", {}
            )
            if old_form_answers == new_gt["form_answers"]:
                # No-op: this row is already up to date.
                continue
            changed += 1

            if dry_run:
                added = set(new_gt["form_answers"]) - set(old_form_answers)
                removed = set(old_form_answers) - set(new_gt["form_answers"])
                logger.info(
                    "[dry-run] %s: +%d -%d keys",
                    scenario_id,
                    len(added),
                    len(removed),
                )
                continue

            new_gt_blob = json.dumps(new_gt, cls=_DateEncoder)
            conn.execute(
                "UPDATE scenarios SET ground_truth = ? WHERE scenario_id = ?",
                (new_gt_blob, scenario_id),
            )
            logger.info("Migrated %s", scenario_id)

        if not dry_run:
            conn.commit()

        return changed
    finally:
        conn.close()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    parser.add_argument(
        "--db",
        type=Path,
        default=DEFAULT_DB,
        help=f"Path to the scenarios SQLite database (default: {DEFAULT_DB}).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print what would change without writing to the database.",
    )
    parser.add_argument(
        "--quiet",
        action="store_true",
        help="Suppress per-row INFO logging; print only the summary.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING if args.quiet else logging.INFO,
        format="%(message)s",
    )

    changed = migrate(args.db, dry_run=args.dry_run)
    verb = "would change" if args.dry_run else "changed"
    print(f"{verb} {changed} scenario row(s).")
    return 0


if __name__ == "__main__":
    sys.exit(main())
