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

## Sprint 9: Expand to Part 2 — Income

**Goal**: Generate realistic employment/income data and render the source
documents (W-2, 1099 family) that students use to verify income on the intake
form.

Each income type maps to a specific IRS source form:

| Person Field | Source Form | Description |
|---|---|---|
| `wage_income` | **W-2** | Wages, salaries, tips from employers |
| `interest_income` | **1099-INT** | Bank/savings interest |
| `dividend_income` | **1099-DIV** | Stock/mutual fund dividends |
| `retirement_income` | **1099-R** | Pensions, IRA distributions, annuities |
| `social_security_income` | **SSA-1099** | Social Security benefits |
| `self_employment_income` | **1099-NEC** | Freelance/gig/contract work |
| `other_income` | **1099-G, 1099-MISC** | Unemployment, misc income |

The sprint is divided into foundation work, per-form tasks, and integration.

---

### Foundation (must land before any form task)

### Step 9.1: Model extensions — `generator/models.py`

Extend Person and add new dataclasses for income documents:

**Employer** dataclass:
- employer_name, employer_ein, employer_address (Address)
- Used by W-2 and 1099-NEC

**W2** dataclass (one per job):
- employer (Employer), employee (Person reference)
- Box 1: wages, Box 2: federal_tax_withheld
- Box 3: social_security_wages, Box 4: social_security_tax
- Box 5: medicare_wages, Box 6: medicare_tax
- Box 12a-d: coded items (retirement contributions, etc.)
- Box 15-17: state/local tax info
- control_number

**Form1099INT** dataclass:
- payer_name, payer_tin
- Box 1: interest_income, Box 3: us_savings_bond_interest
- Box 4: federal_tax_withheld

**Form1099DIV** dataclass:
- payer_name, payer_tin
- Box 1a: ordinary_dividends, Box 1b: qualified_dividends
- Box 2a: capital_gain_distributions
- Box 4: federal_tax_withheld

**Form1099R** dataclass:
- payer_name, payer_tin
- Box 1: gross_distribution, Box 2a: taxable_amount
- Box 4: federal_tax_withheld, Box 7: distribution_code
- Box 7 codes: "7" (normal), "1" (early), "3" (disability), "4" (death)

**SSA1099** dataclass:
- Box 3: total_benefits, Box 4: benefits_repaid
- Box 5: net_benefits (the key training field)

**Form1099NEC** dataclass:
- payer_name, payer_tin
- Box 1: nonemployee_compensation

Extend **Person**:
- `w2s: List[W2]` — one per employer (most people have 1-2)
- `form_1099_ints: List[Form1099INT]`
- `form_1099_divs: List[Form1099DIV]`
- `form_1099_rs: List[Form1099R]`
- `ssa_1099: Optional[SSA1099]`
- `form_1099_necs: List[Form1099NEC]`
- `employer_name, employer_ein` — primary employer (for intake form)

### Step 9.2: `extraction/extract_part2.py`

Extract employment and income distributions from PUMS data → SQLite.

Distribution tables (from DATA_DICTIONARY.md):
- `employment_by_age` — ESR by age bracket (employed/unemployed/NILF)
- `education_by_age` — SCHL by age bracket
- `disability_by_age` — DIS by age bracket
- `social_security` — SSP+SSIP by age bracket
- `retirement_income` — RETP by age bracket
- `interest_and_dividend_income` — INTP by age bracket
- `other_income_by_employment_status` — OIP by ESR
- `public_assistance_income` — PAP by income bracket
- `bls_occupation_wages` — BLS OEWS wage data by SOC code
- `education_occupation_probabilities` — SCHL × OCCP cross-tab
- `age_income_adjustments` — AGEP × WAGP adjustment factors
- `occupation_self_employment_probability` — OCCP × COW rates

Output: appended to `data/distributions_{state}_{year}.sqlite`

CLI: `python -m extraction.extract_part2 --state HI --year 2022`

Reference: `HouseholdRNG/scripts/extract_pums.py` + `extract_bls.py`

### Step 9.3: `generator/employment.py`

Assign employment attributes to each adult Person. Reads Part 2
distribution tables and populates:
- `employment_status` — sampled from employment_by_age
- `education` — sampled from education_by_age
- `occupation_code` + `occupation_title` — sampled from
  education_occupation_probabilities, weighted by education level
- `has_disability` — sampled from disability_by_age

