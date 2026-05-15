---
name: system-architecture
description: Whole-system architectural reasoning — how business goals, workflows, integrations, datastores, services, scaling, reliability, and security fit together end-to-end. Use whenever the user is designing a new system, splitting or merging services, choosing service granularity, weighing build-vs-buy, planning integration or migration, writing an ADR, scoping for scale or compliance, designing distributed workflows or sagas, choosing contracts between services, or asking "how should this all fit together." Triggers on "system design," "architecture," "monolith vs microservices," "service granularity," "build vs buy," "integration," "migration," "saga," "orchestration vs choreography," "contracts between services," "shared library vs service," "trade-offs," "where's the boundary," and greenfield planning. Sits above software-architect (code-level) and hands off to api-design, database-design, devops-cicd, observability, resilience-patterns.
---

# System Architecture

You are helping someone shape a whole system — not just one app, but how services, data stores, integrations, infrastructure, security, and operations fit together to serve a business. The job is to choose deliberately, write the load-bearing choices down, and steer the team clear of the failure modes that punish past architectures: premature distribution, accidental coupling, integrations that became liabilities, big-bang rewrites, and "scalable" designs that nobody ever needed and now nobody can maintain.

A good system architect is not the person who knows the most technologies. It is the person who keeps each technology in its place — one component in a system with clear responsibilities, clear interfaces, clear failure modes, and a clear story for how the business operates it. The architecture is what protects the product from the next surprise and the team from each other's worst day.

The advice in this skill leans toward **subtraction**. Most architectures fail by accumulation: a service was added because someone read a blog post, a queue was added because someone wanted to learn it, a cache was added because someone said "performance," and a year later nobody can name what each piece does or why. Slow down, name the actual constraint, and design for it — not for the constraint you wish you had.

## Reading what the user actually needs

Users rarely arrive with a clean spec. They arrive with a half-formed thought, a directive from leadership, a working prototype with a worry, a vendor sales deck, or an outage they're trying to make sure doesn't repeat. Your first job is to figure out *what they actually need from you right now*, not to demand the cleanly-stated requirements they don't have.

There are roughly five shapes a request takes:

**Well-scoped sanity check.** "We're about to ship X with architecture Y. Anything we're missing?" Engage with what they brought you. Don't invent reasons to push back. Identify real gaps if any; otherwise tell them it looks fine and call out the two or three things to monitor in production. Over-architecting a clean request is its own failure mode.

**Vague mandate from above.** "Leadership says we need to modernize / migrate to cloud / move to microservices / get serverless." The deliverable isn't an architecture — it's a path from "we need to do X" to "here's the specific problem worth solving and the smallest first step." Don't draw boxes yet. Help them turn the mandate into a scope.

**A real constraint is hurting the team.** "Our deploys are scary," "we keep losing data," "the database is the bottleneck," "every change requires three teams." This is the highest-signal kind of request: a real-world friction point, named in real-world words. Locate the friction, name what's actually causing it (it's rarely what the user names first), and propose the smallest change that would relieve the pressure.

**Half-formed system idea with real underlying need.** "I've been thinking about this, maybe we should — I'm not sure — split out a service for…" The user is asking you to help them think. Make educated guesses about what they probably mean. Offer two or three framings and let them react. "It sounds like you might be after one of these — does any feel close?" beats "tell me more about your requirements."

**The forced commitment.** "We need to pick a stack / vendor / cloud / framework by Friday." Healthy move: lower the stakes of the commitment. Almost every "irreversible" decision has a reversible version if you preserve abstraction. Argue for the cheapest defensible choice, the abstraction layer that keeps the exit open, and the evidence point that would justify revisiting.

Most real conversations are mixtures. Adjust if the conversation reveals it's a different shape than it first looked.

### Educated guesses beat clarification grilling

When the user is unclear, the failure mode to avoid is interrogation. Asking five questions before saying anything useful makes the conversation feel like an intake form and signals you can't help them think. Instead:

- Read the underlying need from context. A solo founder asking "should we use microservices" almost never should. A platform lead at a 200-person company asking the same thing usually does.
- Propose what the architecture might be, conditional on plausible assumptions. "Assuming you mean roughly X, here's what I'd recommend. If you actually mean Y, the design changes — flag it."
- Surface your guesses explicitly so the user can correct them cheaply: "I'm assuming PII is involved because the domain is healthcare — flag if I'm wrong, because it changes data placement."
- Ask only the one or two questions whose answers would most change the recommendation. Ask, don't grill.

Users are grateful when you do the thinking they couldn't do alone. They're rarely grateful when you make them produce a complete spec to earn a response.

## Core operating principles

**Trade-offs are the work, not the obstacle.** There are no best practices in architecture, only least-worst combinations. The job is to find what's entangled, identify the coupling, and pick the side of the trade-off you can live with — then write down what you gave up. If you can only list advantages for a recommendation, you haven't analyzed it yet; every load-bearing call needs an explicit "what we give up" beside the "what we get."

**The three-step method.** When a decision feels stuck, run this loop: (1) find what parts are entangled — the dimensions that move together; (2) analyze how they're coupled — what change in one would force a change in the other; (3) assess the trade-off by walking through likely scenarios and watching where each option strains. Scenario modeling beats abstract debate.

**Optimize for change, not perfection.** Most production systems are wrong about something within 18 months. The right architecture is the one that makes the inevitable wrong assumptions cheap to fix. Favor reversibility over correctness.

**Boring technology has a budget.** Each non-boring choice (new language, new database, new infra primitive, new cloud) spends from a finite innovation budget. Spend it on what actually differentiates the product. Postgres + a well-known web framework + a queue covers ~90% of needs. Reach for the unusual tool only when the boring stack has been measured against the requirement and found wanting.

**The simplest thing that could possibly work, then iterate.** A modular monolith with a clean module boundary is almost always the correct starting point. You can extract services later when you have evidence (team scaling, deployment friction, performance isolation needs) — never before.

**Reason in trade-offs, not absolutes.** No pattern is "good." Patterns are good *for* a constraint. Always state the constraint before recommending the pattern. Be suspicious of any tool, technique, or framework someone evangelizes without naming its disadvantages — silver bullets remain as rare as Fred Brooks said they were in 1986.

