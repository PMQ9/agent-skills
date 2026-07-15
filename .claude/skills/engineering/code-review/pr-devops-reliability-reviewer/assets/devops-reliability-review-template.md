# 🚀 DevOps / Operations / Reliability Review

**Reviewer role:** DevOps / Operations / Reliability Reviewer
**Model:** <!-- e.g. Claude Opus 4.8 / Claude Sonnet 5 / DeepSeek-V3 / GPT-5 — the model performing this review -->
**PR / change:** <!-- #123 — title, or file/branch reviewed -->
**Date:** <!-- YYYY-MM-DD -->

## Verdict

**<!-- ✅ Approve | 💬 Comment | 🔴 Request changes -->**

<!-- One or two sentences: is this safe to deploy and operate, and if not, what's the blocker? -->

## Blast radius

<!-- 1-3 sentences sizing the operational risk: what does this change actually
affect in production? Config-only? A schema migration? A new external dependency?
A pipeline change gating every deploy? This frames how deep the review needs to
be. -->

## Summary

<!-- 2-4 sentences. What the change does operationally (in your words, to show you
understood the intended deploy/rollout), and the headline result: safe to operate,
or N findings including M critical. -->

## Findings

<!-- One entry per issue, ordered by severity (Critical first). If there are no
findings, write "No operational issues found." and rely on the checklist below to
show what was examined. Delete the example. -->

### 🔴 Critical | 🟠 Major | 🟡 Minor | 🔵 Question — <short title>

- **Area:** <!-- Infrastructure | Reliability | Observability | Deployment | Operations -->
- **Location:** `path/to/file.ext:LINE` <!-- manifest / module / pipeline stage -->
- **Problem:** <!-- What is operationally wrong. -->
- **Production scenario:** <!-- The concrete situation that makes it bite, e.g. "when the upstream API is slow", "during the rolling deploy when v1 and v2 are both live", "when this migration runs against the 40M-row table". -->
- **Consequence:** <!-- What breaks: outage / failed deploy / can't roll back / silent data loss / leaked secret / on-call has no signal. -->
- **Suggested fix:** <!-- Specific, minimal change. Config snippet / manifest key / command if helpful. -->

<!-- Example:
### 🔴 Critical — Outbound call to payments API has no timeout
- **Area:** Reliability
- **Location:** `services/checkout/client.py:88`
- **Problem:** `requests.post(PAYMENTS_URL, json=payload)` uses no timeout, so it inherits the default of "wait forever".
- **Production scenario:** Payments API degrades and starts hanging (not erroring).
- **Consequence:** Checkout worker threads block indefinitely, the pool exhausts, and the entire checkout service stops responding — a full outage triggered by a partial dependency failure.
- **Suggested fix:** Pass `timeout=(3, 10)` (connect, read) and wrap in a retry-with-backoff + circuit breaker so a slow dependency degrades gracefully instead of taking the service down.
-->

## What I checked and considered fine

<!-- Builds trust and shows the review was thorough. Check the lenses you traced
that held up. Delete rows that don't apply to this change. -->

**Infrastructure**
- [ ] Environment variables (all referenced vars are set; no missing/typo'd keys)
- [ ] Secrets management (no hardcoded/committed/logged secrets; sourced from a vault/secret store)
- [ ] Configuration (defaults sane; config validated; no environment-specific values baked in)
- [ ] Containerization (non-root, pinned base image, resource limits, small attack surface)
- [ ] Kubernetes manifests (liveness/readiness probes, requests/limits, rollout strategy)
- [ ] Terraform changes (plan reviewed; no unintended force-replacement/destroy of stateful resources)
- [ ] CI/CD updates (pipeline still gates correctly; no leaked credentials; no broken deploy path)

**Reliability**
- [ ] Timeouts on every network/IO call
- [ ] Retries bounded, with backoff + jitter, only on retryable errors
- [ ] Circuit breakers / bulkheads where a dependency can drag the service down
- [ ] Graceful degradation when a dependency is unavailable
- [ ] Idempotency for anything that can be retried or redelivered
- [ ] Resource cleanup on all paths (connections, files, locks, goroutines/threads)

**Observability**
- [ ] Logging (right level, structured, no secrets/PII, not spammy)
- [ ] Metrics for new code paths and failure modes
- [ ] Tracing / correlation IDs propagated
- [ ] Alerting implications considered (new failure modes are alertable)
- [ ] Error messages actionable (say what failed and what to do)

**Deployment**
- [ ] Backward compatibility during the rollout window (old + new run together)
- [ ] Database migration safety (non-blocking, expand/contract, reversible)
- [ ] Zero-downtime deployment (no flag-day coupling of code + schema + config)
- [ ] Feature flags used to decouple deploy from release where risky
- [ ] Rollback strategy exists and actually works (not blocked by migrated data)
- [ ] Config compatibility (new config optional/defaulted; old config still valid)

**Operations**
- [ ] Monitoring covers the new surface (dashboards/SLOs exist)
- [ ] Operational complexity justified (not adding a moving part for little gain)
- [ ] Failure modes understood and bounded
- [ ] Scalability at expected + 10x load
- [ ] Runbook / recovery steps updated for new failure modes

## Open questions for the author

<!-- Anything you couldn't confirm from the diff alone: how a var gets set in the
target environment, the actual row count a migration will run against, whether a
rollback path exists. Omit if none. -->
