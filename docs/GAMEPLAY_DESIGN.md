# Gameplay Design Notes

> **Status:** Pre-implementation design notes. None of this is in MVP. The current MVP ships with single-player Encounter mode against generated scenarios; everything described here is the longer-term vision the architecture is being built to support.
>
> **Companion documents:** [`SCENARIO_LIFECYCLE.md`](./SCENARIO_LIFECYCLE.md) for scenario data flow, [`CONCEPT_CATALOG.md`](./CONCEPT_CATALOG.md) for the concept inventory, [`VIDA_DESIGN.md`](./VIDA_DESIGN.md) for the workflow engine and Vida's role, [`UI_TRANSITION_NOTES.md`](./UI_TRANSITION_NOTES.md) for the Encounter / Verify split.

---

## Core philosophy: contribution, not consumption

VITAPrep treats players as *contributors to a simulated workforce*, not *consumers of training content*. From the first scenario, even before the player is skilled, their work has value to the larger system. Their intake submissions become quality-review practice for senior players. Their early efforts populate the workflow that more advanced players progress through.

This is the differentiator from every other tax-training tool. Surgent teaches you. Gleim drills you. VITAPrep puts you on the team.

The implications run through every other design choice:

- Progression rewards engagement with the shared workflow, not just personal mastery.
- The de-leveling mechanic exists because contribution quality matters — bad contributions degrade the pool everyone else relies on.
- Even imperfect work has value, because downstream players can correct it. New players are encouraged to participate even when they're not yet skilled.
- The end-game is when the player is fully participating in the workflow at all roles, not when they've reached a level cap.

---

## Three task types, three gameplay surfaces

VITAPrep has three core gameplay loops corresponding to the three roles a remote VITA volunteer can play:

**Intake (Encounter mode).** Player handles a fresh client. Reads documents and the pre-filled left column of the 13614-C, fills the right column (volunteer column), submits. Output is a completed intake form ready for verification.

**Verify (Peer Review mode).** Player audits a pre-filled intake from another volunteer (NPC or, eventually, another player). Right column already populated; player checks each entry against documents and interview, flags discrepancies, confirms correct entries. Output is a verified intake ready for preparation.

**Prep (Tax Preparation mode, future product).** Player computes the actual return from the verified intake. Lives in VITAPrep proper, the future product.

These are *separate gameplay surfaces*, not stages of a single workflow. Each is its own screen, its own submission flow, its own grader, its own progression metric. A scenario flows through them sequentially (intake → verify → prep), but each role is performed by a (potentially) different player.

The three roles are gated by progression. New players can only do intake. They unlock Verify after demonstrating intake competence. They unlock Prep after demonstrating verify competence. Eventually they can perform any role at varying difficulty levels.

---

## Two progression layers: learning and mastery

The progression system tracks two distinct things, and conflating them produces design errors.

**Learning.** Whether a concept (or a role) has been *exposed* to the player. Binary, append-only. A concept enters the player's "learned" list the first time they encounter it. From that point forward, the system treats them as aware of the concept — it can appear in scenarios without explanation, and the player can drill it via the dungeon queue.

**Mastery.** How *reliably* the player performs on a learned concept. Continuous, can rise and fall. Implemented as an Elo-style rating per concept, fed by signals like grading accuracy, time-to-completion, coach-script firing rate, and self-toggle history.

The two layers serve different purposes:

- Learning unlocks new content and new roles. It's the curriculum dimension.
- Mastery measures skill development. It's the practice dimension.

They award different kinds of progression:

- Learning produces visible unlocks ("HSA eligibility added to your concept catalog").
- Mastery produces continuous metric improvement ("your HoH determination rating went from 1450 to 1480").

De-leveling applies only to mastery. A player who lets a concept get rusty loses mastery rating but doesn't *unlearn* the concept. They just need to drill it back up.

---

## Three content sources

Three distinct paths produce scenarios for the player. Each serves a different purpose in the progression model.

### Main story — system-curated, tutorial-scaffolded

The main story is the system's curated path through learning. New concepts are introduced through main-story scenarios delivered via the dungeon queue. Vida-as-coordinator decides when the player is ready for a new concept based on their mastery of prerequisites; she paces introduction so the player always has something new on the horizon without being overwhelmed.

