---
description: Evaluate every SKILL.md as both a domain expert and an AI/skill-design researcher, parallelized across sub-agents.
argument-hint: "[optional path filter under .claude/skills/, e.g. engineering/backend]"
---

# Evaluate every skill in this library

You are auditing the SKILL.md files in this repo. Each SKILL.md is loaded by Claude Code agents at runtime, so you must judge each file on **two axes simultaneously**:

1. **Domain expert** — wear the hat of a senior practitioner in the skill's domain (15+ years). Evaluate technical accuracy, currency (today's date is the system date), completeness, and snippet correctness. Flag anything wrong, outdated, deprecated, or misleading. Be specific about versions, RFCs, retired services, and security defaults.
2. **AI / skill-design researcher** — evaluate whether the file is well-designed for an LLM agent. Is the YAML `description` a clear trigger? Is the body actionable instructions vs textbook prose? Does it have pattern-matchable code snippets? Right size (not bloated, not skeletal)? Does it route cleanly to sibling skills?

## Procedure

**Step 1 — Discover.** Run `find .claude/skills -name SKILL.md -type f | sort` from the repo root. If `$ARGUMENTS` is non-empty, restrict to paths matching it. Read `README.md` to understand the catalog and stated philosophy ("bias toward fewer, broader skills; split only when sub-area has materially different guidance").

**Step 2 — Cluster.** Group the skills by their parent directory (e.g. `engineering/architecture/*`, `engineering/backend/*`, `engineering/cloud/*`, `engineering/data/*`, `engineering/devops/*` + `engineering/iac/*`). One cluster per sub-agent.

**Step 3 — Dispatch in parallel.** Spawn one `general-purpose` sub-agent per cluster **in a single message with multiple Agent tool calls** so they run concurrently. Each sub-agent prompt must:
- State both hats explicitly (domain expert + AI/skill-design researcher).
- List the absolute paths of the SKILL.md files in its cluster and tell the agent to read each in full.
- Include relevant 2026-current context for the cluster's domain (current versions, recently deprecated APIs, security-default changes, modern best practices).
- Reference `README.md` for catalog conventions.
- Demand a structured deliverable per skill:
  ```
  ### <skill-name>
  **Domain-expert verdict:** [A-F] — one-line headline.
  - Technical issues found: [bullets with file:line refs]
  - Missing/outdated content: [bullets]
  - Currency check: [stale items]
  - Snippet quality: [idiomatic/runnable?]

  **AI-skill-design verdict:** [A-F] — one-line headline.
  - Frontmatter / trigger quality
  - Structure & actionability
  - Size / signal density
  - Routing clarity (overlap with siblings)

  **Top 3 concrete fixes:** [imperative bullets]
  ```
- Demand a closing **Cross-cutting observations** section per cluster (composition, redundancy, missing skills in the cluster).
- "Be specific, cite file paths with line numbers, no sycophancy, tight — no filler."

**Step 4 — Synthesize.** Once all sub-agents return, write the final report to the user with these sections, in order:

1. **Grades at a glance** — markdown table of every skill with two columns: Domain grade, AI-design grade. Use clickable markdown links: `[skill-name](.claude/skills/.../SKILL.md)`.
2. **Highest-impact technical fixes (per skill)** — one short paragraph per skill, leading with the most consequential fixes and citing `file:line` via clickable `[path](path#Lline)` links.
3. **Cross-cluster patterns** — recurring themes across the whole library: snippet density, routing-pointer consistency, currency drift, structural symmetry between siblings, genuine catalog gaps (missing skill names with priority order).
4. **Factual errors that would mislead an agent today** — short list, highest priority. These are the candidates for an immediate follow-up fix.

## Rules

- Do not edit any SKILL.md during the evaluation — this command is read-only. If the user asks for fixes after, do them in a follow-up turn.
- Do not delegate synthesis to a sub-agent. The main loop must read each sub-agent's report and write the final consolidated output itself.
- Use clickable markdown links (`[text](relative/path#Lline)`) for every file reference, per this environment's conventions.
- Don't be sycophantic. Skills are meant to be improved.
- If `$ARGUMENTS` narrows the set to a single cluster, still spawn at least one sub-agent rather than evaluating inline — it keeps the main context clean.
