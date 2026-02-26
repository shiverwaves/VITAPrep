# Build Plan — Step-by-Step Implementation Guide

This document is designed to be followed sequentially. Each sprint produces
working, testable output. Do not skip ahead — later sprints depend on earlier ones.

---

## Sprint 1: Data Models + Sampling Utilities

**Goal**: Define all data structures. Everything else depends on these.

### Step 1.1: `generator/models.py`
Create the core data models. These are Python dataclasses (not Pydantic).

**Person** — represents one individual in a household:
- Statistical fields: person_id, relationship, age, sex, race, hispanic_origin
- PII fields (empty until pii.py populates them): legal_first_name, legal_middle_name,
  legal_last_name, suffix, ssn, dob, phone, email
- ID document fields: id_type, id_state, id_number, id_expiry, id_address (may differ
  from household address for "just moved" scenarios)
- Employment fields (empty until Part 2): employment_status, education, occupation_code,
  occupation_title
- Income fields (empty until Part 2): wage_income, self_employment_income,
  social_security_income, retirement_income, interest_income, dividend_income, other_income
- Expense fields (empty until Part 3): student_loan_interest, educator_expenses, ira_contributions
- Dependent fields: is_dependent, can_be_claimed, months_in_home
- Helper methods: total_income(), is_adult(), is_child(), is_senior(), to_dict()

**Address** — physical address:
- street, apt (optional), city, state, zip_code

**Household** — a group of people at one address:
- household_id, state, year, pattern, members (List[Person]), address (Address)
- Pattern metadata: expected_adults, expected_children_range, expected_complexity
- Household-level expenses (Part 3): property_taxes, mortgage_interest, etc.
- Helper methods: get_adults(), get_children(), get_householder(), get_spouse(),
  total_household_income(), filing_status (derived property)

**FilingUnit** — a tax return within a household:
- filing_unit_id, household_id, filing_status (enum)
- primary_filer, spouse_filer (optional), dependents list
- Tax fields: adjusted_gross_income, taxable_income, total_tax, refund_or_owed

**Enums**: FilingStatus, EmploymentStatus, RelationshipType, Race, EducationLevel

**PATTERN_METADATA** dict: maps pattern names to expected adults, children range,
complexity, description, and default relationships.

Reference: `HouseholdRNG/generator/models.py` — port and extend with PII fields.

### Step 1.2: `generator/sampler.py`
Port directly from `HouseholdRNG/generator/sampler.py`. This is stable, well-tested code.

Functions needed:
- `weighted_sample(df, weight_col, n)` — sample rows by weight
- `sample_from_bracket(bracket_str)` — random value from "$25-50K" style strings
- `parse_dollar_amount(s)` — "$25K" → 25000
- `get_age_bracket(age, brackets)` — find matching bracket
- `match_age_bracket(age, bracket)` — check if age fits "25-34" style string
- `sample_age_from_bracket(bracket)` — random age within bracket
- `set_random_seed(seed)` — reproducibility

### Step 1.3: Tests
- `tests/test_models.py` — create Person, Household, verify helpers
- `tests/test_sampler.py` — test weighted sampling, bracket parsing

**Checkpoint**: `pytest tests/` passes. Models can be instantiated and serialized.

---

## Sprint 2: Database Layer + Part 1 Extraction

**Goal**: Get PUMS data into SQLite so generators can consume it.

### Step 2.1: `generator/db.py`
SQLAlchemy-based distribution table loader.

- `DistributionLoader` class with `__init__(connection_string=None)`
- Auto-detect SQLite files in `data/` directory if no connection string given
- `load_tables(state, year, table_list)` — load specific tables as DataFrames
- `load_part1_tables(state, year)` — convenience: loads only Part 1's 12 tables
- `load_part2_tables(state, year)` — loads Part 2's tables (for later)
- `load_all_tables(state, year)` — loads everything
- `list_available_states()` — scan SQLite for available state/year combos
- Supports both SQLite and PostgreSQL via SQLAlchemy (same interface)

Part 1 tables (12):
```
household_patterns, children_by_parent_age, child_age_distributions,
adult_child_ages, stepchild_patterns, multigenerational_patterns,
unmarried_partner_patterns, race_distribution, race_by_age,
hispanic_origin_by_age, spousal_age_gaps, couple_sex_patterns
```

