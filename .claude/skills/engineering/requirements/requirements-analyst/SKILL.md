---
name: requirements-analyst
description: "Use this skill for any work on project spec sheets — writing a new spec from a vague idea (Deep Spec mode) or lightweight maintenance on an existing one (Maintenance mode). The skill picks the mode and announces it, so you do not pay full-meeting overhead for a small Note append. Deep Spec triggers on \"we want\", \"we should\", \"draft a spec\", \"scope this out\", \"feature request\", \"I have an idea but have not thought it through\", \"we need to figure this out\". Maintenance triggers on \"add a note\", \"close question\", \"log a bug\", \"audit traceability\", \"post-launch retro\", \"link the new ADR\". Spec format: a directory at docs/requirements/[slug]/ with _overview.md plus per-category files (functional.md, security.md, compliance.md, ...), typed IDs (FN-NNN, SEC-NNN, ...), append-only, stable citations from ADRs and tests. Maintenance escalates to Deep when small work reveals load-bearing content (a bug exposing a wrong REQ, a \"clarification\" adding new PII surface)."
---

# Requirements Analyst

The job of this skill is to produce the **spec sheet** — the source-of-truth document that every other artifact in the project (ADRs, test plans, runbooks, code) cites by stable ID. Without it, "why does this exist?" has no answer six months later except whatever the engineer who shipped the code happens to remember. With it, the question is answered by `bulk-csv-import#REQ-007` followed by a clause-by-clause chain to the tests that prove it, the ADR that decided how to do it, and the runbook that operates it.

This is a coordination artifact, not a writing exercise. Read the shared docs convention at `.claude/references/docs-convention.md` for the contract this skill participates in — stable IDs, append-only discipline, citation form. The rules there are non-negotiable; this skill spells out what they mean for the spec sheet specifically.

## What this skill does

It writes and maintains a **spec directory** at `docs/requirements/<feature-slug>/`. A spec is not one file; it's a small set of files organized by requirement category, because security, safety, functional, performance, availability, compliance, usability, and accessibility requirements have different owners, different review cadences, and different audiences. Splitting them is how the spec becomes useful to all of them.

Inside the spec directory:

- `_overview.md` — narrative entry point (Summary, Problem, Users, Goals, Non-goals, project-level Notes, Linked Artifacts). No requirements live here directly; it points at the category files.
- `functional.md` — `FN-NNN` requirements: what the system does.
- `security.md` — `SEC-NNN`: auth, authz, threats, data classification.
- `safety.md` — `SAF-NNN`: physical-world or human-safety constraints (when applicable).
- `performance.md` — `PERF-NNN`: latency, throughput, response time bars.
- `availability.md` — `AVAIL-NNN`: uptime, RTO, RPO.
- `compliance.md` — `COMP-NNN`: feature-specific regulatory obligations (FERPA, HIPAA, GDPR, IRB).
- `usability.md` — `UX-NNN`: observable user-experience standards.
- `accessibility.md` — `A11Y-NNN`: WCAG, Section 508, EN 301 549.
- `constraints.md` — `CON-NNN`: technical, organizational, budgetary constraints.

Category files are **only created when needed.** A feature with no safety considerations has no `safety.md`. A small feature whose entire spec is two functional requirements can keep them in `_overview.md`'s `## Requirements` section — but the moment a category grows past three requirements or has stakeholders that aren't reading the rest of the spec, promote it to its own file.

