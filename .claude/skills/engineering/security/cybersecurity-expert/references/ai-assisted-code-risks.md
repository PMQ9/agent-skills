# AI-Assisted Code Risks

Most new code is now written with AI assistance, and it fails in distinct, predictable ways.
Independent 2026 analyses put AI-generated code at roughly **2.7x the vulnerability density**
of human-written code, with elevated rates of injection, XSS, hardcoded secrets, and
broad-privilege patterns. The good news: because the failure modes are systematic, they're
checkable. Treat any AI-assisted code (which is most code) as needing these specific passes
*in addition to* the standard review in `secure-code-review.md`.

## Why AI code is riskier — the root causes

1. **It reproduces its training data, insecure parts included.** Models emit the *common*
   pattern, and the common pattern on the internet is often the insecure one (string-built
   SQL, `Math.random()` tokens, missing authz). Plausible-looking code is not safe code.
2. **It omits controls you didn't ask for.** A model asked to "add a file upload" produces an
   upload — not necessarily size limits, type validation, path confinement, or authz, unless
   prompted. The vulnerability is in the *absence*, which a diff-focused reviewer can miss.
3. **It is confidently wrong.** Output reads as authoritative regardless of correctness, which
   lowers reviewer skepticism exactly when it should be highest.
4. **It hallucinates external facts**, including package names — the basis of slopsquatting.

## Slopsquatting / package hallucination (supply chain)

LLMs invent plausible-but-nonexistent dependency names. Attackers register those names with
malware, so an `npm install` / `pip install` of a hallucinated package runs attacker code on
the dev machine and in CI. This is now a primary supply-chain vector for AI-assisted projects.

**Check before installing any AI-suggested dependency:**
- Does the package actually exist on the registry, and is it the *real* one (not a typo-twin)?
- Reasonable download counts, age, maintainers, repo, and recent releases — not a brand-new
  package with zero history matching exactly what the model "remembered"?
- Is the name suspiciously close to a popular package (typosquat) or just made up?
- Pin and lock versions; verify integrity hashes; scan with a dependency scanner.

When reviewing, treat every newly added import/require as a claim to verify, not a given.

## Prompt injection that reaches code

When an LLM or agent processes untrusted content (a web page, an issue/PR description, a file,
a tool result) and that content carries instructions, those instructions can change what the
model writes or does. In 2026 this graduated from theory to CVEs: hidden instructions in a
pull-request description drove an AI coding assistant to insert attacker-chosen behavior,
yielding remote code execution (CVE-2025-53773, CVSS 9.6). Assessments find a majority of
tested AI systems exploitable via prompt injection.

Defensive review points for any system where a model influences code or takes actions:
- **Trust boundary:** content fed to the model is untrusted input. Don't grant the model (or
  its tools) authority that untrusted content could redirect — minimal tools, minimal
  permissions, human approval on high-impact actions (OWASP "excessive agency").
- **Don't let model output flow unchecked into a sink.** Generated commands, queries, file
  paths, and especially auto-applied code edits need the same validation as any other
  untrusted input. "The AI wrote it" is not a trust credential.
- **Isolate and constrain** the execution environment (sandbox, no ambient credentials), so a
  successful injection is contained. See the prompt-injection-defense material for depth.

## The systematic review pass for AI-assisted code

Run these checks specifically, because they target where AI code reliably fails:

1. **Injection sinks:** is every query parameterized, every command using an arg array, every
   path confined? Models default to the unsafe string-built form.
2. **Missing controls:** for each new feature, list the controls it *should* have (authz,
   input validation, size/rate limits, output encoding) and confirm each is present. Absence
   is the bug.
3. **Secrets:** grep the diff for keys, tokens, passwords, connection strings. AI code shows a
   measurably higher rate of hardcoded secrets (~40% more in some 2026 datasets).
4. **Crypto and randomness:** flag `Math.random()`/`rand()` for tokens, plain hashes for
   passwords, disabled TLS verification, home-rolled crypto.
5. **Authz on data access:** AI scaffolds CRUD that authenticates but rarely checks ownership
   → IDOR/BOLA by default.
6. **Dependencies:** verify every added package exists and is genuine (slopsquatting, above).
7. **Over-broad permissions:** AI-generated IaC/IAM trends toward `*` and wide scopes; tighten
   to least privilege.
8. **Error handling that fails open:** check that auth/validation failures deny rather than
   fall through.

## How to phrase the finding

Tie it back to the cause so the human recalibrates trust: "This is the classic AI-generated
pattern — the query is correct functionally but built by string concatenation, so it's a SQL
injection. AI assistants emit this constantly because it's the most common pattern in training
data. Use a parameterized query." The lesson (be skeptical of plausible AI output near a sink)
generalizes far beyond this one line.
