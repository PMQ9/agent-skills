---
description: Review the retrospective backlog, cluster patterns, and ship skill improvements as PRs (shared → agent-skills repo, project-specific → consumer repo). Requires `gh`.
---

# Skills Retrospective and Improvement — Act on the Backlog

This skill is the analysis-and-action half of the retrospective system.
The capture half (`session-retrospective`) writes entries to the
backlog on every session close. This skill consumes the backlog, finds
patterns, and ships improvements as pull requests.

The two skills are paired. They share the same backlog format and
location. Neither stands alone.

The PR is the durable artifact. There is no local staging directory —
once the skill runs successfully, every change has a PR URL on GitHub
that you can review, merge, or close. The backlog entry records the PR
URL when marked ACTIONED, giving you the full provenance trail:
backlog entry → PR → merged commit → submodule pull (for shared
changes) or repo merge (for project-specific changes).

---

## Why This Skill Exists

A backlog of observations only matters if it converts into changed
skills. Three failure modes occur when there is no analysis pass:

1. **Entry rot.** Entries pile up, lose context over time, and become
   harder to act on the longer they sit.
2. **Pattern blindness.** Three entries each looking minor in
   isolation may, taken together, point at a structural skill gap.
   Without clustering, the pattern stays invisible.
3. **Skill drift.** Skills accumulate one-off rules without ever
   being pruned. A periodic review asks "what should we *remove*?"
   with the same seriousness as "what should we add?".

This skill formalizes the analysis pass and routes the resulting
changes through the right review gate (PR) for the right destination
(shared library or consumer project).

---

## Architecture

