# agent-skills

A shared library of AI agent skills (`SKILL.md` files), designed to be consumed as a git submodule by other repos. Each skill is self-contained: YAML frontmatter (`name`, `description`) followed by guidance the agent reads when the trigger conditions match.

## For AI agents reading this repo

**This README is the catalog.** Scan the tables below for the matching domain or trigger keyword, then read the listed `SKILL.md` file directly. Paths are relative to the repo root.

Picking rules:
- Prefer the **most specific** skill that fits. e.g. use `postgresql` over `database-design` when the user says "Postgres"; use `fastapi` over `backend-development` when the file imports FastAPI; use `aws` over `infrastructure-fundamentals` for AWS-specific work.
- Skills compose. A FastAPI service on AWS using Postgres may invoke `fastapi` + `aws` + `postgresql` together.
- If no skill in the catalog matches the user's request, do not invent one — fall back to general reasoning.

## Catalog

### Engineering / Architecture

| Skill | Path | Use when |
|---|---|---|
| system-architecture | [.claude/skills/engineering/architecture/system-architecture/SKILL.md](.claude/skills/engineering/architecture/system-architecture/SKILL.md) | Designing new systems, evaluating patterns (monolith vs microservices, sync vs async, layered vs hexagonal), writing ADRs, debugging architectural smells. |
| api-design | [.claude/skills/engineering/architecture/api-design/SKILL.md](.claude/skills/engineering/architecture/api-design/SKILL.md) | Designing or reviewing HTTP APIs — REST, RPC, GraphQL, gRPC, webhooks; resource modeling, status codes, pagination, versioning, idempotency, rate limiting, OpenAPI. |

### Engineering / Backend

| Skill | Path | Use when |
|---|---|---|
| backend-development | [.claude/skills/engineering/backend/backend-development/SKILL.md](.claude/skills/engineering/backend/backend-development/SKILL.md) | General backend service work below the controller — data access, caching, async/jobs, transactions, config, secrets, logging, retries, idempotency, feature flags, testing strategy. |
| fastapi | [.claude/skills/engineering/backend/fastapi/SKILL.md](.claude/skills/engineering/backend/fastapi/SKILL.md) | Python FastAPI services — project structure, DI, Pydantic, async SQLAlchemy/SQLModel, auth, background work, testing, observability. |
| django | [.claude/skills/engineering/backend/django/SKILL.md](.claude/skills/engineering/backend/django/SKILL.md) | Django / DRF — models, migrations, querysets, serializers, admin, URL routing, auth, signals, Channels, Celery, async views, ORM performance, testing with pytest-django. |
| nodejs-backend | [.claude/skills/engineering/backend/nodejs-backend/SKILL.md](.claude/skills/engineering/backend/nodejs-backend/SKILL.md) | Node.js / TypeScript backends — Fastify, Hono, Express, NestJS; Zod validation; Drizzle, Prisma; async error handling; auth; testing. |
| go-backend | [.claude/skills/engineering/backend/go-backend/SKILL.md](.claude/skills/engineering/backend/go-backend/SKILL.md) | Go services — net/http, chi/echo/gin/fiber, goroutines, channels, context, error wrapping, database/sql/sqlx/sqlc/pgx/GORM, slog, table-driven tests, pprof. |

### Engineering / Frontend

| Skill | Path | Use when |
|---|---|---|
| frontend-development | [.claude/skills/engineering/frontend/frontend-development/SKILL.md](.claude/skills/engineering/frontend/frontend-development/SKILL.md) | Framework-agnostic frontend work — HTML/CSS/JS fundamentals, browser APIs, web performance, bundle size, asset loading, forms, build tooling (Vite/esbuild/Turbopack/webpack), monorepos, design systems, i18n, browser compat, progressive enhancement. |
| frontend-react-next | [.claude/skills/engineering/frontend/frontend-react-next/SKILL.md](.claude/skills/engineering/frontend/frontend-react-next/SKILL.md) | React and Next.js — components, hooks, RSC vs client, App/Pages Router, server actions, caching (`fetch`/`unstable_cache`/`revalidatePath`), TanStack Query, hydration mismatches, `"use client"`/`"use server"`, Vitest/Playwright. |
| accessibility-wcag | [.claude/skills/engineering/frontend/accessibility-wcag/SKILL.md](.claude/skills/engineering/frontend/accessibility-wcag/SKILL.md) | Web accessibility — WCAG 2.1/2.2, Section 508, ADA, EN 301 549, ARIA, semantic HTML, keyboard navigation, focus management, screen readers (NVDA/JAWS/VoiceOver), contrast, axe/Lighthouse, VPAT/ACR, a11y remediation. |

