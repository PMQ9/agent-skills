# MCP Server — Review Guide

Checks for the MCP lens, as **look for → why → fix**. Spec facts verified 2026-09-24
against modelcontextprotocol.io (revisions 2025-11-25 and **2026-07-28**, current),
`schema/2026-07-28/schema.ts`, python-sdk (v2.2.x, v1.30.0), typescript-sdk
(`@modelcontextprotocol/server` 2.1.0, v1.30.1). On a new revision, re-verify §0 and §7.

§0 Revision & SDK · §1 Selection · §2 Schemas · §3 Results & errors · §4 Agent safety ·
§5 Transport · §6 Auth · §7 Revision rules · §8 Evolution · §9 Running it · §10 Grep · §11 False alarms

## §0 Pin the revision and SDK

| Signal | Targets |
|---|---|
| `from mcp.server.fastmcp import FastMCP` | Python SDK v1 (2025-era spec) |
| `from mcp.server.mcpserver import MCPServer` | Python SDK v2 (2026-07-28) |
| `@modelcontextprotocol/sdk` | TS SDK v1 · `@modelcontextprotocol/server` → TS v2 |
| `sessionIdGenerator`, `Mcp-Session-Id` | stateful 2025-era |
| `InputRequiredResult`, `request_state`, `resultType`, `server/discover` | 2026-07-28 |

- v1 is still maintained; don't fault it for missing 2026 features (a migration note is 🔵 at most).
- **Pin vs import:** SDK v2 deliberately raises on `import mcp.server.fastmcp`. FastMCP imports with an
  unpinned/`>=2` `mcp` dependency crash on fresh install → 🔴. Fix: pin `mcp<2` or migrate.

## §1 Tool selection

- **Descriptions**: non-trivial tools need what / when / **when-not** (vs nearest sibling) / error meanings.
  One-liners on side-effecting or ambiguous tools → 🟠.
- **Names**: vague (`run`, `do`), unscoped where servers coexist. Spec (since 2025-11-25): 1–128 chars,
  `[A-Za-z0-9_.-]`, unique per server.
- **Granularity**: `action: str, params: dict` mega-tools discard schema guidance → split per unit of work or
  discriminated `oneOf`. Tools differing by one boolean → merge. >20–30 tools → selection degrades.
- **Hidden side effects**: `get_*`/`list_*` that write, assign, mark read, or consume quota. The model calls
  reads freely and speculatively.
- **Primitive**: flag only when misleading (same data as both tool and resource).

## §2 Input schemas

- Every param described (format, unit, example); enums for closed sets; constraints (min/max/pattern).
- Polymorphic/untyped (`dict`, `Any`, `z.any()`, `z.record`) → the SDK emits exactly that untyped schema;
  the model guesses shapes, code `KeyError`s. Inconsistent keys across branches make it worse.
- Required-ness must match the code. Secrets as params → §4.
- Spec: `inputSchema` root `type: "object"`, JSON Schema 2020-12 default; no-arg tool →
  `{"type":"object","additionalProperties":false}`.

## §3 Results and errors

**Two channels.** Tool execution error = result with `isError: true` (API/business/validation failures —
clients SHOULD show the model, which can self-correct). Protocol error = JSON-RPC `error` (unknown tool,
malformed request) — the model usually never sees it.

- **Failure-as-success**: `return "Error: 404"` / `"failed"` as normal text → no `isError`; frameworks treat it
  as success → 🟠.
