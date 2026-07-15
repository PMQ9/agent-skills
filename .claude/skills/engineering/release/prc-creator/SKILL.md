---
name: prc-creator
description: >-
  Create a Product Readiness Checklist (PRC) — a structured, evidence-backed go/no-go across
  architecture, reliability, scalability, security, data & privacy, testing, observability,
  release, and ownership before a product, feature, or service ships. Use whenever someone is
  preparing to launch or release and wants to know if it's ready, or is planning something and
  wants a readiness checklist to track against. Trigger on "are we ready to launch,"
  "production readiness," "PRR," "launch checklist," "go/no-go," "pre-launch review,"
  "readiness review," "what's missing before we release," "is this production-grade," or when
  someone points at a repo/service and asks whether it's ready for real users — even when the
  word "checklist" is never used. Produces a markdown checklist in Assessment mode (inspect a
  real codebase and grade it) or Template mode (emit a tailored blank checklist to fill in).
  Draws on system-architecture, software-architect, cybersecurity-expert, full-stack-engineer,
  and test-planning.
---

# Product Readiness Checklist (PRC) Creator

A Product Readiness Checklist answers one question honestly: *can this survive contact with real users and real load?* It is a structured go/no-go across the dimensions that decide whether a launch goes smoothly or becomes an incident — architecture, reliability, scalability, security, data, testing, observability, release, and ownership.

The failure mode of readiness checklists is theater: a wall of green checkboxes that nobody actually verified, or a 200-item list where everything is "P0" and so nothing is. This skill exists to produce the opposite — a checklist where every item is scoped to the product, every judgment is backed by evidence, every finding is ranked by real impact, and the whole thing ends in a verdict a team can act on. A PRC that flatters the product is worse than none, because it launches the risk with a signed-off feeling of safety.

## Pick the mode first

The same catalog of concerns produces two very different deliverables depending on whether the thing exists yet.

**Assessment mode** — a codebase, service, or system exists. Inspect the actual artifacts (code, config, IaC, CI files, dashboards, docs, ADRs) and grade each applicable item with a status, the evidence you based it on, a severity, and a remediation. The output is a filled-in review that ends in a go/no-go verdict. Reach for this when the user points at a repo, says "review our service," "are we ready," or there's a running system to examine.

**Template mode** — the product is being planned or is mid-build with little to inspect. Emit a tailored blank checklist the team fills in and signs off, scoped to the product type so it isn't padded with irrelevant items. Reach for this when the user says "we're planning to build," "give me a launch checklist," or there's nothing concrete to examine yet.

**Hybrid is common and fine.** Some parts exist and some are planned. Assess what exists, template the rest — an item is either graded-with-evidence or an unchecked box with an owner.

Default: if artifacts are available, assess them; if not, produce a template. If it's genuinely unclear which the user wants, ask one question — don't guess wrong and produce the wrong artifact.

## Establish the product type and the bar (before writing anything)

Readiness is relative. A localhost prototype and an internet-facing payments service are held to different bars, and applying the wrong bar makes the checklist either paranoid or dangerously lax. Pin these early — infer from context and surface your assumptions rather than interrogating:

- **Product type** — web app, API / backend service, mobile app, data pipeline (batch/ETL/streaming), infra/platform service, or ML/LLM feature. This decides which items apply and which are N/A. See `references/product-profiles.md`.
- **Risk tier** — internet-facing? handles money or PII? regulated (GDPR/HIPAA/FERPA/PCI/SOC 2)? A higher tier promotes many items from "nice to have" to "ship-blocker."
- **Scale and launch shape** — expected load, launch timeline, blast radius if it breaks, team size and on-call reality.

State these at the top of the checklist. If a load-bearing one is unknown (e.g., "is this internet-facing?"), name the gap — the answer changes the severity of half the security dimension.

## Core principles

**Evidence over assertion.** In assessment mode, every judgment cites where you looked. "Looks secure" is not a finding; "`listOrders()` at `api/orders.ts:42` runs `SELECT * FROM orders` with no `WHERE user_id` — any authenticated user reads every tenant's orders" is. If you didn't verify something, mark it *Not assessed*, don't mark it Pass.

**Numbers, not adjectives.** "Fast," "scalable," "highly available" are wishes until they're numbers. Pin the SLO, the p99 latency budget, the throughput target, the RTO/RPO — or flag that the number is missing, which is itself a readiness gap.

