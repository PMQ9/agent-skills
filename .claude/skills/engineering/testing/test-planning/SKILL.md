---
name: test-planning
description: Use this skill to design a test plan for a feature before writing tests — derive test cases from acceptance criteria, systematically generate edge cases, decide which layer (unit / integration / e2e / manual) each case belongs in, and write the plan to a markdown file the team can review. Trigger on phrases like "write a test plan", "what should we test", "test strategy for", "what are the edge cases", "QA plan", "test coverage", "test cases for this feature", "what tests do we need", or whenever a feature has acceptance criteria (or a requirements doc) and the next sensible step is figuring out what proves it works. This skill is about deciding *what* to test; use the integration-testing skill for *how* to actually write integration tests in pytest/Jest/etc., and the engineering:testing-strategy skill for higher-level test architecture questions.
---

# Test Planning

A test plan is a written argument that this feature works — not the tests themselves, but the case for *which* tests would prove it. Skipping this step is what produces test suites that hit every line of code but miss the failure modes that actually break in production. The line coverage was fine; nobody tested the empty-cart edge case, the second-time-clicked Submit button, or what happens at 11:59:59 on a leap second.

The job of this skill is to turn "this feature is built" into "we have evidence this feature works under the conditions we can articulate and a list of conditions we know we haven't tested." The plan is the artifact; the tests are the implementation.

## When to invoke this skill

Use it when:

- A feature has acceptance criteria (ideally a requirements doc at `docs/requirements/<slug>.md`) and you need to plan tests against them.
- You're about to write tests and you're not sure what's worth writing.
- A bug was reported and you want to expand the test plan to cover the gap and any neighboring ones.
- You're reviewing a PR and want to ask "what's missing from this test coverage?" in a structured way.
- You're handing a feature to QA / manual testing and you need a list of cases.

Skip it when the change is a one-line fix with an obvious single test, or when the feature is small enough that the test plan would be longer than the tests.

## How this skill relates to the others

- **requirements-analyst** produces the spec directory at `docs/requirements/<slug>/` with stable typed IDs (`FN-NNN`, `SEC-NNN`, `PERF-NNN`, ...) across one or more category files (`functional.md`, `security.md`, `performance.md`, ...). This skill turns those requirements into tests. If the spec is missing or thin (Open Questions touching testability, ACs in adjective form), the first move is to back up — guessing at requirements while writing tests produces tests that drift from intent. The test plan's coverage matrix is keyed on typed requirement IDs (e.g., `bulk-csv-import#SEC-003`), not on free-text AC summaries, so the trace stays unambiguous.
- **Inherited policies.** If a category file lists `_policies/<slug>` inheritances, the policy's REQs are tested at the policy level (one canonical test plan lives alongside each policy file, or a project-level test plan covers all policies). Feature-level tests reference policy tests by ID rather than re-implementing them.
- **integration-testing** covers how to actually wire up testcontainers, fixtures, fake third parties, transactional rollback patterns, and so on. This skill stops at "we need an integration test that does X" and hands off.
- **engineering:testing-strategy** is for higher-level questions — pyramid shape, what to mock, when to skip a layer. This skill operates inside that strategy on a specific feature.

A reasonable flow is: requirements → test plan → (now you know what tests to write) → use the relevant testing skill for the implementation.

## Core operating principles

**Every test cites the REQs it covers.** A test case that doesn't carry a `Covers: <spec-slug>#REQ-NNN` line is either testing implementation detail (delete or convert to a unit test) or revealing a requirement that should be in the spec sheet (back up and add it via the requirements-analyst skill). Every requirement in the spec gets at least one test; every test traces to a requirement. This is the trace that lets someone six months from now answer "why does this test exist?" by reading one line.

**Tests are append-only too.** Test cases carry stable IDs (`T-001`, `T-002`, ...) inside the test plan. When a test becomes wrong because the underlying REQ was superseded, mark the test `Status: Superseded by T-NNN` and add a new test. Don't rewrite the test in place — the project's QA history lives in the test plan, not in git blame.

