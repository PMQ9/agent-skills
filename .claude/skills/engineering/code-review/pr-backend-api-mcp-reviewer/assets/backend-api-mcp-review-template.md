# 🔌 Backend / API / MCP Review

**Reviewer role:** Backend / API / MCP Reviewer
**Model:** <!-- the model performing this review -->
**PR / change:** <!-- #123 — title -->
**Date:** <!-- YYYY-MM-DD -->
**Surfaces:** <!-- MCP server (transport; SDK + spec revision) · HTTP API · service internals — or "none" -->
**Contract check:** <!-- performed — <what you ran> | static — <why> | not applicable -->

## Verdict

**<!-- ✅ Approve | 💬 Comment | 🔴 Request changes -->**. <!-- One sentence: can callers rely on this after merge? The blocker, if any. -->

## Summary

<!-- 2–3 sentences: what the change exposes, and the worst thing a caller hits. -->

## Findings

<!-- Group under the lenses present; omit empty groups. Critical/Major: ≤ ~5 lines each. Minor/Question: one line each.
Out-of-lane defects with concrete harm go here at full severity, tagged "(also: <owner lens>)".
If the brief asks for Priority/merge-blocking/DOCS labels, append them to each heading. -->

### MCP server

#### 🔴 Critical — <title> · `file:line`
**Problem:** <!-- what's wrong + the concrete trigger -->
**Caller impact:** <!-- what the model / client / attacker experiences -->
**Fix:** <!-- smallest change; snippet only if unavoidable, ≤ 8 lines -->

### HTTP API contract

### Service semantics

### Minor / questions

- 🟡 <!-- one line: location — issue — fix -->
- 🔵 <!-- one line: what you couldn't confirm -->

## Checked

<!-- Marks only: ✅ clean · ⚠️ finding · – n/a. Keep rows for surfaces present.
✅ means none of your findings touches that row — a row with any related finding is ⚠️. -->

| MCP | |
|---|---|
| selection & descriptions (cold-read) · schemas · errors reach model · bounded output | |
| annotations truthful · destructive/money ops guarded · scope contained · no secrets via params/elicitation | |
| transport (stdout / Origin / state-as-auth) · auth (audience, no passthrough) · revision-specific rules · evolution | |

| HTTP API | |
|---|---|
| breaking changes · status codes · error envelope · shapes & types | |
| pagination (clamped, unique cursor) · idempotency as implemented · concurrency (ETag/If-Match) · OpenAPI matches code | |

| Service semantics | |
|---|---|
| retried · redelivered · interrupted halfway · raced by a twin | |
| transactions · dual writes/outbox · outbound calls · cache correctness | |

## Deferred to other reviewers

<!-- Only unverified observations whose harm you can't state. One line each. Delete if empty. -->

## Open questions for the author

<!-- Omit if none. -->
