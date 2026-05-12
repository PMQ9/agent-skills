# Shared `docs/` convention

A versioned, traceable system for capturing what we're building, why, and how decisions map to implementation. The convention exists so that any person or skill picking up the work months later can answer "why does this code exist?" by following a chain of stable IDs from implementation back to a specific requirement.

This is not optional decoration. It is the coordination contract that lets requirements-analyst, system-architecture, test-planning, devops-cicd, and backend-development hand off work to each other without losing context.

## Layout

```
docs/
├── requirements/
│   ├── <feature-slug>/                # ← a spec is a directory, not a file
│   │   ├── _overview.md               # Summary, Problem, Users, Goals, Non-goals, Notes, Linked artifacts
│   │   ├── functional.md              # FN-NNN — what the system does
│   │   ├── security.md                # SEC-NNN — auth, authz, threats, data classification
│   │   ├── safety.md                  # SAF-NNN — physical-world or human-safety constraints
│   │   ├── performance.md             # PERF-NNN — latency, throughput, response time bars
│   │   ├── availability.md            # AVAIL-NNN — uptime, RTO, RPO
│   │   ├── compliance.md              # COMP-NNN — feature-specific regulatory obligations
│   │   ├── usability.md               # UX-NNN — observable user-experience standards
│   │   ├── accessibility.md           # A11Y-NNN — WCAG / Section 508 / EN 301 549
│   │   └── constraints.md             # CON-NNN — technical, organizational, or budgetary constraints
│   └── _policies/                     # cross-cutting requirements cited by many features
│       ├── security-baseline.md       # SEC-NNN in the security-baseline namespace
│       ├── uptime-sla.md              # AVAIL-NNN system-wide
│       └── ferpa-handling.md          # COMP-NNN institutional standards
├── adr/
│   └── NNNN-<adr-slug>.md             # numbered globally, append-only
├── test-plans/
│   └── <feature-slug>.md              # one unified plan per feature (not split by category)
├── runbooks/
│   └── <runbook-slug>.md
└── system/
    └── overview.md                    # optional high-level overview
```

## Why a spec is a directory, not a file

Different requirement categories have different owners (security review reads `security.md`; ops reads `availability.md`; product reads `functional.md`), different audit / regulatory implications, and different lifecycles. Stuffing them into one file makes a security audit walk through every functional requirement and forces a cross-cutting compliance rule to duplicate across many feature files.

