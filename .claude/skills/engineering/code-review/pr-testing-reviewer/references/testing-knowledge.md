# Testing knowledge for the Test Reviewer

Distilled from the `test-planning` and `integration-testing` skills, reframed for
*reviewing* a change rather than writing tests from scratch. Read this when you want
to be systematic about what to look for — especially the edge-case sweep (so gaps
come from a checklist, not from whatever you happened to think of), the assertion
triad, and the flakiness sources. The core idea throughout: humans (and models) are
bad at inventing edge cases on demand and good at running down a checklist and
asking "does this one apply to the change in front of me, and is there a test for
it?" Use it that way.

## Table of contents

1. Edge-case inventory — the systematic gap sweep
2. The assertion triad — what a good test asserts
3. Determinism — the sources of brittleness/flakiness
4. Layer fit — is each test at the right level?
5. Anti-patterns — smells that make a green suite meaningless
6. Judging assertion quality — the "break it and see" method

---

## 1. Edge-case inventory — the systematic gap sweep

For each changed behavior, walk these categories and ask: *does the change touch
this surface, and if so, is there a test that pins it?* Most changes touch four or
five categories; the rest are honestly "not applicable here" — say so rather than
padding. Name the specific missing case, not the category.

**Inputs**
- Empty / null / undefined / missing field.
- Min length, max length, one-past-max (overflow: int, string length, file size).
- Negative, zero, one (the classic off-by-one neighbourhood).
- Whitespace-only; leading/trailing whitespace.
- Unicode: emoji, RTL scripts, combining characters, homoglyphs.
- Characters with special meaning in the stack: quotes, backslashes, SQL/HTML/JS
  chars, shell metacharacters.
- Duplicate submission; submitting stale data that changed underneath.

**Time**
- Leap day/second, end of month, end of year.
- DST transitions (spring forward, fall back) in the user's TZ *and* in UTC.
- Operations spanning midnight in the user's timezone.
- Far past / far future dates.
- Wall-clock-dependent behavior: rate limits, expirations, scheduled jobs, TTLs.
- Clock skew between client and server.

