# Operational review checklist — concrete red flags

This is the detailed reference for the five review areas. Work through the items
that apply to what the diff actually touches — a config-only change doesn't need
the Kubernetes section. Each item is a concrete thing to look for and *why it
bites in production*, so you can write a specific finding rather than a vague
"consider reliability." Don't treat it as a form to fill out; treat it as a
memory aid for failure modes you'd otherwise forget under time pressure.

## Table of contents

1. Infrastructure — env vars, secrets, config, containers, Kubernetes, Terraform, Bicep, cloud, networking, CI/CD
2. Reliability — timeouts, retries, circuit breakers, bulkheads, idempotency, resource cleanup, caching, queues
3. Observability — logging, metrics, tracing, alerting, correlation IDs, error messages
4. Deployment — backward compat, migrations, zero-downtime, feature flags, rollback, config compat
5. Operations — monitoring gaps, complexity, failure modes, scalability, runbooks, ownership

---

## 1. Infrastructure

### Environment variables & configuration
- A var is **referenced but never set** anywhere in the manifests/pipeline/`.env.example` — the deploy starts and crashes (or worse, silently uses an empty string). Trace every new `os.environ[...]` / `process.env.X` to where it's actually provided.
- **Environment-specific values baked into code or image** (URLs, region, account IDs) instead of injected as config — breaks "build once, promote everywhere."
- Config with **no validation at startup** — a typo'd or missing value should fail fast and loud at boot, not produce mysterious behavior three hours later.
- New **required** config with no default and no migration note — every existing deployment breaks on rollout until someone sets it. Prefer optional-with-safe-default, or call out the required rollout step explicitly.

