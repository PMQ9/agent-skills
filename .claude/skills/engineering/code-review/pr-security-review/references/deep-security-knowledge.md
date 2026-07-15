# Security PR Review — Deep Reference Notes

Distilled from a broader security skill set (application-security, authn-authz, secrets-management,
pii-handling, audit-logging, threat-modeling). These go **beyond** the basics in
`security-checklist.md` — every item is something to grep for or verify in a diff. Read the
section that matches what the PR touches.

## 1. Authentication & session (deeper)

**Password/credential handling**
- Only acceptable hash for greenfield is **Argon2id** via library defaults (`argon2-cffi`,
  `node-argon2`, `Argon2BytesGenerator`) — flag hand-tuned parameters. **Bcrypt** only for an
  existing store with rehash-on-login, cost ≥ 12. **PBKDF2** only under FIPS/hardware
  constraint. Reject SHA/MD5/unsalted/SHA-1.
- Min length **12+** (NIST SP 800-63B: length > complexity). Flag missing breach-corpus check
  (HIBP k-anonymity).
- Password reset tokens: single-use, ≤30 min, sent only to a verified email, **rotate session
  on reset**, notify user out-of-band. Flag any reset flow missing any of these.

**JWT/session pitfalls**
- Reject `alg: none` — the verifier must pin a specific algorithm, not "whatever the token says."
- **Algorithm confusion**: if a verifier accepts both RS256 and HS256, an attacker uses your
  public key as the HMAC secret. Pin the algorithm.
- Prefer **EdDSA or ES256** for new systems. Validate `exp`, `nbf`, `iss`, `aud` every time.
  Access-token TTL **5–15 min**; flag bearer tokens >24h.
- No sensitive data in the JWT body (base64, not encryption).
- Server-side sessions are preferred (revocable). If JWT is used: short TTL, refresh-token
  rotation, server-side denylist, key rotation, `kid` header.
- **Rotate the session ID on privilege change** (login, MFA step-up, role assumption) —
  prevents fixation. Logout must destroy server-side, not just clear the cookie. Session ID
  ≥128 bits from a CSPRNG.

**Token storage** — `localStorage` is XSS-readable; flag auth tokens there, prefer `HttpOnly`
cookies.

**OAuth/OIDC**
- Default to **OAuth 2.1**: PKCE (`code_challenge_method=S256`) required for **all** clients;
  implicit and ROPC removed — flag either.
- Verify the ID token: signature, issuer, audience, expiration, nonce. Use `state` (CSRF on
  redirect) + `nonce` (binds the ID token to the session).
- **Redirect URI: exact-match allowlist on the server** — no wildcards, no path-prefix that
  allows `/callback/../evil`.
- Never hand-parse SAML XML (signature-wrapping attacks); use maintained libraries.

**MFA / step-up** — require MFA on the **action** (admin, bulk data access, export), not just at
login. Preference: passkeys/FIDO2 > TOTP > SMS.

**Service-to-service** — never "we're both in the VPC, so it's fine." mTLS > OIDC/client-
credentials > static API keys (last resort: long random, in a manager, rotated, scoped).

## 2. Authorization (deeper)

- **Return 404, not 403**, when the existence of a resource is itself sensitive (403 confirms
  it exists).
- The authz decision must use **the actual resource object**, not just the user's role. Enforce
  at **both** the route handler and the data layer (Postgres RLS, or query helpers that take
  the actor) so a missing route check still fails closed.
- Centralize into a single `can(user, action, resource)` policy module; framework enforcement
  must **fail closed** on routes that didn't declare a requirement. Engines: OPA, Cedar, Casbin.

**Concrete bug patterns to grep**
- **Mass assignment**: `user.update(**request.json)` binding `{"role":"admin"}` / `owner_id` /
  `tenant_id` — require an explicit field allowlist, not a denylist.
- **Verb tampering**: auth on `GET`/`POST` but not `PUT`/`PATCH`/`DELETE` on the same path.
- **Forgotten endpoints**: `/api/v1/...` gated, `/api/v2/...` ships ungated.
- **JWT with stale claims**: user demoted, token still says admin → needs short TTL +
  invalidation.
