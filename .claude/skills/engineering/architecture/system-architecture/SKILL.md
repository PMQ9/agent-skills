---
name: system-architect
description: Architectural reasoning, decision-making, and system design for backend services. Use whenever the user is designing a new system, evaluating architectural patterns (monolith vs microservices, layered vs hexagonal, sync vs async), making technology choices, writing ADRs, debugging architectural smells, or asking "how should I structure this." Triggers on phrases like "design," "architecture," "structure," "should I use," "trade-offs," "scale," and any greenfield system planning.
---

# System Architect

Architectural decisions are expensive to reverse. The job of this skill is to slow down enough to choose deliberately, write the choice down, and avoid the common failure modes — premature distribution, anemic domain models, leaky abstractions, and big-bang rewrites.

## Core operating principles

**Optimize for change, not perfection.** Most production systems are wrong about something within 18 months. The right architecture is the one that makes the inevitable wrong assumptions cheap to fix. Favor reversibility over correctness.

**Boring technology has a budget.** Each non-boring choice (new language, new database, new infra primitive) spends from a finite innovation budget. Spend it on what actually differentiates the product. Postgres + a well-known web framework + a queue covers ~90% of needs.

**The simplest thing that could possibly work, then iterate.** A monolith with a clean module boundary is almost always the correct starting point. You can extract services later when you have evidence (team scaling, deployment friction, performance isolation needs) — never before.

**Reason in trade-offs, not absolutes.** No pattern is "good." Patterns are good *for* a constraint. Always state the constraint before recommending the pattern.

## When you're asked "how should I architect this"

Before suggesting anything, extract:

1. **What's the read/write ratio and absolute scale?** "Lots of users" is meaningless. 100 RPS, 10K RPS, and 1M RPS are entirely different systems.
2. **What's the team size and shape?** A 3-person team should not run microservices. A 200-person team probably can't ship a single monolith.
3. **What are the consistency requirements?** Money and inventory need strong consistency. Feeds, search, analytics tolerate eventual consistency. This drives the entire data layer.
4. **What's the latency budget end-to-end?** p50 and p99. "Fast" means nothing without numbers.
5. **What changes most often?** The thing that changes most often deserves the cleanest abstraction. Stable things can be coupled.
6. **What's the failure mode of getting it wrong?** Lost email vs lost payment vs corrupted medical record are different problems.

If the user can't answer these, the right next step is to surface the questions, not to draw boxes.

## Architectural patterns: when each applies

### Modular monolith (default)
Single deployable unit, but internally split into modules with explicit boundaries (separate packages, no cross-module DB access, defined interfaces between modules). All the speed of a monolith, most of the discipline of services. **Use when:** team < 30, you don't yet have proven scale bottlenecks, you want one CI/CD pipeline. **Watch for:** modules reaching into each other's database tables — that's the rot that kills monoliths. Enforce module boundaries with import linting.

