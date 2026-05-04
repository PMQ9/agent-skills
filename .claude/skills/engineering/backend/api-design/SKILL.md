---
name: api-design
description: Use this skill for designing the HTTP surface of a service — resource modeling, URI structure, HTTP method and status code choices, request/response shapes, pagination, filtering, versioning, error envelopes, idempotency keys, conditional requests (ETag/If-Match), rate limiting, and OpenAPI conventions. Trigger when designing a new REST API, reviewing an endpoint before it ships, deciding between PUT and PATCH, choosing how to paginate a list endpoint, designing an error format, planning an API version bump, writing or reviewing OpenAPI specs, or whenever the user is shaping what an HTTP request and its response should look like. Use this even when the user doesn't say "REST" — anything about endpoint design, URL structure, or what a response body should contain belongs here. This skill complements backend-development (which covers what happens below the controller) by focusing entirely on what crosses the network.
---

# API Design

This skill is about the HTTP surface — the contract between your service and the clients that call it. The contract is the most expensive thing you'll ship, because once anyone depends on it, every change costs you. Get it right early.

This is not a REST purity manifesto. It's the set of conventions that, in 2026, lets a competent client engineer integrate against your API without reading the source. When you depart from these, have a reason.

## What "REST" actually buys you

REST as a discipline gives you three things worth keeping: a uniform interface (everyone understands `GET /users/123`), cacheability (HTTP caches, ETags, conditional requests are free if you play along), and statelessness (any instance can serve any request). HATEOAS — the hypermedia constraint — almost nobody implements end-to-end, and that's fine; clients hardcode URL templates and the world keeps turning.

Reach for REST when you're exposing resources that map cleanly to nouns and the operations are mostly CRUD-shaped. Reach for RPC-style (gRPC, JSON-RPC) when operations are inherently action-shaped (`refundPayment`, `cancelShipment`) and resource modeling feels forced. Reach for GraphQL when clients have wildly varying read needs and the alternative is a proliferation of bespoke read endpoints. Most internal APIs end up RPC-flavored REST and that's honest — name the action endpoints clearly (`POST /orders/{id}/cancel`) rather than torturing them into resource shape.

## Resource modeling

The first design move is identifying the resources, not the endpoints. A resource is a thing the client cares about: an order, a user, a subscription, a payment. Endpoints are derived from resources.

Two passes that catch most modeling mistakes:

First, write the **client's vocabulary** before you write any URIs. If the client says "shipment" and your database says `tracking_record`, the API exposes "shipment". The API is a translation layer. Internal names leak implementation; external names are a contract.

Second, ask whether each resource is a **thing** or an **event**. Things are mutable nouns (`/orders/{id}` — same resource over time, properties change). Events are immutable facts (`/order-events/{id}` — created once, never updated). Mixing them produces APIs where it's unclear whether a `PUT` overwrites history or amends a record.

Sub-resources express containment, not just association. `/orders/{order_id}/line-items` is right when line items don't exist outside their order. If a line item could be referenced from elsewhere, it's a top-level resource with a foreign key (`/line-items/{id}` with `order_id` in the body). Don't nest more than two levels — `/users/{u}/orders/{o}/line-items/{l}` is a sign you're modeling joins, not resources.

## URI conventions

A few conventions that pay for themselves in interop:

Use plural nouns for collections (`/orders`, not `/order`). The collection is the resource; an item is identified by ID within it.

Use lowercase with hyphens, not underscores or camelCase. `/shipping-addresses`, not `/shippingAddresses` or `/shipping_addresses`. URIs are case-sensitive in the path; pick a convention and never deviate.

Don't put verbs in URIs *unless* the operation isn't CRUD-shaped. `POST /orders/{id}/cancel` and `POST /payments/{id}/refund` are clearer than contorting them into PATCH operations. The rule is: nouns by default, verbs when the alternative is dishonest.

Don't expose internal IDs that leak business volume (auto-increment integers). Use UUIDs (v7 if you can — time-ordered) or opaque slugs. This was covered in `backend-development`; the API is where the choice becomes visible to the world.

Query parameters are for filtering, sorting, paginating, and shaping responses — not for identifying resources. `/orders?status=shipped` is filter; `/orders/shipped` is wrong because "shipped" isn't an order.

