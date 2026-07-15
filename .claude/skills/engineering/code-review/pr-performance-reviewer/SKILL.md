---
name: pr-performance-reviewer
description: >-
  In-depth performance review of a pull request or code diff. Use this whenever
  someone asks to review a PR, review changes, or "check this diff" and wants a
  performance lens — or whenever a diff touches database queries, loops over
  collections, async/await, I/O, or caching. Hunts for the specific, fixable
  implementation problems: N+1 queries, unnecessary or repeated DB calls,
  expensive loops, wasteful memory allocations, async misuse, blocking I/O on
  hot paths, and missed caching opportunities. Trigger on "review this PR for
  performance," "is this slow," "will this scale," "performance review," "look
  at PR #123," "check my diff," or any request to critique code where speed,
  latency, throughput, or resource use is on the table — even when the user does
  not say the word "performance." This skill stays at the implementation level
  ("this call is inefficient") and deliberately avoids architecture or redesign
  advice.
---

# Performance PR Reviewer

You are reviewing a pull request through one lens only: **runtime performance of
the code as written**. Your job is to catch the concrete, fixable inefficiencies
that make an otherwise-correct implementation slow or wasteful, and to hand the
author a review they can act on line by line.

## The one rule that shapes everything

Stay at the implementation level. You are answering *"is this code inefficient?"*
— never *"is this the right architecture?"*

The difference matters because architecture feedback is expensive to act on,
usually out of scope for a PR, and often not the reviewer's call. A performance
review that says "you should split this into a separate service" is noise to
someone who just wants to merge a working change. A review that says "you're
issuing one query per row here — fetch them in a single query" is a gift.

Concretely:

- Say: "This loads the user inside the loop, so it runs N queries. Fetch all
  users once before the loop."
- Don't say: "This service is doing too much; consider a CQRS split."
- Say: "`.count()` is called on every iteration and hits the DB each time. Hoist
  it out of the loop."
- Don't say: "You should introduce a read model / denormalize this table."

If the only real fix is a redesign, note briefly that the hot path is
structurally expensive and stop there — don't design the replacement. The author
asked for a performance review, not a rewrite.

## What to hunt for

These seven categories are the whole job. Read the diff (and enough surrounding
context to understand data flow) looking specifically for each one. Most real
findings fall into one of these buckets, so use them as a checklist — but lead
with judgment: a finding only counts if it plausibly costs real time, memory, or
DB load at realistic input sizes.

1. **N+1 queries** — a query issued once per element of a collection, where a
   single batched query would do. The classic tell is a DB/ORM/API call *inside*
   a loop, or lazy-loading a relation while iterating.
2. **Unnecessary / repeated DB calls** — fetching the same data twice, querying
   inside a loop for something that could be fetched once, `SELECT *` when two
   columns are needed, counting or existence-checking with a full fetch.
3. **Expensive loops** — accidentally quadratic work (a nested lookup that could
   be a hash-map/set lookup), re-computing an invariant every iteration, building
   a list only to take its length, sorting inside a loop.
4. **Memory allocations** — materializing a whole collection when a stream/
   generator/iterator would do, unbounded accumulation, copying large structures,
   building huge intermediate lists, loading an entire file into memory.
5. **Async misuse** — awaiting independent operations sequentially instead of
   concurrently (missing `gather`/`Promise.all`), `await` inside a loop that
   serializes calls, fire-and-forget that drops errors, mixing blocking calls
   into async code, unnecessary `async` overhead.
6. **Blocking I/O** — synchronous file/network/disk calls on a hot path or inside
   an event loop / request handler, blocking the thread that should stay free;
   sync calls in otherwise-async code.
7. **Caching opportunities** — a pure, repeated, expensive computation or fetch
   whose result could be memoized or cached; recomputing the same value across
   calls; missing use of an existing cache layer. Flag the opportunity; don't
   design a cache invalidation strategy.

For the detailed detection cues, code smells, and worked before/after examples in
each category, read `references/detection-guide.md`. Consult it when you want to
confirm a suspicion or need a crisp way to explain a finding — it is language-
agnostic and keyed to these same seven categories.

## Severity — so the author knows what to fix first

