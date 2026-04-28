---
name: authn-authz
description: Implement and review authentication (who you are) and authorization (what you can do) for any feature touching protected data, user accounts, sessions, tokens, API endpoints, or admin functionality. Use whenever the work involves login, logout, SSO, SAML, OIDC, OAuth, JWT, sessions, cookies, password handling, MFA, API keys, service accounts, role checks, permission checks, "can user X do Y," tenancy isolation, impersonation, or anything that gates access to data. Trigger even when the request doesn't say "auth" — phrases like "add an admin page," "let advisors edit this," "expose this endpoint," "service-to-service call," "reset password," or "remember me" all need this skill. Missing or broken authz is the single most common cause of FERPA / data breaches in student systems; treat every endpoint as guilty until proven authorized.
---

# Authentication and Authorization

Two distinct things, often confused:

- **Authentication (authn)** — proves *who* the actor is. The output is an identity (a user, a service, an agent).
- **Authorization (authz)** — decides *what* that identity is allowed to do. The output is a permit/deny on a specific action against a specific resource.

You can have great authn and zero authz and still leak the entire database. Most real-world breaches in academic systems are authz failures — IDOR-style "I logged in as student A and changed the URL to student B's ID" — not authn failures. Plan and review accordingly.

## Authentication

### Use the institutional SSO. Do not roll your own.

For any Vanderbilt-facing application, identity comes from the institutional identity provider (IdP) — typically a SAML or OIDC integration with the central SSO. Your application should be a Service Provider / Relying Party, not an identity store.

Why: the IdP enforces password policy, MFA, account lifecycle (offboarding when someone leaves), suspicious-activity detection, and shared compromise response. Reimplementing any of that in your app means re-implementing all of it, badly.

Practical guidance:

- **OIDC over SAML when offered.** OIDC is simpler, JSON, better library support. Use SAML if that's what's offered.
- **Use a maintained library.** OIDC: `openid-client` (Node), `authlib` (Python), Spring Security (Java). SAML: `python3-saml`, `passport-saml`. Don't parse SAML XML by hand — XML signature wrapping attacks are real and well-documented.
- **Verify the ID token** — signature, issuer, audience, expiration, nonce. Most libraries do this; don't disable checks.
- **PKCE for public clients.** SPA or mobile? Use Authorization Code with PKCE (`code_challenge_method=S256`). Never use Implicit flow.
- **Use the `state` parameter** to prevent CSRF on the redirect, and the `nonce` to bind the ID token to the session.
- **Validate the redirect URI on the server.** Allowlist exact match; no wildcards, no path-prefix matches that allow `/callback/../evil`.

### Session management

Once authn succeeds, you create a session. The session is the durable artifact that gets attacked.

- **Server-side sessions** with a random session ID stored in a cookie, when you can. Easier to revoke, simpler to reason about.
- **JWTs** if you must (microservices with no shared session store) — but you give up easy revocation. Compensate: short access-token TTLs (5–15 min), refresh tokens with rotation, a server-side denylist for emergency revocation, key rotation, `kid` header in tokens.
- **Cookie flags, every time:**
  - `Secure` — HTTPS only.
  - `HttpOnly` — not readable by JS. Defeats most XSS-based session theft.
  - `SameSite=Lax` for normal apps; `Strict` if you don't have third-party flows; `None` only with `Secure` and a real reason.
  - `Path=/` typical; restrict if appropriate.
  - `Domain` — set explicitly; don't leak to subdomains you don't own.
- **Session ID entropy** — use the framework's session generator (≥128 bits of entropy from a CSPRNG). Don't roll your own.
- **Rotate session ID on privilege change** — login, MFA step-up, role assumption. Prevents session fixation.
- **Idle timeout and absolute timeout.** Idle 15–30 min for sensitive apps; absolute 8–12 hours typical. Educational record systems should be on the shorter end.
- **Logout actually destroys the session server-side.** Don't just clear the cookie.

### JWT pitfalls (read this if you're using JWTs)

