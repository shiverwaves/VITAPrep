# VITA Form Fields Reference

## Form 13614-C: Intake/Interview & Quality Review Sheet

### Part I — Your Personal Information

These are the exact fields from the IRS VITA intake form that this app
generates and verifies. Field numbers match the official form.

#### Section A: About You

| # | Field | Type | Validation Notes |
|---|-------|------|-----------------|
| 1 | First name | Text | Must match SSN card exactly |
| 1 | Middle initial | Text | Often omitted — common error source |
| 1 | Last name | Text | Must match SSN card (maiden name issues) |
| 2 | Date of birth (MM/DD/YYYY) | Date | Cross-check against DL and age on 12/31 of tax year |
| 3 | Your SSN or ITIN | SSN | Must match SSN card exactly — transposition errors common |
| 4 | Job title | Text | Should be consistent with W-2 employer |
| 5 | Are you a US citizen? | Yes/No | Determines form eligibility |
| 6 | Daytime phone number | Phone | Optional but common |
| 7 | Email address | Email | Optional |

#### Section B: Mailing Address

| # | Field | Type | Validation Notes |
|---|-------|------|-----------------|
| 8 | Street address and apt number | Text | Must match across docs (DL may have old address) |
| 8 | City | Text | Consistent with ZIP |
| 8 | State | Text | Must match household state |
| 8 | ZIP code | Text | 5 digits, consistent with city/state |

#### Section C: About Your Spouse (if applicable)

| # | Field | Type | Validation Notes |
|---|-------|------|-----------------|
| 9 | Spouse first name | Text | Must match spouse's SSN card |
| 9 | Spouse middle initial | Text | Same issues as primary |
| 9 | Spouse last name | Text | May differ from primary (maiden name) |
| 10 | Spouse date of birth | Date | Cross-check against spouse DL |
| 11 | Spouse SSN or ITIN | SSN | Must match spouse SSN card |
| 12 | Spouse job title | Text | Consistent with spouse W-2 |

#### Section D: Filing Status

| # | Field | Type | Validation Notes |
|---|-------|------|-----------------|
| 13 | Filing status | Radio | Single, MFJ, MFS, HOH, QSS |

Determination rules:
- **Single**: Unmarried, no dependents qualifying for HOH
- **Married Filing Jointly (MFJ)**: Married + both agree to file jointly
- **Married Filing Separately (MFS)**: Married but filing apart
- **Head of Household (HOH)**: Unmarried + paid >50% of keeping up home + qualifying person lived with you
- **Qualifying Surviving Spouse (QSS)**: Spouse died in prior 2 years + dependent child

Common errors to inject:
- Single selected but household has spouse
- HOH selected but no qualifying dependent
- MFS when MFJ would be more beneficial
- QSS when spouse died >2 years ago

#### Section E: Dependents

| # | Field | Type | Validation Notes |
|---|-------|------|-----------------|
| 14a | Dependent first name | Text | Must match dependent's SSN card |
| 14a | Dependent last name | Text | May differ in blended families |
| 14b | Dependent date of birth | Date | Determines qualifying child age test |
| 14c | Dependent relationship | Text | Must be qualifying relationship |
| 14d | Months lived in home | Number | Must be >6 for qualifying child (12 for newborns born in tax year) |
| 14e | Single/Married | Radio | Dependent's own marital status |
| 14f | US citizen | Yes/No | Required for most credits |
| 14g | Student (full-time) | Yes/No | Extends qualifying child age to 24 |
| 14h | Disabled | Yes/No | No age limit for qualifying child |

Up to 4 dependents on the form (additional on attached sheet).

Dependent qualification tests:
- **Relationship test**: Child, stepchild, foster child, sibling, or descendant
- **Age test**: Under 19 at end of tax year, or under 24 if full-time student, or any age if permanently disabled
- **Residency test**: Lived with taxpayer for more than half the year (>6 months)
- **Support test**: Did not provide more than half of own support
- **Joint return test**: Dependent did not file MFJ (with exceptions)

#### Section F: Additional Questions

| # | Field | Type | Validation Notes |
|---|-------|------|-----------------|
| 15 | Can anyone claim you as a dependent? | Yes/No | Based on support and income tests |
| 16 | Have you been a dependent in prior years? | Yes/No | History context |

---

## Form 1040 — Personal Information Section (Page 1 Header)

For Mode 3 (cross-reference against 1040), these are the fields:

| Field | Location | Validation Notes |
|-------|----------|-----------------|
| Filing status checkboxes | Top of 1040 | Single, MFJ, MFS, HOH, QSS |
| First name and middle initial | Line header | Must match SSN card |
| Last name | Line header | Must match SSN card |
| Your SSN | Right of name | Must match SSN card |
| Spouse first name (if MFJ) | Second line | Must match spouse SSN card |
| Spouse last name | Second line | May differ from primary |
| Spouse SSN | Right of spouse name | Must match spouse SSN card |
| Home address | Below names | Number, street, apt |
| City, town, state, ZIP | Below address | Consistent with DL |
| Dependents section | Lines below | Name, SSN, relationship, child tax credit checkbox |

---

## Document Cross-Reference Matrix

This shows which documents verify which form fields:

| Form Field | SSN Card | Driver's License | W-2 | Birth Cert |
|-----------|----------|-----------------|-----|------------|
| Legal name | ✅ Primary | ✅ Secondary | ✅ Check | |
| SSN | ✅ Primary | | ✅ Check | |
| DOB | | ✅ Primary | | ✅ Secondary |
| Address | | ✅ Primary | ✅ Check | |
| Filing status | | | | (derived from household) |
| Dependent name | ✅ (their card) | | | |
| Dependent SSN | ✅ (their card) | | | |
| Dependent DOB | | | | (calculated from age) |
