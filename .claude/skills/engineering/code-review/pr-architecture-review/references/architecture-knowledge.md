# Architecture Knowledge — Reviewer's Field Guide

Distilled reviewing knowledge drawn from application-level architecture
(`software-architect`) and whole-system architecture (`system-architecture`).
This is the deep reference behind the eight review categories: the vocabulary to
*name* a structural problem precisely, the tells that reveal it in a diff, and
the design fix to recommend.

Everything here is reframed for **reviewing a change**, not designing a system
from scratch. You are not the architect of record; you are the reviewer catching
the structural problems a diff introduces or worsens. Stay at the design level,
tie every finding to change cost, and — as always — **ignore
micro-optimizations**; performance tuning is a different review.

## The lens behind every finding

These principles decide whether something is actually a finding or just a
difference of taste. Cite them when you explain *why* a finding costs.

- **Trade-offs are the work.** Every design choice buys something and pays for
  something. A finding is legitimate only when you can name what the current
  shape *costs* — not merely that you'd have done it differently. "You get X,
  you give up Y" is the shape of honest feedback.
- **Optimize for change, not perfection.** The question is never "is this
  perfect" but "will the next change be cheap or expensive?" Flag the things that
  make the *next* change expensive.
- **Abstractions are a tax, not a feature.** Every interface, layer, base class,
  and extension point charges rent forever. An abstraction with one
  implementation and no named second case is a finding (over-engineering), just
  as much as a missing seam is.
- **The rule of three.** First time, just do it. Second time, wince and
  duplicate. Third time, extract. A PR that abstracts on the first occurrence is
  usually premature; a PR that copies the same logic a third time is usually
  missing an extraction. Use the count as evidence.
- **Code in the language of the domain.** Names in the code should match the
  words the business uses. A rename that drifts from domain language is a real
  (if minor) finding — every reader now pays a translation tax.
- **Make illegal states unrepresentable > check at runtime.** Prefer designs
  where the wrong state can't be constructed over designs that validate after the
  fact. A diff that adds a fifth boolean flag to a struct where a sum
  type/enum-of-states belongs is a finding.

## Anti-pattern catalog (application level)

Each entry: the tell you'll see in a diff, and the fix to recommend. These map
mostly to categories 1–8 (separation of concerns, responsibilities, coupling,
abstraction boundaries, organization, maintainability).

- **Anemic domain model.** Tell: an entity that's all getters/setters, with every
  rule living in a `XxxService`. Cost: rules scatter and duplicate; there's no
  home for invariants. Fix: move behavior onto the entity that owns the data it
  guards. (Fine if the domain is genuinely thin CRUD — say so.)
- **God class / god module.** Tell: a class or module named `Manager`, `Helper`,
  `Util`, `Core`, `Service`, `Common` that keeps growing and that everything
  imports. Cost: no independent reasoning, huge blast radius, merge contention.
  Fix: split by cohesion of change into named, domain-meaningful units.
- **Stringly-typed state.** Tell: important states as bare strings/magic
  constants (`status = "shipped"`) with transitions enforced by scattered `if`s.
  Cost: illegal transitions are constructible; a typo is a bug. Fix: an explicit
  enum/sum type and a state machine with guarded transitions.
- **Primitive obsession.** Tell: `userId: string`, `email: string`,
  `amountUsd: number` — primitives carrying rules. Cost: validation and arithmetic
  rules spread to every call site. Fix: value objects (`Email`, `UserId`,
  `Money`) that centralize the rule; the constructor becomes a free regression
  test. Only wrap primitives that carry rules.
- **Feature envy.** Tell: a method that reaches for another object's data more
  than its own. Cost: coupling and duplicated knowledge. Fix: move the method to
  the class whose data it uses.
- **Train wreck / Law of Demeter.** Tell:
  `order.getCustomer().getAddress().getCity().getZip()`. Cost: the caller is
  welded to the internal shape of three objects. Fix: a method on the nearest
  object (`order.shippingZip()`), or rethink the exposed surface.
- **Speculative generality / over-engineering.** Tell: an interface with one
  implementation, a factory that constructs one type, a `DefaultFooStrategy`, an
  abstract base with no second subclass, config hooks nobody uses. Cost: readers
  peel indirection to find five lines of real work. Fix: subtract — inline it
  until a real second case arrives. **This is as much a finding as under-design.**
- **The "and" function/class.** Tell: a name containing "and," or a unit you
  can't describe without "and" — it does two jobs. Cost: the jobs must change
  together and can't be tested apart. Fix: split by concern.
