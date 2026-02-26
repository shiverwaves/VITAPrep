"""
Weighted sampling utilities for household generation.

Port from HouseholdRNG/generator/sampler.py — that code is stable and tested.
All sampling uses weighted probabilities from PUMS/BLS distributions.
"""

import logging
import random
import re
from typing import List, Optional

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def set_random_seed(seed: Optional[int]) -> None:
    """Set random seed for reproducible generation.

    Args:
        seed: Integer seed, or None to use system entropy.
    """
    if seed is not None:
        random.seed(seed)
        np.random.seed(seed)
        logger.debug("Random seed set to %d", seed)


def parse_dollar_amount(s: str) -> int:
    """Parse a dollar string into an integer.

    Handles formats like "$25K", "$25,000", "$150K", "$0", "25000".
    The "K" suffix multiplies by 1_000.

    Args:
        s: Dollar string to parse.

    Returns:
        Integer dollar amount.

    Raises:
        ValueError: If the string cannot be parsed.
    """
    if not s:
        raise ValueError("Empty dollar string")

    cleaned = s.strip().replace("$", "").replace(",", "").strip()

    if cleaned.upper().endswith("K"):
        numeric_part = cleaned[:-1].strip()
        if not numeric_part:
            raise ValueError(f"Cannot parse dollar amount: {s!r}")
        return int(float(numeric_part) * 1_000)

    return int(float(cleaned))


def sample_from_bracket(bracket_str: str) -> int:
    """Sample a random dollar value from a bracket string.

    Handles formats like "$25,000-$49,999", "$25K-$50K", "$25-50K",
    "Under $10,000", "$100,000+", "$100K+".

    Args:
        bracket_str: Bracket string describing a dollar range.

    Returns:
        Random integer dollar amount within the range.

    Raises:
        ValueError: If the bracket string cannot be parsed.
    """
    s = bracket_str.strip()

    # "Under $X" or "Less than $X" → range is [0, X)
    under_match = re.match(r"(?:under|less\s+than)\s+(.+)", s, re.IGNORECASE)
    if under_match:
        upper = parse_dollar_amount(under_match.group(1))
        return random.randint(0, max(upper - 1, 0))

    # "$X+" or "$X or more" → range is [X, X * 1.5]
    over_match = re.match(r"(.+?)(?:\s*\+|\s+or\s+more)\s*$", s, re.IGNORECASE)
    if over_match:
        lower = parse_dollar_amount(over_match.group(1))
        upper = int(lower * 1.5) if lower > 0 else 10_000
        return random.randint(lower, upper)

    # Range: "$X-$Y" or "$X to $Y"
    range_match = re.split(r"\s*[-–—]\s*|\s+to\s+", s, maxsplit=1)
    if len(range_match) == 2:
        left, right = range_match

        # Handle "$25-50K" where the K only appears on the right side
        right_stripped = right.strip()
        left_stripped = left.strip()
        if right_stripped.upper().endswith("K") and not left_stripped.upper().endswith("K"):
            # Check if left side looks like a bare number without K suffix
            left_clean = left_stripped.replace("$", "").replace(",", "").strip()
            if left_clean.replace(".", "").isdigit():
                left_stripped = left_stripped + "K"

        lower = parse_dollar_amount(left_stripped)
        upper = parse_dollar_amount(right_stripped)
        if upper < lower:
            lower, upper = upper, lower
        return random.randint(lower, upper)

    # Single value fallback
    return parse_dollar_amount(s)


def match_age_bracket(age: int, bracket: str) -> bool:
    """Check if an age falls within a bracket string.

    Handles formats like "25-34", "65+", "Under 18", "85+".

    Args:
        age: Integer age to check.
        bracket: Bracket string like "25-34" or "65+".

    Returns:
        True if the age falls within the bracket.
    """
    b = bracket.strip()

    # "Under X" or "Less than X"
    under_match = re.match(r"(?:under|less\s+than)\s+(\d+)", b, re.IGNORECASE)
    if under_match:
        return age < int(under_match.group(1))

    # "X+" or "X or older" or "X and over"
    over_match = re.match(
        r"(\d+)\s*(?:\+|or\s+older|and\s+over)", b, re.IGNORECASE
    )
    if over_match:
        return age >= int(over_match.group(1))

    # "X-Y" range
    range_match = re.match(r"(\d+)\s*[-–—]\s*(\d+)", b)
    if range_match:
        return int(range_match.group(1)) <= age <= int(range_match.group(2))

    # Single number
    if b.isdigit():
        return age == int(b)

    return False


def get_age_bracket(age: int, brackets: List[str]) -> Optional[str]:
    """Find the bracket that contains the given age.

    Args:
        age: Integer age to look up.
        brackets: List of bracket strings like ["18-24", "25-34", "35-44"].

    Returns:
        The matching bracket string, or None if no match.
    """
    for bracket in brackets:
        if match_age_bracket(age, bracket):
            return bracket
    return None


def sample_age_from_bracket(bracket: str) -> int:
    """Sample a random age from within a bracket.

    Args:
        bracket: Bracket string like "25-34", "65+", "Under 18".

    Returns:
        Random integer age within the bracket bounds.

    Raises:
        ValueError: If the bracket string cannot be parsed.
    """
    b = bracket.strip()

    # "Under X" → [0, X-1]
    under_match = re.match(r"(?:under|less\s+than)\s+(\d+)", b, re.IGNORECASE)
    if under_match:
        upper = int(under_match.group(1))
        return random.randint(0, max(upper - 1, 0))

    # "X+" → [X, X+20]  (cap at reasonable max)
    over_match = re.match(
        r"(\d+)\s*(?:\+|or\s+older|and\s+over)", b, re.IGNORECASE
    )
    if over_match:
        lower = int(over_match.group(1))
        return random.randint(lower, lower + 20)

    # "X-Y" range
    range_match = re.match(r"(\d+)\s*[-–—]\s*(\d+)", b)
    if range_match:
        lower = int(range_match.group(1))
        upper = int(range_match.group(2))
        return random.randint(lower, upper)

    # Single number
    if b.isdigit():
        return int(b)

    raise ValueError(f"Cannot parse age bracket: {bracket!r}")


def weighted_sample(
    df: pd.DataFrame,
    weight_col: str = "weight",
    n: int = 1,
) -> pd.DataFrame:
    """Sample rows from a DataFrame using weighted probabilities.

    Args:
        df: DataFrame to sample from. Must have a numeric weight column.
        weight_col: Name of the column containing weights/counts.
        n: Number of rows to sample.

    Returns:
        DataFrame with n sampled rows (may contain duplicates if replace=True).

    Raises:
        ValueError: If weight column is missing or all weights are zero.
    """
    if weight_col not in df.columns:
        raise ValueError(
            f"Weight column {weight_col!r} not found. "
            f"Available columns: {list(df.columns)}"
        )

    weights = df[weight_col].astype(float)
    total = weights.sum()
    if total <= 0:
        raise ValueError(f"All weights in column {weight_col!r} sum to zero")

    probabilities = weights / total
    indices = np.random.choice(
        df.index, size=n, replace=True, p=probabilities.values
    )
    return df.loc[indices].reset_index(drop=True)
