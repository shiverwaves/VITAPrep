# CLAUDE.md — Project Context for Claude Code

## Project Overview

**VITATrainer** is a tax preparation training application that generates realistic
synthetic households and produces practice exercises modeled on the IRS VITA
(Volunteer Income Tax Assistance) intake workflow.

The app generates fake-but-realistic client scenarios using U.S. Census PUMS
(Public Use Microdata Sample) demographic distributions, overlays synthetic PII
(names, SSNs, DOBs, addresses), renders mock identity documents (SSN cards,
driver's licenses), and presents exercises where students verify personal
information against the IRS Form 13614-C intake sheet or Form 1040.

## Architecture

```
data/distributions_hi_2022.sqlite    (read-only reference data, shipped with repo)
data/scenarios.sqlite                (runtime data, gitignored)
        │
        ▼
┌───────────────────┐     ┌──────────────────┐     ┌─────────────────┐
│  generator/        │────▶│  training/        │────▶│  api/            │
│  Pipeline by VITA  │     │  Documents,       │     │  FastAPI         │
│  section           │     │  errors, grading  │     │  endpoints       │
└───────────────────┘     └──────────────────┘     └─────────────────┘
```

### Key Design Decisions

1. **Two SQLite databases**: Distribution data (PUMS reference tables, read-only,
   committed to repo) and scenario data (generated exercises, grades, gitignored).
   Distribution data uses SQLAlchemy so it can optionally point at PostgreSQL.

2. **Modular by VITA section**: Extraction and generation are split by the section
   of the VITA intake form they serve (Part 1 = personal info, Part 2 = income, etc.).
   Each section only requires its own distribution tables.

3. **PII is a first-class generation stage**, not an afterthought. The `Person` model
   includes PII fields (names, SSN, DOB) alongside statistical fields (age, sex, race).

4. **Single FastAPI process**: No API→Worker proxy split. One app serves scenarios,
   documents, and grades.

5. **Exercises are scenario-based**: A scenario bundles a generated household, rendered
   documents, a blank or pre-filled form, optional seeded errors, and an answer key.

## Tech Stack

- **Python 3.11+**
- **SQLite** (distributions + scenarios) via **SQLAlchemy**
- **pandas / numpy** for data processing
- **Faker** for synthetic PII generation
- **Jinja2 + WeasyPrint** for document rendering (HTML → PNG/PDF)
- **FastAPI** for the API
- **pytest** for testing

## File Structure Overview

```
vita-trainer/
├── CLAUDE.md                 ← You are here
├── README.md
├── requirements.txt
├── pyproject.toml
├── cli.py                    # Command-line entry point
│
├── data/                     # SQLite databases
│   └── .gitkeep
│
├── extraction/               # PUMS/BLS → SQLite (run once per state)
│   ├── extract_part1.py      # Household structure + demographics (12 tables)
│   ├── extract_part2.py      # Employment + income (11 tables)
│   ├── extract_part3.py      # Deductions + credits (4 tables)
│   ├── extract_all.py        # Runs all extraction modules
│   └── pums_download.py      # Shared PUMS/BLS file downloader + cache
│
├── generator/                # Core generation pipeline
│   ├── models.py             # Person, Household, FilingUnit, Address
│   ├── sampler.py            # Weighted sampling utilities
│   ├── db.py                 # SQLAlchemy loader for distribution tables
│   ├── demographics.py       # Part 1: age, sex, race, relationships
│   ├── children.py           # Part 1: child generation
│   ├── pii.py                # Part 1: names, SSNs, DOBs, addresses (Faker)
│   ├── employment.py         # Part 2: employment, education, occupation
│   ├── income.py             # Part 2: income assignment
│   ├── expenses.py           # Part 3/4: deductions, credits
│   └── pipeline.py           # Orchestrates generation by VITA section
│
├── training/                 # VITA training features
│   ├── document_renderer.py  # HTML templates → PNG/PDF
│   ├── error_injector.py     # Seed discrepancies between docs
│   ├── exercise_engine.py    # Assemble scenarios (docs + form + key)
│   ├── grader.py             # Compare submissions to answer key
│   ├── scenario_store.py     # CRUD for scenarios (SQLite)
│   └── templates/            # Jinja2 HTML templates
│       ├── base.css
│       ├── ssn_card.html
│       ├── drivers_license.html
│       ├── form_13614c_p1.html
│       └── form_1040_header.html
│
├── api/                      # FastAPI application
│   ├── main.py               # App setup, lifespan, middleware
│   └── routes/
│       ├── scenarios.py      # Generate, get, submit, grade
│       ├── config.py         # States, patterns, difficulty
│       └── progress.py       # Student history
│
├── tests/
│   ├── conftest.py
│   ├── test_demographics.py
│   ├── test_children.py
│   ├── test_pii.py
│   ├── test_pipeline.py
│   ├── test_document_renderer.py
│   ├── test_error_injector.py
│   └── test_grader.py
│
├── docs/
│   ├── BUILD_PLAN.md         # Step-by-step implementation guide
│   ├── DATA_DICTIONARY.md    # PUMS fields → VITA fields mapping
│   ├── VITA_FORM_FIELDS.md   # Exact fields from 13614-C and 1040
│   └── ARCHITECTURE.md       # Detailed architecture with diagrams
│
└── scripts/
    └── seed_data.sh          # One-time: extract PUMS → SQLite for HI
```

## Coding Conventions

- **Type hints everywhere** — all function signatures fully typed
- **Dataclasses for models** — not Pydantic in the generator layer (Pydantic in API layer only)
- **Logging** — use `logging.getLogger(__name__)` in every module
- **No print statements** — use logger
- **Tests alongside implementation** — write tests for each module as you build it
- **Docstrings** — Google style, include Args/Returns/Raises
- **SSNs always use 9XX prefix** — test range, never assigned to real people
- **All rendered documents must have "SAMPLE — FOR TRAINING USE ONLY" watermark**

## Build Order

See `docs/BUILD_PLAN.md` for the full step-by-step. The short version:

1. `generator/models.py` — data models (everything depends on this)
2. `generator/sampler.py` — weighted sampling utilities
3. `generator/db.py` — SQLite distribution loader
4. `extraction/extract_part1.py` — PUMS → SQLite for Part 1 tables
5. `generator/demographics.py` — age, sex, race, household structure
6. `generator/children.py` — child demographics
7. `generator/pii.py` — Faker overlay (names, SSNs, DOBs, addresses)
8. `generator/pipeline.py` — orchestrate Part 1 generation
9. `training/document_renderer.py` + templates — SSN card, DL, forms
10. `training/error_injector.py` — seed discrepancies
11. `training/grader.py` — score submissions
12. `api/main.py` + routes — serve it all

## Prior Work

This project builds on learnings from the HouseholdRNG repository
(github.com/shiverwaves/HouseholdRNG) which contains:
- PUMS/BLS extraction scripts (extract_pums.py, extract_bls.py, extract_derived.py)
- Household generation pipeline (7 stages)
- Data models (Person, Household, FilingUnit)
- Weighted sampling utilities
- FastAPI + Docker deployment

Key code to reference/port from HouseholdRNG:
- `generator/sampler.py` — weighted_sample, bracket parsing (use as-is)
- `generator/models.py` — Person, Household, FilingUnit (extend with PII fields)
- `scripts/extract_pums.py` — PUMS download + extraction logic (split by section)
- `generator/adult_generator.py` — demographic sampling logic (split into demographics + employment)
- `generator/child_generator.py` — child generation (port mostly as-is)