- **Long parameter lists.** Tell: more than ~4 positional parameters. Cost: a
  missing concept is hiding in the signature. Fix: a parameter object or a named
  domain type.
- **Hidden mutable global state.** Tell: singletons, module-level mutables,
  ambient caches, env vars read ten layers deep. Cost: invisible coupling the
  type system can't see; tests interfere. Fix: inject the dependency; read config
  once at the composition root and pass it down.
- **Cyclic dependencies.** Tell: module A imports B and B imports A (directly or
  transitively). Cost: not two modules but one with a fake seam; fragile build
  order. Fix: extract the shared concept to a third place, or invert one
  dependency.
- **Comments where a name would do.** Tell: a comment explaining a confusingly
  named variable/function. Cost: every reader re-derives intent. Fix: rename.
  (Usually a Nit.)
- **Layer-first sprawl in a large codebase.** Tell: a feature smeared across
  `/controllers`, `/services`, `/repositories`. Cost: every change touches many
  directories. Fix: feature-first modules (`billing/`, `billing/api`,
  `billing/domain`) once the app is large enough to warrant it.

## Layering & dependency direction

The single most consequential application-level property. Default rule: **inner
layers (domain, application/use-cases) know nothing about outer layers (HTTP, DB,
queues, framework).** Adapters depend on the domain; never the reverse.

Tells in a diff:

- A domain/business file adds an `import` of the ORM, the HTTP framework, a
  logging library, or a framework request/response type. **This is the highest-
  value layering finding** — read the imports the diff adds.
- Business logic reads `request.headers` / builds an `HttpResponse` / returns a
  framework status object.
- A repository or model calls up into a controller or use-case.
- UI/template code queries the database directly.

Why it costs: the inner layer can no longer be tested or reused without the outer
one; domain tests get slow and flaky; the business rules get married to a
framework you may want to swap. Fix: return plain domain results/raise domain
errors, and let the outer layer map them. The fix is incremental (one entity, one
use case, one adapter) — don't demand a grand refactor in a PR.