Port from `HouseholdRNG/generator/adult_generator.py`:
- `_sample_employment_status(age)`
- `_sample_education(age)`
- `_sample_disability(age)`
- `_sample_occupation(education, age)`

### Step 9.4: `generator/income.py`

Assign income amounts by type for each adult Person. Creates the income
document objects (W2, 1099-INT, etc.) and attaches them.

Core logic:
- **Wages**: Look up occupation in bls_occupation_wages, apply
  age_income_adjustments, add variance. Generate 1-2 W-2s per employed
  person.
- **Self-employment**: occupation_self_employment_probability determines
  if any SE income. Generate 1099-NEC if so.
- **Interest/dividends**: age-correlated probability and amount from
  interest_and_dividend_income. Generate 1099-INT / 1099-DIV.
- **Social Security**: age 62+ from social_security distributions.
  Generate SSA-1099.
- **Retirement**: age 55+ from retirement_income distributions.
  Generate 1099-R.
- **Withholding calculations**: federal tax withheld estimated from
  income bracket + filing status. SS tax = 6.2% of wages (capped).
  Medicare = 1.45% of wages.

Also generates:
- Employer name (Faker), EIN (random format XX-XXXXXXX), employer address
- Payer names for 1099s (bank names, brokerage names via Faker)
- Payer TINs

---

### Per-Form Tasks

### Step 9.A: W-2 — Template + Renderer

**Template**: `training/templates/w2.html`
- Generic IRS-standard layout (not vendor-specific for now)
- All boxes labeled by number (Box 1, Box 2, etc.)
- Employer info section (name, EIN, address)
- Employee info section (name, SSN, address)
- Watermark: "SAMPLE — FOR TRAINING USE ONLY"
- Future: W-2 vendor variants (ADP, Paychex, etc.) for layout training

**Renderer**: Add to `training/document_renderer.py`
- `render_w2_html(person: Person, w2_index: int = 0) -> str`
- Handles multiple W-2s per person

**Tests**: Render W-2 for person with wage income, verify HTML contains
correct box values, employer name, SSN.

### Step 9.B: 1099-INT + 1099-DIV — Templates + Renderers

**Templates**:
- `training/templates/1099_int.html` — interest income
  - Payer name/TIN, recipient name/SSN
  - Box 1 (interest income), Box 3 (US savings bonds), Box 4 (fed withheld)
- `training/templates/1099_div.html` — dividend income
  - Payer name/TIN, recipient name/SSN
  - Box 1a (ordinary dividends), Box 1b (qualified), Box 2a (cap gains)

These two forms share nearly identical structure — consider a shared
base layout with form-specific box sections.

**Renderer**: Add to `training/document_renderer.py`
- `render_1099_int_html(person: Person, index: int = 0) -> str`
- `render_1099_div_html(person: Person, index: int = 0) -> str`

**Tests**: Render each form, verify box values match Person income fields.

### Step 9.C: SSA-1099 + 1099-R — Templates + Renderers

**Templates**:
- `training/templates/ssa_1099.html` — Social Security benefits
  - SSA as payer, beneficiary name/SSN
  - Box 3 (total benefits), Box 4 (repaid), Box 5 (net benefits)
  - Distinctive blue/government styling
- `training/templates/1099_r.html` — retirement distributions
  - Payer name/TIN, recipient name/SSN
  - Box 1 (gross distribution), Box 2a (taxable amount)
  - Box 7 (distribution code — important for tax treatment)

**Renderer**: Add to `training/document_renderer.py`
- `render_ssa_1099_html(person: Person) -> str`
- `render_1099_r_html(person: Person, index: int = 0) -> str`

**Tests**: Render each form, verify amounts and distribution codes.

### Step 9.D: 1099-NEC — Template + Renderer

**Template**: `training/templates/1099_nec.html`
- Payer name/TIN (business that paid contractor)
- Recipient name/SSN
- Box 1: nonemployee compensation (the main field)
- Simple form but different generation context (self-employment)

**Renderer**: Add to `training/document_renderer.py`
- `render_1099_nec_html(person: Person, index: int = 0) -> str`

**Tests**: Render form, verify Box 1 matches self_employment_income.

---

### Integration

### Step 9.E: Extend form fields + populator for Part 2

