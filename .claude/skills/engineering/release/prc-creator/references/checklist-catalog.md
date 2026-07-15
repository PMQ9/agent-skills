# PRC Checklist Catalog

The item bank for the nine readiness dimensions. Each item is written as: **the check** — *why it matters* — **how to verify it** (the signal to look for in assessment mode). Not every item applies to every product; use `product-profiles.md` to prune and to mark items N/A with a reason.

Treat these as the "given a product, when we inspect it, then we expect X" statements. In template mode they become the unchecked boxes; in assessment mode they become the graded findings.

## Contents

1. [Architecture & Design](#1-architecture--design)
2. [Reliability & Resilience](#2-reliability--resilience)
3. [Scalability & Performance](#3-scalability--performance)
4. [Security](#4-security)
5. [Data & Privacy](#5-data--privacy)
6. [Testing & Quality](#6-testing--quality)
7. [Observability & Operability](#7-observability--operability)
8. [Release & Deployment](#8-release--deployment)
9. [Documentation & Ownership](#9-documentation--ownership)

---

## 1. Architecture & Design

- **Service boundaries follow data ownership — one writer per row, no database shared between services.** *A shared database collapses "services" back into one unit that must deploy and fail together; it's the coupling that quietly kills a microservices story.* Check: do two services write the same tables? Are ORM models imported across service boundaries?
- **No distributed monolith or long synchronous call chains (A→B→C→D).** *Every extra synchronous hop multiplies failure probability and tail latency.* Check: trace a representative request; count cross-service hops on the hot path.
- **Cross-service workflows have a deliberately chosen coordination pattern.** *Communication (sync/async) × consistency (atomic/eventual) × coordination (orchestrated/choreographed) is chosen by accident otherwise — and async+atomic+choreographed ("Horror Story") takes weeks to debug.* Check: is there an orchestrator per workflow? Are compensating actions defined for partial failure?
- **No cross-service distributed transactions where atomicity is required.** *If two operations must be atomic to the business, they belong in one service; a saga bolted onto a bad boundary is a self-inflicted wound.* Check: any two-phase-commit or "we'll make it consistent later" across a boundary that the business treats as atomic.
- **Dependency direction is inward — the domain doesn't import the ORM, HTTP framework, or logging library** (for non-trivial domains). *Keeps business logic testable without infrastructure and portable across it.* Check: imports in domain modules; are domain tests able to run with no DB?
- **No god service/module; modules named for the domain, not the layer.** *"CoreService," "Manager," "utils," "common" are where responsibility goes to die.* Check: module names and their fan-in.
- **Load-bearing decisions are recorded as ADRs with alternatives and consequences.** *A decision you can't defend in six months gets reversed by the next engineer; the "alternatives considered" is what prevents re-litigation.* Check: `docs/adr/`; do ADRs list what was given up, not just what was chosen?
- **Architectural invariants are enforced by fitness functions, not hope.** *Layering and boundaries decay silently without an automated check.* Check: import-linter/dependency-cruiser/ArchUnit in CI, performance budgets, consumer-driven contract tests.
- **Topology is right-sized for the team and the measured load.** *Premature microservices/Kubernetes/NoSQL/caching import all the cost for none of the benefit.* Check: team size vs. number of services; is there a measured reason for each non-boring technology?
- **Commodities are bought/integrated, not rebuilt.** *Identity, auth, payments, email deliverability, search relevance are "looks easy, isn't."* Check: any hand-rolled auth/identity/billing.

## 2. Reliability & Resilience

- **Availability target is stated as a number (SLO) with an error budget.** *"Highly available" is unbudgeted; 99.9% vs 99.99% is a 10x cost and architecture difference.* Check: is there a written SLO?
- **Single points of failure are identified and addressed to the level the SLO requires.** *An SLO you can't meet because of one un-redundant component is fiction.* Check: single DB with no replica/failover, single AZ, one-of-everything.
- **Every outbound call has a timeout; retries use backoff + jitter.** *A missing timeout turns one slow dependency into a full outage; naive retries cause storms.* Check: HTTP/DB/queue client configs.
- **Writes that can be retried are idempotent.** *Networks retry, users double-click, queues deliver twice — non-idempotent writes double-charge and duplicate.* Check: idempotency keys, upserts, dedupe on event id.
- **Graceful degradation for downstream failure; fail-closed for security, fail-open where safe.** *A dependency being down should degrade a feature, not the whole product.* Check: fallback paths, circuit breakers on flaky dependencies.
- **A rollback plan and/or kill switch exists for the launch.** *If you can't turn it off fast, every bug is a crisis.* Check: feature flags on risky features, documented rollback.
- **RTO and RPO are defined and backups are restore-tested — not just taken.** *An untested backup is a hope; teams discover backups don't restore during the incident.* Check: last restore drill; point-in-time recovery if the RPO needs it.
- **Liveness and readiness health checks exist and are wired to the orchestrator/LB.** *Without them, traffic routes to dead or not-yet-ready instances.* Check: `/healthz`, `/readyz` (or platform equivalent).
- **Blast radius is contained — per-tenant limits, bulkheads, noisy-neighbor protection.** *One tenant's spike shouldn't degrade everyone.* Check: per-tenant rate limits/quotas at the points that matter.
- **Async work has dead-letter handling and a poison-message strategy.** *A single bad message shouldn't wedge a queue forever.* Check: DLQ config, max-retry handling.

## 3. Scalability & Performance

- **Latency budget (p50/p95/p99) is defined and measured against a number.** *"Fast" is meaningless; p99 is where users feel pain, especially under fan-out.* Check: is there a measured latency baseline vs. a target?
- **Throughput target (RPS/ingest rate) is defined and load-tested at that target.** *Capacity assumed but never tested fails at the worst time — launch.* Check: any load test artifact at expected peak.
- **Fan-out tail latency is accounted for.** *N independent calls at p99 X aggregate to far worse than X; by N=100 the effective p99 approaches the call's p99.99.* Check: hottest endpoint's downstream call count.
- **DB connection pool is sized to the database's capacity; a pooler sits in front of serverless.** *Serverless functions exhaust DB connections instantly without PgBouncer/RDS Proxy.* Check: pool size vs. DB max connections; pooler presence.
- **Caching is added only where measured, with an invalidation strategy.** *Premature caching adds an invalidation bug you didn't need.* Check: is each cache justified by a measurement? How is it invalidated?
- **Hot paths are free of N+1 queries and missing indexes.** *The most common real-world performance cliff.* Check: query logs/EXPLAIN on the busiest endpoints.
- **Autoscaling and resource limits are configured.** *No limits ⇒ one runaway process starves the node; no autoscaling ⇒ manual firefighting under load.* Check: requests/limits, HPA or platform autoscaling.
- **List endpoints paginate and payloads are bounded.** *Unbounded lists and payloads are latency and memory time-bombs as data grows.* Check: pagination on every list endpoint; max payload/body size.
- **Cost at target scale has been sanity-checked.** *A "scalable" design that's unaffordable at target load isn't ready.* Check: rough cost estimate at projected load.

## 4. Security

Report security findings attacker-first: what an attacker does, then the fix. Calibrate the bar to the risk tier.

- **Assets, adversaries, and trust boundaries are mapped; the design has been threat-modeled (STRIDE).** *You can't evaluate a control without knowing what it defends and against whom.* Check: any threat model doc; can the team name the top three abuse cases?
- **All untrusted input is validated/parsed at the trust boundary.** *Untrusted input includes bodies, headers, query params, uploads, webhooks, third-party API responses, and LLM-fed content.* Check: schema validation at the edge (`Schema.parse(...)`, not `as Type`).
- **Authentication is not hand-rolled; passwords hashed with argon2/bcrypt/scrypt; MFA where the tier needs it.** *Hand-rolled auth and hashing fail catastrophically and silently.* Check: framework/provider auth; hashing algorithm.
- **Authorization is row-level, not just route-level — every query is scoped to the principal/tenant.** *Guarding the route but running `SELECT * FROM things` leaks every user's data the moment a second user exists; it's invisible to happy-path testing.* Check: list/read/write queries for a `WHERE user_id/tenant_id` scope.
- **Browser session credentials live in `HttpOnly`+`Secure`+`SameSite` cookies; no JWT in `localStorage`.** *A token readable by JS is one XSS from account takeover.* Check: where the web app stores its session token.
- **Secrets are in a real secret store, not committed, and differ per environment.** *A committed key is a breach waiting for a repo leak.* Check: grep the repo/history for keys/tokens; is `.env` committed? Rotation policy?
- **Dependencies are scanned for known CVEs; supply chain is pinned.** *Unpatched dependencies are the Equifax class of breach.* Check: SCA/Dependabot; lockfile committed; versions pinned (no `LATEST`).
- **AI-generated code has been security-reviewed for insecure defaults and hallucinated packages.** *AI-assisted code ships materially more vulnerabilities and can import non-existent ("slopsquatted") packages.* Check: were AI-written diffs reviewed? Do all imported packages exist and are they the intended ones?
- **Injection classes are closed.** *SQLi, command injection, SSRF, XSS, deserialization.* Check: parameterized queries, output encoding, no shell string concatenation, SSRF egress controls.
- **Transport is encrypted (TLS) and sensitive data is encrypted at rest.** Check: TLS enforced/HSTS; at-rest encryption on stores holding sensitive data.
- **State-changing requests are protected against CSRF / cross-origin abuse; CORS is locked down.** Check: CSRF tokens or same-site strategy; CORS allowlist, not `*`.
- **Abuse-prone endpoints are rate-limited.** *Login, signup, password reset, search, and any expensive operation.* Check: rate limiting presence.
- **File uploads are validated (type, size) and stored where they can't execute.** Check: content-type/size checks; uploads not served from an executable path.
- **Privileged and sensitive actions are audit-logged (who, what, when).** *Without audit, you can't do incident forensics or compliance.* Check: audit trail on admin/sensitive operations.
- **IAM, service accounts, and DB roles follow least privilege.** Check: are prod credentials scoped, or is everything an admin/root?

## 5. Data & Privacy

- **The core data shape is a single contract that flows through every layer unchanged in meaning; parse at boundaries.** *The classic seam bug is a type/shape/unit that drifted between layers.* Check: is the shape generated from one source (schema → types), or hand-maintained in several places? Is the API response parsed or `as`-cast?
- **Lossy conversions at the seams are handled deliberately.** *Dates (store UTC, send ISO-8601, format in UI), money (integer minor units or decimal, never float), big integers (JSON loses precision past 2^53 — send as strings), enum casing, null vs. undefined vs. absent.* Check: how money and dates cross the wire.
- **Migrations are backward-compatible (expand/contract): add nullable → backfill → enforce; never rename-in-place.** *During a deploy the old and new code run simultaneously; an in-place rename breaks the old code mid-rollout.* Check: migration files for destructive in-place changes tied to a single deploy.
- **Backups are automated and a restore has actually been performed.** Check: backup schedule + a dated restore drill.
- **Data integrity is enforced in the database (foreign keys, constraints), not only in app code.** *App-level-only integrity fails the moment any code path forgets.* Check: FK/constraint presence on critical relations.
- **There is exactly one system of record per concept.** *Two authoritative sources make reconciliation a permanent project.* Check: is customer/billing/user data authoritative in one place?
- **The compliance regime is identified and its data rules are met.** *GDPR/HIPAA/FERPA/PCI/SOC 2 shape residency, retention, deletion/right-to-erasure, consent, and audit.* Check: which regime applies, and are retention/deletion implemented?
- **PII is inventoried, minimized, access-controlled, and encrypted/tokenized.** Check: what PII is collected, who can read it, is collection minimized?
- **Sensitive data isn't leaking into logs, error trackers, or analytics.** Check: log/error payloads for tokens, PII, secrets.

## 6. Testing & Quality

- **Test coverage traces to acceptance criteria / requirements — every requirement has at least one test.** *Line coverage doesn't know what matters; requirement coverage does.* Check: is there a test plan keyed to requirements, or just a coverage %?
- **The pyramid is right: many unit tests on domain logic, fewer integration tests against a real DB, a few e2e on critical paths.** *Unit tests that mock the database don't prove the SQL; e2e everything is slow and flaky.* Check: integration tests use a real datastore (containerized), not mocks; e2e count is small and focused on signup/login/core action.
- **The seams are tested hardest — frontend↔backend contract, auth across layers, backward-compatible migration.** *Seams are where cross-layer bugs live and where breadth is thinnest.* Check: is there a test that would catch a contract drift or a missing tenant filter?
- **Negative and edge cases are covered from a checklist, not from inspiration.** *Inputs (empty/max/unicode/injection chars), time (DST/leap/midnight), auth (expired/cross-tenant/privilege), concurrency (double-submit/optimistic lock), downstream failure (timeout/5xx/malformed), data state (missing/soft-deleted/large aggregate), locale.* Check: are there more negative tests than happy-path ones?
- **Known coverage gaps are stated explicitly.** *Honesty about what isn't tested beats a green bar that hides it.* Check: is there a "known gaps" note, or silence?
- **CI runs the tests and blocks merge on failure; flaky tests are quarantined, not ignored.** Check: branch protection / required checks.
- **Producer/consumer boundaries have contract tests** (where the team doesn't own both sides). Check: Pact-style or schema contract tests on external boundaries.
- **There's a load test if there's a perf SLO, and a security scan appropriate to the tier.** Check: load test at target; SAST/DAST/dependency scan.
- **Rollback and the migration have been rehearsed in staging.** *A rollback first attempted during an incident often fails.* Check: staging drill evidence.

## 7. Observability & Operability

- **Logs are structured with consistent keys and carry no secrets/PII.** *Unstructured logs can't be queried at 3am; leaky logs are a breach.* Check: structured logging library; a correlation/request id.
- **Metrics cover rate, errors, and duration (and saturation for resources).** *The golden signals are how you see trouble before users report it.* Check: RED/USE metrics on key services.
- **Distributed traces exist for multi-service flows.** *Without traces, a microservices outage is undebuggable.* Check: tracing (OTel or platform) with propagated context.
- **An error tracker is wired up with sourcemaps/symbolication.** Check: Sentry-or-equivalent; are stack traces readable?
- **Alerts are tied to SLOs / symptoms, are actionable, and don't cry wolf.** *CPU-only alerts miss user pain; noisy alerts get muted.* Check: do alerts map to user-facing symptoms and page a human who can act?
- **There are dashboards for the golden signals, and the "3am test" passes.** *Could an on-call engineer diagnose a failure with what's instrumented?* Check: dashboards exist and are current.
- **On-call rotation and escalation are defined; each component and integration has a named owner who gets paged.** *"Both teams page each other" is not an ownership model.* Check: rotation + escalation policy.
- **Runbooks exist for the common failures and for each alert.** Check: alert → runbook link.

## 8. Release & Deployment

- **A CI/CD pipeline builds, tests, and deploys; builds are reproducible and the lockfile is committed.** *Manual deploys are unrepeatable and error-prone.* Check: pipeline config; pinned deps.
- **Migrations run as a gated, ordered deploy step.** Check: are migrations part of the deploy, not run by hand?
- **A rollout strategy is chosen (rolling/blue-green/canary) with health gating; the API and frontend stay backward-compatible during rollout.** *Old and new versions of both run simultaneously during a deploy.* Check: rollout config; does the new frontend require a not-yet-deployed API field?
- **Rollback is a single action and has been tested.** Check: documented + rehearsed rollback.
- **Config and secrets are per-environment and never in code or CI logs.** Check: env-scoped secret management; no secrets echoed in pipeline output.
- **Infrastructure is defined as code (reviewable, reproducible), not click-ops.** Check: Terraform/CloudFormation/Bicep/Pulumi presence for prod infra.
- **The database is managed with automated backups** (small teams shouldn't self-host prod Postgres). Check: managed DB or a very good reason not.
- **Dev/staging/prod have parity where it matters — same database engine, similar config.** *SQLite-in-dev/Postgres-in-prod hides bugs until production.* Check: engine parity.
- **The whole stack comes up locally with one command and seeded data.** *Debugging blind and painful onboarding otherwise.* Check: compose/Procfile/Tilt + seed script.
- **Container images are minimal, scanned, and run as non-root** (image signing/attestation for higher tiers). Check: base image, user, scan step.

## 9. Documentation & Ownership

- **A current architecture overview exists at the right altitude (a C4-ish context/container diagram).** *Onboarding and incident response both start here.* Check: is there a diagram, and is it current?
- **The API contract is documented, typed, versioned, and generated — not tribal knowledge.** Check: OpenAPI/typed client; is it generated from one source?
- **Non-obvious decisions have ADRs.** (See Architecture.) Check: `docs/adr/`.
- **Runbooks and on-call docs exist and are findable.** Check: linked from alerts/README.
- **Every component and integration point has a clear owner.** *Unowned code becomes a junk drawer; unowned integrations page nobody.* Check: CODEOWNERS or an ownership doc.
- **A new engineer can run and understand the system from the docs.** *The local-run + overview + runbooks together are the onboarding path.* Check: is the README enough to get running?
- **Dependencies and their licenses are inventoried** (matters more at higher tiers / for distribution). Check: SBOM or dependency/license list.
- **There's a launch comms/support plan and published SLA/SLO for stakeholders.** Check: who's told what, and what's promised.
