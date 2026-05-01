# Concept Catalog

This document is the master list of tax-law concepts VITAPrep can drill. Each concept is a tagged feature the system recognizes in a generated scenario and, eventually, can target on demand.

> **Companion documents:** [`BUILD_PLAN.md`](./BUILD_PLAN.md) describes when concepts are built. [`SCENARIO_LIFECYCLE.md`](./SCENARIO_LIFECYCLE.md) describes how concepts attach to scenarios at runtime.

---

## Purpose

Three audiences read this doc, each looking for something different.

**Claude Code (and any future contributor doing implementation)** uses this catalog as the predicate inventory for `tax_core`. The "Predicates required" list under each concept resolves to functions that must exist in `tax_core/predicates/` before the concept can be implemented. The MVP predicate list at the bottom of this doc is the work order for Restructure A.

**The product owner** uses this catalog to scope what the tool teaches. Concept count and coverage are the actual product surface. Adding a concept is a feature; deferring one is a deliberate scope decision. The phase tags make those decisions visible.

**A learner studying tax** (EA Part 1, CPA REG, VITA certification) uses this catalog as a study map. Each entry names the rule, cites the source, and explains why the rule trips up new preparers. Reading the catalog end to end is one way to audit your own knowledge — concepts you can't explain in plain English are concepts to study before working on them in code.

The catalog is a living document. Add concepts as you encounter them in the wild. Deferred concepts are not lost — they're parked until the predicate work to support them is justified.

---

## How to read an entry

Each concept has the following fields:

- **Name** — the code identifier (snake_case). Used as the concept's class name and tag.
- **Category** — filing status, dependency, income, deductions, credits, events.
- **Phase** — `mvp`, `p2`, or `p3`. See "Phase tags" below.
- **Lifecycle dependency** — earliest lifecycle stage at which the concept can evaluate. See "Lifecycle dependencies" below.
- **Rule tested** — plain-English statement of what tax law says.
- **Source** — IRC section, IRS publication, or other canonical reference for further reading.
- **Predicates required** — the `tax_core` functions the concept's `matches()` would call.
- **Why it matters** — the pedagogical hook. Why a learner blows this, why it's worth drilling.
- **Subtlety dial** — how the obfuscation layer can vary the difficulty of recognizing this in a scenario.

---

## Phase tags

`mvp` — Implement during Restructures A–D. Three to five of these ship with the first pass. Each pulls in two to four predicates. Together they exercise the full lifecycle (generation → analyzer → ground truth → concept tag → grading).

`p2` — Implement after MVP is stable. Round out Part I/II/III coverage. Mostly mechanical once the pattern is established.

`p3` — Deferred. Either too narrow to drill (rare situations), too complex for current scope (multi-form interactions like ACA premium tax credit), or genuinely outside individual tax (entity-level concerns). Keep them listed so they aren't forgotten.

---

## Lifecycle dependencies

`fact` — Concept evaluates against generated facts only. Predicates read household composition, income, documents. Can run as soon as ground truth exists (Stage 4). Most concepts are this kind.

`interview` — Concept evaluates against the divergence between what the client claimed and what the facts show. Requires the obfuscation layer to be in place (Stage 6). Examples: "client claimed HoH but doesn't actually qualify."

`computed` — Concept evaluates against a counterfactual computation. Requires `tax_core` to be able to compute a return under alternate assumptions. Example: `mfj_vs_mfs` fires only when filing separately would change the outcome materially — that's a comparison of two computed returns.

The MVP concepts are all `fact` for a reason: the other two require infrastructure that doesn't exist yet.

---

## Catalog summary

Quick-scan view. Detailed entries follow.

