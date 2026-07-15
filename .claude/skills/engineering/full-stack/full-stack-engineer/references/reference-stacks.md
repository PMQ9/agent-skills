# Reference stacks and build-vs-buy

Strong defaults, not laws. The right stack is the one the team can write idiomatically and operate calmly — boring tech used well beats clever tech used adequately. Use these as starting points and deviate with a reason.

## Choosing a stack: the one question that matters most

Pick the stack your team is most fluent in. A solo founder who knows Python should not learn Go for a CRUD app because a benchmark looked good. The second question is the *shape of the product* (below). Almost everything else is detail.

## Reference stacks by product shape

### Content / marketing / docs site (mostly static)

- **Astro**, or a framework's static export (Next, SvelteKit), or 11ty for plain control.
- Markdown/MDX content, deploy to a static host + CDN (Cloudflare Pages, Netlify, Vercel).
- No database until you actually need one. Forms via a form service or a single serverless function.
- *Why:* the platform does 95% of this. A SPA framework here is pure overhead.

### Form-heavy internal tool / admin app / line-of-business CRUD

- **Server-rendered monolith**: Django, Rails, Laravel, or Phoenix. Server-side templates + a sprinkle of interactivity (htmx, Hotwire/Turbo, Alpine, or Livewire/LiveView).
- One Postgres. The framework's built-in auth. The framework's admin (Django admin is a superpower for internal tools).
- *Why:* the interactivity is small and the framework has already solved auth, forms, CSRF, migrations, and the admin. Reaching for a React SPA + separate API here doubles the work for no user-visible gain.

### Rich SPA / dashboard / product with heavy client interactivity

- **TypeScript end to end**: React (or Svelte/Vue/Solid) + a Node/TS API (or a Python/Go API), Postgres, a shared schema or generated client types.
- Query cache for server state (TanStack Query). A meta-framework (Next.js, Remix, SvelteKit) if you want SSR and file-based routing; a Vite SPA + standalone API if the app is fully behind auth.
- *Why:* genuine client-side complexity (live data, canvas, complex stateful UI) is what SPAs are for. TS-everywhere lets you share the contract directly.

### API-first / mobile + web clients

- A standalone API (FastAPI, NestJS, Go, or your team's language) with an **OpenAPI or gRPC contract as the source of truth**; generate clients per platform.
- Token-based auth (bearer tokens / OAuth) since native clients can't use cookies the same way; web client still prefers cookies.
- *Why:* multiple consumers make the contract the center of gravity — codegen keeps every client honest.

### "I want to ship this weekend" / prototype / MVP

- A batteries-included meta-framework with a managed backend: **Next.js + Supabase**, or **Rails/Django + Postgres on a PaaS**, or Remix + a hosted DB.
- Buy auth, file storage, and email (below). Deploy to a PaaS.
- *Why:* the goal is a walking skeleton in front of users fast. Minimize the number of services you operate.

## Hosting defaults by scale

| Stage | Frontend | API | Database | Why |
|---|---|---|---|---|
| Solo / MVP / small team | Vercel / Netlify / Cloudflare Pages | PaaS (Render, Railway, Fly.io) or serverless | Managed Postgres (Supabase, Neon, RDS, the PaaS's own) | Near-zero ops, deploy in minutes, scales further than you'd think |
| Growing (real traffic, a team) | Same + CDN tuning | Containers (ECS Fargate, Cloud Run, App Platform) | Managed Postgres with read replicas, connection pooler | Control and headroom without running Kubernetes |
| Large / compliance / multi-team | CDN + edge | Containers/K8s on a cloud | Managed Postgres (Aurora/Cloud SQL), maybe sharding | Hand off to `aws`/`azure` + `devops-cicd` + `system-architecture` |

Don't start at the bottom row. The cloud-native setup is a permanent operational tax; pay it when the workload justifies it, not before.

## Build vs buy: buy the commodities

These are undifferentiated heavy lifting with disproportionate, often silent failure modes when home-grown. Default to buying; spend your build budget on what makes the product distinctive.

| Capability | Buy (default) | Build only if… |
|---|---|---|
| **Auth / identity** | Auth0, Clerk, WorkOS, Supabase Auth, Cognito, Firebase Auth, or your framework's built-in | You have a hard requirement no provider meets and security expertise on staff |
| **Payments / billing** | Stripe (Billing for subscriptions), Paddle/Lemon Squeezy (merchant-of-record handles tax) | Essentially never roll raw card handling — PCI scope alone is disqualifying |
| **Transactional email / SMS** | Resend, Postmark, SendGrid, SES; Twilio for SMS | Never build SMTP/deliverability yourself |
| **File storage / uploads** | S3 / R2 / GCS + presigned URLs; Uploadcare/Cloudinary for images | You have unusual residency or media-processing needs |
| **Search** | Postgres full-text (start here!), then Typesense / Meilisearch / Algola / OpenSearch | You've outgrown Postgres FTS and measured it |
| **Error tracking** | Sentry (or Rollbar, Bugsnag) | Never DIY; it's table stakes from day one |
| **Analytics / product metrics** | PostHog, Plausible, Amplitude, GA4 | You have specific privacy/warehouse requirements |
| **Background jobs / queues** | The cloud's managed queue (SQS) or your DB-backed job lib (Sidekiq, Oban, Celery, BullMQ) | — |
| **Feature flags** | LaunchDarkly, Unleash, PostHog flags, OpenFeature | A trivial app where an env var genuinely suffices |
| **Notifications (multi-channel)** | Knock, Courier, Novu | Single-channel, low volume |

The pattern: if it's a solved, cross-cutting concern that isn't your product's reason to exist, buying it is almost always the right full-stack call. Integrate, don't reinvent.

## A note on monorepos for full-stack

A monorepo (Turborepo, Nx, pnpm/npm workspaces, or just a `shared/` folder) shines for full-stack specifically because it lets the frontend and backend **import the same contract** — the single biggest defense against the seam bug. You don't need heavy tooling to start: a workspace with `web/`, `api/`, and `shared/` packages gets you shared types and atomic cross-stack commits. Reach for Nx/Turborepo when build caching and task orchestration start to hurt, not before.
