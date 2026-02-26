#!/usr/bin/env python3
"""
Data inventory — reports what distribution data exists in the repository.

Scans data/ for SQLite distribution files and prints a summary of tables,
row counts, state/year, and file sizes. Outputs to stdout as a readable table,
and optionally as JSON or GitHub Actions step summary markdown.

Usage:
    python scripts/data_inventory.py                   # Human-readable table
    python scripts/data_inventory.py --format json     # Machine-readable JSON
    python scripts/data_inventory.py --format markdown  # Markdown table (for CI)
    python scripts/data_inventory.py --github-summary  # Write to $GITHUB_STEP_SUMMARY
"""

import argparse
import json
import logging
import os
import re
import sqlite3
import sys
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)

# Repo root is two levels up from this script (scripts/ -> repo root)
DEFAULT_DATA_DIR = Path(__file__).resolve().parent.parent / "data"

# Expected tables by extraction part
PART1_TABLES = [
    "household_patterns",
    "children_by_parent_age",
    "child_age_distributions",
    "adult_child_ages",
    "stepchild_patterns",
    "multigenerational_patterns",
    "unmarried_partner_patterns",
    "race_distribution",
    "race_by_age",
    "hispanic_origin_by_age",
    "spousal_age_gaps",
    "couple_sex_patterns",
]

PART2_TABLES = [
    "employment_by_age",
    "education_by_age",
    "disability_by_age",
    "social_security",
    "retirement_income",
    "interest_and_dividend_income",
    "other_income_by_employment_status",
    "public_assistance_income",
    "homeownership_rates",
    "property_taxes",
    "mortgage_interest",
    "bls_occupation_wages",
    "education_occupation_probabilities",
    "age_income_adjustments",
    "occupation_self_employment_probability",
]


@dataclass
class TableInfo:
    """Summary of a single table within a distribution database."""
    name: str
    row_count: int
    column_count: int
    columns: List[str]
    part: Optional[str] = None  # "part1", "part2", or None


@dataclass
class DatabaseInfo:
    """Summary of a single distribution SQLite file."""
    filename: str
    path: str
    state: str
    year: int
    file_size_bytes: int
    table_count: int
    total_rows: int
    tables: List[TableInfo] = field(default_factory=list)
    parts_present: List[str] = field(default_factory=list)
    part1_complete: bool = False
    part2_complete: bool = False


def parse_filename(filename: str) -> Optional[tuple]:
    """Parse state and year from distribution filename.

    Args:
        filename: Filename like 'distributions_hi_2022.sqlite'.

    Returns:
        Tuple of (state, year) or None if filename doesn't match pattern.
    """
    match = re.match(
        r"distributions_([a-z]{2})_(\d{4})\.sqlite$",
        filename,
        re.IGNORECASE,
    )
    if match:
        return match.group(1).upper(), int(match.group(2))
    return None


def classify_table(table_name: str) -> Optional[str]:
    """Classify a table as part1, part2, or unknown.

    Args:
        table_name: Name of the database table.

    Returns:
        'part1', 'part2', or None.
    """
    if table_name in PART1_TABLES:
        return "part1"
    if table_name in PART2_TABLES:
        return "part2"
    return None


def inspect_database(db_path: Path) -> Optional[DatabaseInfo]:
    """Inspect a single distribution SQLite file.

    Args:
        db_path: Path to the SQLite file.

    Returns:
        DatabaseInfo with table details, or None if file can't be parsed.
    """
    parsed = parse_filename(db_path.name)
    if parsed is None:
        logger.warning("Skipping unrecognized file: %s", db_path.name)
        return None

    state, year = parsed
    file_size = db_path.stat().st_size

    try:
        conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    except sqlite3.Error as e:
        logger.error("Cannot open %s: %s", db_path, e)
        return None

    try:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
        )
        table_names = [row[0] for row in cursor.fetchall()]

        tables = []
        total_rows = 0
        parts_seen = set()

        for table_name in table_names:
            cursor.execute(f"PRAGMA table_info([{table_name}])")
            columns = [row[1] for row in cursor.fetchall()]

            cursor.execute(f"SELECT COUNT(*) FROM [{table_name}]")
            row_count = cursor.fetchone()[0]

            part = classify_table(table_name)
            if part:
                parts_seen.add(part)

            tables.append(TableInfo(
                name=table_name,
                row_count=row_count,
                column_count=len(columns),
                columns=columns,
                part=part,
            ))
            total_rows += row_count

        part1_tables_present = {
            t.name for t in tables if t.part == "part1"
        }
        part2_tables_present = {
            t.name for t in tables if t.part == "part2"
        }

        return DatabaseInfo(
            filename=db_path.name,
            path=str(db_path),
            state=state,
            year=year,
            file_size_bytes=file_size,
            table_count=len(tables),
            total_rows=total_rows,
            tables=tables,
            parts_present=sorted(parts_seen),
            part1_complete=part1_tables_present == set(PART1_TABLES),
            part2_complete=part2_tables_present == set(PART2_TABLES),
        )
    finally:
        conn.close()


def scan_data_directory(data_dir: Path) -> List[DatabaseInfo]:
    """Scan data directory for all distribution SQLite files.

    Args:
        data_dir: Path to the data directory.

    Returns:
        List of DatabaseInfo objects, sorted by state then year.
    """
    if not data_dir.exists():
        logger.warning("Data directory does not exist: %s", data_dir)
        return []

    results = []
    for db_file in sorted(data_dir.glob("distributions_*.sqlite")):
        info = inspect_database(db_file)
        if info:
            results.append(info)

    results.sort(key=lambda x: (x.state, x.year))
    return results


