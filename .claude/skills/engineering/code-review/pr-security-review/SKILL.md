---
name: pr-security-review
description: >-
  In-depth SECURITY review of a pull request — the home for everything security-related in code
  review. Traces untrusted input to dangerous sinks and checks authentication, authorization
  (IDOR/BOLA), injection, XSS, CSRF/CORS, secrets, file uploads, SSRF, unsafe redirects,
  sensitive logging, deserialization, path traversal, crypto, dependencies, PII, and audit
  logging. Use whenever someone asks to security-review a PR, "check this PR for
  vulnerabilities," "is this change safe to merge," "audit this diff," "look at PR #123 for
  security issues," pastes a GitHub PR URL or branch mentioning security/risk/exploits, or asks
  whether a change introduces auth, injection, XSS, SSRF, secrets, or upload problems — even
  without the word "security." Prefer this over a generic review when the goal is finding
  security bugs in a changeset. Fetches the diff with the gh CLI, writes findings into a
  mandatory template that names the Security Reviewer and the model, and posts the review back to
  the PR as a comment.
---

# Security PR Review

This skill runs a focused, adversarial security review of the changes in a pull request and
writes the result into one fixed template. The job is not to produce a flat list of style nits
— it is to find the bugs that let an attacker do something they shouldn't, ranked by real
impact, and hand the author a report they can act on.

Two things are non-negotiable:

1. **Every review uses the template in `assets/review-template.md`** (reproduced below). The
   template header explicitly records the **Security Reviewer** and the **model** that did the
   review, so a human reading the PR always knows what looked at their code.
2. **Review the diff, but understand the whole change.** A one-line diff that drops a
   user-supplied value into an existing query is a SQL injection even though the query looked
   fine yesterday. Always ask what the change now *reaches* and whether it *weakens an existing
   control*.

## Workflow

1. **Get the change.** Identify the PR (a number, URL, or branch). Use the gh CLI to pull the
   diff, the changed-file list, and the PR description/title. See "Using the gh CLI" below. If
   you can't reach GitHub, ask the user to paste the diff and review that instead.
2. **Map the attack surface first.** Before reading line by line, note where untrusted input
   enters this change (request params/body/headers, uploads, webhooks, third-party or
   LLM-generated content, message queues, file contents) and what sensitive things the code
   touches (databases, the filesystem, shell, outbound HTTP, auth/session state, secrets).
   This tells you which checks matter most for *this* PR.
3. **Trace source → sink.** For each untrusted input, follow it to every sink where it could
   do damage (a query, a command, a file path, an HTML response, a redirect, a deserializer,
   an outbound URL). A vulnerability is untrusted data reaching a dangerous sink without
   correct, context-appropriate neutralization. This single technique finds most injection,
   XSS, SSRF, and path-traversal bugs.
4. **Run the checklist.** Walk every category in "What to check" below. For deep guidance on
   any category — what the bug looks like, how to confirm it, the real fix — read
   `references/security-checklist.md`, and for the harder specifics (JWT algorithm confusion,
   mass assignment, DNS-rebinding SSRF, CSP nonces, field-level encryption, audit-log rules,
   OAuth redirect-URI rules, tenant isolation) read `references/deep-security-knowledge.md`.
   Load whichever matches what the change touches.
   - **Absence is a finding.** For each new feature the diff adds, list the controls it *should*
     have (authz, input validation, size/rate limits, output encoding) and confirm each is
     present — the most common real bug is a missing control, not a wrong one. This matters
     doubly for AI-assisted code, which reliably omits controls nobody asked for; see
     `references/secure-design-and-ai-risks.md` for that pass (injection sinks, missing controls,
     secrets, crypto, authz-on-data, hallucinated/slopsquatted dependencies).
   - **Quick threat-model question** for anything non-trivial: *what's the worst input that
     reaches this code, from where, and what's the most-trusted thing it can reach?* Do a fuller
     STRIDE-lite / trust-boundary pass (in `deep-security-knowledge.md`) when the diff adds a
     trust boundary or touches money, PII, auth, or secrets.
5. **Write findings into the template.** One finding per issue, each with a severity, the
   file:line, why it's exploitable (state the precondition if it depends on one), and a
   concrete fix. Fill in the Security Reviewer and model fields. Never skip the template.
