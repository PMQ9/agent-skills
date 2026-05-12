---
name: backend-development
description: Use this skill for any backend service work — application architecture, data access, caching, async processing, background jobs, transactions, configuration, secrets, structured logging, retries, idempotency, feature flags, or testing strategy. Trigger when implementing a new service, refactoring an existing one, debugging concurrency or consistency issues, choosing between sync and async, designing a domain model, or reviewing service code. This skill complements api-design (which focuses on the HTTP surface) by covering everything below the controller layer.
---

# Backend Development

A backend service is a long-running program that holds state on behalf of users. Most of the bugs that matter come from three places: shared mutable state, distributed-systems failure modes you didn't plan for, and data access that worked fine on a developer laptop but melts under load. This skill is about avoiding those.

## Before writing code: read what's been decided, and cite by ID

For non-trivial features, before opening an editor:

1. Read **`docs/requirements/<slug>/`** — start with `_overview.md` for narrative; then read each category file relevant to your implementation (`functional.md`, `security.md`, `performance.md`, etc.). Inherited policies in `_policies/` are mandatory reading. Implementing against a verbal description means re-deriving requirements in code, which means the requirements drift from intent without anyone noticing.
2. Read **`docs/test-plans/<slug>.md`** — what cases must the implementation handle? The test plan is the inverted shape of the implementation: every case it lists is a code path you need.
3. Read the relevant **ADRs in `docs/adr/`** — what constraints have already been chosen? A new feature implemented with a different framework, ORM, or queue than the existing house style is a surprise nobody wanted.

**Gate check before non-trivial code:**

- The spec directory exists and the typed requirements you're implementing (FN-NNN, SEC-NNN, PERF-NNN, ...) are `Accepted`.
- The test plan covers those requirement IDs in its coverage matrix.
- ADRs governing the implementation choices (framework, datastore, queue, auth approach) exist or are obvious from the existing codebase.
- Inherited `_policies/` files exist and have their own tests.

If any of those are missing for a non-trivial change, surface it before coding — back up to the relevant skill (requirements-analyst, test-planning, system-architecture). Implementing against guesses produces code whose `why` lives only in someone's head.

**Citation in code.** When the trace would otherwise be invisible to a future reader, cite by typed ID:

- Commit messages and PR descriptions name the requirements implemented (`Implements bulk-csv-import#FN-004, FN-005, SEC-002`). Lets `git log --grep` answer "what changed because of FN-004?"
- Comments on non-obvious code cite the requirement or ADR that explains it (`# PERF-002 — P95 < 500ms; this is why we batch-prefetch`).
- A surprising design choice (an unusual data structure, a hand-rolled algorithm, a deviation from house style) names the ADR (`# Per ADR-0007 — using Postgres JSONB rather than a separate document store`).

Don't pepper every line. Cite where the *why* would be lost otherwise.

For one-line fixes and small refactors, skip the docs lookup — the cost of reading is higher than the cost of being wrong. For new endpoints, new background jobs, schema changes, or anything touching money/auth/PII, read first.

## Architecture: keep layers honest

A typical service has four layers, even when they're not named that way:

1. **Transport** — HTTP/gRPC/queue handlers. Parse, validate, authenticate. Owns nothing.
2. **Application / use case** — orchestrates a single user-meaningful operation. Knows about transactions, retries, side effects.
3. **Domain** — the business rules. Pure where possible. No framework, no I/O.
4. **Infrastructure** — databases, queues, external APIs, file systems. Implementations of interfaces the domain layer declares.

The dependency direction is one-way: transport → application → domain ← infrastructure. The domain doesn't import the database client. This isn't dogma; it's what makes the code testable and what keeps you sane when you swap Postgres for something else, or add a second consumer (a CLI, a worker) that needs the same logic.

You don't need DDD, hexagonal architecture, or clean architecture diagrams to do this. You need to notice when business logic ends up inside an HTTP handler or an ORM model and move it.

## Domain modeling

Make illegal states unrepresentable. If an `Order` can only be `paid` after it is `submitted`, encode that in the type/state machine, not in 14 scattered `if` statements.

Use value objects for things that have invariants (`Money`, `EmailAddress`, `OrderId`). Validate at the boundary; trust your own types inside the domain.

Don't model anemic objects (data with no behavior) and a separate "service" that does everything. The data and the rules that govern it belong together.

## Data access

### ORMs are fine, but…

ORMs are great for CRUD and terrible for everything else. The first time you find yourself writing N+1 queries to please the ORM, drop into raw SQL. Most modern stacks (sqlc, jOOQ, Diesel, Slonik, Prisma raw) make this easy.

A good rule: **simple writes through the ORM, complex reads through SQL.** Reads are where performance lives.

### N+1 is the most common backend bug

Loading a list of orders, then looping and loading each order's customer, is N+1. Watch for it whenever a loop touches a relation. Fixes:

- Eager loading / `JOIN` / `IN (...)` batch
- DataLoader-style request-scoped batching
- A read-side query that returns the joined shape directly

Detect it: log queries per request in dev. If you see >5 queries for one HTTP request, look harder.

### Connection pooling

Every service that talks to a database needs a connection pool sized to the database's capacity, not the service's request load. Postgres tops out around a few hundred connections; if you have 50 service instances each opening 50 connections, you've already exhausted the database.

Use a pooler (PgBouncer, RDS Proxy) in front. Inside the service, set max pool size based on `(db_max_connections / number_of_instances) * safety_factor`. Always set a connection timeout and an idle timeout.

### Migrations

- Migrations are append-only. You don't edit a migration that's been deployed.
- Every migration is **forward-compatible with the running code** and **backward-compatible with the previous code**, because at deploy time both versions run for a window. Practical implications:
  - Add column nullable first, backfill, then add NOT NULL in a later deploy.
  - Don't drop a column in the same deploy that stops writing to it. Stop writing → deploy → drop in next migration.
  - Renames are two-step: add new, dual-write, switch reads, drop old.
- Long-running data backfills don't belong in migrations. Run them as one-off jobs.

### Transactions

A transaction wraps work that must succeed or fail together. Keep them short — long transactions hold locks. Don't make HTTP calls inside a transaction. Don't `sleep` inside a transaction.

Pick an isolation level deliberately. Most services run at READ COMMITTED (Postgres default) and that's fine for most things, but anything involving "read, decide, write" needs either:

- **SELECT ... FOR UPDATE** (row-level lock)
- **SERIALIZABLE** isolation (and handle serialization failures with retry)
- **Optimistic concurrency** (version column; reject if it changed)

Optimistic is usually cleanest for user-driven updates: include a `version` or `updated_at` in the request, `UPDATE ... WHERE version = ?`, return 409 on zero rows.

### Identity