**Auth & authorization**
- Unauthenticated request to an authenticated endpoint.
- Expired / revoked token; deleted-or-disabled user with a still-valid token.
- Wrong role / insufficient scope; privilege escalation (regular user hits admin path).
- Cross-tenant access (user A reaching user B's data).
- Missing CSRF token / wrong origin on state-changing requests.

**Concurrency**
- Two requests modifying the same record at once.
- Same operation issued twice with the same idempotency key (does it dedupe?).
- Long write competing with a short read; interleaving across service instances.
- Optimistic-concurrency rejection (write refused because version changed).

**Errors and failure modes** (usually the richest source of gaps)
- Downstream times out / returns 5xx / returns malformed response (truncated JSON,
  unexpected schema).
- Network partition mid-multi-step-operation — what state is left behind?
- Disk full / OOM during a write; DB connection pool exhausted.
- Retry behavior: does retry-with-backoff actually back off, and stop?

**Data state**
- Record doesn't exist yet (404 vs create-or-update semantics).
- Record in an unexpected state: soft-deleted, archived, locked.
- Orphan reference (foreign-key target missing).
- Empty aggregate (zero items, zero orders) and large aggregate (1,000 items).
- Stale cache vs fresh DB.

**Locale and presentation**
- Multiple languages incl. RTL; long translated strings overflowing UI.
- Currency rounding: zero-decimal (JPY) vs three-decimal (JOD); money as float.
- Date/number format and pluralization differing by locale.

**Accessibility** (for UI changes)
- Keyboard-only completion of the flow; focus management on dialogs/errors.
- Screen-reader announces labels, errors, state changes; color isn't the only signal.

**Performance/scale** (only when an acceptance criterion sets a bar)
- One request at the latency SLO; N concurrent at the throughput SLO.
- Large-payload edge; cold vs warm cache.

A change to test-worthiness: **plan on there being more negative cases than positive
ones.** Most of the cost of bugs lives in the cases nobody thought of, and the happy
path is almost always the one that *is* tested. A review that only confirms the
happy path is covered has checked the least valuable half.

---

## 2. The assertion triad — what a good test asserts

For a test to meaningfully protect a behavior, look for up to three things. The
third is the most-skipped and often the most valuable:

1. **The observable result** — the return value, the API response, the emitted
   message. (Responses are derived from *intent*; they can lie about what actually
   happened.)
2. **The persistent side effect** — the DB row, the queued message, the file
   written. (This is derived from what *actually* happened. Bugs hide in the gap
   between 1 and 2 — a test asserting only the response misses them.)
3. **What did *not* happen** — no second row, no duplicate event, no charge to the
   wrong account, downstream *not* called. "We don't double-charge" and "an empty
   message is not sent" are properties worth an explicit assertion.

When reviewing, flag a test that asserts only (1) when (2) or (3) is where the risk
lives. "It returns 201" is not the same claim as "a row with status=pending now
exists and no duplicate was created."

Also: **assert observable outcomes, not implementation.** "The DB row updated" via
poking internals is weaker and more brittle than "GET /orders/123 returns
`paid`." And **negative assertions need a real signal** — `assert not bug` has no
failure mode; there must be an observable (a count, an idempotency-key check, a
specific error code) that actually goes red.

---

## 3. Determinism — the sources of brittleness/flakiness

A brittle test fails for reasons unrelated to the behavior it should protect, which
trains the team to rerun-until-green, `@retry`, or delete it — so it protects
nothing. Almost all flakiness traces to three sources; hunt for them specifically:

- **Time.** `datetime.now()` / `new Date()` sampled inside code (or a test) that
  asserts time-dependent behavior. Exact equality on a computed time value
  (`toBe(30)` on elapsed minutes) is a flake — any elapsed millisecond breaks it.
  The fix the reviewer should recommend: inject the clock / pass `now` explicitly,
  or use a freezer (`time-machine`/`freezegun`, `vi.useFakeTimers`), and use
  `toBeCloseTo`-style tolerance where a real duration is unavoidable.
- **Random / IDs.** A UUIDv4 generated in production and asserted against a fixed
  string in the test. Recommend injecting the RNG / ID generator.
- **Concurrency / ordering.** Asserting on the order of inherently unordered things
  (dict/set iteration, query results without `ORDER BY`, event arrival). Recommend
  set-equality not list-equality, and "X happened, then Y happened" rather than
  "the third event was Y."

Two more brittleness tells worth flagging:

- **`sleep(N)` instead of polling a predicate.** Every fixed sleep is a future flake
  — it's a duration, not a deadline, so it breaks under CI load. Recommend a
  deadline-bounded poll (`wait_for(predicate, timeout=...)`).
- **Passes locally, fails in CI.** The usual suspects: time/TZ (CI is UTC), parallel
  execution (CI runs concurrently), data leaks between tests (order-dependence), and
  slower CI turning a `sleep(0.1)` into a race. If the diff introduces any of these,
  call it out even though CI is currently green.

And for tests that hit external HTTP: a test that can silently reach the real
network (no `onUnhandledRequest: "error"`, no
`assert_all_requests_are_fired=True`) will do so in surprising ways — flag missing
guards on the mock boundary.

---

## 4. Layer fit — is each test at the right level?

The cheapest layer that gives meaningful confidence is the right one, and a test at
the *wrong* layer often proves nothing:

- A **unit test that mocks the database is not testing the SQL.** If the behavior at
  risk is the query, the migration, the transaction boundary — the review should ask
  for an integration test against a real DB, because the mock will happily agree with
  a broken query.
- Conversely, an **integration test that mocks the thing it's supposed to integrate
  with** is just a slow unit test wearing a costume — flag it as mislabeled and
  either demote it or make the dependency real.
- **Mock what you don't own; integrate with what you do.** Third-party APIs
  (Stripe, Twilio, OpenAI) should be stubbed/recorded; your own DB/queue/Redis
  should be real (containers) when the wiring is the point.
- **E2E is for a few smoke tests on critical paths, not for covering every case** —
  flaky-at-1% × twenty tests ≈ a failure every fifth CI run. If a change piles edge
  cases into E2E that belong in unit/integration, that's a finding.

Quick reference:

| Layer | Proves | Right when |
|---|---|---|
| Unit | Pure logic: inputs → output | Calculation, parsing, validation, business rules. Mock I/O. |
| Integration | Code + a real dependency agree | DB queries, queue, HTTP boundary, third-party contract (recorded fake). |
| Contract | Two services agree on message shape | Producer/consumer boundary you don't own end-to-end. |
| E2E | Whole system, real-ish flow | A few smoke tests on critical paths only. |
| Manual | Hard-to-script cases | Visual layout, real screen-reader behavior, exploratory. |

---

## 5. Anti-patterns — smells that make a green suite meaningless

Flag these on sight; each one is a way a passing suite fails to protect the code:

- **Coverage by line, not by behavior.** "92% of lines" says nothing about whether
  the right *cases* ran. A line can execute under a test that asserts nothing about
  it. Reason about behaviors and acceptance criteria, not the percentage.
- **Mocking the thing under test.** A test for the DB adapter that mocks the DB, a
  test for the retry logic whose mock never fails — it exercises nothing.
- **No negative tests.** Happy-path-only suites ship the failure modes intact.
- **Assertion on log lines as the primary check.** Logs change constantly; they're a
  fragile assertion target. Assert on state and return values; treat logs as
  secondary.
- **Snowflake fixtures.** A 200-line fixture nobody can read, or a shared fixture
  that grows a field and breaks 50 tests. Prefer small test-data builders where each
  test states only what it cares about.
- **Order-dependent tests.** If T-b only passes when T-a ran first, that's one test
  masquerading as two, and a CI-parallelism flake waiting to happen.
- **A test with no behavior it protects.** If you can't say which requirement or
  behavior a test guards, it's either testing an implementation detail (brittle) or
  it reveals an unstated requirement. Either way, surface the mismatch.
- **"Test everything," no priority.** Eighty cases all marked critical is dishonest
  about cost — distinguish what must run on every PR from nightly from manual.
- **Migrations applied differently in test vs prod** (`create_all()` in tests,
  Alembic in prod) — "works in tests, fails in prod." Down-migrations untested in CI
  are a production incident waiting for the worst moment.

---

## 6. Judging assertion quality — the "break it and see" method

The single most convincing test-review technique: mentally (or actually) introduce
the bug the test should catch, and check whether the assertion would go red.

- Flip a boundary operator (`>=` → `>`), negate a condition, change a returned
  constant, delete a branch, swap a payload field name. If every test still passes,
  the behavior is unguarded — and you can *say exactly that* in the finding, which is
  far more persuasive than "consider more coverage."
- A finding of the form "change line 42 from `>=` to `>` and the whole suite stays
  green — the boundary at exactly `limit` is unasserted" is worth ten vague
  suggestions. When you can write the missing test case or the strengthened
  assertion, write it.
- Be honest about what you couldn't verify: a fixture in `conftest.py`, a shared
  helper, or coverage config you couldn't see might already cover a case. Mark those
  as questions to the author, not as asserted gaps.