### Engineering / Data

| Skill | Path | Use when |
|---|---|---|
| database-design | [.claude/skills/engineering/data/database-design/SKILL.md](.claude/skills/engineering/data/database-design/SKILL.md) | Schema modeling, normalization, indexing strategy, transaction/isolation reasoning, migration discipline — engine-agnostic. |
| postgresql | [.claude/skills/engineering/data/postgresql/SKILL.md](.claude/skills/engineering/data/postgresql/SKILL.md) | Postgres-specific work — EXPLAIN, JSONB, GIN, partitioning, replication, `pg_stat`, pgbouncer, vacuum, WAL, query tuning. |
| pgvector-embeddings | [.claude/skills/engineering/data/pgvector-embeddings/SKILL.md](.claude/skills/engineering/data/pgvector-embeddings/SKILL.md) | Vector similarity search and RAG — pgvector schema, index choice (HNSW vs IVFFlat), chunking, hybrid search, when to graduate to a dedicated vector DB. |
| redis-caching | [.claude/skills/engineering/data/redis-caching/SKILL.md](.claude/skills/engineering/data/redis-caching/SKILL.md) | Redis / Valkey / KeyDB / Dragonfly / ElastiCache / Upstash — caching strategies, TTLs, eviction, key design, data structures (sorted sets, streams, HyperLogLog), distributed locks, rate limiting, pub/sub, Lua, pipelining, Cluster, hot/big keys, cache stampedes. |

### Engineering / Cloud

| Skill | Path | Use when |
|---|---|---|
| infrastructure-fundamentals | [.claude/skills/engineering/cloud/infrastructure-fundamentals/SKILL.md](.claude/skills/engineering/cloud/infrastructure-fundamentals/SKILL.md) | Cloud-agnostic infra & networking — DNS, TLS, load balancing, CDNs, reverse proxies, firewalls, VPNs, private connectivity, service meshes, certs. |
| aws | [.claude/skills/engineering/cloud/aws/SKILL.md](.claude/skills/engineering/cloud/aws/SKILL.md) | AWS work — service selection, IAM, VPC, EC2/ECS/EKS/Lambda/Fargate, S3/RDS/Aurora/DynamoDB, SQS/SNS/EventBridge, KMS, CloudWatch, Well-Architected. |
| azure | [.claude/skills/engineering/cloud/azure/SKILL.md](.claude/skills/engineering/cloud/azure/SKILL.md) | Azure work — service selection, Entra ID & RBAC, VNet/NSG, App Service/AKS/Container Apps/Functions, Azure SQL/Cosmos, Key Vault, Monitor/App Insights. |

### Engineering / IaC

| Skill | Path | Use when |
|---|---|---|
| iac-terraform | [.claude/skills/engineering/iac/iac-terraform/SKILL.md](.claude/skills/engineering/iac/iac-terraform/SKILL.md) | Terraform / OpenTofu — HCL, modules, state, backends, workspaces, `for_each`/`count`/`dynamic`, `moved`/`removed`/`import`, drift, plans, CI. |
| iac-bicep | [.claude/skills/engineering/iac/iac-bicep/SKILL.md](.claude/skills/engineering/iac/iac-bicep/SKILL.md) | Azure-native IaC — Bicep/ARM, deployment scopes (RG/sub/MG/tenant), what-if, Bicep registry, `az deployment`, ARM-to-Bicep conversion. |

### Engineering / DevOps

| Skill | Path | Use when |
|---|---|---|
| devops-cicd | [.claude/skills/engineering/devops/devops-cicd/SKILL.md](.claude/skills/engineering/devops/devops-cicd/SKILL.md) | CI/CD pipelines (GitHub Actions, GitLab CI, Buildkite, Jenkins), Dockerfiles, deploy strategies (rolling/blue-green/canary), artifact registries, image signing, supply-chain security, branch protection. |
| kubernetes-helm-gitops | [.claude/skills/engineering/devops/kubernetes-helm-gitops/SKILL.md](.claude/skills/engineering/devops/kubernetes-helm-gitops/SKILL.md) | Kubernetes manifests (Deployments/StatefulSets/Jobs), Helm charts, Argo CD / Flux, HPA/VPA/PDB, RBAC, network policies, ingress, debugging stuck rollouts and CrashLoopBackOff. |

