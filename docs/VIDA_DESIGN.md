# Vida Design Notes

> **Status:** Pre-implementation sketch. Vida is not in MVP scope. This document captures the design space discussed during architecture planning so the choices are recorded when implementation is eventually scheduled.
>
> **Companion documents:** Vida consumes [`SCENARIO_LIFECYCLE.md`](./SCENARIO_LIFECYCLE.md) (scenario state), [`CONCEPT_CATALOG.md`](./CONCEPT_CATALOG.md) (what concepts exist), [`INTERVIEW_NOTES_EXPANSION.md`](./INTERVIEW_NOTES_EXPANSION.md) (the boilerplate baseline procedure scripts walk over), and the predicate library in `tax_core` (the source of tax-law truth). Vida adds nothing to those layers; she surfaces what they already know.

---

## Persona (locked)

Vida is the in-product avatar for VITAPrep — a Latina VITA site coordinator who guides the player through scenarios. Warm, capable, bilingual-coded, experienced. Plays the role a senior preparer plays at a real VITA site: over-the-shoulder presence who knows the procedure, knows the rules, has seen every common mistake, and helps without doing the work for the player.

Persona is fixed. What needs designing is her behavior — when she speaks, what she says, how players invoke her, how she changes as players improve.

---

## Core principle: Vida surfaces, never invents

Vida has no independent knowledge of tax law. Every fact she states traces to either:

- A predicate in `tax_core`, with its IRC citation and publication reference.
- A scenario field (ground truth, household composition, document content).
- A coach-script or procedure-script template authored by humans.

When a player asks "why does HoH require more than half the year?" Vida doesn't reason about it. She reads the predicate's docstring and the cited Pub 501 excerpt and presents that material in conversational form. The engine owns truth; Vida owns voice.

This rule is non-negotiable. Violating it produces the failure mode where Vida confidently states tax law that's wrong, undermining the trust the rest of the product earns. Every Vida-related design decision should be checkable against this principle: *is Vida sourcing this from `tax_core`, scenario state, or a human-authored script?* If the answer is "she's generating it," the design is wrong.

---

## What Vida actually does: two jobs, one workflow engine

Vida's behavior decomposes into two distinct jobs that share infrastructure but differ in trigger.

### Coach (reactive)

Catches mistakes and omissions. Fires in response to player behavior: a stuck pause, a skipped field, a wrong submission, a too-fast click-through. The player is doing something; Vida intervenes when the something is wrong or about to be.

Coach scripts are deterministic event handlers. Each script has a trigger predicate over player state and 3-6 response variants. Examples:

- `intake_completeness_check` — fires when a section is submitted with required fields blank.
- `document_reconciliation` — fires when a section is marked complete but a document in the pile wasn't referenced.
- `citizenship_first` — fires when filing status is filled before citizenship is recorded.
- `pacing_caution` — fires when a section is completed in under 30 seconds.
- `dependent_residency_check` — fires when a child is claimed without residency being verified.

A starter catalog of 8-12 scripts covers the common procedural failure modes. Catalog grows over time as new patterns surface.

### Tutor (proactive)

Walks the player through the workflow step by step. Fires when the player explicitly requests guidance ("what do I do next?"), when they're stalled, or when tutorial mode is active.

Tutor logic is a procedure script — an ordered list of steps with completion checks. The current step is the first step whose completion check fails. Each step has Vida-voiced introduction text and stuck-text. The procedure script is stateless; player state determines current step.

Steps can express prerequisites ("compute_agi requires intake_complete, income_recorded, adjustments_recorded") so non-linear play still produces the right "what's next" answer — Vida always volunteers the first step whose prerequisites are met and whose completion check fails.

---

## The workflow engine

Coach and Tutor sit on top of the same primitive: a workflow engine that knows the procedure and tracks where the player is in it. The engine is the architectural foundation; coach and tutor are policies that consume it.

### What the engine is

A small piece of `learn` that maintains, per scenario:

- Which procedure is active (Intake / Verify / Prep — see "Three loops, three procedures" below).
- Which step is current (the first whose prerequisites are met and whose completion check fails).
- Player state — fields filled, time elapsed, recent submissions, which coach scripts have fired this scenario.

That's it. The engine doesn't render anything; it answers questions like "what's the next step?" and "is this step complete?" Coach scripts (which fire on triggers) and tutor scripts (which surface the current step) both read from it.

