# VITATrainer

Generate realistic tax preparation practice scenarios for VITA (Volunteer Income Tax Assistance) training.

## What It Does

- Generates synthetic households using U.S. Census PUMS demographic distributions
- Creates mock identity documents (SSN cards, driver's licenses)
- Produces practice exercises based on IRS Form 13614-C intake workflow
- Grades student submissions with field-level feedback

## Quick Start

```bash
# Install dependencies
pip install -r requirements.txt

# Generate a practice scenario (once data is set up)
python cli.py generate --mode intake --difficulty easy --state HI
```

## Documentation

- [Build Plan](docs/BUILD_PLAN.md) — Step-by-step implementation guide
- [Data Dictionary](docs/DATA_DICTIONARY.md) — PUMS fields to VITA form mapping
- [VITA Form Fields](docs/VITA_FORM_FIELDS.md) — Exact form fields reference

## Prior Work

Builds on [HouseholdRNG](https://github.com/shiverwaves/HouseholdRNG) — Census PUMS
extraction and household generation pipeline.

## License

MIT
