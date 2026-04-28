---
name: amplify-platform
description: Integrate with Vanderbilt's Amplify GenAI platform (GitHub org `gaiin-platform`) — its serverless AWS backend, Next.js frontend, Terraform IaC, agent loop, MCP server registration model, Cognito auth, and the public `/chat`, `/files/*`, `/user-data/*`, `/assistants/*` endpoints. Use this skill when work touches Amplify, gaiin-platform repos (`amplify-genai-backend`, `amplify-genai-frontend`, `amplify-genai-iac`, `pycommon`, `amplify-mcp-servers-examples`, `fastify-mcp-server`, `claudia`/`opcode`, `open-notebook`, `skills` fork), the CCC social-media drafting pipeline integration, or any task that says "Amplify chat," "amplify-lambda-*," "amplify-agent-loop," "amplify MCP server," "register MCP in DynamoDB," "Cognito JWT for Amplify," or "Vanderbilt GenAI platform." Trigger on `amplify@vanderbilt.edu`, the maintainers (Jules White, Allen Karns, Karely Rodriguez, Max Moundas), or v0.9.0/v0.8.1 release references.
---

# Amplify Platform — Technical Overview for CCC Integration

This document captures what the Amplify team (Vanderbilt, GitHub org [gaiin-platform](https://github.com/gaiin-platform)) has built, how it is deployed, and the surfaces we can integrate with from the CCC social-media drafting pipeline. It is sourced from direct inspection of the nine submodules under `external/` of the CCC project at the pinned commits, plus the public org profile.

Maintainer contact: `amplify@vanderbilt.edu`. Primary authors visible across repos: Jules White, Allen Karns, Karely Rodriguez, Max Moundas.

> Scope note. Several submodules in `external/` are the user's personal forks of upstream repos (notably `skills`, `fastify-mcp-server`, `opcode`/`claudia`, `open-notebook`). Where the upstream is an outside project rather than Amplify's own work, that is called out explicitly in the "Origin" line for that repo.

> Path note. Links of the form `../external/<repo>/...` below resolve inside the `ccc-social-media-drafting-agents` repository, where each repo is pinned as a git submodule. From outside that repo, navigate via the public `gaiin-platform` GitHub org instead.

---

## 1. What Amplify Is

Amplify is Vanderbilt's open-source, multi-tenant, multi-provider enterprise GenAI platform. Its stated posture:

- Vendor-independent across LLM providers: OpenAI, Azure OpenAI, Anthropic (via AWS Bedrock), Google (Gemini), Amazon Bedrock-native models (Nova), Mistral.
- Self-hosted on AWS, deployed by each institution in their own account — minimum hosting floor cited at ~$250/mo plus token spend.
- Open source (MIT for the core repos; some document-manipulation skills are source-available).
- Built for higher-ed and partner-organization use: admin operations, research, teaching, and external business-partner access through the same tenancy primitives.

The public product surface is a Next.js chat UI backed by a sprawling serverless Python + Node backend on AWS, with a growing plug-in ecosystem (Assistants, MCP servers, agents, skills).

## 2. GitHub Organization Inventory

From [github.com/gaiin-platform](https://github.com/gaiin-platform):

| Repo | Purpose | Primary language |
|---|---|---|
| `amplify-genai-backend` | Serverless backend monorepo (14+ Lambda services) | Python |
| `amplify-genai-frontend` | Next.js web app | TypeScript |
| `amplify-genai-iac` | AWS infrastructure-as-code (Terraform) | HCL |
| `pycommon` | Shared Python SDK consumed by every backend service | Python |
| `amplify-mcp-servers-examples` | Reference MCP server templates for Lambda | Python |
| `fastify-mcp-server` | Fastify plugin for HTTP MCP servers (forked, enhanced) | TypeScript |
| `claudia` | Desktop GUI for Claude Code (aka the "opcode" codebase upstream) | TypeScript/Rust |
| `amplify-claudia-plugins` | Plugin pack for Claudia | — |
| `skills` | Fork of Anthropic's Agent Skills repo | Markdown/Python |
| `open-notebook` | Fork of open-notebook research assistant | TypeScript/Python |
| `.github` | Org profile, overview docs | — |
| `majk-market` | (empty / internal) | — |

The three "canonical" Amplify repos are `amplify-genai-backend`, `amplify-genai-frontend`, `amplify-genai-iac`. Everything else is supporting tooling, example material, or forks used to round out the ecosystem.

## 3. High-Level Architecture

```
                       ┌───────────────────────────────────────────┐
                       │   amplify-genai-frontend (Next.js 14)     │
                       │   - NextAuth (Cognito/Auth0/SAML)         │
                       │   - Chat UI, Assistants, Admin, MCP       │
                       │   - Runs on ECS Fargate behind ALB        │
                       └──────────────────┬────────────────────────┘
                                          │  HTTPS (JWT bearer)
                                          ▼
                       ┌───────────────────────────────────────────┐
                       │   API Gateway  (AWS_PROXY, streaming)     │
                       └──────────────────┬────────────────────────┘
                                          │
             ┌────────────────────────────┼────────────────────────────┐
             ▼                            ▼                            ▼
  ┌────────────────────┐      ┌────────────────────┐       ┌────────────────────┐
  │ amplify-lambda     │      │ amplify-lambda-js  │       │ assistants / agent │
  │ (Python 3.11 core) │      │ (Node 22, LiteLLM) │       │ loop lambdas       │
  │ chat, files, RAG   │      │ LLM orchestration  │       │ MCP, scheduled     │
  └─────────┬──────────┘      └─────────┬──────────┘       └─────────┬──────────┘
            │                           │                            │
            └──────── shared infra ─────┴────────────────────────────┘
                        │
    ┌───────────────┬───┴────────────┬───────────────┬───────────────┐
    ▼               ▼                ▼               ▼               ▼
 DynamoDB       Aurora PG       S3 (files,       Secrets Mgr    Parameter Store
 (conv, state,  pgvector        traces,          (API keys,     (non-secret
 billing, ACL)  (embeddings)    artifacts)       OAuth)         env config)

 Identity:  AWS Cognito user pool (OAuth2/OIDC, optional SAML IdP, optional pre-auth Lambda)
 Models:    OpenAI, Azure OpenAI, Anthropic-on-Bedrock, Gemini, Amazon Nova, Mistral (via LiteLLM)
 Agent trigger path:  SQS → amplify-agent-loop-lambda (scheduled, email-triggered, tool-calling)
```

Everything is AWS-native and serverless. Release v0.9.0 (Feb 2026) is the current line; v0.8.1 was Dec 2025. v0.9.0 was a breaking release because it moved all shared env vars into AWS Parameter Store under `/amplify/<stage>/amplify-<dep-name>/*`, and migrated chat streaming from Function URLs to API Gateway `AWS_PROXY` with 8-byte frame delimiters.

## 4. Backend — `amplify-genai-backend`

Monorepo at `external/amplify-genai-backend`. Deployed via Serverless Framework v3 with `serverless-compose.yml` orchestrating the core services; a few services deploy standalone.

### 4.1 Services

Compose-managed (deploy together from the repo root):

| Service | Runtime | Purpose |
|---|---|---|
| `amplify-lambda` | Python 3.11 | Core chat/conversation API, file upload, RAG query, available-models listing, user-state KV store, sharing |
| `amplify-assistants` | Python 3.11 | OpenAI Assistants API proxy — threads, runs, messages |
| `amplify-lambda-admin` | Python 3.11 | Admin panel backend: model registry, web-search config, critical-error dashboard, audit logs. Gated by `ADMINS` env var (CSV emails) |
| `amplify-lambda-api` | Python 3.11 | External partner/integration API gateway layer |
| `amplify-lambda-artifacts` | Python 3.11 | Generated artifact storage, versioning, conversation exports |
| `amplify-lambda-js` | Node.js 22 | LLM orchestration hub via **LiteLLM**; skill registry; datasource registry; MCP integration |
| `amplify-lambda-ops` | Python 3.11 | Internal operational tooling |
| `chat-billing` | Python 3.11 | Token/cost accounting, rate lookups, billing tables |
| `data-disclosure` | Python 3.11 | Data residency / compliance checks |
| `amplify-embedding` | Python 3.11 | Bedrock / OpenAI embeddings → Postgres `pgvector`; SQS DLQ pipeline |
| `amplify-object-access` | Python 3.11 | Object-level ACL enforcement / tenant isolation |

Standalone (deploy individually):

| Service | Runtime | Purpose |
|---|---|---|
| `amplify-agent-loop-lambda` | Python 3.11 | Agent execution engine; SQS-triggered; tool-calling, scheduled tasks, email-to-agent routing |
| `amplify-lambda-assistants-api` | Python 3.11 | Assistants API with tools, code interpreter, vision, structured outputs |
| `amplify-lambda-assistants-api-google` | Python 3.11 | Google Workspace integration (Drive, Sheets, Calendar) — OAuth2 + MCP server |
| `amplify-lambda-assistants-api-office365` | Python 3.11 | Microsoft 365 integration (OneDrive, Excel, Outlook) — MSAL OAuth + MCP server |
| `amplify-lambda-python-base` | — | Shared Python layer base |

Config files worth knowing: `external/amplify-genai-backend/serverless-compose.yml`, `dev-var.yml-example`, `build-layer.sh`, `lambda_layers/` (pandoc + pgvector prebuilt zips), and the per-service `serverless.yml` in each `amplify-*` subdirectory.

### 4.2 Python SDK — `pycommon`

Every Python service depends on [github.com/gaiin-platform/pycommon](https://github.com/gaiin-platform/pycommon), pinned with a git+https reference (v0.1.1 at time of writing). Modules worth knowing:

- `pycommon.api.get_endpoint` — uniform way to resolve OpenAI/Azure/Bedrock endpoints
- `pycommon.authz` — JWT validation, permission decorators (`@validated`)
- `pycommon.llm.chat` — chat wrapper
- `pycommon.dal.providers.aws.*` — DynamoDB / S3 / Secrets Manager access helpers
- `pycommon.logger` — structured logging

If we build a Python client or service that talks to Amplify on the backend side, we can either vendor `pycommon` or re-implement just the pieces we need.

### 4.3 Data stores

- **DynamoDB** — the workhorse. Tables cover conversation metadata, user accounts, chat usage, shared state, admin config, critical errors, agent state, scheduled tasks, workflow registry, OAuth tokens, MCP server registry.
- **Aurora PostgreSQL (Serverless v2, 0.5–16 ACUs) + `pgvector`** — RAG embeddings.
- **S3** — user files, shared conversations, document-conversion artifacts, chat traces, workflow templates.
- **Secrets Manager** — LLM API keys, OAuth client secrets.
- **Parameter Store** — centralized non-secret env config (new in v0.9.0).

### 4.4 LLM stack

- Python: **LiteLLM** (v1.78.7) is the unified LLM abstraction, plus the OpenAI SDK for direct calls. The LiteLLM Python layer was aggressively trimmed in v0.9.0 (from 200+ MB down to ~12–25 MB) via `external/amplify-genai-backend/amplify-lambda-js/scripts/build-python-litellm-layer.sh`.
- Node: `openai@4.x`, `@azure/openai@2.0.0-beta.1`, `@aws-sdk/client-bedrock-runtime`, `@dqbd/tiktoken`.
- Model registry lives in `amplify-lambda-admin/service/supported_models.py` and is admin-configurable at runtime. Pricing table: `chat-billing/model_rates/model_rate_values.csv`.
- Bedrock Guardrails are optional, configured via `BEDROCK_GUARDRAIL_ID` + `BEDROCK_GUARDRAIL_VERSION`.

### 4.5 Agent framework (`amplify-agent-loop-lambda`)

Event-driven, SQS-fronted agent runner. Key concepts:

- Tools are registered with a `@register_tool` decorator; the framework injects an action context and handles function-calling dispatch.
- Triggers: SQS queue (`AgentQueue`), `croniter`-driven scheduled tasks, and **email-to-agent** via plus-addressing routed by `EMAIL_TO_AGENT` templates.
- State in DynamoDB: `agent-state`, `scheduled-tasks`, `workflow-registry`, `agent-event-templates`.
- Docs worth reading: `amplify-agent-loop-lambda/docs/AGENT_FRAMEWORK.md`, `BUILDING_AGENTS.md`, `EMAIL_TO_AGENT.md` in the same folder.

The assistants-API service (`amplify-lambda-assistants-api/integrations/mcp_servers.py`) is where outbound MCP calls go — including the Google and Office365 MCP servers and any custom third-party MCP endpoints users register.

### 4.6 Integration surface (for us)

Public HTTP endpoints (API Gateway, Cognito JWT bearer auth):

| Endpoint | Method | Purpose |
|---|---|---|
| `/chat` | POST | Streaming chat, optional RAG |
| `/available_models` | GET | List deployed models with limits and pricing |
| `/files/upload`, `/files/query`, `/files/download`, `/files/delete` | POST/GET/DELETE | File ops (RAG-indexed) |
| `/user-data/{key}` + `/user-data/batch/*` + `/user-data/query/{prefix}` | GET/PUT/DELETE/POST | Per-user KV store with TTL |
| `/state/share`, `/state/share/load` | POST | Share / load conversation state |
| `/assistants/*`, `/threads/*` | * | Assistants + threads |
| `/admin/*` | * | Admin-gated |

Chat input schema (`amplify-lambda/schemata/chat_input_schema.py`):

```jsonc
{
  "temperature": 0.7,
  "max_tokens": 4096,
  "dataSources": ["file-id-1", "file-id-2"],
  "messages": [{"role": "user", "content": "..."}],
  "options": {
    "ragOnly": false,
    "skipRag": false,
    "assistantId": "astp/...",
    "model": {"id": "gpt-5"},
    "prompt": "optional system override"
  }
}
```

## 5. Frontend — `amplify-genai-frontend`

At `external/amplify-genai-frontend`. Next.js 14.2.4 / React 18.2 / TypeScript 4.9 app, output mode `standalone` for container deployment.

### 5.1 Stack highlights

- **Auth** — NextAuth v4 with Cognito, Auth0, and SAML IdPs. Middleware at `middleware.ts` gates `/assistants/*`.
- **UI** — Mantine v6, Tailwind with runtime CSS variables for white-label theming, shadcn/ui-style patterns, Emotion.
- **Markdown + math** — `react-markdown` + `remark-gfm`, `remark-math`, `rehype-katex`; code via `react-syntax-highlighter`/Prism; diagrams via Mermaid.
- **Viz + data** — Vega/vega-lite/react-vega, papaparse, `read-excel-file`, `mammoth` (DOCX), `jszip`.
- **Safety** — `dompurify` for user-generated HTML; `bad-words` profanity filter.
- **i18n** — 22 locales via `next-i18next`.
- **Analytics** — Mixpanel (`mixpanel-browser`).
- **Tokens/cost** — `@dqbd/tiktoken` for in-browser token counting.
- **v0.9.0 additions** — MCP client wiring (`services/mcpService.ts`, `services/mcpToolExecutor.ts`, `hooks/useMCPChat.ts`, `pages/mcp-oauth-callback.tsx`), admin critical-error dashboard, per-conversation web-search toggle (Google Custom Search via `pages/api/google.ts`), batch delete on data sources, DOCX/ZIP artifact downloads, JIT user provisioning, case-insensitive email autocomplete with LZW compression.

### 5.2 Component surface

46 top-level component groups. The ones we care about if we integrate:

- `Chat/`, `Chatbar/`, `PromptTextArea/` — conversation UI
- `Assistants/`, `AssistantWorkflows/`, `AssistantGallery/`, `LayeredAssistants/`, `GroupAssistants/`, `AssistantApi/` — assistant authoring + execution
- `DataSources/` — file upload + embedding
- `Integrations/` — Google Drive, SharePoint, Bedrock KB connectors
- `Admin/` — admin panel (user mgmt, config, critical errors)
- `Workspace/`, `Share/`, `Folder/` — org / sharing / library
- `Artifacts/`, `Memory/`, `Emails/`, `Skills/`, `Operations/`, `Market/`, `Optimizer/`
- Building blocks: `Sidebar/`, `TabSidebar/`, `Markdown/`, `Download/`, `Loader/`, `Spinner/`, `Search/`, `JsonForm/`, `ReusableComponents/`

Services layer (`services/`) has ~40 modules — notably `chatService`, `conversationService`, `assistantService`, `assistantWorkflowService`, `assistantArtifactsService`, `mcpService`, `mcpToolExecutor`, `adminWebSearchService`, `oauthIntegrationsService`, `shareService`, `fileService`, `dataDisclosureService`, `mtdCostService`, `userDataService`, `emailAutocompleteService`, `adminService`, `scheduledTasksService`, `pollRequestService`, `memoryService`, `skillsService`, `groupsService`.

### 5.3 Deployment targets

Three supported shapes, all from the same repo:

1. **AWS Amplify Hosting** — `amplify.yml` handles env export and `npm ci && npm run build`.
2. **ECS Fargate** — `Dockerfile` multi-stage Alpine build, non-root user, white-label build args (`NEXT_PUBLIC_CUSTOM_LOGO`, `NEXT_PUBLIC_DEFAULT_THEME`, `NEXT_PUBLIC_BRAND_NAME`). Driven by the IaC module below.
3. **Kubernetes** — `k8s/chatbot-ui.yaml` (single-replica reference manifest).

Tests: Vitest for unit (`__tests__/`); Selenium (Python) for end-to-end across sidebar, modal, chat, conversation, custom-instructions, and tab surfaces.

## 6. Infrastructure — `amplify-genai-iac`

At `external/amplify-genai-iac`. Terraform ≥0.14, AWS provider ~5.15, `us-east-1`. Two environment directories (`dev/`, `prod/`) share the same module set; state backend (S3 + DynamoDB lock table) is implied but configured per site.

### 6.1 Modules

| Module | What it creates |
|---|---|
| `modules/load_balancer` | VPC, public + private subnets across 2 AZs, ALB (HTTPS w/ HTTP→HTTPS redirect), target group (port 3000), ACM certs (incl. SAN for root-redirect), Route53 records, SGs |
| `modules/ecr` | Private ECR repo, scan-on-push, mutable tags |
| `modules/ecs` | Fargate cluster (Container Insights on), service, task definition (CPU/memory configurable, secrets from Secrets Manager), execution + task roles, CloudWatch log group (90d retention), CloudWatch alarms wired to SNS (email), step-scaling policies |
| `modules/cognito_pool` | User pool (case-insensitive), app client (with secret), custom domain + ACM cert via DNS validation, optional SAML IdP, optional pre-auth Lambda (`files/preAuthLambda.py`) for SAML group checks, `saml_groups` custom attribute |
| `modules/lambda_layer` | `pandoc_layer` Lambda layer, Python 3.10/3.11 compatible, from prebuilt zip in `files/` |

### 6.2 Environment shape

- `dev/` defaults: 0.5 vCPU, 1 GB, 1–2 tasks.
- `prod/`: same module composition, larger sizes, more replicas, HA multi-AZ.
- Four Secrets Manager entries per env (envs, secrets, openai key, openai endpoints); values are populated out-of-band, not in Terraform.
- Tag-ignore policy set to `["*"]` to avoid drift from external tagging.

### 6.3 Install workflow

`install/install.sh` is the orchestrator:

1. Prompt env (dev/prod).
2. Capture backend + frontend repo paths to `{env}_directories.config`.
3. Optional `terraform init` → `terraform apply` → emit `{env}-outputs.json`.
4. Hand outputs (Cognito IDs/secrets, Secrets Manager names, ECR URI, ECS names, subnet IDs, pandoc layer ARN) to `var-update.sh` which injects them into the backend's serverless config.
5. `deploy-to-ecr.sh` builds + pushes the frontend container; `update-ecs-service.sh` / `update-task-definition.sh` roll the service.

## 7. MCP Integration

Two repos in the ecosystem define how MCP servers plug into Amplify.

### 7.1 `amplify-mcp-servers-examples`

Origin: original Amplify work (Python). Location: `external/amplify-mcp-servers-examples`.

Four reference servers, all Python 3.12 on AWS Lambda (containerized, ECR-deployed, Lambda Function URL + CORS, JSON-RPC 2.0 over HTTP):

| Server | Tools | Notable behavior |
|---|---|---|
| Data Transformation | CSV↔JSON, JSON↔XML, YAML↔JSON (6 tools) | Pure stdlib + pyyaml / lxml |
| Image Processing | resize, crop, rotate, filters, format convert, thumbnails (6 tools) | Pillow; results >4 MB returned via S3 presigned URL (24h TTL) |
| Node.js Execution | sandboxed JS exec (1 tool) | VM isolation, 5–30 s timeout, no fs/network |
| Jupyter | create notebook, exec cell, list cells, get output, install package, upload file (6 tools) | Strips `AWS_*` creds from kernel env |

Pattern per server: `server.py` with a `TOOLS` array (JSON Schema `inputSchema`) + Flask handler for `tools/list` + `tools/call`, delegating to a `manager.py`. `lambda_handler.py` adapts to Lambda; `Dockerfile.lambda` builds on `public.ecr.aws/lambda/python:3.12`. Scripts `push-to-ecr.sh` + `deploy-lambda-ecr.sh` do the build/push/deploy.

Registration into Amplify is via a **DynamoDB record** on the `amplify-v6-lambda-dev-user-data-storage` table:

- PK: `{user_id}#amplify-mcp#mcp_servers`
- Value: server URL, enabled flag, and the full tool schemas (so the chat UI can render forms).

`SECURITY.md` is explicit that these are demonstration templates — no per-user auth, no user isolation, no quotas, no audit with user attribution, no package allow-list, no network restrictions. Any production MCP server we ship will need to add those.

### 7.2 `fastify-mcp-server`

Origin: **fork of Flavio Del Grosso's Fastify MCP plugin**, enhanced by gaiin-platform. Published as `@majkapp/fastify-mcp-server@0.4.3`. Location: `external/fastify-mcp-server`. Node ≥18, TypeScript strict, ES modules, 100% coverage target.

Two modes:

- **Traditional** (`FastifyMcpServer`) — one MCP server per Fastify app.
- **Per-bearer-token** (`createPerBearerMcpServer`, 1000+ LOC core) — the big addition. The same `/mcp` endpoint serves completely different tool sets depending on the bearer token presented. Each token maps to a server factory; servers are cached; full lifecycle is observable via events (`tokenAdded/Removed/Updated`, `serverRegistered/Removed`, `sessionCreated/Ended`, `toolCalled`).

HTTP surface (streamable HTTP MCP):

- `POST /mcp` — create session or send request (`mcp-session-id` header optional on create).
- `GET /mcp` — SSE stream for an existing session.
- `DELETE /mcp` — terminate session.

Auth support: pluggable bearer verifier via `authorization.bearerMiddlewareOptions`, optional required scopes, optional OAuth2 well-known endpoints (`/.well-known/oauth-authorization-server`, `/.well-known/oauth-protected-resource`). Tool handlers receive `authInfo` with `token` + `scopes`.

Examples in `examples/` show the traditional pattern, an events demo, and a complete per-bearer SaaS pattern. Demos runnable via `npm run demo:simple` and `demo:per-bearer`.

### 7.3 How we would ship an MCP server for CCC

Two viable paths:

- **Python / AWS Lambda** — clone a folder under `amplify-mcp-servers-examples/servers/`, implement `manager.py` + `server.py`, Dockerize, push to ECR, deploy, then register the Function URL + tool schemas in the Amplify user's DynamoDB record.
- **TypeScript / Fastify** — start from `@majkapp/fastify-mcp-server`'s per-bearer-token pattern if we need multi-tenant isolation (e.g. distinct tools per requester), run it anywhere (Fargate, EC2, or behind an ALB), register the HTTPS URL in Amplify.

For the drafting pipeline, the Python/Lambda path is the closer match to Amplify's house style and deployment posture.

## 8. Supporting / Forked Repos

These four show up in `external/` but are not core Amplify services — they are forks and complementary tools. Important to understand what they are so we know which team owns what.

### 8.1 `opcode/` (a.k.a. Claudia)

Origin: **upstream `opcode` by the Asterisk team**. The gaiin-platform org keeps a fork/rename as [`claudia`](https://github.com/gaiin-platform/claudia) and maintains a companion `amplify-claudia-plugins` pack. Not affiliated with Anthropic.

What it is: a Tauri 2 desktop GUI for Claude Code (Anthropic's CLI). Local SQLite store, session/checkpoint timeline, custom agent authoring, usage/cost analytics (recharts), MCP server registry, global shortcuts, clipboard integration. Frontend: React 18 + Vite 6 + Tailwind v4 + Zustand. Backend: Rust with Tauri 2. Package manager: Bun. License: AGPL-3.0.

Relevant for us only if a CCC team member wants a local power-user UI on top of Claude Code; it is not in the serving path of Amplify.

### 8.2 `open-notebook/`

Origin: **fork of open-notebook.ai** (Luis Novo's project), an open-source, privacy-first alternative to Google NotebookLM. Not original Amplify work. License: MIT.

Stack: FastAPI (Python 3.11+), LangGraph, SurrealDB (graph DB), Next.js 16 / React 19 frontend, Esperanto for multi-provider LLM abstraction (OpenAI / Anthropic / Google / Groq / Ollama / Mistral / DeepSeek / xAI), `content-core` for 50+ file types, `podcast-creator` for multi-speaker audio, `uv` for deps, Docker + compose.

Relevant as a possible research/ingest companion — if CCC has content corpora we want to chat with or summarize outside the Amplify chat surface, Open Notebook is a drop-in. It is not wired into Amplify by default.

### 8.3 `skills/`

Origin: **fork of Anthropic's official `skills` repo**. Agent Skills = markdown instruction packs (`SKILL.md` with YAML frontmatter) that Claude loads to specialize behavior. Spec at [agentskills.io/specification](https://agentskills.io/specification).

Contents: example skills (brand-guidelines, internal-comms, claude-api, mcp-builder, skill-creator) under `skills/skills/`, plus document-manipulation skills (`docx`, `pdf`, `pptx`, `xlsx`) that are source-available (not open source). A minimal `template/SKILL.md` is in `template/`.

Relevant because the drafting pipeline's tone, brand, and format guidance is a natural "skill" — we could author a CCC social-media skill and surface it in Claude Code, Claude.ai, or via the Claude API's `skills` parameter.

### 8.4 `gaiin-github/` (org `.github` repo)

Origin: Amplify's own org profile repo. Location: `external/gaiin-github`.

Contents: `profile/README.md` is the public org landing page; `docs/` and `docs/Legacy Documentation/` hold chat-interface, sharing, assistants/templates, integrations, troubleshooting, and deployment walkthroughs. Worth skimming for terminology and user-facing concepts before any conversation with the Amplify team, and for the v0.9.0 Parameter Store breaking-change notice.

## 9. Security & Tenancy Model (What We Need to Mirror or Trust)

From backend + IaC reading:

- **AuthN** — Cognito user pool, OAuth2/OIDC, JWT bearer tokens validated with `aws-jwt-verify` (Node) / `python-jose` (Python). Optional SAML IdP + pre-auth Lambda in the Cognito module for group-based gating.
- **AuthZ** — resource-scoped, driven by `pycommon.authz.validated` decorators and per-operation schemas in each service's `schemata/permissions.py`. Admin endpoints gated by the `ADMINS` CSV env var.
- **Least-privilege IAM** — every Lambda gets its own role via `serverless-iam-roles-per-function`.
- **Tenant isolation** — user-scoped DynamoDB keys (`user_id` + type), `amplify-object-access` service for ACL enforcement, per-user S3 prefixes are not enforced by the MCP examples (flagged in SECURITY.md).
- **Secrets** — AWS Secrets Manager only; env vars in Parameter Store. Nothing sensitive in git or serverless configs.
- **Guardrails** — Bedrock Guardrails optional at the LLM layer; Pydantic schemas on input; DOMPurify + `bad-words` on the frontend for rendered content.
- **Audit** — `amplify-lambda-admin/service/critical_error_notifier.py` tracks critical errors with email alerts; CloudWatch log retention at 365d (backend) / 90d (frontend ECS); X-Ray tracing enabled; `data-disclosure` for residency checks.

For our pipeline this means: if we call Amplify endpoints, we authenticate with a Cognito JWT; if we host an MCP server that Amplify calls, we are responsible for bearer-token verification on our side (Fastify plugin supports this natively, the Lambda examples do not).

## 10. Integration Options for the CCC Drafting Pipeline

Given the platform's shape, three concrete collaboration patterns are available:

1. **Amplify as the LLM + RAG backbone**. Our pipeline calls Amplify's `/chat`, `/files/upload`, `/files/query`, `/available_models`, and `/user-data` endpoints with a Cognito-issued JWT. We reuse their model registry, billing, guardrails, and per-user KV for draft state. Lowest integration cost, tightest coupling.

2. **Our pipeline exposed as an MCP server to Amplify**. We ship a Python Lambda (Amplify-style) or a Fastify service (per-bearer-token style) that exposes CCC-specific tools — e.g. `draft_social_post`, `fetch_brand_voice`, `schedule_publish`, `request_human_approval`. Amplify users invoke the tools from any chat. This keeps the safety/approval loop on our side and lets Amplify stay a thin orchestrator. This is probably where we spend most of our time.

3. **Shared skill for social-media voice**. Author a CCC social-media skill under the Agent Skills spec and drop it into the `skills` fork so both Amplify-hosted assistants and standalone Claude sessions can pick up the same tone/brand guidance. Cheap, additive, composes with (1) and (2).

The three are not mutually exclusive. The likely target architecture is (2) + (3): we own the drafting/approval workflow and expose it as an MCP server, while a published skill carries the voice. Amplify is the chat surface for CCC users who prefer to draft conversationally.

## 11. Open Questions to Confirm with the Amplify Team

- Which Cognito user pool do they want us to federate against for CCC users? Dedicated tenant or shared?
- Is there a published OpenAPI/JSON schema for the `/chat`, `/files/*`, `/user-data/*` endpoints beyond what lives in `schemata/`? The docs folder has `bedrock-kb-datasource.md` and `bedrock-kb-frontend-integration.md` but not a complete contract.
- What's the preferred path for registering MCP servers at the institution level (i.e. available to all CCC users) vs. per-user via DynamoDB?
- Do they want us to use `pycommon` on our side, or stay fully isolated and just speak HTTP?
- Are Bedrock Guardrails enabled in their Vanderbilt deployment, and do they want our drafting pipeline to enforce the same guardrail IDs?
- Retention/residency posture for anything we write to their `/user-data` store.
- Release cadence and whether we should pin to v0.9.0 contracts or track `main`.

## 12. File Map (for quick navigation)

- Backend entry: `external/amplify-genai-backend/README.md`, `RELEASE_NOTES_v0.9.0.md`, `serverless-compose.yml`
- Agent framework: `external/amplify-genai-backend/amplify-agent-loop-lambda/docs/`
- Frontend entry: `external/amplify-genai-frontend/README.md`, `package.json`, `next.config.js`
- IaC entry: `external/amplify-genai-iac/README.md`, `install/install.sh`
- MCP examples: `external/amplify-mcp-servers-examples/README.md`, `DEPLOYMENT_GUIDE.md`, `SECURITY.md`
- Fastify MCP: `external/fastify-mcp-server/README.md`, `src/per-bearer-mcp-server.ts`
- Skills: `external/skills/README.md`, `template/`
- Org profile: `external/gaiin-github/profile/README.md`