- **Useless text**: good errors state what, why, what to try next, and whether retry helps.
- **What the SDK does with a raised exception** (don't claim "crashes the server"):
  - Python v1 FastMCP: every exception → `isError` with `"Error executing tool <name>: <exception text>"` —
    **raw text leaks** (URLs, `KeyError: 'x'`, SQL).
  - Python v2 MCPServer: `ToolError` and arg-validation text reach the model; **any other exception → generic
    `"Error executing tool <name>"`** (traceback server-side only) → safe but unrecoverable. Expected failures
    (not found, wrong state, invalid PIN) must raise `ToolError("…guidance…")`. (v2 returns `isError` for
    unknown tools — SDK divergence, not the author's bug.)
  - TS v1/v2: thrown errors → `isError` with **`error.message` verbatim** → write messages for the model, keep
    internals out.
- **Unbounded output**: results land in the context window. Every-row lists/exports, large inline blobs
  (images, base64 receipts, file bodies) → `limit` + opaque cursor/`next_cursor`, a hard cap, explicit
  truncation notice, or `resource_link` handles. 🟠; 🔴 when the normal case overflows. Removing pagination a
  previous version had is also a breaking change.
- **Structured output**: `structuredContent` MUST match a declared `outputSchema`; also send a text copy for
  older clients. Missing schema on structured data → 🟡.
- **Untrusted content** (ticket bodies, emails, web pages) in results is an injection vector — note; the real
  defense is §4 scope.

## §4 Agent safety

Assume an attacker's text can make the agent call any tool with any arguments.

- **Annotations** (hints clients use to skip confirmation). Defaults: `readOnlyHint` false, `destructiveHint`
  true, `idempotentHint` false, `openWorldHint` true. **Wrong** hints are the defect: `readOnlyHint` on a
  writer → auto-approved writes; `idempotentHint`/`destructiveHint:false` on money movement or creation →
  retries and no confirmation. 🟠; 🔴 on money/deletion. Missing hints are 🟡 (defaults are conservative).
- **Destructive/money tools unguarded**: no confirmation (two-phase or host-side), no dry-run, no soft delete,
  **no idempotency key** (retry → duplicate payout/refund). A confirm argument the model fills itself is not a
  safeguard.
- **Scope escape**: `os.path.join(root, p)` returns `p` if absolute; `../` walks out → resolve + verify inside
  root, reject symlinks. Same for IDs interpolated into URL paths, URLs (SSRF), table names, shell args.
  (Roots deprecated in 2026-07-28 — enforce server-side.)
- **Arbitrary execution** (`run_sql`, shell, `http_request`, `eval`): 🔴 on production data reachable by
  untrusted content unless sandboxed (read-only role, allowlist, row caps, tenant scope). "Read query" in the
  description enforces nothing.
- **Secrets through the model**: `api_key`/`token` params, docs telling users to paste keys → transcripts,
  logs, exfiltration → 🔴. **Form-mode elicitation MUST NOT request passwords, API keys, access tokens, or
  payment credentials — those MUST use URL-mode elicitation** (spec wording; a PIN or OTP is a password in
  all but name — say so as your inference, don't quote it as spec text) (the URL must not carry PII/credentials and the
  server must verify the user who opens it).
- **Tenant/principal scoping**: tools acting on any ID without checking it belongs to the verified caller;
  actions performed as an identity taken from arguments or state instead of the verified token → rate at true
  severity (usually 🔴 for money).
- Baseline (spec): validate inputs, enforce access control, rate-limit, sanitize outputs.

## §5 Transport

- **stdio**: stdout is the protocol channel. Any `print`/`console.log`/banner/library stdout write corrupts
  the stream (often intermittently) → 🔴. Log to stderr. Confirm transport before flagging.
- **Streamable HTTP**: servers MUST validate `Origin` (403 if present and invalid; DNS-rebinding defense).
  `cors({origin:"*"})` with no Origin check → 🟠/🔴. Local servers SHOULD bind 127.0.0.1 (and prefer stdio).
  - Python SDK: Host/Origin protection auto-enables **only** for host `127.0.0.1`/`localhost`/`::1` with no
    `transport_security` → **`host="0.0.0.0"` (or `transport_security=None` off-localhost) silently disables
    it**; pass explicit `TransportSecuritySettings`.
  - TS v2 `createMcpExpressApp()` defaults to 127.0.0.1 with protection; hand-rolled Express has none.
- Deprecated HTTP+SSE (`/sse` + `/messages`) in new code → 🟡.

## §6 Authorization (remote)

- **Audience**: server MUST validate tokens were issued for it (RFC 8707). `jwt.verify` without `audience`
  accepts every token your IdP issues for any app → 🔴.
- **No token passthrough**: MUST NOT forward the client's token upstream or accept tokens not issued for it
  (confused deputy, broken audit, audience bypass) → 🔴. Use the server's own upstream credentials.
- **Discovery**: 401 with `WWW-Authenticate: Bearer resource_metadata="…"` and/or
  `/.well-known/oauth-protected-resource` (RFC 9728, ≥1 authorization server). A bare 401 can't be connected
  to by spec clients → 🟠 for a remote connector.
- 401 invalid/expired; 403 `insufficient_scope`. Scopes ≠ authorization checks. No tokens in query strings.
- Proxies with a static upstream client ID MUST get per-client consent (exact `redirect_uri`, single-use
  `state`). DCR deprecated in 2026-07-28 (prefer Client ID Metadata Documents) → new DCR code 🟡.

## §7 Revision-specific rules

**2025-era (Python v1, TS v1):**
- Sessions MUST NOT be used for authentication — trusting a known `Mcp-Session-Id` without re-auth → 🔴.
- Session IDs MUST be non-deterministic (`${user}-${Date.now()}` is guessable), SHOULD bind to the user.
- In-memory session maps: no expiry, break behind LBs without stickiness (scaling → DevOps).

**2026-07-28 (Python v2, TS v2):**
- Stateless: no `initialize`, no sessions; `_meta` per request; `server/discover` required; results carry
  `resultType`. `tools/list` MUST NOT vary per connection (MAY vary by authorization).
- **State handles and `requestState` are not authentication.** Verify every request; bind state to the
  principal from the verified token; expire it.
- **`requestState` is attacker-controlled**: if it influences authz or business logic it MUST be
  integrity-protected (HMAC/AEAD) and SHOULD bind user, expiry, request digest.
  - Python SDK v2 seals it by default (`RequestStateBoundary`, AES-GCM) — don't report sealed state as
    plaintext. The defects are in configuration: default key is **process-local** (`ephemeral`) → state
    minted on one replica fails on another (multi-replica deployments need shared `keys=[…]`); a
    **hard-coded fallback key** (`os.environ.get(..., "dev-key")`) makes state forgeable wherever the env var
    is missing; **`bind_principal=None`** unbinds state from the caller (replay across users).
  - Handlers that trust identities or amounts *read back from* `request_state` instead of the verified caller
    → 🔴.
- **Headers vs body**: `MCP-Protocol-Version`, `Mcp-Method`, `Mcp-Name` required and MUST match the body.
  `x-mcp-header` params must not be secrets/PII (headers get logged).
- **Cache hints**: list results carry `ttlMs` + `cacheScope`. Lists that vary by user/role/authorization MUST be
  `"private"` — `"public"` lets caches serve one principal's tool list to another → 🟠. Long TTLs delay
  revocation of role changes.
- Deprecated: Roots, Sampling, Logging (`notifications/message` only if the request set `logLevel`), DCR,
  HTTP+SSE → new adoption 🟡.
- Tasks (`io.modelcontextprotocol/tasks` extension): only if the client declared it; unguessable IDs; authorize
  every `tasks/*` call.

## §8 Evolution

Breaking: removing/renaming tools or params, newly required params, narrowed values, changed semantics or
output structure callers chain on, removed pagination. Fix: new name alongside old, `DEPRECATED: use X` in the
old description, remove later. Safe: new tools, optional params, output fields. Dynamic surfaces announce
`list_changed` (2026-07-28: only on an opted-in `subscriptions/listen` stream).

## §9 Running it (only when cheap)

```bash
npx @modelcontextprotocol/inspector --cli <server command> --method tools/list
npx @modelcontextprotocol/inspector --cli <server command> --method tools/call --tool-name <t> --tool-arg k=v
```
Check `--help` for current flags. Needs secrets, a VPN, stubs, or installs → skip, `Contract check: static`.

## §10 Grep

```bash
D="gh pr diff <N>"
$D | grep -nE '^\+.*\b(print\(|console\.log\(|sys\.stdout|process\.stdout\.write)'        # stdio pollution
$D | grep -nE '^\+.*(api_key|token|password|secret|pin)\b'                                # secrets
$D | grep -nE 'Hint|ToolAnnotations|cache_hints|CacheHint|scope='                         # hints to verify
$D | grep -nE ':\s*dict\b|:\s*Any\b|z\.any\(|z\.record\('                                 # untyped params
$D | grep -nE 'return\s+f?["'\'']Error|raise (ValueError|RuntimeError|Exception|PermissionError)'
$D | grep -nE 'limit\s*[:=]\s*[0-9]{3,}|per_page|allFor|export_|Image\(|base64'           # output size
$D | grep -nE 'os\.path\.join|path\.join|db\.raw|execute\(|subprocess|eval\('             # scope/exec
$D | grep -nE 'jwt\.|audience|Bearer|WWW-Authenticate|oauth-protected-resource'           # auth
$D | grep -nE 'sessionIdGenerator|Mcp-Session-Id|cors\(|Origin|0\.0\.0\.0|transport_security|request_state|bind_principal|RequestStateSecurity|elicit'
```

## §11 False alarms

- "Exception crashes the server" — SDKs convert to `isError`; the finding is the text the model gets.
- stdout writes on an HTTP-only server don't break the protocol.
- Sealed `requestState` (Python v2 default) is not plaintext — check key config and principal binding instead.
- v1 SDK is not a defect. Missing annotations aren't lies. Long descriptions are good.
- Arbitrary-exec tools on an explicitly sandboxed dev server: flag missing sandbox evidence, not the tool.