**`training/form_fields.py`**: Add income field constants matching
Form 13614-C Part II income questions:
- `INCOME_WAGES` — wages, salaries, tips (from W-2s)
- `INCOME_INTEREST` — interest income (from 1099-INT)
- `INCOME_DIVIDENDS` — dividend income (from 1099-DIV)
- `INCOME_SOCIAL_SECURITY` — SS benefits (from SSA-1099)
- `INCOME_RETIREMENT` — pensions/annuities (from 1099-R)
- `INCOME_SELF_EMPLOYMENT` — self-employment (from 1099-NEC)
- Per-source yes/no checkboxes + amount fields

**`training/form_populator.py`**: Extend `build_field_values()` to
populate income fields from Person's income document objects.

### Step 9.F: Extend intake form, grader, and error injector

**Intake form**: Add Part II income section to `form_13614c_p1.html`
(or create `form_13614c_p2.html`). Income questions with input fields.

**Error injector**: New income error types:
- W-2 wage amount doesn't match intake total
- Wrong employer name on intake vs W-2
- Missing 1099 income (student forgets a source)
- SSN mismatch between W-2 and SSN card
- Transposed digits on income amounts

**Grader**: Extend `grade_intake()` and `grade_verification()` to
cover income fields. Income amount matching with tolerance (allow
rounding differences).

### Step 9.G: API routes for income documents

Add endpoints to `api/routes/scenarios.py`:
- `GET /scenarios/{id}/documents/w2/{person_id}/{index}` — W-2 HTML
- `GET /scenarios/{id}/documents/1099-int/{person_id}/{index}`
- `GET /scenarios/{id}/documents/1099-div/{person_id}/{index}`
- `GET /scenarios/{id}/documents/ssa-1099/{person_id}`
- `GET /scenarios/{id}/documents/1099-r/{person_id}/{index}`
- `GET /scenarios/{id}/documents/1099-nec/{person_id}/{index}`

Update exercise page to list all available income documents.

### Step 9.H: Tests

Tests are written alongside each step above, but the final checkpoint
is an end-to-end integration test:
- Generate household with PII + employment + income
- Render all applicable income documents
- Verify income fields populated on intake form
- Inject income errors, grade, verify feedback

**Checkpoint**: Full Part 2 gameplay loop works — generate scenario with
income → view W-2s and 1099s in browser → fill income section of intake
form → grade → get feedback on income fields.

---

## Sprint 10: Multi-Section Intake UI

The backend pipeline (Sprint 9) generates income data and documents, but
the web UI only presents Part I of the 13614-C intake form. Sprint 10
adds the Part II income form as a separate page and establishes the
multi-section navigation pattern that Part III (expenses) will follow.

### Design

The real IRS Form 13614-C is a multi-page document:

- **Page 1 / Part I** — Personal Information (Sections A–F)
- **Page 2 / Part II** — Income
- **Page 3 / Part III** — Expenses & Life Events (future)

The app mirrors this with separate form routes per section:

```
GET /scenarios/{id}/form           → Part I  (personal info)
GET /scenarios/{id}/form/income    → Part II (income)
GET /scenarios/{id}/form/expenses  → Part III (future)
```

Each form page:
1. Submits only its own fields to a section-specific endpoint
2. Shows a section nav bar (Part I / Part II / ...) so students can
   move between sections in any order
3. Pre-fills fields in verify mode (same as Part I today)
4. Grades independently — the grader already handles partial submissions

The exercise landing page shows one button per available section
instead of a single "Open Intake Form" button.

### Step 10.A: Part II Income Form Page

Add `GET /scenarios/{id}/form/income` route that renders an interactive
HTML form with:
- 6 income source rows, each with a checkbox and dollar amount input
  (wages, interest, dividends, social security, retirement,
  self-employment)
- Total income field
- Section nav bar linking to Part I and Part II
- Pre-fill support for verify mode
- POST to a section-aware submit endpoint

**Files**: `api/routes/scenarios.py`

**Checkpoint**: Navigate to `/scenarios/{id}/form/income` in the browser,
see the income form, fill it in manually.

### Step 10.B: Section-Aware Submission & Grading

Update the submission flow so each section can be graded independently:
- `POST /scenarios/{id}/submit/intake` — grades Part I fields only
- `POST /scenarios/{id}/submit/income` — grades Part II fields only
- Each returns a results page scoped to that section's fields
- Grades are saved per-section so the landing page can show progress
  (e.g., "Part I: 95%, Part II: not yet submitted")

Alternatively, keep a single submit endpoint but partition feedback
by section in the results display.

**Files**: `api/routes/scenarios.py`

**Checkpoint**: Submit the income form, see graded results for income
fields only.

### Step 10.C: Exercise Landing Page & Navigation