6. **Deliver, then post the comment.** Save the report to `security-review.md`, then post it
   back to the PR **as a comment using the gh CLI** — this is the default final step, not
   optional: `gh pr comment <number> --body-file security-review.md`. Do this automatically once
   the review is written. Only skip posting if the user explicitly said not to, or if `gh` is
   unavailable/unauthenticated — in which case save the file and give the user the exact command
   to run. After posting, report the comment URL that gh returns.

## Severity rubric

Anchor severity to **impact × exploitability**, not novelty. Be honest — inflating Lows to
Criticals trains people to ignore you.

- **Critical** — unauthenticated (or trivially authenticated) path to RCE, auth bypass, full
  data exposure, or compromise of all tenants. Exploitable now, high impact.
- **High** — significant data exposure or integrity loss, privilege escalation, or injection
  that needs a modest precondition (e.g. any valid low-privilege account).
- **Medium** — a real weakness that needs chained conditions or is limited in scope; missing
  defense-in-depth on a sensitive path.
- **Low** — minor info leak or hardening gap with limited impact.
- **Info** — defensive suggestion, no direct exploit.

When you're torn between two levels, state the precondition and let it decide: "Critical *if*
this endpoint is internet-facing; High if it's internal-only."

## What to check

Walk these for every review. They're ordered roughly by how often they cause real incidents.
`references/security-checklist.md` has the detailed "what it looks like / how to confirm / how
to fix" for each — read it when a change lands in one of these areas.

- **Authentication** — password storage (bcrypt/argon2/scrypt, never fast hashes or plaintext),
  session/token generation and lifetime, JWT verification (signature, `alg`, audience, expiry;
  reject `alg:none`), missing rate limiting on login/reset/MFA, session fixation. Review
  account-recovery flows as carefully as login — they're a frequent bypass.
- **Authorization** — the #1 web risk. For every read/write of a resource, find the line that
  proves the caller may touch *that specific* object (IDOR/BOLA). Check function/role-level
  checks on admin actions, and that the change didn't broaden a scope or drop a check. Watch
  for authz done in the client only, or a missing `await` on an async check.
- **Injection** — SQL/NoSQL/ORM-raw, OS command, LDAP, XPath, template (SSTI). Fix is
  separating code from data: parameterized queries (never string-concatenate SQL), argument
  arrays instead of shell strings, allowlisted identifiers where params can't go. Escaping is a
  fallback, not the primary fix.
- **Cross-site scripting (XSS)** — untrusted data reflected into HTML/JS/attributes/URLs
  without context-correct encoding. `dangerouslySetInnerHTML`, `innerHTML`, `v-html`, and
  template `| safe`/`raw` are red flags. Sanitize HTML with a vetted library, not regex; add a
  CSP as defense in depth.
- **CSRF & CORS** — state-changing requests authenticated only by ambient cookies without an
  anti-CSRF token or `SameSite`; `Access-Control-Allow-Origin` reflected or `*` together with
  credentials. Fix: CSRF tokens or SameSite cookies; an explicit origin allowlist.
- **Secrets** — API keys, passwords, tokens, private keys hardcoded in source, committed
  config, client bundles, or test fixtures. Flag anything that looks like a live credential and
  recommend rotation + a secret manager + a pre-commit/CI secret scan. Check `.env` / example
  files aren't shipping real values.
- **File uploads** — validate type by content not just extension, cap size, store outside the
  webroot with generated names, never execute uploaded content, guard against path traversal in
  the stored filename, and scan where appropriate. Image/office parsers are a common RCE and
  SSRF vector.
- **SSRF** — user-controlled URL fetched by the server reaching internal services or cloud
  metadata (`169.254.169.254`). Fix: allowlist destinations, block internal/link-local ranges,
  disable redirects into them. Especially relevant for "fetch this URL," webhooks, and image/
  document import features.
- **Unsafe redirects (open redirect)** — redirect target taken from user input without an
  allowlist, enabling phishing and OAuth token theft. Validate against a fixed set of allowed
  destinations or use relative paths only.
- **Sensitive logging & data exposure** — passwords, tokens, full PANs, PII, or auth headers
  written to logs, error messages, or stack traces returned to clients; verbose errors, debug
  endpoints, or directory listings in prod. Mask in logs; generic errors to clients, detail
  server-side only.