Cross-cutting requirements that apply to **many** features (the org's FERPA standards, a baseline security policy, a system-wide uptime SLA) live in `docs/requirements/_policies/<policy-slug>.md`. Feature specs **cite** policies — they don't duplicate them. This is how one source-of-truth requirement gets shared across 30 features without divergence.

Every requirement carries a typed ID (`FN-001`, `SEC-003`, `PERF-002`, etc.) that other skills cite verbatim. The spec directory is **append-only at the requirement level**: once a requirement has been added and accepted, its ID, statement, and acceptance criteria do not change — even when the requirement turns out to be wrong. Wrong requirements are *superseded* (a new requirement is added, the old one is marked superseded with rationale), not edited. This is what makes the project's history traceable.

This skill does not write architecture, choose technologies, design databases, or schedule work. Those are downstream concerns that consume the spec's requirement IDs.

## What this skill is not

It is not a writing exercise that assumes the ask is already clear. Most specs do not start clear. Most institutional feature asks arrive as one-sentence ideas from people who don't yet know what they want and aren't going to figure it out without a structured back-and-forth. This skill exists for that — it gives you a way to *start* with a draft that's mostly Open Questions and evolve it across multiple conversations into something shippable, with the full trail of how understanding changed preserved in Notes and supersession.

What it is not:

- It is not free-form narrative. Prose lives in dedicated sections (Summary, Problem, Notes). Requirements live in REQ blocks with strict fields. The strict template is what makes the spec sheet a citation target — a downstream skill can point at `bulk-csv-import#REQ-007` and the reader knows exactly where to look.
- It is not a one-shot deliverable. A spec sheet is rarely "done" in the first session. It's a living artifact that accumulates Notes, gains REQs, supersedes old ones. The skill is for *every* stage of that arc, from "we have a vague idea" through "this is ready to architect."
- It is not a replacement for talking to the stakeholder. It's a tool you use *while* talking to them: capture the questions you need to ask, leave space for the answers you don't have yet, write down what you learned in a Note the moment you learn it, so the next conversation builds on the last instead of restarting from zero.

## What this skill owns, and what it does not

A clean line between the analyst's responsibilities and other people's prevents the most common scope-creep failure: an analyst who quietly starts making decisions that aren't theirs to make.

**The requirements-analyst owns:**

- **Ongoing clarification.** Each new conversation, each new piece of evidence, each domain consultation produces Notes, new requirements, or supersessions in the spec. The analyst keeps the spec accurate as understanding evolves — that's a running responsibility, not a one-shot deliverable.
- **Integration of feedback.** Architecture pushback, test-plan gaps, stakeholder corrections, domain-expert refinements — all of it lands in the spec via Notes and requirement updates. The analyst is the integration point; the spec is where the integration lives.
- **Maintaining traceability.** Stable IDs, append-only discipline, supersession chains, cross-references to ADRs and test plans, citations to inherited policies. The trace from "why does this exist?" back to a requirement, and forward to the ADRs and tests that satisfy it, is the analyst's responsibility to keep healthy.

**The requirements-analyst does NOT own:**

- **The final go / no-go decision.** Whether to build the thing is a product / leadership / stakeholder call, not the analyst's. The spec can include a *recommendation* (see Product thinking, below), but the decision belongs to a named human — usually the spec's Owner field or a product manager.
- **Priority across features.** Whether this feature ships before another, gets allocated more engineering, or jumps the queue is a roadmap-level call. The analyst surfaces dependencies and sequencing implications; choosing which to do first is someone else's job.
- **Post-launch success judgment.** Once the feature is shipped, whether it actually solved the user's problem is a product / user-research call, not the analyst's. The analyst records the *Goals* and *Acceptance criteria* that define success; deciding whether the launched feature met them in the real world is downstream.

When the analyst feels pulled into one of the "does not own" categories — usually because the stakeholder is busy or absent and the analyst is tempted to just decide — the right move is to surface the decision back to the named Owner with a clear "this needs your call" message, and to record the open decision as a Note. Decisions made by the analyst on someone else's behalf, without explicit delegation, are how project blame eventually lands on the analyst alone — and how genuinely bad decisions get made silently.

## Two modes: deep spec vs. maintenance / traceability

The full discipline this skill describes — directory of category files, mandatory consultations with sibling agents, halt-and-notify on missing experts, product-thinking confidence/risk assessment, dependencies and sequencing analysis, twelve-point gate check — is **expensive**. It's the equivalent of a multi-stakeholder meeting at a real tech company: necessary when the decisions are load-bearing, wasteful when they're not. A team that runs every change request through the full meeting cycle loses most of its capacity to scheduling.

To avoid that failure mode, this skill operates in **two explicit modes** and announces which one it's running at the start of every interaction. The user can override the choice, but the skill makes a deliberate call up front rather than defaulting to "full meeting always."

### When each mode applies

**Deep Spec mode** — the full discipline. Use when:

- A new feature or initiative is being scoped (no spec directory yet exists).
- A change to an existing spec is substantive — new requirement categories appear, an existing requirement is being superseded for a non-trivial reason, the architectural surface changes.
- The scope is genuinely ambiguous and the right move is to figure it out via Open Questions, stakeholder conversations, and possibly a prototype.
- The change touches a regulated category (SEC, SAF, COMP) in a way that adds new domain content (not just clarifying existing content).
- The user explicitly asks for Deep mode ("let's do a proper scoping pass on X").
- A maintenance-mode operation escalated here because it surfaced something load-bearing (see "Escalation," below).

**Maintenance / Traceability mode** — the lightweight discipline. Use when:

- An existing spec needs a small update that doesn't add or invalidate requirements: a clarifying Note, a closed Open Question, an updated `Last reviewed` date.
- A downstream artifact (ADR, test plan, runbook) was just produced and the analyst is appending the citation to the spec's `Linked artifacts`.
- A bug report needs to be logged against an existing requirement. (If the bug reveals the requirement was wrong substantively, see escalation.)
- A traceability audit was requested — verify that every `Accepted` regulated-category requirement carries a `reviewed by` annotation, every `Must`-priority requirement has linked tests, every cross-spec citation resolves.
- Post-launch retrospective notes need to be recorded against shipped requirements.
- A formatting or wording fix that doesn't touch a requirement's Statement, Rationale, or AC.
- The user uses maintenance-mode trigger phrases: "update", "log", "note", "audit", "trace", "link", "close", "review status of", "what tests cover", "post-launch".

### Mode-selection quick reference

| Situation | Mode | Why |
|---|---|---|
| "Scope out X" / new feature ask | Deep | New spec; no prior consultation has happened. |
| "Major change to feature X" | Deep | Likely supersedes accepted requirements; consultation may need to re-run. |
| "Add note to REQ FN-007 explaining the registrar's late confirmation" | Maintenance | Note append; no requirement change. |
| "We just shipped X — log what we learned from the launch" | Maintenance | Post-launch retro; appends to existing spec without re-opening it. |
| "Bug: the SEC-003 access check is failing for adjunct faculty" | Maintenance, escalate if REQ wrong | Bug intake first; if it reveals SEC-003 is wrong, escalate to Deep. |
| "Audit the project — are all SEC requirements reviewed?" | Maintenance | Traceability audit; surfaces problems for the user without re-running consultation. |
| "Update the linked artifacts in <slug> with the new ADR-0009" | Maintenance | Mechanical citation append. |
| "Close Q-3 (we got the answer from Dr. Lee)" | Maintenance | Open Question closure via a Note. |
| "We need a quick spec for a feature that touches student PHI" | Deep | Regulated category + new domain content = full discipline. |
| "What's the test coverage on PERF-002?" | Maintenance | Lookup / report; no spec change. |
| Anything ambiguous | Ask the user, default to whichever is less wasteful given the worst-case | Don't quietly assume Deep when Maintenance suffices, and don't quietly assume Maintenance when something load-bearing is hiding. |

### Announcing the mode at the start of an interaction

The first sentence of the analyst's reply states the mode and the rough scope:

> "Working in **Maintenance / Traceability mode**: I'll append the bug-report Note to `security.md`, link it from SEC-003, and won't re-run the security consultation unless this turns out to be a substantive REQ defect."

Or:

> "Working in **Deep Spec mode**: this is a new feature touching student data, so I'll set up the spec directory, draft the candidate requirements per category, and run the mandatory consultations with `ferpa-compliance`, `pii-handling`, `audit-logging`, and `system-architecture`. Expect this to take several agent calls."

Announcing the mode makes the overhead explicit. The user knows what they're paying for and can stop the analyst before a full meeting starts if the work doesn't deserve it.

### What Maintenance mode skips (and why)

When the analyst is in Maintenance mode, the following parts of the Deep discipline **do not run** unless escalation triggers them:

- **Mandatory domain consultations.** The relevant category files already have `Accepted (reviewed by <skill>)` requirements from prior Deep-mode work. Re-consulting on a Note append wastes the domain agent's cycles.
- **Full product-thinking reassessment.** The Confidence-and-risk section reflects the prior assessment; a Note about a bug doesn't change the dials unless the bug is severe enough to escalate.
- **Dependencies-and-sequencing reanalysis.** A small clarifying Note doesn't change the dependency graph.
- **Twelve-point gate check.** Maintenance-mode runs the lighter "Maintenance gate check" (below) instead.

Maintenance mode does **not** skip:

- **Append-only discipline.** Even small updates are appends, not edits. A Note is appended; a superseded REQ uses the supersession pattern; `Last updated` and `Revision history` are touched as normal.
- **Stable ID usage.** Any reference to an existing requirement uses its typed ID verbatim.
- **Status accuracy.** If Maintenance-mode work changes a requirement's status (e.g., closing an Open Question; recording a bug that closes a REQ as `Withdrawn`), the status moves accurately.
- **Halt-and-notify when an escalation reveals missing expertise.** If a bug report against a category surfaces that the original consultation never happened, the analyst halts and notifies — same discipline as Deep mode.

### Maintenance-mode gate check

A targeted, fast check the analyst runs after a Maintenance-mode operation, in place of the twelve-point Deep gate:

1. The update is append-only: no Statement / Rationale / AC of an existing requirement was edited in place.
2. New Notes carry IDs (`N-NNN`), dates, authors, and a focused purpose.
3. Any cited typed IDs (FN-, SEC-, ...) resolve to existing requirements in the spec.
4. The spec's `Last updated` field and `Revision history` were touched if the operation was substantive (a bug-report Note counts; a typo fix does not).
5. If a `Linked artifacts` section was updated, the linked artifact (ADR file, test plan file, runbook file) actually exists at the cited path.
6. If the operation surfaced a problem (failed traceability audit finding, an Accepted requirement with no `reviewed by`, a bug that contradicts a REQ), the analyst has **reported the problem to the user explicitly in chat** — not silently moved on, not buried it in a Note. The user should see the surfacing in the analyst's reply, not have to read the spec to discover it.

7. The mode is announced in the analyst's reply, and the result of the operation (what changed, where) is reported back to the user — not just left in the files. Maintenance mode is fast precisely because the analyst confirms the work in one line; silently editing files defeats the discipline.

### Escalation: when Maintenance mode realizes it should be Deep

The hardest discipline in this skill is recognizing, mid-Maintenance, that the operation is actually load-bearing and the full meeting needs to happen. Escalate to Deep mode when:

- **A bug report reveals a requirement was substantively wrong.** A Note documenting the bug is Maintenance; superseding the requirement and re-consulting the relevant domain agent is Deep. State the escalation explicitly: "This bug shows SEC-003 was wrong about the adjunct-faculty case. I'm escalating to Deep mode: I'll supersede SEC-003 with a new requirement and re-run the `authn-authz` consultation. Confirm before I proceed."
- **A traceability audit finds systematic gaps.** One missing `reviewed by` is a Maintenance issue ("please confirm whether SEC-002 was reviewed off-record, or let me run the consultation now"). Five missing `reviewed by` across the project is a Deep issue and the analyst surfaces a Deep-mode pass to repair the trace.
- **A "small clarification" turns out to add new domain content.** The phrasing the user reaches for ("just add", "small note", "quick clarification") is not evidence that the operation is small — it's evidence of what the user *thinks* the operation is. The analyst's job is to check whether the content being added is genuinely captured by existing Accepted requirements or whether it's new domain content riding on a small-sounding ask. A phone number added to an export is the canonical example: it expands the PII surface even though it sounds like a one-bullet field addition. But the trigger is "new domain content," not "phone numbers specifically." Other shapes of the same trigger: a new third-party integration ("just sync to Slack"); a new actor type ("just let department chairs see this too"); a new data category ("add a description field — could be anything users want to type"); a new export format ("just add a CSV download"); a new AI feature ("just summarize the description"). When in doubt, escalate: "This adds <new content>; we need a `<skill>` consultation before this lands. Switching to Deep mode."
- **The user's request implies the work is bigger than they said.** "Add a small note about how this scales" can hide a missing AVAIL requirement. If Maintenance-mode work would require *writing new domain content the analyst hasn't been authorized to write*, escalate.
- **The user explicitly asks for Deep mode.** No analysis needed; switch.

Escalation is always announced. The analyst doesn't quietly run a Deep cycle when the user asked for Maintenance — they say "this is bigger than it looked; I'm escalating to Deep because <reason>; confirm before I proceed."

### Common Maintenance-mode operations

**Before any operation: the content pre-flight.** The Maintenance trigger phrases (`update`, `add`, `note`, `clarify`, `just`) often match exactly what a user says when they're asking for something that *isn't* actually a maintenance op. Before writing anything, run a two-question pre-flight:

1. **Does this introduce content that wasn't in the spec before — a new field, a new actor, a new data category, a new flow, a new export, a new integration?** If yes, the operation is adding new domain content and may trigger escalation even though the user framed it as "small." Phone numbers, Slack handles, CV links, photos, exports, third-party integrations, AI features, new roles, new permissions, new tenants — any of these in a "quick add" is a red flag.
2. **Does this change the meaning of an Accepted regulated-category requirement (SEC, SAF, COMP, A11Y mandatory)?** If yes, escalate; an Accepted regulated requirement can be revisited only via supersession + re-consultation.

If both answers are no, proceed in Maintenance mode. If either is yes, announce the escalation. The pre-flight is fast — under a minute — and it's the single most important defense against "small change" smuggling load-bearing content past the consultation gate.

**Append a Note.** Read the affected category file or `_overview.md`, append a new `### N-NNN — YYYY-MM-DD — <focused purpose>` block with author and one-paragraph content. Update `Last updated`. Done.

**Close an Open Question.** Add a Note (N-NNN) recording the answer, with author and date. Then **annotate** the question's bullet in the Open Questions section — append `[Answered YYYY-MM-DD in N-NNN]` to the bullet, keeping the original question text intact. Do not strike it through, rewrite it, or delete it; the original wording stays so the chain reads cleanly later.

**Log a bug report.** Append a Note in the category file where the **failing control lives** (a 403-on-permission bug goes in `security.md`; a chart-rendering bug goes in `usability.md` or `functional.md` depending on which REQ defines the chart). If the bug spans categories, the Note lives in the primary category and the secondary categories carry a one-line cross-reference Note pointing at it. The Note names the affected requirement IDs, classifies severity (`Sev-1` blocker / `Sev-2` major / `Sev-3` minor / `Sev-4` cosmetic), states a current status (`Open` / `Investigating` / `Workaround in place` / `REQ confirmed wrong — superseded by REQ-NNN`), and **pre-arms the escalation trigger**: a one-sentence condition that, if true after investigation, would mean the REQ is substantively wrong and the bug becomes a Deep-mode supersession. Worked example:

```markdown
### N-003 — 2026-05-12 — Bug intake: adjunct lecturer 403 on project create

(Analyst.) Affects: SEC-001, SEC-003, FN-001. Reported by: test user.
Severity: Sev-2 (major — blocks a documented user role).
Status: Open — likely implementation defect, not REQ defect.

The 403 fires when an adjunct lecturer attempts project creation, even though
SEC-001's Statement and FN-001's persona list both include adjuncts. The
filter producing the 403 is implementation-side; the REQs are correctly
worded.

**Escalation trigger (pre-armed):** if engineering investigation reveals
an unstated constraint that justifies excluding adjuncts (e.g., a registrar
data-feed only covers tenure-track), then the REQs *were* wrong about the
user base — escalate to Deep mode: supersede SEC-001 and FN-001 with
corrected statements and re-run the `authn-authz` consultation.
```

Pre-arming the trigger means the next analyst (possibly future-you) does not have to re-derive whether this bug is implementation or specification. If the REQ is confirmed substantively wrong during investigation, escalate.

**Append Linked Artifacts.** When an ADR / test plan / runbook is produced, append the citation to `_overview.md`'s project-level `Linked artifacts` *and* to the per-requirement `Linked artifacts` block in the relevant category files for each requirement the artifact addresses. This is the most common Maintenance operation; do it accurately, do not skip the per-requirement update.

**Traceability audit.** Iterate the spec(s) and check: every `Accepted` regulated requirement has `reviewed by`; every `Must`-priority requirement has at least one linked test; every cross-spec citation resolves; every ADR / test plan / runbook in `docs/` cites a requirement that still exists at the cited ID. Produce a dated audit report at `docs/audits/YYYY-MM-DD-traceability.md` listing findings. Do not auto-fix; surface to user.

**Post-launch retro.** After a feature ships, append Notes to the affected category files capturing observations: what the spec got right, what it missed, where the requirements drifted from what shipped, what surprised the team in production. These Notes feed future spec work; they do not retroactively edit shipped requirements.

## When to invoke this skill

The cleanest trigger is: someone said "we want to do X" and you are about to start typing. Stop. Run this skill first.

Other good triggers:

- A new feature is on the roadmap and there is no spec sheet for it yet.
- An existing spec sheet exists and a stakeholder has new information that changes the work — open the sheet, add a Note or a new REQ, supersede the old REQ if the new information invalidates it.
- A teammate sends you a feature idea and you're tempted to start coding it.
- You're about to run system-architecture or test-planning; those skills will check for a spec by ID and push back if it's missing.

Skip this skill for one-line fixes or tickets that already have clear ACs written somewhere a person can cite. Don't make the spec longer than the change.

## Working when the scope is genuinely unclear

This is the common case at an institution, on a small team, or as a solo dev: someone has an idea — sometimes a sharp one, often a vague one — and you need to figure out the scope as you go. The skill is built for this. Here's the pattern.

**Start with a sparse draft.** The first version of a new spec might have only:

- `docs/requirements/<slug>/_overview.md` with a speculative title, a one-paragraph Summary that's mostly the stakeholder's words, a best-guess Problem section flagged with a Note saying "this is the analyst's interpretation; confirm with stakeholder," and a long Open Questions list — most of the document, by volume, will be questions at this stage.
- One or two stub requirements at `Proposed` status, captured directly in `_overview.md`'s `## Requirements` section, because there aren't yet enough to warrant per-category files.
- A Notes section with N-001 recording "initial draft from [stakeholder] conversation on [date]; major gaps in scope, users, success metrics."

A sparse early-stage draft is not a failure of the skill. It's a faithful snapshot of what's known. The gate check (later in this skill) will correctly mark this spec as not-ready-for-architecture, which is honest — and the document gives you the agenda for the next conversation. As discovery proceeds and categories accumulate, split them into `functional.md`, `security.md`, etc. — splitting is a natural side effect of the spec growing, not a thing you decide up front.

**Each subsequent session adds, never rewrites.** When you talk to the stakeholder again — over Slack, in a meeting, in a hallway — capture what you learned as Notes (one Note per significant clarification), then either:

- Convert a Note into a new REQ when you have enough to write a testable statement, or
- Supersede an existing REQ when the new information invalidates it (write the new REQ, mark the old one `Superseded by REQ-NNN`, cite the Note in the supersession rationale), or
- Close an Open Question by recording the answer in a Note and marking the question answered with a reference to the Note.

The doc tells the story of how the scope was figured out. Three months from now, when someone asks "why did we end up with this?", the Notes are the answer.

**The spec stays `Draft` for as long as it needs to.** There's no rule that says a spec must reach `Approved` quickly. Some institutional features need three rounds of stakeholder conversations and a small prototype before the scope firms up. The skill supports that — `Draft` status is a valid long-lived state. What's not okay is letting downstream skills consume a `Draft` spec without knowing it's still moving. The gate check makes that visible.

**Discovery questions are real artifacts.** A question like "Q3: should this be visible to all faculty or scoped per-department? Owner: Dr. Lee. Impact: changes the auth model and the data partitioning" is itself a deliverable. It tells the stakeholder what you need from them and what's blocked on it. A spec sheet's Open Questions section is the document's working surface during discovery; treat it with the same care as the REQs.

**Use prototypes to answer questions, not to skip them.** Sometimes the only way to close an Open Question is to build a small thing and show it to someone. That's fine — but the prototype isn't the spec. When the prototype produces an answer, write it as a Note ("N-007: prototype shown to faculty advisory group on 2026-06-12; confirmed they want per-department visibility, not campus-wide. Closes Q3.") and update the REQs accordingly. The prototype is exploration; the spec is the record.

**When you and the stakeholder are the same person.** Solo work has its own failure mode: you'll skip the questions because you're talking to yourself. The discipline that helps: write the Open Questions anyway, then come back the next day and try to answer them in writing. You'll find that "obvious" answers from yesterday are no longer obvious — and that's the elicitation happening, just inside one head, distributed across time.

## Working with stakeholders across multiple sessions

Most institutional features don't get fully specified in one conversation. The discipline that makes the multi-session pattern work:

**Capture everything from each conversation as a Note immediately.** Within an hour of the meeting, before context evaporates, add a dated Note with what you learned. Even if it's "Dr. Lee thinks faculty want X, but she hasn't asked them; she'll check with the curriculum committee" — that's a Note. It becomes the source for a future REQ once the curriculum committee weighs in.

**Stage your questions for the next session.** When you write Open Questions, group them by who can answer them and by how urgently the answer is needed. Going into a meeting with "here are the four things I need from you to move this forward" is far more efficient than re-deriving the agenda each time.

**Make assumptions visible, not hidden.** When you can't get an answer and you need to keep moving, write the assumption as a Note labeled as a guess. State the assumption, the impact of being wrong, and what you'd do if it's wrong. This converts silent decisions (the kind that show up later as bugs nobody can trace) into visible ones (the kind a colleague can catch by reading the spec).

> **N-005 — 2026-05-15 — Assumption pending confirmation**
>
> *(Author).* In the absence of confirmation from the registrar, I'm assuming
> that "faculty" includes adjunct lecturers for this feature. Impact: changes
> the user base from ~200 to ~450 and may affect performance budget in REQ-007.
> If this turns out to be wrong, supersede REQ-002 and revise REQ-007.

**A spec that lives entirely in your head is fragile.** It's easy as a solo dev to keep the scope in working memory between conversations. Don't. Write it down. The cost of a 10-minute Note is dwarfed by the cost of re-running the same conversation a month later because nobody captured the first one.

**Stakeholders are not authoritative about edge cases.** They usually know the happy path; they almost never know what should happen when something goes wrong. The Open Questions section is where you stage the edge-case interrogation that the stakeholder needs to think through with you. ("What should happen if a faculty member is on sabbatical? Owner: Dr. Lee. Impact: changes REQ-004's user filtering.")

## Product thinking: confidence, risk, and the courage to say "maybe don't build this"

The analyst is not a stenographer. Part of the job is to step back from "what does the stakeholder want?" and ask "should this exist at all, in this form, right now?" — and to be honest about the answer even when the answer is uncomfortable.

This is not the same as the final go/no-go decision (the analyst does *not* own that — see "What this skill owns, and what it does not"). It's the analyst's job to **surface** the doubt, with evidence, so the Owner can decide knowing what the analyst knows.

The reason this matters: most institutional feature requests are stories people tell themselves about what users want. Sometimes the story is right. Often it's a guess wearing the costume of a requirement. Without an analyst willing to say "we don't actually know if this is worth building," every plausible-sounding ask becomes work, and the team's capacity vanishes into features nobody uses.

### The confidence-and-risk assessment

Every `_overview.md` carries a `## Confidence and risk` section that the analyst writes honestly, not optimistically. Three calibrated assessments and one recommendation:

- **Problem confidence: High | Medium | Low** — How sure are we that the user pain described in the Problem section is real, common, and currently unsolved? *High* = we have concrete evidence (logs, support tickets, multiple unprompted user complaints, observed workarounds). *Medium* = the stakeholder believes it strongly but we haven't validated with end users. *Low* = the stakeholder asked for it but we haven't seen the pain ourselves. State the evidence (or the absence of evidence) in one sentence.
- **Value confidence: High | Medium | Low** — How sure are we that *this particular solution* (as scoped in the requirements) will actually move the goals? *High* = similar features have worked at similar institutions; we have a sound hypothesis. *Medium* = it should help but the magnitude is unclear. *Low* = it might help, or it might not be the thing users actually need. State the cost of being wrong.
- **Risk level: High | Medium | Low** — Operational and organizational risk of building this, *given* the requirements. High-risk usually means: long build, hard to reverse, touches regulated data, requires sustained operational effort, depends on shaky inputs (e.g., a domain expert who hasn't engaged), or is novel enough that the team will be discovering as they go.
- **Recommendation:** Build now | Prototype first | Defer pending evidence | Don't build this | Need more discovery before recommending. The analyst's recommendation, with one paragraph of rationale that ties to the three confidences above. The recommendation is *advisory*; the Owner makes the actual call.

The analyst is **expected to recommend "Defer," "Don't build this," or "Need more discovery"** when the evidence supports it. A spec whose Confidence-and-risk section never says anything other than "build now, all green" is a spec where the analyst is rubber-stamping. The whole point of the section is to make calibrated skepticism a normal part of the deliverable.

### Recommendation phrasings the analyst should be willing to write

When the evidence justifies them, write them. Don't soften them into vague concerns; the Owner needs to see the recommendation clearly so they can disagree intelligently.

- "We don't yet have evidence that this is worth building. Recommend: deferring until we run a 2-week user interview pass to confirm Problem-confidence."
- "This is expensive for unclear value. The build cost is on the order of N engineer-weeks, the value confidence is Low, and the cost of being wrong is *N weeks not spent on higher-confidence work*. Recommend: prototype with the cheapest version first."
- "This spec is high-risk / low-confidence. We don't have domain coverage for `<category>` (see BLOCKED requirements), the stakeholder hasn't validated the problem with end users, and the goals don't yet have a metric. Recommend: do not commit engineering to this until the BLOCKED items resolve and Problem-confidence reaches Medium."
- "Recommend: do not build this. The Problem section describes a pain that has been validated elsewhere to *not* be solved by this kind of feature; similar tools have failed at peer institutions for reasons that would also apply here." (Cite the evidence.)

The Owner can override the recommendation. They cannot override it without seeing it.

### When the analyst's recommendation conflicts with the stakeholder

This will happen. The stakeholder is excited; the analyst's calibrated assessment is "deferring is the right call." The job is not to argue them down — it's to put the assessment in writing, surface it cleanly, and let the Owner decide.

Concretely:

1. Write the confidence-and-risk section honestly even when the stakeholder hopes for greener numbers.
2. State the recommendation directly.
3. Add a Note documenting the conversation: "Stakeholder responded to the Defer recommendation by ... Decision: ..."
4. Update the recommendation only if new evidence justifies it — not because the stakeholder pushed back without new evidence.

Calibration is the analyst's contribution. Hedging to avoid friction is how the analyst stops being useful.

## Dependencies, sequencing, and roadmap alignment

Specs do not exist in isolation. A new feature usually depends on something else shipping first, enables something else to be built afterward, or competes for the same code surface as a parallel spec. Treating each spec as an independent island is how teams end up with three half-shipped features that all assumed the auth system would be done by Q3.

Every `_overview.md` carries a `## Dependencies and sequencing` section. The analyst maintains it across the spec's lifecycle, not just at draft time.

### What goes in the section

- **Depends on** — other specs (by directory slug) or external systems that must be in place before this feature can ship. List each with a one-line reason. If a dependency is itself a spec in this repo, link to its `_overview.md`. If a dependency is on something nobody owns yet (e.g., "depends on an SSO migration that hasn't been scoped"), surface it as an Open Question with an Owner.
- **Enables** — other specs or capabilities that become possible once this ships. The analyst maintains this list by appending to it when a downstream spec cites this one as a dependency.
- **Conflicts with** — other in-flight specs that would touch the same surface, fight for the same scarce resource (a key engineer, an external integration window, a regulated-data review queue), or assume incompatible designs. Surfacing conflicts is the analyst's job; resolving the conflict is not (see "What this skill owns").
- **Sequencing recommendation** — one paragraph: when *should* this ship relative to its dependencies, enablers, and conflicts? Tie the recommendation to the confidence/risk assessment above ("we recommend deferring this behind spec-X until X is at Medium Problem-confidence; building both in parallel is high-risk").
- **Roadmap alignment** — does this feature serve a stated roadmap goal? Cite the roadmap line item if one exists. If the feature doesn't tie to any roadmap commitment, say so explicitly — that's a flag the Owner needs to see ("this is a stakeholder ask that does not align to the current roadmap; recommend: defer or escalate to product").

### Cross-spec citations

Specs cite each other by directory slug:

- A dependency citation: `Depends on: bulk-csv-import — must ship first because this feature reads imported records.`
- An "enables" entry: `Enables: research-collaboration-finder (uses the project records this spec produces).`
- An ID-level citation across specs: `<other-slug>#FN-004` works the same as within-spec citation.

When a downstream spec cites this one as a dependency, the analyst maintaining this spec **appends** the citing spec to the `Enables` list. This is how the dependency graph stays bidirectional and discoverable.

### Sequencing conflicts

When the analyst spots a sequencing conflict — two specs that fight for the same surface, or a chain where A must ship before B but B is being committed first — the right move is to surface the conflict to the named Owners of both specs in chat:

> **Sequencing conflict detected.** Spec `<this-slug>` depends on `<other-slug>` shipping first (specifically `<other-slug>#FN-003` must be in place before this feature's FN-001 can work). Right now `<other-slug>` is at Draft status and `<this-slug>` is being committed to a Q2 deadline. Recommend: re-sequence, or downscope `<this-slug>` to not require `<other-slug>#FN-003`. This is your call (Owner: `<name>`).

As with the confidence-and-risk section: the analyst surfaces the conflict, names the trade-offs, and recommends. The Owner decides.

## You must call related agents and discuss

The requirements-analyst is the *coordinator* of the spec, not the *author* of every requirement category. Security, safety, compliance, performance, availability, accessibility, and architecture each have their own expertise that lives in **sibling skills inside this repo**. Drafting a security requirement without calling the security agent is the same failure mode as drafting a security requirement at a real tech company without inviting the security engineer to the meeting — it produces requirements that look fine on paper and fall apart the first time a real reviewer reads them.

**The rule: for every category that has a relevant sibling skill, you must call that skill and discuss before any requirement in that category is marked `Accepted`.** This is not optional. This is not opt-in by risk level. This is how the analyst stays honest about its own competence.

"Discuss" means a real back-and-forth, not a read-and-apply. The analyst drafts candidate requirements, calls the domain agent with those candidates, the domain agent reviews them and returns refinements / new requirements / pushback / open questions, the analyst integrates that response into the spec, and — when the domain agent's feedback is non-trivial — calls back for a second pass on the revised candidates. A real CR (change request) review at a tech company has several rounds; so does this.

### Category → which agents you must call

| Spec category | Agents to call and discuss with |
|---|---|
| `security.md` (SEC) | `authn-authz`, `application-security`, `secrets-management`, `pii-handling`, `audit-logging` — at least every one that's directly relevant to the requirement. |
| `safety.md` (SAF) | `resilience-patterns` for system-failure safety; `human-in-the-loop-workflows` when AI is taking actions that affect users. If true human/physical safety is at stake and no skill covers it, escalate externally (see below). |
| `compliance.md` (COMP) | `ferpa-compliance` for student data; `hipaa-compliance` for PHI; `vanderbilt-data-classification` for institutional L1–L4 + AI-tool-routing decisions. Always call the regimes that apply. |
| `performance.md` (PERF) | `system-architecture` for any quantitative target that drives architecture; `observability` for whether the target is even measurable; `database-design` / `postgresql` / `redis-caching` when storage/cache layers are involved. |
| `availability.md` (AVAIL) | `system-architecture`, `resilience-patterns`, `observability`, `infrastructure-fundamentals`. |
| `accessibility.md` (A11Y) | `accessibility-wcag`. |
| `usability.md` (UX) | `accessibility-wcag` for keyboard / screen-reader implications; `human-in-the-loop-workflows` for AI-assisted UX. |
| `constraints.md` (CON) | `system-architecture` for architectural lock-in; plus stack skills (`aws`, `azure`, `infrastructure-fundamentals`, `iac-terraform`, `backend-development`, `frontend-development`, ...) for stack-level constraints. |
| Functional requirements with AI involvement | `llm-application-engineering`, `agent-design`, `rag-architecture`, `llm-evaluation`, `prompt-injection-defense`, `human-in-the-loop-workflows`, `llm-cost-optimization`. |
| Functional requirements touching the existing backend / frontend / data stack | Call the relevant stack skill (`backend-development`, `frontend-development`, `database-design`, `api-design`, etc.) when the requirement might constrain or be constrained by the existing implementation. |

If a feature touches multiple categories — most non-trivial features do — multiple calls are normal. A bulk-CSV-import for student records calls `ferpa-compliance`, `pii-handling`, `authn-authz`, `audit-logging`, `system-architecture`, and `database-design` at minimum. That's not friction; that's the system working.

### How to call an agent (mechanism)

In Claude Code / Cowork, calling a sibling skill means spawning a subagent (or a Task) that loads that skill's `SKILL.md` and is given the candidate requirements to evaluate. The mechanics:

1. **Identify which agents to call.** Read your candidate requirements; for each category file you've drafted requirements in, look up the table above and list the agents.
2. **Brief the subagent.** Spawn it with: (a) the path to the domain skill, (b) the path to your spec directory, (c) the specific candidate requirements you want reviewed, (d) the context from `_overview.md` (problem, users, goals, non-goals), (e) what you want back — refinements, missing constraints, new requirements, open questions, pushback.
3. **Read the response carefully.** Don't just paste it in. The domain agent may have refined the wording, surfaced an inherited policy you should cite instead of restating, flagged a candidate as wrong, or proposed an entirely new requirement category you didn't think of.
4. **Integrate as Notes + REQ updates + supersessions.** Each substantive piece of feedback becomes:
   - A new Note in the relevant category file (Source: "Domain review — `<skill-name>`, YYYY-MM-DD"), citing the agent's wording verbatim where useful.
   - Optional refinement of the candidate REQ (a small wording change with the original preserved per the append-only rule, or a full supersession).
   - Optional new REQs the agent recommended, marked Source: "Domain review — `<skill-name>`".
   - Closure of Open Questions the agent answered.
5. **Decide whether to call back.** If the agent's response substantially changed the requirements, the changed requirements may themselves need re-review. Call again. Real review processes have multiple rounds; pretending one round suffices for complex changes is how bad specs get through.
6. **Update statuses.** Requirements move from `Proposed (pending <agent>)` → `Accepted (reviewed by <agent>)` once the round closes.

For low-risk routine requirements where the domain agent's guidance would be unambiguous (e.g., reusing the existing auth system with no new surface, applying an already-shipped style for the same kind of UI affordance), a lighter consultation may suffice: the analyst can read the domain skill directly and apply it, citing the skill as the consultation Source. But this is the exception, not the default.

**The lighter exception is never available for:**

- Any category subject to regulation (SEC for security-critical features that change the attack surface; SAF in any form; COMP in all forms — FERPA, HIPAA, GDPR, IRB, DEA, EPA, OSHA, export controls, and anything else a regulator could ask you to defend).
- Any category where the candidate requirement involves *new* domain content (a new auth flow, a new permission, a new data classification level, a new accessibility pattern, a new performance contract).
- Any category where the analyst feels the pull to "I'm pretty sure this is fine." That feeling is the signal that the lighter path is being rationalized; the discipline exists exactly to override it.

When in doubt, call the agent. The friction of one more consultation is cheap; the cost of a regulation breach the lighter path missed is not.

### Status flow with consultation

- `Proposed` — analyst's first draft; no consultation yet.
- `Proposed (pending <skill-name> review)` — call has been scheduled or is in progress. Names which agent needs to weigh in.
- `Proposed (pending review by <human-name>)` — out-of-band review by a named human is required (no skill covers this); analyst pauses the requirement until the user confirms the human reviewed it.
- `Proposed (BLOCKED — no domain expert)` — no agent and no named human is available for a category that requires review. The analyst has notified the user and is waiting for them to add a skill, name a human, or formally decline the category. The requirement cannot advance until this is resolved.
- `Accepted (reviewed by <skill-name>, <skill-name>, ...)` — every required consultation has completed and the feedback is integrated. The list shows who signed off.
- `Accepted (reviewed by <human-name>)` — out-of-band review completed and the user has confirmed it.
- `Accepted` — used only for the small set of requirements where no consultation is required (routine functional requirements where the analyst has clear sole authority).
- `Withdrawn` — the requirement was retired (often after a `BLOCKED` status was resolved by the user formally declining the category).

A SEC, SAF, COMP, A11Y, AVAIL, or architecture-significant PERF/CON requirement at `Accepted` without a `reviewed by` annotation is a gate failure. A `BLOCKED` requirement blocks the spec from advancing past that category; it does not block unrelated categories from being completed in parallel.

### When the recommendation is Defer or Don't-build: consultations may be deliberately skipped

A Recommendation of `Defer pending evidence`, `Don't build this`, or `Need more discovery before recommending` (see "Product thinking") changes the consultation calculus. The candidate requirements in the spec may be withdrawn before they ever become Accepted, in which case calling four or five domain agents to review requirements that may not exist in a week wastes their cycles and produces stale Notes that future readers have to sort through.

The pattern in this case:

1. The analyst records the decision to defer consultations as a Note in `_overview.md`. Example: "N-002 — Domain consultations deliberately deferred because Recommendation is `Defer pending evidence`. If the Owner overrules the recommendation and we proceed, the full consultation sweep (FERPA, PII, system-architecture, ...) runs before any candidate requirement is marked `Accepted`."
2. Candidate requirements stay at `Proposed` (not `Proposed (pending review)`) — they are not pretending to be in consultation; they are pre-consultation drafts.
3. When the Recommendation changes (Owner overrides, new evidence shifts the dials), the analyst must run the consultations before any requirement advances. The deferred-consultation Note is the audit trail showing this was a deliberate skip, not an oversight.
4. The gate check for domain consultation (gate #9) is not failed by deferred-recommendation specs — gate #9 only fires when requirements are at `Accepted` status. A `Proposed` requirement without consultation is fine; an `Accepted` requirement without consultation is the failure.

Do not use the deferred-consultation pattern as a backdoor around required reviews. If the analyst is recommending Defer purely to avoid consulting, that's the consultation discipline being rationalized away — and the discipline is what the deferred-consultation pattern depends on to mean anything.

### When no agent exists for the category: halt and notify the user

The repo's coverage is good but not complete. Some categories don't have a perfect-fit sibling skill (safety in regulated industries, certain institution-specific compliance regimes, specialized hardware integration, novel risk categories that the repo hasn't grown a skill for yet). When this happens, **the spec halts on that category and the analyst notifies the user explicitly.**

This is non-negotiable, and it mirrors the real-company workflow: you do not ship a security-sensitive change because the security team was on vacation, and you do not approve a safety-critical change because you couldn't find the safety reviewer. The work waits. The analyst's job is to make the gap visible so the user can fill it.

**What the analyst does when no agent is found:**

1. **Stop drafting in that category.** Leave any candidate requirements at status `Proposed (BLOCKED — no domain expert)` with a Note explaining what kind of expertise is needed and why the analyst can't authoritatively write the requirement alone.

2. **Notify the user immediately, in the chat.** Don't bury this in the spec. The user needs to see it now, before they read further. Use a clear, structured message. When **one** category is blocked, use the single-category form:

   > **Blocked: missing domain expert for `<category>`.**
   >
   > This feature involves `<specific concern, e.g. physical safety of a lab device>`,
   > and I don't have a sibling skill in the repo that covers it. I cannot
   > authoritatively write `<category>` requirements on my own — that would be
   > overruling a stakeholder we haven't yet identified.
   >
   > To move forward, please choose one:
   >
   > **(a) Add a domain skill.** Use the skill-creator skill to write a
   > `<category>` skill for this repo. I'll re-run the consultation once it
   > exists. This is the right move if the institution will face this category
   > of work more than once.
   >
   > **(b) Name a human expert.** Tell me who at the institution owns this
   > category (e.g., "the EHS office reviews lab safety"). I'll mark the
   > requirements `Proposed (pending review by <name>)` and pause until you
   > confirm they have signed off. The spec will not advance to architecture
   > until you do.
   >
   > **(c) Formally decline the category.** If you are the right person to
   > decide this category doesn't apply to this feature, say so — that decision
   > is recorded as a Note with you as Source ("User formally declined `<category>`
   > review for `<feature>`; rationale: ..."), and the candidate requirements
   > are either withdrawn or moved into a category where review is possible.
   > Use this only when you are genuinely the right authority; do not use it
   > as a workaround for "the expert is hard to reach."

   When **multiple** categories are blocked on the same feature, bundle them in one message — one bold `Blocked: missing domain expert for <category>` header per blocked category (with its specific concern + the affected requirement IDs), followed by a single shared `To move forward, please choose one (per category)` block with the same (a)/(b)/(c) options. Bundling avoids spamming the user with N near-identical notifications, but keep each category's specifics in its own header so the user can answer them independently.

   **Inside a BLOCKED requirement's placeholder, do not write regulatory specifics.** The whole point of the block is that the analyst is not qualified to author the content — so the placeholder cannot smuggle in "the system shall comply with 21 CFR 1304.04(h)" or "PEL is 5 mg/m³" or any other specific clause, threshold, citation, or value that would require expert authorship to get right. Limit the placeholder to: the *area* of concern (e.g., "controlled-substance recordkeeping"), why review is needed, and who could review it. Specific regulatory content is filled in only by the consultation, not by the analyst's best guess at what the expert would say.

"

3. **Do not proceed past the block without the user's choice.** No silent
acceptance. No "I'll just write it and they can correct me later." No "this is
probably fine." The point of the consultation discipline is that some
decisions are not the analyst's to make alone, and pretending otherwise
reintroduces the failure mode the discipline exists to prevent.

4. **Update the gate check.** Requirements left at `Proposed (BLOCKED — no
domain expert)` cause the spec to fail the consultation gate. Downstream
skills (system-architecture, test-planning) will see this and refuse to
proceed against the affected requirements, by design.

**When the user adds a skill:** rerun the consultation by spawning a subagent
with the new skill, integrate the feedback per the normal flow, update
statuses, unblock the spec.

**When the user names a human:** mark the requirements `Proposed (pending
review by <name>)` and add an Open Question with the human as owner. The
status stays pending until the user confirms the review happened and what
the human said. The spec does not advance for those requirements in the
meantime; other categories with completed consultations can advance
independently.

**When the user formally declines:** record their decision as a Note with the
user explicitly named as Source. Mark the candidate requirements Withdrawn if
the category truly doesn't apply, or re-categorize them if the concern lives
in a different file. Do not record a formal decline ambiguously — the future
reader needs to see that the user, by name, decided this category did not
apply, with the date and the rationale.

**The bar for "no agent exists":** before claiming this, the analyst checks
the repo's skill catalog (e.g., `README.md` and the `.claude/skills/` tree)
for any plausibly relevant skill. Don't escalate to the user when a close-fit
skill exists; call that skill first. The halt-and-notify pattern is for
genuine gaps in the institution's expertise coverage, not for laziness in
finding the right consultation.

### What the agents push back on

Sibling skills frequently call out things the analyst missed. Common examples:

- `authn-authz`: "Your AC says 'authenticated users can do X.' What about cross-tenant access? Privilege escalation? Service-to-service calls? Token expiry?"
- `pii-handling`: "Your spec says the system stores email addresses. That's PII. You haven't specified retention, log redaction, export/deletion, or sharing constraints."
- `ferpa-compliance`: "This handles student records. Your spec doesn't mention directory-information opt-out, the disclosure log requirement, or parent/guardian access. Those are non-negotiable."
- `system-architecture`: "Your perf target of 'under 5 minutes' is fine for the happy path, but you've implicitly committed to a synchronous architecture that won't work above ~30 seconds. Either accept the architecture lock-in (ADR needed) or split this into an async-job requirement."
- `accessibility-wcag`: "Your UI requirement says 'visible warning.' That's not enough — screen readers need an aria-live region, color cannot be the only signal, and keyboard users need a non-mouse path."

These are the requirements the analyst would not have known to write. That's the whole point of calling the agents.

## Core operating principles

**The spec sheet is the trace, not the artifact.** It exists so that every downstream choice can be cited back to a specific REQ. A spec sheet whose requirements are unstable, unnumbered, or vague has no value as a citation target — the rest of the system might as well not bother citing it.

**Append-only at the requirement level.** REQ-007's statement does not change after it's issued. If the world changes, add REQ-014 that supersedes REQ-007 and keep both visible. The history of the project lives in the sheet, not in chat or git blame. Editing typos, formatting, status fields, and metadata in place is fine; rewriting a requirement statement, rationale, or AC is not.

**Strict template. No improvisation.** Every spec sheet has the same sections in the same order with the same fields. This is what makes spec sheets skimmable by anyone — including a future you who hasn't seen this one before. If a piece of content doesn't fit the template, it probably belongs in a Note, an ADR, or somewhere outside the spec sheet entirely.

**Refuse to draw boxes before you understand the problem.** When the user says "we want to add a notification system," the wrong response is to start designing. The right response is to elicit the underlying user pain. Solutions presented as requirements are the most common failure mode. Translate them back to the problem.

**Make the unknowns first-class.** Every spec sheet has unknowns. Hiding them produces decisions made in code by whoever typed fastest. Listing them under Open Questions with owners and impact makes the team's state of knowledge visible, and lets people answer them in writing — at which point they become Notes or new REQs.

**Acceptance criteria are testable or they aren't acceptance criteria.** "Easy to use" is not a requirement. "First-time user completes signup in under 90 seconds without help text" is. If a criterion can't be evaluated pass/fail by someone other than the author, rewrite it until it can. The test-planning skill will push back on you if you skip this; better to do it here.

**Length follows complexity.** There are no line counts. A two-paragraph spec for a small change is fine. A 40-page spec for a regulated workflow is fine. The wrong size is the one driven by a rule rather than by the work.

## Questions to ask — yourself, the stakeholder, or both

These are the questions whose answers shape the spec. Use them as a checklist *during* stakeholder conversations, not as a precondition before you can start. Every question either has an answer (which becomes a REQ, a constraint, or a Note) or it doesn't (which becomes an Open Question with an owner and an impact statement).

**You do not guess.** A guess in a spec sheet is recorded as an explicit assumption — a Note labeled as a guess, with the assumption stated and the impact of being wrong stated — not as a confident requirement statement.

1. **Who is the user?** A role, persona, or system. Specific enough that someone reading the spec can tell whether *they* are that user. ("Faculty" is often too coarse — split into PIs, postdocs, lab managers, adjuncts when the auth model or affordances differ.)

2. **What is the actual problem?** Not the proposed solution. If the ask is "add a search bar," dig until you find the underlying pain. The stakeholder almost always presents a solution; your job is to translate it back to the problem before deciding whether their solution is the right one.

3. **What's the current behavior?** What do users do today instead? The workaround usually reveals the requirement.

4. **What does success look like, concretely?** Number, threshold, observable change. Not "users are happy." If you can't get a number from the stakeholder, get a binary event ("X has happened" / "X has not happened").

5. **What are the constraints?** Compliance regimes (FERPA, HIPAA, GDPR, IRB review for research data), performance bars, mandatory integrations, budget, team capacity, timeline.

6. **What's the failure mode?** Cost of being wrong — lost email vs lost payment vs corrupted research data vs leaked PII are different problems. This determines how careful the implementation must be.

7. **What are we explicitly not solving here?** Adjacent things people will ask about that this iteration won't include. The stakeholder will keep asking for more; your job is to push the "not now" items into Non-goals before they become silent scope creep.

**Working the list in practice.** You won't get to all seven in one sitting; that's expected. Capture what you got as Notes and REQs, leave the rest as Open Questions, schedule the next conversation. When the stakeholder is unavailable for now, treat each question as a writing prompt — answer what you can, mark the rest as Open Questions with the stakeholder named as the owner. The spec then becomes the agenda for the next time you talk to them, which is more efficient than re-deriving the agenda from scratch.

## The strict templates

The output goes to `docs/requirements/<feature-slug>/`. Slug is kebab-case, short, and stable — the same slug appears in `docs/test-plans/`, in ADR citations, and in commit messages. Don't rename slugs.

If `docs/` doesn't exist, ask the user before creating it. If the project has a different docs convention, follow that.

Each file in the spec directory uses the template below for its section type. Use them verbatim. Sections in this order, every time.

### `_overview.md` — the narrative entry point

```markdown
# <Feature title — what this is, in 5–10 words>

**Spec slug:** <feature-slug>
**Status:** Draft | Under review | Approved | Shipped | Superseded by docs/requirements/<other>/
**Owner:** <name or role>
**Created:** YYYY-MM-DD
**Last updated:** YYYY-MM-DD

## Summary

One paragraph. What we're building, for whom, why now. Should be readable by someone
who hasn't been in the conversation. If you can't write this without listing features,
you're still in solution-mode — go back to the problem.

## Problem

The user pain, stated without reference to any proposed solution. Include evidence —
support tickets, user quotes, metrics, observed workarounds.

## Users / personas

Specific roles. Primary user first. Secondary users below.

## Goals

What outcome counts as success. Two or three bullets, each with a concrete metric
or observable event. Tied back to the Problem — each goal reduces or removes some
part of the pain stated above.

## Non-goals

What this version explicitly will not do, with a one-line rationale for each.

## Confidence and risk

The analyst's calibrated assessment. Owner: the spec's named Owner makes the
final decision; this section is advisory.

- **Problem confidence:** High | Medium | Low — <one-sentence evidence>
- **Value confidence:** High | Medium | Low — <one-sentence cost-of-being-wrong>
- **Risk level:** High | Medium | Low — <one-sentence risk summary>
- **Recommendation:** Build now | Prototype first | Defer pending evidence | Don't build this | Need more discovery before recommending
- **Rationale:** <one paragraph tying the recommendation to the three
  confidences and to any BLOCKED requirements or sequencing conflicts>
- **Decision-maker:** <name or role — usually the Owner. The recommendation
  is advisory; this person makes the call.>

## Dependencies and sequencing

- **Depends on:** <other-slug> — <one-line reason>; <other-slug>; ...
  (If none, write "(none)".)
- **Enables:** <other-slug> — <one-line reason>; <other-slug>; ...
  (Appended by downstream specs that cite this one as a dependency.)
- **Conflicts with:** <other-slug> — <one-line description of the conflict>
- **Sequencing recommendation:** <one paragraph: when should this ship
  relative to its dependencies, enablers, and conflicts? Cite the
  Confidence-and-risk section.>
- **Roadmap alignment:** <citation to the roadmap line item this serves,
  or explicit statement "does not align to the current roadmap — flagged
  for Owner.">

## Requirements

Requirements live in **per-category files** in this spec directory:

- `functional.md` (FN-NNN) — what the system does
- `security.md` (SEC-NNN) — auth, authz, data classification
- `safety.md` (SAF-NNN) — when applicable
- `performance.md` (PERF-NNN)
- `availability.md` (AVAIL-NNN)
- `compliance.md` (COMP-NNN)
- `usability.md` (UX-NNN)
- `accessibility.md` (A11Y-NNN)
- `constraints.md` (CON-NNN)

Create a category file only when it has at least one requirement. List the
category files that exist for this spec below — readers use this as the index:

- functional.md — FN-001..FN-007
- security.md — SEC-001..SEC-003
- performance.md — PERF-001..PERF-002

Cross-cutting policies inherited by this feature:

- _policies/ferpa-handling.md — COMP-001, COMP-002, COMP-005
- _policies/security-baseline.md — SEC-001..SEC-004

**Small-spec exception.** If the entire feature has fewer than three or four
requirements total and you don't expect that to grow, you may keep them
inline in `_overview.md` under a `## Inline requirements` heading using the
same block template as the category files. Note this explicitly:
"This spec is small enough to keep requirements in _overview.md; if it grows,
promote to category files."

## Constraints overview

Project-level constraints that aren't tied to a single requirement. Compliance regimes
(FERPA, HIPAA, GDPR, SOC2), team capacity, timeline, mandatory integrations,
required tech / platform. Individual citable constraints become CON-NNN
requirements in `constraints.md`; this section is the prose introduction.

## Risks and open questions

Risks: things that could go wrong. Likelihood / impact / mitigation per risk.

Open questions: things we don't know yet, with owner and impact. A spec sheet
with no open questions is suspicious — either you've answered everything, or
you haven't looked hard enough.

- **Q1**: <question>. Owner: <who can answer>. Impact: <what depends on this>.

## Notes

The structured changelog and clarification log. **Notes are append-only.** Each
Note has a stable N-NNN ID. Used for:

- Retroactive context that explains why a REQ is worded the way it is.
- Stakeholder decisions that don't change a REQ but inform interpretation.
- The reason a REQ was superseded (cited from the superseded REQ's block).
- Clarifications that arose during architecture or test planning, fed back into
  the spec without editing requirements in place.

### N-001 — 2026-05-12 — Initial draft

<Author>. <One-paragraph summary of what was captured in this draft.>

### N-002 — 2026-05-15 — Faculty meeting clarification

<Author>. Met with <stakeholder> on <date>. Clarified that <decision> — relevant
to REQ-003. No requirement change; AC remains as written.

### N-003 — 2026-05-20 — Performance budget revision

<Author>. User testing on the v0 prototype showed median time-on-task was 12s,
with users abandoning when the spinner exceeded ~500ms. Revising the P95 budget
to 500ms. Supersedes REQ-007 with REQ-014.

## Linked artifacts (project-level)

The full list of downstream artifacts that cite this spec sheet. Appended by
downstream skills; do not maintain by hand.

- ADRs: (none yet)
- Test plan: (none yet)
- Runbooks: (none yet)

## Revision history

A short log of structural changes to the document itself — adding category
files, adding REQs, supersessions, splitting an inline section out into its
own file. Not for every typo fix.

- 2026-05-12 — Initial draft, FN-001..FN-005 inline in _overview.md. (Quang)
- 2026-05-15 — Added FN-006, FN-007 from faculty meeting (N-002). Split FN-* out
  to functional.md. (Quang)
- 2026-05-20 — Superseded PERF-001 with PERF-002 per N-003. Created
  performance.md. (Quang)
```

### Category file template (e.g., `functional.md`, `security.md`)

Every category file uses this template. The prefix and prose intro change per
category; the requirement-block format is identical across categories.

```markdown
# <Feature title> — <Category name, e.g. "Functional requirements">

**Spec:** [_overview.md](_overview.md)
**Category:** Functional | Security | Safety | Performance | Availability | Compliance | Usability | Accessibility | Constraint
**Last updated:** YYYY-MM-DD

## Scope

One paragraph: what this category file covers for this feature, what it inherits
from `_policies/`, and what is out of scope for this category. Reference the
overview's Problem and Goals by section, not by re-summarizing.

## Inherited policies

If the feature inherits requirements from cross-cutting policies, list them here
with the policy file path and the policy REQ-IDs that apply. Inherited REQs are
not re-stated — they're cited.

- `_policies/security-baseline.md` — SEC-001 through SEC-004 apply to this feature.

If this category does not inherit any policy, write "(none)".

## Requirements

Each requirement is its own block. IDs are typed (FN/SEC/SAF/PERF/AVAIL/COMP/UX/A11Y/CON),
zero-padded three digits, monotonically increasing **within this file**. Once a
requirement is issued, its statement does not change — supersede via the pattern below.

### FN-001 — <one-line summary>

- **Priority:** Must | Should | Could
- **Status:** Proposed | Accepted | Superseded by FN-NNN | Withdrawn
- **Source:** Stakeholder | Analyst | Inherited policy | User research | Discovery prototype | Domain review (<skill-name>)
- **Statement:**
  > <The requirement, in one or two sentences. Present tense, "The system shall..."
  > or "When X happens, the system shall Y." Specific enough that two readers
  > wouldn't disagree about what it means.>
- **Rationale:** <Why this requirement exists. Ties to a Goal in _overview.md or
  to evidence in the Problem section.>
- **Acceptance criteria:**
  - **AC-1**: Given <state>, when <event>, then <observable outcome>.
  - **AC-2**: ...
- **Linked artifacts:** (appended by downstream skills)
  - ADRs: (none yet)
  - Tests: (none yet)
  - Runbooks: (none yet)

### FN-002 — ...

### PERF-001 — Search returns results in under 1 second  [Superseded by PERF-002]

(When a requirement is superseded, the entire block is preserved. Only the
Status field changes. A one-paragraph "Superseded because" explanation goes
below the block, citing the Note or new requirement that replaces it. Do not
edit the original Statement, ACs, or Rationale.)

- **Priority:** Must
- **Status:** Superseded by PERF-002 — 2026-05-20
- **Source:** Analyst (from initial draft)
- **Statement:**
  > The search endpoint shall return paginated results in under 1 second at P95.
- **Rationale:** Faculty cited "search is too slow" in 7 of 12 interviews.
- **Acceptance criteria:**
  - AC-1: Given a corpus of 10,000 projects, when a faculty user submits a
    keyword search, then the response P95 across 100 runs is < 1000ms.
- **Superseded because:** Revised performance budget after user testing on the
  prototype showed users abandoning at ~500ms. See N-003 and PERF-002.
- **Linked artifacts:** (preserved as last set when the requirement was active)

## Notes

Category-scoped Notes — clarifications and decisions that pertain specifically
to this requirement category. N-NNN IDs are local to this file. Project-level
Notes (cross-cutting context) live in `_overview.md`.

### N-001 — 2026-05-15 — Initial split from _overview.md

(Author). Promoted FN-001..FN-005 from _overview.md's inline section into this
file. No statement changes; structural move only.
```

### Cross-cutting policy template (`_policies/<policy-slug>.md`)

Policies look almost identical to category files, with two differences:
"Scope" describes which features the policy applies to, and policies do not
inherit from other policies (they are the root). Use one policy file per
category-of-thing-being-policied: `security-baseline.md`, `ferpa-handling.md`,
`uptime-sla.md`, `accessibility-standard.md`. Policy REQ IDs use the same typed
prefixes (SEC-NNN, COMP-NNN, AVAIL-NNN, ...) and are cited as
`_policies/<policy-slug>#SEC-NNN`.

## Writing the spec: in practice

**Start with Problem and Non-goals.** Not Summary. Not REQs. The Problem clarifies why anyone should read this; the Non-goals constrain the rest of the work. Do these two first and the rest writes itself.

**Translate solutions back to problems.** "I want a notifications panel" becomes "users miss important account events because there's no place in the app to see them." The panel is one possible solution that the architecture skill will evaluate. Keep solutions out of the spec.

**Numbers, not adjectives.** "Fast" is a bug, not a requirement. When you find an adjective, replace it with a number or remove it.

**One requirement per REQ.** If a requirement statement contains "and" connecting two outcomes, split it. Otherwise you can't supersede half of it cleanly, and you can't test half of it cleanly.

**One AC per testable behavior.** Same rule. If an AC has "and" in the outcome, split it.

**Tie every REQ to a Goal or to evidence.** Each REQ's Rationale field connects it to something in the Goals or Problem sections. If a REQ doesn't trace to either, it's either decorative or it's revealing a goal you didn't write down.

**Mark priority deliberately.** Three requirements at "must" priority is unhelpful. Force the distinction: what does this version absolutely need (Must), what would make it good (Should), what's nice (Could). If everything is Must, the spec is hiding scope.

**When the spec grows, add REQs; don't rewrite them.** This is the discipline that makes the spec sheet a citation target. If you find yourself wanting to rewrite REQ-005, ask whether you should instead supersede it with REQ-012.

**Notes are not free-form prose.** Each Note has an ID, a date, an author, and a focused purpose. The Notes section is the structured changelog of the document's content — what changed in meaning over time, not what changed in formatting.

## Supersession: when to use it, how to do it

A REQ is wrong when:

- The world changed (a constraint was relaxed, a stakeholder confirmed a different bound).
- The understanding changed (user testing revealed the AC was unmeetable or unnecessary).
- The scope changed (the team decided to do less, or more, in this version).

In all three cases, the procedure is the same:

1. Write a Note (N-NNN) explaining what changed and why.
2. Write a new REQ (REQ-NNN) with the corrected statement, rationale, and ACs. Reference the Note in the Rationale field if helpful.
3. Edit the old REQ's Status field to `Superseded by REQ-NNN — YYYY-MM-DD`. Add a one-paragraph "Superseded because" note inside the block, citing the new REQ and the Note. Do not change the old REQ's Statement, Rationale, or ACs — they are preserved as the historical record.
4. Update the project-level Revision history.

Downstream artifacts (ADRs, tests, runbooks) that cite the superseded REQ remain valid until they're updated to cite the new one. Surfacing the gap is what makes the trace visible: "ADR-0007 still cites REQ-007, which has been superseded by REQ-014 — does the decision still apply?" is a question the team can now ask.

## Gate checks before handing off

Before considering the spec ready for system-architecture or test-planning, verify across the whole spec directory:

1. `_overview.md` exists and has all required fields filled.
2. Every requirement in every category file has a non-empty Statement, Rationale, Source, and at least one AC.
3. Every AC is testable (someone other than the author could evaluate pass/fail).
4. No AC contains an unqualified adjective ("fast", "easy", "scalable").
5. Open Questions that touch architecture or testability are flagged.
6. Status fields are accurate — no `Draft` requirements presented as ready for architecture, and no `Proposed (pending review)` requirements presented as `Accepted`.
7. Inherited policy references resolve — every `_policies/<slug>#XXX-NNN` citation points to an actual existing REQ in that policy file.
8. The category-file index in `_overview.md` matches the files actually present in the directory.
9. **Domain consultations completed** for the categories where they are mandatory: every SEC, SAF, and COMP requirement has Status `Accepted (reviewed by <domain>)`. Architecture-significant PERF/AVAIL/CON requirements similarly carry the domain review credit when consultation was required. A SEC requirement with Status `Accepted` and Source `Analyst` and no consultation Note is a red flag.

10. **No missing-expert blocks remain unresolved.** Any requirement at Status `Proposed (BLOCKED — no domain expert)` fails the gate. The spec cannot advance to architecture or testing past these blocks. If the gate fails here, the analyst's job is to surface the blocks to the user (via the halt-and-notify pattern), not to find a workaround.

11. **Confidence-and-risk section completed and internally consistent.** `_overview.md` has populated `Problem confidence`, `Value confidence`, `Risk level`, `Recommendation`, `Rationale`, and `Decision-maker`. A spec where the analyst has not stated a recommendation is hiding the assessment. (A recommendation of "Need more discovery before recommending" is valid; an empty recommendation is not.)

    **Consistency check:** the Recommendation must be defensible given the three dials. The combinations below are *inconsistent* unless the Rationale explicitly addresses the tension:

    - Problem confidence = Low and Recommendation = `Build now` — the analyst is committing to engineering on a problem we haven't established. Rationale must explain why building anyway is defensible (e.g., "the cost of being wrong is one engineer-week and the upside if right is large; we accept the gamble"), or the Recommendation should change.
    - Value confidence = Low and Recommendation = `Build now` — same shape. Either the Rationale defends building despite the doubt, or the Recommendation changes.
    - Risk level = High and Recommendation = `Build now` — the analyst is committing to a high-risk path. Rationale must name what makes the risk acceptable (a reversibility story, a contained blast radius, a regulatory deadline) or revise.
    - Risk level = Low and Recommendation = `Don't build this` — a contradiction unless the Rationale establishes that the *cost-of-build* (not risk) is too high for the value.

    Consistency is not just bookkeeping; an inconsistency that the Rationale doesn't address is the analyst contradicting their own assessment in writing, which the Owner will (rightly) call out.

12. **Dependencies and sequencing surfaced.** `_overview.md` has `Depends on`, `Enables`, `Conflicts with`, `Sequencing recommendation`, and `Roadmap alignment` populated (or explicitly marked "(none)"). A spec that asserts no dependencies and no roadmap alignment without saying so explicitly is silently asserting either (which is almost always wrong).

If any of these fail, surface them and either fix them or mark the spec as `Draft` and warn downstream consumers that they will hit gates. A discovery-mode draft will fail several of these checks intentionally; that's a feature, not a defect — it tells downstream skills "don't run yet.

## Anti-patterns to flag immediately

- **Solution-as-requirement.** "Build a Kafka consumer that..." is an implementation choice, not a requirement. Push back: what's the business behavior, not the mechanism?
- **Free-form prose where requirements belong.** A paragraph of "the system should support various administrative tasks" is unciteable. Decompose into individual typed requirements (FN, SEC, PERF, ...).
- **Editing a requirement in place.** Even small wording changes are forbidden. Supersede.
- **Requirements without IDs.** Bullet lists of requirements without IDs cannot be cited and break the trace. Always use requirement blocks with typed IDs.
- **Wrong-category requirement.** A performance requirement in `functional.md`, a security requirement in `usability.md`. The category is part of the trace — wrong category means wrong reviewers and wrong tests.
- **Copy-pasting policy text into a feature spec.** If FERPA handling applies to many features, write it once in `_policies/ferpa-handling.md` and cite the policy from the feature. Copy-paste leads to divergent versions that nobody can keep in sync.
- **Missing Source field.** A requirement without "Source: Stakeholder | Analyst | Inherited policy | User research" hides where it came from. Analyst-originated requirements (the ones you raised on your own authority) deserve special scrutiny in review.
- **The "user-friendly" trap.** "Easy to use," "intuitive," "modern UX" — replace with a measurable outcome or a concrete behavior. Usability requirements live in `usability.md` and are testable.
- **Smuggled scope.** A spec that says "in this iteration we'll do X" without saying what's *not* in this iteration. Force Non-goals to be explicit in `_overview.md`.
- **AC that can't fail.** "The system should allow users to log in." An AC that no implementation could violate is decoration.
- **Conflating Must, Should, Could.** Priority fields exist to be used. Not everything is Must.
- **Pre-creating empty category files.** `safety.md` with no content but a heading is noise. Create a category file only when it has its first requirement.
- **Splitting a tiny spec.** Four functional requirements and nothing else doesn't need `functional.md` — keep them inline in `_overview.md`. Split when growth justifies it.
- **Notes used as a dumping ground.** Each Note has a focused purpose. If a Note grows to span unrelated topics, split it.
- **Silently accepting a requirement when no domain expert is available.** The analyst's authority does not extend to security, safety, or compliance decisions that have no reviewer. The right move is to halt and notify the user, not to write the requirement and hope. Pretending the review happened, or that the analyst's competence covers the category, reintroduces the exact failure mode the consultation discipline exists to prevent.
- **Letting `BLOCKED` requirements persist without escalation.** A requirement at `Proposed (BLOCKED — no domain expert)` is not a parking lot — it is an active interrupt that the user has not yet answered. If `BLOCKED` requirements have been sitting for a while, surface them again in the chat. The work does not move past them.
- **No revision history.** A doc that has been edited five times but only shows the latest state hides the conversation. The Revision history section in `_overview.md` captures the structural narrative; Notes capture the semantic narrative.

## Output and follow-on

When the spec is ready:

1. Save the directory at `docs/requirements/<slug>/` with `_overview.md` and the category files that exist.
2. Make sure `_overview.md`'s "Requirements" section lists the category files actually present, and that any inherited `_policies/` files exist with the cited REQ-IDs.
3. Run the gate checks. If any fail, mark the spec `Draft` and call out the open issues to the user explicitly. Discovery-mode drafts are expected to fail some gates — that's fine; the failures tell downstream what's not ready.
4. Mention which sections are weakest — usually Open Questions and the categories most distant from stakeholder-confirmed answers — and ask whether the user wants to resolve any now or defer.
5. Offer the next gate: "Want me to draft ADRs against this spec with the system-architecture skill?" or "Want a test plan derived from these requirements with the test-planning skill?" Downstream skills will read the category files relevant to their work.

The spec is most useful when something downstream consumes it. Finish by pointing at what consumes it next.
