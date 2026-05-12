---
name: pr-description-writer
description: Write clean, structured PR descriptions that anyone on the team can understand — and (with the user's go-ahead) open the pull request via `gh`. Use this skill whenever the user wants to open, draft, or describe a pull request — even when they don't say "description" explicitly. Trigger on phrases like "open a PR", "make a PR", "submit a pull request", "gh pr create", "describe these changes", "write me a PR", or any request whose obvious next step is putting changes up for review. The skill auto-collects context from git (branch name, commits, diff stats), helps pick from six common templates (feature, bugfix, refactor, docs, chore, hotfix), fills in the draft with a plain-language summary that non-engineers can follow, shows it to the user for approval or edits, and only then runs `gh pr create`. Branch pushing also happens behind a confirmation gate.
---

# PR Description Writer

This skill turns a branch full of commits into a clear pull request — without surprising the user. The two non-negotiables: (1) collect context first so the description isn't generic boilerplate, (2) never push a branch or create a PR without showing the user exactly what's about to happen and getting an explicit OK.

## Who reads a PR description

A PR description is not just for the reviewer who knows the code. It's read by:

- **The reviewer** — needs enough technical detail to evaluate the change: file names, function names, the actual mechanism.
- **The future maintainer** — six months from now, someone debugging will land on this PR. Will they understand what changed and why?
- **Non-engineers on the team** — PMs, designers, support, leadership. They often skim merged PRs to understand what shipped, and they don't speak the codebase.

This is why every PR body produced by this skill starts with a **TLDR** that anyone on the team can read without context — and is followed by technical sections with real code references (file paths, function names, the actual fix) for the people doing review and future maintenance. Both audiences win, and neither gets a watered-down version.

## Writing style rules

Apply these to everything.

- **TLDR is for everyone; the technical sections are not.** The TLDR should be readable by a PM or new hire — short, no undefined jargon. The technical sections below it should be technical: name the files, name the functions, reference the specific change. Don't dumb those down.
- **Define jargon the first time it appears in the TLDR, or avoid it there.** "Cache" → "the temporary storage we use to avoid hitting the database every time." "SSRF" → "a class of bug where an attacker tricks our server into making requests it shouldn't." If the term truly is unavoidable, give a parenthetical gloss the first time. Below the TLDR, technical terms can stand on their own — reviewers expect them.
- **In technical sections, reference real code.** Mention the file path (`src/cache/user.ts`), the function or class (`UserCache.updateProfile`), and the specific change (`this.invalidate(userId)`). A description that says "fixed the cache bug" is much less useful than one that says "added `this.invalidate(userId)` after the DB write in `UserCache.updateProfile` so the next read repopulates from the source of truth."
- **Prefer short sentences and concrete nouns.** "Users saw old data for five minutes after editing their profile" beats "Stale cache entries persisted post-mutation for the TTL window" — but the latter phrasing is fine *inside* a Problem or Root cause section where the audience already knows the terms.
- **No emojis.** They look unprofessional in a PR and don't survive well across email notifications, screen readers, and downstream tools. This applies to the title and body. GitHub task-list syntax (`- [ ]` / `- [x]`) is not an emoji and is fine for checklists. Avoid decorative characters like ✓, ✅, ✨, 🚀.
- **No filler.** If you have nothing meaningful for a section, omit it. "Risk: None" is fine; "Risk: Minimal risk associated with this change as it follows existing patterns" is noise.

## When the skill is the wrong tool

If the user already has a finished PR body and just wants it posted, skip the template step — read the body, confirm the title/base branch, and go straight to the approval gate. If they're partway through writing the description themselves, help them finish it, don't restart from a template.

## Workflow

### 1. Confirm intent and gather context

Read git state before asking the user anything — most of what you need is already there.

```bash
# Current branch
git rev-parse --abbrev-ref HEAD

# Default/base branch (best-effort; fall back to "main" if gh isn't authed)
gh repo view --json defaultBranchRef -q .defaultBranchRef.name 2>/dev/null || echo main

# Commits on this branch vs base
git log <base>..HEAD --pretty=format:'%h %s'

# What changed, at a glance
git diff <base>..HEAD --stat

# Full diff — only read if the stat looks manageable (< ~500 lines changed)
git diff <base>..HEAD
```

If the branch has no commits past base, stop and tell the user — there's nothing to PR.

### 2. Suggest a template

Pick a template before asking. Use these heuristics on the branch name and commit messages:

- `feat/`, `feature/`, conventional commit `feat:` → **feature**
- `fix/`, `bug/`, conventional commit `fix:` → **bugfix**
- `refactor/`, conventional commit `refactor:` → **refactor**
- `docs/`, conventional commit `docs:` → **docs**
- `chore/`, `deps/`, `ci/`, conventional commit `chore:`/`build:`/`ci:` → **chore**
- `hotfix/`, branch off `main` with urgency cues in commits → **hotfix**
- Anything else → look at the diff. Mostly docs files → docs. Test-only or config-only → chore. New code paths → feature. Otherwise default to **feature** and let the user override.

Then confirm with the user. A one-line "I'm going to use the **bugfix** template — sound right? (or pick: feature, refactor, docs, chore, hotfix)" is enough. Don't make them sit through a menu if the suggestion is obvious.

### 3. Fill the template

Templates live below. Every template starts with an `## TLDR` section that explains the change to a non-technical reader in two or three sentences. Write that first, because if you can't explain it plainly, you don't understand it well enough to write the rest.

Fill the technical sections from git context. For fields you can't infer — motivation, testing notes, breaking changes, issue links — ask the user a tight batch of questions rather than one at a time. If a field is optional and you have nothing for it, leave it out instead of writing filler.

Keep the body short. Three crisp sections beat ten padded ones.

### 4. Show the draft and get approval

Display the **title** and **body** in the chat as plain markdown. Then ask: "Want me to open this PR, or edit something first?" Treat any edit request as a normal revision — apply the change, show the updated draft, ask again. Do not proceed to `gh pr create` until you have an explicit yes.

### 5. Push the branch if needed

Before creating, check whether the branch exists on the remote:

```bash
git ls-remote --exit-code --heads origin "$(git rev-parse --abbrev-ref HEAD)" > /dev/null
echo $?  # 0 = exists on remote, 2 = doesn't exist
```

If it doesn't exist, ask: "The branch isn't on the remote yet. OK to run `git push -u origin <branch>`?" Wait for confirmation. If the user says no, stop — they may want to push manually or rename the branch first.

### 6. Create the PR

Write the body to a temp file so shell escaping doesn't mangle it, then call `gh`:

```bash
BODY_FILE="$(mktemp -t pr-body.XXXXXX.md)"
cat > "$BODY_FILE" <<'EOF'
<paste body here>
EOF

gh pr create \
  --title "<title>" \
  --body-file "$BODY_FILE" \
  --base "<base-branch>"
```

Use `--draft` if the user asked for a draft PR. After it runs, show the URL `gh` prints and clean up the temp file.

If `gh pr create` fails (auth, no remote, existing PR for the branch), surface the error verbatim and ask what to do — don't retry blindly.

## Templates

All six are below. Inline them directly into the PR body. Square-bracketed text is placeholder guidance for you, not for the final PR.

**Required on every template:** `## TLDR` at the top. Treat it as the most important paragraph — many readers won't go past it.

**Optional, include when relevant:** `## Checklist` and `## Links & references` at the bottom. Both are defined once below the templates and apply to all of them. Include `## Checklist` for any change that's substantial enough to merit one (most features, bugfixes, refactors). Include `## Links & references` whenever there's a tracking issue, related PR, design doc, blocker, or known follow-up to mention. Skip them when there's nothing real to put there — empty sections are worse than no section.

### Feature

```markdown
## TLDR
[Two to three sentences for anyone on the team. What can users now do that they couldn't before? Why does it matter? No undefined jargon. Example: "Customers can now download their reports as a CSV file (a plain text format that opens in Excel or Google Sheets). Before, the only option was PDF, which was hard to work with for further analysis."]

## What
[The change in one or two sentences for an engineer. Concrete capabilities or behaviors added. Name the entry-point file or function where the new behavior lives.]

## Why
[The motivation — what problem this solves, who asked for it, what it unlocks. If you don't know, ask the user.]

## How
[Key implementation notes for a reviewer. Name the major new files/classes/functions and explain anything non-obvious. Example: "New `CsvExporter` service in `src/reports/CsvExporter.ts` streams rows so the whole report doesn't sit in memory. `ReportDetail.tsx` adds the trigger button and hands the report off."]

## Testing
[How this was tested: unit tests added (name them), manual steps, screenshots. Don't invent — if you don't know, leave a clear placeholder or ask.]
```

### Bugfix

```markdown
## TLDR
[Two to three sentences for anyone on the team. What was going wrong from a user's point of view, and what will happen now instead? Example: "When you updated your profile, the old name and photo kept showing up for about five minutes before the new ones appeared. This change makes the update show right away."]

## Problem
[What was broken — symptoms and reproduction steps if known. Written for an engineer who didn't see the bug firsthand. Bullet points are fine if there are multiple observable symptoms.]

## Root cause
[What was actually wrong under the hood — not "the bug," the underlying reason. Reference the specific code path: file, function, the line of logic that was missing or wrong.]

## Fix
[What changed to address it. Reference the specific code change: file, function, the call or condition added. Example: "Added `this.invalidate(userId)` in `UserCache.updateProfile` (`src/cache/user.ts`) immediately after the DB write."]

## Testing
[How the fix was verified; name any regression test added.]
```

### Refactor

```markdown
## TLDR
[Two to three sentences for anyone on the team. The user-visible behavior is unchanged — say so clearly. Then explain why this internal cleanup matters: future work it unblocks, bugs it prevents, or simply that the code is now easier to understand and change. Example: "Nothing changes for users. We reorganized the code that handles login so it's easier to work with, which will let us add two-factor authentication next month with much less risk."]

## What changed
[Scope of the refactor: which modules, which patterns swapped. Name them.]

## Why
[Readability, performance, prep for an upcoming change, killing dead code.]

## Behavior change
None — pure refactor.
[If there is an intentional behavior delta, describe it here instead of "None".]

## Risk
[What could break; what reviewers should pay extra attention to.]
```

### Docs

```markdown
## TLDR
[Two to three sentences for anyone on the team. What information is now available that wasn't before, and who is it for? Example: "We added a step-by-step guide for new engineers on how to set up the project on their laptop. Until now, this knowledge lived only in Slack threads."]

## What
[Which docs were added/changed. Name the files.]

## Why
[Context — confusing area, new feature being documented, stale info corrected.]
```

### Chore

```markdown
## TLDR
[Two to three sentences for anyone on the team. Plain English: what behind-the-scenes thing is changing and why anyone should care. If it's a security update, say what attack it prevents in lay terms. If it's a dependency bump, say what the library does. Example: "We upgraded one of the libraries our backend uses for talking to other servers. The new version fixes a security hole that could let an attacker trick our server into fetching data it shouldn't."]

## What
[The change: dependency bump (give versions), CI tweak, config change, build tooling, etc.]

## Why
[Motivation — security advisory (cite the CVE), new requirement, cleanup.]

## Impact
[Anything developers, CI, or runtime will notice. Use "None expected" if truly invisible. Call out any breaking changes from major-version bumps.]
```

### Hotfix

```markdown
## TLDR
[Two to three sentences for anyone on the team. What was breaking in production, who was affected, and what this change does to stop it. Be direct — leadership and support will read this. Example: "Checkout has been failing for about 20% of customers since last night's release because of a payment validation bug. This change disables the new validation rule so checkout works again while we fix it properly."]

## Incident
[Link to incident doc or describe production impact: when it started, what fraction of users, how it surfaces.]

## Fix
[The minimal change that stops the bleeding. Name the file/function.]

## Rollback plan
[Exactly how to revert if this makes things worse. Be specific — "git revert <SHA>" or "flip the `feature_x` flag off in LaunchDarkly".]

## Follow-up
[What longer-term work this defers — file a ticket and link it.]
```

### Optional sections (apply to any template)

Add these at the bottom when they have real content. Omit them when empty.

```markdown
## Checklist
[A short list of what's done and what's still outstanding. Use GitHub task-list syntax. Check items honestly — don't pre-check anything that hasn't actually been done. Example list to draw from, picking the items that apply:]
- [ ] Tests added or updated for the changed behavior
- [ ] No changes to public API (or: breaking changes called out above)
- [ ] Screenshots attached for UI changes
- [ ] Security implications reviewed
- [ ] Docs updated where user-facing
- [ ] Performance impact considered

## Links & references
[Real links and pointers only — skip the section if you have none. Example items:]
- Closes #123 (or: Refs #123 for partial fixes)
- Related PR: org/repo#456
- Design doc: <URL>
- Incident: <URL>
- Known issue / follow-up: <one-line description, ideally with a ticket link>
- Blocked by: #789
```

## Title conventions

Default to a conventional-commit-style title because most teams use them and reviewers parse them quickly:

- Feature: `feat(<scope>): <imperative summary>`
- Bugfix: `fix(<scope>): <imperative summary>`
- Refactor: `refactor(<scope>): <imperative summary>`
- Docs: `docs(<scope>): <imperative summary>`
- Chore: `chore(<scope>): <imperative summary>`
- Hotfix: `fix(<scope>): <imperative summary>` (mark `[hotfix]` if the team uses tags)

Scope is optional — drop the parentheses if there isn't a clear one. Keep titles under ~72 chars and use plain words (no emojis, no special characters that look fine in your terminal but break in email subject lines). If the user's repo clearly uses a different convention (look at recent merged PR titles via `gh pr list --state merged --limit 5`), follow that instead.

## Worked example

**Input context:** branch `fix/cache-invalidation`, one commit `Invalidate user cache on profile update`, diff touches `src/cache/user.ts` and adds a test. Linked issue #842 in the tracker.

**Title:** `fix(cache): invalidate user cache on profile update`

**Body:**

```markdown
## TLDR
When you updated your profile, the old name and photo kept showing up for about five minutes before the new ones appeared. This was because we keep a short-term copy of profile data in fast memory (a "cache") to avoid hitting the database for every request, and we were forgetting to throw out that copy when the profile changed. This change throws out the old copy as soon as you save, so the update is visible right away.

## Problem

- Profile updates were persisted to the DB but the user cache was left untouched.
- Any read within the cache TTL window (~5 minutes) returned the pre-update profile.
- Users perceived their changes as silently failing or reverting.

## Root cause
The profile update path in `UserCache.updateProfile` (`src/cache/user.ts`) wrote to `db.users.update(...)` and returned the new profile, but never invalidated the cached entry for that user. The cache and the database fell out of sync until the TTL elapsed.

## Fix
Added `this.invalidate(userId)` in `UserCache.updateProfile` immediately after the database write and before returning the updated profile. The next read for that user misses the cache and repopulates it from the source of truth.

## Testing
Added a regression test in `src/cache/user.test.ts` (`profile update invalidates cache`) that updates a profile and asserts the next read does not return the stale entry.

## Checklist

- [x] Regression test added
- [x] No changes to public API
- [ ] Manual verification in staging (planned before merge)

## Links & references

- Closes #842
- Related: incident notes from 2026-05-04 on stale-profile reports
```

## Guardrails

- **Never run `gh pr create` or `git push` without a fresh "yes" from the user.** Past approval of the draft does not authorize pushing.
- **Don't fabricate details.** If you don't know whether something was tested, ask. Better to write "Testing: TBD — manual verification pending" than to invent a unit test that doesn't exist. Same goes for motivation, ticket numbers, and affected user counts.
- **Don't paste the diff into the body.** Reviewers can read the diff in GitHub; the description's job is to explain what they're looking at.
- **Respect existing PR templates.** If the repo has `.github/PULL_REQUEST_TEMPLATE.md` or `.github/pull_request_template.md`, read it and use that structure instead of the templates here — but still add a `## TLDR` opener at the top, since that's the part most non-engineers will read. Tell the user you're using the repo's template and adding the TLDR. If the repo's template already includes a checklist or links section, fill it in honestly; don't pre-check items the user hasn't actually done.
- **No emojis anywhere — title or body.** GitHub task-list syntax (`- [ ]` / `- [x]`) is fine and is not an emoji. Avoid decorative characters like check marks, sparkles, rockets, fire, and so on.