### Why this is the right architectural primitive

Workflow ordering is a **presentation concern, not a generation concern.** VITAPrep generates the same scenario data regardless of how the player will be guided through it. The workflow engine decides how to reveal it. Same scenario, three modes (tutorial / practice / solo), three reveal patterns — all sitting on top of one set of generated facts.

The `category` field already on every interview note is the substrate: notes are grouped by category, categories map to procedure steps, steps have completion signals. The infrastructure for grouping and ordering is largely in place; the gap is the engine that walks it and the "what's next" logic that answers Vida's queries.

### Three loops, three procedures

VITAPrep supports three distinct gameplay loops. The workflow engine serves all three with the same machinery and different procedure-script content.

**Intake loop (data entry and discovery).** Player receives a scenario, reads documents and interview notes, fills the form from blank. Procedure script: 13614-C intake, six steps (see below). Vida walks the player through identity -> filing status -> dependents -> income -> expenses -> credits.

**Verify loop (peer review).** Player receives a scenario where the form is *already filled in* — possibly correctly, possibly with introduced errors, possibly clean. Their job is to audit. Procedure script: Quality Review, walking the form against documents and interview notes section by section, looking for three failure modes (form vs document, form vs interview, document vs interview). Mirrors the Quality Review role at a real VITA site, where a second volunteer reviews the prep before the return is filed. ~15% of Verify scenarios have no errors at all — the player must be willing to declare a return correct rather than always assuming something is wrong.

**Prep loop (1040 preparation, future product).** Player computes the return from intake data. Procedure script: gather data -> AGI -> adjustments -> deductions -> tax -> credits -> payments -> refund. Lives in VITAPrep proper, not the current intake-focused product. Same workflow engine, different content.

That all three loops use the same engine is the architectural reason to build the engine cleanly rather than as a one-off intake feature. Once it works for Intake, Verify is a content addition; once Verify works, Prep is the same.

### The intake procedure (six steps)

For the Intake loop specifically, the procedure script walks the 13614-C in this order. Each step has a clear input (interview-note category + corresponding documents), action (fill the relevant form section), and completion signal (that section graded correctly).

1. **Identity & citizenship** — verify ID documents, confirm SSN, citizenship status. Inputs: `citizenship` and `contact` notes, SSN cards, IDs.
2. **Filing status** — marital status, determine correct filing status. Inputs: `filing` notes.
3. **Dependents** — qualifying child/relative tests, months in home, student status. Inputs: `dependent` notes, dependent SSN cards.
4. **Income** — walk through each income type, match to documents. Inputs: `income` notes, W-2s, 1099-Rs, SSA-1099s, 1099-INTs, 1099-DIVs, 1099-NECs.
5. **Expenses & deductions** — itemized vs standard, above-the-line deductions. Inputs: `expenses` notes, Form 1098s.
6. **Credits & other events** — education credits, child care credit, prior-year items. Inputs: `expenses` notes (life-events portion).

The procedure ends at step 6 with intake complete. It does not include "compute refund" — that's a Prep procedure step, in the Prep loop. It does not include "verify entries" as a final review — that's the *Verify procedure*, which is its own loop, not a step within Intake.

### The Verify procedure (separate loop, separate procedure script)

The Verify loop runs when the player is auditing a pre-filled form rather than filling one from blank. It walks the same six form sections in roughly the same order, but the action at each step differs: instead of "fill from interview + documents," the action is "compare form entry to interview, compare form entry to documents, flag any discrepancy or confirm correct." A Verify procedure script lives alongside the Intake script in `learn`, sharing all the same step structure and most of the completion checks but with audit-specific Vida-voiced text and audit-specific coach scripts (e.g., "you confirmed Part II without flagging anything — are you sure every line matches the interview?").

The Verify-mode corruption strategy — what kinds of errors are introduced, at what frequency, how the audit submission is graded — is a separate design problem covered in the Verify Mode design (forthcoming). This document only specifies that the workflow engine is the same.

---

## Response tiers

Three tiers of how Vida produces her words. MVP uses tiers 1 and 2 only.

### Tier 1: Canned variants

Each coach script and procedure step has 3-6 prewritten lines covering different tones and situations. Picked round-robin or weighted-random to avoid repetition. Pure templates with `{player_name}`, `{client_name}`, etc. substituted. No AI.

