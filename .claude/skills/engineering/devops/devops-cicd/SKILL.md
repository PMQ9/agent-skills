---
name: devops-cicd
description: Use this skill for any work involving CI/CD pipelines, build systems, container images, deployment strategies, release engineering, supply-chain security, environment promotion, or developer workflow. Trigger when designing or fixing GitHub Actions / GitLab CI / Buildkite / Jenkins pipelines, writing Dockerfiles, choosing rolling vs blue/green vs canary, setting up artifact registries, signing images, scanning for vulnerabilities, configuring branch protection, designing pre-commit hooks, or moving a team from manual deploys to automated ones. Also trigger when reviewing a pipeline for slowness, flakiness, or security gaps.
---

# DevOps & CI/CD

The job of CI/CD is to give your team confidence that the code on `main` is shippable, and to ship it with the smallest possible distance between "merge" and "in production." Every minute added to that distance compounds across every change for the lifetime of the system.

## The pipeline as a contract

A CI/CD pipeline is a contract: *if this passes, this artifact is safe to deploy.* That means:

- The same artifact runs in every environment. Build once, promote — never rebuild for staging vs prod.
- The pipeline is the source of truth for what "shippable" means. Local "works on my machine" doesn't count.
- Every step is reproducible. Pinned versions, pinned images, pinned actions.
- It's fast enough that humans don't avoid it. Aim for <10 minutes from push to PR feedback. Beyond that, people start batching changes and skipping CI locally.

## Pipeline phases (typical, in order)

1. **Static checks** — formatting, linting, type checks. Fastest, runs first.
2. **Unit tests** — fast, parallel.
3. **Build** — compile + container image. The artifact is named by content (image digest, not tag).
4. **Integration tests** — against real dependencies in containers.
5. **Security scans** — SAST, dependency vulns, image scan, secret scan.
6. **Push artifact** — to registry, signed.
7. **Deploy to staging** — automatic.
8. **Smoke / E2E in staging** — small, focused.
9. **Promote to prod** — with appropriate gating (auto, manual approval, time window).
10. **Post-deploy verification** — synthetic checks, error rate watch.

Steps that don't depend on each other run in parallel. Failures fast-fail the rest where it makes sense.

## Trunk-based development

Default to trunk-based: short-lived branches (hours to a day or two), merged behind PR review and CI, with feature flags hiding incomplete work. The alternative — long-lived feature branches and merge windows — produces big-bang merges, painful conflicts, and stale PRs.

GitFlow has its place (regulated environments with hard release boundaries), but for SaaS-style continuous delivery, trunk-based wins. Keep `main` always shippable.

## Branch protection (GitHub or equivalent)

Non-negotiable for any team larger than one:

- Require PR reviews (at least 1, often 2 for critical paths).
- Require status checks before merge.
- Require branches up to date before merge (or use merge queue).
- Disallow force-push to `main`.
- Require linear history (squash or rebase merges, not merge commits) — or don't, but pick consistently.
- Require signed commits if you care about provenance.
- Block direct pushes to `main`.

Use a **merge queue** if you have enough PR volume that "rebase, push, wait, repeat" becomes a tax. The queue serializes the final test run.

## Building container images

Dockerfile principles that actually matter:

```dockerfile
# Pin the base image by digest, not just tag
FROM python:3.12-slim@sha256:abc123...

# Layer ordering: things that change rarely on top
WORKDIR /app
COPY pyproject.toml uv.lock ./
RUN pip install --no-cache-dir uv && uv sync --frozen --no-dev

# Source last so source changes don't bust the dep cache
COPY src/ ./src/

# Don't run as root
RUN useradd -r -u 1001 app && chown -R app:app /app
USER app

# Explicit port doc; not required for runtime
EXPOSE 8080

# Real PID 1, so SIGTERM gets delivered
ENTRYPOINT ["python", "-m", "src.main"]
```

Things to do:

- **Multi-stage builds.** Build deps in one stage, copy artifacts to a slim runtime stage. The shipped image has no compilers, no `apt`, no shell history.
- **Non-root user.** Always.
- **Pinned base image** by digest (`@sha256:...`) for reproducibility and supply-chain hygiene.
- **Minimal base** — `distroless`, `alpine` (with care — musl differences), or `-slim` variants. Smaller image = faster pull = smaller attack surface.
- **`.dockerignore`** — keep `.git`, `node_modules`, local secrets, test fixtures out of the build context.
- **One process per container.** If you need supervision, that's what the orchestrator does.
- **Health check** in the image (or, better, in the orchestrator definition).

