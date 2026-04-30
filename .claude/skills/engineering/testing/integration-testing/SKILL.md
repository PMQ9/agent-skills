---
name: integration-testing
description: Use this skill for any work involving integration tests — writing new ones, running them, or debugging failures. Trigger on phrases like "integration test", "write a test that hits the database", "test the API end-to-end with a real Postgres", "test that uses testcontainers", "spin up the service and call it", "mock this third-party API", "test the consumer against a real Kafka", "this test is flaky", "investigate a failing CI run", "the test passes locally but fails in CI", and any request that mixes "real" infrastructure (DB, queue, HTTP server) with assertion-driven tests. Covers pytest, Jest/Vitest, and language-agnostic principles. Always use this skill when the user wants to test the wiring between a service and its real dependencies, even if they don't say the words "integration test".
---

# Integration Testing

Integration tests verify that components work together against real (or close-to-real) dependencies — your service hitting a real Postgres, your consumer reading from a real Kafka, your handler calling a recorded version of a third-party API. They sit between unit tests (single function, mocks for everything) and end-to-end tests (whole system, real users, real network). The goal is to catch the bugs that only show up when wiring meets wiring: schema drift, transaction semantics, serialization mismatches, retry behavior under real timeouts.

The reason integration tests are worth the slowness is that the hardest production bugs almost always live in the seams. Unit tests with mocks tell you "my code does what I think it does"; integration tests tell you "my code and Postgres agree about what happened." Those are different statements.

## When to write one

Reach for an integration test when the behavior you care about depends on something **outside your code's control**:

- The database (migrations applied, indexes in place, transaction isolation behaving)
- An HTTP boundary (request parsing, status codes, content negotiation, auth middleware)
- A queue or stream (delivery semantics, ordering, ack/nack, DLQ)
- A third-party API (auth flow, rate limits, error shapes — usually with a recorded fake)
- Cross-component flow (request → handler → repo → DB → outbox → publisher)

If you can express the bug as "X works in isolation but breaks when wired to Y," you want an integration test. If the only thing you're checking is `f(x) == y`, write a unit test instead — they're 100× faster and don't deserve the integration tax.

## The cardinal decisions

Before writing the test, decide three things explicitly. Most flakiness and most slowness comes from getting one of these wrong.

**1. What's real, what's mocked.** Real DB, real queue, *fake* third-party APIs (recorded or stubbed). External services you don't own should not be hit from tests — they're slow, rate-limited, and they break your CI when their staging environment goes down. Use WireMock / MSW / `pytest-httpx` / `nock` to stand in. Real infra you own and that has deterministic behavior — DB, Redis, RabbitMQ, Kafka — should be real, via testcontainers or docker-compose.

**2. Test data lifecycle.** Three viable patterns, in roughly this order of preference:

- **Transactional rollback** — open a transaction at test start, run the test inside it, rollback at end. Fast, deterministic, no cleanup code. Works for anything DB-only that doesn't span its own transactions.
- **Per-test schema reset** — truncate or recreate tables before each test. Slower but works when the code under test commits its own transactions.
- **Per-test isolated DB / namespace** — each test gets a fresh DB or schema. Slowest but bulletproof. Use when tests can't share a DB (e.g., schema migrations under test).

**3. Test isolation.** If two tests can affect each other, you have one test, not two. Order-dependent test suites are tech debt that compounds. Either fully isolate (above) or accept that you'll spend an hour every two weeks debugging a heisenbug.

## pytest

The pytest patterns below are the workhorses. Adapt freely.

### Real Postgres via testcontainers

```python
# tests/conftest.py
import pytest
from testcontainers.postgres import PostgresContainer
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

@pytest.fixture(scope="session")
def pg_container():
    with PostgresContainer("postgres:16-alpine") as pg:
        yield pg

@pytest.fixture(scope="session")
def engine(pg_container):
    engine = create_engine(pg_container.get_connection_url(), future=True)
    # Apply migrations once per session — alembic, sqlalchemy create_all, raw SQL, whatever.
    with engine.begin() as conn:
        conn.execute(text(open("schema.sql").read()))
    return engine

@pytest.fixture
def db_session(engine):
    """Transactional rollback — every test sees a clean DB.

    Uses the SQLAlchemy "join an external transaction" pattern: an outer
    transaction wraps the test, the session runs inside a SAVEPOINT, and
    any session.commit() inside production code is rewritten to release
    the SAVEPOINT (not the outer transaction). Without this, a single
    session.commit() in the code under test makes the outer rollback a
    no-op and tests bleed into each other.
    """
    connection = engine.connect()
    transaction = connection.begin()
    # expire_on_commit=False so test assertions can read attributes without
    # SQLAlchemy reissuing SELECTs after the savepoint releases.
    Session = sessionmaker(bind=connection, expire_on_commit=False, join_transaction_mode="create_savepoint")
    session = Session()
    try:
        yield session
    finally:
        session.close()
        transaction.rollback()
        connection.close()
```