| Concept | Category | Phase | Lifecycle |
|---|---|---|---|
| `hoh_qualifying_person` | filing status | mvp | fact |
| `qualifying_child_residency` | dependency | mvp | fact |
| `refundable_credit_only_filer` | filing | mvp | fact |
| `self_employment_threshold` | income | mvp | fact |
| `social_security_taxability` | income | mvp | fact |
| `standard_vs_itemized` | deductions | mvp | fact |
| `qualifying_surviving_spouse` | filing status | p2 | fact |
| `mfj_vs_mfs` | filing status | p2 | computed |
| `qualifying_child_age` | dependency | p2 | fact |
| `qualifying_relative_support` | dependency | p2 | fact |
| `tiebreaker_rules` | dependency | p2 | fact |
| `schedule_a_substantiation` | deductions | p2 | fact |
| `hsa_eligibility` | deductions | p2 | fact |
| `eitc_qualifying_child_rules` | credits | p3 | fact |
| `aotc_vs_llc` | credits | p3 | computed |
| `premium_tax_credit_reconciliation` | credits | p3 | fact |
| `ira_contribution_phaseout` | deductions | p3 | fact |
| `claimed_status_diverges_from_truth` | filing status | p3 | interview |

---

## MVP concepts (6)

### `hoh_qualifying_person`

- **Category:** filing status
- **Phase:** mvp
- **Lifecycle:** fact

**Rule tested.** Head of Household requires three things: the filer is unmarried (or considered unmarried) at year-end, paid more than half the cost of keeping up a home, and a qualifying person lived with them more than half the year. A "qualifying person" is a qualifying child OR a qualifying relative who is a parent or other specified relative.

**Source.** IRC §2(b); IRS Publication 501, "Filing Status."

**Predicates required.**
- `is_unmarried(filer, year)` — including legally separated under divorce decree, or living apart from spouse last six months of year with dependent.
- `paid_more_than_half_household_costs(filer, household)`
- `has_qualifying_person_for_hoh(filer)` — combines qualifying-child and qualifying-relative tests with HoH-specific filters.
- `qualifying_child_residency_test(child, year)` (shared)
- `qualifying_relative_test(person, household)` (shared)

**Why it matters.** Most-blown call at VITA sites by margin. New preparers default to "single" for unmarried clients, missing HoH eligibility entirely. The opposite mistake — claiming HoH when the residency test fails — is also common and triggers IRS attention because HoH gets a bigger standard deduction and lower brackets.

**Subtlety dial.**
- *Obvious:* client states "I'm a single mom, my daughter lived with me all year."
- *Moderate:* client describes a shared-custody arrangement; player must compute months.
- *Subtle:* mother of a divorced filer lives in a separate apartment the filer pays for; qualifying-relative HoH is in scope but the filer didn't think to mention it.

---

### `qualifying_child_residency`

- **Category:** dependency
- **Phase:** mvp
- **Lifecycle:** fact

**Rule tested.** A qualifying child must have the same principal place of abode as the taxpayer for more than half the tax year. Statutory exceptions: temporary absences (school, illness, military), birth or death during the year, kidnapping.

**Source.** IRC §152(c)(1)(B); IRS Pub 501.

**Predicates required.**
- `qualifying_child_residency_test(child, year)` — returns months in home, pass/fail, exceptions applied.

**Why it matters.** The "more than half the year" rule is the boundary case players misjudge. Six months exactly fails; six months and one day passes. Players who memorize "half the year" without the "more than" qualifier get this wrong consistently. The borderline 5–7 months range also forces players to actually count rather than rely on the client's vague answer.

**Subtlety dial.**
- *Obvious:* client states number of months explicitly.
- *Moderate:* "she was with me during the school year, with her dad in summer" — player computes.
- *Subtle:* split residency described casually across multiple interview answers; player must reconstruct.

---

### `refundable_credit_only_filer`

- **Category:** filing
- **Phase:** mvp
- **Lifecycle:** fact

**Rule tested.** A taxpayer below the income filing threshold may still file to claim refundable credits (EITC, Additional Child Tax Credit, American Opportunity Credit refundable portion). They are not *required* to file, but if they don't, they don't get the refund.

**Source.** IRC §6012 (filing requirements); IRC §32 (EITC); IRC §24(d) (ACTC).

**Predicates required.**
- `total_income(filer)`
- `filing_threshold_for(status, year)`
- `qualifies_for_eitc(filer)` (or any refundable credit)
- `qualifies_for_actc(filer)`

