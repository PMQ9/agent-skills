# Service Semantics — Review Guide

Checks for the service lens, as **look for → why → fix**. Distilled from `backend-development`.
Assumption: **everything happens more than once and anything can stop halfway.** For each changed side
effect, replay it: retried · redelivered · interrupted between any two lines · raced by a concurrent twin.

§1 Transactions · §2 Idempotency end to end · §3 Consumers & relays · §4 Outbound calls · §5 Errors ·
§6 Caches · §7 Boundaries & config · §8 False alarms

## §1 Transaction boundaries

- **Network I/O inside a DB transaction** (provider call, email, publish): locks held across a remote
  round-trip, and the systems disagree when either side fails (money moved, row rolled back). Fix: record
  intent + key, commit, call, record outcome — or outbox.
- **No transaction where one is needed**: related writes (marker + effect, ledger + balance) issued as
  separate autocommit statements → a failure between them leaves half a change.
- **Read-decide-write** (read balance/stock/status, compute in app, write absolute value) → concurrent twins
  both pass the check or overwrite each other. Fix: atomic `UPDATE … SET x = x - $n WHERE … AND x >= $n`
  (check rows affected), `SELECT … FOR UPDATE`, or a version column.
- Invariants checked outside the lock or against a stale read; long transactions (loops of remote calls).

## §2 Idempotency end to end

A key at the surface is worthless if the layers below repeat the effect.
- Unsafe operation with no idempotency (money, messages, provisioning).
- Key checked but not claimed atomically / not persisted **before** the effect (see api guide §6).
- Key not forwarded to the downstream that performs the effect (when it supports one).
- An operation *declared* idempotent (PUT, annotation, "retry-safe" job) that isn't.

## §3 Consumers, jobs, relays

At-least-once is the delivery semantics of every real queue and webhook provider.
- **Dedupe marker vs effect**: the marker (processed_events insert) must commit **in the same transaction as
  the effect**. Marker first, effect later (or no enclosing transaction) → a crash/exception after the marker
  makes the redelivery look like a duplicate → effect lost forever. Effect first, marker later → duplicates.
- Handlers that increment/credit/send/insert with no dedupe key, unique constraint, or upsert.
- **Outbox relay**: must publish **then** mark (at-least-once) — marking `published_at` before the send loses
  events on send failure. Multiple relay replicas must **claim** rows (`FOR UPDATE SKIP LOCKED`, lease column)
  or they publish the same rows concurrently (tolerable only if every consumer dedupes).
- **Visibility timeout / lease shorter than worst-case processing** (batch size × per-message time including
  retries and backoff) → message redelivered to another worker mid-processing. Fix: extend visibility per
  message, shrink batches, or bound per-message time.
- **Threshold side effects** ("email when balance < 10%") must fire on the **crossing** (old ≥ t > new), not on
  every event below it — otherwise every subsequent event re-sends.
- Webhook receivers: verify signature, dedupe on provider event ID, handle failure events, reconcile local
  state written at request time with state confirmed by the webhook.
- Dual writes (DB then queue, ledger then balance) as independent steps → outbox or one transaction;
  publishing before commit → consumers act on rolled-back state.

## §4 Outbound call safety

Own these when they break the contract (duplicates, hung requests that callers then retry); pure latency
belongs to DevOps.
- No timeout in a request/tool/consumer path.
- **Retrying a non-idempotent POST** (email, payment) on timeout without an idempotency key → duplicates (a
  timeout doesn't mean it didn't happen).
- **HTTP errors treated as success**: httpx/fetch don't raise on 4xx/5xx unless asked
  (`raise_for_status()`, `res.ok`) — an `except HTTPStatusError` without `raise_for_status` is dead code and a
  500 counts as sent. Final failure after the last attempt silently returned/swallowed.
- Unbounded retries, no backoff/jitter, retrying 4xx.

## §5 Error mapping

- Swallowed errors (`except: pass`, log-and-continue returning success).
- Status codes as control flow inside the domain; everything collapsed into one generic error (callers can't
  tell retryable from permanent); raw downstream errors passed through to clients/models.

## §6 Cache correctness

"Should this be cached" is Performance's; "is the cached value correct" is yours.
- **Invalidation before commit** (`cache.delete` inside the transaction) → a concurrent reader re-caches the
  old value for the whole TTL. Invalidate **after** commit (or on the outbox event), or use versioned keys.
- No TTL; cache key missing a dimension (tenant, user, role, locale, API version) — missing tenant/user is a
  data leak; caching authorization decisions past validity; entitlement caches with long TTLs after plan
  changes.

## §7 Boundaries and config

- Input trusted past the boundary (negative/NaN amounts, absurd sizes).
- **Config with silent fallbacks** (`os.environ.get("URL", "https://prod…")`, default signing keys) → crash at
  startup instead. `process.env.X!` turns a missing secret into a runtime `undefined`.
- Hand-built JSON/SQL via string formatting (quotes in IDs break payloads).

## §8 False alarms

- Naturally idempotent operations (set-status, natural-key upserts) don't need keys.
- No outbox needed for a single-datastore write with no event.
- Frameworks often wrap handlers in transactions, set client timeouts, or dedupe — check before flagging.
- Scale severity with contention and side effects: an external call in a transaction on an uncontended
  internal table is 🟡, not 🔴.
