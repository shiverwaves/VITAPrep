# Extraction & Data Management

How to extract PUMS distribution data and manage what's in the repo.

---

## Overview

The extraction pipeline downloads Census ACS PUMS microdata, processes it into
small SQLite distribution tables, and commits the results to the repo. Raw PUMS
files are large (~400MB per state) and temporary — only the output SQLite
(~1MB) belongs in the repo.

```
Census Bureau → PUMS ZIPs → extract_part1.py → data/distributions_{state}_{year}.sqlite
                  (400MB)                           (~1MB, committed to repo)
```

---

## GitHub Actions Workflows

### Extract Distributions (`extract-distributions.yml`)

**When to use:** Adding a new state, updating to a new PUMS year, or
re-extracting after changes to extraction logic.

**Trigger:** Manual dispatch (Actions → "Extract Distributions" → Run workflow)

**Inputs:**

| Input | Description | Default | Example |
|-------|-------------|---------|---------|
| `states` | Comma-separated state abbreviations | `HI` | `HI,CA,TX` |
| `year` | ACS 5-Year PUMS data year | `2022` | `2022` |
| `parts` | Which extraction parts to run (space-separated) | `1` | `1 2` |
| `create_pr` | Open a PR with the data (vs. just build artifacts) | `true` | `true` |

**What "parts" means:**
- `1` = Part 1: Personal demographics (12 tables — household patterns, race,
  age, relationships, etc.)
- `2` = Part 2: Employment and income (15 tables — not yet implemented, Sprint 9)

Multiple states run in **parallel** as separate matrix jobs. Each state
downloads its own PUMS files, extracts independently, and contributes to
a single PR.

**What happens:**
1. Runner downloads PUMS CSVs from Census Bureau (cached between runs)
2. `extraction/extract_all.py` processes data into distribution tables
3. Validates the output (table counts, row counts)
4. Runs data inventory and writes summary to the job summary
5. Opens a PR with the new/updated SQLite file(s)

**Valid years:** 2013–2023 (5-Year ACS PUMS releases)

**Valid states:** All 50 US states + DC + PR (two-letter abbreviations)

---

### Data Inventory (`data-inventory.yml`)

**When to use:** Quick check of what distribution data is in the repo.

**Trigger:** Manual dispatch, or automatically on pushes that modify
`data/distributions_*.sqlite` files.

**No inputs required.** Just click "Run workflow."

Results appear in the **job summary** (click the completed run in the Actions
UI). Shows a markdown table of every state/year, table counts, row counts,
file sizes, and which extraction parts are complete.

---

## Running Locally

### Extract data for a state

```bash
# Full extraction (download + process + save to data/)
python -m extraction.extract_part1 --state HI --year 2022 --verbose

# Or via the orchestrator (same thing, but supports --parts for future use)
python -m extraction.extract_all --state HI --year 2022 --parts 1
```

Output: `data/distributions_hi_2022.sqlite`

PUMS files are cached in `extraction/pums_cache/` (gitignored) so subsequent
runs for the same state/year skip the download.

### Check what data exists

```bash
# Human-readable table
python scripts/data_inventory.py

# Markdown (same format as the GitHub Actions summary)
python scripts/data_inventory.py --format markdown

# Machine-readable JSON
python scripts/data_inventory.py --format json

# Exit code 1 if no data found (useful in CI)
python scripts/data_inventory.py --check
```

### Download PUMS files without extracting

```python
from extraction.pums_download import download_pums_files
household_zip, person_zip = download_pums_files("HI", 2022)
# Files cached at: extraction/pums_cache/hi_2022/csv_hhi.zip, csv_phi.zip
```

---

## File Layout

```
data/
  distributions_hi_2022.sqlite    ← Committed to repo (Part 1: 12 tables)
  distributions_ca_2022.sqlite    ← One file per state/year
  scenarios.sqlite                ← Runtime data, gitignored
  .gitkeep

extraction/
  pums_download.py                ← Downloads + caches PUMS CSV ZIPs
  extract_part1.py                ← 12 Part 1 extraction functions + CLI
  extract_part2.py                ← Part 2 (Sprint 9, not yet implemented)
  extract_all.py                  ← Orchestrator, called by CI workflow
  pums_cache/                     ← Gitignored, ~400MB per state

scripts/
  data_inventory.py               ← Reports on data/ contents

.github/workflows/
  extract-distributions.yml       ← CI extraction pipeline
  data-inventory.yml              ← Lightweight data summary
```

---

## Part 1 Distribution Tables (12)

These tables are extracted from PUMS and used by the household generator
(Sprint 3+) to produce realistic demographics.

| Table | Rows (HI) | Purpose |
|-------|-----------|---------|
| `household_patterns` | ~8 | Household type distribution (married, single, etc.) |
| `children_by_parent_age` | ~30 | Child count by parent's age bracket |
| `child_age_distributions` | ~70 | Child ages by relationship type |
| `adult_child_ages` | ~50 | Adult children (18+) still in household |
| `stepchild_patterns` | ~15 | Stepchild frequency and composition |
| `multigenerational_patterns` | ~20 | 3+ generation household structures |
| `unmarried_partner_patterns` | ~25 | Cohabiting couple demographics |
| `race_distribution` | ~9 | Overall race distribution (weighted) |
| `race_by_age` | ~60 | Race by age bracket |
| `hispanic_origin_by_age` | ~14 | Hispanic origin by age bracket |
| `spousal_age_gaps` | ~50 | Age difference between spouses |
| `couple_sex_patterns` | ~10 | Same-sex vs opposite-sex couples |

Row counts are approximate and vary by state.