**Why it matters.** This is the concept that legitimizes the zero-income scenario you raised earlier in the build process. A scenario with no W-2s and no self-employment income is incoherent unless a reason for filing exists; a refundable credit is the most common one in VITA populations. Pedagogically, it tests whether the player recognizes that "below filing threshold" doesn't mean "can't file" — and whether they identify the credit-eligibility path correctly.

**Subtlety dial.**
- *Obvious:* client says "I just want my refund from the credits."
- *Moderate:* client describes the situation factually; player infers filing reason.
- *Subtle:* client uncertain why they're filing; player must determine eligibility from facts.

---

### `self_employment_threshold`

- **Category:** income
- **Phase:** mvp
- **Lifecycle:** fact

**Rule tested.** Net earnings from self-employment of $400 or more trigger Schedule SE. The threshold is per-person, not per-return. SE tax (15.3% on the first portion, 2.9% above the SS wage base) is separate from income tax and is owed even if no income tax is owed.

**Source.** IRC §1401, §1402; Schedule SE instructions.

**Predicates required.**
- `total_self_employment_income(person)` — sums 1099-NEC, Schedule C net, partnership SE earnings.
- `requires_schedule_se(person)` — `total_self_employment_income >= 400`.

**Why it matters.** New preparers see "freelancer made $500 dog-walking" and treat it as ordinary income, missing Schedule SE entirely. The threshold is small enough that it catches casual gig work most people wouldn't think of as "self-employment." Also tests whether the player connects 1099-NEC presence to Schedule SE obligation, which is the single most common Part 2 mistake.

**Subtlety dial.**
- *Obvious:* 1099-NEC for a clear amount over the threshold.
- *Moderate:* 1099-NEC just over the threshold (e.g., $450), tests whether player knows the rule applies.
- *Subtle:* SE income reported verbally without a 1099 (cash side gigs); player must remember the SE obligation applies regardless of form issuance.

---

### `social_security_taxability`

- **Category:** income
- **Phase:** mvp
- **Lifecycle:** fact

**Rule tested.** Social Security benefits become partially taxable when "provisional income" (AGI + tax-exempt interest + ½ of SS benefits) exceeds base amounts ($25,000 single, $32,000 MFJ for the lower tier; $34,000/$44,000 for the higher tier). Up to 50% of benefits are taxable above the lower threshold; up to 85% above the higher.

**Source.** IRC §86; IRS Pub 915.

**Predicates required.**
- `compute_provisional_income(filer)` — AGI + tax-exempt interest + ½ SS.
- `ss_taxability_thresholds(filing_status, year)` — returns the two-tier thresholds.
- `compute_taxable_ss(filer, year)` — runs the §86 worksheet.

**Why it matters.** Common, counterintuitive, and missed. New preparers either tax Social Security fully (overstating tax) or not at all (understating tax). The MFS-living-with-spouse rule (zero threshold, 85% taxable) is the trap inside the trap. Senior populations are a major VITA constituency, so this concept fires often.

**Subtlety dial.**
- *Obvious:* SSA-1099 in pile with other income clearly above threshold.
- *Moderate:* income just over the lower threshold; player computes the partial inclusion.
- *Subtle:* tax-exempt municipal bond interest pushes provisional income over a threshold; player must remember it counts.

---

### `standard_vs_itemized`

- **Category:** deductions
- **Phase:** mvp
- **Lifecycle:** fact

**Rule tested.** A taxpayer chooses between the standard deduction (a fixed amount by filing status, indexed annually) and itemizing deductions on Schedule A. The itemized total is the sum of: state and local taxes paid (SALT — state income tax + property taxes, capped at $10,000), mortgage interest (Form 1098), medical and dental expenses exceeding 7.5% of AGI, and charitable contributions. The taxpayer should choose whichever is larger. Most taxpayers take the standard deduction; the SALT cap ($10K since TCJA 2017) pushed many former itemizers below the threshold.

**Source.** IRC §63 (standard deduction); IRC §164 (state and local taxes); IRC §163(h) (mortgage interest); IRC §213 (medical expenses); IRC §170 (charitable contributions); IRC §164(b)(6) (SALT cap).