Update the exercise landing page (`GET /scenarios/{id}`) to:
- Show separate buttons for each form section (Part I, Part II)
- Display per-section grade status if previously graded
- Group document links by type (identity docs vs income docs) with
  clear visual separation
- Add section nav bar to Part I form page (matching Part II)

**Files**: `api/routes/scenarios.py`

**Checkpoint**: Landing page shows two form buttons. Each form page has
a nav bar to switch between sections. Previously graded sections show
scores on the landing page.

### Step 10.D: Tests

- Test Part II form renders with correct field names and pre-fill
- Test Part II submission parses income fields and grades correctly
- Test section nav links appear on both form pages
- Test landing page shows per-section grade status
- Test verify mode pre-fills income fields with injected errors

**Checkpoint**: All tests pass. Full user flow works in browser:
generate scenario → review income documents → fill Part II form →
submit → see income-specific feedback → navigate to Part I → submit →
see personal info feedback.

---

## Future: Additional Income Generators

Sprint 9 covers the six most common VITA Basic income types. The real
IRS Form 13614-C Part II lists ~15 income categories. The remaining
types need their own extract → generate → render cycle before they
can be added to the intake form and graded.

### VITA Basic level (high priority)

| Income Type | Document | Generator Needed | Notes |
|-------------|----------|-----------------|-------|
| Tips | W-2 (Box 7/8) | Extend W2 model | Already on W-2, add tip fields |
| Unemployment | 1099-G | New model + generator | State unemployment benefits |
| Disability benefits | 1099-R / W-2 | Extend existing | Distribution code "3" on 1099-R |

### VITA Advanced level (medium priority)

| Income Type | Document | Generator Needed | Notes |
|-------------|----------|-----------------|-------|
| Stock/bond sales | 1099-B | New model + generator | Cost basis, short/long term |
| Rental income | Schedule E | New model + generator | Rental expenses offset |
| Gambling winnings | W-2G | New model + generator | Withholding varies |
| Alimony | None (verbal) | Client profile fact | Pre-2019 vs post-2019 rules |
| State/local refund | 1099-G (Box 2) | Extend 1099-G model | Only taxable if itemized prior year |

### Out of scope for VITA

| Income Type | Reason |
|-------------|--------|
| 1099-K (payment apps) | Reporting threshold changes; complex |
| 1099-MISC (miscellaneous) | Mostly replaced by 1099-NEC for VITA |
| Foreign income | Not in VITA scope |
| Crypto/digital assets | Not in VITA Basic/Advanced scope |

Each new income type follows the same sprint pattern:
1. Add model dataclass and document fields
2. Add distribution data or generation logic
3. Add Jinja2 template for document rendering
4. Add form fields, populator entries, and error injection targets
5. Add grading support and tests

The intake form UI (Sprint 10) is designed to accept new income rows
without structural changes — each row is a checkbox + amount input
keyed by field name.

---

## Future: Zero-Income Household Filtering

About 10% of generated households end up with zero income and no tax
documents. This happens when all adults are sampled as `unemployed` or
`not_in_labor_force` and the probabilistic investment/SS/retirement
income assignments also produce nothing.

In real life, these households typically **don't need to file** (below
the filing threshold) and wouldn't visit a VITA site — unless filing
voluntarily for refundable credits (EITC, CTC, recovery rebate).
Either way, a zero-income scenario makes for a poor training exercise
since there's nothing to practice on the income form.

### Recommended approach

Filter at the **exercise level**, not the generator level. Keep the
generators statistically honest — they produce what the data says.
The `ExerciseEngine` decides whether a scenario is useful for training.

**Implementation:**
- In `ExerciseEngine.generate_scenario()`, after generation, check
  whether the household has at least one income document (W-2, 1099,
  or SSA-1099)
- If not, regenerate with a new seed (up to N retries, e.g. 5)
- If all retries produce zero income, accept the scenario but add a
  client fact noting "Client is filing to claim refundable credits"
- Optionally log a warning so we can tune the distributions if the
  retry rate is too high

**Files:** `training/exercise_engine.py`

**Why not fix in the generators:**
- The employment/income distributions reflect real Census data — some
  people genuinely have no income
- Special-casing "force at least one employed adult" distorts the
  demographics and creates odd scenarios (e.g. forcing a 75-year-old
  retiree into employment)
- Filtering at the exercise layer cleanly separates statistical
  accuracy from training usefulness

---

Each future VITA section follows this same pattern:
extract → generate → render → exercise → grade.