Part 2 tables (14):
```
employment_by_age, education_by_age, disability_by_age,
social_security, retirement_income, interest_and_dividend_income,
other_income_by_employment_status, public_assistance_income,
homeownership_rates, property_taxes, mortgage_interest,
bls_occupation_wages, education_occupation_probabilities,
age_income_adjustments, occupation_self_employment_probability
```

Reference: `HouseholdRNG/generator/database.py` — simplify, add SQLite auto-detect.

### Step 2.2: `extraction/pums_download.py`
Shared PUMS file downloader with local caching.

- `download_pums_files(state, year)` → returns paths to cached CSV ZIPs
- `load_pums_data(household_zip, person_zip)` → returns (households_df, persons_df)
- Cache directory: `extraction/pums_cache/` (gitignored)
- Download from: `https://www2.census.gov/programs-surveys/acs/data/pums/{year}/5-Year/`

Reference: `HouseholdRNG/scripts/extract_pums.py` lines 72-152 (download + load functions).

### Step 2.3: `extraction/extract_part1.py`
Extract the 12 Part 1 distribution tables from PUMS data → SQLite.

Functions to port from `HouseholdRNG/scripts/extract_pums.py`:
- `extract_household_patterns()` (line 155)
- `extract_children_by_parent_age()` (line 258)
- `extract_child_age_distributions()` (line 298)
- `extract_adult_child_ages()` (line 803)
- `extract_stepchild_patterns()` (line 853)
- `extract_multigenerational_patterns()` (line 928)
- `extract_unmarried_partner_patterns()` (line 1007)

New extraction functions (were in extract_pums.py but categorized as Part 1):
- `extract_race_distribution()`
- `extract_race_by_age()`
- `extract_hispanic_origin_by_age()`
- `extract_spousal_age_gaps()`
- `extract_couple_sex_patterns()`

Output: `data/distributions_{state}_{year}.sqlite`

CLI: `python -m extraction.extract_part1 --state HI --year 2022`

### Step 2.4: Tests
- `tests/test_db.py` — load tables from SQLite, verify shapes

**Checkpoint**: SQLite file exists for HI with 12 tables. `db.py` can load them.

---

## Sprint 3: Part 1 Generators (Demographics + Children)

**Goal**: Generate a household with members (age, sex, race, relationships) but no PII yet.

### Step 3.1: `generator/demographics.py`
Generates adult household members with demographic attributes only.

Port from `HouseholdRNG/generator/adult_generator.py` but EXCLUDE:
- `_sample_employment_status()` → moves to `employment.py` (Sprint 6)
- `_sample_education()` → moves to `employment.py` (Sprint 6)
- `_sample_disability()` → moves to `employment.py` (Sprint 6)
- `_sample_occupation()` → moves to `employment.py` (Sprint 6)

KEEP:
- `generate_adults(household)` → returns list of Person with age, sex, race, relationship
- `_determine_adult_count(pattern, metadata)`
- `_assign_relationships(pattern, num_adults, household)`
- `_generate_single_adult(relationship, household, existing_adults)`
- `_sample_age()` and all age-related helpers (householder, spouse, partner, parent)
- `_sample_sex()`
- `_sample_race(age)`
- `_sample_hispanic_origin(age)`

Required tables: household_patterns, race_distribution, race_by_age,
hispanic_origin_by_age, spousal_age_gaps, couple_sex_patterns

### Step 3.2: `generator/children.py`
Port from `HouseholdRNG/generator/child_generator.py` mostly as-is.

- `generate_children(household)` → returns list of child Person objects
- Child ages based on parent ages and distributions
- Relationship types: biological_child, adopted_child, stepchild, grandchild
- Race inherited from parents

Required tables: children_by_parent_age, child_age_distributions,
adult_child_ages, stepchild_patterns

### Step 3.3: `generator/pipeline.py`
Orchestrates generation by VITA section.

```python
class HouseholdGenerator:
    def __init__(self, state, year, connection_string=None):
        self.db = DistributionLoader(connection_string)
        self.distributions = self.db.load_part1_tables(state, year)
        self.demographics = DemographicsGenerator(self.distributions)
        self.children = ChildGenerator(self.distributions)

    def generate_part1(self, pattern=None, seed=None):
        """Generate household with structure + demographics only."""
        household = self._select_pattern(pattern)
        adults = self.demographics.generate_adults(household)
        household.members = adults
        children = self.children.generate_children(household)
        household.members.extend(children)
        return household
```