Where it overreaches (don't over-flag): a genuinely CRUD-heavy app where the
"domain" is "write the form to the table" doesn't need hexagonal ceremony. Three
interfaces to save one user is a smell, not architecture. Flag *missing* layering
only when there's real domain logic to protect.

## Domain modeling checks

Most bugs are domain-modeling bugs in disguise. When a diff touches the model:

- **Legal states only.** Can an illegal state be constructed (`shipped` without
  `placed`)? Push for sum types / discriminated unions over enum-plus-flags.
- **Value objects for rule-bearing primitives.** `Money`, `Email`, `UserId`.
- **Entity vs value object.** Identity (compare by ID) vs equality-by-value.
  Getting this wrong shows up as wrong equality/dedup logic.
- **Aggregates draw the consistency boundary.** One transaction should touch one
  aggregate. A diff that writes two aggregates in one transaction, or reaches
  across an aggregate boundary to mutate another's internals, is a finding.
- **The model should be the easiest thing to change.** If a small model change in
  the diff ripples through ten files, the model is leaking — flag the leak.

## Design patterns — earns-its-keep vs. cargo-cult

Patterns are vocabulary, not goals. When a diff introduces one, ask whether it's
paying rent. Quick judgments:

- **Repository** — worth it when the domain is tested in isolation or the store
  might change. Not worth it for tiny CRUD where the ORM already is the
  abstraction.
- **Factory** — worth it for tricky invariants or subtype selection. Skip when
  `new Thing(...)` is fine.
- **Strategy/policy** — needs *two existing* implementations. A lone
  `DefaultXStrategy` is an awkwardly named class, not a strategy → over-engineering
  finding.
- **Decorator** — good for cross-cutting behavior (caching, logging) on a closed
  class.
- **Observer/pub-sub** — inside one app, usually overkill; a function call is
  simpler. Earns its keep with multiple unrelated reactors.
- **Command/use-case object** — good for queues, undo, audit, thin handlers.
- **Builder** — good for many optional params / staged construction.
- **State machine** — good when transitions/guards dominate; far better than
  stringly-typed status.

Reviewer rule: if a pattern is introduced without a named concrete second case or
a real complexity it tames, that's a **speculative generality** finding. If a
pattern is *missing* and the diff hand-rolls its problem badly (e.g., stringly-
typed state where a machine belongs), that's an under-design finding.

## Module boundaries

Where to draw lines, and what a diff can break:

1. **Cohesion of change** — things that change together belong together. A diff
   that edits one feature across five directories signals wrong boundaries.
2. **Data ownership** — one module owns each table/aggregate (one writer per
   row). A diff where a second module starts writing another's table is a hidden-
   coupling finding.
3. **Domain-language names** — modules named for business concepts age better
   than layer names.
4. **Public vs internal surface** — a diff that reaches into another module's
   internals instead of its public API is a coupling finding; recommend the
   public surface (and, if the team enforces it, an import-linter rule).
5. **Independent reasoning** — if you can't understand the changed module without
   the whole app in your head, the boundary is wrong.

Watch the **god module** ("common"/"utils"/"core"): a diff that dumps domain-
specific code there is misfiling. Recommend a named home.

## Cross-cutting concerns — placement findings

- **Errors** — a small set of meaning-bearing error types (validation, not-found,
  conflict, infrastructure); the edge maps them to HTTP. Tell: `throw new
  Exception("...")` with stringly-typed meaning from deep code.
- **Logging** — structured, consistent keys; the domain logs through a port or
  not at all. Tell: ad-hoc `print`/logger calls with bespoke keys in domain code.
- **Auth** — authn/authz at the edge (middleware / use-case guard), not in the
  domain. Tell: a domain method checking permissions.
- **Transactions** — boundary per use case. Tell: `@Transactional` sprinkled on
  random deep methods, or a transaction spanning two aggregates.
- **Configuration** — read once at startup into a typed object, passed down.
  Tell: env vars read deep in the call stack.

## Coupling vocabulary (system level)

For diffs that touch service boundaries, integrations, or distributed workflows,
name coupling precisely:

- **Static coupling** — what a component needs to exist/boot (its DB, broker,
  libraries, other services). The static-coupling picture answers "if I change
  this, what breaks?" Things sharing a static coupling point (a shared database)
  **share fate** even if the org chart says otherwise.
- **Dynamic coupling** — how components talk at runtime during a workflow. Two
  services cooperating in a workflow entangle their latency, scalability, and
  fault tolerance for its duration.
- **Architecture quantum** — an independently deployable artifact with high
  functional cohesion and its own operational characteristics. A monolith with a
  shared database is *one quantum* no matter how many "services" the diagram
  shows — the shared DB collapses them. Use this to call out a **distributed
  monolith**: services that must deploy together / share a DB / call each other
  in synchronous chains get the cost of distribution with none of the benefit.

Three dimensions of dynamic coupling (name which one a workflow diff is picking):
**communication** (sync/async), **consistency** (atomic/eventual), **coordination**
(orchestrated/choreographed).

## Contracts — strict to loose

Every place two parts meet, there's a contract. Match strictness to volatility
and trust:

- **Strict** (gRPC/protobuf, schema-validated) — fidelity and compile-time
  safety, at the price of lockstep change. Fine for stable, internal, latency-
  critical, same-bounded-context contracts.
- **Loose** (REST/JSON, GraphQL) — evolves easily; needs consumer-driven contract
  tests to stay honest. Right for anything crossing team boundaries, changing
  often, or public.

**Stamp coupling** (watch for this): passing a big shared structure between
components when each needs a fraction of it. Tell: a fat DTO / "envelope" threaded
through many services or layers. Cost: any field change breaks every consumer.
Fix: pass only what each side needs. (Legit exception: deliberately carrying
workflow state in a choreographed saga.)

Reviewer finding shapes: a diff that makes a *breaking* change to a published/loose
contract without versioning; a diff that leaks an internal/implementation type
through a public signature (also an abstraction-boundary finding); a diff that
introduces stamp coupling.

## Reuse in distributed systems

When a diff shares code across services, the choice has architectural weight:

- **Code replication** — only for tiny, static, never-changing snippets.
- **Shared library (compile-time)** — good for stable shared code; prefer
  fine-grained, function-specific libraries over a coarse "shared-everything" jar;
  never depend on `LATEST` — pin versions.
- **Shared service (runtime)** — deploy once, everyone gets it — and that's the
  risk: runtime fate-sharing, network latency per call, coupled scaling. Use only
  when the logic *must* change in lockstep. A diff that introduces a shared
  *service* for **domain** logic is usually a sign two services should be one —
  flag it.
- **Sidecar / mesh** — right for infrastructure cross-cutting concerns, wrong for
  domain logic.

## Service granularity — for PRs that split or add a service

Don't size by counting nouns. Weigh disintegrators (reasons to split) against
integrators (reasons to keep together). A split needs two or more disintegrators
and no strong integrator pulling the other way.

Disintegrators: unrelated scope/low cohesion; divergent code volatility;
divergent scaling profiles; fault isolation; a tightened security boundary
(PII/PCI); named coming extensibility.

Integrators (argue *against* a split): a required cross-service ACID transaction;
chatty workflows (rule of thumb: if >~70% of requests need inter-service calls,
they want to be one service); shared *domain* code (>~40% and changing often);
tight data relationships.

Reviewer finding: a diff that introduces a service split which would force a
distributed transaction, or that creates a chatty synchronous chain — the
boundary is wrong. Recommend keeping it one service and re-splitting later along
data ownership.

## Cross-service workflows / sagas

If a diff wires a workflow across services, name the combination it's picking:
{sync/async} × {atomic/eventual} × {orchestrated/choreographed}. Two practical
review notes:

- Most healthy workflows land on **orchestrated + eventual** (Fairy Tale =
  sync/eventual/orchestrated, or Parallel = async/eventual/orchestrated).
- The **Horror Story** (async + atomic + choreographed) recurs because each
  choice sounds fine alone; the combination fights itself and is undebuggable.
  Flag it.
- If a diff needs **atomic consistency across services**, the boundary is
  probably wrong — recommend keeping those operations in one service rather than
  a two-phase commit or a fragile saga.

Orchestration vs choreography: complexity (many steps, error branches,
compensations, "where is this workflow?") → orchestrator earns its keep. Pure
throughput with rare errors → choreography. High complexity + choreography is the
smell.

## Multi-tenant checks

When a diff touches a system serving multiple tenants/customers/departments:

- **Tenant scoping must be impossible to forget** — passed through a typed
  context, not pulled from a global. Tell: a query/handler/job in the diff that
  isn't scoped by tenant, or reads tenant from ambient state.
- **Cross-tenant leakage** — the highest-severity finding here: a change that
  could let tenant A's data reach tenant B (a cache key without tenant, a query
  missing the tenant predicate, a shared in-memory structure).