def format_size(size_bytes: int) -> str:
    """Format byte count as human-readable string."""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    else:
        return f"{size_bytes / (1024 * 1024):.1f} MB"


def format_text(databases: List[DatabaseInfo]) -> str:
    """Format inventory as a human-readable text table."""
    if not databases:
        return "No distribution databases found in data/ directory."

    lines = []
    lines.append("Distribution Data Inventory")
    lines.append("=" * 70)
    lines.append("")
    lines.append(
        f"{'State':<7} {'Year':<6} {'Tables':<8} {'Rows':<10} "
        f"{'Size':<10} {'Parts':<15} {'Complete'}"
    )
    lines.append("-" * 70)

    for db in databases:
        parts_str = ", ".join(db.parts_present) if db.parts_present else "none"
        complete_parts = []
        if db.part1_complete:
            complete_parts.append("P1")
        if db.part2_complete:
            complete_parts.append("P2")
        complete_str = ", ".join(complete_parts) if complete_parts else "-"

        lines.append(
            f"{db.state:<7} {db.year:<6} {db.table_count:<8} "
            f"{db.total_rows:<10,} {format_size(db.file_size_bytes):<10} "
            f"{parts_str:<15} {complete_str}"
        )

    lines.append("")
    lines.append(f"Total: {len(databases)} database(s)")

    # Detailed table breakdown
    for db in databases:
        lines.append("")
        lines.append(f"--- {db.state} {db.year} ({db.filename}) ---")
        for table in db.tables:
            part_tag = f" [{table.part}]" if table.part else ""
            lines.append(
                f"  {table.name:<45} {table.row_count:>8,} rows  "
                f"({table.column_count} cols){part_tag}"
            )

    return "\n".join(lines)


def format_markdown(databases: List[DatabaseInfo]) -> str:
    """Format inventory as a markdown table (for GitHub Actions summary)."""
    if not databases:
        return "### Data Inventory\n\nNo distribution databases found."

    lines = []
    lines.append("### Distribution Data Inventory")
    lines.append("")
    lines.append(
        "| State | Year | Tables | Total Rows | Size | Parts | Complete |"
    )
    lines.append(
        "|-------|------|--------|------------|------|-------|----------|"
    )

    for db in databases:
        parts_str = ", ".join(db.parts_present) if db.parts_present else "-"
        complete_parts = []
        if db.part1_complete:
            complete_parts.append("P1")
        if db.part2_complete:
            complete_parts.append("P2")
        complete_str = ", ".join(complete_parts) if complete_parts else "-"

        lines.append(
            f"| {db.state} | {db.year} | {db.table_count} | "
            f"{db.total_rows:,} | {format_size(db.file_size_bytes)} | "
            f"{parts_str} | {complete_str} |"
        )

    lines.append("")
    lines.append(f"**Total:** {len(databases)} database(s)")

    # Per-database table details
    for db in databases:
        lines.append("")
        lines.append(f"<details><summary>{db.state} {db.year} — table breakdown</summary>")
        lines.append("")
        lines.append("| Table | Rows | Columns | Part |")
        lines.append("|-------|------|---------|------|")
        for table in db.tables:
            part_str = table.part or "-"
            lines.append(
                f"| `{table.name}` | {table.row_count:,} | "
                f"{table.column_count} | {part_str} |"
            )
        lines.append("")
        lines.append("</details>")

    return "\n".join(lines)


def format_json(databases: List[DatabaseInfo]) -> str:
    """Format inventory as JSON."""
    data = {
        "databases": [asdict(db) for db in databases],
        "summary": {
            "total_databases": len(databases),
            "states": sorted(set(db.state for db in databases)),
            "years": sorted(set(db.year for db in databases)),
            "total_rows": sum(db.total_rows for db in databases),
        },
    }
    return json.dumps(data, indent=2)


def write_github_summary(content: str) -> bool:
    """Write content to GitHub Actions step summary.

    Args:
        content: Markdown content to write.

    Returns:
        True if written successfully, False if not in GitHub Actions.
    """
    summary_path = os.environ.get("GITHUB_STEP_SUMMARY")
    if not summary_path:
        logger.info("Not running in GitHub Actions, skipping step summary")
        return False

    with open(summary_path, "a") as f:
        f.write(content + "\n")
    return True


def main() -> None:
    """Run the data inventory."""
    parser = argparse.ArgumentParser(
        description="Report on distribution data in the repository"
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=DEFAULT_DATA_DIR,
        help="Path to data directory (default: data/)",
    )
    parser.add_argument(
        "--format",
        choices=["text", "markdown", "json"],
        default="text",
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--github-summary",
        action="store_true",
        help="Also write markdown to $GITHUB_STEP_SUMMARY",
    )
    parser.add_argument(
        "--check",
        action="store_true",
        help="Exit with code 1 if no databases found",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    databases = scan_data_directory(args.data_dir)

    if args.format == "json":
        output = format_json(databases)
    elif args.format == "markdown":
        output = format_markdown(databases)
    else:
        output = format_text(databases)

    print(output)

    if args.github_summary:
        md = format_markdown(databases)
        if write_github_summary(md):
            logger.info("Wrote summary to GitHub Actions step summary")

    if args.check and not databases:
        sys.exit(1)


if __name__ == "__main__":
    main()
