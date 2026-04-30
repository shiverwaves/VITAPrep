# Sprint 9.1: Income document models + Part 2 build plan

## Summary

- **Expand `BUILD_PLAN.md`** with detailed Sprint 9 breakdown for Part 2 (Income). Foundation steps (model extensions, PUMS extraction, employment/income generators), per-form tasks (W-2, 1099-INT/DIV, SSA-1099/1099-R, 1099-NEC), and integration steps (form fields, grader, error injector, API routes).
- **Add income document dataclasses** to `generator/models.py`: `Employer`, `W2`, `Form1099INT`, `Form1099DIV`, `Form1099R`, `SSA1099`, `Form1099NEC`. Each maps to a real IRS source form with the correct box numbers as fields.
- **Extend `Person`** with lists of income documents (`w2s`, `form_1099_ints`, `form_1099_divs`, `form_1099_rs`, `ssa_1099`, `form_1099_necs`) and updated `to_dict()` serialization.
- **Clean up remaining PDF references** from CI workflow, training `__init__.py`, and `base.css` comments (carried over from prior session).

## Design decisions

| Decision | Rationale |
|----------|-----------|
| `int` for all dollar amounts | Consistent with existing Person income fields. Templates format as `$XX,XXX.00` at render time. |
| Document objects live on `Person`, not `Household` | A person can have multiple W-2s (multiple jobs) or multiple 1099s. Each document carries its own payer/employer info. |
| `Employer` is a separate dataclass | Reused by W-2 and potentially 1099-NEC. Contains name, EIN, and address. |
| Box numbers as field names | `W2.wages` = Box 1, `W2.federal_tax_withheld` = Box 2, etc. Maps directly to IRS form layout for template rendering. |

## Changes

| File | Change |
|------|--------|
| `generator/models.py` | +155 lines — 7 new dataclasses, Person extended with income document lists |
| `docs/BUILD_PLAN.md` | +269 lines — Sprint 9 expanded from 5 lines to full breakdown |
| `.github/workflows/test-generators.yml` | Removed stale PDF/WeasyPrint references |
| `training/__init__.py` | Removed PDF mention from docstring |
| `training/templates/base.css` | Removed PDF comment |

## New dataclasses

```python
Employer(name, ein, address)
W2(employer, wages, federal_tax_withheld, social_security_wages, ...)
Form1099INT(payer_name, payer_tin, interest_income, ...)
Form1099DIV(payer_name, payer_tin, ordinary_dividends, qualified_dividends, ...)
Form1099R(payer_name, payer_tin, gross_distribution, taxable_amount, distribution_code, ...)
SSA1099(total_benefits, benefits_repaid, net_benefits)
Form1099NEC(payer_name, payer_tin, nonemployee_compensation, ...)
```

## Test plan

- [x] All 435 existing tests pass — no regressions
- [x] Smoke test: `W2`, `Employer`, and all 1099 dataclasses instantiate and serialize via `to_dict()`
- [x] `Person` with populated income document lists serializes correctly
- [ ] Full test coverage comes in Step 9.H after generators populate these models