## HTTP methods, with intent

`GET` is safe and idempotent. It must not have side effects. If a `GET` writes to the database (audit log, view counter, "recently viewed" tracker), think hard — caches, prefetchers, and crawlers will fire it. At minimum, make the side effect idempotent.

`PUT` replaces a resource. The request body is the new state. `PUT /users/{id}` with a partial body wipes out fields you didn't include. PUT is idempotent: doing it twice is the same as doing it once.

`PATCH` partially updates. Use JSON Merge Patch (RFC 7396) for simple cases — the request body is a sparse object, present fields overwrite, `null` deletes. Use JSON Patch (RFC 6902) when you need array operations or path-based edits, but it's heavier and most clients hate it. Pick one per API and document it.

`POST` creates, or executes a non-idempotent action. `POST /orders` creates an order; `POST /orders/{id}/cancel` cancels it. POST is the catchall when nothing else fits — that's intentional.

`DELETE` removes. Idempotent: deleting an already-deleted resource returns 404 or 204, not 500. For anything involving money, compliance, or audit, prefer soft delete (a flag) or a separate archive resource — true deletes are nearly always regretted later.

The safety/idempotency table matters because retries depend on it: clients (and middleboxes) will retry safe and idempotent methods automatically. They will not retry POST without an idempotency key (covered below).

## Status codes that mean something

Use a small, consistent set. The full IANA registry is a trap — clients only handle the common ones gracefully.

For success: `200 OK` (request succeeded, body has the result), `201 Created` (a new resource was created — include `Location` header pointing to it), `202 Accepted` (request accepted, work happens async — include a way to poll), `204 No Content` (success, no body, common for DELETE and some PUTs).

For client errors: `400 Bad Request` (malformed, validation failed — body explains what), `401 Unauthorized` (no/bad credentials), `403 Forbidden` (credentials fine, not allowed), `404 Not Found` (resource doesn't exist or shouldn't be visible to this caller), `409 Conflict` (request conflicts with current state — concurrent edit, duplicate creation, illegal state transition), `410 Gone` (resource permanently removed — useful for deprecated endpoints), `422 Unprocessable Entity` (semantic validation failed — disputed; many APIs use 400 for everything client-side, which is fine if consistent), `429 Too Many Requests` (rate limited — include `Retry-After`).