### Layered (n-tier)
Routes → services/use-cases → repositories → DB. Easy to teach, easy to test. **Use when:** CRUD-heavy apps, small teams, when domain logic is thin. **Watch for:** anemic domain models (entities are just data bags, all logic lives in "service" classes — that's procedural code dressed as OO).

### Hexagonal / Ports & Adapters / Clean Architecture
Domain is the center; everything else (DB, HTTP, queues, external APIs) is an adapter the domain doesn't know about. The domain depends on nothing; everything depends on the domain. **Use when:** business logic is non-trivial, you need to swap infrastructure (DB engine, queue, payment provider), or you want fast unit tests with no DB. **Watch for:** over-engineering — three interfaces to save one user is a code smell, not architecture.

### Event-driven / message-based
Components communicate via events on a queue or log (Kafka, NATS, RabbitMQ, SQS). Decouples producers from consumers, enables fan-out, supports replay. **Use when:** multiple consumers need the same event, you need durability/replay, you're integrating across team boundaries, you have async workflows. **Watch for:** debugging is harder, ordering guarantees are subtler than they look (per-partition vs global), exactly-once delivery is largely a myth — design for idempotency.

### Microservices
Multiple independently deployable services, each owning its data. **Use when:** you have organizational scaling pressure (many teams stepping on each other in one repo), genuinely different scaling profiles per component, or different runtime/language needs. **Do not use when:** you just want "clean architecture" — that's what modules are for. The cost of microservices (network latency, distributed tracing, eventual consistency, deployment complexity, schema coordination) is enormous and only pays off above a real organizational threshold.

### CQRS (Command Query Responsibility Segregation)
Separate write model from read model. Often combined with event sourcing. **Use when:** read and write patterns diverge sharply (e.g., complex aggregations on read, simple state transitions on write), you need multiple read projections of the same data, or you've maxed out a single relational model. **Watch for:** introducing eventual consistency where the UX can't tolerate it.

### Event sourcing
State is the result of replaying an append-only log of events. **Use when:** audit/compliance requires full history, debugging requires replay, or you genuinely need temporal queries ("what did state look like at time T"). **Watch for:** schema evolution is hard, "rebuild the projection" can take hours at scale, most teams don't actually need this.

## Decision heuristics

| Situation | Default choice | When to deviate |
|---|---|---|
| New product, small team | Modular monolith on Postgres | You have measured scale evidence requiring otherwise |
| Need async work | Background queue (Postgres-based or Redis) | High volume + multiple consumers → Kafka/NATS |
| Need search | Postgres full-text + trigram | Genuinely complex relevance → Elasticsearch/Meilisearch |
| Need vector similarity | pgvector | >50M vectors with low-latency reqs → dedicated (Pinecone/Qdrant/Weaviate) |
| Need cache | Postgres first, then Redis | Don't add Redis just to cache 100 rows |
| Need file storage | S3-compatible object storage | Never the database |
| Need a graph | Postgres with recursive CTEs | True graph traversal at scale → Neo4j |
| Need real-time updates | Postgres LISTEN/NOTIFY + WebSockets, or SSE | Massive fan-out → dedicated pub/sub |

The pattern: **start with Postgres for everything you can, peel off only what's measurably broken.**

## Quality attributes — what you're actually optimizing

When you say "scalable" or "reliable," pin it down. These are the attributes worth designing for explicitly:

- **Availability** — % uptime. 99.9% is ~8.7h/year of downtime. 99.99% requires multi-AZ and removing single points of failure. Each nine roughly 10x's cost.
- **Latency** — p50/p95/p99/p999. Optimize for the percentile your business cares about. p99 matters for fan-out (one request making N backend calls).
- **Throughput** — RPS, ingest rate, batch size. Different from latency; you can have one without the other.
- **Consistency** — strong, read-your-writes, monotonic, eventual. Pick per-operation, not per-system.
- **Durability** — probability of data loss. Replication factor, backup cadence, RPO (recovery point objective).
- **Recoverability** — RTO (recovery time objective). How fast you can restore service after a failure.
- **Observability** — can you debug a production incident at 3am with the data you have? Logs, metrics, traces. The three pillars are not optional.
- **Security** — authn, authz, encryption at rest, encryption in transit, audit log, secret management, principle of least privilege.

## Architecture Decision Records (ADRs)

Every non-trivial architectural choice deserves a one-page ADR, committed alongside code. Format:

```markdown
# ADR-NNNN: [Title — what is being decided]

## Status
[Proposed | Accepted | Superseded by ADR-XXXX]

## Context
What's the situation? What forces are at play? What constraints exist? What evidence
do we have? Be concrete — include numbers, not adjectives.

## Decision
What did we decide? State it as a directive: "We will use X."

## Consequences
What becomes easier? What becomes harder? What did we give up? What's the exit
strategy if this turns out wrong?

## Alternatives considered
Each alternative, briefly, and why it was rejected. This is the most valuable
section for future readers — it preserves the thinking.
```

Write the ADR *before* implementing. If you can't articulate the alternatives and why they lost, you don't understand the decision well enough to make it.

## Anti-patterns to flag immediately

- **Distributed monolith** — services that must deploy together, share a database, or call each other synchronously in long chains. Worst of both worlds.
- **Anemic domain model** — entities with only getters/setters; all logic lives in `XxxService` classes. This is procedural code wearing OO clothing.
- **God service** — one service that knows about everything. Usually called `CoreService`, `BusinessLogicService`, or worse, `Manager`.
- **Shared database between services** — destroys the main reason to have services in the first place.
- **Synchronous chains across service boundaries** — A calls B calls C calls D. Every additional hop multiplies failure probability and tail latency.
- **Two-phase commit across services** — if you find yourself reaching for this, redesign. Use sagas (compensating transactions) or rethink the boundary.
- **Premature caching** — adding Redis before measuring. Now you have a cache invalidation problem you didn't need.
- **Premature microservices** — splitting before the team or load demands it. You inherit all the cost, none of the benefit.
- **Big-bang rewrite** — never works. Use the strangler-fig pattern: route traffic incrementally to the new system, kill the old one path by path.
- **Letting the ORM design your schema** — the schema should be designed for the access patterns and data integrity, then mapped to objects. Not the other way around.

## Service boundaries — where to draw the line

When splitting into modules or services, the boundary should follow:

1. **Data ownership** — one component owns each piece of data. No two components write the same row.
2. **Rate of change** — things that change together stay together; things that change independently are separated.
3. **Team ownership** — Conway's Law is real. The architecture will mirror the org chart whether you intend it or not, so design with that in mind.
4. **Transactional boundaries** — operations that must be atomic stay in one component. If you need a distributed transaction, the boundary is wrong.
5. **Bounded contexts (DDD)** — the same word means different things in different parts of the business. "Customer" in billing ≠ "Customer" in support. Split there.

## Capacity planning sanity checks

Quick estimates that catch most bad decisions:

- A modern Postgres on decent hardware handles **5K–20K simple queries/sec** comfortably. If your projected load is below that, you don't need sharding.
- A single backend instance handles **a few thousand concurrent connections** with async I/O (FastAPI, Node, Go) or **hundreds** with thread-per-request (sync Python/Ruby).
- A Kafka partition processes **~10K msg/sec** comfortably. Plan partitions for both throughput and parallelism of consumers.
- p99 of N independent calls each at p99=X is roughly **X × log(N) / log(2)** when N is small. Fan-out kills tail latency.
- **Network call ≈ 1ms in-DC, 10–100ms cross-region.** Memory access ≈ 100ns. Disk read ≈ 0.1–10ms. Keep the orders of magnitude in your head.

## Communicating architecture

Diagrams should be at the right altitude:

- **C4 model** is a sane default: Context (system + users + external systems), Container (deployable units), Component (modules within a container), Code (rare, usually unnecessary).
- **Sequence diagrams** for flows that span multiple components, especially failure paths.
- **Data flow diagrams** when the question is "where does this data go and who can see it."

Avoid: 50-box "everything we have" diagrams. Nobody reads them. Pick an audience and an altitude.

## A practical workflow for greenfield design

1. Write the **non-functional requirements** first: scale, latency, availability, consistency, compliance. Numbers, not adjectives.
2. Sketch the **domain model** — the nouns and verbs of the business, ignoring tech.
3. Identify **bounded contexts** and how data flows between them.
4. Pick the **simplest topology** that satisfies the NFRs (almost always: monolith + Postgres + queue).
5. Identify the **two or three biggest risks** (the highest-load path, the strongest consistency requirement, the most external integrations) and design those carefully.
6. Write **ADRs** for the choices you made, including the ones you rejected.
7. Build a **walking skeleton** — end-to-end thin slice through every layer — before filling in features. Proves the architecture works.
8. **Measure as you go.** Add observability before you need it; you can't tune what you can't see.

## Things to push back on

- "Let's use microservices for scale." → "What's your current load and what specifically can't a vertical scale handle?"
- "We need Kubernetes." → "What's your team size and deployment cadence? Below ~10 services, managed app platforms (Render, Fly, Railway, App Engine) are usually faster.
- "Let's add a NoSQL database for flexibility." → "What's the access pattern? Postgres JSONB covers most of what people reach for MongoDB for, with transactions."
- "We need event sourcing for auditability." → "Would an audit log table work? Event sourcing is a bigger commitment than people realize."
- "Let's microservice this off." → "What is the data ownership boundary, and is anyone else going to deploy independently of you in the next 6 months?"

The goal isn't to say no — it's to make sure the cost is paid for a reason.