- **`alg: none` must be rejected.** Configure the verifier to require a specific algorithm, not "whatever the token says."
- **Algorithm confusion attacks** — if your verifier accepts both RS256 and HS256, an attacker can take your public key and use it as the HMAC secret. Pin the algorithm.
- **Don't put sensitive data in the JWT body.** It's base64, not encryption. No grades, no SSNs, no anything you wouldn't want logged.
- **Validate `exp`, `nbf`, `iss`, `aud` every time.**
- **Short TTLs.** Access tokens 5–15 minutes. Long-lived bearer tokens are landmines.
- **Store carefully.** `localStorage` is XSS-readable. Prefer `HttpOnly` cookie for the token; if that's not possible, accept the risk consciously and harden CSP. See `application-security`.

### Password handling (only if you have local accounts)

You probably shouldn't have local accounts. If you do:

- `argon2id` (preferred) or `bcrypt` with cost ≥ 12. Never plain SHA / MD5 / unsalted anything.
- Minimum length 12+. NIST SP 800-63B: length matters more than complexity rules.
- Check against breach corpora (HIBP API has a k-anonymity endpoint).
- Rate-limit and lock out on repeated failures, but with care to avoid enabling user enumeration or DoS via lockout.
- Password reset flows: single-use, time-bound (≤30 min) tokens, sent only to the verified email; rotate session on reset; notify the user out-of-band.
- MFA. Even if the IdP enforces it for primary login, sensitive actions (admin, data export) deserve step-up.

### MFA / step-up authentication

For administrative actions, bulk data access, or anything that would be logged in the FERPA disclosure log, require MFA on that *action*, not just on the original login. The IdP usually supports `acr_values` / `prompt=login` to force re-authentication.

### Service-to-service auth

Microservices and background jobs need identity too. Options:

- **mTLS** — strongest, provides identity via certificate. Requires a PKI you can manage.
- **Signed JWTs / OAuth client credentials** — common, well-tooled. Rotate secrets, scope tokens narrowly.
- **Static API keys** — last resort. If you must: long random values, stored in a secrets manager (not env files in git), rotated on a schedule, logged on use, scoped per consumer.

Never authenticate inter-service traffic with "we're both inside the VPC, so it's fine." Lateral movement is real.

## Authorization

The vast majority of vulnerabilities here boil down to: **the code asked "is the user logged in?" but forgot to ask "is this user allowed to access this specific resource?"**

### The decision is per request, per resource

Authn happens once, at session start. Authz must happen on every protected request, against the specific object the request touches.

```python
# WRONG — the classic IDOR
@app.get("/api/students/{student_id}/transcript")
def get_transcript(student_id, current_user=Depends(require_login)):
    return db.transcripts.get(student_id)  # any logged-in user gets any transcript

# RIGHT
@app.get("/api/students/{student_id}/transcript")
def get_transcript(student_id, current_user=Depends(require_login)):
    if not can_view_transcript(current_user, student_id):
        raise NotFound()  # not 403 — see below
    log_disclosure(current_user, "transcript", student_id, basis="legitimate_educational_interest")
    return db.transcripts.get(student_id)
```

`NotFound` instead of `Forbidden` for resources the user can't see — `Forbidden` confirms the resource exists, which is itself a leak. Use `Forbidden` only when the existence is already known (e.g., the resource is in their org but they lack the specific permission).

### Choose a model and stick with it

- **RBAC (role-based)** — users have roles, roles have permissions. Easy to reason about, hard to express "instructor of *this* course." Good baseline.
- **ABAC (attribute-based)** — decisions use attributes of the user, resource, action, and context. More expressive, more complex. Use when relationships matter ("user advises this student," "user owns this report").
- **ReBAC (relationship-based)** — Zanzibar / OpenFGA style. Best for graph-shaped permissions ("members of group X can read documents in folder Y"). Worth the setup cost when relationships are central.

For a registrar-adjacent system, you almost always need at least RBAC + scoping (ABAC-lite). A "registrar staff" role exists, *and* an "instructor" role scoped to specific course sections, *and* an "advisor" role scoped to specific advisees, *and* "self" — the student themselves.

### Implement authz as a single chokepoint

Scatter authz checks throughout the code and one will be missing. Centralize:

- A policy module that exposes `can(user, action, resource)` and is the only place the rules live.
- Middleware or framework-level enforcement that fails closed on routes that haven't declared their requirement.
- A policy engine (OPA, Cedar, Casbin) when rules get complex enough to deserve their own DSL.