- **TOCTOU**: permission checked, then resource re-fetched and changed — check against the same
  data you act on.
- **Second-channel bypass**: UI hides the button but an undocumented API endpoint doesn't check.
- "Admin page is internal-only" is **not** authz. Never trust `X-Forwarded-For` or client
  headers for trust decisions.

**Multi-tenancy** — every query needs the tenant filter, enforced at the framework/DB level. A
single missing `WHERE org_id = ?` is a cross-tenant leak.

**Impersonation / "view as"** — privileged roles only (never self); log both real + impersonated
actor; bound by the target's permissions; time-limited.

## 3. Secrets management (deeper)

**Two failure modes drive everything**: the secret leaks, and it can't be rotated when it does.

**Detection to require in the diff/pipeline** — pre-commit + CI `gitleaks`/`trufflehog`;
provider push protection. **Git history**: a committed secret is compromised the instant it's
pushed. Order is **rotate first, then redact** with `git filter-repo` — redaction alone is never
sufficient.

**Leakage vectors to flag**
- Secrets in **image build args / Dockerfile `ENV`** — baked into inspectable layers forever;
  require BuildKit `--secret` or runtime fetch.
- **CI logs**: masking only covers registered secret variables — **custom-derived values (e.g.
  base64 of a secret) are NOT masked**. Flag `echo $TOKEN`-style debugging.
- `.env` gitignored is local-dev only; `.env.example` holds placeholders, never real values.
- Stack traces with bound query parameters leak passwords — structured loggers must redact
  known-secret fields.
- Single `prod-secrets` blob → every service reads every secret; require per-service split with
  scoped IAM/Vault policies.

**Prefer identity over secrets** — cloud workload identity (EKS Pod Identity/IRSA, GKE Workload
Identity Federation, AKS Workload Identity) and **cloud DB IAM auth** (RDS
`rds:GenerateDBAuthToken` → 15-min token as the DB password) eliminate stored secrets entirely.
Managers: Vault/OpenBao, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault.

**Rotation** needs cadence + mechanism + an **overlap window** (old and new both valid until all
consumers refresh — hard cutovers cause outages). Rotate immediately on departure, exposure, or
audit failure.

## 4. PII & data protection (deeper)

**What counts** — **quasi-identifiers re-identify**: DOB + ZIP + gender + cohort usually single
out one person. Treat anything resembling PII as PII. Regimes to recognize and escalate:
**FERPA** (education records), **GLBA/FTC Safeguards** (financial-aid data), **HIPAA** (medical),
**PCI DSS v4.0.1** (cards), **GDPR** (EU subjects), plus US state laws. Route novel flows to the
privacy office.