### Step 3.4: Tests
- `tests/test_demographics.py` — generate adults, verify age/sex/race populated
- `tests/test_children.py` — generate children for various patterns
- `tests/test_pipeline.py` — end-to-end Part 1 generation

**Checkpoint**: `python -c "from generator.pipeline import HouseholdGenerator; g = HouseholdGenerator('HI', 2022); h = g.generate_part1(); print(h.to_dict())"` works.

---

## Sprint 4: PII Generator

**Goal**: Overlay realistic names, SSNs, DOBs, and addresses onto generated households.

### Step 4.1: `generator/pii.py`
Takes a Household from Sprint 3 and populates PII fields on each Person.

**Name generation:**
- Use Faker with locale hints based on Person.race and hispanic_origin
- Spouse may have different last name (maiden name scenarios, ~30% probability)
- Children share a parent's last name (biological) or may differ (stepchildren)
- Blended families have mixed last names
- Occasional suffixes (Jr., III) when father/son share first name

**SSN generation:**
- Always 9XX-XX-XXXX (IRS test/advertising range, never issued to real people)
- Unique within household
- Format: "9{2 random digits}-{2 random digits}-{4 random digits}"

**DOB generation:**
- Calculate from Person.age and tax_year
- Random month and day within the valid year
- Edge cases: born on Dec 31 (affects tax year age), born on Jan 1

**Address generation:**
- One household address shared by all members
- Generated with Faker, state matching Household.state
- ID address usually matches household address
- ~15% chance of "just moved" scenario (ID has old address)

**ID document details:**
- id_type: "drivers_license" for adults, none for children
- id_state: matches household state
- id_number: state-specific format (see docs/DATA_DICTIONARY.md)
- id_expiry: 4-8 years from issue, may be expired (~10% chance)

**Phone and email:**
- One phone per adult (Faker)
- Email for primary filer (Faker)

```python
class PIIGenerator:
    def overlay(self, household: Household, tax_year: int = 2024) -> Household:
        """Populate PII fields on all persons in household. Modifies in place."""
```

### Step 4.2: Tests
- `tests/test_pii.py` — verify names generated, SSNs in 9XX range, DOBs match ages,
  addresses consistent within household, last name logic for blended families

**Checkpoint**: Generate household → overlay PII → print full profile with names/SSNs/DOBs.

---

## Sprint 5: Document Rendering + Templates

**Goal**: Produce SSN card images, driver's license images, blank/filled intake forms.

### Step 5.1: `training/templates/base.css`
Shared CSS: watermark overlay, font stacks (monospace for SSN/ID numbers),
print-friendly sizing.

### Step 5.2: `training/templates/ssn_card.html`
Jinja2 template for Social Security card mock-up.
- Fields: legal name (first middle last), SSN
- "SAMPLE — FOR TRAINING USE ONLY" watermark
- Card dimensions: standard SSN card ratio (~3.375" × 2.125")

### Step 5.3: `training/templates/drivers_license.html`
Jinja2 template for state driver's license mock-up.
- Fields: name, DOB, address, sex, ID number, expiry, photo placeholder
- State parameter controls header/layout (start with generic, add HI-specific later)
- Photo: placeholder silhouette for MVP, generated face for later
- Watermark

### Step 5.4: `training/templates/form_13614c_p1.html`
Form 13614-C Part I as an HTML form.
- Two modes: blank (student fills in) or pre-filled (student verifies)
- Fields match IRS form layout (see docs/VITA_FORM_FIELDS.md)
- Interactive version for web UI (input fields)
- Static version for PDF export (text in field positions)

### Step 5.5: `training/document_renderer.py`
Renders templates to images (PNG) or PDF.

```python
class DocumentRenderer:
    def render_ssn_card(self, person: Person) -> Path:
    def render_drivers_license(self, person: Person) -> Path:
    def render_intake_form(self, household: Household, prefilled: bool = False) -> Path:
    def render_1040_header(self, household: Household) -> Path:   # Future
    def render_w2(self, person: Person) -> Path:                   # Future
```

Uses Jinja2 for template rendering, WeasyPrint or Playwright for HTML → image/PDF.

### Step 5.6: Tests
- `tests/test_document_renderer.py` — render each doc type, verify files created

**Checkpoint**: CLI generates household → overlay PII → render SSN card + DL as PNG files.