**The mapping is one-to-many, not one-to-one.** A REQ of the form "given X, when Y, then Z" typically wants a happy-path test, at least one negative test, and one or two edge cases around boundaries in X and Y. If a REQ produces zero tests, either the REQ is decorative or you missed it.

**Edge cases come from a checklist, not from inspiration.** Humans are bad at thinking of edge cases unprompted. They're good at running through a checklist and asking "does this case apply here?" Use the inventory below systematically rather than waiting for cases to come to mind.

**Pick the layer deliberately.** Most test cases can be written at multiple layers (unit / integration / e2e / manual). The cheapest layer that gives meaningful confidence is the right one. A unit test that mocks the database isn't testing the same thing as an integration test that uses a real one; pick based on what failure modes you want to catch.

**State the coverage gaps as plainly as the coverage.** Every test plan ships with a list of things it doesn't cover, and why. Untested code paths, untested concurrency, untested environments, untested time-of-day behavior — list them. The plan is more honest than 100% line coverage; line coverage doesn't know what's hard.

**Test the failure modes, not just the happy paths.** Most of the cost of bugs is in the cases nobody thought of. The negative tests — what should fail, what error should the user see, what should *not* happen — are usually where the bugs are. Plan more negative cases than positive ones.

**Tests are documentation that runs.** A test plan that someone reads in six months should be enough to understand what the feature does, in terms of inputs and outcomes. If the plan reads as "test 1, test 2, ..." with no semantics, it's a list, not a plan.

## The plan workflow

1. **Locate the spec directory.** Read `docs/requirements/<slug>/_overview.md` and each category file present (`functional.md`, `security.md`, `performance.md`, ...). If the directory doesn't exist and the feature is non-trivial, stop and write the spec first (run the requirements-analyst skill, or surface the gap to the user). Trying to write a test plan against a verbal description is wasted work.

2. **Run the gate check.**
   - Every requirement (across all category files) has at least one AC.
   - Every AC is testable (concrete, observable, pass/fail).
   - No AC contains unqualified adjectives ("fast", "user-friendly").
   - Open Questions don't block testability.
   - Statuses of the requirements you're testing against are `Accepted`, not `Draft` or `Superseded`.
   - Inherited `_policies/` files exist and have their own test coverage referenced.
   If any check fails, push back to requirements-analyst before continuing. Do not write tests against ambiguous or unstable requirements.

3. **List the requirements in scope.** Copy each requirement's typed ID and one-line summary into the coverage matrix. Every requirement appears at least once. Inherited policies are listed separately at the top of the matrix with pointers to their own test files.

