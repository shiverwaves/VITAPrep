"""
Convenience runner — extracts all distribution tables.

Runs all available extraction modules (Part 1, and Part 2 when implemented)
for a given state and year. This is the script called by the GitHub Actions
extraction workflow.

Usage:
    python -m extraction.extract_all --state HI --year 2022
    python -m extraction.extract_all --state HI --year 2022 --parts 1
    python -m extraction.extract_all --state HI --year 2022 --parts 1 2
"""

import argparse
import logging
import sys
from pathlib import Path
from typing import List, Optional

logger = logging.getLogger(__name__)


def run_extraction(
    state: str,
    year: int,
    parts: Optional[List[int]] = None,
    output: Optional[Path] = None,
) -> Path:
    """Run extraction for specified parts.

    Args:
        state: Two-letter state abbreviation.
        year: ACS 5-Year data year.
        parts: List of part numbers to extract (default: all available).
        output: Optional output SQLite path.

    Returns:
        Path to the created/updated SQLite file.

    Raises:
        ValueError: If an unsupported part number is requested.
    """
    if parts is None:
        parts = [1, 2]

    output_path = None

    for part in sorted(parts):
        if part == 1:
            from .extract_part1 import extract_all_part1
            output_path = extract_all_part1(state, year, output)
        elif part == 2:
            from .extract_part2 import extract_all_part2
            output_path = extract_all_part2(state, year, output_path or output)
        else:
            raise ValueError(f"Unknown extraction part: {part}. Valid: 1, 2")

    if output_path is None:
        raise RuntimeError("No extraction parts were run successfully")

    return output_path


def main() -> None:
    """CLI entry point for running all extractions."""
    parser = argparse.ArgumentParser(
        description="Extract distribution tables from PUMS data"
    )
    parser.add_argument(
        "--state",
        required=True,
        help="Two-letter state abbreviation (e.g., HI, CA)",
    )
    parser.add_argument(
        "--year",
        type=int,
        required=True,
        help="ACS 5-Year data year (e.g., 2022)",
    )
    parser.add_argument(
        "--parts",
        type=int,
        nargs="+",
        default=None,
        help="Which parts to extract (default: all available). E.g., --parts 1 2",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output SQLite path (default: data/distributions_{state}_{year}.sqlite)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    try:
        output = run_extraction(args.state, args.year, args.parts, args.output)
        print(f"\nExtraction complete: {output}")
    except Exception:
        logger.exception("Extraction failed")
        sys.exit(1)


if __name__ == "__main__":
    main()
