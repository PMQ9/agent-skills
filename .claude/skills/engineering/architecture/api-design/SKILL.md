---
name: api-design
description: Use this skill whenever designing, reviewing, or implementing an HTTP API — REST, RPC, GraphQL, gRPC, or webhooks. Trigger on any request involving endpoint design, resource modeling, status codes, pagination, versioning, error responses, authentication, idempotency, rate limiting, OpenAPI specs, SDK generation, API contracts, or backwards compatibility. Also trigger when reviewing an existing API surface for inconsistencies or breaking changes, or when a developer is choosing between REST/GraphQL/gRPC for a new service.
---

# API Design

Designing an API is designing a contract that other people — including future you — will be stuck with. The cost of a bad decision compounds with every consumer that integrates. Most "API style" arguments are bikeshedding; the decisions that actually matter are: resource model, error semantics, evolution strategy, and auth.

## Pick the style first, and pick honestly

Default to **REST/JSON over HTTP** unless you have a concrete reason not to. It's the boring, interoperable choice and almost every tool, proxy, and developer expects it.

Use **GraphQL** when you have many clients (especially mobile) with widely different data needs against the same domain, and you control both ends. The cost is real: N+1 query problems, harder caching, harder rate limiting, more complex auth (per-field). Don't pick it because it's trendy.

Use **gRPC / Protobuf** for internal service-to-service traffic where you control both ends, want strong typing, streaming, and care about latency/throughput. Don't expose it as a public-facing API for browsers without a gateway.

Use **webhooks** when *you* need to push events to consumers. Always include retries, signing, and an idempotency key — see the webhooks section below.

Use **JSON-RPC** or a plain RPC-over-HTTP style when your operations are genuinely action-oriented and don't fit a resource model. Don't twist verbs like `cancelOrder` into `POST /orders/{id}/cancellations` unless that resource actually has meaning.

## REST: resource modeling

Model **nouns**, not verbs. The HTTP method is the verb. URL paths name resources and collections.

```
GET    /orders              # list orders
POST   /orders              # create an order
GET    /orders/{id}         # fetch one
PATCH  /orders/{id}         # partial update
DELETE /orders/{id}         # delete
GET    /orders/{id}/items   # sub-collection
```

Use plural collection names consistently. Use kebab-case in paths (`/shipping-addresses`), not snake_case or camelCase. Reserve query strings for filtering, sorting, pagination, and field selection — not for identifying the resource.

When an action genuinely doesn't fit CRUD (state transitions, RPC-shaped operations), it's fine to model it as a sub-resource representing the action: `POST /orders/{id}/cancellations`, `POST /invoices/{id}/payments`. Returning the created action resource is more useful than returning nothing.

## HTTP methods and status codes

Use methods according to their semantics, not by reflex:

- `GET` — safe, idempotent, cacheable. Never causes side effects.
- `POST` — non-idempotent create or action.
- `PUT` — idempotent full replacement. Caller supplies the complete representation.
- `PATCH` — partial update. Use JSON Merge Patch (RFC 7396) for simple cases or JSON Patch (RFC 6902) when you need explicit add/remove/test ops.
- `DELETE` — idempotent removal. Returning 204 on a re-delete is acceptable and arguably correct.

Status codes should distinguish three concerns: who's at fault, what state the request is in, and what the client should do.

| Code | Use it for |
|---|---|
| 200 | Success with body |
| 201 | Created, with `Location` header pointing to the new resource |
| 202 | Accepted, work is async — return a status URL |
| 204 | Success, no body (e.g., DELETE) |
| 301/308 | Permanent redirect (308 preserves method) |
| 400 | Malformed request the client can fix by changing input |
| 401 | Not authenticated (missing/invalid credentials) |
| 403 | Authenticated but not authorized |
| 404 | Resource doesn't exist (or shouldn't be exposed) |
| 409 | Conflict with current state (e.g., version mismatch, duplicate) |
| 410 | Gone — was here, deliberately removed |
| 412 | Precondition failed — for `If-Match` / `If-Unmodified-Since` |
| 415 | Unsupported `Content-Type` |
| 422 | Semantically invalid (validation errors). Optional; many APIs use 400. |
| 429 | Rate limited. Always include `Retry-After`. |
| 500 | Server bug |
| 502/503/504 | Upstream / temporarily down / timeout |

Don't invent codes. Don't return 200 with `"success": false` — that's the cardinal sin of REST. Clients, proxies, and monitoring all key off the status code.

## Error response shape

Standardize errors. **RFC 9457** (`application/problem+json`, obsoletes RFC 7807) is the right default:

```json
{
  "type": "https://api.example.com/errors/insufficient-funds",
  "title": "Insufficient funds",
  "status": 422,
  "detail": "Account balance 50.00 is below the requested withdrawal of 100.00.",
  "instance": "/accounts/abc/withdrawals/xyz",
  "code": "insufficient_funds",
  "errors": [
    { "field": "amount", "code": "exceeds_balance", "message": "..." }
  ]
}
```

Always include a stable, machine-readable `code`. Humans read `title` and `detail`; programs branch on `code`. Don't change `code` values once published — that's a breaking change.

## Versioning

Pick one strategy and stick to it:

- **URL path versioning** (`/v1/orders`) — simplest, most visible, most cache-friendly, most common. Default to this.
- **Header versioning** (`Accept: application/vnd.example.v2+json`) — cleaner URLs but invisible in logs and harder for casual clients.
- **Date-based versioning** (Stripe's model: `Stripe-Version: 2024-09-30`) — every breaking change pinned to a release date; clients opt in by setting their version header. Strong choice for APIs with many small breaking changes over time.
- **Query param versioning** — avoid; breaks caching and convention.

Prefer to **not version at all** by being additive. Adding optional fields, new endpoints, new enum values *should* be safe — but only if you've told clients up front that you'll do this. Bake "tolerant reader" expectations into your docs from day one.

A new major version should be the last resort. When you do bump, run both versions in parallel and publish a deprecation timeline measured in months or years, not weeks. Use the `Deprecation` header (RFC 9745) and `Sunset` header (RFC 8594) on every response from a deprecated version so clients can detect it programmatically.

## What's a breaking change?

Treat all of these as breaking and bump the version:

- Removing or renaming a field, endpoint, query param, header, or status code
- Changing a field's type, format, or cardinality
- Tightening validation (newly rejecting input that used to work)
- Changing default behavior (default sort, default pagination size)
- Changing auth requirements
- Adding a required request field

These are *not* breaking, assuming clients are tolerant readers:

- Adding a new optional field to a response
- Adding a new endpoint
- Adding a new optional query param
- Adding a new enum value (but document this up front — many client libraries blow up on unknown enums)

## Pagination

Pick offset or cursor based on the data:

- **Offset/limit** (`?page=3&page_size=50`) — simple, allows random access, fine for small slowly-changing collections. Breaks down on large or rapidly-changing collections (you'll skip and double-count rows as data shifts).
- **Cursor / keyset** (`?cursor=opaque_token&limit=50`) — stable under writes, scales to huge collections, but no random access. Default to this for anything user-facing or large.

Always return pagination metadata in a predictable place. Two common shapes:

```json
{
  "data": [ ... ],
  "page": { "next_cursor": "abc...", "has_more": true }
}
```

Or use `Link` headers (RFC 8288, obsoletes RFC 5988) — interoperable but harder for non-browser clients to consume.

Cap page size on the server. If the client asks for `limit=10000`, return 100 and document the cap.

## Filtering, sorting, sparse fields

- **Filtering**: keep it flat where you can. `?status=open&created_after=2024-01-01`. Avoid baking a query DSL into URLs unless you really need it; once you do, you've reinvented SQL badly.
- **Sorting**: `?sort=-created_at,name` — minus prefix for descending. One param, comma-separated.
- **Field selection**: `?fields=id,name,total` to let clients reduce payload size. Useful for mobile.
- **Embedding**: `?expand=customer,items` to inline related resources. Be careful — once you support arbitrary expansion you'll fight N+1 forever. Limit which paths can be expanded.

## Idempotency

Any non-idempotent endpoint that takes money, sends messages, or otherwise has real-world consequences needs idempotency keys.

The pattern: client generates a key (UUID is fine), sends it in `Idempotency-Key` header. Server stores `(key, request_hash, response)` for a TTL (24h is typical). On retry with the same key:

- Same request hash → return the stored response.
- Different request hash → 422 with `code: "idempotency_key_reused"`.

Stripe's implementation is the canonical reference; copy it. The IETF `Idempotency-Key` HTTP header draft (`draft-ietf-httpapi-idempotency-key-header`) is the standardization vehicle if you want a published spec to point at. This is non-negotiable for payments, transfers, message sends, anything externally observable.

## Authentication and authorization

Default to **OAuth 2.1** (consolidates OAuth 2.0 + best-current-practice; PKCE required for *all* clients including confidential; implicit flow and ROPC removed). See `authn-authz` for the full token, session, and JWT story; this section is the API-contract slice.

For server-to-server: **OAuth 2.1 client credentials** or **mTLS**. Static API keys are acceptable for low-stakes integrations — rotate them and scope them.

For user-acting clients: **OAuth 2.1 authorization code with PKCE**. Don't invent your own. Consider **PAR (RFC 9126)** for sensitive flows and **DPoP (RFC 9449)** for sender-constrained tokens.

For first-party browser apps with a session: **HttpOnly, Secure, SameSite cookies** with the `__Host-` prefix, plus CSRF protection (SameSite=Lax handles top-level POST; double-submit-token still recommended for non-cookie auth on cross-origin requests).

JWTs are not magical. They're a way to pass signed claims; they aren't sessions. Keep lifetimes short (minutes) and pair with refresh tokens. Validate signature, `iss`, `aud`, `exp`, `nbf`, and reject `alg: none` on every request. Prefer EdDSA or ES256 over RS256 for new systems. Don't put PII in them — they're often logged.

Authorization is separate from authentication. Don't conflate "they have a token" with "they can do this." Centralize policy (e.g., an authorization service or library), keep checks at the edge of every endpoint, and prefer attribute-based checks over hardcoded role checks.

## Rate limiting

Return `429 Too Many Requests` with a `Retry-After` header and the structured-fields `RateLimit` header (the IETF `draft-ietf-httpapi-ratelimit-headers` draft converged on RFC 9651 structured fields):

```
Retry-After: 30
RateLimit: "default"; limit=100; remaining=0; reset=30
```

The flat `RateLimit-Limit` / `RateLimit-Remaining` / `RateLimit-Reset` shape is the *older* draft and the legacy `X-RateLimit-*` family is still widely deployed; either is acceptable for compatibility, but new APIs should emit the structured-fields form.

Limit per credential, not per IP — IPs share. Tiered limits (per-second burst, per-minute sustained) are friendlier than a single hard wall. Document the limits. See `resilience-patterns` for the underlying mechanics (token bucket vs leaky bucket, load shedding).

## Long-running operations

Don't hold an HTTP connection open for minutes. Pattern:

1. `POST /exports` → `202 Accepted` with `Location: /exports/{id}` and a body containing `{ "id": "...", "status": "pending" }`.
2. Client polls `GET /exports/{id}` → `pending` → `running` → `succeeded` (with a download URL) or `failed` (with an error).
3. Optionally support webhooks/SSE/WebSocket for push notification.

The job resource is a real resource. It's queryable, cancellable (`DELETE /exports/{id}`), and survives client disconnects.

## Webhooks (when you're producing events)

- **Sign payloads.** HMAC-SHA256 over the raw request body, with a timestamp to prevent replay. Document exactly how to verify.
- **Retry with exponential backoff** on non-2xx. Cap at ~24h. Surface failures in a UI so consumers can debug.
- **Include an event ID** so consumers can dedupe. Webhooks are at-least-once.
- **Versioned event payloads.** Don't break the schema silently.
- **Don't put secrets in the payload.** Send IDs and let the consumer fetch.

## OpenAPI / contract-first

Write the OpenAPI spec first or alongside the code. Generate clients, server stubs, mock servers, and docs from it. Lint it (Spectral) in CI. The spec becomes the source of truth that prevents drift between docs, server, and SDKs.

Not negotiable for any API with more than one consumer.

## Anti-patterns

- Returning `200 { "error": "..." }`. Use a status code.
- Embedding verbs in URLs (`/getUser`, `/createOrder`) for what is plainly REST.
- Tunneling everything through `POST /api` with an `action` field — this is RPC pretending to be REST. If that's what you want, just be honest and use JSON-RPC or gRPC.
- Mixing snake_case and camelCase in the same response.
- Returning unbounded arrays without pagination.
- Using auto-incrementing integer IDs in public URLs (enumeration, leaks volume). Use UUIDs or ULIDs.
- Different shapes of error responses across endpoints.
- Coupling request and response schemas. The thing you create is rarely identical to the thing you read back.
- Letting the client drive sort/filter against unindexed columns (DOS-by-query).
- Versioning by changing existing endpoints in place.

## Quick checklist before shipping

- [ ] OpenAPI spec exists and is linted in CI
- [ ] Every endpoint has authn + authz
- [ ] All non-idempotent state-changing endpoints accept `Idempotency-Key`
- [ ] Errors follow a single shape with a stable `code`
- [ ] Pagination is enforced server-side with a cap
- [ ] Rate limiting per credential, with documented limits and 429 headers
- [ ] No PII in URLs, query strings, or logs
- [ ] Deprecation policy documented
- [ ] Health check (`/healthz`) and readiness (`/readyz`) endpoints exist and are unauthenticated
- [ ] Request/response payloads have a max size and the server enforces it
