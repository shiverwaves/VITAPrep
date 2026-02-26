# Data Dictionary — PUMS Fields to VITA Form Mapping

## PUMS Data Source

- **Source**: American Community Survey Public Use Microdata Sample (ACS PUMS)
- **URL**: https://www2.census.gov/programs-surveys/acs/data/pums/
- **Format**: CSV inside ZIP, one file per state (person + household)
- **Documentation**: https://www.census.gov/programs-surveys/acs/microdata/documentation.html

## Part 1: Personal Information

### Distribution Tables Extracted

| Table Name | Source File | PUMS Fields Used | Purpose |
|------------|-----------|-----------------|---------|
| `household_patterns` | Household + Person | SERIALNO, RELSHIPP, MAR, NP | Household type distribution (married couple, single parent, etc.) |
| `children_by_parent_age` | Person | AGEP, RELSHIPP | How many children by parent's age bracket |
| `child_age_distributions` | Person | AGEP, RELSHIPP | Child age distribution by relationship type |
| `adult_child_ages` | Person | AGEP, RELSHIPP | Age distribution of adult children (18+) still in household |
| `stepchild_patterns` | Household + Person | RELSHIPP, MAR, SEX | Stepchild frequency and household composition |
| `multigenerational_patterns` | Household + Person | RELSHIPP, AGEP | 3+ generation household structures |
| `unmarried_partner_patterns` | Household + Person | RELSHIPP, SEX | Cohabiting couple demographics |
| `race_distribution` | Person | RAC1P, PWGTP | Overall race distribution (weighted) |
| `race_by_age` | Person | RAC1P, AGEP, PWGTP | Race distribution by age bracket |
| `hispanic_origin_by_age` | Person | HISP, AGEP, PWGTP | Hispanic/Latino origin by age bracket |
| `spousal_age_gaps` | Person | AGEP, RELSHIPP | Age difference between householder and spouse |
| `couple_sex_patterns` | Person | SEX, RELSHIPP | Same-sex vs opposite-sex couple distribution |

### Key PUMS Variables for Part 1

| PUMS Variable | Description | Values | Maps To |
|--------------|-------------|--------|---------|
| `SERIALNO` | Household serial number | Unique ID | Links person ↔ household |
| `RELSHIPP` | Relationship to householder | 20=householder, 21=spouse, 23=bio child, 24=adopted, 25=stepchild, 26=sibling, 27=parent, 28=grandchild, 30=unmarried partner, etc. | Person.relationship |
| `AGEP` | Age | 0-99 | Person.age → Person.dob (via pii.py) |
| `SEX` | Sex | 1=Male, 2=Female | Person.sex |
| `MAR` | Marital status | 1=Married, 2=Widowed, 3=Divorced, 4=Separated, 5=Never married | Household.filing_status derivation |
| `RAC1P` | Race (recoded) | 1=White, 2=Black, 3-5=AIAN, 6=Asian, 7=NHPI, 8=Other, 9=Two+ | Person.race → name generation hints |
| `HISP` | Hispanic origin | 1=Not Hispanic, 2-24=specific origins | Person.hispanic_origin → name generation |
| `NP` | Number of persons | 1-20 | Household size validation |
| `PWGTP` | Person weight | Integer | Sampling weight (population representation) |
| `WGTP` | Household weight | Integer | Sampling weight for household records |

### Mapping to Form 13614-C Part I

| 13614-C Field | Generated From | Verified Against |
|---------------|---------------|-----------------|
| Your first name | Faker (race/ethnicity-informed) | SSN card template |
| Middle initial | Faker | SSN card template |
| Last name | Faker (family consistency rules) | SSN card template |
| Your SSN | Random 9XX-XX-XXXX | SSN card template |
| Date of birth | Person.age + tax_year → random date | Driver's license |
| Mailing address | Faker (state-matched) | Driver's license |
| City/State/ZIP | Faker (state-matched) | Driver's license |
| Spouse first name | Faker | Spouse SSN card |
| Spouse SSN | Random 9XX-XX-XXXX | Spouse SSN card |
| Spouse DOB | Spouse Person.age → date | Spouse DL |
| Filing status | Derived from household composition | Household members |
| Dependent name | Faker (family name rules) | Dependent SSN card |
| Dependent SSN | Random 9XX-XX-XXXX | Dependent SSN card |
| Dependent DOB | Child Person.age → date | Calculated |
| Dependent relationship | Person.relationship | Household pattern |
| Months lived in home | 12 (default) or calculated for newborns | DOB cross-check |

## Part 2: Income (Future — Sprint 9+)

### Distribution Tables

| Table Name | PUMS Fields | Purpose |
|------------|------------|---------|
| `employment_by_age` | AGEP, ESR, PWGTP | Employment rate by age bracket |
| `education_by_age` | AGEP, SCHL, PWGTP | Education level by age |
| `disability_by_age` | AGEP, DIS, PWGTP | Disability rate by age |
| `social_security` | AGEP, SSP, SSIP, PWGTP | SS income by age bracket |
| `retirement_income` | AGEP, RETP, PWGTP | Retirement income distribution |
| `interest_and_dividend_income` | AGEP, INTP, PWGTP | Investment income |
| `other_income_by_employment_status` | ESR, OIP, PWGTP | Other income sources |
| `public_assistance_income` | HINCP, PAP, PWGTP | Means-tested assistance |
| `bls_occupation_wages` | (BLS OEWS data) | Occupation-specific wage ranges |
| `education_occupation_probabilities` | SCHL, OCCP | Education → occupation mapping |
| `age_income_adjustments` | AGEP, WAGP | Age-based wage adjustment factors |
| `occupation_self_employment_probability` | OCCP, COW | Self-employment rates by occupation |

## Part 3/4: Deductions and Credits (Future)

| Table Name | PUMS Fields | Purpose |
|------------|------------|---------|
| `homeownership_rates` | TEN, AGEP, HINCP | Owner vs renter by demographics |
| `property_taxes` | TAXAMT, TEN | Property tax distribution |
| `mortgage_interest` | (derived) | Mortgage costs by income bracket |

## State-Specific ID Number Formats

| State | DL Format | Example |
|-------|----------|---------|
| HI | H + 8 digits | H01-234-5678 |
| CA | 1 letter + 7 digits | D1234567 |
| TX | 8 digits | 12345678 |
| NY | 9 digits or 1 letter + 18 digits | 123456789 |
| FL | 1 letter + 12 digits | N123-456-78-901-2 |

Start with HI for MVP, add others as needed.
