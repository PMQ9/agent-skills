---
description: Capture end-of-session retrospective entries (friction, wins, new-skill candidates) into the backlog for later action by /skills-retrospective-and-improvement.
---

# Session Retrospective — Capture What the Session Taught Us

This skill is the capture half of the retrospective system. Its job is
**observation and durable capture** — appending entries to the backlog at
session end. It does not analyze, decide, or update skills. That's the job
of the paired `skills-retrospective-and-improvement` skill.

The backlog this skill writes to is the single shared input for the
improvement skill. If capture is thin, analysis will be thin. Treat every
entry as if a future agent (or future you) will need to act on it without
having seen the original session.

---

## Why This Skill Exists

Skills improve fastest when real-session friction is captured at the
moment it happens — not reconstructed from memory days later. Three
things tend to get lost between sessions if there's no capture protocol:

1. **Subtle friction.** A workflow that worked but felt clunky. A step
   the agent had to figure out from scratch even though a skill *should*
   have covered it. These rarely surface as user complaints, but they're
   exactly the signal that improves a skill.
2. **Positive signal.** A technique that worked unusually well. A tool
   combination that saved time. These deserve to be promoted from
   "we got lucky" to "the skill recommends this."
3. **New-skill candidates.** A multi-step pattern that recurred and
   didn't have a home. These get re-derived every session until someone
   names them.

This skill closes that gap by formalizing the end-of-session capture.

---

## When to Trigger

This skill is **active at the end of any task-oriented session**.

**Explicit triggers:**

- The user says "let's wrap up", "we're done", "that's it for now",
  "anything else to log", "session retro", "/retro", "/session-retro"
- The user asks the agent to summarize or close out the session
- The user thanks the agent and signals end-of-work

**Implicit triggers (proactive):**

- A multi-step task has reached a clear completion point and the
  conversation is winding down
- The deliverables for the session have been produced and approved
- The user has gone quiet for an extended turn and the substantive work
  appears finished
- The session is about to be compacted or context-trimmed

When in doubt, prompt briefly: *"Before we close out, want me to log a
quick retro?"* A premature offer is a small interruption. A missed retro
is lost signal.

**Do NOT trigger** during casual chat, quick factual questions, or other
non-task interactions where no tools were used and no deliverables were
produced. The retrospective is a session-level capture, not a per-turn
one.

---

## The Backlog

### Location

```
.claude/retrospective-backlog/backlog.md
```

This path is **consumer-project-local**, not inside any shared submodule.
Each project has its own backlog. If the file or directory doesn't exist,
create it on first use using the structure below.

### Backlog Structure

```markdown
# Retrospective Backlog

Skill-improvement signal captured at the end of work sessions. Each entry
records something worth acting on later.

**Status key:** OPEN = not yet actioned | ACTIONED = applied via PR
(URL noted on entry) | DECLINED = reviewed and decided against

---

## [YYYY-MM-DD] — [session topic]

### Entry [N]: [short descriptive title]
**Status:** OPEN
[... full entry format ...]
```

Entries are appended to the end of the file. New session blocks go at the
end. Never re-order or insert mid-file — the backlog must stay greppable
and chronological.

### Entry Format

```markdown
### Entry [N]: [Short descriptive title]

**Date:** [YYYY-MM-DD]
**Session topic:** [one-line summary of what the session was about]
**Category:** [improvement | pattern | roadblock | new-pattern | new-skill-candidate]
**Scope:** [shared | project-specific | unsure]
**Skill(s) affected:** [skill name(s), or "All skills", or "New skill candidate: [working name]"]
**Status:** OPEN

**What happened:** [Concrete description. What did the agent do, what
did the user correct, what pattern emerged, what was awkward, what
worked well. Include enough detail that someone reading this weeks
later can understand the context without having seen the conversation.]

**Why it matters:** [What this entry suggests about the skill or the
workflow. Why is it worth capturing? What would change if it were
acted on?]

**Suggested next step:** [Concrete suggestion. For existing skills,
reference the section or rule that should change. For new-skill
candidates, sketch the scope and key components. For roadblocks,
suggest what would unblock similar tasks in future.]
```

### Categories

Pick the single category that best fits the entry. If two genuinely
apply, pick the one that drives the most useful follow-up action.

- **improvement** — an existing skill could be clearer, more complete,
  or better organized. Includes missing rules, ambiguous wording,
  missing edge cases, outdated guidance.
- **pattern** — a recurring approach (positive or negative) worth
  naming. Successful workflows that should be promoted from incidental
  to recommended. Failure modes that should be added as anti-patterns.