**Predicates required.**
- `standard_deduction_for(status, year)` — returns the standard deduction amount.
- `compute_salt(state_tax, property_tax, year)` — applies the $10K SALT cap.
- `compute_medical_deduction(medical_expenses, agi)` — applies the 7.5% AGI floor.
- `compute_itemized_total(household, year)` — aggregates SALT + mortgage + medical + charitable.
- `should_itemize(household, year)` — compares itemized total against standard deduction for filing status.

**Why it matters.** This is already implemented in the codebase (`expenses.py: _calculate_totals()`). It's a core VITA competency — the volunteer must evaluate whether itemizing benefits the client. The most common mistake is not checking: defaulting to standard deduction without computing the alternative, or conversely, itemizing when the standard deduction is higher. The SALT cap is the wrinkle that catches experienced filers who haven't updated their intuition since TCJA.

**Subtlety dial.**
- *Obvious:* large mortgage interest and property taxes clearly exceed the standard deduction.
- *Moderate:* itemized total is within a few hundred dollars of the standard deduction; player must compute carefully.
- *Subtle:* medical expenses appear large but fall below the 7.5% AGI floor; SALT appears large but is capped at $10K. The headline numbers look like itemizing wins, but after applying the floor and cap, standard deduction is better.

**Existing code (Restructure A extraction target).**
- `STANDARD_DEDUCTION` dict → `tax_core/thresholds.py`
- `SALT_CAP` constant → `tax_core/thresholds.py`
- Medical 7.5% AGI floor logic → `tax_core/predicates/deductions.py`
- Standard vs itemized comparison in `_calculate_totals()` → `tax_core/predicates/deductions.py`

---

## P2 concepts (7)

These ship after MVP is stable. Each entry is briefer; expand as you implement.

### `qualifying_surviving_spouse`

- **Category:** filing status — **Phase:** p2 — **Lifecycle:** fact
- **Rule:** A widow(er) with a dependent child can use MFJ rates for two years following the spouse's death, provided they paid more than half the cost of keeping up a home that was the child's main residence. IRC §2(a).
- **Predicates:** `spouse_died_within_n_years(filer, n)`, `has_dependent_child_in_home(filer)`, `has_not_remarried(filer)`, `paid_more_than_half_household_costs(filer, household)`.
- **Why it matters.** Almost never recognized. Filers often don't volunteer "my husband died last year" in an intake interview, and preparers don't ask. The window is two years and easy to miss.

### `mfj_vs_mfs`

- **Category:** filing status — **Phase:** p2 — **Lifecycle:** computed
- **Rule:** Married couples can choose joint or separate. MFS forfeits multiple credits (EITC, education credits, child and dependent care) and uses the worst rate brackets, but can be advantageous in narrow cases (large itemized medical for one spouse, income-based student loan repayment, liability separation).
- **Predicates:** `compute_tax_mfj(scenario)`, `compute_tax_mfs(scenario)`, `material_difference(a, b)`.
- **Why it matters.** New preparers default MFJ without considering MFS. The concept fires when the math actually flips, which forces engagement with the comparison.
- **Note:** This is a `computed` concept — needs `tax_core` to support full return computation under alternate filing statuses. Not implementable until that exists.

### `qualifying_child_age`

- **Category:** dependency — **Phase:** p2 — **Lifecycle:** fact
- **Rule:** Qualifying child must be under 19, OR under 24 and a full-time student for at least five months, OR permanently and totally disabled (no age limit). Separately, the Child Tax Credit cuts off at 17 — a 17-year-old can still be a dependent but loses CTC. IRC §152(c)(3); §24.
- **Predicates:** `child_age_test(child, year)`, `is_full_time_student(person, year)`, `is_permanently_disabled(person)`, `eligible_for_ctc(child, year)`.
- **Why it matters.** Two trap ages: 17 (loses CTC), 19 (loses qualifying-child status unless student or disabled). Players who know "under 19" miss the student extension; players who know "under 24 if student" miss the five-month rule.

### `qualifying_relative_support`

