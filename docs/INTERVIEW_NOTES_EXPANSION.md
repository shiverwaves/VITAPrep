# Interview Notes Expansion Plan

This plan replaces the placeholder "Future: 13614-C Pages 2–3 Interview Notes" section in [`BUILD_PLAN.md`](./BUILD_PLAN.md). It covers boilerplate notes for Pages 2–3, deferred questions, the rendering-negatives principle, and how the work serves both Intake and Verify gameplay loops.

> **Cross-references:** [`SCENARIO_LIFECYCLE.md`](./SCENARIO_LIFECYCLE.md) for the obfuscation layer (Stage 6). [`CONCEPT_CATALOG.md`](./CONCEPT_CATALOG.md) for the predicates that may eventually be triggered by these notes.

---

## Background

The current MVP renders interview notes for Page 1 of the 13614-C (citizenship, filing status, dependents) only. Pages 2 (income) and 3 (expenses, life events) are absent — the player sees income and expense documents but is never "asked" the corresponding intake questions. In a real VITA encounter, the client has filled the left column of all three pages before the volunteer sits down; the volunteer's job is to verify that attestation against documents.

This plan adds boilerplate notes for the questions on Pages 2–3 whose answers can already be derived from generated household data. Out-of-scope questions are documented so they aren't lost when generators eventually expand to cover them.

---

## What boilerplate notes are doing in MVP

Boilerplate notes are the **direct ground-truth surfacing layer**. They state, in plain client-voice prose, what the generated facts are. The player sees them as the simulated client's answers to the volunteer's intake questions.

Until the obfuscation layer (Restructure C2) is wired into the player UI, boilerplate notes and documents will agree by construction — both reflect the same generated facts. That's correct for MVP. The pedagogically interesting case (interview and documents intentionally disagreeing) is what the obfuscation layer exists to introduce. Boilerplate is the deterministic baseline that obfuscation later perturbs.

One implication for implementation: boilerplate notes should read as client speech, not as database rows. "No, I don't think so" or "No, I didn't have any of those" beats a bare "No." These remain deterministic — pick a randomized phrasing per render from a small set — but preserve the interview panel's client-voice quality.

## Render every in-scope question, including negatives

A real 13614-C is filled in by the client before the volunteer arrives. Every left-column question has an answer; "No" is just as much an answer as "Yes." A simulated client whose interview panel only contains positive answers is acting unlike a real client.

More importantly, a player who only ever sees positive notes never develops the habit of *checking that every question on the form was considered*. They'll match documents to questions that appeared, but never notice that a question on the form is unaddressed. Rendering negatives teaches the player that "the volunteer asked, the client said no, and that question is closed" — distinct from "the volunteer never asked, the question is open."

**Policy:** every in-scope question renders, regardless of whether the answer is positive or negative. Difficulty is not controlled by withholding boilerplate — boilerplate is ground-truth. Difficulty comes from the obfuscation layer when it's introduced (intentional disagreement between client claim and documents) and from the complexity of the generated scenario itself.

A small style note: negative renders should sound like client speech, as above. "No, I don't think so." "No, I didn't have any of those." Pick weighted-randomly from a phrasing pool per question. This is free to do correctly from the start and avoids a refactor later.

## Relationship to the obfuscation layer (Restructure C2 and beyond)

Boilerplate notes establish *what the client truthfully said*. The obfuscation layer in C2 onward wraps boilerplate and slot-rendered notes in additional narrative variation, and eventually introduces the *intentional disagreement* cases that real VITA encounters produce: a client who says "no" to interest but has a 1099-INT in the pile; a client who says "yes" to charitable contributions but brought no receipt; a client who claims an HSA but is on Medicare. None of those scenarios can be authored without a boilerplate baseline — you can only obfuscate or perturb what's been stated.

This sequencing also explains why difficulty doesn't gate boilerplate: the obfuscation layer is where difficulty lives, and the obfuscation layer needs the baseline to operate on.

---

## In-scope: 13 boilerplate notes across Pages 2–3

These are the questions whose answers can be derived from existing generator output (with minor extensions noted per subset).

Each note follows the **Yes/No + detail** pattern. Yes/No comes first as a separate `InterviewNote` instance. When the answer is "Yes," a follow-up `InterviewNote` provides the count or amount. This mirrors the actual flow of a 13614-C intake — the volunteer asks the question, the client answers, the volunteer asks the follow-up.

Example shape (household with two W-2s, total $58,000):

```
InterviewNote(category="income", question="Did you receive wages as a part-time or full-time employee?",
              answer="Yes", source_slot=None)
InterviewNote(category="income", question="How many jobs?",
              answer="2", source_slot=None)
```