- **roadblock** — something blocked or slowed the work. A tool
  limitation, a missing capability, a step that took too long because
  no skill covered it.
- **new-pattern** — a workflow that emerged organically during the
  session and didn't fit any existing skill. Worth a name even if it's
  not yet a full skill.
- **new-skill-candidate** — a multi-step process that recurred or was
  substantial enough to deserve its own skill.

### Scope (mandatory tagging)

Every entry must be tagged with one of three scope values. The scope
determines where the eventual fix lands when the improvement skill
acts on the entry.

- **shared** — the insight applies regardless of which project this
  came up in. Generalizable methodology, missing rule that would help
  anywhere, a pattern worth promoting universally. Lands as a PR to
  the shared `agent-skills` repo.
- **project-specific** — only makes sense for this project. Domain
  conventions, client-specific workflows, project-bounded tooling
  decisions. Lands as a PR within the consumer project, targeting
  `.claude/project-skills/<name>/SKILL.md` or `.claude/CLAUDE.md`.
- **unsure** — first-pass call wasn't confident. Escalates to user
  judgment during the review pass.

**Default when uncertain: `project-specific`.** It's better to
under-promote a useful pattern (fixable next review) than to
over-promote a project-specific quirk into the shared library, where
it creates noise for every other project pulling the submodule.

