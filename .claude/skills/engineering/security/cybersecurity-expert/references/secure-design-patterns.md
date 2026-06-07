# Secure Design Patterns (macro phase)

These are the architectural principles that make whole classes of bugs impossible or
survivable. A system built on them degrades gracefully when a single control fails; a system
without them turns one bug into a full compromise. Evaluate a design against these *before*
judging individual lines of code.

## Defense in depth

No single control should be the only thing standing between an attacker and the asset. Assume
each layer will eventually fail and ask "then what?" A WAF is not a substitute for input
handling; network isolation is not a substitute for authorization; encryption at rest is not
a substitute for access control. The test: name any one control, imagine it fully bypassed,
and check that the breach is still contained.

## Least privilege

Every component, credential, and user should have the minimum access needed and nothing more.
This is the single highest-leverage principle because it bounds blast radius. Concretely:

- Service accounts scoped to the exact resources they use, not `*`.
- Database users with only the verbs they need (the read path shouldn't hold `DROP`).
- Short-lived, narrowly-scoped tokens over long-lived broad ones.
- For agents/automation: minimal tool set and minimal permissions per tool (see OWASP's
  "excessive agency" — excessive functionality, permissions, and autonomy are distinct sins).

When a credential leaks — and they leak — least privilege is what decides whether it's an
incident or a catastrophe.

## Secure defaults / fail closed

The default state, with no configuration, should be the safe state. Access denied unless
granted; TLS on unless explicitly downgraded; features off until enabled. And when something
errors, it should fail *closed* (deny) rather than open (allow). A classic breach pattern is
an auth check that throws an exception and a catch block that proceeds as if the user passed.

## Zero trust / never trust the network

Don't grant access based on network location ("it's behind the VPN, so it's safe").
Authenticate and authorize every request between services, not just at the perimeter. The
flat internal network where one foothold reaches everything is how a phishing email becomes a
domain-wide ransomware event. Segment, authenticate service-to-service, and verify explicitly.

## Complete mediation: check authorization every time, server-side

Every access to a protected resource must be checked, on every request, on the server. Two
failure modes dominate real breaches:

- **Authentication ≠ authorization.** Knowing *who* the user is doesn't tell you *what*
  they're allowed to touch. The most common serious web bug is IDOR/BOLA: a logged-in user
  changes `/invoices/123` to `/invoices/124` and reads someone else's data because the code
  authenticated them but never checked ownership.
- **Trusting the client.** Hidden form fields, disabled buttons, and client-side role checks
  are not security. Re-derive identity and permissions on the server from trusted state
  (session/token), never from request-supplied claims like `?isAdmin=true` or an editable JWT.

## Minimize attack surface and data

Every endpoint, parameter, dependency, and stored field is something to defend. The data you
never collect can't leak; the endpoint you don't expose can't be attacked; the dependency you
don't add can't be a supply-chain vector. Default to less.

## Secrets management

Secrets (keys, tokens, DB passwords) belong in a secrets manager or injected environment, not
in source code, not in client bundles, not in logs, not in error messages. AI-assisted code
has a measurably higher rate of hardcoded secrets, so this is a primary review target. When a
secret is exposed, rotate it — removing it from the latest commit doesn't un-leak it from
history or from wherever it was already scraped.

## Cryptography: use, don't invent

- Never roll your own crypto or your own auth protocol. Use vetted, maintained libraries and
  standard constructions.
- Passwords: a slow, salted password hash designed for the job (argon2id, scrypt, bcrypt).
  Never plain hashes (SHA-256) and never encryption (passwords are verified, not decrypted).
- Use authenticated encryption (AES-GCM, ChaCha20-Poly1305); don't hand-assemble modes.
- Randomness for security (tokens, IDs, nonces) must come from a cryptographically secure RNG,
  not `Math.random()`/`rand()`.
- Verify TLS certificates; don't disable verification to "make it work."
- Compare secrets with constant-time comparison to avoid timing leaks.

## Auditability

You can't respond to what you can't see. High-value actions (auth events, privilege changes,
data exports, admin actions) need tamper-evident logs — and logs must never contain the
secrets or full PII they're recording. Logging a password or token is itself a finding.

## Resilience and abuse limiting

Availability is a security property. Rate-limit and quota anything an attacker can call in a
loop (login, password reset, expensive queries, LLM calls — "unbounded consumption" is both a
cost and a DoS risk). Set timeouts and bound resource use so one bad actor can't exhaust the
system for everyone.

## How to apply this in a review

Walk the design and, for each principle, ask "is this present, and what fails if it's
absent?" The most valuable architectural findings are usually *missing* layers — no authz at
the data boundary, a flat trust network, secrets in code, no rate limiting — not the presence
of a wrong one. Name the missing layer, the breach it enables, and the smallest change that
restores defense in depth.
