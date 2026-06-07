# Secure Code Review (micro phase)

This is the working checklist for reading code and diffs. Use it *after* you know what the
code protects and what reaches it (see the macro references). The aim is to find the bugs
that compromise the asset, ranked by impact — not to produce a flat list of style nits.

## How to read code for security

1. **Follow untrusted input.** Start at every place attacker-influenced data enters (request
   params/body/headers, uploads, webhooks, third-party responses, message queues, file
   contents, LLM-generated content) and trace it to every **sink** — a place where it can do
   damage: a SQL query, a shell command, a file path, an HTML response, a deserializer, a
   redirect, an `eval`, a system call. A vulnerability is untrusted data reaching a dangerous
   sink without correct neutralization. This source→sink tracing finds most injection bugs.
2. **Check authorization at each sink that touches data.** For every read/write of a
   resource, find the line that proves the caller is allowed to touch *that specific*
   resource. If it isn't there, it's IDOR/BOLA until proven otherwise.
3. **Diff review:** read what changed *and* what it now reaches. A one-line change that adds a
   user-supplied value into an existing query is a SQL injection even though the query looked
   fine yesterday. Check whether the change weakens an existing control (removes a check,
   broadens a scope, disables verification).

## Severity rubric

Anchor severity to impact × exploitability, not novelty.

- **Critical** — unauthenticated or trivially-authenticated path to RCE, full data exposure,
  auth bypass, or compromise of all tenants. Exploitable now, high impact.
- **High** — significant data exposure or integrity loss, privilege escalation, or injection
  requiring some precondition (a valid low-priv account).
- **Medium** — meaningful weakness needing chained conditions or limited in scope; missing
  defense-in-depth on a sensitive path.
- **Low** — minor info leak, hardening gaps with limited impact.
- **Info** — defensive improvements, no direct exploit.

When unsure between two levels, state the precondition and let it decide: "Critical *if* this
endpoint is internet-facing; High if it's internal-only."

## The vulnerability classes that matter (OWASP-grounded)

### Injection (SQL, NoSQL, OS command, LDAP, XPath, template, ORM-raw)
Untrusted data interpreted as code/query. **Fix by separating code from data**: parameterized
queries / prepared statements (never string-concatenate SQL), safe APIs instead of shell
(`execve`-style arg arrays, not `system("... " + input)`), allowlisted identifiers where
parameters can't be used (table/column names). Escaping is a fallback, not the primary fix.

### Broken access control (IDOR/BOLA, missing function-level authz, path traversal)
The #1 web risk. Object references taken from the request without an ownership check; admin
functions reachable without a role check; `../` in a file path escaping the intended
directory. Fix: authorize against server-side identity for the *specific* object on *every*
request; canonicalize and confine file paths to a base directory.

### Authentication & session flaws
Weak password storage (see crypto in `secure-design-patterns.md`), guessable/long-lived
tokens, missing rate limiting on login/reset (enables credential stuffing), session fixation,
JWTs trusted without verifying signature/audience/expiry, `alg:none` accepted, secrets in the
token. Account recovery flows are a frequent bypass — review them as carefully as login.

### Cross-site scripting (XSS) and output encoding
Untrusted data reflected into HTML/JS/attributes/URLs without context-correct encoding.
Prefer frameworks that auto-escape; treat `dangerouslySetInnerHTML`/`innerHTML`/`v-html` and
template `| safe` as red flags. Sanitize HTML with a vetted sanitizer, not regex. Set a
Content-Security-Policy as defense in depth.

### Cross-site request forgery (CSRF) and unsafe CORS
State-changing requests authenticated only by ambient cookies; or `Access-Control-Allow-Origin`
reflected/`*` together with credentials. Fix: anti-CSRF tokens or SameSite cookies; an
explicit origin allowlist for CORS.

### Server-side request forgery (SSRF)
User-controlled URL fetched by the server, reaching internal services or cloud metadata
(169.254.169.254). Fix: allowlist destinations, block internal/link-local ranges, disable
redirects to them. Especially relevant for "fetch this URL" and webhook features.

### Insecure deserialization & unsafe parsing
Deserializing attacker data into live objects (Python `pickle`, Java native serialization,
unsafe YAML loaders) → RCE. Use data-only formats (JSON) and safe loaders; never deserialize
untrusted bytes into code-bearing objects.

### Sensitive data exposure
Secrets in code/logs/errors/client bundles; PII without encryption or minimization; verbose
stack traces to users; directory listings; debug endpoints in prod. Mask in logs, generic
errors to clients, detailed errors only server-side.

### Security misconfiguration
Default credentials, debug mode in prod, permissive cloud storage (public buckets), missing
security headers, unnecessary services/ports, overly broad IAM. Often the easiest real-world
foothold.

### Vulnerable & malicious dependencies (supply chain)
Known-CVE versions; typosquatted or hallucinated package names (see
`ai-assisted-code-risks.md`); unpinned or unverified installs; build/CI with broad secrets.
Fix: pin and lock, scan dependencies, verify a package exists and is the real one before
adding it, minimize CI privileges.

### Race conditions / TOCTOU & business-logic flaws
Check-then-act gaps (e.g., balance checked then debited non-atomically → double-spend),
negative quantities, price/coupon manipulation, workflow steps skippable out of order. These
have no signature; you find them by reasoning about the *intended* invariant and asking how to
violate it.

## Language-specific footguns (quick scan list)

- **Python:** `pickle`/`yaml.load` on untrusted data; `subprocess(..., shell=True)`; f-string
  SQL; `eval`/`exec`; `assert` for security checks (stripped with `-O`).
- **JavaScript/TS:** `eval`/`Function`; prototype pollution via deep-merge of untrusted JSON;
  `child_process.exec` with interpolation; `innerHTML`; regex DoS; missing `await` on an authz
  check; npm typosquats.
- **Java:** native deserialization; XXE in XML parsers (disable external entities);
  reflection from input; SpEL/OGNL injection; `Runtime.exec` with strings.
- **Go:** `text/template` instead of `html/template` for HTML; ignored errors on auth paths;
  SQL via `fmt.Sprintf`.
- **C/C++:** memory safety — buffer overflows, use-after-free, integer overflow, `strcpy`/
  `sprintf`, format-string bugs. Prefer bounded/safe APIs and run sanitizers.
- **PHP/Ruby:** `eval`, `system`, unsafe `Marshal`/`unserialize`, mass assignment, dynamic
  `include` from input.
- **SQL/ORM:** raw-query escape hatches (`.raw()`, `queryRaw`, `extra()`) with interpolation.

## Don't over-report

A review that flags 50 things teaches the reader to ignore all 50. If a finding wouldn't
change what an attacker can do, it's Info at most or it's omitted. Spend your credibility on
the few findings that matter, make the fix concrete, and explain the underlying class so the
next instance gets caught at authoring time.
