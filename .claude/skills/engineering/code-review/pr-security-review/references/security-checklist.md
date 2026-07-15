# Security PR Review — Detailed Checklist

Deep guidance for each category in the main SKILL.md. For every category: **what the bug looks
like**, **how to confirm it in a diff**, and **the correct fix**. Read the sections relevant to
what the PR touches. The overarching technique is always the same: trace untrusted input to a
dangerous sink and ask whether it's neutralized correctly for that sink's context.

## Table of contents

1. Authentication
2. Authorization (access control)
3. Injection
4. Cross-site scripting (XSS)
5. CSRF & CORS
6. Secrets
7. File uploads
8. SSRF
9. Unsafe redirects
10. Sensitive logging & data exposure
11. Insecure deserialization & unsafe parsing
12. Path traversal
13. Crypto misuse
14. Vulnerable & malicious dependencies
15. Business logic & race conditions
16. Language-specific footguns

---

## 1. Authentication

**Looks like:** passwords stored with fast hashes (MD5/SHA-256) or plaintext; predictable or
long-lived session tokens; JWTs decoded without verifying the signature, `alg`, audience, or
expiry; `alg:none` accepted; secrets embedded in a token payload; no rate limiting on login,
password reset, OTP, or MFA; session IDs not rotated after login (fixation).

**Confirm in a diff:** look for `jwt.decode(...)` without a verify step or with
`verify=False`; new login/reset endpoints with no throttling; `createHash('sha256')` or
`md5(` near a password; a session token built from `Math.random()`, a timestamp, or a
sequential counter.

**Fix:** bcrypt/argon2id/scrypt for passwords; verify JWT signature + `alg` allowlist +
`aud` + `exp`; rate-limit and lock/backoff on auth endpoints; rotate the session on
privilege change; use a CSPRNG for tokens. Review account-recovery flows as carefully as
login — they're the most common bypass.

## 2. Authorization (access control)

The #1 web risk (OWASP A01). **Looks like:** an object ID taken from the request and used to
fetch/update a record with no ownership check (IDOR/BOLA); an admin action with no role check;
authorization enforced only in the UI/client; a scope silently broadened.

**Confirm in a diff:** for every new `findById(req.params.id)` / `WHERE id = ?` on a
user-owned resource, find the line that proves the *current user* owns *that* object. If it's
absent, it's IDOR until proven otherwise. Watch for a missing `await` on an async permission
check (the code proceeds before the check resolves), and for a diff that removes a guard.

**Fix:** authorize against server-side identity for the specific object on every request
(`WHERE id = ? AND owner_id = current_user`), centralize checks, deny by default.

## 3. Injection

**Looks like:** untrusted data concatenated into a SQL/NoSQL query, an OS command, an LDAP or
XPath filter, or a server-side template (SSTI). Escaping used as the primary defense.

**Confirm in a diff:** string building around `SELECT`/`UPDATE`/`WHERE`; f-strings /
template literals / `+` with request data inside a query; `.raw()`, `queryRaw`, `.extra()`,
`Sequelize.literal` with interpolation; `exec`/`system`/`child_process.exec` with a string
that includes input; user data reaching `render_template_string` / a template compiled at
runtime.

**Fix:** parameterized queries / prepared statements — never concatenate. For shell, pass an
argument array (no `shell=True`), or avoid the shell entirely. For identifiers that can't be
parameterized (table/column names), use a strict allowlist. Escaping is a last resort.

## 4. Cross-site scripting (XSS)

**Looks like:** untrusted data written into HTML, an attribute, a `<script>` block, or a URL
without context-correct encoding. Reflected, stored, or DOM-based.

**Confirm in a diff:** `dangerouslySetInnerHTML`, `innerHTML`, `outerHTML`,
`document.write`, `v-html`, Angular `[innerHTML]`/`bypassSecurityTrust*`, template filters
like `| safe` / `| raw` / `{{{ }}}`, `href`/`src` built from input (`javascript:` URIs),
HTML assembled by string concatenation.

**Fix:** rely on the framework's auto-escaping; sanitize HTML you must render with a vetted
sanitizer (DOMPurify), never regex; encode per context (HTML vs attribute vs JS vs URL); set
a Content-Security-Policy as defense in depth.