4. **For each requirement, write at least:**
   - The happy path test (the REQ's primary AC interpreted literally).
   - One or two boundary cases (just below / at / just above any threshold).
   - One negative case (what should happen if the precondition fails or the input is malformed).

5. **Sweep the edge-case checklist.** For each category that applies (inputs, time, auth, concurrency, errors, data state, locale, accessibility), ask whether the feature touches that surface, and add tests for the cases that apply. Each new test case must declare which REQ-IDs it covers. Most features touch 3-5 of these categories.

6. **Decide the layer for each test.** Use the layer guide below. When in doubt, write it at the lowest layer that exercises the failure mode you care about.

7. **Identify the cases you're not testing.** Things you considered but decided not to test, with a one-line reason. This is the "Known gaps" section. If a REQ is in the spec but you're not testing it (and not putting it in Known gaps), the coverage matrix exposes that — that's the point.

8. **Save the plan** to `docs/test-plans/<slug>.md` (same slug as the spec sheet). Append `- Test plan: docs/test-plans/<slug>.md` to the spec sheet's project-level `Linked artifacts` section. For each REQ tested, append `- Tests: T-001, T-005, T-012` to that REQ's per-block Linked artifacts.

## Edge-case inventory

Run through these whenever you're planning tests. Most features touch four or five categories; the rest are honestly answered "not applicable here."

**Inputs:**
- Empty / null / undefined.
- Min length / max length / over max length.
- Min value / max value / over max (int overflow, length overflow, file size).
- Negative numbers / zero / one.
- Whitespace only, leading/trailing whitespace.
- Unicode (emoji, RTL scripts, combining characters), characters that look like control characters.
- Characters with special meaning in your stack: quote marks, backslashes, SQL chars, HTML/JS chars, shell metacharacters.
- Duplicate submissions.
- Submitting a form with stale data (changed under you).

**Time:**
- Leap days, leap seconds, end of month, end of year.
- DST transitions (spring forward, fall back) in the user's timezone *and* in UTC.
- Operations spanning midnight in the user's timezone.
- Dates in the far past and far future.
- Operations where wall-clock time matters (rate limits, expirations, scheduled jobs).
- Clock skew between client and server.

**Auth & authorization:**
- Unauthenticated request to an authenticated endpoint.
- Expired / revoked token.
- User with the wrong role / scope.
- Deleted / disabled user with a still-valid token.
- Cross-tenant access (user A trying to access user B's data).
- Privilege escalation (regular user calling an admin endpoint).
- Missing CSRF token / wrong origin for state-changing requests.

**Concurrency:**
- Two requests modifying the same record at once.
- The same operation issued twice with the same idempotency key.
- A long-running write competing with a short-running read.
- Operations interleaved across multiple instances of the service.
- Optimistic concurrency: write rejected because version changed.

**Errors and failure modes:**
- Downstream service times out.
- Downstream returns 5xx.
- Downstream returns malformed response (truncated JSON, unexpected schema).
- Network partition during a multi-step operation — what state does the system end up in?
- Disk full / out of memory during a write.
- Database connection pool exhausted.
- Retry storms (does retry-with-backoff actually back off?).

**Data state:**
- Record doesn't exist yet (404 / create-or-update semantics).
- Record exists but is in an unexpected state (soft-deleted, archived, locked).
- Foreign key target missing (orphan reference).
- Aggregate empty (zero items in cart, zero orders, no children).
- Large aggregate (cart with 1000 items, customer with 10000 orders).
- Stale cache vs fresh DB.

**Locale and presentation:**
- Multiple languages, including RTL (Arabic, Hebrew).
- Currency rounding (especially currencies with no decimal places — JPY — vs three decimal places — JOD).
- Date / number format expectations differ by locale.
- Pluralization rules in the user's language.
- Long translated strings overflowing UI.

**Accessibility:**
- Keyboard-only navigation completes the flow.
- Screen reader announces meaningful content (labels, errors, state changes).
- Color is not the only signal for state.
- Focus management on dialogs, errors, dynamic content.

**Performance and scale (when the AC has a perf bar):**
- Single request at the latency SLO.
- N concurrent requests at the throughput SLO.
- Large payload edge cases.
- Cold cache vs warm cache.

Don't try to cover every category in every plan. Pick the four or five that apply and cover them well; mention the rest in Known Gaps if relevant.

## Layer guide: which test goes where

| Layer | Fast? | What it proves | Use when |
|---|---|---|---|
| **Unit** | Very fast (ms) | Pure logic: given inputs, function returns expected output. | Calculation, parsing, validation, business rules. Always mock I/O. |
| **Integration** | Slow (seconds) | Code and a real dependency agree: my code and Postgres saw the same row. | DB queries, queue interactions, HTTP boundary, third-party API contracts (with recorded fakes). |
| **Contract** | Fast | Two services agree on the message shape and semantics. | Producer/consumer boundary you don't own end-to-end. Pact-style. |
| **End-to-end** | Slowest | Whole system, real user-ish flow. | A small number of smoke tests on the critical paths. Don't try to cover every case here. |
| **Manual exploratory** | Human time | Cases that are hard to script: visual layout, UX intuition, exploratory edge poking. | Pre-release pass on UI changes, accessibility, anything where automation has diminishing returns. |

Rules of thumb:

- A unit test that mocks the database is not proving the SQL works. If you care about the SQL working, write the integration test.
- An end-to-end test that's flaky 1% of the time will fail roughly every fifth CI run if you have 20 of them. Keep e2e narrow.
- Manual tests belong in the plan if they're the cheapest way to catch a specific class of bug (visual regressions, real screen-reader behavior). Don't apologize for them — they're cheaper than the test infrastructure to fully automate them.

## The plan template

Save to `docs/test-plans/<feature-slug>.md`. Use the same slug as `docs/requirements/<slug>.md`.

```markdown
# Test plan: <feature title>

**Status:** Draft | Under review | Approved | Complete
**Linked requirements:** [docs/requirements/<slug>.md](../requirements/<slug>.md)
**Last updated:** YYYY-MM-DD

## Scope

One paragraph: what this plan covers and what it doesn't. Reference the requirements
doc's acceptance criteria — by AC number, not by re-summarizing.

## Strategy

Which layers will dominate this plan and why. What's real (DB, queue, third party) vs
mocked. What test data approach (transactional rollback, per-test schema, fixtures).
Two or three paragraphs at most.

## Coverage matrix

Every requirement across all category files in the spec directory appears here. Every test below appears in this matrix. The typed ID prefix (FN/SEC/PERF/...) tells you which category file it lives in.

| Requirement                          | Tests                |
|--------------------------------------|----------------------|
| <spec-slug>#FN-001                   | T-001, T-002, T-007  |
| <spec-slug>#FN-002                   | T-003                |
| <spec-slug>#SEC-001                  | T-010, T-011         |
| <spec-slug>#PERF-001                 | T-020                |
| <spec-slug>#A11Y-001                 | T-030 (manual)       |
| _policies/security-baseline#SEC-002  | (see policies/security-baseline test plan) |
| ...                                  | ...                  |

Inherited policy requirements are tested at the policy level; cite the canonical test plan rather than re-implementing the tests.

## Test cases

Each test case carries a stable `T-NNN` ID. Test cases are append-only: if a test
becomes wrong because the REQ was superseded, mark the test Superseded and add a
new one. Don't rewrite in place.

### Happy paths

#### T-001 — <short title>
- **Covers:** <spec-slug>#FN-001
- **Status:** Active | Superseded by T-NNN
- **Layer:** integration
- **Preconditions:** <DB state, user state, config>
- **Steps / inputs:** <what's done>
- **Expected outcome:** <what's observed>

#### T-002 — ...

### Boundary and edge cases

#### T-005 — <short title>
- **Covers:** <spec-slug>#FN-001
- **Status:** Active
- **Layer:** unit
- **Edge category:** input — empty string
- **Preconditions:** ...
- **Steps / inputs:** ...
- **Expected outcome:** ...

(Repeat for the edge categories that apply.)

### Negative tests / failure modes

#### T-010 — <short title>
- **Covers:** <spec-slug>#FN-001, <spec-slug>#REQ-003
- **Status:** Active
- **Layer:** integration
- **Failure mode:** downstream returns 503
- **Preconditions:** ...
- **Steps / inputs:** ...
- **Expected outcome:** <user-visible behavior, system state>

### Non-functional checks

(Performance, security, accessibility, compatibility — when REQs require them.)

#### T-020 — P95 latency on the search endpoint
- **Covers:** <spec-slug>#PERF-001
- **Status:** Active
- **Layer:** load test
- **Setup:** ...
- **Expected outcome:** P95 ≤ 300ms under 50 concurrent users.

## Known gaps

Things we considered and chose not to test, with a one-line reason each.

- We do not test the legacy API path that was removed in <ADR-NNNN>. No production
  consumer left.
- We do not test concurrent writes from >50 instances. Out of scope for v1; covered
  by R-3 in the requirements doc.
- Browser compatibility tested only on Chrome and Safari. Firefox/Edge handled by
  the existing E2E suite.

## Risks

Anything the plan will not catch even when fully implemented — areas where automated
tests have a known blind spot.

- Visual regressions on the new dashboard chart aren't caught by unit/integration;
  rely on T-030 (manual) for now.
- Time-of-day bugs near DST require manual run with a clock override; covered by
  T-018, but only if executed.

## Revision history

- YYYY-MM-DD — initial draft.
```

## Writing the cases: in practice

**Title each case after what it proves, not what it does.** "Empty cart submit returns 400 with `empty_cart` error" is better than "Test empty cart." The title is half the documentation.

**Be specific about preconditions.** "User is logged in" is too vague. "User is logged in as a paid customer, has one item in cart, has no saved payment method" is enough for someone else to reproduce.

**Expected outcome is observable, not implementation.** "The database row is updated" is implementation; "GET /orders/123 returns status `paid`" is the observable outcome. Aim for the latter.

**Negative tests deserve as much specificity as positive ones.** "Returns 400" is incomplete; specify the error code or message the client sees, because that's what consumers depend on. A change from `INVALID_INPUT` to `BAD_REQUEST` breaks clients even if the status code didn't move.

**Sometimes a test is a paragraph.** Some cases — especially manual ones, or load tests — don't fit the steps/preconditions/expected-outcome template cleanly. That's fine; write them as a paragraph that includes the same information. The template is a default, not a law.

**Tests for "this should not happen" need an observable signal.** "The system should not double-charge the user" — *what* observable do we check? The number of charge records? An idempotency-key assertion? A log line that we look for? An assertion that's literally `assert not bug` has no failure mode to verify.

## Anti-patterns to flag immediately

- **"Test everything" — no priority.** A plan with 80 test cases that are all "P0" is unfaithful about cost. Prioritize: which ten cases must run on every PR, which forty on nightly, which thirty are manual?
- **Coverage by line, not by behavior.** "We covered 92% of lines" tells you nothing about whether the right cases ran. Optimize for "we covered every AC plus the edge cases we listed."
- **Mocking the thing under test.** A test for the database adapter that mocks the database isn't testing anything. Use integration tests when the integration is the point.
- **Snowflake fixtures.** A test that depends on a 200-line fixture nobody can read is a test that nobody can maintain. Build small, scoped fixtures inside the test or in narrow factories.
- **Asserting on log lines as the primary observable.** Logs are a useful signal but a fragile assertion target — they change too often. Assert on state and on returned values; check logs as a secondary thing.
- **Tests that depend on test order.** If T-005 only passes if T-003 ran first, you have one test, not two. Either combine them or isolate them.
- **No negative tests.** A test plan with only happy paths will ship the failure modes intact. Most bugs live in the negatives.
- **Tests with no covered AC.** Either you missed adding the AC to the requirements, or the test is testing something the spec doesn't require. Either way, surface the mismatch.

## When the requirements doc is missing or incomplete

If you've been asked for a test plan and there's no requirements doc, your first move is to either:

1. **Write a thin requirements draft first** (use the requirements-analyst skill) — even a one-page sketch with ACs is enough to anchor the test plan.
2. **Or, if the feature is small and the user just wants tests now**, extract implicit ACs from the conversation, list them at the top of the test plan in a "Working acceptance criteria" section, and ask the user to confirm. The test plan's coverage matrix then references those.

A test plan whose ACs are invisible is hiding the most important content. Make the ACs explicit even if they're informal.

## Output and follow-on

When the plan is written:

1. Save to `docs/test-plans/<slug>.md`.
2. Append to the requirements doc's "Linked artifacts" section: `Test plan: docs/test-plans/<slug>.md`.
3. Point out: which sections of the plan are likely to need the most work (usually the edge cases and the negative tests), and which cases are best suited to the integration-testing skill (so the user can hand off the implementation).

The plan exists to be executed. Finish by naming the next move — usually "implement the integration tests" or "schedule the manual pass."
