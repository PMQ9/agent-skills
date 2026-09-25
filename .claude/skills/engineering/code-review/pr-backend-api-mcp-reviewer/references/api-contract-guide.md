# HTTP API Contract — Review Guide

Checks for the HTTP lens, as **look for → why → fix**. Distilled from `api-design`.

§1 Breaking changes · §2 Methods & status · §3 Errors · §4 Shapes · §5 Pagination ·
§6 Idempotency & concurrency (as implemented) · §7 Auth & limits · §8 OpenAPI · §9 Webhooks · §10 False alarms

## §1 Breaking changes (check first)

The contract lives in serializers/DTOs/`toXResponse`/`response_model`, route paths, status codes, enums, and
the OpenAPI file. Any change to these on an existing endpoint is a contract change until proven otherwise.
🔴 on a published/public version (you can't redeploy mobile apps or partners); 🟠 internal.

- Field removed/renamed (casing too: `created_at`→`createdAt`); type changed (`"129.99"`→`12999`).
- **Meaning changed under the same name** (dollars→cents, pre-tax→post-tax) — no parser fails, numbers are wrong.
- ID format/source changed (public UUID → internal bigint; >2^53 corrupts in JS; stored IDs stop resolving).
- Request field newly required, or previously accepted values rejected.
- **New enum value** returned to clients/SDKs that decode as a closed enum (Swift `Codable`, kotlinx/Moshi,
  Jackson with fail-on-unknown, runtime validators like zod) → decode failures. (Plain TS unions are erased at
  runtime — they break exhaustive `switch`/`never` checks, not decoding.) Fix: document enums as open + `unknown` fallback, or gate behind a version/opt-in.
- Status or error code changed for the same outcome; defaults changed (sort, page size, filter).
- **Pagination scheme changed** (page→cursor): old params silently ignored → clients loop on page 1 or stop early.
- Fix pattern: add alongside, deprecate (`Deprecation`/`Sunset`, spec `deprecated: true`), remove in a new
  version. Tooling: `oasdiff breaking base.yaml head.yaml` (sees only the spec).

Usually safe: new optional request params, new response fields, new endpoints.

## §2 Methods and status codes

- **Writes in GET** (view counters, last-viewed, auto-assign) — prefetchers, crawlers, retries fire GETs.
- **200 with `{"success": false}`** — monitoring, retries, and client libraries all read it as success.
- PUT implemented as partial update (or vice versa); 5xx for client mistakes; 5xx instead of 429 +
  `Retry-After`; DELETE of a deleted resource → 500.
- Missing `201` + `Location` / `202` + poll URL: 🟡 unless the spec promises it (then §8).

## §3 Error envelope

- More than one error shape in the API → clients write one parser. One envelope (RFC 7807
  `application/problem+json` default; an existing consistent envelope beats switching).
- **Internals leaked**: `err.stack`, driver messages, SQL, hostnames, raw provider bodies. Stable `code`/`type`
  + human `detail`; internals to logs keyed by `trace_id`.
- Validation errors must name the field.

## §4 Shapes and types

- Money as float (`parseFloat`, `* 100`, JSON number dollars) → integer minor units or decimal string +
  currency; mind currency exponents (JPY 0, KWD 3).
- IDs as JSON numbers; internal auto-increment IDs exposed; mixed casing; same resource with different shapes
  per endpoint; dates without timezone; `null` vs absent inconsistent.
- Serializing the DB row → new internal/PII fields leak into responses (rate at true severity; tag security).
- Collections as a bare array → no room for pagination metadata later.

## §5 Pagination

- No server-side max (`limit` straight from the query) → one request becomes an outage.
- Unvalidated numbers (`NaN` offsets); malformed cursor → 500 instead of 400.
- **Cursor on a non-unique sort key** (`created_at` alone with strict `<`/`>`) → rows sharing a value at a page
  boundary are skipped (or duplicated with `<=`). Fix: compound cursor `(created_at, id)` + matching ORDER BY.
- Non-opaque cursors clients construct; sort/filter on arbitrary fields (allowlist).
- Offset is fine for small/admin data.

## §6 Idempotency and concurrency — verify the implementation

**Idempotency-Key must have all four, or it fails exactly on the retry it exists for:**
1. **Atomic claim before the side effect** — `SET key NX` / unique insert of `(scope, key)` in `processing`
   state. A plain `GET` then act lets two concurrent retries both miss and both charge.
2. **Persisted before the effect completes** — storing the response only after the charge means a crash or
   timeout in between lets the retry charge again. Record intent → effect → store result.
3. **Scoped to the tenant/principal** — a global `idem:{key}` lets one merchant's key return another's response.
4. **Request fingerprint** — same key + different body must be rejected (409/422), not silently answered with
   the first result. Keep keys ≥ 24h for mobile retries.
Also: forward a key to the downstream provider when it supports one.

- **No key at all** on POSTs that move money, send messages, or create billable things → 🔴 on public APIs.
- **Side effect before the local record** (provider refund, then insert) → failed insert = untracked money;
  retry repeats it.
- **Cumulative invariants** (total refunds ≤ order total) checked per request instead of against the running
  sum, or without a lock → repeated/concurrent requests exceed it.

**If-Match / ETag:**
- ETag must change on **every** write: `updated_at` truncated to seconds collides for two writes in the same
  second → If-Match passes on stale data. Use a version counter or full-precision timestamp/hash.
- Check-then-save is a race: compare in the `UPDATE … WHERE id = $1 AND version = $2` and treat 0 rows as 412.
- Optional If-Match still permits blind overwrites — fine if documented.

**PATCH semantics:** JSON Merge Patch (RFC 7396) means `null` **deletes/clears** a field. Code that skips `None`
values silently breaks that promise. JSON Patch is different — check which one the API documents.

## §7 Auth and limits at the surface

- Credentials in query strings; a new endpoint with a different auth scheme.
- **Authorization beyond authentication**: a money-moving or destructive route guarded only by "logged in" /
  "same account" with no role/permission check → rate at true severity (🔴/🟠), tag `pr-security-review`.
- Expensive new endpoints without rate limits where the API has them.

## §8 OpenAPI drift

- Handler contract changed, spec didn't (or vice versa) — the absence of a spec hunk is the finding.
- Spec status ≠ handler status (spec `201`, code `200` → clients branching on 201 treat success as failure and
  retry). Spec types ≠ code (dollars vs cents). New endpoint without spec or examples.

## §9 Webhooks

Receiving: verify signature + timestamp before acting; dedupe on provider event ID; ack fast; idempotent
effects; handle failure events, not just success. Sending: per-subscriber signing secret, event ID, backoff
retries, replay window.

## §10 False alarms

- Internal API with its only client updated in the same diff → coordination, not breakage.
- `POST /orders/{id}/cancel` is correct. 400 vs 422 only matters if mixed.
- Don't demand RFC 7807 over an existing consistent envelope; don't demand ETags where concurrent edits don't
  matter; don't demand idempotency keys on naturally idempotent operations.