Things to avoid:

- `latest` tags anywhere in your supply chain.
- `RUN apt-get update && apt-get install -y curl` without `--no-install-recommends` and without cleaning the apt cache afterward.
- Secrets baked into image layers. Image layers are eternal — even if you `RUN rm secret`, it's still in the prior layer. Use build-time secret mounts (`--secret`) or runtime injection.
- Building images as part of test runs. Build once, test the artifact.

## Artifact registry & immutable artifacts

Push images to a registry (ECR, ACR, GAR, GitHub Container Registry, Harbor). Address them by **digest** (`registry/image@sha256:...`), not by tag, for any deploy. Tags are mutable; digests are not.

A common deploy bug: "we deployed `v1.2.3`" and somebody else moved that tag. Digests prevent this.

Retain artifacts long enough to roll back to anything in production. Garbage-collect older ones on a policy.

## Signing and provenance

Sign your images. **Sigstore / cosign** is the default-good choice in 2026. Verification at deploy time (in admission control or in the CD step) ensures the artifact came from your pipeline and not an attacker who breached the registry.

Generate **SBOMs** (`syft`) for every image and store them alongside. Generate **attestations** (`SLSA provenance`) describing how the artifact was built. Even if nobody queries them today, you'll need them when something downstream needs to ask "did this image have log4j?" or when a customer wants SLSA-3 evidence.

## Vulnerability scanning

Run on every image, every PR:

- **Image scan** (`trivy`, `grype`) — base image and dependency CVEs.
- **SCA / dependency scan** — known vulns in app dependencies.
- **SAST** — code-level security issues (Semgrep, CodeQL).
- **Secret scan** — `gitleaks` or equivalent. Yes, even on `main`. Yes, even on private repos.

Treat scanner output as *signal*, not law. A CVSS-9.8 in a code path you don't reach is less urgent than a 5.0 in your auth flow. Triage by reachability and exploitability, not score alone. But never let the scan being noisy be the reason you stop running it.

## Deployment strategies

| Strategy | When | Trade-offs |
|---|---|---|
| **Recreate** | Acceptable downtime; stateful single-instance. | Simple, has downtime. |
| **Rolling** | Default for stateless services. | Old + new run together briefly — needs forward/backward compatible changes. |
| **Blue/green** | Big risky changes; need instant rollback. | Doubles capacity briefly; cutover is binary. |
| **Canary** | High-traffic, want to limit blast radius. | Needs traffic routing and good metrics; more complex. |
| **Feature-flag rollout** | Behavior change without deploy risk. | Doesn't help with infra/runtime changes. |

Most services should default to **rolling deploys + feature flags for risky behavior changes**. Reserve canary for high-stakes services where you can actually compare metrics between cohorts.

The crucial property of any deploy strategy: you can **roll back** in one click within minutes. A deploy you can't undo is an outage waiting to happen.

## Schema migrations and zero-downtime deploys

Two rules together cover most cases:

1. **Code is forward-compatible** with the next migration.
2. **Schema is backward-compatible** with the previous code.

This means migrations always come in two shapes: an "expand" that adds new structure (new column, new table, dual-write) and a later "contract" that removes the old structure once nothing reads it. Never expand and contract in the same release.

## Environment promotion

Three environments is enough for most teams:

- **dev/staging** — short-lived or shared; test data; auto-deploys from `main` (or per-PR previews).
- **prod** — the real one.
- **(optional) canary** — a slice of prod for early signal.

Reject the temptation to keep adding environments (UAT, pre-prod, integration, perf, ...). Every extra environment is config drift, secrets to manage, and another place where "it worked there but not here" lives. Better one shared staging that's actually production-like than four bespoke ones nobody trusts.

Promotion should be the **same artifact**, just a different deploy target. Different config, same code, same image digest.

## Secrets in pipelines

- Never echo secrets. Most CI systems mask known secret values; don't rely on it for derived values.
- Rotate any secret a developer has seen.
- Prefer **OIDC / workload identity federation** over long-lived cloud credentials. GitHub Actions → AWS / Azure / GCP via OIDC means no static keys in CI.
- Scope secrets to environments (`environment: prod`) so PR pipelines can't reach prod credentials.
- Audit secret usage: who pulled which secret when.