This tier covers most of what Vida says. Cheap, debuggable, predictable.

### Tier 2: Templates with structured content

Templates pull scenario-specific facts in to make the response feel personalized. Example post-grading explanation:

> "You marked {client.first_name} as a qualifying child, but she only lived with you {child.months_in_home} months. The residency test ({predicate.citation}) requires more than half the year."

Still deterministic — the template renders against ground truth and predicate results. No AI. Feels personalized because it cites this exact scenario's facts.

### Tier 3: AI-generated free-form responses

Player asks an open-ended question Vida doesn't have a canned response for. An LLM with constrained context (current scenario, ground truth, relevant predicate citations, IRS publication excerpts) generates a reply.

Critical constraint: the LLM is given the answer and asked to *explain* it. Never asked to *compute* it. The deterministic system computes; the LLM voices.

**Deferred from MVP.** Tier 3 is impressive in demos, expensive to get right, and the most common source of "AI made up tax law" failures. Tiers 1 and 2 cover the procedural-fluency case completely. Add tier 3 only after extensive use of tiers 1 and 2 reveals it's needed and after the safeguards (citation-checking, refusal patterns, escalation paths) are designed.

---

## Modes

Three modes controlling how aggressively Vida's scripts fire. Player-toggleable; system-defaulted by competence rating.

### Tutorial