The agent makes the first-pass scope call when logging. The user (or
the improvement skill's review pass) can override later.

---

## What to Capture

The job of this skill is **breadth of capture, not depth of analysis**.
Cast a wide net — the improvement skill will cluster, dedupe, and
decide what's actionable. A useful retro typically produces 2–8 entries.

### Signals worth capturing

For **existing skills** (improvement / pattern / roadblock):

- The agent failed to follow a rule despite it being documented (the
  enforcement is weak even if the rule is correct)
- The user corrected the agent's output in a way that revealed a
  missing rule, edge case, or ambiguity
- A skill's recommended workflow turned out to be slower or worse than
  what emerged organically — promote the organic version
- A workflow step turned out to be more important than the skill
  suggests, or less important than its emphasis (simplification signal)
- A skill assumption turned out to be wrong in practice
- A rule has never been relevant in many sessions where the skill was
  active (simplification signal)
- The user provided feedback that generalizes beyond the current
  instance
- A skill section is loaded into context but never acts on the agent's
  behavior (dead weight)

For **new-skill candidates / new-pattern**:

- A multi-step workflow that could be reused across projects or
  sessions
- A methodology the user explained that isn't captured anywhere
- A task type that keeps coming up with similar structure
- A domain-specific process with clear inputs, phases, and outputs
- A process the user described as "I always do it this way"
- A pattern the agent had to re-derive from scratch

### Signals NOT to capture

- One-off corrections that don't generalize
- User preferences already captured in an existing skill
- Tool bugs or temporary platform issues unrelated to skill methodology
- Generic praise or generic complaints with no actionable specifics
  ("that was good", "that was annoying")

If a possible entry doesn't pass the "would acting on this change a
future skill?" test, skip it.

---

## How to Log

### Append silently when triggered

When the retrospective is invoked at session end, work through the
session methodically and append entries to the backlog file in a single
pass. Do not interrupt the user with each entry. Do not surface entries
until the full set is logged — see "Surface After Logging" below.

### Numbering protocol (mandatory)

Before assigning an entry number, **read the backlog file and find the
highest existing entry number**. Increment from there. Never trust
in-session memory of "the next number" — parallel sessions and
context-compaction can desync the count.

```bash
grep -oE '^### Entry [0-9]+:' .claude/retrospective-backlog/backlog.md \
  | grep -oE '[0-9]+' | sort -n | tail -1
```

If the backlog file is new and empty, start at `Entry 1`.

**Numbering collision protection:** when two sessions write to the
backlog on the same day, both may compute the same "next number"
against a snapshot and collide on write. After appending, re-read the
file and count occurrences of the entry number you just wrote. If it
appears more than once, renumber your appended entry to `max+1` in
place. This is a self-healing pattern that handles parallel writes
without locking.

### Format and insertion rules

- Always use the `### Entry [N]:` format — not alternatives like
  `OBS-YYYY-MMDD-NN` or `## Entry`
- Always append to the END of the backlog
- Never insert entries mid-file
- One entry per logical observation — don't bundle two patterns into
  one entry; the analysis pass needs clean signal

### Session header

When opening a new session block in the backlog:

```markdown
## [YYYY-MM-DD] — [short session topic]
```

If multiple retros run on the same date, suffix with a sequence
identifier (`## 2026-04-29 — afternoon design review`).

---

## Surface After Logging

After all entries are appended, surface a brief summary:

- Number of entries logged this session
- One-line title of each entry (just the title — no full body)
- Their tagged scopes (so the user sees how things will route)
- Any entries flagged as `unsure` and why
- A note that entries will be picked up by the next
  `skills-retrospective-and-improvement` pass

Keep this summary concise. The backlog is the durable artifact; the
end-of-session message is just confirmation that capture happened.

**Example surface message:**

> Logged 4 retrospective entries to the backlog:
>
> 1. *docx skill: header anchoring rule needs an example* — `shared`
> 2. *Recurring pattern: client-research checklist worth its own
>    skill* — `unsure` (could be project-specific to this client)
> 3. *Roadblock: image-to-table extraction had no skill coverage* —
>    `shared`
> 4. *Pattern: parallel subagent approach worked better than
>    sequential — promote to recommended* — `shared`
>
> These will be picked up by the next
> `skills-retrospective-and-improvement` pass.

---

## Self-Application — This Skill Logs About Itself Too

This skill is itself a skill. If during the session anything was
awkward, unclear, or improvable about the retrospective process,
**log it like any other entry** with `Skill(s) affected: session-retrospective`.
Common self-improvement signals:

- The retro fired too late or too early in the session
- The entry format proved insufficient for some kind of observation
- The category list missed a useful category
- The numbering protocol ran into an edge case
- The trigger was missed entirely until the user prompted

Self-entries are tagged `Scope: shared` (this skill lives in the
shared `agent-skills` repo). The improvement skill will route the
fix as a PR upstream, like any other shared change.

---

## Pre-Flight Self-Check

Before declaring the retrospective complete, verify:

1. Did I scan the full session — including post-task discussion and
   any reflective conversation — not just the active task execution
   phase?
2. Were entries appended to the backlog file (not held in memory or
   surfaced inline)?
3. Does each entry have a category, scope, affected skill, and all
   required fields filled?
4. Were entry numbers verified against the file, not guessed from
   memory?
5. After appending, did I re-check for numbering collisions?
6. Did I include any self-improvement entries about
   `session-retrospective` itself if anything in the retro process
   was awkward?
7. Is the surface message a brief summary (titles + scopes only),
   not a full dump?

If any check fails, fix it before closing out.

---

## Anti-Patterns

**Logging only when the user asks.** The retro is the default at
session end, not a feature the user has to remember to invoke.
Description-level activation plus a CLAUDE.md hook is the reliable
pattern.

**Logging in batches at the end of a multi-day project.** The backlog
is a per-session artifact. End-of-session means at the end of *this*
session, even if the project continues.

**Editorializing in the entry.** Entries are observations, not
decisions. "This skill is bad and should be deleted" is not an entry;
"This skill's section X has not triggered in any session over the
last [N] uses" is. Save judgment for the analysis pass.

**Bundling unrelated entries.** One entry per observation. Two
observations that share a session block but address different skills
should be two entries.

**Skipping scope tagging.** The scope field is mandatory. If genuinely
unsure, tag `unsure` and explain why in the suggested-next-step field
— don't leave it blank.

**Defaulting `unsure` to `shared`.** Conservative routing keeps the
shared library clean. When in doubt, `project-specific` is the safer
default; the review pass can promote it later.

**Summarizing the session in the surface message.** The surface
message lists what was logged, with scopes. The session summary
itself, if the user wants one, is a separate output.

**Skipping the retro because "nothing happened."** If a substantive
task session produced no entries at all, log that fact as an entry:
either the session was unusually frictionless (positive signal) or
the agent isn't noticing well enough (process signal).

---

## Quick Reference

| Question | Answer |
|----------|--------|
| When does this fire? | At the end of every task-oriented session |
| What does it produce? | Appended entries in `.claude/retrospective-backlog/backlog.md` |
| Who acts on the entries? | `skills-retrospective-and-improvement` on its next pass |
| Backlog location | Consumer-project-local, NOT inside the submodule |
| Format | `### Entry [N]:` with date, session topic, category, scope, skill, status, what-happened, why-it-matters, suggested-next-step |
| Categories | improvement, pattern, roadblock, new-pattern, new-skill-candidate |
| Scope values | shared, project-specific, unsure |
| Default scope when uncertain | `project-specific` (conservative) |
| How to number | Read file, find max, increment, post-write collision check |
| What if nothing happened? | Log that fact — frictionless sessions are signal too |
| Self-improvement? | Yes — log entries about this skill, scoped `shared` |
| When to surface? | After all entries logged, brief title-and-scope summary |