**Right-size, and record what you skip.** Prune items that don't apply to the product type, but mark them `N/A` *with a one-line reason* rather than dropping them silently — the reason is part of the record, and it proves the item was considered, not forgotten.

**Rank by impact; separate blockers from cleanup.** Order findings Critical → Low. The verdict is driven by the open Critical/High items (the blockers), not by the raw count. Twelve Low findings and zero blockers is a launch; one unresolved Critical is not.

**An item without an owner is theater.** Every item that isn't Done or N/A needs a named owner. Unowned work doesn't happen, and a checklist of unowned work is a document that makes people feel ready without being ready.

**Subtraction beats padding.** A tight checklist that covers what matters beats an exhaustive one nobody finishes. Don't inflate the list to look thorough; cover the applicable items well and say plainly what you left out.

**Readiness is a verdict, not a vibe.** End with **Go / Go with conditions / No-go**, the specific blockers, and the conditions. A checklist that stops at a list of items forces the reader to do the actual judgment call the PRC was supposed to make.

## The dimensions

A complete PRC walks nine dimensions. Each is summarized in one line here; the full item list — with *why each matters* and *how to check it in assessment mode* — lives in `references/checklist-catalog.md`. Read that file before building the checklist; it is the substance of this skill.

1. **Architecture & Design** — boundaries, coupling, data ownership, ADRs, right-sized topology.
2. **Reliability & Resilience** — SLOs, failure modes, timeouts/retries/idempotency, rollback, backups, health checks.
3. **Scalability & Performance** — latency and throughput budgets, load testing, connection pooling, caching discipline.
4. **Security** — trust boundaries, authn/authz (incl. row-level scoping), secrets, dependencies/supply-chain, injection, encryption, audit.
5. **Data & Privacy** — the data contract, lossy conversions, backward-compatible migrations, backups/restore, compliance, PII handling.
6. **Testing & Quality** — coverage traced to requirements, the test pyramid, seam tests, negative/edge cases, stated gaps.
7. **Observability & Operability** — structured logs, metrics, traces, error tracking, SLO-based alerts, runbooks, on-call.
8. **Release & Deployment** — CI/CD, gated migrations, rollout strategy, one-action rollback, config/secrets per env, IaC.
9. **Documentation & Ownership** — architecture docs, API contract, ADRs, runbooks, a clear owner per component and integration.

To scope these to the specific product — which dimensions dominate, which items are commonly N/A — read `references/product-profiles.md`.

## Workflow

### Assessment mode

1. **Establish context** — product type, risk tier, scale, timeline (infer + surface assumptions). Set the bar.
2. **Gather artifacts** — the repo, config, IaC, CI/CD files, dependency manifests/lockfiles, migrations, dashboards, ADRs, runbooks. Note what you *couldn't* find; absence of an artifact is often the finding.
3. **Walk the catalog dimension by dimension.** For each applicable item, assign a status (Pass / Gap / Fail / N-A / Not assessed) with **evidence** (file:line, config snippet, or observation), a **severity**, and a **remediation**. Use `references/product-profiles.md` to skip or N/A items that don't apply.
4. **Rank and total.** Count findings by severity; identify the blockers (open Critical/High).
5. **Render the PRC** in the format below and compute the verdict. Save to `docs/readiness/<slug>.md` (or a path the user names). Finish by naming the top blockers and which domain skill to pull in for each.

### Template mode

1. **Establish product type, risk tier, target launch.**
2. **Select the applicable items** from the catalog + product profile. Drop or `N/A` (with reason) the ones that don't apply.
3. **Emit a blank checklist** — each item an unchecked box with its *why*, a priority, an owner field, and an evidence/notes field to fill in.
4. **Add a sign-off block** (one row per dimension owner) and a verdict placeholder.
5. **Save** to the path the user names and point out which items usually need the most work for this product type.

## Output format

Adapt the depth to the product, but keep this skeleton so PRCs are comparable across products and re-runnable near launch.

