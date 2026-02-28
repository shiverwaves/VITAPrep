#!/usr/bin/env python3
"""Generate a sample household with PII and print as JSON.

This is the script invoked by the Generate Household workflow to show
what the pipeline actually produces at runtime.

Uses the real SQLite distribution data shipped in data/ when available.
Falls back to the HouseholdGenerator pipeline which handles loading.

Usage:
    python scripts/generate_sample.py                          # random pattern
    python scripts/generate_sample.py --pattern single_parent  # specific pattern
    python scripts/generate_sample.py --seed 42 --format json  # reproducible
    python scripts/generate_sample.py --render --output-dir /tmp/docs  # render docs
"""

import argparse
import json
import logging
import sys
from pathlib import Path

# Ensure repo root is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from generator.models import PATTERN_METADATA
from generator.pipeline import HouseholdGenerator
from generator.sampler import set_random_seed

logger = logging.getLogger(__name__)


def generate_household(pattern=None, seed=None, state="HI", year=2022):
    """Generate a single household with demographics + PII.

    Args:
        pattern: Household pattern name, or None for random.
        seed: Random seed for reproducibility.
        state: Two-letter state code (must have SQLite data in data/).
        year: PUMS data year.

    Returns:
        Household with all fields populated.
    """
    if seed is not None:
        set_random_seed(seed)

    generator = HouseholdGenerator(state, year)
    household = generator.generate_with_pii(pattern=pattern, seed=seed)
    return household


def render_documents(household, output_dir):
    """Render SSN cards and photo IDs for all household members.

    Args:
        household: Household with PII populated.
        output_dir: Directory to write rendered PNG files.

    Returns:
        Dict mapping document labels to file paths.
    """
    from training.document_renderer import DocumentRenderer

    renderer = DocumentRenderer(output_dir=output_dir)
    paths = renderer.render_household_documents(household)
    return paths


def main():
    parser = argparse.ArgumentParser(
        description="Generate a sample household with PII"
    )
    parser.add_argument(
        "--pattern",
        choices=list(PATTERN_METADATA.keys()),
        default=None,
        help="Household pattern (default: random)",
    )
    parser.add_argument(
        "--seed",
        type=int,
        default=None,
        help="Random seed for reproducibility",
    )
    parser.add_argument(
        "--state",
        default="HI",
        help="State code (default: HI)",
    )
    parser.add_argument(
        "--year",
        type=int,
        default=2022,
        help="PUMS data year (default: 2022)",
    )
    parser.add_argument(
        "--format",
        choices=["json", "text"],
        default="json",
        help="Output format (default: json)",
    )
    parser.add_argument(
        "--render",
        action="store_true",
        help="Render SSN cards and photo IDs as PDF files",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="Directory for rendered documents (default: /tmp/vita_docs)",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.WARNING,
        format="%(levelname)s: %(message)s",
    )

    household = generate_household(
        pattern=args.pattern,
        seed=args.seed,
        state=args.state,
        year=args.year,
    )
    data = household.to_dict()

    if args.format == "json":
        print(json.dumps(data, indent=2, default=str))
    else:
        print(f"Pattern: {data['pattern']}")
        print(f"Adults: {data['adult_count']}, Children: {data['child_count']}")
        print(f"Filing status: {data['filing_status']}")
        print(f"Address: {household.address.one_line()}")
        print()
        for i, m in enumerate(data["members"], 1):
            name = f"{m['legal_first_name']} {m['legal_last_name']}"
            if m.get("suffix"):
                name += f" {m['suffix']}"
            print(f"  {i}. {name} ({m['relationship']}, {m['age']}{m['sex']}) SSN: {m['ssn']} DOB: {m['dob']}")

    if args.render:
        output_dir = args.output_dir or "/tmp/vita_docs"
        print(f"\nRendering documents to {output_dir}/ ...", file=sys.stderr)
        paths = render_documents(household, output_dir)
        print(f"Rendered {len(paths)} documents:", file=sys.stderr)
        for label, path in sorted(paths.items()):
            print(f"  {label}: {path}", file=sys.stderr)


if __name__ == "__main__":
    main()
