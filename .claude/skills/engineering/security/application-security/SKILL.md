---
name: application-security
description: Apply web application security defenses to any code that handles HTTP requests, user input, database queries, file operations, outbound requests, rendering, redirects, or session handling. Covers the OWASP Top 10 with a focus on the issues most likely to bite a Vanderbilt student data app: broken access control / IDOR, injection (SQL, command, template), SSRF, CSRF, XSS, insecure deserialization, security misconfiguration (CSP, headers), open redirect, and dependency / supply chain risk. Use whenever the work involves new endpoints, new query parameters, file uploads, downloads, fetching URLs, embedding HTML/markdown, third-party callbacks, redirects, allowlisting/denylisting, dependency upgrades, or anything where untrusted input meets a sensitive sink. Trigger even when not asked — every web feature has security implications and it's faster to bake them in than retrofit. This is the generic web-app security baseline that pairs with `authn-authz` for access control and `pii-handling` for data protection.
---

# Application Security

Generic web-application security defenses. The Vanderbilt-specific compliance work is in `ferpa-compliance` and `pii-handling`; the access-control mechanics are in `authn-authz`. This skill covers the rest of the OWASP Top 10 plus the specific anti-patterns that cause real incidents.

The guiding principle: **untrusted input + sensitive sink = vulnerability**. Every defense below is a way of breaking that pairing — by validating the input, sanitizing the output, or removing the sink.

## Broken Access Control (OWASP A01) — including IDOR

The most-exploited class of bugs in modern web apps. Most of this is in `authn-authz`; the input-side issues:

**IDOR (Insecure Direct Object Reference).** Any endpoint that takes an ID — `/api/transcripts/{id}`, `/files/{name}`, `?student=123` — must verify the caller is permitted to access *that specific* object. "Logged in" is not enough.

```python
# WRONG
@app.get("/api/transcripts/{tid}")
def get_transcript(tid, user=Depends(require_login)):
    return db.transcripts.get(tid)

# RIGHT
@app.get("/api/transcripts/{tid}")
def get_transcript(tid, user=Depends(require_login)):
    t = db.transcripts.get_for_actor(actor=user, transcript_id=tid)
    if not t:
        raise HTTPNotFound()  # 404, not 403 — see authn-authz
    return t
```

Check both the *route handler* and the *data layer*. Defense in depth: row-level security (RLS) in the DB or query helpers that take the actor as an argument.

**Verb tampering / forgotten methods.** Auth check on `GET` but not `PUT`. Lint for it; better, write authz at the framework level so any unenforced route fails closed.

**Mass assignment.** Don't bind request bodies straight to ORM models. Use explicit field allowlists.

```python
# WRONG
user.update(**request.json)  # client sends {"role": "admin"} → game over

# RIGHT
ALLOWED = {"display_name", "preferred_pronouns"}
user.update(**{k: v for k, v in request.json.items() if k in ALLOWED})
```

**Path traversal.** User input + filesystem path = always suspect. Resolve and validate.

```python
# WRONG
path = f"/data/uploads/{user_input}"

# RIGHT
base = Path("/data/uploads").resolve()
target = (base / user_input).resolve()
if not target.is_relative_to(base):  # Python 3.9+, otherwise str startswith with care
    raise BadRequest()
```

## Injection (OWASP A03)

### SQL injection

Parameterize. Always.

```python
# WRONG
db.execute(f"SELECT * FROM students WHERE id = '{sid}'")

# RIGHT
db.execute("SELECT * FROM students WHERE id = %s", (sid,))

# RIGHT (ORM)
session.query(Student).filter(Student.id == sid).first()
```