Vida proactively walks the procedure. Procedure scripts run heavily; coach scripts can be quieter (less reactive nudging needed when she's actively guiding). Default for new players or unfamiliar form sections.

Useful framing: tutorial mode is "step-by-step reveal" — Vida walks the player through one category at a time, and the next category isn't surfaced until the current one is complete. The form sections may all be visible, but Vida's attention (and her nudges) are scoped to the current step. Brand-new VITA volunteers who have never done a live intake benefit most from this.

### Practice

Vida is silent unless asked or until something needs catching. Coach scripts fire on omissions and mistakes; procedure scripts available on demand if the player clicks "what should I do next?" The default mode for the bulk of play.

Useful framing: practice mode is "all sections visible, all coach scripts active." The player owns the flow; Vida intervenes when they stall or err. Useful for volunteers who know the rules but lose track during a complex scenario.

### Solo

Vida is fully silent. No coach, no procedure. Player completes the scenario from scratch and only sees Vida at grading. For experienced players testing themselves on familiar concepts.

Mode applies per scenario or per form section, not globally. A player can be solo-confident on Part I while still wanting tutorial-mode guidance on Part III.

---

## Competence rating

The system's per-concept (or per-section) read of player skill, used to default mode appropriately and to power eventual progression elements.

Signals composed into the rating:

- Grading accuracy on a concept over the last N attempts (strongest signal)
- Coach-script firing rate (high firing + correct answers = correct because of nudges, not skill)
- Time-to-completion (fast and correct = mastery; fast and wrong = rushing)
- Self-toggle history (toggling to harder modes signals confidence)

Closer to Elo than to XP — drifts up with mastery, down with slips. XP-style "only goes up" doesn't match how skill actually works.

Default mode for a loaded scenario is the lowest competence level among the concepts the scenario tests. Player can override. The rating is also the substrate for any future RPG layer (specialization trees, boss-fight selection, progression unlocks) — those features visualize the rating; they don't replace it.

---

## What's not in scope here

The following come up when discussing Vida and are deferred:

- **RPG meta-game** (recurring clients, building a practice, specialization trees). Sits on top of competence ratings. Separable from Vida proper.
- **Tier 3 AI inference.** Documented in tiers above as deferred.
- **Voice/audio.** Vida is text-only for MVP. Voice acting is an aesthetic choice, not an architecture decision.
- **Spanish-language scripts.** The persona is bilingual-coded; whether the product actually supports Spanish UI is a localization question, separate from Vida's design.
- **Vida-as-narrator-for-non-Vida content.** Tempting to make Vida the voice of system messages ("Scenario generated"), error states, etc. Don't. Keeps her contextual and prevents her from becoming wallpaper.
- **Verify-mode corruption strategy.** What kinds of errors are introduced, at what frequency, how audit submissions are graded. The workflow engine serves the Verify loop the same way it serves Intake; the corruption-and-grading mechanics are a separate design surface.

---

## Prerequisites

Two prerequisites before Vida implementation can usefully begin.

1. **Interview-notes expansion through Subset 5.** The Intake procedure script's steps 4-6 (income, expenses, credits) walk the player through interview content that doesn't currently exist for Pages 2-3 of the 13614-C. Without that content, the procedure script walks through three empty steps in the middle. See [`INTERVIEW_NOTES_EXPANSION.md`](./INTERVIEW_NOTES_EXPANSION.md). Vida implementation can begin in parallel with later subsets but cannot complete before Subset 5 ships.
2. **Restructure E complete.** The competence rating signal "grading accuracy on a concept" requires concept tagging from Restructure D, and concept-driven scenario selection requires the targeting from E. The earlier Vida sub-features (player state model, coach scripts, tutorial procedure script) can land before E; competence-driven mode defaulting cannot.

---

## Build order (when this becomes in-scope)

The smallest viable Vida is smaller than it looks. The order:

1. **Player state model.** Track which scenario, section, fields filled, time elapsed, recent submissions. Most of the value of an "AI tutor" is just *having* this state model — most existing tools don't.
2. **Workflow engine.** Procedure-script type system, current-step resolution, prerequisite handling. No content yet — the engine accepts a procedure script and answers "what's next." Initially serves the Intake procedure only.
3. **Coach script framework.** Trigger-and-response infrastructure plus a starter catalog of 8-12 scripts. Covers reactive nudging.
4. **Tier 1 + tier 2 response renderer.** The voicing layer that takes a script's chosen variant and renders it with substitutions.
5. **Procedure script for 13614-C Intake.** First proactive walkthrough, six steps, covering intake end to end.
6. **Mode toggle.** Tutorial / practice / solo selector. Initially manual, no auto-defaulting.
7. **Procedure script for Verify loop.** Adds the Quality Review walkthrough using the same engine and similar step structure but audit-specific text and coach scripts. Depends on Verify-mode corruption strategy being designed (separate doc).
8. **Competence rating.** Per-concept and per-section. Begins driving auto-default for mode.
9. **(Later) Procedure script for 1040 Prep.** When VITAPrep proper exists. Same engine, new content.
10. **(Later) Tier 3 AI inference.** Free-form Q&A. Only after 1-8 are stable and there's evidence the deterministic tiers are insufficient.

Each step ships independently. Stopping after step 5 produces a usable coach + tutor with manual mode control for Intake. Adding 6 produces mode flexibility. Adding 7 closes the Verify-mode coaching gap. Adding 8 produces a system that adapts to player skill. Steps 9 and 10 are decoration on top.

---

## Authoring guidelines for scripts (when writing them)

A note for whoever writes the script catalog (you, future-you, or someone helping):

- **Vida's voice is warm but professional.** Senior coordinator at a community VITA site. Not a peppy game NPC. Not a corporate help bot.
- **Specificity over generality.** "Have you checked the citizenship boxes for both spouses?" beats "Don't forget about citizenship!" The specific reference to the scenario fact is what makes it feel intelligent.
- **Questions over imperatives.** "Have you confirmed her residency?" lets the player check their own work. "Confirm her residency!" tells them what to do, which is closer to doing the work for them.
- **Short.** Two sentences. Three at most. Long Vida lines feel like reading a textbook.
- **Cite the source when relevant.** "Pub 501 says..." lands better than "the rule is..." because it teaches the player where to look themselves.
- **Never confirm or deny answers in coach mode.** "Are you sure that's right?" if you suspect they're wrong. "Looks good, want to move on?" if they look correct. Don't say "that's correct" — let grading handle that, so Vida doesn't accidentally green-light a wrong submission a less-thorough coach script missed.

---

## Open design questions

Resolve when implementing.

- How does the player explicitly invoke Vida — a chat panel, a button, a hover menu, a global "ask Vida" hotkey?
- Where do Vida's responses render — modal, sidebar, inline annotation on the form, all of the above?
- Does Vida's coach mode interrupt the player or queue (silently log nudges and surface them at submission)?
- What's the failure mode when no script matches? Default response, silence, or escalate to tier 3?
- How are script catalog entries tested? Snapshot tests on rendered output, hand-review, both?
- For Verify mode: does Vida coach the audit differently than the prep? (Probably yes — different failure modes to catch.)

These are UX-design questions more than architecture questions. Defer to when the product is ready to be built.