- **Category:** dependency — **Phase:** p2 — **Lifecycle:** fact
- **Rule:** Non-child dependents must pass: relationship or member-of-household-all-year, gross income under threshold (~$5,050 for 2024, indexed), support (taxpayer provided more than half), and not a qualifying child of another taxpayer. IRC §152(d).
- **Predicates:** `qualifying_relative_test`, `support_test`, `gross_income_test`, `relationship_test`, `member_of_household_test`.
- **Why it matters.** "Dependent" intuition defaults to children. Adult dependents (parents, siblings, adult children, unrelated household members) require explicit consideration. The gross income test is the most-missed condition.

### `tiebreaker_rules`

- **Category:** dependency — **Phase:** p2 — **Lifecycle:** fact
- **Rule:** When a child could be claimed by more than one taxpayer, statutory tiebreakers apply: parent over non-parent; if both parents, the one with whom the child lived longer; if equal, higher AGI. Special rule for divorced parents per IRC §152(e). IRC §152(c)(4).
- **Predicates:** `multiple_potential_claimants(child, scenario)`, `tiebreaker_resolve(claimants)`, `divorced_parents_rule(child)`.
- **Why it matters.** Divorced and multigenerational households trigger this regularly. New preparers either don't recognize the conflict or apply the wrong rule (often defaulting to "whoever the client says").

### `schedule_a_substantiation`

- **Category:** deductions — **Phase:** p2 — **Lifecycle:** fact
- **Rule:** Cash charitable contributions of $250+ require a contemporaneous written acknowledgment from the charity. Non-cash contributions over $500 require Form 8283. Non-cash over $5,000 requires a qualified appraisal. IRC §170(f)(8); §170(f)(11).
- **Predicates:** `charitable_contribution_total(filer)`, `has_receipt_for(contribution)`, `requires_8283(non_cash_contribution)`, `requires_appraisal(contribution)`.
- **Why it matters.** Players see a charitable contribution on the intake and enter it without checking substantiation. Concept fires when substantiation is borderline or missing — forces the player to ask "do you have receipts?"

### `hsa_eligibility`