The container starts once per session (slow); each test runs inside a transaction that's rolled back (fast). `scope="session"` is doing real work here — without it, you pay the container startup cost per test.

`join_transaction_mode="create_savepoint"` (SQLAlchemy 2.0+) is the modern shorthand for the older `after_transaction_end` listener dance. If you're on SQLAlchemy 1.4, use `session.begin_nested()` plus a listener that re-opens a SAVEPOINT after each release — the [SQLAlchemy docs "Joining a Session into an External Transaction"](https://docs.sqlalchemy.org/en/20/orm/session_transaction.html#joining-a-session-into-an-external-transaction-such-as-for-test-suites) recipe spells it out.

For containers that need readiness probes beyond TCP open (Kafka, Elasticsearch, custom services), use `Wait.forLogMessage(...)` / `wait_for_logs(...)` — a port being open is not the same as the service being ready, and "fast laptop, slow CI" flakiness usually traces back to this.

### FastAPI service test

```python
# tests/conftest.py (continued)
@pytest.fixture
def client(db_session):
    """Override get_db inside a fixture so the override is cleaned up
    even when the test fails. Doing app.dependency_overrides.clear() at
    the bottom of a test leaks the override on any earlier assertion."""
    from app.main import app
    from app.deps import get_db
    app.dependency_overrides[get_db] = lambda: db_session
    try:
        yield TestClient(app)
    finally:
        app.dependency_overrides.clear()


# tests/test_orders_api.py
def test_create_order_persists_and_returns_201(client, db_session):
    res = client.post("/orders", json={"sku": "ABC-123", "qty": 2})
    assert res.status_code == 201
    body = res.json()
    assert body["status"] == "pending"

    # Verify DB state, not just the response — the response can lie about what was persisted.
    row = db_session.execute(
        text("SELECT sku, qty, status FROM orders WHERE id = :id"),
        {"id": body["id"]},
    ).one()
    assert row.sku == "ABC-123" and row.qty == 2 and row.status == "pending"
```

The point of asserting both the response *and* the DB state is that responses are derived from intentions; rows are derived from what actually happened. Bugs hide in the gap. Defer FastAPI-specific test wiring (lifespan, dependency injection patterns, `httpx.AsyncClient` vs `TestClient`) to the [fastapi](../../backend/fastapi/SKILL.md) skill.

### Mocking an external HTTP service

```python
# tests/test_payment.py
import pytest_httpx

def test_charge_falls_back_when_stripe_returns_402(httpx_mock, db_session):
    httpx_mock.add_response(
        url="https://api.stripe.com/v1/charges",
        method="POST",
        status_code=402,
        json={"error": {"code": "card_declined"}},
    )

    result = charge_card(db_session, card_token="tok_visa", amount_cents=1500)

    assert result.status == "declined"
    assert result.reason == "card_declined"
    # Make sure we recorded the attempt — auditability bug magnet.
    attempts = db_session.execute(text("SELECT * FROM payment_attempts")).all()
    assert len(attempts) == 1 and attempts[0].outcome == "declined"
```

Pick the stub library that matches the HTTP client in production code:

- `httpx` → `pytest-httpx` (fixture-based, shown above) or `respx` (route-matcher API closer to MSW; better when assertions are about call counts and request bodies).
- `requests` → `responses`. Use `@responses.activate(assert_all_requests_are_fired=True)` to fail tests that stub URLs the code never calls.
- `aiohttp` → `aioresponses`.
- `urllib3` directly → also `responses` (it intercepts the urllib3 layer).

The pattern is the same across all four: capture the outbound HTTP at the transport layer, return a deterministic response, then assert on side effects.

### pytest-asyncio mode

Set `asyncio_mode = "auto"` in `pyproject.toml` (`[tool.pytest_asyncio]`) or `pytest.ini`. In `auto` mode every `async def test_*` is treated as an async test, no `@pytest.mark.asyncio` decorator needed. The default `strict` mode requires the decorator on every test, which is noise once you've decided your suite is async.

### Async / event-driven