```python
# Policy module
def can_view_grade(user, course_id, student_id):
    if user.id == student_id:
        return True, "self"
    if user.role == "registrar_staff":
        return True, "registrar_legitimate_interest"
    if user.role == "instructor" and is_instructor_of_record(user, course_id):
        return True, "instructor_of_record"
    if user.role == "advisor" and is_advisor_of(user, student_id):
        return True, "academic_advising"
    return False, None
```

The reason string flows into the disclosure log (see `audit-logging` and `ferpa-compliance`).

### Object-level checks at the data layer

In addition to the route-level check, scope queries at the data layer so a missing route check still fails closed.

```sql
-- WRONG: relies on the route to filter
SELECT * FROM grades WHERE student_id = $1;

-- RIGHT: data layer enforces visibility
SELECT g.* FROM grades g
WHERE g.student_id = $1
  AND EXISTS (SELECT 1 FROM v_visible_students v
              WHERE v.actor_id = $2 AND v.student_id = g.student_id);
```

Row-level security (RLS) in Postgres / equivalent in your DB is excellent for this. Defense in depth.

### Common authz bugs to watch for

- **IDOR** — see `application-security`. Any path or query parameter that names a resource is suspect.
- **Mass assignment** — accepting `{"role": "admin"}` in a JSON PATCH and binding it directly to the model. Use allowlists, not denylists.
- **Verb tampering** — auth check on POST but not PUT/PATCH/DELETE for the same path.
- **Forgotten endpoints** — `/api/v1/...` is gated, `/api/v2/...` ships and isn't. Lint for this.
- **Admin pages assuming network-level access** — "internal-only" is not authz.
- **JWT with stale claims** — user demoted but token still says admin. Short TTLs + a way to invalidate.
- **Insecure direct path traversal in URLs** — `/files/../../etc/passwd`. See `application-security`.
- **Time-of-check / time-of-use** — checked permission, then re-fetched the resource, and it changed. Do the check against the same data you act on.
- **Bypass via second channel** — UI shows the right buttons, but the API has an undocumented endpoint that doesn't check.

### Tenancy / scoping

If your app serves multiple schools, departments, or cohorts, every query must include the tenant filter, ideally enforced at the framework or DB level. A single missing `WHERE org_id = ?` is a cross-tenant leak.

### Impersonation / "view as" features

These are useful for support but extraordinarily dangerous for FERPA. Requirements:

- Only specific roles can impersonate, never users themselves.
- Every action under impersonation is logged with both real actor and impersonated actor.
- The UI clearly indicates impersonation is active; the impersonator's permissions remain bounded by what the impersonated user can do (no privilege escalation through impersonation).
- Time-bounded; auto-exit.
- Reviewed by privacy office before shipping.

## Review checklist

Run through every PR:

- Does this endpoint have an explicit authz decision, or is it relying on "the user is logged in"?
- Does the decision use the actual resource being accessed, not just the user's role?
- Is the failure mode a 404, not a 403, when existence itself is sensitive?
- Is the decision logged with a reason string?
- Are query parameters that name resources validated against the user's scope at the data layer too?
- For state-changing requests (POST/PUT/PATCH/DELETE), is CSRF mitigated? See `application-security`.
- For service-to-service calls, is the caller authenticated and scoped, not just inside the network?
- For new admin/bulk/export features, is MFA step-up required?
- Are session cookies set with `Secure`, `HttpOnly`, `SameSite`?
- Does logout destroy the session server-side?
- Does the code allow assignment to fields the user shouldn't be able to set (role, owner_id, tenant_id)?

## Things to never do

- Roll your own crypto, password hashing, or session token generator.
- Use `localStorage` for auth tokens without a deliberate threat model.
- Accept the JWT `alg` from the token itself.
- Store secrets in source control or `.env` files committed to repos.
- Rely on `X-Forwarded-For` or any client-supplied header for trust decisions.
- Build "this query parameter says I'm admin" debug modes that ship to production.
- Issue long-lived (>24h) bearer tokens.
- Do authz only in the UI ("we hid the button").
- Trust referer headers for security decisions.