- **Noisy neighbor / tenant config drift** — per-tenant limits at the points that
  matter; resist per-tenant special-casing that turns SaaS into hosted custom
  software.

## System-level anti-patterns

- **Distributed monolith** — services that deploy together / share a DB / long
  sync chains.
- **Shared database between services** — collapses the quantum; two writers to
  one table are one service in disguise.
- **Synchronous chains across boundaries** — A→B→C→D multiplies failure
  probability and tail latency.
- **Two-phase commit across services** — redesign the boundary instead.
- **God service** (`CoreService`, `BusinessLogicService`) — god class at larger
  blast radius.
- **No clear system of record** — two systems both authoritative about the same
  data; reconciliation becomes permanent.
- **Letting the ORM design the schema** — schema should follow access patterns
  and integrity, then map to objects.
- **Reinventing identity/auth** — almost always wrong; use an existing IdP and
  standards.

## Testability is an architectural property

Hard-to-test is hard-to-change; treat testability as a design finding, not a QA
afterthought. Tells and fixes:

- Domain tests that need a database to run → layering is wrong (see above).
- Side effects (time, randomness, network, DB) reached via globals instead of
  injected → can't substitute in tests. Fix: inject them.
- A diff that tests private internals / mocks collaborators inside its own domain
  → locks in the implementation; usually means the object is too coupled.
- Prefer pure functions where possible; test through a module's public surface.

## Fitness functions — self-enforcing decisions

When a review defends a load-bearing invariant (layering, no cycles, module
boundaries, a stable public API), recommend the automated check that keeps it
true — the "unit test of architecture." These are cheap (often three lines) and
run on every build:

- **Cycle detection / boundary enforcement:** `import-linter`, `pydeps` (Python);
  `dependency-cruiser`, `madge` (JS/TS); ArchUnit (Java); NetArchTest (.NET);
  `go-cleanarch` (Go).
- **Contract tests:** Pact and similar make loose contracts safe.
- **Budgets/gates:** bundle size, startup time, vulnerability/license scans in CI.

Reviewer discipline: when you flag a layering or boundary violation that will
recur, note the fitness function that would have caught it — "and add an
import-linter rule so `domain.*` can't import the ORM." That turns a one-time
review comment into a permanent guardrail. Don't over-prescribe a wall of checks.

## Calibration — reviewing, not redesigning

- Not every difference is a finding. Tie each to concrete change cost.
- Respect PR scope. If the only real fix is a large refactor, note the risk
  briefly as a follow-up; don't block a working change on a rewrite unless the
  design actively endangers the codebase.
- Over-engineering is a finding. Adding abstraction is not automatically an
  improvement — flag premature interfaces/factories/layers as readily as missing
  ones.
- Stay out of the performance lane. No loop hoisting, no query narrowing, no
  allocation counting. If it's a micro-optimization, it is not this review's job.