- `Scope: shared` → PR to the `agent-skills` repo (the submodule's upstream), via a fresh `mktemp -d` clone — never edit the submodule's working tree.
- `Scope: project-specific` → PR within the consumer project, targeting `.claude/project-skills/<name>/SKILL.md` or `.claude/CLAUDE.md`.
- `Scope: unsure` → escalates to user judgment in this review.

The PR is the artifact: no local staging directory, no in-place edits. Repo layout, the rationale for "no local staging" and "never edit submodule in place" are in [references/skills-retrospective-and-improvement.md](../references/skills-retrospective-and-improvement.md).

---

## Hard Requirement: `gh` Must Be Available

This skill requires the GitHub CLI (`gh`) to be installed and
authenticated. Without it, the skill refuses to run. Pre-flight
check:

```bash
command -v gh &> /dev/null || { echo "gh not installed"; exit 1; }
gh auth status &> /dev/null || { echo "gh not authenticated"; exit 1; }
```

If either check fails, surface a clear message to the user:

> This skill requires the GitHub CLI (`gh`) to be installed and
> authenticated. Please install it from https://cli.github.com and
> run `gh auth login`, then invoke this skill again.

Do not attempt to fall back to manual staging or any other workflow.
The single-path design is intentional — it keeps this skill simple
and predictable.

---

## When to Trigger

### Explicit triggers

- User invokes "/skill-review", "skills retro", "review the backlog",
  "let's improve the skills", "update the skills", "act on the
  retrospective backlog"
- User explicitly references entry numbers from the backlog and asks
  for them to be acted on

### Implicit triggers (proactive)

- At the start of a task-oriented session, the backlog has not been
  reviewed for **7+ days** (check `last-review-date.txt`)
- The backlog has accumulated **10+ OPEN entries** (volume signal)
- A scheduled recurring task fires

When proactively firing, briefly inform the user: *"The retrospective
backlog hasn't been reviewed in [N] days and has [M] open entries.
I'll run the improvement pass before continuing — should take a few
minutes."*

### Do NOT trigger

- During short, single-step interactions where there's no time for a
  full review
- When the backlog has zero OPEN entries
- If the user has explicitly declined a review in this session — do
  not re-prompt

---

## Pre-Flight Checks

Before running the procedure, verify in order:

1. **`gh` available and authed** (see Hard Requirement above). If not,
   refuse.
2. **Backlog file exists** at `.claude/retrospective-backlog/backlog.md`.
   If not, no work to do — inform the user and exit.
3. **`agent-skills` remote known.** Read the submodule URL from
   `.gitmodules` (typically the entry pointing to the submodule
   directory). The skill will clone this remote when shared updates
   are needed. If the submodule isn't configured, surface the issue
   and stop.
4. **Last-review timestamp.** Read `last-review-date.txt`. If missing,
   treat as "never reviewed".
5. **Skills inventory available.** Use `<available_skills>` from the
   system prompt, or list the skills directory.
6. **OPEN entries exist.** If all entries are ACTIONED or DECLINED
   and no cross-cutting patterns remain, skip the review. Update
   the timestamp and inform the user the library is current.

If any pre-flight check fails, surface the failure and stop. Do not
attempt to proceed with partial state.

---

## Procedure

### Step 1: Load the backlog

Read `.claude/retrospective-backlog/backlog.md`. Extract every entry
with `Status: OPEN`. For each, record entry number, date, category,
scope, affected skill(s), title, and full body.

Group entries by **affected skill** as a working index. Entries
tagged "All skills" or "New skill candidate" form their own buckets.

### Step 2: Cluster and analyze

Pattern analysis is the most valuable part of this skill. Look for:

**Common wins** — entries flagged as positive patterns or successful
techniques. If multiple entries from different sessions praise the
same approach, that's a cross-cutting principle worth promoting, not
just a per-skill win.

**Common roadblocks** — recurring friction. Same kind of roadblock
appearing more than once is a durable gap: either a skill needs
strengthening, a new skill needs creating, or a tooling limitation
needs flagging.

**Common improvement opportunities** — multiple entries pointing at
the same skill or section. Two entries asking for clearer wording in
the same paragraph should be merged into a single, well-scoped
change.

**Simplification signals** — entries flagging dead weight, unused
rules, or one-off additions that haven't proven recurrent. Treat
these with the same weight as additions. Healthy skills both grow
and shrink.

**New-skill candidates** — entries categorized as
`new-skill-candidate` or `new-pattern`. Two or more converging
entries describing the same un-skilled workflow is a strong signal.
A single entry is weaker — flag for user judgment rather than
creating autonomously.

**Cross-cutting principles** — patterns that apply not just to one
skill but to skills in general (e.g., "every skill with rules should
include a pre-flight self-check"). These get added to the principles
file and propagated across affected skills.

### Step 3: Resolve `unsure` scopes

For each entry tagged `Scope: unsure`, present it to the user with a
recommendation and ask for the call. Don't proceed past Step 4 with
unresolved scopes — the routing decision blocks the PR target.

If running in interactive mode, ask inline. If running autonomously
(scheduled run), defer all `unsure` entries to the next interactive
review and skip them in this pass — better to wait than to guess.

### Step 4: Decide actions per cluster

For each cluster, decide one of:

- **APPLY** — clear, low-risk change. Open a PR.
- **APPLY-WITH-RESTRUCTURE** — substantial change reshaping a
  section or workflow. Open a PR, flag for careful review.
- **CREATE NEW SKILL** — strong signal for a new skill (typically
  two or more converging entries). Draft and open a PR.
- **ESCALATE** — needs user input before action. Use this when:
  - Naming or scope of a new skill is genuinely ambiguous
  - The change would delete or substantially restructure existing
    content
  - The entry itself flags uncertainty
  - Two entries point in opposite directions
- **DECLINE** — not actionable, not generalizable, or already
  addressed. Mark the entry DECLINED with a brief reason.

In interactive mode, present clusters and decisions to the user as
a grouped summary and wait for confirmation before opening PRs. In
autonomous mode, proceed with non-escalated clusters; leave
escalated ones for the next interactive pass.

### Step 5: Open PRs for shared updates

For each cluster scoped `shared`: clone `agent-skills` (URL from `.gitmodules`) into `mktemp -d`, branch `retro/<skill-name>/<YYYY-MM-DD-HHMM>`, apply the change, push, and `gh pr create`. **Read the live SKILL.md fresh from the clone before editing** — never from memory or a cached version, since another session may have updated it upstream. On any failure (push rejected, PR creation failed) leave the temp directory in place and report its path; do not auto-cleanup.

Full bash template (clone, branch, commit, push, `gh pr create` with body heredoc): [references/skills-retrospective-and-improvement.md § Step 5](../references/skills-retrospective-and-improvement.md#step-5--shared-updates-pr-to-agent-skills-upstream).

### Step 6: Open PRs for project-specific updates

For each cluster scoped `project-specific`: stay in the consumer repo, branch `retro/project/<skill-name>/<YYYY-MM-DD-HHMM>`, apply the change to `.claude/project-skills/<name>/SKILL.md` or `.claude/CLAUDE.md` (create if absent), push, `gh pr create`, return to the previous branch. Same failure handling — leave the branch in place and report its name.

Full bash template: [references/skills-retrospective-and-improvement.md § Step 6](../references/skills-retrospective-and-improvement.md#step-6--project-specific-updates-pr-within-consumer-repo).

### Step 7: New skill drafts

For clusters decided as CREATE NEW SKILL:

- **Shared new skill** — drafted on a branch in the temp clone of
  `agent-skills`, opened as a PR upstream. PR description includes
  the working name, scope, key components, and source entries. Do
  not install — the user reviews the PR.
- **Project-specific new skill** — drafted on a branch in the
  consumer repo at `.claude/project-skills/<new-name>/SKILL.md`,
  opened as a PR. Same review treatment.

For weaker single-entry candidates that don't warrant a full skill
yet, add them to a "deferred new-skill candidates" list in the
summary report and leave them as OPEN entries in the backlog. Note
the deferral on the entry: `Deferred: awaiting reinforcement from
additional sessions`.

### Step 8: Self-update

If any backlog entries target `session-retrospective`,
`skills-retrospective-and-improvement`, or "All skills" in a way
that applies to this skill, treat them like any other shared change
in Step 5. Both meta-skills live in `agent-skills`; their fixes go
through the same upstream PR gate. There is no in-place self-edit
privilege.

This is deliberate. The strict-discipline answer: all shared
changes ship through review, including changes to the skills that
manage shared changes. Bypassing review for meta-skills is the kind
of edge case that produces "wait, when did this rule change?"
mysteries six months later.

### Step 9: Cross-cutting principles

When pattern analysis surfaces an insight that applies to all
skills (e.g., "every skill with explicit rules should include a
pre-flight self-check"):

1. Add it to
   `.claude/retrospective-backlog/cross-cutting-principles.md`
   under "Active Principles" with date, applies-to, requirement,
   and propagation mode (immediate or opportunistic).
2. If propagation is immediate, open a PR per affected shared skill
   that needs to comply, all referencing the new principle. The
   user reviews each PR independently — principles are sensitive
   enough to warrant per-skill scrutiny.
3. If propagation is opportunistic, the principle is checked on
   the next update of each skill, not retroactively applied across
   the library in this run.

The principles file structure:

```markdown
# Cross-Cutting Principles

Principles that apply to all skills. Read as a mandatory checklist
during any skill creation or update.

---

## Active Principles

### 1. [Principle title]
**Added:** [date]
**Applies to:** [all skills | all skills with rules | etc.]
**Requirement:** [what the principle requires]
**Propagation:** [immediate | opportunistic]
**Status:** active
```

### Step 10: Mark entries

For each acted-on entry, update its status in `backlog.md`:

- `Status: ACTIONED — PR: <url> ([YYYY-MM-DD] review)`
- `Status: DECLINED — [brief reason]`
- `Status: OPEN — Deferred: [reason]` (for entries intentionally
  deferred)

Entries that were ESCALATED stay OPEN with a note: `Escalated:
[reason, awaiting user input]`.

### Step 11: Archive resolved entries

Move entries that were marked ACTIONED or DECLINED in **previous
reviews** (not the current one) to:

```
.claude/retrospective-backlog/archive/backlog-[YYYY-MM-DD].md
```

Entries marked ACTIONED or DECLINED **during this current review**
stay in the active backlog for one cycle so the user can see them
in the summary report. They get archived on the next review.

This deferred-archival pattern prevents premature loss of
just-resolved entries while keeping the active backlog focused on
OPEN work.

### Step 12: Update timestamp

Write today's date to:

```
.claude/retrospective-backlog/last-review-date.txt
```

This is what the next session's pre-flight check reads to decide
whether to fire the 7-day proactive trigger.

### Step 13: Present summary

Deliver a structured summary in this format:

```markdown
## Skills Retrospective Review — [YYYY-MM-DD]

Reviewed [N] open backlog entries.

### Common Patterns Identified
- [pattern — entry numbers]

### Common Wins
- [win — what worked, where promoted]

### Common Roadblocks
- [roadblock — what's being done about it]

### PRs Opened — Shared (agent-skills)
- [skill-name]: [PR URL] — entries #[N], #[N]

### PRs Opened — Project-Specific
- [skill-name]: [PR URL] — entries #[N], #[N]

### New Skill Drafts
- [new-skill-name] (shared): [PR URL]
- [new-skill-name] (project): [PR URL]

### Cross-Cutting Principles Added
- [principle title] — [propagation mode] — PRs: [URLs]

### Escalated (needs your input)
- Entry #[N]: [one-line summary of what needs your call]

### Declined
- Entry #[N]: [one-line reason]

### Deferred (still OPEN)
- Entry #[N]: [reason for deferral]
```

Each PR URL should be clickable — review, merge what you accept,
close what you don't. For shared PRs, after merging upstream, run
`git submodule update --remote` in the consumer project to pull the
change.

---

## Anti-Patterns

**Auto-merging PRs.** Never. The PR is the review gate. Opening a
PR and walking away is the correct behavior. `gh pr merge` is not
called by this skill under any circumstance.

**Editing the submodule's working tree directly.** Always clone to a
temp directory for shared updates. Editing the submodule in place
risks committing a moved submodule pointer to the consumer project.

**Treating the backlog as a TODO list.** It's an observation log,
not a task list. Some entries don't merit action — DECLINING them
with a reason is correct, not a failure.

**Applying every entry mechanically.** If two entries conflict,
escalate. If an entry is too vague to act on, escalate or
DECLINE — don't fabricate a plausible interpretation.

**Reading from a stale skill file.** When applying a change inside
the temp clone, read the SKILL.md fresh from the clone (upstream
HEAD), not from memory or a cached version. Another session may
have updated the skill upstream since you last saw it.

**Skipping the unsure-resolution step.** Entries tagged `unsure`
must be resolved (by user input or deferral) before any PR is
opened that depends on them. Don't guess the scope.

**Defaulting `unsure` to `shared`.** Conservative routing keeps the
shared library clean. Promote to `shared` only with explicit user
confirmation or clear evidence the pattern generalizes.

**Creating new skills autonomously without user approval.** Even
strong multi-entry signals get drafted as a PR, never installed
directly. The user reviews the PR like any other change.

**Cleaning up the temp clone on failure.** If `git push` or
`gh pr create` fails, leave the temp directory in place and report
its path. The user can finish manually without redoing the work.

**Asking only "what should we add?".** Healthy reviews also ask
"what should we remove?". Simplification entries get the same
treatment as additions.

**Letting the backlog grow without acting.** If the 7-day proactive
trigger keeps firing because reviews aren't happening, that's
itself a signal — log it as a backlog entry about this skill.

---

## Self-Application — This Skill Updates Itself Too

Entries targeting `skills-retrospective-and-improvement` follow the
shared path: PR upstream, review, merge, pull via submodule update.
The skill does not modify itself in place during a review. The
update takes effect after the user merges the PR and updates the
submodule pointer in the consumer project.

This adds one cycle of latency to self-fixes (PR → merge → pull
before the fix is live) but preserves the review discipline. The
consistency is more valuable than the speed.

---

## Cross-Repo Considerations

Edge cases — fork-when-no-push-access, duplicate PRs from concurrent consumer projects, post-merge `git submodule update --remote` reminder — are documented in [references/skills-retrospective-and-improvement.md § Cross-repo considerations](../references/skills-retrospective-and-improvement.md#cross-repo-considerations). On a `git push` failure for shared PRs, surface the fork instructions from that file and stop.

---

## Quick Reference

| Question | Answer |
|----------|--------|
| When does this fire? | On request, on 7-day staleness, on 10+ OPEN entries, on schedule |
| Hard requirement | `gh` installed and authenticated; refuses otherwise |
| Input | `.claude/retrospective-backlog/backlog.md` |
| Output | PR URLs (shared → agent-skills, project-specific → consumer repo) |
| Local staging? | None. The PR is the artifact. |
| Shared updates: where edited? | Fresh `mktemp -d` clone of agent-skills, never the submodule working tree |
| Project updates: where edited? | Branch in the consumer repo from current HEAD |
| Auto-merge? | Never. The PR is the review gate. |
| Five action types | APPLY, APPLY-WITH-RESTRUCTURE, CREATE NEW SKILL, ESCALATE, DECLINE |
| Always read live file? | Yes — fresh from the temp clone or current branch, never from memory |
| `unsure` scope handling | Resolve via user input before opening any PR |
| Default scope when uncertain | `project-specific` (conservative) |
| New skill from one entry? | Weak signal — defer or escalate, don't draft |
| New skill from 2+ entries? | Draft as PR, never auto-install |
| Self-update? | Same shared PR path; no in-place self-edit |
| Cross-cutting principles | Tracked in `cross-cutting-principles.md`; one PR per affected skill on immediate propagation |
| Archive timing | Entries actioned in *current* review stay visible one cycle |
| Failure handling | Leave temp clone / branch in place, report path, never auto-cleanup on failure |
| Submodule pull reminder | Included in summary for any shared PRs opened |