### Engineering / Reliability

| Skill | Path | Use when |
|---|---|---|
| observability | [.claude/skills/engineering/reliability/observability/SKILL.md](.claude/skills/engineering/reliability/observability/SKILL.md) | Logs, metrics, traces, alerts, dashboards, SLIs/SLOs/error budgets — OpenTelemetry, Prometheus, Grafana/Loki/Tempo, Jaeger, Datadog, Honeycomb, structured logging, cardinality. |
| resilience-patterns | [.claude/skills/engineering/reliability/resilience-patterns/SKILL.md](.claude/skills/engineering/reliability/resilience-patterns/SKILL.md) | Behavior under failure — timeouts, retries, backoff/jitter, circuit breakers, bulkheads, rate limiting, load shedding, idempotency, graceful degradation, queues/back-pressure, sagas, DLQs. |

### Engineering / Security

| Skill | Path | Use when |
|---|---|---|
| secrets-management | [.claude/skills/engineering/security/secrets-management/SKILL.md](.claude/skills/engineering/security/secrets-management/SKILL.md) | Storing, fetching, rotating secrets — Vault, AWS Secrets Manager/SSM, GCP Secret Manager, Azure Key Vault, KMS, SOPS, Sealed Secrets, External Secrets Operator, IRSA/Workload Identity, mTLS. |
| authn-authz | [.claude/skills/engineering/security/authn-authz/SKILL.md](.claude/skills/engineering/security/authn-authz/SKILL.md) | Authentication and authorization — login, SSO, SAML, OIDC, OAuth, JWT, sessions, cookies, MFA, API keys, role/permission checks, IDOR, tenancy isolation, admin gating. |
| application-security | [.claude/skills/engineering/security/application-security/SKILL.md](.claude/skills/engineering/security/application-security/SKILL.md) | Web app security baseline — OWASP Top 10, injection (SQL/command/template), SSRF, CSRF, XSS, deserialization, CSP/headers, open redirect, file uploads, dependency/supply-chain risk. |
| audit-logging | [.claude/skills/engineering/security/audit-logging/SKILL.md](.claude/skills/engineering/security/audit-logging/SKILL.md) | Audit logs for "who did what when" — auth events, authz decisions, admin actions, data access/exports, FERPA § 99.32 disclosure logs, tamper-evident retention, forensics. |
| pii-handling | [.claude/skills/engineering/security/pii-handling/SKILL.md](.claude/skills/engineering/security/pii-handling/SKILL.md) | PII lifecycle — collection, storage, transit, derivation, sharing, deletion; quasi-identifiers, re-identification risk, anonymization, PII in logs/caches/LLM prompts, vendor sharing. |

### Engineering / Compliance

| Skill | Path | Use when |
|---|---|---|
| ferpa-compliance | [.claude/skills/engineering/compliance/ferpa-compliance/SKILL.md](.claude/skills/engineering/compliance/ferpa-compliance/SKILL.md) | FERPA rules for student data — education records, directory info, parent/guardian access, SIS/registrar data, rosters, grades, advising, vendor disclosures. |
| vanderbilt-data-classification | [.claude/skills/engineering/compliance/vanderbilt-data-classification/SKILL.md](.claude/skills/engineering/compliance/vanderbilt-data-classification/SKILL.md) | Vanderbilt's L1–L4 data classification + approved-AI-tool matrix (ChatGPT Edu / Amplify / Copilot), masking/redaction before LLM calls, M365 sensitivity labels, when to escalate to Cybersecurity. |
| hipaa-compliance | [.claude/skills/engineering/compliance/hipaa-compliance/SKILL.md](.claude/skills/engineering/compliance/hipaa-compliance/SKILL.md) | PHI / ePHI handling — HIPAA Privacy/Security/Breach Notification Rules, 2025 Security Rule update, BAAs, 18 identifiers, Safe Harbor / Expert Determination, EHR integrations (Epic/Cerner/Athena), VUMC clinical data, FHIR/HL7, sending PHI to LLMs. |

### Engineering / AI