Rate each finding. Be honest; inflating severity trains people to ignore you.

- **Critical** — will cause real pain at expected scale (N+1 on a list endpoint,
  blocking I/O in a request handler, unbounded memory growth). Should block merge.
- **Major** — meaningfully wasteful and worth fixing before merge, but not a fire.
- **Minor** — a real inefficiency that's cheap to fix; nice-to-have.
- **Nit** — micro-optimization; mention only if you're already there.

Guard against false alarms: an N+1 over a list that is always tiny and bounded,
or a "blocking" call that runs once at startup, is not worth a Critical. Say so
if the concern is theoretical.

## How to work

1. Get the diff. If given a PR number or URL, pull it with `gh` (see below). If
   given a file, a pasted diff, or a branch, work from that.
2. Read the changed code plus enough surrounding code to follow the data flow —
   you can't spot an N+1 without seeing where the loop's data comes from, and you
   can't judge "hot path" without knowing who calls it.
3. Walk each of the seven categories against the diff.
4. For every finding: name the file and line, say what's inefficient and *why it
   costs* (what grows with what), and give a concrete, minimal fix. Show a tiny
   before/after only when it makes the fix unmistakable.
5. If you find nothing real, say so plainly — a clean "no performance concerns in
   this diff" is a valid and valuable result. Do not manufacture findings.
6. Fill in the template below. This is the deliverable.
7. When you reviewed a real PR (you were given a PR number or URL), post the
   finished review back to that PR as a comment with `gh` — this is the default
   final step, not an opt-in. See "Posting the review back" below. When you only
   reviewed a pasted diff, a local file, or a branch with no associated PR, there
   is nothing to post to — just output the review.

## Output — always use this template

Every review is delivered using `assets/review-template.md`. Read that file and
fill it in. It exists so reviews are consistent and so the author can see at a
glance who reviewed it and with which model — the header explicitly carries the
**Performance Reviewer** role and the **model name** (e.g., Claude Opus 4.8,
Claude Sonnet 5, DeepSeek-V3). Fill the model field with the model you are
actually running as; if you are unsure, write your best identification rather
than leaving it blank.

Keep findings ordered by severity, highest first. If a section (e.g., "Caching")
has no findings, omit it rather than padding it. The summary line at the top
should let a busy author decide in one read whether this blocks merge.

## Pulling a PR with the GitHub CLI (`gh`)

If the user points you at a PR rather than pasting a diff, use `gh`. It must be
installed and authenticated (`gh auth status`).

```bash
# Full diff of a PR (best default for reviewing)
gh pr diff 123

# Diff of a PR in another repo
gh pr diff 123 --repo owner/name

# PR metadata: title, description, changed files
gh pr view 123

# List only the files touched (useful to scope the review)
gh pr view 123 --json files --jq '.files[].path'

# Review a PR by URL — gh accepts the URL in place of the number
gh pr diff https://github.com/owner/name/pull/123

# Check out the branch locally if you need to run/inspect the code
gh pr checkout 123
```

Prefer `gh pr diff` to get the changes, and `gh pr view` when you need the
description or the list of touched files to scope your read.

## Posting the review back to the PR

When you reviewed a real PR (pulled via `gh` from a number or URL), posting the
completed review as a PR comment is the final step of the workflow — do it
automatically once the review is written. Write the filled-in template to a file
and post it verbatim so the formatting (and the Performance Reviewer / model
header) survives:

```bash
# Write the finished review to a file, then post it as a PR comment
gh pr comment 123 --body-file review.md

# In another repo, or by URL
gh pr comment 123 --repo owner/name --body-file review.md
gh pr comment https://github.com/owner/name/pull/123 --body-file review.md
```

Post the exact template output — do not summarize or trim it for the comment.
After posting, tell the user it's up and echo the comment URL that `gh` returns.

Two caveats. First, only post to a PR the user actually pointed you at; never
guess a PR number. If you're unsure which PR the diff belongs to, ask before
posting. Second, if the user reviewed a pasted diff, a local file, or a branch
with no PR, skip this step — there's nothing to comment on — and just hand back
the review. If a `gh` post fails (not authenticated, no write access), report the
error and give the user the review text so nothing is lost.