```markdown
# Product Readiness Checklist — <product / feature>

**Mode:** Assessment | Template | Hybrid
**Product type:** <web app | API/service | mobile | data pipeline | infra/platform | ML-LLM>
**Risk tier:** <prototype/internal | internet-facing | money/PII | regulated: NAME>
**Reviewer(s):** <name>   **Date:** YYYY-MM-DD   **Target launch:** <date or TBD>

## Verdict

**<GO | GO WITH CONDITIONS | NO-GO>**

Blockers (must clear before launch): <list, or "none">
Conditions / follow-ups: <list, or "none">

## Summary

| Dimension | Status | Critical | High | Med | Low |
|---|---|---|---|---|---|
| Architecture & Design | ⚠️ Gaps | 0 | 1 | 2 | 0 |
| Reliability & Resilience | ❌ Blocked | 1 | 1 | 0 | 1 |
| ... | ... | | | | |

Legend: ✅ Pass · ⚠️ Gaps · ❌ Blocked · ➖ N/A · ☐ Not assessed

## <Dimension name>

<!-- Assessment mode: graded items -->
#### [HIGH] Every data query is scoped to the authenticated principal — ❌ Fail
- **Evidence:** `api/orders.ts:42` — `SELECT * FROM orders` with no tenant filter.
- **Risk:** any logged-in user retrieves every tenant's orders (cross-tenant data leak).
- **Remediation:** add `WHERE user_id = $currentUser`; add an integration test with two tenants.
- **Owner:** @backend-lead

<!-- Template mode: blank items -->
- [ ] **Every data query is scoped to the authenticated principal** (Critical) — prevents silent cross-tenant data leaks — Owner: ___ — Evidence/Notes: ___

## Sign-off

| Dimension | Owner | Signed off | Date |
|---|---|---|---|
| Security | | ☐ | |
| ... | | ☐ | |
```

### Severity rubric

Anchor severity to **impact × likelihood**, not to how unusual the issue is.

- **Critical** — ship-blocker. Data loss/corruption, breach, cross-tenant leak, guaranteed outage under normal load, or a legal/compliance violation. The launch does not go until this clears.
- **High** — significant risk; fix before launch or immediately after with a mitigation in place. Missing rollback, no backups restore-tested, no auth on a sensitive endpoint.
- **Medium** — real but survivable; schedule it. Missing alerts on a secondary path, thin test coverage on a non-critical flow.
- **Low** — cleanup, hardening, polish.
- **Info** — worth noting, no action required.

The verdict follows mechanically: any open **Critical** ⇒ No-go; open **High** ⇒ Go with conditions (named mitigations + owners) at most; only Medium/Low open ⇒ Go.

## Handoffs — the PRC is the map, not the whole journey

The PRC finds and ranks the gaps; the depth work belongs to the specialist skills. When a flagged item needs real design or fix work, name the skill and invite the user to pull the thread:

- `system-architecture` — service boundaries, coupling, sagas, scaling topology, migrations between systems.
- `software-architect` — module boundaries, dependency direction, domain modeling, refactoring a tangled area.
- `cybersecurity-expert` — threat modeling and secure code review on any security finding.
- `full-stack-engineer` — the seams (data contract, auth across layers, backward-compatible rollout) and end-to-end wiring.
- `test-planning` — turning a coverage gap into an actual test plan traced to requirements.
- Others when present: `devops-cicd` (pipelines, rollout), `observability` (logs/metrics/traces/alerts), `api-design` (HTTP surface), `database-design` (schema/indexes/migrations), `ai-solution-architect` / `prompt-injection-defense` (ML/LLM features).

A good PRC ends by pointing at the two or three skills that will do the most good on the biggest gaps.

## Anti-patterns to avoid

- **Green theater** — items marked Pass that were never actually verified. If you didn't check it, it's *Not assessed*.
- **The all-P0 list** — everything Critical means nothing is. Rank honestly; most items are Medium/Low.
- **Adjectives instead of numbers** — "scalable," "fast," "secure" with no SLO, budget, or threat model behind them.
- **Unowned items** — a checklist of work nobody owns is a wish list.
- **Wrong bar** — grading a prototype at payments-grade, or a payments service at prototype-grade. Set the risk tier first.
- **Padding** — items copied in that don't apply to the product type, drowning the ones that do. Prune, and mark N/A with a reason.
- **One-and-done** — a PRC written once at the start and never re-run. Re-run it near launch when the artifacts are real.
- **Findings without remediation** — naming a gap without the smallest correct fix leaves the reader stuck. Every Fail/Gap gets a next step.