| Skill | Path | Use when |
|---|---|---|
| llm-application-engineering | [.claude/skills/engineering/ai/llm-application-engineering/SKILL.md](.claude/skills/engineering/ai/llm-application-engineering/SKILL.md) | Production LLM apps — model selection, structured outputs, streaming, prompt caching, retries, fallbacks, cost/latency control, observability, hardening prototypes for ship. |
| agent-design | [.claude/skills/engineering/ai/agent-design/SKILL.md](.claude/skills/engineering/ai/agent-design/SKILL.md) | Designing LLM agents — agent vs workflow, tool design, agent loop, context management, runaway/cost control, planner-executor, "tool use," "function calling loop," autonomous task execution. |
| rag-architecture | [.claude/skills/engineering/ai/rag-architecture/SKILL.md](.claude/skills/engineering/ai/rag-architecture/SKILL.md) | Retrieval-augmented generation — chunking, embeddings, hybrid search, reranking, contextual retrieval, query rewriting, citations, "chatbot over our docs," RAG that degrades in prod. |
| llm-evaluation | [.claude/skills/engineering/ai/llm-evaluation/SKILL.md](.claude/skills/engineering/ai/llm-evaluation/SKILL.md) | LLM evals — golden datasets, rubrics, assertions, LLM-as-judge, calibration, regression tests, "is the new prompt better?", offline/online evals, A/B tests for LLM features. |
| mcp-server-design | [.claude/skills/engineering/ai/mcp-server-design/SKILL.md](.claude/skills/engineering/ai/mcp-server-design/SKILL.md) | Model Context Protocol servers — tools vs resources vs prompts, schema design, error handling, auth, transports, pagination, "expose this to Claude," debugging tool-calling. |
| prompt-injection-defense | [.claude/skills/engineering/ai/prompt-injection-defense/SKILL.md](.claude/skills/engineering/ai/prompt-injection-defense/SKILL.md) | LLM security — direct/indirect prompt injection, jailbreaks, untrusted content, capability containment, output validation, exfiltration vectors (URLs, markdown, file writes), agent threat models. |
| human-in-the-loop-workflows | [.claude/skills/engineering/ai/human-in-the-loop-workflows/SKILL.md](.claude/skills/engineering/ai/human-in-the-loop-workflows/SKILL.md) | HITL design — approval gates, review queues, confidence thresholds, escalation UX, reviewer tooling, feedback loops to prompts/training, moderation/QA at scale, active learning. |
| amplify-platform | [.claude/skills/engineering/ai/amplify-platform/SKILL.md](.claude/skills/engineering/ai/amplify-platform/SKILL.md) | Vanderbilt's Amplify GenAI platform (`gaiin-platform` org) — backend Lambda services, Next.js frontend, Terraform IaC, agent loop, MCP registration via DynamoDB, Cognito JWT, `/chat` & `/files/*` & `/user-data/*` endpoints, CCC drafting pipeline integration. |
| multi-agent-orchestration | [.claude/skills/engineering/ai/multi-agent-orchestration/SKILL.md](.claude/skills/engineering/ai/multi-agent-orchestration/SKILL.md) | Coordinating multiple LLM agents — orchestrator/worker, supervisor/router, parallel agents, handoffs, A2A protocol, planner-executor splits, swarms, LangGraph/CrewAI/AutoGen/OpenAI Agents SDK, "one agent or many," sub-agents, context overflow. |
| llm-cost-optimization | [.claude/skills/engineering/ai/llm-cost-optimization/SKILL.md](.claude/skills/engineering/ai/llm-cost-optimization/SKILL.md) | Reducing LLM token cost and latency — model selection (Opus/Sonnet/Haiku, GPT-5/4o/4-mini, Gemini Pro/Flash), prompt caching, batch APIs, model routing/cascades, semantic caching, output length control, distillation, "the bill is too high," prod cost scaling. |

## Adding a new skill

1. Pick the discipline and the domain subdirectory. Create a new domain folder if none fits.
2. Create `<skill-name>/SKILL.md` with frontmatter:

   ```markdown
   ---
   name: <skill-name>
   description: <one sentence on when this skill should activate — include trigger keywords>
   ---

   # <Title>

   <body — guidance the agent reads when triggered>
   ```

3. Add a row to the appropriate catalog table above. Keep the "Use when" cell to one sentence with concrete trigger keywords; the full description belongs in the SKILL.md frontmatter.

## Conventions

- One skill per directory; the file is always named `SKILL.md`.
- Skill names are kebab-case and unique across the library.
- The frontmatter `description` is what an agent uses to decide relevance — write it as a trigger statement, not a feature list.
- Bias toward fewer, broader skills. Split only when a sub-area has materially different guidance from its parent (e.g. `postgresql` vs `database-design`).
