---
name: kubernetes-helm-gitops
description: Use this skill for any work involving Kubernetes, Helm, or GitOps — including writing Deployments/StatefulSets/Jobs, designing cluster topology, authoring or refactoring Helm charts, debugging stuck rollouts or CrashLoopBackOff, configuring HPA/VPA/PDB, network policies, RBAC, namespaces, ingress, service mesh, operators/CRDs, or setting up Argo CD / Flux. Trigger when the user mentions kubectl, manifests, charts, values.yaml, "deploy to k8s", clusters, pods, "my deployment is stuck", or a GitOps workflow. Also trigger when reviewing an existing chart or manifest for production-readiness, or when deciding whether to use Kubernetes at all.
---

# Kubernetes, Helm & GitOps

Kubernetes is a control loop that drives observed state toward desired state. Almost every problem reduces to one of three questions: *what is the desired state?*, *what is the observed state?*, *why isn't the controller able to close the gap?* Lose sight of that and you'll be lost in a forest of YAML.

Helm and GitOps are downstream of that mental model. Helm packages the desired state. GitOps makes Git the source of truth for it.

## When *not* to use Kubernetes

Push back if the user is reaching for k8s for a single small service, an early-stage prototype, a CRUD app with one database, or a team of fewer than ~5 engineers without dedicated platform capacity. The operational tax — upgrades, RBAC, networking, secrets, storage, autoscaling, observability — is real and chronic. ECS Fargate, Cloud Run, App Runner, Fly.io, Render, or even a couple of VMs with systemd are often the right answer. Kubernetes pays off when you have many services, polyglot runtimes, custom scheduling needs, or you're already running a platform team.

If they've already committed to Kubernetes, skip this section and help them.

## The mental model

Three concepts carry most of the weight:

- **Declarative state.** You write what you want. Controllers make it true. You don't `kubectl run`; you `kubectl apply`.
- **Reconciliation.** Every controller is a loop: read desired, read actual, take an action that nudges actual toward desired, repeat. Failures don't break the system — the loop just retries.
- **Labels and selectors.** This is how everything finds everything else. Services find Pods by label. Deployments find ReplicaSets by label. NetworkPolicies select by label. Get the labels right and most other things become tractable.

A Deployment is not a Pod. It manages a ReplicaSet, which manages Pods. When debugging, walk the chain: `kubectl get deploy → rs → pods → events → logs`.

## Workload kinds — pick deliberately

- **Deployment** — stateless. Default choice for HTTP services, workers that don't keep local state.
- **StatefulSet** — stable identity and stable storage per replica. Use for databases, queues, things that must be `pod-0`, `pod-1`. Don't use it just because you have a PVC.
- **DaemonSet** — one per node. Log shippers, node exporters, CNI agents.
- **Job / CronJob** — run-to-completion. Migrations, backups, batch.
- **Bare Pod** — almost never. No self-healing.

If you're not sure, it's almost certainly a Deployment.

## Resource requests and limits

This is where production clusters die.

- **Requests** are what the scheduler reserves. Too low and you'll get noisy-neighbor problems and OOMKills under pressure. Too high and you waste capacity.
- **Limits** are hard ceilings. CPU limits cause throttling — usually invisible, often disastrous for tail latency. Memory limits cause OOMKill.

Sensible defaults to start from, then tune with real data:

```yaml
resources:
  requests:
    cpu: 100m
    memory: 128Mi
  limits:
    memory: 256Mi          # set memory limit
    # no cpu limit         # often the right call — see below
```

The CPU-limit debate: setting CPU limits causes CFS throttling that hurts p99 latency even when total CPU isn't saturated. Common practice in production is to set CPU **requests** (so the scheduler does its job) but leave CPU **limits** unset, relying on requests-based fairness. Memory limits, on the other hand, you almost always want — memory has no graceful degradation. Whatever you choose, be consistent and document it.

Run with the Vertical Pod Autoscaler in *recommendation mode* for a week to get real numbers before guessing.

## Probes — get them right or pay later

