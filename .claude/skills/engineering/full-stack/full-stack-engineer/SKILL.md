---
name: full-stack-engineer
description: Use this skill for end-to-end, cross-layer engineering — carrying a feature or whole app from database to UI and into production, owning the seams where most rework lives. Trigger whenever someone is building an app, feature, MVP, or SaaS solo or on a small team; wiring a frontend to a backend; designing the frontend↔backend contract; deciding where logic belongs (database vs API vs client); threading auth and sessions through every layer; choosing a coherent stack; setting up a local dev environment; or asking how the pieces fit together. Use it even when the user names one layer but owns the whole slice ("add login to my side project," "why does my data look different on the page than in the database"). This is the generalist's skill — for deep single-layer work hand off to backend-development, frontend-development, api-design, database-design, system-architecture, aws/azure, or devops-cicd, but reach for it first whenever the job spans layers or the user owns the whole thing.
---

# Full-Stack Engineer

Full-stack does not mean "expert at every layer." Nobody is. It means you can carry a user-meaningful capability from the database to the pixel and back, and you are responsible for the parts no single specialist owns: the seams between layers. That is where the work actually is. A backend specialist makes the API correct; a frontend specialist makes the UI correct; the bug that ships anyway lives in the gap between them — a field that's a string on one side and a number on the other, a timezone that's UTC in the database and local in the browser, an auth token that's valid until it crosses one more hop.

Three failure modes are specific to working across the whole stack, and most of this skill is about avoiding them structurally:

1. **The seam bug.** Two layers each work in isolation and disagree at the boundary. Almost always a contract problem — a shape, a type, a null, a unit, an encoding that the two sides don't share.
2. **The comfort-layer trap.** You go deep in the layer you enjoy and leave the others shallow and fragile. The app is only as good as its weakest layer, and weakest is usually "the one you didn't want to touch."
3. **Losing the end-to-end thread.** You optimize a query, a component, an endpoint — and lose sight of whether the whole slice actually works for a user. Local maxima in each layer, broken experience overall.

Your edge as a full-stack engineer is breadth plus judgment: you hold the whole picture in your head, you put each piece of logic in the cheapest correct layer, and you know when a problem has gotten deep enough that a specialist (or a specialist skill) should take over. You will be shallower than a specialist everywhere. That's the trade you're making; the value is in the connective tissue.

## Build in vertical slices, not horizontal layers

The single most important habit. Build one thin feature *all the way through* — schema → API → UI → deployed and usable — before you build breadth in any layer. This is the **walking skeleton**: the smallest end-to-end path that actually runs, deploys, and exercises every seam.

Why this and not the intuitive "finish the database, then the API, then the UI": integration is where the risk lives, and the horizontal approach defers all of it to the end. You discover the auth flow doesn't fit, the API shape is awkward for the UI, the deploy pipeline doesn't exist — all at once, at the worst time, with everything half-built. A walking skeleton retires that risk on day one. After it's running, every new feature is another thin slice through a path you've already proven.

Concretely, for a new app: pick the smallest real feature (not "set up the project" — an actual user action, like "a user can create one note and see it"). Build the table, one endpoint, one screen, and deploy it to a real environment. Now you have a skeleton to hang everything on. For a new feature in an existing app: same shape, smaller — migration, endpoint, UI, test, ship.

## The data contract is the spine

If you internalize one thing from this skill: **the shape of your core data is a contract, defined once, that flows through every layer unchanged in meaning.** A `User`, an `Order`, a `Note` has one canonical shape. The database stores it, the API serializes it, the client parses it, the UI renders it — and at no point should two layers hold quietly different ideas of what it is.

The seam bug is almost always a contract that drifted. The defenses:

**One source of truth for the shape, and generate the rest.** Maintaining the same type by hand in three languages guarantees they diverge. Pick a generator and let it propagate:

- Database schema → types (Prisma, sqlc, Drizzle, jOOQ, SQLAlchemy models).
- API schema → client types (OpenAPI codegen, tRPC for TS-everywhere, GraphQL codegen, gRPC/protobuf).
- A shared schema package both sides import (Zod/Valibot/Pydantic schema in a monorepo package).

The win isn't elegance — it's that a change in one place breaks the build everywhere it needs to, instead of failing silently at runtime in front of a user.

**Parse at every trust boundary; trust your types inside it.** A boundary is anywhere data crosses from "someone else's responsibility" to yours: a row from the database, a request body from a client, a *response* body in the client from your own API (the network can mangle it, the API can deploy a new version, the cache can be stale). Validate at the edge — `StudentSchema.parse(await res.json())`, not `as Student`. Once parsed, the rest of that layer trusts the type. `unknown` from `fetch().json()` propagating as `any` is how runtime crashes ship.

**Validate the same rule wherever it must hold, but own it in one place.** "Email must be valid," "quantity ≥ 1" — these belong in the shared schema so client and server enforce identically. The client copy is for fast UX feedback; **the server copy is the one that's load-bearing, because the client is untrusted.** Never enforce a real rule only on the client.

**Watch the lossy conversions at the seams.** Dates (store UTC, send ISO-8601, format in the UI — never send a pre-formatted string), money (integer minor units or decimal, never float), big integers (JSON numbers lose precision past 2^53 — send as strings), enums (same casing both sides), null vs undefined vs absent. These are the recurring seam bugs; name them and handle them deliberately.

## A tour of the stack (enough to be dangerous, with defaults)

You need a working default and an awareness of the traps at every layer, even the ones you'll hand off when they get deep. Here is the spine of each. Depth lives in the specialist skills named at the end of each part.

### Data layer

**Default to a relational database (Postgres) until you can articulate why not.** It gives you transactions, constraints, joins, JSON columns when you need schemaless-ish flexibility, and decades of operational knowledge. "We'll need to scale so we picked Mongo" is the most common premature-optimization mistake in new apps; you will hit a hundred other walls first.

Model the schema as the domain, not as the screens. Foreign keys and constraints in the database are free correctness — let the database reject bad data rather than hoping every code path remembers to. Migrations are append-only and run as a deploy step; use the **expand/contract** pattern (add nullable column → backfill → enforce; never rename-in-place) because during a deploy the old and new code run simultaneously. Size a connection pool to the *database's* capacity, not your request load, and put a pooler (PgBouncer, RDS Proxy) in front of serverless functions or you'll exhaust connections instantly.

For schema design, indexing, and query tuning, hand off to `database-design` and `postgresql`.

### Backend and the API

Keep the layers honest even in a small app: a thin **transport** layer (parse, authenticate, validate), an **application/use-case** layer (orchestrate one operation, own the transaction), a **domain** layer (the business rules, no framework or I/O), and **infrastructure** (DB, queues, external APIs). Dependencies point inward — the domain doesn't import the database client. You don't need hexagonal-architecture diagrams; you need to notice when business logic ends up inside an HTTP handler and move it, so the same logic is reachable from a job or a CLI later.

The **API is the contract** the frontend lives against, so shape it deliberately: resource-oriented URLs, a consistent response envelope (and a consistent *error* envelope — `{ error: { code, message, fields } }`, not a bare 500 with an HTML stack trace), pagination on every list endpoint from day one, and typed domain errors that the transport layer maps to status codes. Make writes that might be retried **idempotent** (idempotency keys, upserts, dedupe on event ID) — networks retry, users double-click, queues deliver twice.

For everything below the controller — caching, async jobs, retries, transactions, idempotency — hand off to `backend-development`. For the HTTP surface itself — status codes, pagination shapes, versioning — `api-design`.

### Auth, end to end — the canonical full-stack seam

Auth gets its own section because it touches every layer at once and it is where full-stack engineers most reliably get burned. The mental model:

- **Authentication** = who are you (login). **Authorization** = what may you do (every request after). They're different problems; don't conflate them.
- **Where the credential lives** is the decision that determines your whole security posture. For a browser app, put the session token in an **`HttpOnly`, `Secure`, `SameSite` cookie** — it can't be read by JavaScript, so an XSS bug can't exfiltrate it. **Storing a JWT in `localStorage` is the classic full-stack mistake**: convenient, and one XSS away from total account takeover. Bearer tokens in headers are right for native mobile and third-party API clients, not for your own web frontend.
- **The flow, traced through the layers:** user submits credentials → server verifies and creates a session (or issues a token) → the credential is set as a cookie / returned to a native client → every subsequent request carries it automatically → the API verifies it at the edge (transport layer) → an authorization check confirms this principal may do this action → the domain operates only on already-authorized input. The domain layer should never be checking permissions; that belongs at the edge.
- **Authorization is row-level, not just route-level.** Guarding the endpoint isn't enough — *every data query must be scoped to the authenticated principal.* A list endpoint that runs `SELECT * FROM clients` instead of `SELECT ... WHERE user_id = $1` quietly returns *everyone's* data. This missing tenant filter is one of the most common and damaging full-stack bugs precisely because it's invisible to the kind of testing people actually do: the demo works, the happy path passes, and it only shows its teeth once a second user exists. Make "scoped to the current user" the default shape of every read and write, not something you remember to add.

**Do not roll your own.** Password hashing (use argon2/bcrypt/scrypt via a library, never a hand-rolled hash), session management, OAuth flows, MFA — these are solved, and the failure modes are catastrophic and silent. Use your framework's battle-tested auth, or buy a provider (Auth0, Clerk, WorkOS, Supabase Auth, AWS Cognito, Firebase Auth). The provider list is in `references/reference-stacks.md`. For depth on authorization models, token design, and secrets, hand off to `authn-authz`, `secrets-management`, and `application-security`.

### Frontend

The UI's job is to render the data the user cares about, accept input, and stay out of the way. Get the structure right and most "messy frontend" problems don't appear.

**Categorize state before you manage it** — this dissolves most state-management debates:

| Kind | Example | Where it lives |
|---|---|---|
| Server state | the list of orders, current user | a query cache (TanStack Query, SWR, RTK Query) — *not* a hand-rolled global store |
| URL state | filters, pagination, selected tab | the URL (search params) — survives reload, shareable |
| Local UI state | is this menu open, this input's value | component-local |
| Cross-component UI | theme, toast queue, sidebar | a small store (Zustand, signals, context) |
| Persistent client | drafts, "remember me" | `localStorage` / `IndexedDB` |

The default *wrong* move is dumping fetched server data into a global store and reimplementing caching and refetching by hand. Use a query cache; it does dedup, retry, and refetch-on-focus for free.

**Parse the API response at the boundary** (the same contract discipline from above). **Treat loading, error, and empty as first-class states**, designed up front — not a spinner bolted on after the happy path. A screen that only handles "data arrived successfully" is a screen that breaks for real users on real networks. Set a performance budget early (LCP < 2.5s, INP < 200ms, CLS < 0.1) and reach for the platform before libraries (`<dialog>`, `IntersectionObserver`, `Intl`, container queries — a lot of npm installs reimplement things the browser already does).

For browser depth, performance, and bundling, hand off to `frontend-development` and `frontend-react-next`; for accessibility, `accessibility-wcag`.

### The network in between

The wire between frontend and backend is itself a place bugs live. Latency is real and variable; design for it. The worst pattern is the **request waterfall** — component A fetches, then its child B fetches based on A's result — serializing calls that should be parallel; hoist fetches up or use a framework that parallelizes them. Use **optimistic UI** (update immediately, reconcile when the response lands, roll back on failure) only for actions safe to assume succeed. Every fetch needs a timeout and an `AbortController` so a user navigating away doesn't write a stale response into a now-unmounted view. And re-validate everything server-side: the client is convenience, never the source of truth.

## Run the whole stack locally

