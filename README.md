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

### Engineering / Data

| Skill | Path | Use when |
|---|---|---|
| database-design | [.claude/skills/engineering/data/database-design/SKILL.md](.claude/skills/engineering/data/database-design/SKILL.md) | Schema modeling, normalization, indexing strategy, transaction/isolation reasoning, migration discipline — engine-agnostic. |
| postgresql | [.claude/skills/engineering/data/postgresql/SKILL.md](.claude/skills/engineering/data/postgresql/SKILL.md) | Postgres-specific work — EXPLAIN, JSONB, GIN, partitioning, replication, `pg_stat`, pgbouncer, vacuum, WAL, query tuning. |
| pgvector-embeddings | [.claude/skills/engineering/data/pgvector-embeddings/SKILL.md](.claude/skills/engineering/data/pgvector-embeddings/SKILL.md) | Vector similarity search and RAG — pgvector schema, index choice (HNSW vs IVFFlat), chunking, hybrid search, when to graduate to a dedicated vector DB. |

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
