# Secure Design Principles & AI-Assisted Code Risks

Adapted from the cybersecurity-expert skill. The first half is the macro lens — the
architectural principles whose **absence** is often the most valuable finding in a review. The
second half is the AI-assisted-code pass, which matters because most PRs today are written with
AI help and fail in distinct, predictable ways.

## Part 1 — Secure design principles (find the missing layer)

The highest-value architectural findings are usually a *missing* layer, not a wrong one. For
each principle below, ask "is it present, and what fails if it's absent?" — then name the missing
layer, the breach it enables, and the smallest change that restores it.

- **Defense in depth.** No single control should be the only thing between an attacker and the
  asset. Test: name any one control, imagine it fully bypassed, and check the breach is still
  contained. A WAF is not a substitute for input handling; encryption at rest is not a substitute
  for access control.
- **Least privilege.** Every component, credential, and user gets the minimum access and nothing
  more — this bounds blast radius when (not if) a credential leaks. Service accounts scoped to
  exact resources not `*`; DB users with only the verbs they need; short-lived narrow tokens over
  long-lived broad ones. For agents: minimal tools and minimal permission per tool (OWASP
  "excessive agency").
- **Secure defaults / fail closed.** The no-config default state is the safe state (access
  denied unless granted, TLS on, features off). On error, deny rather than allow. A classic
  breach is an auth check that throws and a `catch` that proceeds as if the user passed.
- **Zero trust / never trust the network.** Don't grant access by network location ("it's behind
  the VPN"). Authenticate and authorize every request between services, not just at the
  perimeter — a flat internal network is how one foothold becomes domain-wide ransomware.
- **Complete mediation.** Check authorization every time, on the server, against trusted state
  (session/token) — never request-supplied claims like `?isAdmin=true` or an editable JWT.
  Authentication ≠ authorization: knowing *who* the user is doesn't tell you *what* they may
  touch (IDOR/BOLA).
- **Minimize attack surface and data.** Every endpoint, parameter, dependency, and stored field
  is something to defend. Data you never collect can't leak; the endpoint you don't expose can't
  be attacked. Default to less.
- **Cryptography: use, don't invent.** Vetted libraries and standard constructions only. Slow
  salted password hashes (argon2id/scrypt/bcrypt), authenticated encryption (AES-GCM/
  ChaCha20-Poly1305), CSPRNG for all security randomness, verified TLS, constant-time comparison
  for secrets.
- **Auditability & resilience.** High-value actions need tamper-evident logs that never contain
  the secrets/PII they record. Availability is a security property — rate-limit and bound
  anything an attacker can call in a loop.

## Part 2 — AI-assisted code risks

Independent 2026 analyses put AI-generated code at roughly **2.7× the vulnerability density** of
human-written code, concentrated in injection, XSS, hardcoded secrets, and broad-privilege
patterns. Because the failure modes are systematic, they're checkable. Treat any AI-assisted code
(which is most code) as needing this pass **in addition to** the standard checklist.

**Why it's riskier**
1. It reproduces its training data, insecure parts included — the *common* internet pattern is
   often the insecure one (string-built SQL, `Math.random()` tokens, missing authz). Plausible ≠
   safe.
2. It omits controls you didn't ask for. "Add a file upload" yields an upload — not necessarily
   size limits, type validation, path confinement, or authz. **The vulnerability is in the
   absence**, which a diff-focused reviewer can miss.
3. It is confidently wrong — authoritative-looking output lowers reviewer skepticism exactly when
   it should be highest.
4. It hallucinates package names → slopsquatting.

**Slopsquatting / package hallucination (supply chain).** LLMs invent plausible-but-nonexistent
dependency names; attackers register them with malware, so an `npm install`/`pip install` runs
attacker code on the dev machine and in CI. Treat **every newly added import/require as a claim
to verify**: does the package actually exist and is it the real one (not a typo-twin)? Reasonable
download counts, age, maintainers, repo, recent releases? Pin, lock, and scan.

**Prompt injection that reaches code.** When a model/agent processes untrusted content (a web
page, a PR description, a file, a tool result) that carries instructions, those instructions can
change what it writes or does — in 2026 this produced real CVEs (hidden instructions in a PR
description drove an AI assistant to insert attacker behavior → RCE). If the PR builds a system
where a model influences code or takes actions: content fed to the model is untrusted input;
don't grant the model/tools authority untrusted content could redirect (minimal tools, human
approval on high-impact actions); don't let model output flow unchecked into a sink; isolate the
execution environment.

**The systematic pass for AI-assisted code** — run these specifically:
1. **Injection sinks** — every query parameterized, every command an arg array, every path
   confined? Models default to the unsafe string-built form.
2. **Missing controls** — for each new feature, list the controls it *should* have (authz, input
   validation, size/rate limits, output encoding) and confirm each is present. Absence is the bug.
3. **Secrets** — grep the diff for keys/tokens/passwords/connection strings (~40% higher rate in
   AI code).
4. **Crypto/randomness** — `Math.random()`/`rand()` for tokens, plain hashes for passwords,
   disabled TLS verification, home-rolled crypto.
5. **Authz on data access** — AI scaffolds CRUD that authenticates but rarely checks ownership →
   IDOR/BOLA by default.
6. **Dependencies** — verify every added package exists and is genuine.
7. **Over-broad permissions** — AI-generated IaC/IAM trends toward `*`; tighten to least
   privilege.
8. **Error handling that fails open** — auth/validation failures must deny, not fall through.

**Phrase the finding to recalibrate trust.** "This is the classic AI-generated pattern — the
query is functionally correct but built by string concatenation, so it's a SQL injection. AI
assistants emit this constantly because it's the most common pattern in training data. Use a
parameterized query." The lesson (be skeptical of plausible AI output near a sink) generalizes.
