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
