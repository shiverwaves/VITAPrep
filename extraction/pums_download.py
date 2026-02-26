"""
Shared PUMS/BLS file downloader with local caching.

Downloads Census PUMS CSV files and caches locally to avoid re-downloading.
Cache directory: extraction/pums_cache/ (gitignored)

Files downloaded per state/year:
- csv_h{state}.zip  (household records)
- csv_p{state}.zip  (person records)

Source: https://www2.census.gov/programs-surveys/acs/data/pums/{year}/5-Year/

Reference: HouseholdRNG/scripts/extract_pums.py lines 72-152
"""

import logging
import zipfile
from pathlib import Path
from typing import Tuple

import pandas as pd
import requests

logger = logging.getLogger(__name__)

# Census PUMS download URL template
# 5-Year ACS PUMS files (most recent: 2022, released Dec 2023)
PUMS_BASE_URL = (
    "https://www2.census.gov/programs-surveys/acs/data/pums/{year}/5-Year/"
)

# File naming conventions (Census uses lowercase state abbreviations)
HOUSEHOLD_ZIP_TEMPLATE = "csv_h{state}.zip"
PERSON_ZIP_TEMPLATE = "csv_p{state}.zip"

# Cache directory (relative to this file's parent, i.e., extraction/)
CACHE_DIR = Path(__file__).resolve().parent / "pums_cache"

# State abbreviation → FIPS code (needed for some Census endpoints)
STATE_FIPS = {
    "AL": "01", "AK": "02", "AZ": "04", "AR": "05", "CA": "06",
    "CO": "08", "CT": "09", "DE": "10", "DC": "11", "FL": "12",
    "GA": "13", "HI": "15", "ID": "16", "IL": "17", "IN": "18",
    "IA": "19", "KS": "20", "KY": "21", "LA": "22", "ME": "23",
    "MD": "24", "MA": "25", "MI": "26", "MN": "27", "MS": "28",
    "MO": "29", "MT": "30", "NE": "31", "NV": "32", "NH": "33",
    "NJ": "34", "NM": "35", "NY": "36", "NC": "37", "ND": "38",
    "OH": "39", "OK": "40", "OR": "41", "PA": "42", "RI": "44",
    "SC": "45", "SD": "46", "TN": "47", "TX": "48", "UT": "49",
    "VT": "50", "VA": "51", "WA": "53", "WV": "54", "WI": "55",
    "WY": "56", "PR": "72",
}

# Valid ACS 5-Year PUMS years
VALID_YEARS = list(range(2013, 2024))  # 2013-2023 (update as Census releases new data)


def validate_inputs(state: str, year: int) -> str:
    """Validate state abbreviation and year.

    Args:
        state: Two-letter state abbreviation (case-insensitive).
        year: ACS 5-Year PUMS data year.

    Returns:
        Lowercase state abbreviation.

    Raises:
        ValueError: If state or year is invalid.
    """
    state_upper = state.upper()
    if state_upper not in STATE_FIPS:
        raise ValueError(
            f"Invalid state: {state!r}. Must be a two-letter US state abbreviation."
        )
    if year not in VALID_YEARS:
        raise ValueError(
            f"Invalid year: {year}. Valid range: {VALID_YEARS[0]}-{VALID_YEARS[-1]}"
        )
    return state.lower()


def get_cache_dir(state: str, year: int) -> Path:
    """Get the cache directory for a specific state/year.

    Args:
        state: Two-letter state abbreviation.
        year: ACS data year.

    Returns:
        Path to the cache subdirectory.
    """
    cache_path = CACHE_DIR / f"{state.lower()}_{year}"
    cache_path.mkdir(parents=True, exist_ok=True)
    return cache_path


def download_file(url: str, dest: Path, chunk_size: int = 8192) -> Path:
    """Download a file with progress logging.

    Args:
        url: URL to download.
        dest: Destination file path.
        chunk_size: Download chunk size in bytes.

    Returns:
        Path to the downloaded file.

    Raises:
        requests.HTTPError: If the download fails.
    """
    if dest.exists():
        logger.info("Using cached file: %s", dest.name)
        return dest

    logger.info("Downloading %s", url)
    response = requests.get(url, stream=True, timeout=300)
    response.raise_for_status()

    total_size = int(response.headers.get("content-length", 0))
    downloaded = 0

    with open(dest, "wb") as f:
        for chunk in response.iter_content(chunk_size=chunk_size):
            f.write(chunk)
            downloaded += len(chunk)
            if total_size > 0 and downloaded % (chunk_size * 100) == 0:
                pct = downloaded / total_size * 100
                logger.info(
                    "  Progress: %.1f%% (%d / %d MB)",
                    pct,
                    downloaded // (1024 * 1024),
                    total_size // (1024 * 1024),
                )

    logger.info("Downloaded %s (%.1f MB)", dest.name, dest.stat().st_size / (1024 * 1024))
    return dest