## Pipeline performance

Slow pipelines are a productivity tax. Common wins:

- **Cache dependencies.** Maven/npm/pip/go module caches; Docker layer cache; mount caches in BuildKit.
- **Parallelize tests.** Split by file or dynamically by past timing.
- **Run only what changed.** Path filters, monorepo tools (Nx, Turbo, Bazel) for selective execution.
- **Self-hosted runners** for heavy workloads, with autoscaling.
- **Avoid full clones** for shallow operations (`fetch-depth: 1`).
- **Don't rebuild the world** for a doc change.

Watch for flakiness. A 99% reliable test in a pipeline of 50 steps is failing 40% of the time. Quarantine flaky tests immediately, fix them or delete them — don't let "just re-run it" become the team's default.

## Pre-commit / local checks

Pre-commit hooks (e.g., `pre-commit` framework, `lefthook`, `husky`) catch the cheap stuff: formatters, basic linters, trailing whitespace, secret detection. Makes CI faster by eliminating preventable failures.

Don't put slow checks (full test suite, integration tests) in pre-commit. Developers will bypass it (`--no-verify`) and stop trusting it.

## Observability of the pipeline itself

Track:

- **Lead time** — commit to production.
- **Deployment frequency** — deploys per day/week.
- **Change failure rate** — % of deploys that need a fix or rollback.
- **Mean time to restore** — incident start to resolution.

These are the DORA metrics. If you don't know yours, instrument them. They will reveal where the pipeline is actually broken better than any retro will.

## Rollback

Every deploy should answer: "How do I undo this in 60 seconds?"

- For stateless services: redeploy previous image digest.
- For schema changes: design the migration to be rolled forward only; keep code that handles both shapes during the transition.
- For data corruption: have a backup strategy with tested restore procedure. An untested backup is a hope, not a backup.
- For feature flags: flip the flag.

Practice rollbacks. A rollback that nobody has run in six months is a rollback that won't work when you need it.

## Common anti-patterns

- "Build once" violated: separate build per environment with different config baked in.
- Tags as the primary deploy reference. Use digests.
- Deploys requiring a human to SSH and edit config.
- Database migrations run by hand outside the pipeline.
- "It works locally" — pipeline doesn't reproduce the local environment, or vice versa.
- Production deploys outside of business hours as a *policy*. Deploy on Tuesdays at 10am when everybody's around. If you can't deploy any day, fix the deploy.
- Branch-per-environment (`dev` branch, `staging` branch, `main` branch). Promote artifacts, not branches.
- Long-lived feature branches. Use feature flags instead.
- A single pipeline that takes 45 minutes and nobody knows how to debug.
- Quarantine queue of "flaky" tests that no one ever fixes — they accrete, the suite rots.
- Manual smoke tests in production after deploys. Automate them or stop pretending they happen.

## A reasonable default GitHub Actions skeleton

```yaml
name: ci
on:
  pull_request:
  push:
    branches: [main]

permissions:
  contents: read
  id-token: write    # for OIDC to cloud
  packages: write    # for ghcr.io

concurrency:
  group: ${{ github.workflow }}-${{ github.ref }}
  cancel-in-progress: ${{ github.event_name == 'pull_request' }}

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: # lint, format check, type check

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: # unit + integration tests with cached deps

  build:
    needs: [lint, test]
    runs-on: ubuntu-latest
    if: github.event_name == 'push' && github.ref == 'refs/heads/main'
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - uses: aws-actions/configure-aws-credentials@v4
        with:
          role-to-assume: arn:aws:iam::...:role/ci-deployer
          aws-region: us-east-1
      - id: build
        uses: docker/build-push-action@v5
        with:
          push: true
          tags: ${{ env.REGISTRY }}/${{ env.IMAGE }}:${{ github.sha }}
          provenance: true
          sbom: true
      - run: cosign sign --yes ${{ env.REGISTRY }}/${{ env.IMAGE }}@${{ steps.build.outputs.digest }}

  deploy-staging:
    needs: build
    runs-on: ubuntu-latest
    environment: staging
    steps:
      - run: # deploy specific digest, not tag
```

Pin all third-party actions to a commit SHA, not a version tag. Tags can be moved.