Watch for these traps: `LIKE` clauses (parameterize the value, not the wildcards), dynamic table/column names (allowlist them — they can't be parameterized in most drivers), `IN (...)` lists (use proper array binding, not string concatenation), raw / `text()` escapes in ORMs (still parameterize).

### Command injection

Don't shell out with user input. If you must, don't use `shell=True`; pass an argv list.

```python
# WRONG
subprocess.run(f"convert {filename} out.pdf", shell=True)

# RIGHT
subprocess.run(["convert", filename, "out.pdf"])  # argv, no shell

# Even better: validate filename against an allowlist and prefer a library, not a shell tool
```

### Template injection

User input rendered by a template engine (Jinja, Handlebars, etc.) without escaping or as a template *itself* leads to RCE. Never treat user input as a template; always render it as data.

### LDAP, NoSQL, XPath injection

All variants of the same problem. Use the driver's parameter binding, not string concatenation. For MongoDB: never accept user-supplied operators (`$ne`, `$gt`) as raw input; allowlist field names and types.

### Header / log injection (CRLF)

User input written to headers or log lines must strip `\r\n`. Frameworks usually handle response headers; logs are often where this slips through.

## SSRF (OWASP A10)

Server-Side Request Forgery: your server fetches a URL the user gave it. The classic attack is the cloud metadata endpoint:

```
http://169.254.169.254/latest/meta-data/iam/security-credentials/...
```

…which on AWS hands out IAM credentials. Equivalent endpoints exist for GCP, Azure, OCI.

If your app fetches user-supplied URLs — webhooks, "import from URL," RSS, OEmbed previews, profile picture URLs, anything — you must defend. SSRF defenses, in layers:

1. **Don't fetch user URLs at all** if you can avoid it. Most "import from URL" features can be replaced with file uploads.
2. **Allowlist of permitted hosts** — only fetch from a known set of domains.
3. **Resolve DNS yourself, then validate the resolved IP** before connecting. Reject:
   - Loopback (127.0.0.0/8, ::1)
   - Link-local (169.254.0.0/16, fe80::/10) — this is the metadata endpoint range
   - Private (10/8, 172.16/12, 192.168/16, fc00::/7)
   - 0.0.0.0/8, multicast, broadcast, reserved ranges
4. **Use a forward proxy** with egress allowlists. The application code never opens raw sockets; all outbound fetches go through a proxy that enforces destination policy.
5. **Disable redirects** or re-validate the destination on each redirect. A URL pointing to a public domain that 302-redirects to `169.254.169.254` defeats step 3 if you don't recheck.
6. **Disable non-HTTP schemes**. Block `file://`, `gopher://`, `dict://`, `ldap://`. Allow only `https://` (and `http://` if you really must).
7. **Block IMDSv1 at the cloud level** — on AWS, require IMDSv2 (token-based) so even if SSRF reaches the metadata endpoint, no creds come out without the token request.
8. **Set short timeouts and small response size limits** to limit blast radius.

```python
import ipaddress, socket
from urllib.parse import urlparse

DENY_NETS = [
    ipaddress.ip_network("127.0.0.0/8"),
    ipaddress.ip_network("169.254.0.0/16"),
    ipaddress.ip_network("10.0.0.0/8"),
    ipaddress.ip_network("172.16.0.0/12"),
    ipaddress.ip_network("192.168.0.0/16"),
    ipaddress.ip_network("0.0.0.0/8"),
    ipaddress.ip_network("::1/128"),
    ipaddress.ip_network("fc00::/7"),
    ipaddress.ip_network("fe80::/10"),
]

def safe_url(url: str) -> str:
    p = urlparse(url)
    if p.scheme not in ("https",):
        raise ValueError("scheme not allowed")
    host = p.hostname
    if not host:
        raise ValueError("no host")
    # resolve to all addresses; reject if any is in deny range
    for fam, _, _, _, sa in socket.getaddrinfo(host, None):
        ip = ipaddress.ip_address(sa[0])
        if any(ip in net for net in DENY_NETS):
            raise ValueError("disallowed destination")
    return url
```

Note: this still has a TOCTOU window (DNS could change between validation and fetch). For high-assurance, pin the resolved IP and connect to it directly with a `Host:` header, or use an egress proxy.

## CSRF (Cross-Site Request Forgery)

If your app uses cookie-based sessions, a malicious site can cause the user's browser to submit authenticated requests. Defenses, layered:

1. **`SameSite` cookies** — `SameSite=Lax` blocks most CSRF for top-level navigations and cross-site subrequests. `Strict` is stronger but can break legitimate flows. With `SameSite=Lax` you still need protection for state-changing GETs (which you shouldn't have anyway).
2. **CSRF tokens** for state-changing requests (POST/PUT/PATCH/DELETE). Synchronizer pattern: server issues a token tied to the session; client sends it back in a header or hidden field; server compares.
3. **Double-submit cookie** as an alternative when stateless — token in cookie + same token in header; attacker can't read cookies cross-origin so they can't replay.
4. **Origin / Referer header check** for state-changing requests. Reject if Origin doesn't match an allowlist of expected origins. Don't *only* rely on this (some browsers omit headers in some cases).
5. **JSON-only APIs** require `Content-Type: application/json`. Most browsers will require a CORS preflight for cross-origin JSON POSTs, which doesn't include credentials by default. Combined with strict CORS, this is a reasonable defense for API-only apps.
6. **Re-authentication / step-up MFA** for high-impact actions (delete account, export data, change email).

GraphQL and JSON APIs are not magically immune. Frameworks differ — confirm yours actually enforces CSRF on the routes that need it.

## XSS (Cross-Site Scripting)

User input rendered in a page without proper escaping → attacker runs JavaScript in the user's session.

**Default to framework escaping.** React, Vue, Angular, Svelte, modern templating engines auto-escape interpolations by default. The danger zones are the *bypasses*:

- `dangerouslySetInnerHTML` (React)
- `v-html` (Vue)
- `[innerHTML]` (Angular)
- `{{{ }}}` triple-stash (Handlebars)
- `|safe` filter (Jinja)
- DOM APIs: `.innerHTML`, `document.write`, `eval`, `setTimeout(string, ...)`
- `href="${userInput}"` — `javascript:` URLs

If you must render user-supplied HTML (markdown, rich text), use a vetted sanitizer:

- **DOMPurify** (browser/Node) — battle-tested, configurable allowlist
- **bleach** (Python) — wraps html5lib, allowlist-based
- **sanitize-html** (Node) — allowlist-based

Configure with a tight allowlist of tags and attributes. Disallow `<script>`, `<iframe>` (or scope to `sandbox` if essential), event handlers (`onclick`, etc.), `javascript:` URLs, and CSS expressions.

**Output context matters.** Escape *for the context* you're inserting into:
- HTML body → HTML-escape
- HTML attribute value → HTML-attribute escape (and quote)
- JavaScript context → JSON-encode (and prefer data attributes over inline scripts)
- URL parameter → URL-encode
- CSS value → CSS-escape (or just don't insert user data into CSS)

```jsx
// React, safe
<div>{userBio}</div>

// React, dangerous — only with sanitized input
<div dangerouslySetInnerHTML={{ __html: DOMPurify.sanitize(userBioHtml) }} />

// React, dangerous — javascript: URL
<a href={userUrl}>click</a>  // validate scheme first
```

**Stored vs reflected vs DOM-based.** All three are XSS. DOM-based is the easiest to miss because it never hits your server — `location.hash` parsed by client JS and written to the DOM, for example. Audit client-side code that reads from `location`, `document.referrer`, `postMessage`, `localStorage`, etc., and writes to dangerous sinks.

## CSP (Content Security Policy)

CSP is a defense-in-depth backstop for XSS. It tells the browser what sources are allowed for scripts, styles, images, fonts, frames, and connections. With a strict CSP, an XSS bug that gets through your sanitization may still fail to execute.

A good baseline for new apps:

```
Content-Security-Policy:
  default-src 'self';
  script-src 'self' 'nonce-{RANDOM}' 'strict-dynamic';
  style-src 'self' 'nonce-{RANDOM}';
  img-src 'self' data: https:;
  font-src 'self';
  connect-src 'self' https://api.your-domain.example;
  frame-ancestors 'none';
  base-uri 'self';
  form-action 'self';
  object-src 'none';
  upgrade-insecure-requests;
  report-uri /csp-report;
```

Key choices:

- **Nonce-based, not `'unsafe-inline'`.** Generate a per-request random nonce, include it in the header, and add it to every legitimate `<script>` and `<style>` tag. Inline scripts without the nonce will not execute. `'strict-dynamic'` lets nonced scripts load further scripts without you allowlisting every CDN.
- **No `'unsafe-eval'`.** Some libraries (older Vue, some templating, dev modes) need it; pin those out of production. `eval`, `new Function`, `setTimeout(string)` are blocked.
- **`frame-ancestors 'none'` (or specific origins).** Replaces the older `X-Frame-Options`. Stops clickjacking.
- **`object-src 'none'`** — no Flash, no plugin embedding.
- **`base-uri 'self'`** — prevents `<base>` tag injection.
- **`form-action 'self'`** — prevents form action hijacking.
- **`report-to` / `report-uri`** — CSP violation reports stream to your audit pipeline. See `audit-logging`.

Roll out with `Content-Security-Policy-Report-Only` first, watch the reports, fix violations, then promote to enforcement. `'unsafe-inline'` and `'unsafe-eval'` should be a temporary crutch with a tracked ticket to remove, not a permanent state.

## Other security headers

Set these on every response:

```
Strict-Transport-Security: max-age=31536000; includeSubDomains; preload
X-Content-Type-Options: nosniff
Referrer-Policy: strict-origin-when-cross-origin     # or no-referrer for sensitive apps
Permissions-Policy: geolocation=(), camera=(), microphone=()   # disable what you don't use
Cross-Origin-Opener-Policy: same-origin
Cross-Origin-Resource-Policy: same-origin
```

`X-XSS-Protection` is deprecated; either omit it or set `0` to disable browser heuristics that have caused their own bugs. Modern browsers rely on CSP.

## Open redirect

A classic phishing helper. `?next=https://evil.com` after login → user is redirected to attacker's site. Validate redirect targets:

```python
from urllib.parse import urlparse

def safe_redirect(target):
    p = urlparse(target)
    # allow only relative URLs, or absolute URLs to allowed hosts
    if p.netloc and p.netloc not in ALLOWED_HOSTS:
        target = "/"  # fallback
    return target
```

Reject schemes other than `http(s)`. Reject `//evil.com` (protocol-relative URLs that browsers treat as cross-origin). Reject `\evil.com` and other parser-confusion variants — use the URL parser, not regex.

## File upload

Uploads are an attack surface for content type smuggling, path traversal, large-file DoS, malware, and RCE if served back as the wrong type.

- **Validate type by content sniffing**, not just extension or `Content-Type` header. `python-magic` / `file` command. Allowlist of acceptable types.
- **Re-encode** images through a library (e.g., Pillow → re-save as PNG). Strips embedded scripts and metadata.
- **Generate the storage filename** — never use the user-supplied name. Random ULID + a content-derived extension.
- **Store outside the webroot** if possible. Serve through an authenticated handler that sets `Content-Disposition: attachment` for downloads and a tight `Content-Type`.
- **Set `X-Content-Type-Options: nosniff`** so browsers don't sniff stored files into something executable.
- **Limit size** at the proxy / load balancer, not just the app, to avoid OOM.
- **Scan for malware** when feasible (uploads to shared storage, especially).
- **Strip metadata** from images (EXIF GPS data on a student photo is PII) — see `pii-handling`.

## Insecure deserialization

Pickling, Java serialization, .NET BinaryFormatter, PHP `unserialize`, YAML loaders that allow arbitrary types — feeding untrusted bytes through these is RCE.

- **Don't deserialize untrusted input** with these mechanisms. Use JSON for inter-system data; use schemas (Protobuf, Avro, JSON Schema) when types matter.
- For YAML: `yaml.safe_load`, never `yaml.load`.
- For Pickle: don't accept it from clients, period.

## Dependencies and supply chain (OWASP A06, A08)

- **Lockfiles in source control** (package-lock.json, poetry.lock, Cargo.lock, go.sum). Don't `npm install` in production.
- **SCA scanning** in CI — `npm audit`, `pip-audit`, GitHub Dependabot, Snyk, Trivy, OSV-Scanner. Treat high/critical as build-breakers.
- **Pin direct dependencies** to specific versions; let lockfiles pin transitive.
- **Review the lockfile diff** on dependency updates. Look for new packages with low-reputation maintainers, recent unexplained ownership changes, or unnecessarily broad permissions.
- **Subresource Integrity (SRI)** for any script you load from a CDN: `<script src="..." integrity="sha384-..." crossorigin>`.
- **Build provenance / SLSA** for production-bound artifacts where feasible.
- **Don't `curl | sh`** in build scripts.

## Rate limiting and abuse

- Rate limit at the edge (load balancer / WAF) and again at the app for sensitive endpoints (login, password reset, search).
- Lock-out / back-off on failed authentication, with care to avoid enabling user enumeration ("account locked" reveals account exists).
- Distinguish per-IP limits from per-account limits — both are useful for different threats.

## Error handling

- **Don't expose stack traces, query text, or internal IDs in error responses.** A generic 500 + a request ID the user can quote to support is the model. The detail goes to logs.
- **Map errors to safe messages.** "Email or password incorrect" — not "no such email" vs "wrong password" (user enumeration).
- **Fail closed**, especially in security middleware. If the policy engine is unreachable, deny — don't fall through to "allow."

## Testing

- **SAST** in CI for the languages in use (Semgrep, CodeQL).
- **Dependency scanning** as above.
- **DAST / authenticated scanners** against staging (ZAP, Burp).
- **Fuzz testing** for any parser you wrote.
- **Manual security review** for new features that touch authn, authz, payments, or PII (which on this project is most features).
- **Threat model** when introducing a new architectural element (a new external service, a new trust boundary, a new auth flow). Doesn't have to be a 30-page document; a STRIDE table on a wiki page is fine.

## Quick review checklist

For any PR:

- [ ] Every endpoint has explicit authn and authz (`authn-authz`)
- [ ] No string interpolation into SQL / shell / templates
- [ ] User-supplied URLs that the server fetches go through SSRF defenses
- [ ] State-changing requests have CSRF protection
- [ ] Outputs are escaped for context; HTML rendering uses sanitizer
- [ ] CSP, HSTS, and other headers set
- [ ] No PII in URLs or logs (`pii-handling`)
- [ ] File uploads validated, re-encoded, stored outside webroot
- [ ] Errors don't leak internals; auth errors don't enumerate
- [ ] Redirect targets validated
- [ ] Dependencies pinned and scanned
- [ ] Sensitive actions require step-up auth and are audit-logged (`audit-logging`)
