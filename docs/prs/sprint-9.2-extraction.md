# Sprint 9.2: Part 2 PUMS extraction — employment and income distributions

## Summary

- **Implement `extraction/extract_part2.py`** with 12 extraction functions that produce income/employment distribution tables from Census PUMS person-level data
- **Update `generator/db.py`** — align `PART2_TABLES` list with actual extracted table names
- **Enable Part 2 in `extraction/extract_all.py`** — `--parts 2` now works, default extracts both parts
- **Add 25 new tests** in `tests/test_extract_part2.py` using synthetic PUMS-like DataFrames

## Tables extracted

| # | Table | PUMS Fields | Purpose |
|---|-------|-------------|---------|
| 1 | `employment_by_age` | ESR × AGEP | Employment rate by age bracket |
| 2 | `education_by_age` | SCHL × AGEP | Education level distribution by age |
| 3 | `disability_by_age` | DIS × AGEP | Disability rate by age |
| 4 | `social_security` | SSP + SSIP × AGEP | SS income distribution + receipt rate |
| 5 | `retirement_income` | RETP × AGEP | Retirement income distribution + receipt rate |
| 6 | `interest_and_dividend_income` | INTP × AGEP | Investment income distribution + receipt rate |
| 7 | `other_income_by_employment_status` | OIP × ESR | Other income by employment status |
| 8 | `public_assistance_income` | PAP × AGEP | PA income distribution + receipt rate |
| 9 | `occupation_wages` | WAGP × OCCP | Wage percentiles (p25/median/p75/mean) by 23 major occupation groups |
| 10 | `education_occupation_probabilities` | SCHL × OCCP | Education → occupation cross-tab for sampling |
| 11 | `age_income_adjustments` | WAGP × AGEP | Age-based wage adjustment factors (early vs mid vs late career) |
| 12 | `occupation_self_employment_rates` | COW × OCCP | Self-employment probability by occupation |

## Design decisions

| Decision | Rationale |
|----------|-----------|
| Income brackets use sampler-compatible format | `"$10K-$20K"`, `"Under $10K"`, `"$150K+"` work directly with `sampler.sample_from_bracket()` |
| Income receipt proportions included | Each income table includes `has_*_proportion` so the generator knows P(income type \| age) |
| Occupation wages derived from PUMS, not BLS | Weighted percentiles from WAGP × OCCP as a Census-based proxy. BLS OEWS data can be substituted later for more granularity. |
| 23 major occupation groups | PUMS OCCP codes mapped to SOC-level groups (management, healthcare, sales, etc.) for manageable table size |
| Appends to existing SQLite | Part 2 tables are added to the same `distributions_{state}_{year}.sqlite` created by Part 1 |

## Changes

| File | Change |
|------|--------|
| `extraction/extract_part2.py` | +590 lines — 12 extraction functions + CLI + helpers |
| `generator/db.py` | Aligned `PART2_TABLES` with actual table names (removed 3 deferred housing tables, renamed 2) |
| `extraction/extract_all.py` | Enabled Part 2 extraction (was stubbed) |
| `tests/test_extract_part2.py` | +240 lines — 25 tests covering all functions |

## Usage

```bash
# Extract Part 2 tables for Hawaii 2022
python -m extraction.extract_part2 --state HI --year 2022

# Extract both Part 1 and Part 2
python -m extraction.extract_all --state HI --year 2022 --parts 1 2
```

## Test plan

- [x] 25 new tests pass — all extraction functions verified with synthetic PUMS data
- [x] All 460 tests pass (435 existing + 25 new) — no regressions
- [x] Module imports cleanly, CLI entry point works
- [ ] End-to-end extraction against real PUMS data — requires `python -m extraction.extract_part2 --state HI --year 2022` (manual, needs PUMS download)