- **Category:** deductions — **Phase:** p2 — **Lifecycle:** fact
- **Rule:** HSA contributions require the taxpayer to be enrolled in a qualifying high-deductible health plan (HDHP) and have no disqualifying coverage (Medicare, general-purpose FSA, spouse's non-HDHP plan). Contribution limits vary by self-only vs family coverage and include a $1,000 catch-up at 55+. IRC §223.
- **Predicates:** `is_hsa_eligible(person, year)`, `is_hdhp(coverage)`, `has_disqualifying_coverage(person)`, `hsa_contribution_limit(person, year)`.
- **Why it matters.** Players see HSA contribution and enter it without verifying coverage. Disqualifying coverage (especially spouse's plan) is the most-missed disqualifier. Medicare enrollment after age 65 silently disqualifies; clients don't realize.

---

## P3 concepts (deferred)

Not implemented in MVP or first round of P2. Listed so they aren't lost. Each is genuine — we're deferring for scope reasons, not because they don't matter.

### `eitc_qualifying_child_rules`

- **Category:** credits — **Phase:** p3 — **Lifecycle:** fact
- **Note.** EITC has its own qualifying-child definition that differs from §152. No support test. Different age rules. Different residency mechanics for divorced parents (Form 8332 doesn't transfer EITC). Worth its own concept and its own predicate set; conflating with `qualifying_child_residency` is wrong.

### `aotc_vs_llc`

- **Category:** credits — **Phase:** p3 — **Lifecycle:** computed
- **Note.** American Opportunity vs Lifetime Learning Credit trade-offs. AOTC is partially refundable, has a four-year limit, requires half-time enrollment. LLC is non-refundable, no enrollment requirement, available indefinitely. Concept fires when the player should have considered both.

### `premium_tax_credit_reconciliation`

- **Category:** credits — **Phase:** p3 — **Lifecycle:** fact
- **Note.** Form 8962. Marketplace coverage with advance PTC requires reconciliation against actual income. Repayment caps apply at low income. Common in VITA populations. Held to P3 because the form interaction is complex enough to warrant its own implementation pass.

### `ira_contribution_phaseout`

- **Category:** deductions — **Phase:** p3 — **Lifecycle:** fact
- **Note.** Traditional IRA deduction phases out based on MAGI when the filer or spouse is covered by a workplace retirement plan. Roth IRA contribution itself phases out at higher MAGI. Phaseout ranges differ by filing status and indexing. Mechanical once phaseout helpers exist.

### `claimed_status_diverges_from_truth`

- **Category:** filing status — **Phase:** p3 — **Lifecycle:** interview
- **Note.** Fires when the client's claimed filing status (in the interview) doesn't match what the facts actually support. This is the first `interview`-tier concept and requires the obfuscation layer to exist. Generalizes to claimed-vs-actual for any field, but starting with filing status because it's the most commonly miscoded.

### Other deferred items (unsorted, add detail when promoted)

- ACA shared responsibility (largely moot post-2018 federal penalty zero, but still relevant for state-level and prior-year amendments)
- IRA early-withdrawal penalty exceptions (medical, first-home, education)
- Saver's Credit eligibility
- Cancellation of debt (1099-C) income inclusion and exclusions
- Gambling income vs gambling loss treatment
- Foreign earned income exclusion (out of VITA scope, but EA-relevant)
- Net Investment Income Tax (Form 8960) — generally above VITA income range
- Kiddie tax (Form 8615)
- Qualified business income deduction (§199A) — out of basic VITA scope

---

## Predicate inventory for `tax_core`

Derived from the MVP and P2 concepts above. This is the work order for Restructure A's predicate implementation.

### MVP predicates (Restructure A first pass)

These are required for the six MVP concepts.

**Filing status family**
- `is_unmarried(filer, year)`
- `paid_more_than_half_household_costs(filer, household)`
- `has_qualifying_person_for_hoh(filer)`

**Dependency family**
- `qualifying_child_residency_test(child, year)`
- `qualifying_relative_test(person, household)` (HoH may invoke this)

**Income family**
- `total_income(person)`
- `total_self_employment_income(person)`
- `requires_schedule_se(person)`
- `compute_provisional_income(filer)`
- `ss_taxability_thresholds(filing_status, year)`
- `compute_taxable_ss(filer, year)`

**Threshold lookup**
- `filing_threshold_for(status, year)`

**Refundable credit eligibility (stub for MVP — full implementation in P2)**
- `qualifies_for_eitc(filer, year)` — can stub as "any qualifying child + earned income > 0" for MVP, expand later.
- `qualifies_for_actc(filer, year)` — similar.

**Deduction family** *(new — from `standard_vs_itemized`)*
- `standard_deduction_for(status, year)` — lookup by filing status.
- `compute_salt(state_tax, property_tax, year)` — applies SALT cap.
- `compute_medical_deduction(medical_expenses, agi)` — applies 7.5% AGI floor.
- `compute_itemized_total(household, year)` — aggregates Schedule A categories.
- `should_itemize(household, year)` — compares itemized vs standard.

Total: **18 predicates** for the MVP.

### Infrastructure predicates (Restructure A — existing code extraction)

These are not concepts (not drilled as learning objectives) but are tax-law functions that belong in `tax_core`. They exist today in `generator/expenses.py` and `generator/models.py` and must move during Restructure A. Concepts and the grader consume them.

**Filing status derivation** *(currently `Household.derive_filing_status()` in `generator/models.py`)*
- `derive_filing_status(household)` — determines Single / MFJ / MFS / HoH / QSS from household composition. Currently a simplified version (married → MFJ, has children → HoH, else single). Will be refined as concepts like `hoh_qualifying_person` and `mfj_vs_mfs` are implemented. The `Household` method becomes a thin wrapper that delegates to `tax_core`.

**State income tax computation** *(currently in `generator/expenses.py`)*
- `compute_state_income_tax(income, filing_status, state, year)` — progressive bracket calculation. Currently hardcoded to Hawaii (`HAWAII_TAX_BRACKETS_SINGLE`, `HAWAII_TAX_BRACKETS_MFJ`). Moves to `tax_core/state_tax/hawaii.py` with a dispatch function that selects the correct state module. State-specific tax law is still tax law.

**Threshold constants** *(currently module-level constants in `generator/expenses.py`)*
- `STANDARD_DEDUCTION` by filing status and year
- `SALT_CAP` by year (currently $10,000)
- `IRA_CONTRIBUTION_LIMIT` / `IRA_CONTRIBUTION_LIMIT_50_PLUS` by year
- `STUDENT_LOAN_INTEREST_LIMIT` by year (currently $2,500)
- `EDUCATOR_EXPENSE_LIMIT` by year (currently $300)

All move to `tax_core/thresholds.py` as year-indexed lookups. The expense generator imports them from `tax_core` instead of defining them locally. One module, one source of truth.

**Above-the-line deduction caps** *(logic currently in `generator/expenses.py`)*
- Student loan interest, educator expense, and IRA contribution caps are applied during generation but are tax-law limits. The cap-checking logic moves to `tax_core`; the random-amount generation stays in `intake`.

### P2 predicates (Restructure D second pass)

Adds the seven P2 concepts.

- `spouse_died_within_n_years(filer, n)`
- `has_dependent_child_in_home(filer)`
- `has_not_remarried(filer)`
- `compute_tax_mfj(scenario)` *(computation, not predicate)*
- `compute_tax_mfs(scenario)` *(computation)*
- `child_age_test(child, year)`
- `is_full_time_student(person, year)`
- `is_permanently_disabled(person)`
- `eligible_for_ctc(child, year)`
- `support_test(person, household)`
- `gross_income_test(person, year)`
- `relationship_test(person, householder)`
- `member_of_household_test(person, household, year)`
- `multiple_potential_claimants(child, scenario)`
- `tiebreaker_resolve(claimants)`
- `divorced_parents_rule(child)`
- `charitable_contribution_total(filer)`
- `has_receipt_for(contribution)`
- `requires_8283(non_cash_contribution)`
- `requires_appraisal(contribution)`
- `is_hsa_eligible(person, year)`
- `is_hdhp(coverage)`
- `has_disqualifying_coverage(person)`
- `hsa_contribution_limit(person, year)`

Total: **24 additional predicates** for P2.

### Shared infrastructure

- Threshold tables by year (filing thresholds, gross-income thresholds, HSA limits, IRA limits, SS wage base). One module, one source of truth.
- Year parameter on every predicate. Tax law changes annually; predicates that hard-code constants will silently produce wrong answers next year.
- Rich result objects vs booleans: predicates with multiple failure modes (e.g., `qualifying_child_residency_test`) return structured results so the slot layer and grader can both inspect *why*. Boolean predicates are fine where the answer is genuinely binary.

---

## How to add a new concept

1. **Confirm it isn't already covered.** Search this doc and the deferred list. Many "new" concepts are special cases of existing ones.
2. **Write the entry first.** Before implementing, draft the catalog entry. The act of writing "rule tested" and "why it matters" exposes whether the concept is well-defined.
3. **Identify the predicates.** List what `tax_core` functions the `matches()` would call. If the predicates don't exist, that's a separate work item.
4. **Tag the phase.** Be honest. New concepts default to P2 unless they're blocking the MVP.
5. **Implement the predicates first**, in `tax_core`, with unit tests. Concept implementations are mechanical once predicates work.
6. **Implement the concept** in `learn/concepts/`, with tests confirming it matches positive scenarios and rejects negative ones.
7. **Update this doc** with implementation notes, edge cases discovered, predicate refinements.

---

## References

These are the canonical sources. When in doubt, read these, not blog posts.

- **IRS Publication 17** — General individual tax overview. Updated annually.
- **IRS Publication 501** — Filing status, dependents, exemptions.
- **IRS Publication 525** — Taxable and nontaxable income.
- **IRS Publication 596** — EITC.
- **IRS Publication 915** — Social Security and equivalent railroad benefits.
- **IRS Publication 970** — Tax benefits for education.
- **IRS Publication 4012** — VITA/TCE Volunteer Resource Guide.
- **IRC Title 26** — The actual statute. Look up the section the publication cites when the publication's wording is ambiguous.
- **Treasury Regulations** — Where the statute is silent. Cited as 26 CFR §X.XXX-X.

For EA Part 1 specifically: Pub 17 + Pub 501 + Pub 596 + Pub 970 covers most of the individual tax surface. The Gleim and Surgent EA review materials map to these publications closely.