```python
import asyncio

async def wait_for(predicate, timeout=5.0, interval=0.05):
    """Poll a predicate until it's true. The right way to assert on async side effects."""
    loop = asyncio.get_running_loop()
    deadline = loop.time() + timeout
    while loop.time() < deadline:
        if await predicate():
            return
        await asyncio.sleep(interval)
    raise AssertionError(f"predicate did not become true within {timeout}s")

@pytest.mark.asyncio
async def test_event_published_on_order_create(db_session, kafka_consumer):
    await create_order(db_session, sku="ABC", qty=1)

    async def saw_event():
        msg = await kafka_consumer.getone(timeout=0.1)
        return msg and msg.value["type"] == "order.created"

    await wait_for(saw_event)
```

`time.sleep(2)` is the canonical way to write a flaky test. Always poll a predicate with a deadline. The wait time is a *deadline*, not a duration — under load the test takes longer, but it still passes.

## Jest / Vitest (Node, TypeScript)

Same patterns, different tooling.

### Real Postgres via testcontainers

```typescript
// tests/setup.ts
import { PostgreSqlContainer, StartedPostgreSqlContainer } from "@testcontainers/postgresql";
import { Pool } from "pg";
import * as fs from "node:fs/promises";

let container: StartedPostgreSqlContainer;
export let pool: Pool;

export async function setup() {
  container = await new PostgreSqlContainer("postgres:16-alpine").start();
  pool = new Pool({ connectionString: container.getConnectionUri() });
  await pool.query(await fs.readFile("schema.sql", "utf8"));
}

export async function teardown() {
  await pool.end();
  await container.stop();
}
```

Wire setup/teardown via Vitest's `globalSetup` or Jest's `globalSetup` + `globalTeardown`. **Per-test isolation**: wrap each test in a transaction and rollback. With `pg`:

```typescript
// tests/db.ts
import { pool } from "./setup";
import type { PoolClient } from "pg";

export async function withRollback<T>(fn: (client: PoolClient) => Promise<T>): Promise<T> {
  const client = await pool.connect();
  try {
    await client.query("BEGIN");
    return await fn(client);
  } finally {
    await client.query("ROLLBACK").catch(() => {});
    client.release();
  }
}
```

Then in tests:

```typescript
test("creates order", async () => {
  await withRollback(async (db) => {
    const order = await createOrder(db, { sku: "ABC", qty: 2 });
    const { rows } = await db.query("SELECT * FROM orders WHERE id = $1", [order.id]);
    expect(rows).toHaveLength(1);
    expect(rows[0].status).toBe("pending");
  });
});
```

### HTTP service with supertest

```typescript
import request from "supertest";
import { app } from "../src/app";

test("POST /orders -> 201 + persists", async () => {
  await withRollback(async (db) => {
    app.locals.db = db; // or DI/injection however your app does it
    const res = await request(app).post("/orders").send({ sku: "ABC", qty: 2 });
    expect(res.status).toBe(201);

    const row = await db.query("SELECT * FROM orders WHERE id = $1", [res.body.id]);
    expect(row.rows[0].status).toBe("pending");
  });
});
```

### Mocking external HTTP with MSW

```typescript
import { setupServer } from "msw/node";
import { http, HttpResponse } from "msw";

const server = setupServer();
beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());

test("charge handles 402 from Stripe", async () => {
  server.use(
    http.post("https://api.stripe.com/v1/charges", () =>
      HttpResponse.json({ error: { code: "card_declined" } }, { status: 402 })
    )
  );

  const result = await chargeCard({ token: "tok_visa", amountCents: 1500 });
  expect(result.status).toBe("declined");
});
```

`onUnhandledRequest: "error"` catches the bug where a test silently hits a real third-party API because the mock URL changed. Don't run tests with `"warn"` or `"bypass"` — silent network calls in tests are a category of bug, not a feature.

### Vitest specifics

- Use `pool: "forks"` (or `threads` with care) and `isolate: true` for safety on shared global state.
- `--no-file-parallelism` is the escape hatch when tests pollute each other through global state you can't easily isolate. Reach for it last.
- `vi.useFakeTimers()` is fine for deterministic clocks, but **don't combine it with real network**. The HTTP client likely uses real timers internally and will hang.

## Patterns that apply across stacks

### What to assert

For every integration test, spell out three things:

1. **The observable result** — the API response, the function return, the published message.
2. **The persistent side effect** — what's in the DB, what's in the queue, what file got written.
3. **What did *not* happen** — no second row, no duplicate event, no charge to the wrong account.

The third one is the most-skipped and the most-valuable. "We don't double-charge" is a property worth asserting.