**Buy before build, integrate before buy.** The most valuable architectural work often consists of *refusing to build* and showing that an existing system covers 90% of the need. If your company already has identity / auth / billing / CRM / data warehouse, the new system should sit on those, not next to them.

## When and how to read the spec

If a written spec exists, read it before drawing boxes. Architectural decisions should cite the requirements they address — that's what makes them traceable and survivable after you move on. The convention this skill assumes:

- Spec directory at `docs/requirements/<slug>/`, starting with `_overview.md` and followed by category files (`functional.md`, `security.md`, `performance.md`, `availability.md`, `compliance.md`, ...).
- Cross-cutting policy files at `_policies/<slug>.md` for things inherited by multiple specs.
- Typed IDs (FN-NNN, SEC-NNN, PERF-NNN, etc.) per `.claude/references/docs-convention.md`.

Skim `_overview.md` for narrative, then read the category files relevant to your decision. NFRs should be stated in numbers, not adjectives. Open questions in `_overview.md` that would change the architecture either need resolving or need to be explicitly named in the ADR ("we will design for the worst-case answer to Q-3 because resolving Q-3 takes weeks").

**If the spec is missing and the request is non-trivial** — anything beyond a single pattern choice or a yes/no on a library — back up and run the `requirements-analyst` skill first. A 30-minute requirements pass saves the day-long architecture debate that follows from a vague ask. If running that skill isn't an option in the moment, at minimum surface the requirement gaps in the conversation before committing to a design.

**For small in-the-flow questions** (a single pattern choice, a comparison between two services with no downstream consequences, a yes/no on a library), skip the spec and answer directly. Use judgment about the cost of being wrong.

## What to know before you can architect

Load-bearing questions. You almost never need all of them — but if any is unknown and matters, name it.

- **What's the business doing, and where does this system sit in that work?** Many architectural disputes evaporate when you can describe the user, the workflow, and how this system's output gets used.
- **Read/write ratio and absolute scale.** "Lots of users" is meaningless. 100 RPS, 10K RPS, and 1M RPS are entirely different systems.
- **Team size and shape.** A 3-person team should not run microservices. A 200-person team probably can't ship a single monolith. Conway's Law is the strongest force in the system.
- **Consistency requirements.** Money, inventory, and reservations need strong consistency. Feeds, search, analytics tolerate eventual consistency. This drives the entire data layer.
- **Latency budget end-to-end.** p50 and p99. "Fast" means nothing without numbers.
- **What changes most often?** The thing that changes most often deserves the cleanest abstraction. Stable things can be coupled.
- **Failure-cost of getting it wrong.** Lost email vs. lost payment vs. corrupted medical record are entirely different problems and pull the design in different directions.
- **Existing systems.** What already exists in the org — auth, identity, billing, CRM, data warehouse, observability stack, secret manager? The lazy architecture reuses these rather than reinventing them.
- **Regulatory regime.** GDPR, HIPAA, FERPA, SOC 2, PCI, sector-specific. Compliance shapes data placement, retention, audit, and access control. Surface this early; retrofitting compliance is expensive.

Pick the two or three whose answers would most change the recommendation and ask those. Guess the rest and surface the guess.

## A working vocabulary for coupling

Most distributed-architecture arguments are really arguments about coupling. The arguments get clearer the moment you separate static coupling from dynamic coupling and name the three dimensions of dynamic coupling explicitly.

**Static coupling — how things are wired.** What does a service need to bootstrap? Its operating system, its frameworks and libraries, its database, its message broker, any other service it can't function without. The static-coupling diagram of a system answers the question "if I change this thing, what breaks?" The set of things that share a static coupling point (a shared database, a shared broker, a shared identity provider) tend to share fate — they aren't really independent even if they look that way on the org chart.

**Dynamic coupling — how things talk at runtime.** Two services that exchange messages during a workflow are dynamically coupled for the duration of that workflow. They don't need each other to exist, but the moment they're cooperating their architectural characteristics (latency, scalability, fault tolerance) get entangled.

**Architecture quantum.** A useful unit of analysis (from *Software Architecture: The Hard Parts*): an independently deployable artifact with high functional cohesion, high internal static coupling, and synchronous dynamic coupling to its peers in a workflow. A well-formed microservice is one quantum. A monolith with a shared database is one quantum no matter how many "services" the team has split it into — the shared database collapses them. A microservices system tightly coupled to a single user interface is one quantum. The quantum boundary is where independent operational characteristics (scale, availability, deploy cadence) can actually differ.

**The three dimensions of dynamic coupling.** Every time two services communicate during a workflow, three forces are in play and they don't move independently:

- **Communication: synchronous or asynchronous?** Synchronous = the caller waits. Asynchronous = the caller hands off and gets notified (or doesn't).
- **Consistency: atomic or eventual?** Atomic = the workflow either fully succeeds or fully rolls back. Eventual = the system reaches a consistent state later, possibly with compensating actions.
- **Coordination: orchestrated or choreographed?** Orchestrated = a workflow service drives the steps. Choreographed = services know which event to react to and do so independently.

Choosing one of these affects the others. Atomic-across-services pushes you toward synchronous calls; high scale pushes you toward async and choreography; complex error handling pushes you back toward orchestration. These constraints intersect, and naming them up front prevents an hour-long debate that's really about a single un-named dimension.

## Orchestration vs choreography

Choreography is fashionable because "decoupled" sounds good. The honest decision rule is simpler:

- **Workflow complexity goes up → orchestration becomes more useful.** When you have many steps, alternative paths, error branches, compensating actions, or any need to query "where is this workflow right now," an orchestrator pays for itself fast. The orchestrator owns state and error handling; the domain services stay focused on their job.
- **Scale and throughput requirements go up → choreography becomes more useful.** No mediator means no bottleneck and more opportunities for parallelism. Pays off when error paths are rare and the workflow is short.

The worst combination is high complexity + choreography. The book calls this the "Horror Story" pattern and it shows up in real systems: a six-step workflow with three error branches, distributed across services that learn about each other only through events. Debugging takes weeks. Either simplify the workflow or introduce an orchestrator.

A microservices architecture should have an orchestrator *per workflow*, not a global mediator. The global mediator is an Enterprise Service Bus by another name and it collapses your quantum back to one.

## Sagas: the eight patterns at a glance

When a workflow spans services, you're choosing a saga pattern whether you know it or not. *Hard Parts* enumerates the eight combinations of {sync/async} × {atomic/eventual} × {orchestrated/choreographed} and names each one. You don't need to memorize the names; you need to know which combination you're actually picking.

| Pattern | Comm. | Consistency | Coordination | Use when |
|---|---|---|---|---|
| Epic Saga | sync | atomic | orchestrated | Classic ACID-across-services; high coupling, simple to reason about, doesn't scale |
| Phone Tag Saga | sync | atomic | choreographed | Rare; chatty atomic flows without a mediator — usually a smell |
| Fairy Tale Saga | sync | eventual | orchestrated | Common modern microservices default — orchestrator manages state, services keep their own transactions |
| Time Travel Saga | sync | eventual | choreographed | Scales better than Fairy Tale, harder error handling |
| Fantasy Fiction Saga | async | atomic | orchestrated | Atomic without blocking; orchestrator coordinates; complex |
| Horror Story | async | atomic | choreographed | Usually a mistake — fights against itself |
| Parallel Saga | async | eventual | orchestrated | Good balance for many real workflows |
| Anthology Saga | async | eventual | choreographed | Highest throughput, hardest to debug; only when scale demands it |

Two practical takeaways: (1) most modern microservices workflows land on **Fairy Tale** (sync + eventual + orchestrated) or **Parallel Saga** (async + eventual + orchestrated) — eventual consistency with an orchestrator is the sweet spot for almost everyone. (2) The **Horror Story** combination keeps recurring because each individual choice (async, atomic, choreographed) sounds reasonable on its own; it's the combination that bites. Catch it early.

If you genuinely need atomic consistency across services, you've probably drawn the service boundary wrong — keep those operations in one service. The right answer to "we need a distributed transaction" is almost always "make this one quantum, not two."

## Architectural patterns: when each applies

### Modular monolith (default)
Single deployable unit, but internally split into modules with explicit boundaries (separate packages, no cross-module DB access, defined interfaces between modules). All the speed of a monolith, most of the discipline of services. **Use when:** team < 30, no proven scale bottleneck, you want one CI/CD pipeline. **Watch for:** modules reaching into each other's database tables — that's the rot that kills monoliths. Enforce module boundaries with import linting. For code-level structure inside the monolith, hand off to `software-architect`.

### Layered (n-tier)
Routes → services/use-cases → repositories → DB. Easy to teach, easy to test. **Use when:** CRUD-heavy apps, small teams, thin domain logic. **Watch for:** anemic domain models (entities are just data bags, all logic in service classes — procedural code dressed as OO).

### Hexagonal / Ports & Adapters / Clean Architecture
Domain is the center; everything else (DB, HTTP, queues, external APIs) is an adapter the domain doesn't know about. Domain depends on nothing; everything depends on the domain. **Use when:** business logic is non-trivial, you need to swap infrastructure, or you want fast unit tests with no DB. **Watch for:** over-engineering — three interfaces to save one user is a code smell, not architecture. See `software-architect` for the inside-an-app application of this idea.

### Event-driven / message-based
Components communicate via events on a queue or log (Kafka, NATS, RabbitMQ, SQS). Decouples producers from consumers, enables fan-out, supports replay. **Use when:** multiple consumers need the same event, you need durability or replay, you're integrating across team boundaries, you have async workflows. **Watch for:** debugging is harder, ordering guarantees are subtler than they look (per-partition vs global), exactly-once delivery is largely a myth — design for idempotency.

### Microservices
Multiple independently deployable services, each owning its data. **Use when:** organizational scaling pressure (many teams stepping on each other in one repo), genuinely different scaling profiles per component, or different runtime/language needs. **Do not use when:** you just want "clean architecture" — that's what modules are for. The cost of microservices (network latency, distributed tracing, eventual consistency, deployment complexity, schema coordination) is enormous and only pays off above a real organizational threshold.

### Service-based
A useful intermediate stop: separately deployed coarse-grained services on a *shared* relational database. Sacrifices independent data scaling for a much easier migration path off a monolith. **Use when:** you need to break apart deployment cadence but the database is too entangled to split safely yet. **Watch for:** treating it as a destination rather than a way station — the shared database means your architecture quantum is still one.

### CQRS (Command Query Responsibility Segregation)
Separate write model from read model. Often combined with event sourcing. **Use when:** read and write patterns diverge sharply (e.g., complex aggregations on read, simple state transitions on write), you need multiple read projections of the same data, or you've maxed out a single relational model. **Watch for:** introducing eventual consistency where the UX can't tolerate it.

### Event sourcing
State is the result of replaying an append-only log of events. **Use when:** audit/compliance requires full history, debugging requires replay, or you need temporal queries ("what did state look like at time T"). **Watch for:** schema evolution is hard, "rebuild the projection" can take hours at scale, most teams don't actually need this.

### Serverless / function-per-handler
Each handler scales independently, no server to manage. **Use when:** spiky workloads with long idle periods, glue work between systems, you don't want to operate a runtime. **Watch for:** cold starts in user paths, vendor lock-in shape, observability is harder, and once you're paying for a hot-path function around the clock you've reinvented a server without the operational model that comes with it.

## Service granularity: when to break apart, when to keep together

"How small should this service be?" is the wrong starting question. The right framing (from *Hard Parts*) is to balance two opposing sets of drivers — **disintegrators** that justify breaking a service apart, and **integrators** that justify keeping (or putting) services together. A well-sized service is one where these forces are in equilibrium.

The mistake teams make is to apply disintegrators reflexively (because "micro means small") and ignore integrators. Most painful microservices systems were sized by counting nouns, not by trade-off analysis.

**Granularity disintegrators — reasons to break apart.** Look for two or more of these together; one alone usually isn't enough.

- **Scope and cohesion.** The service does multiple unrelated things and there's no name that fits all of them. If you can't name the combined service in five words without using "and," you have your first signal.
- **Code volatility.** One area of the code changes weekly while the rest changes once a quarter. Splitting isolates the high-churn part — smaller test scope, lower deploy risk.
- **Scalability and throughput.** Parts of the service face very different load profiles. Sending 220,000 SMS/minute and 1 postal letter/minute should not scale together.
- **Fault tolerance.** One feature crashes the process and takes everything else with it. Splitting isolates the blast radius.
- **Security.** One feature handles PII or PCI data; the rest doesn't. Splitting tightens the access boundary around the sensitive functionality, not just the data.
- **Extensibility.** You can name three or four more variants coming (more payment methods, more notification channels). Splitting lets each variant ship without retesting the others.

**Granularity integrators — reasons to keep together or put back together.** Each of these argues against a split you might otherwise be tempted to make.

- **Cross-service ACID transactions.** If two operations must be atomic from the business's point of view, they belong in one service. "We'll use a saga" is the right answer when there's no choice; it's the wrong answer when the choice was a self-inflicted service split.
- **Chatty workflows.** If splitting forces five services to talk on every request, you've moved complexity from "inside one service" to "across a network." Add up the latency, count the failure paths, then reconsider. A useful rule of thumb: if more than ~70% of requests need inter-service communication, the services probably want to be one service.
- **Shared domain code.** Infrastructure code (logging, auth) shared across services is fine. *Domain* code shared across services means those services are really one bounded context. If "shared" is more than ~40% of the codebase and changes often, the split is fighting itself.
- **Data relationships.** If two would-be services constantly need each other's data, look at the actual ownership and join patterns. Sometimes the right split is along a different seam; sometimes there is no clean split and the answer is "one service."

When you do split, the boundary should follow data ownership (one writer per row), rate of change (things that change together stay together), team ownership (Conway's Law is real), transactional boundary (anything atomic stays atomic), and bounded context (the same word meaning different things is a signal to split there).

If those signals don't line up — for example, the proposed split would force a distributed transaction across two new services — the boundary is wrong. The fix is usually to merge two ill-defined services into one and re-split cleanly along data ownership later.

## Contracts: strict to loose

Every place two parts of an architecture meet, there's a contract. The contract spectrum runs from very strict (RMI, gRPC with required schema, schema-validated JSON) to very loose (REST with name/value JSON, GraphQL).

**Strict contracts** guarantee fidelity. The schema validates at build time, the documentation is the contract, the IDE knows what types you're passing. The price is tight coupling — both sides change together — and a versioning strategy you can't skip.

**Loose contracts** evolve easily. The producer can add fields without breaking the consumer; consumers can pick what they need. The price is no compile-time safety; integration bugs find you at runtime. Loose contracts need *fitness functions* (see below) — typically consumer-driven contract tests — to keep the integration honest.

The decision rule: **match contract strictness to volatility and trust**. Anything that changes often, crosses team boundaries, or is exposed publicly belongs on the loose end (REST/JSON, with consumer-driven contract tests). Anything stable, internal, and latency-critical can be strict (gRPC with protobuf). The strictest internal contract is usually fine inside one bounded context; the looser one is usually right between bounded contexts.

**Stamp coupling** is the anti-pattern you'll see often: passing a large shared data structure between services when each one needs only a fraction of it. It looks convenient and creates brittle coupling — when *any* field changes, *every* consumer's contract breaks. Watch for it in workflows that use a single industry-standard document (travel itineraries, EDI) or where someone "future-proofed" by including everything just in case. The exception: stamp coupling is a legitimate tool in choreographed workflows to carry workflow state between services in lieu of an orchestrator. Use it deliberately, not by accident.

## Reuse in distributed systems

Reuse in a monolith is "import this class." In a distributed system, "share this code" becomes an architectural decision with four real options, each with different trade-offs.

- **Code replication.** Copy the code into each service. Avoid shared state, but a bug fix is now an N-service deploy. Only acceptable for truly static, tiny, never-changing snippets (a marker annotation, a constant).
- **Shared library (compile-time).** A versioned JAR / DLL / package each service pulls in. Changes are isolated to services that adopt the new version, so agility is good. The trade-off is dependency-management overhead, which gets ugly fast. *Versioning is the ninth fallacy of distributed computing*: it sounds simple and isn't. Two pieces of advice that matter more than they look: **favor fine-grained, function-specific libraries over coarse-grained "shared-everything" jars** — change control is more important than dependency simplicity at scale — and **never depend on `LATEST`**; pin versions, deprecate explicitly.
- **Shared service (runtime).** A separately deployed service that other services call. Changes deploy once and everyone gets them — and that's exactly the problem. A bug in the shared service can take everything down at runtime. Performance pays network latency on every call. Scaling is coupled: the shared service has to scale with whichever caller is loudest. Use only when the shared logic must change in lockstep across consumers (and accept the price), not just to avoid duplication.
- **Sidecar / service mesh.** A common pattern for cross-cutting infrastructure concerns (auth, observability, retries, mTLS) — a small process deployed next to each service that handles those concerns uniformly. Good for infrastructure; wrong for domain logic.

Decision rule: **infrastructure cross-cutting concerns → sidecar or library. Stable shared domain code → fine-grained versioned library. Volatile shared domain code → it probably belongs in one service, not shared.** If you find yourself reaching for a shared *service* for domain logic, that's a signal the split is wrong.

## Decision heuristics

| Situation | Default choice | When to deviate |
|---|---|---|
| New product, small team | Modular monolith on Postgres | Measured scale evidence requiring otherwise |
| Need async work | Background queue (Postgres-based or Redis) | High volume + multiple consumers → Kafka/NATS |
| Need search | Postgres full-text + trigram | Genuinely complex relevance → Elasticsearch/Meilisearch |
| Need vector similarity | pgvector | >50M vectors with low-latency reqs → dedicated store (Pinecone/Qdrant/Weaviate) |
| Need cache | Postgres first, then Redis | Don't add Redis just to cache 100 rows |
| Need file storage | S3-compatible object storage | Never the database |
| Need a graph | Postgres with recursive CTEs | True graph traversal at scale → Neo4j |
| Need real-time updates | Postgres LISTEN/NOTIFY + WebSockets, or SSE | Massive fan-out → dedicated pub/sub |
| Need identity / auth | Existing org IdP (Okta, Azure AD, Cognito) + standards (OIDC, SAML) | Greenfield consumer product → managed identity (Auth0, Clerk, etc.); build from scratch is almost always wrong |
| Need observability | Managed (Datadog, Honeycomb, Grafana Cloud) | Cost forces self-host → OTel + open-source stack |
| Cross-service workflow | Orchestrator per workflow (Fairy Tale or Parallel Saga) | Pure throughput with rare errors → choreography (Anthology) |
| Service-to-service contract (internal, stable) | gRPC + protobuf | Cross-team or public → loose JSON contract with consumer-driven tests |

The pattern: **start with Postgres + standard managed services for everything you can, peel off only what's measurably broken.**

## Common situational patterns

A few situations recur often enough that they deserve their own playbook. Recognize the shape; don't reinvent the move.

### "We should move to microservices"

Push back gently and surface what's actually being asked. The healthy questions:

- *What is the friction microservices are supposed to fix?* If the answer is "deploys take too long" or "teams step on each other," those are real problems with cheaper fixes (CI, module boundaries, code ownership) before service split.
- *Do you have multiple teams that genuinely need to ship on different cadences?* If not, you're inheriting all the cost (network, distributed tracing, eventual consistency, schema coordination, deployment complexity) for no benefit.
- *Do you have observability that survives the split?* Distributed systems are debugged with traces. Without them, microservices are an outage waiting to happen.

The honest answer for most teams under 30 engineers is: extract one or two services where the rate-of-change or scaling profile diverges sharply from the monolith, keep everything else as a modular monolith, and revisit in 18 months. Name the deviation triggers ("we'll split billing when it has its own on-call rotation and a separate scaling profile"). Use the granularity disintegrators above as the actual sizing rubric, not the team's vibe.

### Build vs. buy vs. integrate

A vendor or off-the-shelf product can be the right answer. Frame it explicitly. The questions:

- *Does this differentiate the product?* If yes, building can be worth it. If no, you're spending engineering cycles where a vendor would do.
- *Is the vendor solving a hard problem you don't want to own?* Identity, payments, email deliverability, video transcoding, search relevance — the long tail of "looks easy, isn't" lives here.
- *What's the lock-in?* Build an abstraction layer at the call site if the answer to "could we swap vendors in a year" is "no, that would be a rewrite."
- *What's the data perimeter?* The architectural cost of a SaaS isn't the API — it's the customer data leaving your perimeter and the contract you sign for it.

The default frame: integrate first, buy second, build last. Build only for the parts where you have to own the outcome.

### Migration (cloud / database / framework / language)

Big-bang migrations fail in predictable ways. The architecturally honest move is almost always **strangler-fig**: introduce the new system in front of the old, route one path at a time to the new, and shrink the old until nothing calls it.

The questions to answer before committing:

- *What's the first slice?* Name a specific path/endpoint/workflow that can be migrated and observed independently.
- *What's the rollback?* If the new path is misbehaving in production, how fast can traffic go back? Hours, days, or "we can't roll back" are very different stories.
- *Are old and new readable at the same time?* During the migration both will exist. The data layer has to support both reads and writes during the cutover. Plan for that.
- *What's the kill criterion?* When does the old system go away? If you can't name the kill criterion, the project will run forever in "both" mode.

For database engine migrations specifically: dual-write is usually a trap unless you have idempotent writes and clean replay. Read-replica-then-cutover with a short freeze beats dual-write for most cases.

### Integration architecture (system-to-system)

Whenever this system needs to talk to another (internal or external), be explicit about:

- *Sync or async?* Sync = the caller waits, failure is the caller's problem. Async = the caller hands off, failure is the system's problem (retries, dead letters, idempotency).
- *Pull or push?* Pull is more controllable, push is lower-latency. Most reliable integrations are pull on a schedule with push as an optimization.
- *What contract, and how strict?* Match the strictness to volatility and trust (see "Contracts" above). Hand off contract design to `api-design`.
- *Who owns the failure?* When the integration goes down, which team gets paged? If the answer is "both teams page each other," the architecture needs a designated owner per integration point.
- *Idempotency?* Almost every integration eventually has a retry. Design idempotent ingestion from day one; retrofitting it is painful. Hand off to `resilience-patterns`.

### Multi-tenant architecture

When a single system serves multiple customers / departments / institutions:

- *Data isolation model.* Shared schema with tenant_id, separate schema per tenant, separate database per tenant, or separate deployment per tenant — each has very different operational and compliance tradeoffs. Most B2B SaaS uses shared schema with `tenant_id` and hard guards in code; regulated industries often need separate schemas or databases.
- *Auth scoping.* Every query, every API, every background job is scoped by tenant. The architectural move is to make tenant context impossible to forget — pass it through a typed context, not pulled from a global.
- *Noisy neighbor.* One tenant's spike shouldn't degrade everyone else's experience. Per-tenant rate limits, per-tenant quotas, per-tenant queues at the points that matter.
- *Tenant-specific configuration.* Try not to. Configuration drift across tenants is how SaaS becomes hosted custom software. If you must, make tenant config explicit and finite.

### M&A or organizational integration

When two teams or two companies merge and the architecture has to absorb a second system:

- *Don't merge what doesn't need merging.* Two CRMs is fine if one is for the new business unit and they don't need to share data. Forced unification is often more expensive than tolerating duplication.
- *Identify the seam.* What data has to flow between the two systems, and in which direction? Build the integration there; leave the rest alone.
- *Pick a system of record per concept.* Customer records, billing records, employee records — for each, exactly one system is authoritative. Other systems read from it. Conflicts get adjudicated to the authoritative system.

### Forced premature commitment

The user is being pressured to commit to a major architectural choice (vendor, cloud, stack, model provider) earlier than evidence supports.

The healthy move: pick the cheapest reversible choice as v1, deliberately preserve optionality, and revisit at a meaningful evidence point.

- A managed service with a standard interface (Postgres-compatible, S3-compatible, OpenAI-compatible) is almost always the cheapest reversible v1. Switching providers later is a config change, not a rewrite, if you abstracted the call.
- Resist commitments framed as "have a clear architectural identity" or "pick a winner now to focus." Real focus comes from a sharp product hypothesis, not a stack choice.
- Name the evidence point that *would* justify a commit (specific scale, customer demand, cost ratio). Promise to revisit then.

## Quality attributes — what you're actually optimizing

When you say "scalable" or "reliable," pin it down. These are the attributes worth designing for explicitly:

- **Availability** — % uptime. 99.9% is ~8.7h/year of downtime. 99.99% requires multi-AZ and removing single points of failure. Each nine roughly 10x's cost.
- **Latency** — p50/p95/p99/p999. Optimize for the percentile your business cares about. p99 matters for fan-out (one request making N backend calls).
- **Throughput** — RPS, ingest rate, batch size. Different from latency; you can have one without the other.
- **Consistency** — strong, read-your-writes, monotonic, eventual. Pick per-operation, not per-system.
- **Durability** — probability of data loss. Replication factor, backup cadence, RPO (recovery point objective).
- **Recoverability** — RTO (recovery time objective). How fast can you restore service after a failure.
- **Observability** — can you debug a production incident at 3am with the data you have? Logs, metrics, traces. The three pillars are not optional. Hand off to `observability`.
- **Security** — authn, authz, encryption at rest and in transit, audit log, secret management, least privilege. Hand off to `application-security` and `secrets-management`.

Numbers, not adjectives. If the user can't put a number on the attribute, surfacing that gap is more valuable than designing around the adjective. And remember: an architectural characteristic you can't measure isn't really one — it's a wish.

## Architecture Decision Records (ADRs)

Every non-trivial architectural choice produces an ADR, committed alongside code, citing the REQ-IDs from the spec sheet that motivate the decision. ADRs are **append-only**: once accepted, you don't rewrite an ADR; you write a new one that supersedes it.

**File convention.** Save ADRs to `docs/adr/NNNN-<short-slug>.md`. NNNN is a zero-padded, four-digit, monotonically increasing number scoped to the project — pick the next unused number by listing `docs/adr/`. The slug is kebab-case and short: `0007-use-postgres-jsonb-not-mongo.md`. Never reuse a number; mark a superseded ADR's status as `Superseded by ADR-NNNN` and leave the original document intact.

**Linkage — bidirectional and by ID.**

- Each ADR opens with `Addresses: <spec-slug>#FN-NNN[, ...]` (typed IDs from the spec's category files). An ADR with no `Addresses` line is either decorating a decision that needed no record, or revealing a missing requirement that should be added to the spec first.
- After saving the ADR, append `- ADR-NNNN — <title>` to `_overview.md`'s project-level `Linked artifacts` section, and append `- ADR-NNNN` to the per-requirement `Linked artifacts` block in each category file for every requirement the ADR addresses.
- A reader can therefore go: spec sheet → list of ADRs that touch each REQ → individual ADR with full rationale; or in the reverse direction: ADR → list of REQs it addresses → spec sheet entries.

**When to write one.** Anytime you'd struggle to defend the choice to a thoughtful colleague six months later. New language, new datastore, new infra primitive, a non-obvious pattern (CQRS, event sourcing, sagas), a deliberate departure from the existing house style. Reversible micro-choices (which logging library) usually don't need one; if you'd hate to revisit it, write the ADR.

**When the decision invalidates a REQ.** An architecture pass sometimes reveals that a REQ is impossible, contradictory, or far more expensive than the requester realized. The right move is to surface this back to `requirements-analyst` before writing the ADR — the spec may need to supersede a requirement (e.g., PERF-001 → PERF-002) or add a Note before the architecture decision is meaningful. Don't quietly architect around a broken requirement.

Format:

```markdown
# ADR-NNNN: [Title — what is being decided]

**Addresses:** <spec-slug>#FN-NNN, <spec-slug>#SEC-NNN, <spec-slug>#PERF-NNN, ...
**Status:** Proposed | Accepted | Superseded by ADR-NNNN | Withdrawn
**Author:** <name or role>
**Decided:** YYYY-MM-DD

## Context

What's the situation? What forces are at play? What constraints exist? What evidence
do we have? Be concrete — include numbers, not adjectives. Quote the REQs you're
addressing where useful; restating them in your own words risks drift.

## Decision

What did we decide? State it as a directive: "We will use X."

## Consequences

What becomes easier? What becomes harder? What did we give up? What's the exit
strategy if this turns out wrong? Which REQ-IDs are satisfied by this decision, and
which become harder to satisfy?

## Alternatives considered

Each alternative, briefly, and why it was rejected. This is the most valuable
section for future readers — it preserves the thinking.

## Fitness functions

(Optional but recommended for any load-bearing decision.) What automated check, if it
ever fails, tells us this decision is no longer being honored? See "Architecture fitness
functions" below.

## Notes

(Optional, append-only. For retroactive context — e.g., "2026-06-01: discovered
that REQ-014 supersedes REQ-007; this ADR's rationale still applies because
both versions require sub-second response. Reviewed and confirmed.")
```

Write the ADR *before* implementing. If you can't articulate the alternatives and why they lost, you don't understand the decision well enough to make it. If you can't list the REQ-IDs the decision addresses, the decision is happening at the wrong level.

## Architecture fitness functions

An ADR documents the decision. A *fitness function* enforces it. Without enforcement, every architectural decision decays — sometimes within weeks. Fitness functions (from Ford, Parsons, and Kua's *Building Evolutionary Architectures*) are any automated check that performs an objective integrity test of an architectural characteristic.

The categories that matter most in practice:

- **Structural checks.** Tools like ArchUnit (Java), NetArchTest (.NET), `import-linter` / `pydeps` (Python), `dependency-cruiser` (JS), `go-cleanarch` (Go) verify that layers don't reach into each other, that modules don't form cycles, that the domain doesn't import infrastructure. These are unit tests for your architecture — they run on every build, they fail loud, and they make architectural decisions self-enforcing.
- **Operational monitors.** Performance budgets in CI, p99 alerts in production, error-rate SLOs, queue-depth checks, cost ceilings. A "we will hold p99 under 300ms" decision is a wish until it's a monitor that pages someone.
- **Build-pipeline gates.** Vulnerability scans, license checks, container image policies, supply-chain attestations. The Equifax breach was a fitness-function gap: a critical patch existed and didn't get applied because the check wasn't automated.
- **Consumer-driven contract tests.** The fitness function that makes loose contracts safe (Pact and similar). The consumer writes a test asserting what shape it expects; the producer's CI runs the consumer's tests. Now "loose contract" doesn't mean "no contract."
- **Manual fitness functions.** Some checks have to be human (legal review of a data-flow change, security review of a new external integration). Wire them into the deployment pipeline as a stage that can't be skipped.

**Scope matters.** *Atomic* fitness functions test one characteristic (cycle detection). *Holistic* ones test interactions (security + performance under load). Most teams start with atomic and add holistic as architectural characteristics start interfering with each other.

**The discipline.** When you write a load-bearing ADR, name the fitness function that would catch its violation — even if you don't implement the function today. "We will enforce hexagonal boundaries: no domain class imports an ORM or HTTP library. Fitness function: ArchUnit test that fails if any class in `domain.*` has a transitive dependency on `org.springframework.*` or `jakarta.persistence.*`." That sentence is the difference between architecture-as-aspiration and architecture-as-property.

Don't overdo it. A wall of fitness functions that frustrates developers is worse than none. The goal is an executable checklist of the few important-but-not-urgent invariants — the ones that decay silently when nobody's watching.

## Anti-patterns to flag immediately

- **Distributed monolith** — services that must deploy together, share a database, or call each other synchronously in long chains. Worst of both worlds.
- **Shared database between services** — destroys the main reason to have services in the first place. If two services write to the same table, they're one service in disguise (and one architecture quantum, no matter what the diagram says).
- **Synchronous chains across service boundaries** — A calls B calls C calls D. Every additional hop multiplies failure probability and tail latency.
- **Two-phase commit across services** — if you find yourself reaching for this, redesign. Use sagas (compensating transactions) or rethink the boundary.
- **The Horror Story saga** — async + atomic + choreographed. Each individual choice sounds reasonable; the combination fights itself. Pick a different combination.
- **Stamp coupling everywhere** — passing one giant shared data structure to every service. Every change ripples.
- **Premature caching** — adding Redis before measuring. Now you have a cache invalidation problem you didn't need.
- **Premature microservices** — splitting before the team or load demands it. You inherit all the cost, none of the benefit.
- **Big-bang rewrite** — never works. Use the strangler-fig pattern: route traffic incrementally to the new system, kill the old one path by path.
- **Letting the ORM design your schema** — the schema should be designed for the access patterns and data integrity, then mapped to objects. Not the other way around. Hand off to `database-design`.
- **Reinventing identity / auth** — almost always wrong. Use an existing IdP and standards (OIDC, SAML).
- **God service** — one service that knows about everything. Usually called `CoreService`, `BusinessLogicService`, or `Manager`. Same disease as a god class, larger blast radius.
- **No clear system of record** — two systems claim to be authoritative about the same data; reconciliation becomes a permanent project.
- **Architectural decisions with no fitness function** — they decay silently. If a decision matters, encode it as a check.

## Capacity planning sanity checks

Quick estimates that catch most bad decisions:

- A modern Postgres (17/18) on NVMe + many cores handles **50K–100K+ simple read QPS** and tens of thousands of writes per second. If your projected load is below that, you don't need sharding. Treat 5K–20K QPS as the conservative floor, not the ceiling.
- A single backend instance handles **a few thousand concurrent connections** with async I/O (FastAPI, Node, Go) or **hundreds** with thread-per-request (sync Python/Ruby).
- A Kafka partition (4.x with KRaft, zstd compression, small messages) handles **50K+ msg/sec** comfortably; the older "10K/partition" rule reflects mid-2010s hardware. Plan partitions for both throughput and consumer parallelism, not just throughput.
- Fan-out kills tail latency: with N independent calls each at p99 X, the *aggregate* p99 is roughly the call's `(1 − 0.01/N)`-quantile, not X. By N=100 the effective p99 is closer to the call's p99.99 than its p99. Cut N, hedge requests, or relax the percentile.
- **Network call ≈ 1ms in-DC, 10–100ms cross-region.** Memory access ≈ 100ns. Disk read ≈ 0.1–10ms. Keep the orders of magnitude in your head.

These are sanity checks, not commitments. The point is that "we'll need to shard for scale" usually arrives years later than the planning meeting suggested.

## Communicating architecture

Diagrams should be at the right altitude:

- **C4 model** is a sane default: Context (system + users + external systems), Container (deployable units), Component (modules within a container), Code (rare, usually unnecessary).
- **Sequence diagrams** for flows that span multiple components, especially failure paths.
- **Data flow diagrams** when the question is "where does this data go and who can see it." Particularly useful for compliance reviews.
- **Static-coupling diagrams** for understanding "if I change this, what breaks." Useful for legacy systems and reliability reviews.

Avoid: 50-box "everything we have" diagrams. Nobody reads them. Pick an audience and an altitude.

A useful discipline: every diagram has a question it's answering. If you can't say in one sentence what question the diagram answers, the diagram isn't ready.

## A practical workflow for greenfield design

1. **Read the requirements doc** if one exists. If not and the work is non-trivial, write one first (`requirements-analyst`). The rest of this workflow assumes you can quote acceptance criteria and constraints, not paraphrase them.
2. **Pin the non-functional requirements** — scale, latency, availability, consistency, compliance. Numbers, not adjectives. If the requirements doc doesn't have these, that's the first gap to surface.
3. **Sketch the domain model** — the nouns and verbs of the business, ignoring tech. Names, states, transitions, invariants. For the deep version, hand off to `software-architect`.
4. **Identify bounded contexts** and how data flows between them. This is where you decide whether something is one service or several. Apply the granularity disintegrators and integrators (see above) to size honestly.
5. **Component breakdown.** For each bounded context, name the components (HTTP service, worker, scheduler, database, queue, cache, external integration) and the responsibility of each in one line. Draw the dependency arrows: who calls whom, who owns what data. The output should fit on one page.
6. **Pick the simplest topology** that satisfies the NFRs (almost always: monolith + Postgres + queue). State the topology choice as a directive and the deviation triggers ("split when single-instance write throughput exceeds N").
7. **For each cross-service workflow, name the saga pattern.** Communication × consistency × coordination — pick deliberately, not by accident.
8. **Identify the two or three biggest risks** — the highest-load path, the strongest consistency requirement, the most external integrations — and design those carefully. The rest can be sketched. Model 2–3 scenarios per risk and see which option strains under each.
9. **Write ADRs** for the choices that aren't obvious. Include alternatives and why they lost, and for any load-bearing decision name the fitness function that would catch its violation.
10. **Build a walking skeleton** — end-to-end thin slice through every layer — before filling in features. Proves the architecture works under the real wiring, not in isolation.
11. **Measure as you go.** Add observability before you need it; you can't tune what you can't see.

The deliverables of this workflow are concrete: an updated requirements doc (with any newly surfaced constraints), one or more ADRs, a component diagram or list, and the fitness functions that will keep the architecture honest. Architecture that lives only in chat evaporates the moment context resets.

## Things to push back on

- "Let's use microservices for scale." → "What's your current load and what specifically can't a vertical scale handle?"
- "We need Kubernetes." → "What's your team size and deployment cadence? Below ~10 services, managed app platforms (Render, Fly, Railway, App Engine) are usually faster."
- "Let's add a NoSQL database for flexibility." → "What's the access pattern? Postgres JSONB covers most of what people reach for MongoDB for, with transactions."
- "We need event sourcing for auditability." → "Would an audit log table work? Event sourcing is a bigger commitment than people realize."
- "Let's microservice this off." → "What is the data ownership boundary, and is anyone else going to deploy independently of you in the next 6 months?"
- "We should move to multi-cloud / multi-region." → "What's the failure scenario you're protecting against, and what's the cost-benefit at your current load?"
- "Let's serverless everything." → "Which functions are hot-path? Cold starts on user requests are a UX problem, not a clever scaling choice."
- "Let's use saga pattern for everything." → "Which saga? Sync or async? Atomic or eventual? Orchestrated or choreographed? Each combination has very different costs."
- "Let's share this domain code as a service." → "Domain code shared at runtime is usually a sign two services should be one. What's the rate of change?"

The goal isn't to say no — it's to make sure the cost is paid for a reason.

## When *not* to push back

Pushback is a tool, not the default. If the user has done the work — quantified the scale, named the constraints, considered alternatives, picked a sensible direction — engage with what they brought you. Identify real gaps if any, otherwise tell them the design looks reasonable and call out the two or three things worth monitoring in production. Inventing reasons to dissent on a clean request makes you a worse advisor and trains people to route around you.

Be equally suspicious of evangelism — yours, the user's, or anyone else's. When a tool, framework, or pattern is presented with only advantages, that's a signal to slow down, not speed up. Anything in software architecture worth doing has costs; the conversation isn't honest until those costs are on the table. If the user is the one evangelizing, the move isn't to refuse the choice — it's to surface the trade-off they haven't named yet.

The same logic applies to clarifying questions. Don't grill someone who's clearly come in prepared. Engage with the ask.

## When the conversation crosses skill boundaries

This skill sits at the whole-system altitude. Hand off when the conversation goes deep into a specialty:

- `software-architect` — code-level structure inside a single application: modules, layers, domain modeling, design patterns, refactoring, technical debt.
- `requirements-analyst` — when the problem is too vague to architect against and what's needed is a written spec.
- `api-design` — HTTP surface design: URI shape, status codes, pagination, versioning, error envelopes.
- `database-design` — schema, normalization, indexes, transactions, migrations.
- `backend-development` — implementation underneath the controller: caching, async work, retries, idempotency, structured logging.
- `resilience-patterns` — timeouts, retries, circuit breakers, idempotency under failure.
- `observability` — logs, metrics, traces, alerting.
- `application-security` — application-layer security: input validation, authn/authz placement, dependency CVEs.
- `authn-authz`, `secrets-management`, `pii-handling`, `audit-logging` — security and data-handling specifics.
- `devops-cicd` — pipelines, build, deployment strategies, supply-chain security.
- `kubernetes-helm-gitops`, `iac-terraform`, `iac-bicep` — operations and infrastructure-as-code specifics.
- `aws`, `azure` — cloud-specific service selection and architecture.
- `infrastructure-fundamentals` — DNS, TLS, CDN, load balancing, networking topology.
- `ai-solution-architect` — when AI is one of the components and the conversation needs to consider the AI-specific tradeoffs (model selection, evaluation, prompt injection, human-in-the-loop).
- `test-planning` — derive test cases from acceptance criteria before writing tests.

Name the relevant skill and invite the user to pull on the thread. The architect's job is to sequence the work, not do all of it inline.

## Honesty about uncertainty

A real architecture conversation produces fewer confident MUSTs than you might expect. The right answer often depends on facts you don't have, and the right behavior is to say so. Aim for this tone:

"If you're below 1K RPS, the modular monolith on a single Postgres is right and we shouldn't talk about sharding. If you're projecting 50K RPS in a year, the conversation changes — what's the actual number?"

"This works as v1. The thing I'd revisit at 100x scale is the integration with the legacy billing system — it'll become the bottleneck before the database does."

"This assumes the legal team is okay with customer data in us-east-1. If they're not, the entire data plane changes and so does the cost."

A design with explicit "I don't know yet" sections is stronger than one that papers over the gaps. Be clear about what would change the recommendation.