For server errors: `500 Internal Server Error` (something broke, not the client's fault), `502/503/504` (upstream/availability/timeout — surface honestly so clients can retry).

Two rules that keep this sane: pick 400 *or* 422 for validation and stick with it; never use 200 with `{"success": false}` in the body — that breaks every HTTP-aware tool the client owns.

## Request and response shapes

Every response body is JSON, even errors. Set `Content-Type: application/json; charset=utf-8`. UTF-8 always.

Keep field names consistent across the API. Pick `snake_case` or `camelCase` and never mix. Most JSON APIs in 2026 use `camelCase` (matches JavaScript clients) or `snake_case` (matches Python/Ruby clients). Either is fine; mixing isn't.

Wrap collection responses in an envelope so you have somewhere to put pagination metadata:

```json
{
  "data": [...],
  "pagination": {"next_cursor": "...", "has_more": true}
}
```

For single-resource responses, returning the resource at the top level is cleaner — `GET /orders/{id}` returns the order object directly, not `{"data": {...}}`. Be consistent: collections wrapped, items not, and document the rule.

Return what you wrote. After `POST /orders` or `PATCH /orders/{id}`, return the full resource (or at least the canonical representation) in the body. Saves the client a follow-up GET and surfaces server-computed fields (timestamps, derived totals).

Dates and times are ISO 8601 with timezone, always: `2026-05-03T14:30:00Z`. Money is an object or a fixed-precision string with currency: `{"amount": "12.50", "currency": "USD"}`, never a float — floats lose pennies and you will get sued.

Booleans are booleans. Don't return `"true"`, `0`, or `"yes"`.

Don't return `null` and `missing field` to mean different things. Pick one — either every field is always present (with `null` for absent) or optional fields are simply omitted. Mixing creates parser bugs in every client.

## Pagination

Two real options. Pick deliberately.

**Offset/limit** (`?page=3&page_size=50` or `?offset=100&limit=50`) is simple and what every dashboard wants. It breaks down badly: results shift if items are inserted or deleted between requests, and `OFFSET 1000000` is slow on any real database. Use it for small, mostly-static datasets and admin tooling.

**Cursor-based** (`?cursor=eyJpZCI6ImFiYyJ9&limit=50`) is what production APIs use. The cursor is an opaque, server-encoded position (typically the sort key of the last returned item, base64'd). The client passes it back to get the next page. It's stable under concurrent writes and it's `O(log n)` regardless of page depth.

The cursor is opaque to the client. Don't expose its internals — that's how you end up unable to change your sort key without breaking everyone. Pass `next_cursor` back in the response; clients don't construct cursors, they only echo them.

Document the maximum page size and enforce it server-side. A client that requests `limit=1000000` should get clamped, not OOM your service.

## Filtering, sorting, sparse fieldsets

Filtering: `?status=shipped&created_after=2026-01-01`. Use exact-match query params for the common cases. Don't invent a filter DSL until you've proven you need one — clients hate them and they're hard to validate. If you need richer filtering, accept a JSON body on a `POST /resource/search` endpoint; URLs aren't the right place for complex predicates.

Sorting: `?sort=-created_at,name`. Comma-separated fields, leading `-` for descending. Document the sortable fields explicitly — letting clients sort by any field is an indexing landmine.

Sparse fieldsets: `?fields=id,name,total`. Useful for mobile clients and bandwidth-sensitive consumers. Easy to add later; don't preemptively complicate v1.

## Versioning

You will need to make breaking changes. Plan for it.

Three viable strategies:

**URI versioning** (`/v1/orders`, `/v2/orders`). Crude but obvious — every client knows what version they're on, every log line shows it, every cache key is naturally segmented. The least clever and the most reliable. Recommended default.

**Header versioning** (`Accept: application/vnd.acme.v2+json` or a custom `API-Version` header). Cleaner URIs, more "RESTful" by some readings. In practice it makes debugging harder (curl-ing an endpoint behaves differently than your client because you forgot the header), and many CDNs/caches ignore custom headers when computing cache keys. Use only if you have a strong reason.

**Date versioning** (`API-Version: 2026-05-01`). Stripe-style. Every client pins to a date; you publish changelogs at each version. Excellent for evolving APIs with thousands of integrations, overkill for internal services.

Whatever you pick: never change behavior of a deployed version. New behavior goes in a new version. Bug fixes in the deployed version are limited to genuine bugs (a 500 that should be a 400), not changes to documented behavior.

Deprecation: announce, set a sunset date, return `Deprecation: true` and `Sunset: <date>` headers, log usage so you know who to email, give clients at least 6 months for public APIs and one quarter for internal ones. `410 Gone` is the right status when you finally turn the old version off.

## Error responses

Errors are an API surface, not an afterthought. Clients write code against them.

Use a single, consistent error envelope across every endpoint. RFC 7807 (Problem Details for HTTP APIs) is the standard worth following — and serve every error body with `Content-Type: application/problem+json` so middleboxes and client libraries can recognize it as a problem document, not an arbitrary JSON shape:

```json
{
  "type": "https://errors.acme.com/insufficient-funds",
  "title": "Insufficient funds",
  "status": 402,
  "detail": "Account balance is $4.20, transaction requires $50.00",
  "instance": "/transactions/abc123",
  "code": "insufficient_funds",
  "trace_id": "01HXYZ..."
}
```

`type` is a stable URI that identifies the error class. Clients switch on it. `title` is human-readable, English, stable. `detail` is contextual and may include user data. `code` is a short, stable string for clients that prefer it to URIs. `trace_id` lets your support team find the request in your logs.

For validation errors with multiple fields, extend the envelope:

```json
{
  "type": "https://errors.acme.com/validation",
  "title": "Validation failed",
  "status": 400,
  "errors": [
    {"field": "email", "code": "invalid_format", "message": "Not a valid email"},
    {"field": "age", "code": "out_of_range", "message": "Must be 18 or older"}
  ]
}
```

Three rules that prevent the most common error-handling bugs:

The HTTP status code and the body must agree. Don't return 200 with an error body. Don't return 400 with `{"success": true}`.

Error messages are for humans (and logs). Error codes are for machines. Clients should never `if (response.message === "Insufficient funds")` — that breaks the moment you fix a typo. They should switch on `code` or `type`.

Never leak stack traces, SQL queries, or internal hostnames. The `detail` field is for the caller, not for your debugging — put internal context in logs, keyed by `trace_id`.

## Idempotency keys

Any non-idempotent operation that handles money, sends an email, or otherwise can't be safely repeated needs an idempotency key. The pattern:

The client generates a UUID per logical operation and sends it in the `Idempotency-Key` header. The server, on first receipt, processes the request and stores `(idempotency_key, response)` for at least 24 hours. On any duplicate within the window, return the stored response without reprocessing.

The key is per-client-intent, not per-retry. The client uses the *same* key when retrying the same operation and a *new* key for a new operation. If the client uses the same key for two genuinely different requests, return `409 Conflict`.

Persist the response, not just "I've seen this key" — otherwise the second caller after a crash gets a different answer than the first. Persist before you do the side effect, ideally in the same transaction (the outbox pattern from `backend-development` composes well here).

Idempotency-Key applies to POST and PATCH. GET, PUT, DELETE are already idempotent at the protocol level.

## Conditional requests, ETags, and optimistic concurrency

ETags solve two problems for free: cache validation and lost updates.

On every `GET /resource/{id}`, return an `ETag: "abc123"` header — a hash of the resource state, or its version number, or its `updated_at`. Clients can later send `If-None-Match: "abc123"` and get `304 Not Modified` (with no body) when nothing has changed. CDNs do this automatically; your origin saves bandwidth.

For writes, require `If-Match: "abc123"` on PUT/PATCH. If the ETag has changed since the client read, you return `412 Precondition Failed` and the client re-fetches. This is optimistic concurrency at the HTTP layer — no extra application code, the protocol does it.

ETags don't have to be content hashes. A version column or `updated_at` works fine. The only requirement is that it changes when the resource changes.

## Rate limiting and quotas

Every public-facing API needs rate limiting. The headers that have become a de facto standard:

```
RateLimit-Limit: 1000
RateLimit-Remaining: 847
RateLimit-Reset: 30
```

(`RateLimit-Reset` is seconds until the window resets, per the IETF draft. Some APIs use `X-RateLimit-*`, which works but is unstandardized.)

When the client hits the limit, return `429 Too Many Requests` with `Retry-After: 30` (seconds, or an HTTP-date). Don't punish overage with 5xx; 5xx tells the client *you're* broken, and they'll retry harder.

Rate-limit by the right key: API key for B2B, user ID for authenticated user APIs, IP only as a backstop (it's a bad key — NATs, CGNATs, mobile carriers all share IPs). Limit by both per-second and per-day for any API where bursts and total usage both matter.

## Authentication at the surface

Most APIs in 2026 use one of three patterns at the HTTP layer:

**Bearer tokens** (`Authorization: Bearer <token>`). The token is a JWT, an opaque API key, or a session token. Simple, works everywhere. Rotate tokens, never put them in URLs.

**OAuth 2.0 / OIDC** for user-authorized third-party access. Use the authorization code flow with PKCE for new integrations. Don't roll your own OAuth.

**mTLS** for high-security service-to-service. Heavier setup, but the client identity is at the transport layer and can't be replayed.

The API design point: pick one, document it, and apply it uniformly. APIs that mix three auth schemes for historical reasons are the ones with the worst integration experience.

Never put credentials in query strings — they end up in access logs, browser history, and every reverse proxy along the way.

## OpenAPI: the contract

If you have an API, you have an OpenAPI (or equivalent) spec. The only question is whether it's checked in or scattered across people's heads.

Pick one of two paths:

**Spec-first.** Write the OpenAPI spec, generate stubs and clients, fill in the implementation. The spec is the source of truth; the code conforms. Best for APIs that ship to external integrators or have many clients.

**Code-first with generated spec.** Annotate handlers (FastAPI, NestJS, etc.) and emit OpenAPI from the code. Faster for internal services, but the spec drifts the moment annotations get stale.

Either way: serve the spec at a stable URL (`/openapi.json` is the convention), version it alongside the API, and use it to drive contract tests in CI. A diff in the spec without an explicit version bump should fail the build.

Document examples for every endpoint. Schema alone is not enough — clients learn from examples faster than from types.

**Tooling worth wiring up early.** `npx @redocly/cli lint openapi.yaml` catches schema mistakes before they reach a reviewer. `npx @stoplight/prism-cli mock openapi.yaml` spins up a mock server from the spec, which lets clients integrate before the backend exists and lets you smoke-test that your own implementation matches the contract.

**Starter template.** When you're starting a new spec, see `assets/openapi-starter.yaml` in this skill — a known-good OpenAPI 3.1 skeleton with cursor pagination, RFC 7807 problem+json error responses, BearerAuth, ETag/If-Match, Idempotency-Key, and rate limit headers already wired up. Copy it and edit the resource names rather than starting from a blank file.

## Webhooks (briefly)

If your API pushes events to clients, design the receive side as carefully as the send side. Each webhook needs:

A signing secret per subscriber, signature in a header (`Webhook-Signature: t=...,v1=...`), payload signed alongside a timestamp to prevent replay. Stripe's format is the de facto reference.

An event ID for deduplication — clients will receive duplicates because at-least-once is the only honest delivery semantic.

A timeout (clients have 5–30 seconds to ack) and a retry schedule with exponential backoff and a final dead-letter behavior (disable subscription after N consecutive failures, alert the customer).

A way to replay events for a window — clients will lose them.

## Delivery checklist

When you're handing over an API design — to a reviewer, to an implementing engineer, or to integrators — make sure the artifact includes all of these. Missing items are where review questions and integration bugs come from:

- Resource model: what the resources are, what their identifiers look like, how they relate
- Endpoint table: URI, method, summary, auth required, status codes that can come back
- Request/response examples (concrete JSON, not just schemas) for the happy path and at least one error path
- Error catalog: every `type` URI / `code` the API can return, with HTTP status mapping
- Pagination, filtering, sorting rules — including the allowlist of sortable fields and the max page size
- Versioning and deprecation policy: which strategy, how long versions live, how breaking changes are communicated
- Auth mechanism (one, not three) and rate-limit policy
- An OpenAPI 3.1 spec, lint-clean

If you're producing a design doc as the deliverable, write it as something a senior engineer could implement from without follow-up questions.

## Anti-patterns

Returning 200 with `{"success": false, "error": "..."}`. The HTTP status code exists for this. Using 200 for failure breaks every monitoring tool, every CDN, every client library that wasn't written specifically for your API.

Action verbs in noun-shaped URIs (`/getOrder/{id}`, `/createUser`). The HTTP method is the verb. The exception, again, is genuinely action-shaped operations on a resource (`POST /orders/{id}/cancel`).

Plural-vs-singular inconsistency. `/users` and `/order` and `/payments` in the same API is a tell that there's no review process.

Different response shapes for the same resource depending on endpoint. `GET /orders` returns `{order_id, status}` but `GET /orders/{id}` returns `{id, status, ...}`. Pick a representation per resource and use it everywhere.

Hardcoded English error messages as the API contract. Once a client greps for `"Insufficient funds"`, you can't fix the typo or translate the API. Use stable codes; messages are documentation.

Boolean flags that should be enums. `is_active`, `is_archived`, `is_deleted` covering a workflow with five real states. Just have a `status` enum.

Nested resources beyond two levels. `/orgs/{o}/teams/{t}/projects/{p}/issues/{i}` is exposing your join graph. Flatten and filter.

Returning IDs as integers in JSON. JSON numbers are doubles; IDs over 2^53 silently corrupt in JavaScript. Use strings for IDs that cross the wire.

Treating `null` and absent as different in some endpoints and the same in others. Pick one rule per API and document it.

Versioning an API by changing field meanings without renaming. If `total` used to mean pre-tax and now means post-tax, that's a breaking change masquerading as a bug fix. Add a new field; deprecate the old one.

Designing the API around your database schema. The schema changes; the API is forever. Translate at the boundary.