### Secrets management
- **Hardcoded / committed secret** — API key, password, token, connection string, private key in the diff. Critical, always. (Check test fixtures and comments too.)
- Secret **logged** or emitted as a Terraform/Bicep **output** (outputs land in state / deployment history / logs).
- Secret **baked into an image layer** — `RUN` that writes then deletes a secret still leaves it in the earlier layer forever. Use build secret mounts or runtime injection.
- Secret sourced from something other than a vault/secret store when the org has one (env var checked into repo, SAS token / long-lived key that won't revoke when someone leaves).

### Containerization (Dockerfile)
- Container **runs as root** (no `USER` directive) — larger blast radius on compromise.
- **Unpinned base image** (`FROM node:latest` or a floating tag) — non-reproducible builds, silent version drift.
- **No multi-stage build** where one applies — shipping compilers, build tools, and shell into prod = attack surface.
- **No resource limits** implied / dependency on orchestrator limits missing.
- Source copied **before** dependency install — busts layer cache, slow builds.
- `latest` tag or a **mutable tag** used for deploy instead of an immutable digest (`@sha256:...`) — "we deployed v1.2.3" becomes meaningless if the tag was re-pushed.

### Kubernetes manifests / Helm
- **No `readinessProbe`** on a Deployment — traffic routes to pods before they're ready during rollout → 500s and dropped requests mid-deploy.
- **`livenessProbe` that checks a downstream dependency** (e.g. the DB) — a DB blip makes every pod fail liveness and crash-loop simultaneously, turning a small dependency wobble into a full-fleet restart cascade. Liveness must reflect *this process only*.
- **Aggressive liveness** on a slow-starting app (JVM) with no `startupProbe` — liveness kills it mid-warmup, it never comes up.
- **No `resources.requests`** (scheduler can't place well) / **no memory limit** (OOM with no graceful bound). A CPU *limit* can cause CFS throttling that hurts p99 even when CPU isn't saturated — flag CPU limits on latency-sensitive services.
- **Multi-replica workload with no PodDisruptionBudget** — a node drain or cluster upgrade can take down all replicas at once.
- **No `topologySpreadConstraints`** — all replicas may land on one node; that node failing = full outage.
- **`terminationGracePeriodSeconds` too short** for a service with long requests → SIGKILL mid-request during deploys.
- **`hostPath` volume in a Deployment** — data lives on whichever node the pod landed on and is gone after reschedule. Stateful data wants a StatefulSet + PVC.
- **Migrations via Helm `pre-upgrade` hooks** — nasty failure mode where the hook succeeds but the upgrade rolls back, leaving schema ahead of code. Prefer an init container / separate Job / pipeline step.
- **HPA scaling on CPU for an I/O-bound service** — it waits on the DB at 5% CPU while the queue grows. Scale on RPS / queue depth / latency.
- Helm chart with **no `values.schema.json`** — a typo like `replciaCount: 5` renders silently and you deploy 1 replica. Required overrides not guarded with `{{ required }}`.
- Large config in a **ConfigMap** (approaching etcd's ~1MB object limit) or binary content in an env-from-ConfigMap (truncates at NUL bytes).
- In **GitOps** clusters: `kubectl edit` / `kubectl rollout undo` / `kubectl apply` from a laptop — the controller reverts it and the "fix disappears." Rollback in GitOps is `git revert`.

### Terraform / OpenTofu
- **`# forces replacement` in the plan** on a stateful resource (DB, disk, volume, anything with data) — silent destroy-and-recreate = data loss + downtime. This is the single most important Terraform review check. Ask to see the plan.
- **`count` over an ordered list** — removing a middle element shifts every later index and Terraform destroys/recreates everything after it. Push for `for_each` over a set/map (keyed addresses) whenever the collection can change.
- **Resource renamed or moved into a module with no `moved {}` block** — a refactor that reads as a rename to a human is a destroy+recreate to Terraform.
- **`prevent_destroy` missing** on stateful prod resources; **`ignore_changes`** used to paper over drift nobody understood rather than to manage genuinely external-managed fields.
- Provider pinned with **`>=`** instead of `~>` (a breaking release eventually lands); `.terraform.lock.hcl` not committed or missing platforms CI runs on.
- **Shared/monolithic state** (prod+dev, or networking+apps together) — huge blast radius; a bad app apply can tear down networking. Workspaces used to "separate" prod/dev (they don't isolate — same state, just names).
- Secrets in `tfvars` committed to the repo; `data`-sourced secrets landing in unencrypted state.
- **CI auto-applies to prod with no human approval gate**, or apply from a developer laptop against shared state.

### Bicep / ARM
- Resource **removed from the template without deployment stacks** — plain ARM deploys are additive, so the resource is orphaned and still billing. Removal PRs need stacks + `--action-on-unmanage`.
- **`what-if` skipped** "because it's small" — that's the change that drops a database.
- Loops indexed by **array position** — reordering the input array recreates resources.
- Secrets emitted as module **`output`** (stored in deployment history); API-version bumps that change schemas and trigger recreation; hardcoded subscription IDs; soft-delete name collisions (Key Vault / App Service).

### Cloud (AWS / Azure) — high-value spot checks
- **`0.0.0.0/0` ingress** to a prod security group / NSG.
- **Wildcard IAM** (`Action:*` / `Resource:*`), loose `iam:PassRole`, a KMS key policy with `"AWS":"*"`, or long-lived IAM users/access keys where OIDC + roles belong. On Azure: `Owner` where `Contributor` suffices; RBAC at subscription scope inheriting everywhere; service principal with a long-lived secret where a managed identity works.
- **Encryption left off** (several AWS defaults are off: EBS/RDS/S3/ElastiCache); Key Vault / Recovery Vault without soft-delete + purge protection.
- **Lambda + RDS without RDS Proxy** — connection-pool exhaustion under concurrency.
- **Private endpoint without a matching Private DNS Zone** (Azure) — the hostname resolves to the public IP and the connection just fails.
- **Single-/two-AZ "HA"**, single shared NAT, prod RDS on burstable `db.t*`, hot partition keys (DynamoDB/Cosmos), async consumers with **no monitored DLQ**, logs with **never-expire retention**.

### Networking
- **Overlapping or undersized CIDRs** (a `/24` VPC that can't grow; ranges that can't peer later).
- **Manual cert renewal** tracked on a calendar (an outage scheduler) instead of ACME/managed; TLS 1.0/1.1 still enabled.
- **DNS TTL not lowered before a planned cutover** — long TTL = long window of mixed old/new routing.
- Proxy **body-size / idle-timeout mismatches** (NGINX default `client_max_body_size` 1MB → surprise 413s; proxy idle < backend idle → resets); response buffering that breaks SSE/streaming/gRPC.
- **CDN cache key including user-specific data** — can serve user A's private data to user B. Trusting `X-Forwarded-For` from arbitrary clients.

### CI/CD pipeline
- **Separate build per environment** with config baked in, instead of building one artifact and promoting the same digest — the thing you tested isn't the thing you shipped.
- Third-party **GitHub Actions pinned to a tag, not a commit SHA** (tags move — supply-chain risk); missing least-privilege `permissions:` block.
- **Secrets scoped so PR pipelines can reach prod credentials** (should be `environment: prod`-scoped); long-lived cloud keys in CI instead of OIDC.
- **No one-click / fast rollback path**, or a rollback nobody has rehearsed in months. DB migrations or config edits done by hand outside the pipeline.
- Flaky tests parked in a permanent "quarantine"; branch-per-environment instead of promoting one artifact.

---

## 2. Reliability

- **Any remote call with no timeout** — HTTP, RPC, DB query, cache, queue, even DNS. SDK defaults are frequently "infinite." This is the most common and most damaging reliability gap: a slow (not failed) dependency causes callers to pile up until the pool/threads exhaust and the whole service stops responding. Every network call in the diff needs an explicit timeout.
- **Fixed timeout instead of a propagated deadline** — if the inbound request has a 5s budget but this call waits 30s, the work is wasted after the caller already gave up. Deadlines should propagate from the inbound request (Go `context`, gRPC deadlines).
- **Retries without exponential backoff + jitter** — synchronized clients hammer a recovering server in lockstep (thundering herd) and keep it down. Want full jitter: `sleep = rand(0, base·2^attempt)`.
- **Retries on non-idempotent operations** (a POST that creates an order/charge) without an idempotency key → duplicates, double charges.
- **Retries on non-retryable errors** (4xx, 401/403), ignoring `Retry-After` on 429, unbounded retry attempts/elapsed time, or no retry budget (retries amplify a dependency's bad day into a self-inflicted DDoS).
- **No circuit breaker / bulkhead** where a single slow dependency can drag the whole service down; breaker state not exposed as a metric (an open breaker nobody can see is a silent outage); absolute-count thresholds that flap (use %-over-window).
- **Single shared connection/worker pool for everything** — one slow dependency starves unrelated traffic. Separate pools per dependency/concern.
- **Unbounded queue / channel / buffer** — a memory leak that hasn't happened yet. Want a bounded queue with back-pressure (block or reject, never silently drop).
- **DB pool sized by guessing** — `max_connections` is a hard ceiling on the *sum* across all instances; exceed it and new connections fail. Size = instances × workers × concurrency, and bound it.
- **Non-idempotent queue consumer** — delivery is at-least-once in practice, so any "exactly-once" assumption is a red flag; long handlers must extend the visibility timeout or they'll be redelivered and double-process.
- **Resource not cleaned up on the error path** — connection/file/lock/goroutine/thread leaked when an exception fires. Check `finally`/`defer`/`with`/`using` covers every path, not just the happy one.
- **Fallback / degraded path that's never exercised** (untested code that runs only during an incident) or a fallback that itself calls a remote service that can also be down.
- **Cache with no TTL or no invalidation** (stale-forever bugs); no request coalescing / singleflight (cache stampede when a hot key expires); negative caching of transient errors for too long.
- **Multi-step distributed transaction / saga** with no compensating actions and no persisted state to resume after a mid-saga crash.

---

## 3. Observability

- **New or changed service/code path ships with no telemetry** — you need it most right after it breaks and have it least. Check the four golden signals are covered: latency, traffic, errors, saturation.
- **Latency as an average or a gauge, not a histogram** — averages hide the p99. Also watch histogram buckets that don't straddle the service's real p50/p95/p99 (all signal collapses into one bucket).
- **High-cardinality metric label** — `user_id`, `request_id`, `trace_id`, full URL with IDs, or any unbounded user-supplied value attached to a metric → time-series explosion that can take down the metrics backend. Use route templates (`/users/:id`), not `/users/12345`.
- **Errors swallowed with no log and no metric** — the definition of a silent failure. Every new failure mode should be observable.
- **Logging a secret / token / PII / full request or response body** — logs persist and are subject to GDPR/FERPA/HIPAA; redact at the logger, not at developer discretion. Watch `print()`/`console.log` that bypasses the structured logger.
- **Unstructured string logs** (regex archaeology later) and **log lines missing the trace/correlation ID** — without it you can't pivot metric → trace → log, or stitch a request across services.
- **Everything logged at ERROR** (or validation 400s logged as ERROR) — real outages get buried and on-call gets paged for noise. ERROR = unrecoverable + human-actionable.
- **Context / correlation not propagated across queues, background jobs, or custom RPC** — auto-instrumentation only covers HTTP/gRPC, so traces silently break at those hops.
- **Tracing that samples out errors** — always keep all error traces; sampling only the happy path defeats the purpose.
- **Threshold alerts** (`CPU > 80%`, `p99 > 200ms for 5m`) instead of symptom / error-budget burn-rate alerts; alerts with **no runbook link, no owner, or that aren't actionable** ("let's see if it clears" = delete it).
- **Error messages that aren't actionable** — say what failed *and* what to do / what to check next, include identifiers, don't just surface a raw stack trace to the operator.
- **Verbose logging on a chatty hot path** — cost blowup (≈1KB/line × 10k RPS ≈ hundreds of GB/day) and signal drowned in noise.
- **Deploys not annotated on dashboards** — can't distinguish a deploy-caused spike from an organic one during an incident.

---

## 4. Deployment

The core question: **during the rollout window, when the old and new versions (and
old and new schema/config) are both live, does everything still work — and if we
have to undo this, can we?**

- **Backward compatibility broken during rollout** — new code assumes a field/endpoint/behavior that old still-running instances don't provide (or vice versa). During a rolling deploy both run simultaneously; a "flag day" that requires all-or-nothing cutover is the red flag.
- **`NOT NULL` column with no default added in a single migration** on a running system — old code inserting rows without that column breaks immediately. Use expand/contract: add nullable → backfill → add constraint in a later release.
- **Dropping a column / renaming / changing a type in the same deploy that starts using the new shape** — split into stages (add new + write-both → read-new → drop-old). Rule of thumb: *code must be forward-compatible with the next migration; schema must be backward-compatible with the currently running code.*
- **Migration that locks a hot table** (blocking `ALTER`, index build without `CONCURRENTLY`, backfill in one giant transaction) — looks fine in a small test DB, takes the table down against 40M rows. Ask what row count it runs against.
- **Migration coupled to the app deploy** so it can't be run/rolled back independently; **no rollback for the migration** (especially destructive ones) or a rollback that's impossible because data was already transformed.
- **Zero-downtime not actually achieved** — no readiness gating, connections dropped on shutdown, no graceful drain (see Infrastructure/Reliability).
- **Risky change shipped without a feature flag** where a flag would decouple deploy from release and give an instant off-switch. Conversely: flags added with no cleanup plan (flag debt) or flag state that isn't safe to flip mid-request.
- **No rollback strategy stated, or a rollback that doesn't actually work** — e.g. can't roll back because the migration already dropped the old column, or because it's GitOps and someone will `kubectl rollout undo` (which the controller reverts). A deploy you can't cleanly undo is an incident waiting to happen.
- **Config change that isn't backward-compatible** — a renamed/removed config key that old instances still read, or a new required key with no default, breaks instances mid-rollout.

---

## 5. Operations

The core question: **six months from now, when the author is gone and this pages
someone at 3am, do they have what they need to see it, understand it, and fix it?**

- **Monitoring gap** — the change adds a component, dependency, or failure mode with no dashboard, no SLO, and no alert. You'll discover the gap during the incident, which is the worst time.
- **Operational complexity not justified** — a new moving part (queue, cache, service, tool) that adds failure modes and on-call surface for marginal benefit. Ask whether the simpler thing would do.
- **Failure modes not understood or bounded** — "what happens when this new dependency is down for an hour?" should have an answer, and ideally one that's been tested. The failure path is the most-untested code in any system.
- **Scalability cliff** — works at today's volume, falls over at 10x (unbounded in-memory accumulation, O(n²) over a growing set, a per-item remote call inside a loop, fan-out with no limit). Flag when growth assumptions are implicit.
- **Runbook / recovery not updated** for a new failure mode, non-automated deploy, or new manual step — tribal knowledge that evaporates when the author leaves.
- **Ownership / cost hygiene** — new cloud resources with no owner/environment/cost-center tags become orphaned, unallocatable, and unpageable.
- **Backups with no tested restore** — an untested backup is a hope, not a backup; a change to a backup/retention path should prompt "has a restore actually been run?"
- **DLQ / poison-message handling** — async consumers whose DLQ depth isn't alerted on, with no tooling to inspect or replay; poison messages silently backing up and starving healthy traffic.
- **Failover assumed but never tested** — "multi-AZ / multi-region on paper," or a hardcoded single region that makes future failover a rewrite.
- **A previously automated flow made manual** — every manual step is a future 3am mistake; flag regressions in automation.