**Data minimization (flag at field-add time)** — need test, granularity test (`≥18` not full
DOB; ZIP not full address), source-of-truth test (fetch on demand, don't replicate), retention
test (set a TTL at write time).

**Encryption at rest** — sensitive fields (SSN, DOB, account #) need **field-level encryption**
with KMS-held keys. Use authenticated encryption (**AES-GCM, ChaCha20-Poly1305**); flag raw
**AES-CBC without integrity**. DB credentials and KMS key access should be **different IAM
identities**. Store `ssn_ciphertext` + `ssn_last_four` for display/search.

**Hashing/tokenization** — plain SHA-256 of an SSN is **not** protection (rainbow tables are
trivial). Require **HMAC with a KMS-held secret key** (security comes from the secret key, not a
salt — salts are non-secret). Use opaque internal UUID/ULID as the cross-system join key, never
raw SSN/gov-ID.

**In transit** — TLS 1.2 min / 1.3 preferred; no SSLv3/TLS 1.0–1.1/RC4. HSTS ≥ 1yr +
`includeSubDomains`. Internal service-to-service is **not** exempt. Email is not a secure
channel — send a link, not the data.

**No PII in** — URLs (leak to history/access logs/referer/CDN), client-side storage, backups
restored to lower-security envs, or dev/staging (use synthetic/masked data). Derived data
(aggregations) re-identify via **small cells** — suppress per policy.

**Erasure traps** — vector stores: **tag every embedding with the source subject id** so
delete-by-tag scrubs derivatives. Fine-tuning on raw PII is generally irrecoverable — don't.
**LLM/AI flows**: sending user data to a model provider is a disclosure; "no-training enterprise
tier" is not by itself sufficient — even prompt context counts.

**SDK-level scrubbing** — configure Sentry/Bugsnag/Rollbar scrubbing; a top-level-only scrubber
leaks nested PII (`{"user": {"ssn": ...}}`) — require a recursive scrubber over sensitive keys.
Redact in `__repr__`/`toString`.

## 5. Audit logging (deeper)

**Two separate pipes** — audit logs (structured, append-only, retained, tamper-evident) vs
debug logs (verbose, ephemeral), with separate retention and access controls.

**Required audit fields** — `event_id` (UUID), `event_time` (ISO-8601+tz, server-generated),
`event_type` (enumerated), `actor_id`/`actor_type` (incl. impersonator+target), `actor_ip`,
`request_id`, `resource_type`/`resource_id`, `action`, `outcome`, `reason`, `metadata` (never
the protected payload).

**Must log** — auth success **and** failure (with reason category), logout, password/MFA
changes, session lifecycle; **every authz decision — allow AND deny** (denies are the security
signal); reads of sensitive records, all writes, bulk ops (log **query + count, not rows**);
admin actions and impersonation start/end; outbound disclosures; API-key lifecycle; rate-limit
triggers, WAF blocks, CSP violation reports.

**Must NEVER log** — passwords (even the hash, even on failed login), full tokens/secrets/API
keys/MFA codes (log a fingerprint), session IDs (log a derived correlation id), full SSNs (last
4 only), the protected payload, free-text fields that may hold PII, Authorization
headers/cookies/full bodies on sensitive endpoints, PII in URLs. Rule: if you wouldn't put it on
a billboard, don't log it.

**Log the fact, not the value** — "User changed email" with redacted before/after, NOT the
actual addresses. **Log injection**: structured JSON, not `f"User {email} did {action}"`; strip
`\r\n` from anything user-controlled written to logs.

**Tamper-evidence (escalating)** — (1) append-only by convention (DB role with only `INSERT`);
(2) a separate sink the app's credentials can't delete (different IAM principal); (3) WORM (S3
Object Lock); (4) hash chaining; (5) external anchoring. Compliance disclosure logs need at
least level 2 — the app that discloses must not be able to delete the record of it. **Never
sample the audit stream.**

## 6. Application security (deeper)

**SSRF depth** — resolve DNS yourself and **validate the resolved IP** before connecting: reject
loopback `127.0.0.0/8`/`::1`, link-local `169.254.0.0/16`+`fe80::/10` (**the cloud metadata
range** — `http://169.254.169.254/latest/meta-data/iam/security-credentials/`), private
`10/8`/`172.16/12`/`192.168/16`/`fc00::/7`, `0.0.0.0/8`. **Re-validate on every redirect.** Block
non-HTTP schemes (`file://`, `gopher://`, `dict://`). **Require IMDSv2** at the cloud level.
Beware DNS-rebinding TOCTOU — pin the resolved IP or route egress through an allowlisting proxy.

**CSP** — nonce-based, **not `'unsafe-inline'`**; `'strict-dynamic'` for nonced scripts; no
`'unsafe-eval'`. `frame-ancestors 'none'` (clickjacking, replaces `X-Frame-Options`),
`object-src 'none'`, `base-uri 'self'`, `form-action 'self'`. Roll out with
`Content-Security-Policy-Report-Only` first; treat any `'unsafe-inline'`/`'unsafe-eval'` as a
tracked temporary crutch.

**Other headers (every response)** — `Strict-Transport-Security: max-age=31536000;
includeSubDomains; preload`, `X-Content-Type-Options: nosniff`, `Referrer-Policy:
strict-origin-when-cross-origin`, `Permissions-Policy` disabling unused features,
`Cross-Origin-Opener-Policy: same-origin`, `Cross-Origin-Resource-Policy: same-origin`.
`X-XSS-Protection` is deprecated — omit or set `0`.

**CSRF depth** — `SameSite=Lax` blocks most CSRF but not state-changing GETs (which shouldn't
exist). Layers: synchronizer token, or **double-submit cookie** when stateless; Origin/Referer
allowlist (not alone); JSON-only APIs requiring `Content-Type: application/json` + strict CORS.
GraphQL/JSON APIs are **not** immune — confirm the framework enforces it on the routes.

**Cookie flags** — `Secure`, `HttpOnly`, `SameSite`, and the **`__Host-` prefix** for session
cookies (guarantees `Secure`, `Path=/`, no `Domain`).

**XSS bypass sinks to grep** — `dangerouslySetInnerHTML`, `v-html`, `[innerHTML]`, Handlebars
`{{{ }}}`, Jinja `|safe`, `.innerHTML`, `document.write`, `eval`, `setTimeout(string,...)`,
`href="${userInput}"` (`javascript:` URLs). **DOM-based XSS** never hits the server — audit
client code reading `location.hash`/`document.referrer`/`postMessage`/`localStorage` into
dangerous sinks. Sanitize with DOMPurify / bleach / sanitize-html; escape per output context.

**File upload** — validate type by **content sniffing** (`python-magic`/`file`), not extension;
**re-encode images** (Pillow re-save) to strip embedded scripts + EXIF GPS; generate the storage
filename (random ULID + validated ext); store outside webroot; serve via an authed handler with
`Content-Disposition: attachment` + `nosniff`; limit size at the proxy.

**Open redirect** — reject `//evil.com` (protocol-relative), `\evil.com`, non-`http(s)` schemes
— use the URL parser, not regex; allowlist hosts.

**Injection extras** — SQL: `LIKE` (parameterize the value, not the wildcards), dynamic
table/column names (allowlist — can't be parameterized), `IN (...)` (array binding, not concat).
MongoDB: never accept user-supplied operators (`$ne`, `$gt`); allowlist field names + types.
**CRLF/log injection**: strip `\r\n` from user input written to headers/logs.

**Rate limiting** — edge (LB/WAF) **and** app for login/reset/search; distinguish per-IP from
per-account; lockout/back-off on failed auth **without enabling user enumeration** ("account
locked" reveals existence).

**Error handling** — no stack traces/query text/internal IDs in responses (generic 500 + request
id); non-enumerating auth errors ("Email or password incorrect"); security middleware **fails
closed** (policy engine unreachable → deny).

**Supply chain** — lockfiles in source control; SCA in CI (`npm audit`, `pip-audit`, Dependabot,
Trivy, OSV-Scanner) as build-breakers on high/critical; **review the lockfile diff** for new
low-reputation/ownership-changed packages; **SRI** (`integrity="sha384-..."`) for CDN scripts;
no `curl | sh` in build scripts.

## 7. Threat-modeling quick pass for a PR

For a small diff, spend one sentence: **"What's the worst input that reaches this code, and from
where?"** Do a fuller pass when the diff adds a trust boundary (new integration, new input
source, new tenant model) or touches money/PII/auth/secrets.

**Trust-boundary question** — a boundary is any line data crosses from lower to higher trust;
attacks concentrate there. For each boundary the diff touches, ask: *what is the most-trusted
thing reachable from the least-trusted side, and what stops the jump?* Common boundaries: network
edge; service↔service and tenant↔tenant; process→OS (input → shell/path/SQL/deserializer);
**untrusted content → LLM context window**; client→server (client checks are UX, not security).

**STRIDE-lite over the changed flows**

| Threat | Ask of the diff | Control to verify |
|---|---|---|
| **S**poofing | Can someone impersonate another user/service? | strong auth, mTLS, signed tokens |
| **T**ampering | Can data be modified in transit/at rest? | signing, integrity checks, write authz |
| **R**epudiation | Can an action be denied with no trace? | tamper-evident audit log |
| **I**nfo disclosure | Can data leak to someone unauthorized? | encryption, authz, minimization |
| **D**oS | Can this be exhausted/crashed? | rate limits, quotas, timeouts, backpressure |
| **E**levation | Can someone do more than allowed? | least privilege, authz at every step |

**Abuse case** — invert each user story the PR implements ("as an attacker I reset *someone
else's* password / read another tenant's invoices"). This surfaces missing authz and rate
limiting almost for free. Rank findings by likelihood × impact — a trivially exploitable bug on
an internet-facing unauthenticated endpoint touching money/PII is where you start.