## 5. CSRF & CORS

**Looks like:** a state-changing endpoint (POST/PUT/DELETE) authenticated only by a cookie,
with no anti-CSRF token and no `SameSite`; `Access-Control-Allow-Origin` reflecting the
request `Origin` or set to `*` while `Access-Control-Allow-Credentials: true`.

**Confirm in a diff:** new mutating routes without CSRF middleware; CORS config that echoes
`req.headers.origin`; `cors({ origin: true, credentials: true })`.

**Fix:** anti-CSRF tokens or `SameSite=Lax/Strict` cookies for browser-authenticated
mutations; an explicit, exact origin allowlist for CORS — never reflect the origin with
credentials enabled.

## 6. Secrets

**Looks like:** API keys, passwords, tokens, private keys, connection strings hardcoded in
source, committed config, client-side bundles, test fixtures, or `.env` files checked in with
real values.

**Confirm in a diff:** high-entropy strings; `AKIA…`, `sk-…`, `ghp_…`, `-----BEGIN … PRIVATE
KEY-----`, `password = "…"`, `Authorization: Bearer <literal>`; a `.env` (not `.env.example`)
appearing in the change.

**Fix:** remove the secret, **rotate it** (assume it's burned once committed), load from a
secret manager or environment, add a pre-commit / CI secret scanner, and ensure `.env` is
git-ignored. Note that history rewriting may be needed for already-pushed secrets.

## 7. File uploads

**Looks like:** trusting the client-supplied filename or MIME type; no size cap; storing
uploads inside the webroot with the original name; serving/executing uploaded content; a
filename with `../` written straight to disk; image/office parsers invoked on untrusted files.

**Confirm in a diff:** an upload handler that uses `file.originalname` for the stored path,
checks only the extension, or writes into a public/served directory.

**Fix:** validate type by content (magic bytes) not extension, enforce a size limit, store
outside the webroot under a generated name, set restrictive permissions, never execute
uploaded files, and canonicalize the destination path. Treat image/document parsing as an RCE
and SSRF surface.

## 8. SSRF

**Looks like:** the server fetches a URL that the user controls, allowing it to reach internal
services, `localhost`, or cloud metadata at `169.254.169.254`. Common in "import from URL,"
webhooks, avatar-by-URL, PDF/HTML renderers, and link-preview features.

**Confirm in a diff:** `requests.get(user_url)`, `fetch(userUrl)`, `axios.get(url)`,
`urllib.urlopen(...)`, an HTTP client library where the destination comes from input; redirects
followed by default.

**Fix:** allowlist destinations (scheme + host), resolve and block private/link-local/loopback
ranges (including IPv6 and DNS-rebinding), disable or re-validate redirects, and don't return
raw upstream responses/errors to the caller.

## 9. Unsafe redirects (open redirect)

**Looks like:** `redirect(request.args["next"])` / `res.redirect(req.query.url)` where the
target is user-controlled and unvalidated — used for phishing and to steal OAuth tokens via a
manipulated `redirect_uri`.

**Confirm in a diff:** a redirect whose target reads from query/body/header; a `returnTo` /
`next` / `callback` parameter passed straight to a redirect.

**Fix:** allowlist redirect targets, or accept only relative paths (reject anything with a
scheme or `//`). For OAuth, match `redirect_uri` exactly against registered values.

## 10. Sensitive logging & data exposure

**Looks like:** passwords, tokens, session IDs, full card numbers, PII, or `Authorization`
headers written to logs; full request/response bodies logged; stack traces or DB errors
returned to the client; debug mode / verbose errors / directory listings in prod.

**Confirm in a diff:** `logger.info(req.body)` / `console.log(user)` on an object that holds
credentials; `printStackTrace()` into a response; `DEBUG = True`; an error handler that echoes
`err.message` / `err.stack` to the client.

**Fix:** mask or omit sensitive fields in logs (allowlist what you log), return generic errors
to clients and keep detail server-side, disable debug in prod, and don't log full tokens/PII.

## 11. Insecure deserialization & unsafe parsing

**Looks like:** deserializing attacker-controlled bytes into live objects — Python `pickle`,
Ruby `Marshal`, Java native `ObjectInputStream`, PHP `unserialize`, unsafe YAML
(`yaml.load` without `SafeLoader`) — leading to RCE. Also XXE: XML parsers with external
entities enabled.

**Confirm in a diff:** `pickle.loads(`, `yaml.load(` (no `Loader=SafeLoader`),
`ObjectInputStream`, `unserialize(`, `Marshal.load`, an XML parser without external-entity
resolution disabled.

**Fix:** use data-only formats (JSON) and safe loaders; never deserialize untrusted input into
code-bearing objects; disable DTD/external entities in XML parsers.

## 12. Path traversal

**Looks like:** a user-influenced value used in a filesystem path, letting `../` escape the
intended directory to read/write arbitrary files.

**Confirm in a diff:** `open(base + user_input)`, `path.join(dir, req.params.name)`,
`fs.readFile(userPath)` with no normalization/confinement.

**Fix:** canonicalize the resolved path (`realpath`) and verify it stays within the intended
base directory; reject `..` and absolute paths; prefer an ID → known-path mapping over
user-supplied paths.

## 13. Crypto misuse

**Looks like:** home-rolled crypto; AES-ECB; static/predictable IV or nonce reuse;
`Math.random()` / `rand()` for tokens or keys; MD5/SHA-1 for passwords; disabled TLS
verification (`verify=False`, `rejectUnauthorized: false`); hardcoded keys/IVs.

**Confirm in a diff:** `ECB`, a constant `iv`, `Math.random()` producing a security token,
`verify=False`, `InsecureSkipVerify: true`, a key literal in source.

**Fix:** use vetted libraries and authenticated encryption (AES-GCM / libsodium), a CSPRNG for
all tokens/IVs, argon2/bcrypt for passwords, and keep TLS verification on. Keys come from a
secret manager, never source.

## 14. Vulnerable & malicious dependencies

**Looks like:** a newly added dependency pinned to a known-CVE version; a typosquatted or
outright hallucinated package name; an unpinned/loose version; installing from an untrusted
source.

**Confirm in a diff:** new entries in `package.json` / `requirements.txt` / `go.mod` / etc.
Verify the package actually exists and is the real, popular one (not `reqeusts`,
`python-dateutil2`, etc.); check the version against known advisories.

**Fix:** pin and lock versions, run a dependency/SCA scan, verify the package's authenticity
before adding, and minimize CI privileges available during install.

## 15. Business logic & race conditions

**Looks like:** check-then-act gaps (balance checked, then debited non-atomically →
double-spend), negative or overflowing quantities, price/coupon/discount manipulation,
workflow steps that can be skipped or replayed, missing idempotency on payments.

**Confirm in a diff:** these have no signature — reason about the *intended invariant* the code
protects and ask how to violate it. Look for read-modify-write on shared state without a
transaction or lock.

**Fix:** enforce invariants atomically (DB transactions, `SELECT … FOR UPDATE`, conditional
updates), validate quantity/price server-side, and make sensitive operations idempotent.

## 16. Language-specific footguns (quick scan)

- **Python:** `pickle` / `yaml.load` on untrusted data; `subprocess(..., shell=True)`;
  f-string SQL; `eval` / `exec`; `assert` for security checks (stripped under `-O`).
- **JavaScript / TS:** `eval` / `new Function`; prototype pollution via deep-merge of
  untrusted JSON; `child_process.exec` with interpolation; `innerHTML`; ReDoS; a missing
  `await` on an authz check; npm typosquats.
- **Java:** native deserialization; XXE (disable external entities); reflection from input;
  SpEL/OGNL injection; `Runtime.exec` with strings.
- **Go:** `text/template` instead of `html/template` for HTML output; ignored errors on auth
  paths; SQL via `fmt.Sprintf`; `InsecureSkipVerify`.
- **C / C++:** buffer overflows, use-after-free, integer overflow, `strcpy`/`sprintf`,
  format-string bugs — prefer bounded APIs and run sanitizers.
- **PHP / Ruby:** `eval`, `system`, unsafe `unserialize` / `Marshal.load`, mass assignment,
  dynamic `include` from input.
- **SQL / ORM:** raw-query escape hatches (`.raw()`, `queryRaw`, `.extra()`) with interpolation.