For a household with no wages:

```
InterviewNote(category="income", question="Did you receive wages as a part-time or full-time employee?",
              answer="No, I didn't work this year.", source_slot=None)
```

(No follow-up is rendered when the primary answer is "No.")

---

### Subset 1: Wage and self-employment income (3 notes)

Bundles with any Sprint 9 generator refinements still pending.

| 13614-C Question | Generator field | Detail follow-up |
|---|---|---|
| Wages as part-time or full-time employee | `wage_income`, `len(w2s)` | "How many jobs?" -> count of W-2s |
| Self-employment payments | `self_employment_income`, count of 1099-NECs | "What kind of work?" -> occupation_title |
| Disability benefits (insurance, worker's comp) | `disability_income_source` on Person | "W-2 or 1099-R?" -> document type |

**Generator work in this subset:**
- **Disability (resolved):** The 13614-C asks about "disability benefits (payments from insurance and worker's compensation)" with the volunteer column specifying "on W-2 or 1099-R." SSDI is covered by the separate Social Security row (SSA-1099/RRB-1099). These are two distinct questions, two distinct reporting paths.
  - **MVP scope: employer-paid short/long-term disability on W-2 only.** Model a person with `has_disability is True` who isn't currently working but has a W-2 from employer-paid disability insurance. Worker's comp adds complexity (separate document, usually nontaxable, poorly categorized) — defer. Disability pensions on 1099-R are a less common VITA scenario — defer.
  - **Implementation:** Add `disability_income_source: Optional[str]` to Person (value `"w2"` for MVP). Set at low frequency when `has_disability is True` and the person has wage income but `employment_status != EMPLOYED`. The boilerplate renders "Yes" and the follow-up is just the dollar amount — the form doesn't ask the volunteer to decompose disability vs regular wages. The W-2 itself carries whatever breakdown the employer provides.
  - **No grader change needed.** The disability flag affects the interview note; the income amount is already on the W-2 and already graded.
- The SE follow-up ("What kind of work?") uses `occupation_title` verbatim — it's already client-voice phrasing from Faker.

---

### Subset 2: Passive income (4 notes)

Mostly mechanical against existing generator output.

| 13614-C Question | Generator field | Detail follow-up |
|---|---|---|
| Retirement account, pension, annuity proceeds | `retirement_income`, count of 1099-Rs | "How much, roughly?" -> rounded amount |
| Social Security or Railroad Retirement | `social_security_income`, SSA-1099 presence | "Roughly how much?" -> rounded amount |
| Interest or dividends | `interest_income`, `dividend_income`, 1099-INT/DIV count | "Roughly how much?" -> rounded total |
| Any other money received during the year | TBD — depends on whether catch-all is implemented | "What kind?" |

**Generator work in this subset:** none required for the first three. The fourth ("any other money") is a catch-all on the form. If the generator doesn't produce miscellaneous income, render "No" and note this as a permanent "No" pending generator expansion.

---

### Subset 3: Schedule A items (4 notes)

| 13614-C Question | Generator field | Detail follow-up |
|---|---|---|
| Mortgage interest | `mortgage_interest`, Form 1098 | "Roughly how much?" -> rounded amount |
| Taxes (state, local, real estate, sales) | `state_income_tax`, `property_taxes` | "What kinds?" -> enumerate |
| Medical, dental, prescription expenses | `medical_expenses` | "Roughly how much?" -> coarse bin label |
| Charitable contributions | `charitable_contributions` | "Roughly how much?" -> rounded amount |

**Generator work in this subset:**
- **Medical expenses (resolved):** Always-generate. Most households produce small amounts ($100–$800 range) that don't clear the 7.5% AGI floor. The existing high-amount logic (exponential draw above floor) stays for elderly/disabled cases. This teaches the player to recognize "yes there are medical expenses, no they don't deduct" — a pattern they'll see constantly at real VITA sites. The boilerplate follow-up renders coarsely using bin labels ("a few hundred dollars", "a couple thousand", "around ten thousand") rather than exact amounts. This signals magnitude without forcing mental math on whether to itemize.
- **Charitable split (resolved — deferred):** Skip the cash/items split. Follow-up is "Roughly how much?" The split becomes load-bearing when `schedule_a_substantiation` concept is implemented (P2 in catalog) — the predicate fires on cash ≥ $250 without receipt, or non-cash ≥ $500 without Form 8283. At that point, add `charitable_cash` and `charitable_noncash` to Household plus a `has_receipt` flag. Until then, a single amount with no type distinction is correct.

---

### Subset 4: Above-the-line deductions and credits (3 notes)

Mostly mechanical.

| 13614-C Question | Generator field | Detail follow-up |
|---|---|---|
| Student loan interest | `student_loan_interest`, Form 1098-E | "Roughly how much?" -> amount |
| Contributions to a retirement account | `ira_contributions`, `ira_type` | "Traditional or Roth?" -> type |
| School supplies (educator expense) | `educator_expenses` | "Roughly how much?" -> amount |

**Generator work in this subset:**
- **IRA type (resolved):** Add `ira_type: str` to Person with values `"traditional"`, `"roth"`, or `"both"`. The 13614-C asks the question because the answer changes the return — Traditional adjusts AGI, Roth doesn't. A player who sees IRA contributions without the type distinction has been taught the wrong lesson. Weight by income tier: Traditional at lower incomes (where the deduction matters), Roth at higher incomes (where phase-outs kill the Traditional deduction anyway). The full phase-out logic is a `tax_core` predicate concern (`traditional_ira_deduction_phaseout`) and doesn't need to exist for the boilerplate to be correct — the boilerplate just states what the client contributed and what type. The form populator routes Traditional → Schedule 1, Roth → not deducted.

---

### Subset 5: Education and child care (2 notes)

| 13614-C Question | Generator field | Detail follow-up |
|---|---|---|
| Educational classes (technical school, college, job-related) | `education_expenses`, Form 1098-T | "Who took the classes?" -> primary filer / spouse / dependent |
| Child and dependent care | `child_care_expenses` | "Roughly how much?" -> amount |

**Generator work in this subset:**
- **Education (resolved):** The `is_full_time_student` flag now works correctly on Person (set via PUMS enrollment rates in `children.py`). The "who took the classes" follow-up reads from the Person who has the 1098-T — already tracked by `_create_expense_documents` which issues the 1098-T to the actual enrolled student. No generator gap remains.
- **Child care (resolved):** `child_care_expenses` is generated on Household for households with children under 13 and working adults, firing ~65% of the time for qualifying households. Renders as "No" when zero (household doesn't qualify or probability didn't fire). No generator gap.

---

## Out-of-scope: Pages 2–3 questions deferred for generator work

These questions exist on the 13614-C and matter pedagogically but cannot be answered from current generator output. They should be addressed when the corresponding generator capability is added.

### Page 2 — Income

| 13614-C Question | Why deferred |
|---|---|
| Tips | Tip income not generated. |
| Unemployment benefits | 1099-G not generated. |
| Refund of state/local income tax | No prior-year state refund tracking. The "itemized last year" follow-up is a prior-year dependency — state refund taxability depends on whether state tax was deducted on Schedule A last year (tax-benefit rule). Requires prior-year infrastructure, not just a generator extension. |
| Sale of stocks, bonds, real estate | No 1099-B, no Schedule D generation. Note: the "did you report a loss last year" follow-up is an audit-trigger question — it gates whether carryover Schedules apply. Same pattern as SE loss below. |
| Alimony received | Not generated. |
| Rental income (real or personal property) | Not generated. Note: the "personal use / rented fewer than 15 days" follow-up is an audit trigger for material participation and Schedule E applicability. |
| Gambling winnings | Not generated. |
| Did you report a loss last year (SE) | Requires prior-year return data. This is an audit-trigger follow-up — it gates whether prior-year carryovers affect the current return. Same pattern appears under Sale of stocks and Rental. When these generators come online, the follow-up pattern is consistent: the question gates whether a more-complex Schedule applies. |

### Page 3 — Adjustments and credits

| 13614-C Question | Why deferred |
|---|---|
| Alimony paid | Not generated. |

### Page 3 — Life events

| 13614-C Question | Why deferred |
|---|---|
| Sale of home | Not generated. Form 1099-S absent. |
| HSA contributions / distributions | **Pedagogically high value** — connects to `hsa_eligibility` concept (P2 in catalog). High priority once generator extends. |
| Marketplace insurance (1095-A) | Not generated. |
| Energy-efficient home items | Not generated. |
| Other (vehicle, etc.) | Not generated. |
| Cancelled debt (1099-C) | Not generated. |
| Disaster loss area | Not generated. |
| Tax credit disallowed in a previous year | Requires prior-year disallowance tracking. |
| Estimated tax payments / prior year refund applied | Requires prior-year tax data. |

### Page 3 — Procedural questions (no data needed)

These don't depend on generator state but also don't currently fit boilerplate.

| 13614-C Question | Notes |
|---|---|
| Receive any letter or bill from the IRS | Procedural — the volunteer always asks. Candidate for a future coaching script rather than a boilerplate note. |
| Brought last year's return | Same — procedural, not data-driven. |

When generators eventually cover these (HSA likely first, given its concept-catalog connection), the corresponding boilerplate note becomes a follow-on subset using the same Yes/No + detail pattern.

**Note on prior-year dependencies:** Several deferred questions share a common infrastructure requirement — prior-year return data. State refund taxability (tax-benefit rule), SE/capital loss carryovers, and "did you itemize last year" follow-ups all need the system to know what happened on last year's return. This is its own infrastructure concern (a prior-year context model), not just a set of generator extensions. When prior-year tracking is eventually designed, multiple deferred questions become unblocked simultaneously.

---

## Implementation order

The five subsets are independent and can ship in any order, but bundling generator work with the corresponding boilerplate is the point. Suggested sequencing:

1. **Subset 2 (passive income)** first — most mechanical, fewest generator gaps, validates the implementation pattern.
2. **Subset 1 (wage/SE)** — most pedagogically central; players see W-2s and 1099-NECs constantly and need the corresponding intake questions.
3. **Subset 3 (Schedule A items)** — small generator decisions to make (medical, charitable cash/items split).
4. **Subset 4 (above-the-line)** — IRA Traditional/Roth decision, otherwise mechanical.
5. **Subset 5 (education)** — child/dependent care is a real generator gap; do this last so the gap can be addressed deliberately.

Each subset is shippable as its own PR with its own tests.

---

## Implementation notes

For each subset:

1. Add `_<subset>_notes(household)` function to `intake/boilerplate.py`. Returns a list of `InterviewNote` instances.
2. Wire into `generate_boilerplate()` so the notes appear in `scenario.interview_notes` alongside existing Page 1 notes.
3. Update the form populator to pre-fill the corresponding form sections from the generated data (this should already work for Sprint 9/12 forms; the boilerplate layer is the new addition).
4. Add unit tests covering positive and negative answer cases for each note.
5. Update the UI to group notes by category (`citizenship`, `filing`, `dependent`, `income`, `expenses`) with section headers matching 13614-C pages. The category labels already exist on `InterviewNote`.

---

## Two gameplay loops, one boilerplate layer

VITAPrep supports two complementary gameplay loops, both of which consume the same generated scenario and the same boilerplate notes. They differ in what the player does with that material.

### Intake loop (data entry and discovery)

The player receives a scenario, reads the documents and interview notes, and fills the form from blank. Their job is to *transcribe and verify* — extract the right values from the right sources, recognize when the interview notes and documents agree, flag when they disagree.

This is the loop most of the existing build plan addresses. The player is the volunteer who took the intake and is doing the prep.

### Verify loop (peer review of pre-filled forms)

The player receives a scenario where the form is *already filled in* — possibly correctly, possibly with introduced errors, possibly clean. Their job is to *audit* — walk the form against the documents and interview notes, identify any discrepancies, confirm correct entries.

This mirrors the Quality Review role at a real VITA site, where a second volunteer reviews the prep before the return is filed. It's the same skill set as Intake but inverted: instead of producing an answer, you're checking one. Some players will find Verify easier (less hunting for data); others will find it harder (you have to scrutinize every entry, not just the ones you noticed).

Both loops share the same machinery: same generator, same documents, same boilerplate, same ground truth. The Verify loop is implemented as Restructure-B-style corruption: take the answer key, perturb selected fields per difficulty, present the perturbed form. ~15% of Verify scenarios should have **no errors at all** — a real Quality Review sometimes confirms a clean prep, and the player needs to be willing to declare a return correct rather than always assume something must be wrong.

### Why the boilerplate layer matters for both

In Intake, boilerplate notes give the player the client's stated answers. They check those against documents and enter the result.

In Verify, boilerplate notes give the player the client's stated answers. They check those against the *pre-filled form* and against documents, looking for three failure modes: form entry doesn't match document, form entry doesn't match interview, document doesn't match interview.

Without complete Page 2–3 boilerplate, the Verify loop has a gap: the player can audit form entries against documents but cannot audit them against interview answers, because the interview is silent on income and expenses. Adding boilerplate closes the gap for both loops in one motion. Verify benefits as much as Intake from this work, possibly more — the audit role is exactly where the volunteer is asked to compare interview against form.

### Verify-specific concerns (deferred to a separate sprint)

The corruption strategy for the Verify loop — what kinds of errors are introduced, at what frequency, and how the grader scores audit submissions — is its own design problem. This expansion plan does not solve it. What it does is ensure the boilerplate baseline exists so Verify-mode corruption has a complete surface to perturb.