def download_pums_files(state: str, year: int) -> Tuple[Path, Path]:
    """Download PUMS household and person CSV ZIPs for a state/year.

    Downloads from the Census Bureau ACS PUMS FTP site. Files are cached
    locally so subsequent runs skip the download.

    Args:
        state: Two-letter state abbreviation (e.g., 'HI', 'CA').
        year: ACS 5-Year data year (e.g., 2022).

    Returns:
        Tuple of (household_zip_path, person_zip_path).

    Raises:
        ValueError: If state or year is invalid.
        requests.HTTPError: If download fails (404, 500, etc.).
    """
    state_lower = validate_inputs(state, year)
    cache_dir = get_cache_dir(state_lower, year)

    base_url = PUMS_BASE_URL.format(year=year)
    household_filename = HOUSEHOLD_ZIP_TEMPLATE.format(state=state_lower)
    person_filename = PERSON_ZIP_TEMPLATE.format(state=state_lower)

    household_zip = download_file(
        url=base_url + household_filename,
        dest=cache_dir / household_filename,
    )
    person_zip = download_file(
        url=base_url + person_filename,
        dest=cache_dir / person_filename,
    )

    return household_zip, person_zip


def load_pums_data(
    household_zip: Path,
    person_zip: Path,
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Load PUMS CSVs from downloaded ZIP files.

    Reads the CSV inside each ZIP into a pandas DataFrame. Only loads
    columns needed for extraction to reduce memory usage.

    Args:
        household_zip: Path to the household records ZIP.
        person_zip: Path to the person records ZIP.

    Returns:
        Tuple of (households_df, persons_df).
    """
    # Household columns needed for Part 1 + Part 2
    household_cols = [
        "SERIALNO",  # Household serial number (join key)
        "WGTP",      # Household weight
        "NP",        # Number of persons
        "TYPE",      # Household type (1=housing unit, 2=GQ)
        "TEN",       # Tenure (own/rent)
        "TAXAMT",    # Property tax amount
        "HINCP",     # Household income
    ]

    # Person columns needed for Part 1 + Part 2
    person_cols = [
        "SERIALNO",  # Household serial number (join key)
        "SPORDER",   # Person number within household
        "PWGTP",     # Person weight
        "AGEP",      # Age
        "SEX",       # Sex (1=Male, 2=Female)
        "RAC1P",     # Race (recoded, single value)
        "HISP",      # Hispanic origin
        "RELSHIPP",  # Relationship to householder
        "MAR",       # Marital status
        "SCHL",      # Educational attainment
        "ESR",       # Employment status recode
        "DIS",       # Disability recode
        "OCCP",      # Occupation code
        "COW",       # Class of worker
        "WAGP",      # Wages/salary income
        "SEMP",      # Self-employment income
        "SSP",       # Social Security income
        "SSIP",      # Supplemental Security Income
        "RETP",      # Retirement income
        "INTP",      # Interest income
        "OIP",       # Other income
        "PAP",       # Public assistance income
    ]

    logger.info("Loading household data from %s", household_zip.name)
    with zipfile.ZipFile(household_zip) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV found in {household_zip}")
        households_df = pd.read_csv(
            zf.open(csv_names[0]),
            usecols=lambda c: c in household_cols,
            dtype={"SERIALNO": str},
        )
    logger.info(
        "Loaded %d household records (%d columns)",
        len(households_df),
        len(households_df.columns),
    )

    logger.info("Loading person data from %s", person_zip.name)
    with zipfile.ZipFile(person_zip) as zf:
        csv_names = [n for n in zf.namelist() if n.lower().endswith(".csv")]
        if not csv_names:
            raise FileNotFoundError(f"No CSV found in {person_zip}")
        persons_df = pd.read_csv(
            zf.open(csv_names[0]),
            usecols=lambda c: c in person_cols,
            dtype={"SERIALNO": str},
        )
    logger.info(
        "Loaded %d person records (%d columns)",
        len(persons_df),
        len(persons_df.columns),
    )

    return households_df, persons_df