Three probes, three jobs. They are not interchangeable.

- **startupProbe** — "is the app done starting?" Disables liveness/readiness until it passes. Use this for slow-starting apps (JVMs, anything with warm-up). Without it, slow starts get killed by liveness.
- **readinessProbe** — "should I receive traffic right now?" Failing readiness removes the pod from Service endpoints; it is *not* killed. Use this for transient overload or upstream dependencies being unavailable.
- **livenessProbe** — "is this process wedged and unrecoverable?" Failing liveness *kills the pod*. Be conservative — a too-aggressive liveness probe is a foot-gun that turns a slow afternoon into a crash loop.

Common mistake: making liveness check downstream dependencies. If your DB is slow, you don't want every pod to restart in a tight loop. Liveness should only fail when the process itself is broken.

## Pod Disruption Budgets

Without a PDB, voluntary disruptions (node drains, cluster upgrades) can take down all replicas of your service simultaneously. Set one for any multi-replica workload:

```yaml
apiVersion: policy/v1
kind: PodDisruptionBudget
metadata: { name: api }
spec:
  minAvailable: 1            # or maxUnavailable: 50%
  selector: { matchLabels: { app: api } }
```

`minAvailable: 1` for small replica counts; `maxUnavailable: 25%` (or similar) for larger.

## HPA — autoscaling reality

Horizontal Pod Autoscaler scales replicas based on metrics. Two reality checks:

1. **CPU is a poor scaling signal for I/O-bound services.** A web service that's mostly waiting on the DB will look 5% CPU while its request queue grows. Scale on RPS, queue depth, or p95 latency via custom metrics (KEDA is much better than the built-in HPA for this).
2. **Scale-down is slow on purpose.** Default `--horizontal-pod-autoscaler-downscale-stabilization` is 5m. Don't fight it; flapping replicas is worse than over-provisioning briefly.

For workers consuming queues, KEDA + queue depth is the right pattern.

## Network and security baselines

- **NetworkPolicies are deny-by-default-able and you should default-deny.** A namespace without a policy is wide open. Apply a default-deny ingress, then explicitly allow what each service needs.
- **RBAC: principle of least privilege.** No `cluster-admin` ServiceAccounts for workloads. ServiceAccount per Deployment, narrow Role/RoleBinding.
- **PodSecurityStandards (`restricted` profile)** at the namespace level: non-root user, read-only root FS where possible, drop all capabilities, no privilege escalation, seccomp `RuntimeDefault`.
- **Disable automount of the default ServiceAccount token** unless a Pod actually needs to talk to the API: `automountServiceAccountToken: false`.

```yaml
securityContext:
  runAsNonRoot: true
  runAsUser: 10001
  readOnlyRootFilesystem: true
  allowPrivilegeEscalation: false
  capabilities: { drop: ["ALL"] }
  seccompProfile: { type: RuntimeDefault }
```

## Configuration: ConfigMaps, Secrets, env

Mount config; inject identity. Some rules:

- Non-secret config → ConfigMap, mounted as files when possible (allows reload without restart on most platforms).
- Secrets → never `kubectl create secret` then commit it. Use External Secrets Operator, Sealed Secrets, or SOPS. (See the secrets-management skill for the full story.)
- Don't put a 4 MB config blob in a ConfigMap; you'll hit etcd object size limits. Reach for object storage.
- Environment variables from a ConfigMap silently truncate at NUL bytes; mount as files for anything binary-ish.

## Helm — what it is and isn't

Helm is a templating engine over Kubernetes manifests, plus a release tracker. It is *not* a configuration language. Treat it as the former and you'll be fine; treat it as the latter and you'll write `{{- if and (or .Values.foo (and .Values.bar (not .Values.baz))) }}` and hate yourself.

### Chart structure

```
mychart/
├── Chart.yaml          # name, version, appVersion
├── values.yaml         # defaults, heavily commented
├── values.schema.json  # JSON schema — validates values, prevents typos
├── templates/
│   ├── _helpers.tpl    # named templates (labels, names)
│   ├── deployment.yaml
│   ├── service.yaml
│   └── NOTES.txt
└── charts/             # subchart dependencies
```