---

## Sprint 6: Error Injection + Grading

**Goal**: Seed discrepancies and grade student responses.

### Step 6.1: `training/error_injector.py`
Modifies rendered documents or pre-filled intake to introduce errors.

Error categories for Part 1:
- **name**: middle name missing, maiden vs married, suffix wrong, nickname vs legal
- **ssn**: transposed digits, one digit off, dependent SSN reuses filer's
- **address**: old address on ID, apt number missing, abbreviation mismatch
- **dob**: month/day swapped, year off by 1, makes dependent age-ineligible
- **filing_status**: wrong status selected given household composition
- **dependent**: child >19 claimed, <6 months residency, relationship wrong
- **expiration**: expired driver's license

```python
class ErrorInjector:
    def inject(self, profile: Household, difficulty: str, error_count: int)
        -> Tuple[Household, List[InjectedError]]:
        """Returns modified household + manifest of what was changed."""
```

~15% of scenarios should be error-free (tests student confidence in clean docs).

### Step 6.2: `training/grader.py`
Compares student submission to ground truth.

```python
class Grader:
    def grade_intake(self, submission: dict, ground_truth: Household) -> GradingResult:
        """Mode 1: Student filled blank intake from source docs."""

    def grade_verification(self, flagged_errors: List[dict],
                          actual_errors: List[InjectedError]) -> GradingResult:
        """Mode 2: Student identified discrepancies."""
```

GradingResult includes: score, max_score, correct_flags, missed_flags,
false_flags, accuracy, narrative feedback, field-level feedback.

### Step 6.3: `training/exercise_engine.py`
Orchestrates full scenario creation.

```python
class ExerciseEngine:
    def generate_scenario(self, state, mode, difficulty, ...) -> Scenario:
        """Full pipeline: generate → PII → render docs → inject errors → package."""
```

### Step 6.4: `training/scenario_store.py`
SQLite CRUD for persisting scenarios, submissions, and grades.

### Step 6.5: Tests
- `tests/test_error_injector.py`
- `tests/test_grader.py`

**Checkpoint**: Generate scenario with errors → grade a mock submission → get feedback.

---

## Sprint 7: API

**Goal**: Serve scenarios via REST endpoints.

### Step 7.1: `api/main.py`
FastAPI app setup, CORS, lifespan (initialize generator + scenario store).

### Step 7.2: `api/routes/scenarios.py`
- `POST /api/v1/scenarios` — generate new scenario
- `GET /api/v1/scenarios/{id}` — get scenario metadata + document URLs
- `GET /api/v1/scenarios/{id}/documents/{filename}` — serve document image
- `POST /api/v1/scenarios/{id}/submit` — submit answers for grading
- `GET /api/v1/scenarios/{id}/answer-key` — get answer key (after submit)

### Step 7.3: `api/routes/config.py`
- `GET /api/v1/config/states` — available states
- `GET /api/v1/config/patterns/{state}` — household patterns for a state

### Step 7.4: `api/routes/progress.py`
- `GET /api/v1/progress` — student history, scores over time

### Step 7.5: `cli.py`
Command-line interface for generating scenarios without the API.

```bash
python cli.py generate --mode intake --difficulty easy --state HI
python cli.py generate --mode verify --difficulty medium --errors 3
python cli.py batch --count 10 --output ./packets/
```

**Checkpoint**: API running, can generate scenario via curl, view documents in browser.

---

## Sprint 8: Web UI (Phase 2)

**Goal**: Interactive browser interface.

- Document viewer (left panel): SSN cards, DL images
- Form (right panel): editable 13614-C Part I
- Grade button → inline feedback
- Progress dashboard

Tech: React, HTMX, or plain HTML + vanilla JS — decide when you get here.

---

## Sprint 9: Expand to Part 2 — Income (Phase 2)

### Step 9.1: `extraction/extract_part2.py`
Port income/employment extraction functions from HouseholdRNG.

### Step 9.2: `generator/employment.py`
Port employment/education/occupation logic from HouseholdRNG's adult_generator.

### Step 9.3: `generator/income.py`
Port from HouseholdRNG's income_generator.py mostly as-is.

### Step 9.4: W-2 template + rendering
### Step 9.5: Part 2 exercises (verify income on intake sheet)

Each future VITA section follows this same pattern:
extract → generate → render → exercise → grade.