A full-stack engineer who can't run the entire system on their machine is debugging blind. Invest early in **one command that brings everything up** — database, API, frontend, and any dependencies — with `docker compose`, Tilt, or a `Procfile` with `foreman`/`honcho`/`overmind`. Seed deterministic test data so the app is usable the moment it's up and everyone sees the same thing (the antidote to "works on my machine" data-shape surprises). Keep **parity where it matters** — run the same database engine as production locally; a SQLite-in-dev, Postgres-in-prod split will hide bugs until the worst moment. This setup also *is* your onboarding doc and the foundation of your CI.

## Shipping the whole stack to production

The full stack includes the part after "it works locally." A minimum viable production for almost any app:

- A **managed database** with automated backups (never self-host Postgres as a solo dev — managed is cheap insurance against the day you'd otherwise lose everything).
- A place to **run the API** (a container, a PaaS dyno, or serverless functions).
- **Static hosting + a CDN** for the frontend (built assets are static files; serve them from the edge with long-cache, content-hashed filenames).
- **Secrets** in a real store or the platform's secret manager — never committed, different per environment.
- **One CI/CD pipeline** that builds, tests, and deploys both halves on every merge to main; migrations run as a gated deploy step.
- **Structured logs**, an **error tracker** (Sentry or equivalent, with sourcemaps), and **health checks** (`/healthz` for liveness, `/readyz` for readiness) from day one — "we'll add observability later" means the first incident costs you a day.

Strong defaults by scale: a solo dev or small team should reach for a **PaaS** (Render, Railway, Fly.io) plus managed Postgres plus a static host (Vercel, Netlify, Cloudflare Pages) — minimal ops, fast to ship. As traffic, team, and compliance needs grow, graduate to containers on a cloud (ECS Fargate + RDS, or GKE/AKS) — at which point hand off to `aws`/`azure` for the platform and `devops-cicd` for the pipeline. Don't start there: the cloud-native setup is a permanent operational tax you shouldn't pay until the workload justifies it.

One contract caveat that bites full-stack deploys: during any rollout, the old and new versions of *both* the frontend and the API run simultaneously for a window. A frontend that requires a new API field, deployed before the API ships it, throws errors for everyone mid-deploy. Roll out backward-compatibly — same expand/contract discipline as database migrations, applied to the API contract.

## Testing across the stack

The test pyramid holds end to end: many fast **unit** tests on domain logic and pure functions, fewer **integration** tests (the API against a real database in a container — not mocks, which hide the bugs that matter), and a **small** number of **end-to-end** tests (Playwright or Cypress driving the real UI against the real API against a real test database). Spend your limited e2e budget on the critical paths — sign up, log in, the one or two actions the product exists for.

The full-stack-specific instruction: **test the seams hardest, because that's where your breadth is thinnest.** The contract between frontend and backend, the auth flow across layers, the migration that has to be backward-compatible — these cross the boundaries no specialist owns, so they're exactly where an integration or e2e test earns its keep. For deciding what to test at which layer, hand off to `test-planning`; for the mechanics of writing them, `integration-testing`.

## Sequencing and scope — the solo / small-team reality

Most full-stack work happens under tight constraints: one or a few people, limited time, no specialist to lean on. The discipline that matters most is **subtraction**.

**Buy the commodities; build only what differentiates you.** Auth, payments, transactional email/SMS, file storage, search, error tracking, analytics — these are undifferentiated heavy lifting with brutal failure modes when home-grown. Use a provider. Your innovation budget is finite; spend it on the thing your product is actually about. (Concrete provider picks are in `references/reference-stacks.md`.)

**Stay boring and integrated.** A modular monolith plus one database beats microservices for virtually every small team — one process to run, one place to debug, transactions that just work, no distributed-systems failure modes you didn't ask for. *Don't distribute a system you can still run in a single process.* Microservices solve an organizational problem (many teams needing to deploy independently) you probably don't have yet. When you genuinely do, hand off to `system-architecture`.

**Defer the abstraction and defer the scale work.** Rule of three: duplicate twice, extract on the third occurrence, when you finally know the real shape. Don't build for 10× the load you have; build so that re-architecting *when* you have it is cheap. For application-internal structure, refactoring, and debt triage, `software-architect` is the deep skill.

**Resist the comfort-layer trap actively.** Notice when you're polishing the layer you enjoy while another rots. Give the boring layer the boring, correct treatment and move on.

## Knowing when to go deep — the handoff map

Your value is knowing the map, not memorizing every road. When a problem gets deep in one layer, name the right specialist skill and pull it in:

| When the question becomes… | Hand off to |
|---|---|
| schema design, normalization, indexes, query plans | `database-design`, `postgresql` |
| caching, async jobs, queues, retries, idempotency, transactions | `backend-development` |
| HTTP surface — status codes, pagination, versioning, error envelopes | `api-design` |
| browser depth, performance budgets, bundling, CSS architecture | `frontend-development`, `frontend-react-next` |
| accessibility, WCAG, screen readers, keyboard nav | `accessibility-wcag` |
| code structure, module boundaries, refactoring, tech debt | `software-architect` |
| multiple services, scaling, infra topology, multi-team | `system-architecture` |
| cloud platform specifics | `aws`, `azure`, `infrastructure-fundamentals` |
| CI/CD pipelines, containers, deploy strategies | `devops-cicd` |
| authz models, token design, secrets, security review | `authn-authz`, `secrets-management`, `application-security`, `cybersecurity-expert` |
| LLM-powered features | `llm-application-engineering`, `ai-solution-architect` |
| what to test at which layer / how to write the tests | `test-planning`, `integration-testing` |
| the problem is too vague to build against | `requirements-analyst` |

Naming the skill and inviting the user to pull the thread is better than producing a shallow answer in a domain that has a deep skill available.

## A worked example

For a concrete, end-to-end walk-through — schema, migration, validated endpoint, generated client types, a UI with real loading/error states, an integration test, and a deploy note, all for one small feature — read `references/vertical-slice-example.md`. It makes the "one source of truth, parse at the boundary, test the seam" advice concrete in code.

## Anti-patterns

- **Two hand-maintained copies of the same type.** The frontend's `User` interface and the backend's `User` struct, edited independently. They will drift; generate one from the other or share a schema.
- **Validating only on the client.** The form library is for UX. The server is the security boundary. Every real rule is enforced server-side.
- **The giant horizontal build.** All the database, then all the API, then all the UI — and integration hell at the end when nothing fits. Build vertical slices.
- **Rolling your own auth, session, or password hashing.** Solved problems with catastrophic, silent failure modes. Use the framework or a provider.
- **JWT in `localStorage`.** One XSS from account takeover. `HttpOnly` cookies for browser sessions.
- **The unscoped query / missing tenant filter.** `SELECT * FROM things` where it should be `... WHERE user_id = ?`. The route looks authenticated and the demo works with one user, so every other user's data leaks silently. Scope every read and write to the authenticated principal.
- **No local environment that runs the whole stack.** Debugging blind, "works on my machine," painful onboarding. One command up, seeded data.
- **The same logic computed in two layers, allowed to disagree.** A total computed in SQL and re-computed in JS that round differently. Compute once; if it must exist twice, test that they agree.
- **Skipping loading, error, and empty states.** A UI that only handles the happy path breaks for real users on real networks.
- **Premature microservices or premature scale work.** Distributing a system you could run in one process; optimizing for load you don't have. Boring monolith first.
- **The comfort-layer trap.** Gold-plating the favorite layer while the rest is fragile. The app is as good as its weakest layer.
- **"We'll add observability later."** You won't, and the first incident proves it. Structured logs and an error tracker from day one.
- **Treating the frontend↔backend contract as tribal knowledge.** An informal, undocumented, untyped agreement that lives in two developers' heads. Make it a typed, versioned, generated artifact.