- **Insecure deserialization & unsafe parsing** — deserializing attacker data into live
  objects (Python `pickle`, Java native serialization, unsafe YAML loaders) → RCE; XXE in XML
  parsers. Use data-only formats and safe loaders; disable external entities.
- **Path traversal** — `../` in a user-influenced file path escaping the intended directory.
  Canonicalize and confine to a base directory.
- **Crypto misuse** — home-rolled crypto, ECB mode, static/predictable IVs, `Math.random()`
  for tokens, MD5/SHA-1 for passwords, disabled TLS verification, hardcoded keys.
- **Vulnerable & malicious dependencies** — newly added packages: known-CVE versions,
  typosquatted or hallucinated names, unpinned installs. Verify a new package actually exists
  and is the real one.
- **Business logic & race conditions (TOCTOU)** — check-then-act gaps (balance checked then
  debited non-atomically), negative quantities, price/coupon manipulation, skippable workflow
  steps. No signature — reason about the intended invariant and how to break it.
- **PII & data protection** — new fields or flows handling personal data: is it minimized (do we
  need this field, at this granularity?), encrypted at rest where sensitive (field-level + KMS,
  authenticated encryption), kept out of URLs/logs/client storage/dev data, and does a
  regulated data type (FERPA/HIPAA/PCI/GDPR) warrant escalation? Plain-SHA-256 of an SSN is not
  protection. See `references/deep-security-knowledge.md` §4.
- **Audit logging & auditability** — are high-value actions (auth events, authz allow *and*
  deny, admin/role changes, data exports, disclosures) logged with the right fields — and do the
  logs avoid secrets, tokens, full PII, and the protected payload? Tamper-evidence for
  compliance logs. See §5.
- **Security headers, transport & cookies** — CSP (nonce-based, not `'unsafe-inline'`), HSTS,
  `X-Content-Type-Options`, `frame-ancestors`/clickjacking, TLS version/verification, and cookie
  flags (`Secure`/`HttpOnly`/`SameSite`/`__Host-`). See §6.
- **Architecture / missing layers** — step back and ask which secure-design principle is absent:
  a data-boundary authz check, fail-closed error handling, least privilege, rate limiting, a
  trust boundary treated as trusted. The missing layer is often the most valuable finding — see
  `references/secure-design-and-ai-risks.md`.

Note when the diff *removes* or *weakens* a control (deletes a check, broadens a CORS origin,
disables verification, loosens a regex) — that's a finding even if nothing new was added.

## Don't over-report

Credibility is the asset. Report exploitable issues and genuine risk, not theoretical concerns
with no path to impact or style preferences dressed up as security. If a category is clean, the
template records it as reviewed-and-clean rather than padding the findings. If the diff is too
large or lacks context to judge something, say so explicitly rather than guessing.

## The mandatory template

Every review is written into this exact structure (the canonical copy is
`assets/review-template.md`). Fill in the Security Reviewer name and the model you are running
as (e.g. `Claude Opus 4.8`, `Claude Sonnet 5`, `DeepSeek-V3`) — this is required so a human
reading the PR knows who and what reviewed it.