### Fixtures vs builders

Fixtures (canned objects) get stale fast. Test data builders scale better:

```python
def a_user(**overrides):
    base = {"email": "u@example.com", "tier": "free", "verified_at": None}
    return {**base, **overrides}

def test_x(db_session):
    db_session.add(User(**a_user(tier="paid")))
```

Each test states only what it cares about. The builder owns the "valid by default" shape. When the schema changes, you change the builder, not 80 tests.

### Determinism

Three sources of nondeterminism cause 90% of flakiness:

- **Time.** Use a freezer (`time-machine` for new Python code, `freezegun` if it's already in the project; `vi.useFakeTimers` in JS) or pass a clock. Never `datetime.now()` inside production code that's being tested for time-dependent behavior. `time-machine` is faster and patches at the C level, which matters for large suites.
- **Random / IDs.** Inject the RNG / ID generator. UUIDv4 in production tested against `uuid == "abc-123"` in the test? Inject.
- **Concurrency / ordering.** Don't assert on the order of unordered things. Set equality, not list equality. For events, assert "X happened, then Y happened," not "the third event was Y."

### External dependencies you can't run locally

Some things are too painful to mock and not worth the fidelity loss: a real S3 (use `moto` or `localstack`), a real Redis (use a container, it's tiny), a real Elasticsearch (container). The rule of thumb: if a high-fidelity local stand-in exists, use it. If only the real service exists (Stripe, Twilio, SendGrid, OpenAI), record + replay or hand-stub.

### Recording and replaying

For high-fidelity third-party tests, record real HTTP traffic on the first run, then replay it forever. Useful when:

- The API is complex and writing a stub would diverge from reality
- You want a regression test on the actual response shape
- You're testing client-library behavior under real responses

Tooling:

- **Python:** `vcr.py` is the standard. `pytest-recording` wraps it with a `@pytest.mark.vcr` marker.
- **Node:** prefer `nock` with its recorder (`nock.recorder.rec({ output_objects: true })` to capture, then commit the fixtures and replay with `nock(...)` calls). MSW v2 supports persisted handlers via the recorder pattern as well. `polly.js` is no longer maintained — avoid for new work.

Sanitize secrets on record (`filter_headers=["authorization"]` in vcr.py, request rewriters in nock) — cassettes get committed and end up on the internet otherwise.

## Running and debugging

### Local: target narrowly first

When iterating, run the smallest test you can:

```bash
pytest tests/integration/test_orders.py::test_create_order_persists -x -v
```

```bash
npx vitest run tests/integration/orders.test.ts -t "creates order"
```

`-x` (pytest) / Vitest's `--bail=1` stop on the first failure. Don't watch CI logs scroll for ten minutes when one assertion will tell you what's broken.

### Reading failures

A typical integration test failure has three suspects in this order: (1) the test assumption (you stubbed the wrong URL), (2) the test data (a fixture from another test leaked), (3) the production code. Triage in that order — production code being broken in a way that only the integration test catches is the rarest case, though it's the one you most want to find.

For a test that fails only in CI but passes locally, the suspects are:

- **Time / TZ.** CI is UTC; your laptop isn't.
- **Concurrency.** CI runs in parallel by default; your laptop runs serially.
- **Data leaks.** A test that depends on order works at home, fails in CI.
- **Network timing.** CI is slower; a `sleep(0.1)` becomes a race.
- **Resource limits.** CI has 2 CPUs and 4GB; your laptop has 16 and 64.

### Flaky tests

A flaky test is a bug, almost always in the test, sometimes in the system. Don't `@retry` it; that hides the bug and makes the next bug invisible. The fix is one of:

- Replace `sleep` with a polled predicate.
- Inject the clock / RNG.
- Isolate test data (transaction rollback or fresh DB).
- Sort before asserting on collections.

If you genuinely can't make it deterministic, quarantine it (mark `@flaky` / `.skip` with a TODO ticket) rather than letting it erode trust in the suite. A green CI that's actually red 10% of the time is worse than a yellow CI.

### Parallelism and CI

Most integration suites can run tests in parallel within a process — pytest-xdist (`-n auto`), Vitest's default workers — provided each test is isolated. The trap is shared state: a global counter, a singleton client, a shared temp dir. Audit that first when adding parallelism.

For CI, prefer **one container per worker** over **all workers sharing one container**. The startup cost is paid once per worker, you eliminate cross-worker contention, and parallelism scales linearly.

Note: vanilla pytest has no built-in shard flag. Use the `pytest-split` plugin (deterministic split by historical durations) or `pytest-shard` (round-robin by collection order):

```yaml
# .github/workflows/ci.yml (sketch — pytest-split)
strategy:
  matrix:
    group: [1, 2, 3, 4]
steps:
  - run: pip install pytest-split
  - run: pytest --splits 4 --group ${{ matrix.group }} tests/integration
```

For Vitest, use `--shard=N/M` (built in): `vitest run --shard=${{ matrix.group }}/4`.

### Slow tests

If the integration suite takes 20+ minutes, reach for these in order:

1. **Profile.** `pytest --durations=10` / `vitest --reporter=verbose`. The Pareto rule applies: ten tests will be 50% of the time.
2. **Reuse containers across tests.** Session-scoped fixtures over function-scoped, *with* per-test isolation inside.
3. **Parallelize.** xdist / matrix shards.
4. **Move some tests down the pyramid.** If a test could be a fast unit test with a fake repo and one less integration test wouldn't change your bug-catch rate, demote it.
5. **Consider whether all of CI needs the full suite on every push.** Smoke set on every push, full suite on merge to main.

## Common pitfalls

- **Treating integration tests as unit tests.** Mocking the DB inside an "integration test" is a smell — you've written a slow unit test. Mock the things you don't own; integrate with the things you do.
- **Sleep instead of poll.** Every `sleep(N)` is a future flake. Replace with a deadline-bounded predicate.
- **Asserting only the response.** APIs lie. Always assert what's in the DB / queue / log too.
- **Shared mutable state across tests.** A class-level `users = []`, a module-level cache, a singleton config. Tests pass alone, fail together.
- **Tests that depend on running order.** If `test_b` only passes after `test_a`, you have one test split into two halves.
- **Hardcoded ports and dirs.** Use ephemeral ports (bind to `:0`), `tmp_path` / `os.tmpdir()`. Two CI jobs on the same runner will collide otherwise.
- **Forgotten cleanup on failure.** Use try/finally, fixtures, or context managers. A test that doesn't clean up on assertion failure pollutes the next test.
- **Skipping cleanup "because rollback handles it."** Rollback handles the DB. Files, S3 objects, queue messages, in-memory caches need explicit teardown.
- **Letting unhandled outbound HTTP through.** `onUnhandledRequest: "error"`, `responses.activate(assert_all_requests_are_fired=True)`. A test that silently hits the internet will silently hit it in production too.
- **Fixtures that grow new fields and break 50 tests.** Use builders.
- **Migrations applied differently in test vs prod.** Run the same migration tooling in tests as in prod. `Base.metadata.create_all()` in tests + Alembic in prod is a recipe for "it works in tests, fails in prod."
- **Not running migrations forward AND back in CI.** Down migrations break in production at the worst time. Test them in CI on a representative dataset.

## When integration tests are the wrong tool

Don't reach for an integration test for:

- **Pure logic** — wasteful. Unit test it.
- **UI behavior** — that's an E2E job. Playwright / Cypress / Detox.
- **Performance / load** — integration tests use containers; performance tests need real-shape infra. Use k6 / Locust / Gatling.
- **Contract testing between services you both own** — Pact + consumer-driven contract tests scale better than spinning up the producer.
- **Smoke testing prod** — synthetic monitors (Datadog, Pingdom, custom) belong in your monitoring stack, not your test suite.

The integration test sweet spot is "this code, talking to its real persistent dependencies, in the shape you'd see in prod, asserting on observable outcomes." Stay in that lane and the suite stays useful.

## See also

- [postgresql](../../data/postgresql/SKILL.md) — Postgres-specific tuning, EXPLAIN, transaction isolation behavior. When a test exposes a query plan or lock-contention bug, this is the next stop.
- [database-design](../../data/database-design/SKILL.md) — when the right fix is a schema/index change rather than a test change.
- [fastapi](../../backend/fastapi/SKILL.md) / [django](../../backend/django/SKILL.md) / [nodejs-backend](../../backend/nodejs-backend/SKILL.md) / [go-backend](../../backend/go-backend/SKILL.md) — framework-specific test wiring (DI, lifespan/app factory, transactional test cases).
- [devops-cicd](../../devops/devops-cicd/SKILL.md) — sharding strategy, matrix builds, caching test images, required vs informational checks.
- [resilience-patterns](../../reliability/resilience-patterns/SKILL.md) — testing retries, timeouts, circuit breakers, idempotency keys deserves its own discipline.
- [observability](../../reliability/observability/SKILL.md) — asserting on emitted spans/metrics/logs as part of an integration test.