Main-story scenarios fire transient tutorial moments — the player encounters a concept for the first time, Vida proactively walks them through it, grading is gentle (won't penalize mastery rating for first-exposure mistakes). After this scenario, the concept is in the player's learned list and subsequent encounters are normal-paced.

The main story is the *only* path to learning new concepts at lower-to-mid levels. The shared mailbox doesn't introduce concepts, and the queue can only drill what's already learned. The system controls the curriculum pace; the player controls how much they engage between main-story beats.

### Side quests — the shared mailbox

The shared mailbox is open work that any qualified player can pick up. New players see only basic cases; senior players see complex compound cases as their level rises. Mailbox scenarios exercise concepts the player has already learned, in fresh combinations.

The mailbox is where *contribution to the workflow* happens. Player intake submissions in the mailbox become QR practice for senior players. Player verify submissions feed prep specialists. Even imperfect work has downstream value — bad submissions are good QR practice, and downstream stages catch what the player missed.

Server-wide rewards are weighted toward mailbox participation. Doing main-story queue scenarios gives mastery progression. Doing mailbox scenarios gives mastery progression *and* contribution rewards. Players who only ever drill in private get the former; players who participate in the shared workflow get both.

This isn't a competition between the two — it's a deliberate weighting that reflects what the system values. Players who want to study privately can; players who want to contribute get more.

### Dungeon queue — player-initiated mastery practice

The dungeon queue is the MMO-style "I want to practice X" mechanic. Player picks a role (intake / verify / prep), optionally picks concept filters, queues. The system generates a scenario matching the constraints and assigns it as a special case. Player works it. Done.

Queued scenarios are *outside the server timeline* — they don't enter the workflow pipeline, don't generate downstream work for other players, don't show up in anyone else's mailbox. They're a personal practice instance.

The queue is the bridge between "I've learned this concept" and "I've mastered it." First exposure happens in the main story; reliable performance happens in the queue. New players have a sparse queue (only what they've learned); senior players have a richer queue (everything they've learned, with finer filtering).

Queue-only players get mastery progression but miss contribution rewards entirely. Mailbox-only players get both but progress less efficiently on specific concepts. The intended endgame mix combines all three sources.

---

he Email UI as Universal Assignment Surface
The inbox is the universal entry point to gameplay. Every path that gets the player into a scenario — player-initiated drilling via the dungeon queue, main-story tutorial assignments introducing new concepts, mailbox routing of shared workflow cases, coordinator-flagged cases, scheduled return visits, async client replies that unblock a stalled case — converges on the same pattern: a message arrives in the player's inbox from Vida (or another NPC dispatcher), with the relevant case attached. Player clicks the message, reads Vida's note, clicks the case to begin.
The drilling queue itself is implemented as a compose-and-reply ritual rather than a configuration form. The player composes a message to Vida requesting specific work (role, concept filters, difficulty), hits send, and a few seconds later receives a reply from her with the matching case attached. The artificial delay creates anticipation and makes Vida feel like a real person reviewing requests. The message format is identical to unsolicited assignments she sends later — main-story scenarios, mailbox routings, coordinator escalations — so the player learns one rhythm that scales to all assignment types.
This design does substantial architectural work behind a calm, familiar email-client interface. The gamification disguises itself as professional work — players see an inbox, not a level select; they see a coordinator, not a quest giver. The studying audience encounters a clean training tool; the gameplay audience encounters a workforce simulation. Both are served by the same UI without compromise. Building MVP with this pattern in mind means every later content-delivery feature slots in without UI rework — they're all just messages from Vida.

---

## The contribution metric

Contribution rewards are *qualitatively different* from mastery rewards. They aren't exchangeable.

Mastery rewards individual skill development: per-concept ratings, eventual access to harder content gated on mastery thresholds.

Contribution rewards participation in the shared workflow: things mastery alone can't unlock. Candidates include:

- **Access** — certain scenario types only available to volunteers with sufficient pipeline contributions.
- **Routing privileges** — high contributors get to choose what they pick from the mailbox; low contributors get auto-assigned.
- **Visibility** — high contributors are visible to others (including NPCs) as senior. Their submissions carry a trust signal.
- **Mentorship** — unlocks the ability to QR new players' work and have the system track that they helped train someone.
- **Coordinator trust** — Vida starts referring tricky cases specifically to the player. The narrative respects their contribution.
- **Community standing** — endgame leaderboards or reputation systems that reflect long-term participation.

Contribution must be coupled to *quality*, not just volume. The metric isn't "did you submit" but "did your submission *work* for the next person who got it." A submission that the QR reviewer flagged as error-laden is a low-quality contribution, even if the player completed the work. The workflow needs to *propagate* downstream outcomes back to upstream contributors.

This requires a multi-stage data model where each scenario tracks all the hands that touched it, with grading outcomes per stage that propagate back to the contributors of earlier stages.

---

## The case history surface

Every scenario the player touches accumulates a persistent multi-stage record:

- Scenario metadata (concepts exercised, difficulty, communication mode).
- A list of submissions, each with: player_id (or NPC marker), stage label (intake / verify / prep), timestamp, submitted data, grading outcome.
- Eventual final state (completed correctly, completed with errors, abandoned, scheduled return visit, referred to paid preparer).

The player's "case history" view joins this data and shows them every scenario they've contributed to, what they did, and what happened next. "You did intake on this case 3 days ago. Player X (NPC) verified it (caught 2 errors). Player Y (NPC) prepped it. Final return: filed correctly."

This view is what makes contribution *feel real*. Without it, the player's work disappears after submission. With it, every submission has a story that continues after the player's involvement.

The view should surface patterns the player can act on: "You've done intake on 27 cases. 4 had downstream errors in dependency residency. Want to drill that?" The system feeds these insights into the queue's recommended filters.

The case history is foundational data architecture. It needs to be in the data model from the moment Verify mode lands (the first stage that creates downstream consequences). Backfilling it later is hard.

---

## Communication channels

Three communication channels, each teaching a different cognitive skill.

**Real-time chat (WhatsApp-style).** Synchronous, client available. High-bandwidth, low-latency. Good for resolving quick ambiguities. Constrained by client availability — not all scenarios have an available client.

**Email.** Asynchronous, timer-gated. Lower-bandwidth (the player has to write more carefully because they can't iterate quickly), higher-latency (replies arrive after a delay). Available when the client isn't online.

**Lobby / shared mailbox.** Where assignments arrive, where ad-hoc cases can be picked up, where coordinator messages land, where async client replies are surfaced. The player's "home base" between scenarios. Email-style UI with a calendar/timer view of active cases.

A scenario has a *communication mode* property that determines which channels are available. This is part of the difficulty profile alongside concept count and obfuscation subtlety.

- Easy / available: client is online, real-time chat works, probes resolve immediately.
- Medium / mixed: client is sometimes online, replies have small delays, sometimes you have to email.
- Hard / offline-only: no real-time chat available, all probes are email-style with timer delays. Some scenarios become unresolvable in one session — the player has to schedule a return visit.

The communication mode can change mid-scenario ("client got busy, going offline"), forcing the player to adapt.

The async timer is *compressed time* — maybe 5 minutes of real time per "delay step" rather than real wall-clock hours. This teaches the rhythm of "ask, wait, work other cases, come back" without requiring real-day-scale waits.

While waiting on one scenario's timer, the player can work on others. This makes simultaneous case management a real skill, gated by progression — new players have one active case at a time; senior players hold multiple.

---

## Coordinator-mediated assignment

Vida-as-coordinator is the entity that routes scenarios to the player. She's not an oracle the player can ask for help; she's a manager who proactively assigns work, escalates issues, and provides feedback.

Coordinator messages can carry many things:

- Out-of-scope referrals ("this case has an out-of-scope element — refer to a paid preparer").
- Scope releases ("normally this would be out-of-scope, but for this scenario it's within bounds").
- Quality flags positive ("nice work on that QR — we're going to send you harder cases now").
- Quality flags negative ("your last three submissions had errors — let's slow down").
- Workload management ("you have three active cases — finish those before picking up new ones").
- Site logistics ("we're closing early today, wrap up what you have").
- Client communications routed through the coordinator ("your client called the site and left a message").
- Peer feedback aggregated by the coordinator ("three other volunteers flagged your QR submissions this week").
- Mentorship invitations ("a new volunteer needs guidance — want to QR their first case?").
- Policy updates ("reminder: standard mileage rate changed for 2026").

The coordinator's job is to keep the player moving forward through the curriculum, manage their case load, and provide narratively-warm feedback that reflects their work patterns. She's distinct from Vida-as-tutor (who walks the player through tutorial scenarios) and Vida-as-coach (who fires reactive nudges during gameplay) — same character, multiple modes.

---

## The endgame

Endgame is reached when the player has been exposed to all concepts in the catalog and has unlocked all roles (intake, verify, prep). It is *not* defined as full mastery of all concepts.

Endgame is a *state*, not a destination. The player reaches it and continues to play within it. There's no "you've completed VITAPrep." There's "you've reached the point where you can do anything the game offers, and now you do whatever feels right."

What players do at endgame:

- Continue grinding mastery on weak concepts (the asymptotic curve of skill refinement).
- Focus on contribution — racking up cases through the mailbox.
- Take on compound-concept scenarios that test multiple high-mastery concepts simultaneously.
- Mentor newcomers (QR new players' work, with the system recognizing the contribution).
- Maintain mastery against decay (mastery ratings drift down without practice).
- Engage with new content as it gets added each tax season (new concepts for new tax law).

Identity-based progression dominates at endgame. The player's pattern of high-mastery concepts and high-participation roles becomes their identity. The system reflects this back: "you're known for HoH determination," "you're a senior verifier," "you've trained 5 new volunteers."

The endgame's scenario generator does different work than the mid-game generator. It synthesizes — combines existing concepts in fresh ways — rather than introducing new content. A scenario might combine five concepts the player has mastered individually into one case where their interactions matter. This is a generation challenge distinct from concept-targeted generation.

Seasonal rhythms (long-term). The simulation can track loose tax-year cycles, with different phases of the season presenting different content, urgency, and coordinator narrative. Players who engage long-term experience these rhythms; the product feels alive across months. New tax-year content arrives in pre-season phases, giving endgame players ongoing reasons to return. This matches real VITA culture, where volunteers experience seasonal arcs, and provides natural temporal texture distinguishing VITAPrep from static training tools.
---

## Difficulty model

Three axes contribute to scenario difficulty. They're independent and can be combined.

**Information density.** How much initial information is provided. Low: client column complete, all answers stated, documents organized. High: client column has gaps, some questions answered ambiguously, documents present in a pile without sorting.

**Probe requirement.** How much the player has to ask for. The trichotomy: reaffirming probes (low value, ~95% return "yes"), confirming-negative probes (procedural completeness, ~80% return "no"), digging probes (high value, ~50/50 return new information). Easier scenarios have most facts surfaced; harder scenarios require more digging probes to resolve. Some scenarios are unresolvable — even with optimal probing, a critical document is missing and the right call is "schedule return visit."

**Concept complexity.** How many concepts are in play and how they interact. Lower difficulty exercises one or two concepts at a time. Higher difficulty exercises many concepts in interaction.

The dungeon queue lets the player pick along these axes. Main-story scenarios pace these for the player. Mailbox scenarios scale them with the player's level.

---

## Tutorial mode (transient)

When a player encounters a concept for the first time, the system fires a *transient tutorial mode* — Vida proactively walks them through it, grading is gentle, time pressure is reduced. After this scenario, the concept is in the learned list and subsequent encounters are normal-paced.

This is different from an "onboarding tutorial" that teaches the tool itself (one-shot, scripted, played at first launch). Transient tutorials fire mid-game whenever new concept exposure happens. The same machinery (Vida's coach + procedure scripts) underlies both, but they have different scopes and triggers.

A small visual indicator should signal that the scenario is a tutorial scenario, so the player understands their performance here is gentler than usual. They should not mistake tutorial-eased performance for true mastery.

The mastery rating treats tutorial scenarios asymmetrically: positive results count, but failures don't lower the rating. The player can't lose mastery on a concept they haven't properly learned yet, but they can gain a small initial rating.

---

## Practice run mode (no-stakes flag)

Any scenario can be opted into as a "practice run" — won't affect mastery rating, won't appear in case history, won't generate downstream work. Useful for players who want to attempt hard concepts without risking their level, or for trying out a role at higher difficulty than they're rated for.

This is *not* a separate gameplay mode. It's a flag on a scenario. The scenario itself plays normally; only the post-game scoring effects differ.

The practice run flag and the dungeon queue together cover the "studying audience" use case. A player who wants to use VITAPrep purely for EA / CPA exam prep can queue scenarios with concept filters, run them as practice (no stakes), and use the system as a pure study tool. The gamified workforce-simulation layer is still there but doesn't impose itself.

---

## Multiplayer (long-term)

The single-player MVP simulates a workforce with NPC participants. The architecture is designed to accommodate real other players replacing some or all of the NPC slots.

Multiplayer hand-off works because every scenario already accumulates a multi-stage submission record. When real players are available, intake submissions get routed to a real verifier rather than an NPC; verify submissions get routed to a real preparer. Same data flow, different participants.

Shared rewards: when a case completes successfully (final return graded correct), all contributors receive a bonus. This rewards participation in the shared pipeline and creates social-stakes texture — the intake volunteer benefits from a thorough QR reviewer, who benefits from a careful preparer.

End-game multiplayer pool: at the highest progression tier, players participate in a live pool of scenarios moving through stages, picking up roles ad-hoc, completing cases collaboratively. This is the closest the tool gets to simulating a real VITA-Online site.

For MVP and near-term, all of this is NPC-driven. The data model accommodates future real-player participation without needing retrofit.

---

## What this design buys

A coherent product that serves three distinct audiences with one platform:

- **VITA trainees.** Engage primarily with assignments and progression. The gameplay simulates the real job. Contribution incentives are meaningful because they reward what real volunteers value.
- **EA / CPA studiers.** Engage primarily through the queue. Configure for exam concepts, drill, track mastery. Contribution and assignments are optional flavor.
- **Practicing volunteers maintaining skills.** Engage at endgame across all surfaces. Use the queue to drill rusty concepts, the mailbox to keep contributing, the multiplayer pool to participate in a community.

All three on the same platform, with the same architecture, with the same scenarios. The progression and reward systems are differentiated enough that each audience finds their natural mode without compromising the others' experience.

The contribution-based design philosophy is the through-line. Players are workers in a simulated workforce, not students taking a course. That framing distinguishes VITAPrep from every other tax-training tool and is the source of most of its pedagogical claims.

---

## Open design questions

These are unresolved and will need attention when the systems they touch are built.

- **De-leveling calibration.** When does mastery rating drop fast vs slowly? How visible are warning states before a drop fires? What's the recovery curve?
- **Sabotage detection.** In multiplayer, how does the system distinguish between "player is genuinely bad" and "player is intentionally producing bad work to harm others"? Pattern-based detection is the likely answer but not fleshed out.
- **Coordinator message types.** Which of the candidate types listed earlier are most pedagogically valuable, and which are flavor? Worth a small content-design pass when Vida-as-coordinator is implemented.
- **Endgame compound-concept generation.** What's the algorithm for combining mastered concepts into interesting interactions? Probably not "random combination" — needs some sense of which combinations are interesting.
- **Server-wide rewards for mailbox participation.** What does "weighted reward" actually mean numerically? How much does mailbox contribution boost progression vs queue grinding? The exact tuning is a balance problem to solve when the systems are live.
- **Tutorial scenario indicator.** How visible is the "this is a tutorial" signal to the player? Too subtle and they don't realize their performance is being graded gently; too prominent and it feels patronizing.
- **Case history view's depth.** How far back does it go? Does it summarize, or show every scenario? At what point does aggregation start? Real players will accumulate hundreds of cases over time.
- **Practice run flag's discoverability.** Where does the player find it? At scenario start? Mid-scenario? In a settings menu? It needs to be accessible enough that nervous players use it, but not so prominent that everyone defaults to no-stakes mode.

None of these block any current work. They're flagged for future-you when the relevant systems land.