Use UUIDs (v7 if you can — they're time-ordered and index-friendly) or ULIDs for primary keys exposed externally. Auto-increment integers leak business volume and enable enumeration.

If you keep an internal integer PK *and* an external UUID, that's fine — many systems do — but the UUID is what crosses the network.

## Caching

Caching is a correctness problem disguised as a performance feature. A wrong cached value is worse than a slow uncached value. Apply this order:

1. **Don't cache.** Tune the query first.
2. **Cache at the edge** (CDN, Cloudflare) for public, immutable, or near-immutable responses. Use proper `Cache-Control` and `ETag`.
3. **In-process cache** for read-mostly reference data (feature flags, config). Cheap, fast, but stale on each instance independently.
4. **Distributed cache** (Redis, Memcached) for shared hot data. Now you have an invalidation problem.

Patterns:

- **Cache-aside / lazy load**: read cache → miss → read DB → write cache. Simple and fine for most cases.
- **Write-through**: write to cache and DB together. Reduces miss rate but adds write latency.
- **Write-behind**: write to cache, async to DB. Risky — cache becomes the source of truth between writes.

Always set a TTL. "Cache forever and invalidate on write" sounds clean but goes wrong every time something else writes to the database (admin tools, migrations, replicas, other services).

Watch for **stampedes**: when a hot key expires and 1000 requests all miss simultaneously, they all hit the DB. Mitigations: lock around the regeneration, jittered TTLs, "stale-while-revalidate" semantics, or pre-warming.

## Async, queues, and background jobs

Move work out of the request path when:
- It takes >100ms and the user doesn't need to wait for the result.
- It can fail and be safely retried.
- It calls a flaky external API.
- It happens fan-out (one event, many consumers).

Use a real queue (SQS, RabbitMQ, NATS, Kafka, Redis Streams). Don't fake it with cron + database table polling unless you really know why and at what scale that breaks (hint: lock contention, tail latency, missed jobs on instance death).

Every job needs to be:

- **Idempotent.** It will run twice. At-least-once is the default delivery semantics of every queue worth using. Achieve idempotency with deterministic IDs, dedupe tables, or designing operations as upserts.
- **Bounded in time.** Set a visibility timeout that exceeds your worst-case runtime. Set a hard timeout in the worker.
- **Retryable with backoff.** Exponential backoff with jitter. Cap retries. Anything that exhausts retries goes to a dead-letter queue, which you actually monitor.
- **Observable.** Log job ID, attempt count, duration, and outcome.

## Retries, timeouts, and circuit breakers

Every outbound call needs:

- A **timeout** — both connect and read. No exceptions. Default to something tight (e.g., 1–3 seconds) and tune up if needed.
- **Retries with exponential backoff and jitter** — only on idempotent operations or with idempotency keys. Don't retry 4xx; do retry 5xx, timeouts, connection failures.
- A **budget** — total time across all retries should be bounded.
- A **circuit breaker** for downstreams that can fail catastrophically. After N failures in M seconds, fail fast for a cooldown rather than piling up. Especially important when downstream pressure causes upstream queues to fill.

The retry-storm pattern is real: downstream slows down → upstream retries → downstream gets more load → fully tips over. Backoff and jitter and circuit breakers exist to prevent this.

## Idempotency throughout

Idempotency isn't just an HTTP header. Inside the service, ensure:

- Database operations use `INSERT ... ON CONFLICT` or upsert semantics where re-running is plausible.
- Outbound effects (email send, payment) are guarded by an idempotency key persisted before the call.
- "Process this event" handlers are keyed by event ID so re-delivery is a no-op.

The cleanest pattern: the **outbox**. Inside the database transaction that does the work, insert a row into an `outbox` table describing the event to publish. A separate process reads the outbox and publishes. This gives you exactly-once-effective delivery: the publish can be retried; the consumer dedupes on event ID.

## Configuration and secrets

- **Config from environment.** 12-factor. No config in code, no environment-conditionals (`if env == "prod"`) sprinkled around.
- **Validate config at startup.** Crash on missing/invalid config, before serving traffic.
- **Secrets never in env files committed to source.** Use a secret manager (AWS Secrets Manager, Azure Key Vault, HashiCorp Vault, SOPS-encrypted files for small teams).
- **Rotate secrets.** Build the rotation in from day one — your service should pick up rotated secrets without restarts where possible.
- **Different secrets per environment.** No prod secrets on a dev laptop, ever.

## Logging, metrics, traces

These are three different things. Use all three:

- **Logs** — discrete events with structured fields. JSON, not free text. Always include: timestamp, level, service name, version, request ID / trace ID, user ID (when known). Never log secrets, full credit cards, full auth tokens, or PII you shouldn't have. Sample debug logs in production.
- **Metrics** — counters, gauges, histograms. Low cardinality (don't tag by user ID; do tag by endpoint). Drives dashboards and alerts.
- **Traces** — per-request spans showing what called what and how long. OpenTelemetry is the standard; use it.

Propagate trace context (`traceparent` header) across every hop, including queues. A trace that ends at the queue boundary is half-blind.

## Health checks

Two endpoints, both unauthenticated:

- `/healthz` — am I alive? Return 200 if the process is up. No DB checks.
- `/readyz` — am I ready to serve? Return 200 only if dependencies are reachable. The load balancer uses this to decide whether to send traffic.

Don't conflate these. A failing DB shouldn't make the load balancer kill the pod (it might recover); it should make readiness fail and stop sending new traffic.

## Graceful shutdown

On SIGTERM:

1. Mark `/readyz` as failing.
2. Wait long enough for the load balancer to notice (usually 5–10s).
3. Stop accepting new requests; finish in-flight ones.
4. Drain background workers (stop dequeuing, finish current job).
5. Close DB connections.
6. Exit.

Without this, every deploy will throw a handful of 502s. Most frameworks support it but it's often off by default.

## Testing strategy

The test pyramid still applies:

- **Unit tests** — pure functions, domain logic. Fast, lots of them.
- **Integration tests** — service + real database (in a container) + real queue. Slower, fewer, much higher confidence than mocks-everywhere.
- **Contract tests** — for service boundaries you don't control end-to-end (Pact-style). Producer publishes contract; consumer verifies.
- **End-to-end** — a few smoke tests against a deployed environment. Don't try to cover everything here; they're slow and flaky.

Avoid mocking the database. Use a real Postgres in a container with `testcontainers` or similar. Mocked SQL hides bugs.

Avoid mocking time. Inject a clock interface and substitute it.

Avoid testing implementation details. Test the externally visible behavior. Refactoring shouldn't break tests.

## Feature flags

Every behavior change worth deploying is worth flagging. The benefits:

- Decouple deploy from release.
- Roll out by percentage / cohort / user.
- Kill switch when something burns.

Use a real feature flag system (LaunchDarkly, Unleash, ConfigCat, OpenFeature with your own backend). Don't just use environment variables — they require a deploy to flip.

Clean up flags. A long-lived flag rots into permanent dead code with two paths nobody fully tests anymore.

## Anti-patterns

- Catching `Exception` and logging "something went wrong." Either handle it specifically or let it propagate.
- Doing I/O in constructors.
- Singletons holding mutable state across requests.
- Using HTTP status codes as control flow inside the same service. Throw a typed domain error and let the transport layer translate.
- "Just one more `if env == 'prod'`" — that's how you get prod-only bugs nobody can reproduce.
- Logging the request body. You will leak PII. Log the IDs.
- Sleep-based test waits. Use polling with timeouts.
- Sharing mutable objects across goroutines / threads / async tasks without synchronization.
- "We'll add observability later." You won't, and the first incident will cost a day.
- Optimistic deletes without soft-delete or audit trail in any system handling money or compliance data.