Splitting also creates a clean place for cross-cutting policies (FERPA standards, the org's uptime SLA, the baseline security requirements every feature inherits) so they aren't repeated in 30 feature spec sheets.

## Required vs optional category files

`_overview.md` is **always** present. It's the narrative entry point: Summary, Problem, Users, Goals, Non-goals, project-level Notes, project-level Linked Artifacts. The narrative does not contain requirements; it points at the category files where the requirements live.

Category files are **created only when needed**. A feature that has zero security requirements doesn't have `security.md`. Don't pre-create empty files to feel tidy. For a small feature with two functional requirements and nothing else, `_overview.md` may include a `## Requirements` section directly and skip the category split — explicitly call this out at the top: "this spec is small enough to stay in `_overview.md`; if it grows, split."

The trigger to split: when a category accumulates three or more requirements, or when the category's stakeholders are different from the rest of the spec's audience, promote it to its own file.

## ID prefixes (typed, per-spec, monotonic within the file)

| Prefix | Category       | Lives in           |
|--------|----------------|--------------------|
| FN     | Functional     | `functional.md`    |
| SEC    | Security       | `security.md`      |
| SAF    | Safety         | `safety.md`        |
| PERF   | Performance    | `performance.md`   |
| AVAIL  | Availability   | `availability.md`  |
| COMP   | Compliance     | `compliance.md`    |
| UX     | Usability      | `usability.md`     |
| A11Y   | Accessibility  | `accessibility.md` |
| CON    | Constraint     | `constraints.md`   |

Each prefix is zero-padded, three digits, monotonically increasing **within the file it lives in**. `FN-001`, `FN-002`, ... can coexist with `SEC-001`, `SEC-002`, ... in the same spec directory because the prefix disambiguates.

Numbering does not reset; requirements are append-only. Deleted requirements are *not* removed — they are marked superseded and the new requirement gets the next ID (see "Append-only" below).

**ADRs** keep their own global numbering: `ADR-NNNN`, four digits, monotonic across the project.

**Test cases** keep `T-NNN` per test plan.

## Citation form

The shape that downstream artifacts use to reference requirements:

- **Inside a feature:** `<feature-slug>#FN-007`, `<feature-slug>#SEC-003`, `<feature-slug>#PERF-002`. The category is implicit in the prefix; the file is implicit in the prefix.
- **Cross-cutting policy:** `_policies/<policy-slug>#SEC-001`, `_policies/uptime-sla#AVAIL-003`.
- **ADR:** `ADR-0007`.
- **Test case:** `<feature-slug>/T-005`.
- **Code citation:** `<feature-slug>#FN-007` in commit messages and comments where the *why* would otherwise be invisible.

A reader sees `bulk-csv-import#SEC-004` and knows: it lives in `docs/requirements/bulk-csv-import/security.md`, it's the 4th security requirement, the security team likely reviewed it.

## Cross-cutting policies

A policy lives in `docs/requirements/_policies/<policy-slug>.md` when:

- The requirement applies to many features, not just one (e.g., "all features that handle student records must X").
- The requirement is owned by a non-feature stakeholder (a security architect, a compliance officer, an SRE org-wide SLA).
- The requirement is institutional: it predates and outlives any single feature.

A feature spec **inherits and cites** policy requirements; it does not duplicate them. In the feature's `compliance.md` or `security.md`, a requirement can be a thin reference:

```markdown
### COMP-001 — Inherits FERPA handling policy

- **Type:** Compliance
- **Status:** Accepted
- **Statement:** This feature complies with all requirements in
  `_policies/ferpa-handling.md` (specifically COMP-001, COMP-002, COMP-005).
- **Rationale:** Feature processes student records.
- **Acceptance criteria:**
  - AC-1: All ACs of the inherited policy REQs are satisfied for this feature.
- **Linked artifacts:** (filled by downstream)
```

This is the difference between policy-as-citation (good — one source of truth) and policy-as-copy-paste (bad — divergent versions across features). Test plans test the policy REQs at the policy level once and reference the test from each feature that cites the policy.

## Append-only discipline

The single most important rule. Specs, ADRs, and test plans grow monotonically. **Never delete or rewrite an issued ID.**

When a requirement is no longer correct:

```markdown
### SEC-004 — All admin actions logged to syslog  [Superseded by SEC-012]

**Status:** Superseded — 2026-05-20
**Original statement:** (preserved as written below)
> All admin actions shall be logged to the host's syslog facility within 1s.

**Superseded because:** Logging strategy revised after ADR-0011 chose structured
JSON logs to S3, not syslog. See SEC-012 and N-004 for rationale.
```

The original text stays. The reader sees both the new requirement and the prior one, with the reason for the change. Git tracks edits to the file; the doc tracks the *semantic* history of the work.

When a constraint changes the meaning of a requirement subtly, prefer adding a Note (N-NNN) inside the REQ over editing the REQ text. Notes preserve the original wording.

Editing typos, formatting, status fields, and metadata in place is fine. Editing requirement statements, decisions, acceptance criteria, or rationale is not.

## Citation: how artifacts reference each other

The skill of "professional coordination" is **citing what motivates your work, by ID, every time**.

- An **ADR** opens with `Addresses: <slug>#FN-NNN, <slug>#SEC-NNN[, ...]` in its front matter. The ADR exists because of these requirements; if it doesn't address any, it probably doesn't belong in the project's ADR log.
- A **test case** declares `Covers: <slug>#FN-NNN[, ...]` in its block. Tests not tied to a requirement are either checking implementation details (delete or convert to unit test) or revealing a missing requirement (add it).
- A **runbook** declares `Implements: <slug>#AVAIL-NNN[, ...]; Per: ADR-NNNN[, ...]`. If the procedure isn't implementing a requirement and isn't following an ADR, it's either ad-hoc work that should be automated or institutional knowledge that should be promoted to an ADR or policy.
- **Code references** cite `<slug>#FN-NNN` in commit messages and PR descriptions, and in code comments only where the *why* would otherwise be invisible.

`_overview.md` has a `Linked artifacts` section at the bottom. Downstream artifacts **append** themselves there: when an ADR is written, it appends `- ADR-NNNN — <title>` to the overview's Linked artifacts. Each category file's individual REQ block also has a Linked artifacts sub-field, populated by downstream skills.

## The strict templates

Every artifact uses a fixed template. Templates live in their respective skill files:

- Overview file (`_overview.md`) → requirements-analyst
- Category files (`functional.md`, `security.md`, ...) → requirements-analyst
- Policy file (`_policies/<slug>.md`) → requirements-analyst
- ADR → system-architecture
- Test plan → test-planning
- Runbook → devops-cicd

If a skill produces an artifact and the template doesn't fit, the right move is to surface the mismatch and decide whether to extend the template (in the skill, deliberately), not to silently deviate.

## Gate model: skills don't run on thin air

Each downstream skill checks the prior artifact before producing its own. If the upstream is thin, the right move is to **push back**, not to fabricate the missing content.

- **system-architecture** checks: `_overview.md` exists, at least one category file has accepted requirements, no Open Questions block the architectural decision being made, requirements cited have unambiguous Statements and ACs.
- **test-planning** checks: every requirement has at least one testable AC, no AC contains unqualified adjectives ("fast", "user-friendly"), referenced policies exist and have their own tests.
- **devops-cicd** checks: at least one operational requirement (AVAIL-NNN, PERF-NNN, COMP-NNN) exists or the relevant policy is cited.
- **backend-development** checks: `_overview.md` + the category files relevant to the implementation exist, test plan covers the requirements being implemented.

The gate model is the discipline. Skipping a gate is fine when the change is small enough that the artifact would be longer than the work; doing it because nobody noticed is not.

## Length is determined by complexity

There are no line counts on any artifact. A two-section spec for a small change is correct; a 40-page spec spread across a directory of category files is correct. The wrong size is the one driven by a rule rather than the work.

## When `docs/` doesn't exist yet

If a skill wants to write an artifact and `docs/` doesn't exist, ask the user:

> "Want me to set up `docs/` for traceable specs, ADRs, and test plans? Each artifact carries typed IDs (FN-, SEC-, AVAIL-, ...) that other skills cite, so we can answer 'why does this exist?' months later. Or I can keep this output in the chat."

If they decline, the skill answers in chat. Don't create empty scaffolding to feel tidy.

## When the project already has a different convention

Follow the project's. The discipline that matters is typed IDs + append-only + cite-on-use + cross-cutting policies. The exact directory layout, ID prefixes, and template fields are negotiable; the discipline is not. If the project uses `RFC-` instead of `ADR-` or `R-` instead of `FN-`, follow that.