### Helm rules of thumb

- **Always include a `values.schema.json`.** A typo in `values.yaml` is otherwise silent — Helm will happily render with `replciaCount: 5` and deploy 1 replica.
- **Use `_helpers.tpl` for the standard labels.** Every resource should carry `app.kubernetes.io/name`, `app.kubernetes.io/instance`, `app.kubernetes.io/version`, `app.kubernetes.io/managed-by`. Don't reinvent these per resource.
- **Don't hide critical values.** If a user *must* override something (e.g., `image.tag`), make it fail loudly when missing: `{{ required "image.tag is required" .Values.image.tag }}`.
- **Avoid Helm hooks for migrations.** `pre-install`/`pre-upgrade` Jobs feel right but have nasty failure modes (the hook succeeded but the upgrade rolled back; the hook is now stranded). Prefer running migrations as an init container, a separate Job applied by your CD tool, or a dedicated migration step in the pipeline.
- **`helm template | kubectl diff -f -` before `helm upgrade`** in non-trivial environments. Surprises are bad.
- **`helm dependency update` belongs in CI, not in muscle memory.** Lock subchart versions in `Chart.lock`; commit it.

### Templating pitfalls

- Whitespace control with `{{-` and `-}}` is finicky; render frequently with `helm template` while writing.
- `tpl` lets you recursively template values — useful for "let users put templates in their values" but easy to abuse.
- `lookup` queries the live cluster at template time. It returns `nil` on `helm template --dry-run` (no cluster). Don't use it for anything required.
- `range` over a map is unordered in Go templates. If order matters (env vars sometimes do), sort with `sortAlpha`.

### When *not* to use Helm

For small, single-team apps with simple config, **Kustomize** is often a better fit — no templating, just patches. For complex platforms with many similar services, a thin internal abstraction (a Helm library chart, or a small generator) beats every team writing their own chart from scratch. Helm umbrella charts that depend on 12 subcharts are usually a sign you should split into multiple releases.

## GitOps — the model

Git is the source of truth for desired state. A controller in the cluster (Argo CD or Flux) reconciles the cluster toward what's in Git. CI builds and pushes images; CD updates a manifest in Git; the controller applies it.

What this buys you:

- **Auditability.** Every change is a Git commit, by a known author, reviewable.
- **Reproducibility.** A new cluster bootstraps itself from the same repo.
- **Drift detection and self-healing.** Manual `kubectl edit` gets reverted (configurable). The controller is loud about drift.

### Repo layout — pick one and stick with it

Two camps:

- **Mono-repo** (everything in one repo, structured by env): simple, easy global refactors, but blast radius of a bad PR is large.
- **Per-app repos + an env repo** (apps build to images; env repo references them): better separation, but the cross-cutting refactor ("change all services' resource requests") gets harder.

For most orgs under ~30 services, a mono-repo with a clear directory structure is fine:

```
gitops/
├── apps/
│   ├── api/
│   │   ├── base/           # plain manifests or Helm chart
│   │   └── overlays/
│   │       ├── staging/
│   │       └── prod/
│   └── worker/...
├── infra/                  # cluster-level: ingress, cert-manager, etc.
└── clusters/
    ├── staging/            # which apps + infra get applied to this cluster
    └── prod/
```

### Argo CD vs Flux

Both are good. Pick based on team taste:

- **Argo CD** — ships with a UI that is genuinely useful for ops. ApplicationSets for templating across clusters. Sync waves for ordering. Slightly more "GUI-friendly" feel.
- **Flux** — more CLI/GitOps-pure, no UI by default, integrates tightly with Helm and Kustomize via dedicated controllers. Smaller surface area.

Whichever you choose, **only one CD tool per cluster** for the workloads it manages.

### Image promotion in GitOps

The CD tool reconciles Git. It does *not* watch a Docker registry by default. So how does a new image get deployed?

Two patterns:

1. **CI writes the new image tag back to Git.** A pipeline step: build image, push, then `git commit` an updated `image.tag` in the env overlay, then PR or push to the env branch. This is auditable and explicit.
2. **Image updater controllers** (Argo CD Image Updater, Flux Image Automation). They watch the registry and commit the change for you. Less explicit; sometimes great, sometimes mysterious.

Always pin to image **digests** in production overlays, not tags. `myapp:v1.2.3` can be re-pushed; `myapp@sha256:...` cannot.

### Rollbacks

In GitOps, a rollback is a `git revert`. That's the whole story. Don't `kubectl rollout undo` in a GitOps cluster — the controller will revert *your* revert.

## Operators and CRDs

CRDs let you extend the API. Operators are controllers for those CRDs. The pattern is powerful and the bar is high — once a CRD is in production it's hard to remove. Use operators for things that genuinely have a control loop (databases that need failover, certificate rotation, Kafka topics). Don't use them as a config-DSL ("AppOperator that creates a Deployment from a custom resource"). That's just Helm with extra steps.

If you do build one, lean on `controller-runtime` (Go) or Kopf (Python). Idempotency, status subresources, and event recording are non-negotiable.

## Debugging playbook

Walk the chain. In order:

1. `kubectl get deploy -n NS APP` — does it exist? `READY` column.
2. `kubectl describe deploy ...` — events at the bottom; conditions; latest ReplicaSet.
3. `kubectl get rs -n NS -l app=APP` — is the new RS scaling up? Old RS scaling down?
4. `kubectl get pods -n NS -l app=APP` — `STATUS` column tells you most of the story.
   - `Pending` → `describe pod`: scheduling failure (resources, taints, PVC binding).
   - `ImagePullBackOff` → wrong image name, missing pull secret, registry down.
   - `CrashLoopBackOff` → `kubectl logs --previous`. App crashed; read the actual error.
   - `Running` but not Ready → readiness probe failing. `describe pod`, look at probe config and recent events.
   - `OOMKilled` → memory limit too low or leak.
5. `kubectl logs -n NS POD -c CONTAINER` — the actual application output.
6. `kubectl get events -n NS --sort-by=.lastTimestamp` — global view.

If the rollout is stuck mid-deploy: `kubectl rollout status` and `kubectl describe deploy` will tell you why (often a failed readiness probe on the new pods, blocking progress per `maxUnavailable`).

## Things that bite people

- **No PDB → cluster upgrade takes down all replicas at once.**
- **Liveness probe checking the database → DB blip causes whole-fleet restart cascade.**
- **No `topologySpreadConstraints` → all replicas land on one node, one node failure = full outage.**
- **`imagePullPolicy: Always` with mutable tag `latest` → silent version skew between pods.**
- **`hostPath` volume in a Deployment → data lives on whichever node the pod ran on; gone after reschedule.**
- **Forgetting to set `terminationGracePeriodSeconds` for a service with long requests → SIGKILL during deploys, dropped connections.**
- **Storing 50 MB of templates in a ConfigMap → etcd object size limit (~1 MB practical) blows up.**
- **`kubectl edit` in a GitOps cluster → controller reverts it, "why did my fix disappear?"**

## Checklist before shipping a manifest to prod

- Resources requested (and memory limited).
- Liveness, readiness, and startup probes set appropriately.
- Replicas ≥ 2 with a PDB.
- TopologySpreadConstraints across zones (and nodes).
- Non-root securityContext, restricted PSS.
- NetworkPolicy in place (default-deny + explicit allows).
- ServiceAccount per workload, narrow RBAC, token automount disabled if unused.
- Image pinned by digest, signed (cosign) and verified in admission (Kyverno / Sigstore policy).
- Labels include `app.kubernetes.io/*` standards.
- Logs go to stdout/stderr (not files inside the container).
- Metrics endpoint exposed; `ServiceMonitor` or scrape annotations applied.
- Manifests are in Git, applied by Argo CD/Flux. No `kubectl apply` from a laptop to prod.
