# Product Profiles & Risk Tiers

Use this to scope the checklist: which dimensions dominate for a given product type, which catalog items are commonly N/A (mark them N/A *with the reason from here*, don't drop them silently), and which type-specific items to add. Then apply the risk-tier modifier, which decides how harsh the bar is.

A good PRC is the intersection of *product type* (what applies) and *risk tier* (how strict). Get both before grading.

## Risk tiers (the bar)

The tier promotes items from optional to mandatory and raises severities. Pick the highest that applies.

- **Prototype / internal, low-risk.** Demo, internal tool, no real user data, easy to take down. Bar: correctness and "don't lose data." Most Security/Compliance items are Low or N/A; a Fail on rollback is Medium, not Critical. Don't paranoia-grade a throwaway.
- **Internet-facing, no sensitive data.** Public but not handling money/PII. Bar: the full Reliability/Scalability/Observability/Release set matters; Security is High-weighted (it's exposed); Compliance mostly N/A.
- **Handles money or PII.** Payments, health, personal data. Bar: Security and Data & Privacy items are Critical/High by default; audit logging, encryption, least privilege, restore-tested backups become ship-blockers.
- **Regulated (GDPR / HIPAA / FERPA / PCI-DSS / SOC 2).** Everything above plus the named regime's specific controls (residency, retention, right-to-erasure, consent, formal audit, access reviews). Compliance gaps are Critical. Note the specific regime in the header.

Rule of thumb: the same missing-backup finding is Low on a prototype, High on an internet-facing app, and Critical on a money/PII service. Set the tier first so severities are consistent.

## Web app (browser frontend + backend)

- **Dominant dimensions:** Security (auth, XSS, cookies), Data contract (frontend↔backend seam), Reliability, Observability, Release (backward-compatible frontend+API rollout).
- **Add these items:** session token in `HttpOnly` cookie (not `localStorage`); XSS/output-encoding and a Content-Security-Policy; loading/error/empty states as first-class UI; Core Web Vitals budget (LCP < 2.5s, INP < 200ms, CLS < 0.1); static assets on a CDN with content-hashed filenames; accessibility (keyboard nav, screen-reader labels, focus management, color-not-the-only-signal) — pull in `accessibility-wcag` if present.
- **Commonly N/A:** data-pipeline items (lineage, backfill), some infra/platform items.

## API / backend service (no first-party UI)

- **Dominant dimensions:** API contract & versioning, Reliability (idempotency, timeouts), Scalability (throughput, pooling), Security (authz scoping, rate limiting), Observability.
- **Add these items:** consistent response *and error* envelope (`{error:{code,message,fields}}`, never a bare 500 with a stack trace); pagination on every list endpoint; idempotency keys on retryable writes; explicit API versioning + deprecation policy; consumer-driven contract tests; per-client rate limits and quotas. Hand off to `api-design`.
- **Commonly N/A:** browser-cookie/XSS/CSP items, accessibility, Core Web Vitals.

## Mobile app (iOS / Android client + backend)

- **Dominant dimensions:** Security (on-device secrets, transport), Release (store review + forced-upgrade), Observability (crash reporting), Reliability (offline/sync).
- **Add these items:** secrets in Keychain/Keystore, never in the bundle or source; certificate pinning for sensitive apps; offline behavior and sync/conflict resolution; forced-upgrade / minimum-supported-version path for breaking API changes; crash reporting (Crashlytics/Sentry) with symbolication; app-store review and privacy-nutrition/permission disclosures; backward-compatible APIs (old app versions live in users' hands indefinitely).
- **Commonly N/A:** server-side autoscaling for the *client*; CSP; CDN of app assets (store handles distribution). The *backend* the app talks to is still assessed as an API service.

## Data pipeline (batch / ETL / streaming)

- **Dominant dimensions:** Data & Privacy (quality, schema evolution, lineage), Reliability (idempotent + replayable jobs), Observability (freshness/lag), Scalability (volume).
- **Add these items:** data-quality checks and validation at ingestion (schema, ranges, null rates); idempotent and *replayable* jobs (safe re-runs, backfill strategy); schema evolution handling (new/renamed/removed fields); late-arriving and duplicate data handling; watermarks/checkpoints for streaming; a freshness/latency SLA and lag alerting; lineage/provenance so a bad number can be traced; partition/backfill cost at volume.
- **Commonly N/A:** browser auth/cookies/XSS, accessibility, Core Web Vitals, end-to-end UI flows.

## Infra / platform service (something other teams build on)

- **Dominant dimensions:** Reliability (you're a dependency — your SLO caps everyone's), Security (control-plane, multi-tenancy), API/contract stability, Documentation (self-serve).
- **Add these items:** strict multi-tenant isolation and per-tenant quotas (noisy-neighbor); backward-compatibility guarantees and a deprecation policy for platform APIs (consumers can't all migrate at once); a customer-facing upgrade/migration path; blast-radius limits (a bad rollout can't take down all tenants at once); control-plane security and least privilege; capacity headroom and clear limits; excellent docs (the product *is* the interface).
- **Commonly N/A:** UI/accessibility/Core Web Vitals items.

## ML / LLM feature

Assess the surrounding software as its underlying type (usually API service or web app), then add the model-specific items. Hand off to `ai-solution-architect`, `agent-design`, and `prompt-injection-defense` if present.

- **Add these items:** an offline eval set with a target metric (not vibes) and a regression gate; online quality monitoring and drift detection; a fallback when the model is slow, down, or low-confidence; prompt-injection defense and trust boundaries for any untrusted content fed to the model (treat model I/O as a trust boundary); human-in-the-loop / approval gates for high-impact actions; output validation and safe handling of tool calls; cost and latency budgets per request (LLM calls are slow and metered); data governance for prompts/training data (PII, retention, no sensitive data in logs); guardrails and abuse/rate limiting.
- **Commonly N/A:** nothing extra to drop — this is additive on top of the base type.

## How to use this in the workflow

1. Identify the product type and pick the profile above.
2. Set the risk tier; that fixes default severities.
3. Start from the full catalog, **add** the profile's type-specific items, and **N/A** (with the profile's reason) the ones this type doesn't touch.
4. Grade (assessment) or emit boxes (template) for what remains.
5. If a product genuinely spans types (e.g., a web app backed by a data pipeline), take the union of the relevant profiles and note it in the header.