```markdown
# 🔒 Security Review

**Security Reviewer:** <name or handle of the reviewer, e.g. Security Reviewer — Claude>
**Model:** <the model performing this review, e.g. Claude Opus 4.8 / Claude Sonnet 5 / DeepSeek-V3>
**PR:** #<number> — <title>
**Commit / branch:** <head SHA or branch>
**Date:** <YYYY-MM-DD>
**Files reviewed:** <count> changed file(s)

## Verdict

<One of: ✅ Approve · 🟡 Approve with comments · 🔴 Request changes · ⛔ Block — merge is unsafe>
<One or two sentences explaining the verdict.>

## Summary

| Severity | Count |
|----------|-------|
| 🔴 Critical | <n> |
| 🟠 High | <n> |
| 🟡 Medium | <n> |
| 🔵 Low | <n> |
| ⚪ Info | <n> |

## Findings

### [<SEVERITY>] <Short title of the issue>
- **Category:** <Authentication | Authorization | Injection | XSS | CSRF | Secrets | File upload | SSRF | Unsafe redirect | Sensitive logging | Deserialization | Path traversal | Crypto | Dependency | Business logic | PII / data protection | Audit logging | Security headers/transport | Architecture>
- **Location:** `<path/to/file.ext>:<line>`
- **Why it's exploitable:** <the attack, and the precondition if any>
- **Recommended fix:** <concrete, specific remediation — ideally a code sketch>

<Repeat one block per finding, ordered highest severity first. If there are no findings, write
"No exploitable issues found in the reviewed changes.">

## Checklist coverage

<Mark each: ✅ reviewed, clean · ⚠️ finding raised · ➖ not applicable to this change>

- ✅/⚠️/➖ Authentication
- ✅/⚠️/➖ Authorization
- ✅/⚠️/➖ Injection
- ✅/⚠️/➖ XSS
- ✅/⚠️/➖ CSRF / CORS
- ✅/⚠️/➖ Secrets
- ✅/⚠️/➖ File uploads
- ✅/⚠️/➖ SSRF
- ✅/⚠️/➖ Unsafe redirects
- ✅/⚠️/➖ Sensitive logging / data exposure
- ✅/⚠️/➖ Deserialization / unsafe parsing
- ✅/⚠️/➖ Path traversal
- ✅/⚠️/➖ Crypto
- ✅/⚠️/➖ Dependencies (incl. hallucinated / slopsquatted packages)
- ✅/⚠️/➖ Business logic / race conditions
- ✅/⚠️/➖ PII / data protection
- ✅/⚠️/➖ Audit logging / auditability
- ✅/⚠️/➖ Security headers / transport / cookies
- ✅/⚠️/➖ Architecture / missing layers

## Notes

<Anything the author should know: assumptions made, context that couldn't be verified from the
diff, follow-ups worth a separate ticket, or "needs more context to judge X".>
```

## Using the gh CLI

The [GitHub CLI](https://cli.github.com/) (`gh`) is the fastest way to read a PR and post the
review. It must be authenticated first (`gh auth status` to check; `gh auth login` if not).

Read the change:

```bash
# Full unified diff for a PR (the primary input to your review)
gh pr diff <number>

# PR title, body, author, base/head, and changed-file list
gh pr view <number> --json number,title,body,headRefName,headRefOid,files

# Just the list of changed files
gh pr view <number> --json files --jq '.files[].path'

# Review a PR in another repo
gh pr diff <number> --repo <owner>/<repo>

# When given a PR URL, gh accepts it directly
gh pr diff https://github.com/<owner>/<repo>/pull/<number>
```

Post the finished review back to the PR — **this is the default final step.** Once the report
is written to `security-review.md`, post it as a PR comment:

```bash
# DEFAULT: post the review as a PR comment (simplest, always works).
# gh prints the comment URL on success — report it back to the user.
gh pr comment <number> --body-file security-review.md

# Post to a PR in another repo
gh pr comment <number> --repo <owner>/<repo> --body-file security-review.md
```

Optionally, submit it as a *formal* PR review instead of a plain comment when you want the
review state recorded on the PR (approve / request-changes):

```bash
gh pr review <number> --request-changes --body-file security-review.md   # Critical/High findings
gh pr review <number> --comment         --body-file security-review.md   # Medium/Low/Info
gh pr review <number> --approve         --body-file security-review.md   # clean
```

Default to `gh pr comment` unless the user asks for a formal review. If `gh` isn't installed or
authenticated (`gh auth status` fails), don't guess — save the report to a file and give the
user the exact `gh pr comment` command to run themselves.

## Reference files

- `assets/review-template.md` — the canonical template (identical to the block above). Copy it
  and fill it in.
- `references/security-checklist.md` — per-category guidance: what each bug looks like, how to
  confirm it, language-specific footguns, and the correct fix. The default checklist reference.
- `references/deep-security-knowledge.md` — the harder specifics distilled from a full security
  skill set: JWT/OAuth pitfalls, mass assignment and tenant isolation, secret-leakage vectors
  and rotation, PII/PHI/PCI handling and field-level encryption, audit-logging do's and don'ts,
  SSRF/CSP/CSRF/cookie depth, and a STRIDE-lite threat-model pass. Read the matching section when
  a change lands in one of these areas.
- `references/secure-design-and-ai-risks.md` — the macro design principles (defense in depth,
  least privilege, fail-closed, complete mediation) whose *absence* is often the finding, plus
  the systematic pass for AI-assisted code (which ships ~2.7× the vulnerabilities) and
  slopsquatting/prompt-injection risks. Read it for architecture-level judgment and whenever the
  code looks AI-generated.
