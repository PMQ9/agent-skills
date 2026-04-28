---
name: secrets-management
description: Use this skill any time secrets, credentials, API keys, tokens, passwords, certificates, or sensitive configuration are involved — including storing secrets, fetching them at runtime, rotating them, sharing across services, encrypting at rest, designing service-to-service auth, or auditing a repo for leaked secrets. Trigger on mentions of Vault, AWS Secrets Manager / SSM Parameter Store, GCP Secret Manager, Azure Key Vault, KMS, SOPS, Sealed Secrets, External Secrets Operator, dotenv files, IRSA / Workload Identity / OIDC federation, mTLS, certificate rotation, or "how do I get this secret to my app". Also trigger when reviewing a repo or pipeline for accidental secret exposure, or when a user proposes putting a secret somewhere it doesn't belong.
---

# Secrets Management

The two failure modes are: (1) the secret leaks, and (2) the secret can't be rotated when it does. Most "secrets management" advice is downstream of those two facts.

## Core principles

- **Never in source control.** Not in `.env.example`, not "just for staging," not "encrypted with my GPG key." The moment a secret is committed, assume it is leaked — Git history is forever, and forks/clones make redaction impossible.
- **Never logged.** Structured loggers should redact known-secret fields by default. Stack traces with bound parameters routinely include passwords; this is a recurring leak vector.
- **Rotation must be a routine event, not an incident.** If rotating the DB password requires a war room, you've designed it wrong. The system should rotate without anyone noticing.
- **Identity, not secrets, where possible.** A workload with a verifiable cloud identity (IRSA, GCP Workload Identity, Azure Managed Identity) doesn't need a long-lived API key. Eliminate the secret rather than manage it.
- **Least privilege, narrow scope, short TTL.** A secret that's read-only, scoped to one resource, and expires in an hour is much less dangerous than an admin token that lives forever.
- **Audit access.** Every read of a high-value secret should produce a log entry tied to a principal, with rate-limiting and anomaly alerts on top.

## The hierarchy of solutions, from worst to best

1. **Plaintext in code or config files** — wrong. Skip.
2. **Plaintext in `.env` files, gitignored** — fine for local dev *only*. Don't kid yourself that this is "secret"; it's just out of view.
3. **Environment variables injected at deploy time from a CI variable store** — workable for small teams. CI variable stores (GitHub Actions secrets, GitLab CI variables) are encrypted at rest and masked in logs, but reading and rotation are clunky and there's no audit trail of *runtime* access.
4. **A dedicated secret manager** (Vault, AWS Secrets Manager, GCP Secret Manager, Azure Key Vault, 1Password Secrets Automation) — the right answer for production. Centralized, audited, rotation-capable, access-controlled.
5. **Workload identity + short-lived dynamic credentials** — best. The workload authenticates with its platform identity and gets a fresh, scoped credential per session. No long-lived secret to leak.

When advising a team, push them up the ladder, but don't let perfect block good. Going from "in Git" to "in a CI secret store" is a real win even if the eventual goal is Vault + dynamic credentials.

## Local development

The least-bad pattern:

- A `.env.example` checked in with **placeholders, not real values**: `DB_PASSWORD=changeme`.
- A `.env` in `.gitignore`, populated locally. Provide a one-line bootstrap script that fetches dev secrets from the team's secret manager (`op read`, `vault kv get`, `aws secretsmanager get-secret-value`).
- A `direnv` (`.envrc`) integration is a nice quality-of-life upgrade.
- Pre-commit hook with `gitleaks` or `trufflehog` to catch accidental commits.

Do not share dev `.env` files in Slack, email, or "team password docs." The CI's secret store, or 1Password/Bitwarden vaults shared at the team level, are the right channels.

## Server-side / production patterns

### Pattern A — Cloud-native secret manager + workload identity

The modern default on a cloud platform.

- **AWS:** EKS pods get an IAM role via IRSA (IAM Roles for Service Accounts). The pod's SDK calls Secrets Manager / SSM with that role. No keys.
- **GCP:** GKE Workload Identity binds a Kubernetes ServiceAccount to a Google Service Account; the SDK gets a token automatically.
- **Azure:** AKS Workload Identity / federated credentials does the equivalent.

This eliminates the bootstrap problem ("how does the secret-fetcher authenticate?") because the platform does it. *Always* prefer this on a cloud-native deployment.

### Pattern B — HashiCorp Vault

Vault shines when you're multi-cloud, on-prem, or need features the cloud-native managers lack:

- **Dynamic secrets** for databases, AWS, etc. — Vault generates a fresh DB user with a TTL on demand.
- **Transit secrets engine** for "encryption as a service" without ever giving the app the key.
- **PKI engine** for short-lived certs / mTLS.
- **AppRole or k8s auth method** for workload authentication.

Vault is operationally heavy. Run it as HA (Raft storage), back it up religiously (auto-unseal with cloud KMS so you don't have to rebuild Shamir keys at 3 AM), and treat the root token like radioactive material.

### Pattern C — Kubernetes-native secrets-in-Git

When you want secrets in Git for GitOps (with auditability) without leaking them, two main tools:

- **SOPS** — encrypt the secret file with a KMS key (AWS KMS, GCP KMS, age, PGP). The file in Git is ciphertext; only principals with KMS access can decrypt. Kustomize and Flux integrate natively. Argo CD via plugin.
- **Sealed Secrets (Bitnami)** — encrypt with a public key whose private key lives only in the cluster controller. Cluster decrypts on the fly. Simpler than SOPS but cluster-bound (a sealed secret encrypted for cluster A won't decrypt in cluster B; treat the controller key as cluster state to back up).

For both, the *value* of the secret is encrypted; metadata (the fact that there's a secret named `db-password` for service `api`) is not. That's usually fine.

### Pattern D — External Secrets Operator

The bridge pattern. The actual secret lives in an external manager (Vault, AWS, GCP, etc.). An ExternalSecret CR in the cluster specifies "fetch X from manager Y, materialize as a Kubernetes Secret named Z." The operator polls and keeps the Secret in sync.

```yaml
apiVersion: external-secrets.io/v1beta1
kind: ExternalSecret
metadata: { name: api-db-creds }
spec:
  refreshInterval: 1h
  secretStoreRef: { name: aws-secrets, kind: ClusterSecretStore }
  target: { name: api-db-creds, creationPolicy: Owner }
  data:
    - secretKey: DATABASE_URL
      remoteRef: { key: prod/api/db, property: url }
```

This is the right answer when you want GitOps for *what* secrets exist (the ExternalSecret is in Git) without putting the *value* in Git at all.

## Service-to-service authentication

A secret you never minted is a secret you can't leak. The patterns, in order of preference:

1. **mTLS with workload identity** — SPIFFE/SPIRE, Istio, Linkerd. Each workload has a short-lived cert tied to its identity. Mutual auth without shared secrets.
2. **OIDC tokens / OAuth2 client credentials** — the service obtains a JWT from an IdP, passes it as a bearer token. Tokens are short-lived. Cloud platforms can mint these from workload identity (GCP, AWS) — no static secret involved.
3. **Static API keys / shared secrets** — if you must. Generate per-consumer, store in a manager, rotate on a schedule, hash at the receiver, and revoke individually.

If you find yourself baking a shared HMAC key into both client and server, ask whether OIDC + signed JWT or mTLS would do the job instead.

## Database credentials specifically

Three options, increasing in maturity:

1. **Static credential in a secret manager.** Acceptable for small teams. Rotate manually on a schedule.
2. **Automated rotation with the secret manager** (AWS Secrets Manager rotation Lambdas, Vault `database/rotate-root`). The manager rotates on a schedule and updates downstream consumers on next fetch. Apps must be tolerant of mid-flight rotations — fail open by retrying once with the freshest secret.
3. **Dynamic credentials per session.** Vault `database` engine: each app instance requests a credential at startup (or per-connection), TTL of an hour or so, leases get renewed. When a pod dies, its DB user dies with it — incident response gets dramatically simpler.

Caveat: dynamic credentials interact poorly with long-lived connection pools that don't refresh credentials. Plan for a short TTL with renewal, or use IAM auth where the cloud DB supports it (RDS IAM auth, Cloud SQL IAM, etc.).

## Cloud database IAM auth — underrated

AWS RDS and Aurora support IAM database authentication. Your app calls `rds:GenerateDBAuthToken` (with its IAM/IRSA identity), receives a 15-minute token, and uses it as the DB password. No secret manager, no rotation, no static credential. GCP Cloud SQL has a similar pattern with the Cloud SQL Auth proxy and IAM. Use these where you can — they're the highest-leverage secret-elimination available.

## TLS certificates

Stop generating long-lived self-signed certs and emailing them. The two patterns that work:

- **cert-manager + Let's Encrypt** for public-facing TLS in Kubernetes. ACME HTTP-01 or DNS-01 challenges, automatic renewal.
- **Vault PKI** or **AWS Private CA / GCP Certificate Authority Service** for internal mTLS. Short-lived (hours, not years), automatic rotation via cert-manager or service mesh.

If you're rotating certs by hand, you'll forget. The 3 AM page when an internal cert expires is a rite of passage you do not need to undergo.

## Rotation

A rotation strategy has three parts:

1. **Cadence.** Define it (monthly, quarterly, on-demand). Calendar it. The auditor will ask.
2. **Mechanism.** Automated (preferred) or runbooked. Test the runbook by *actually doing* a rotation in staging quarterly — runbooks rot.
3. **Overlap window.** During rotation, both old and new secrets must work simultaneously for at least the time it takes for all consumers to refresh. Hard cutover rotations cause outages.

Rotate immediately on:
- Departure of someone with access.
- Exposure (real or suspected — a leaked debug log, a stolen laptop, a public repo push).
- Any audit failure.

## Detecting leaks

- **Pre-commit:** `gitleaks` or `trufflehog` as a hook.
- **CI:** the same tools as a required check on every PR.
- **Cloud provider scanners:** GitHub Secret Scanning + push protection, GitLab equivalent. Turn them on.
- **History scrubbing:** if a secret hits a repo, **rotate first, then redact.** `git filter-repo` to scrub history is necessary but not sufficient — assume the secret is compromised the moment it was pushed, even if the commit was force-deleted seconds later (forks, clones, GitHub's network of caches).
- **Runtime egress monitoring:** detecting *use* of a leaked credential is the last line of defense — anomaly detection on auth events from the secret manager (geographic, time-of-day, principal).

## Anti-patterns to call out

- **"We'll just encrypt the .env file and commit it."** Where does the decryption key live? If it's in the same repo, you've moved the problem. If it's in CI, you've reinvented worse-than-SOPS.
- **Shared service account keys passed around in Slack.** No.
- **"It's an internal secret, doesn't matter."** Internal-network = single network bug from external. Treat all secrets as if the perimeter is compromised tomorrow.
- **A single `prod-secrets` blob with everything in it.** Now every service can read every secret. Split per-service and scope IAM/Vault policies.
- **Secrets in CI logs because someone `echo $TOKEN`'d for debugging.** Most CIs mask known secrets, but only if the variable was registered as a secret. Custom-derived values (e.g. base64 of a secret) are not masked. Audit pipeline output.
- **Long-lived tokens in mobile/desktop client apps.** Use OAuth flows with refresh tokens scoped narrowly, or device-specific keys. A static API key in a published binary is public.
- **Putting secrets in image build args / Dockerfile `ENV`.** Image layers are inspectable; the secret is in the image forever. Use build secrets (`--secret`) or fetch at runtime.

## Quick checklist when reviewing a service for secret hygiene

- Where do secrets live at rest? (Goal: a manager, not a file.)
- How does the workload authenticate to fetch them? (Goal: platform identity, not another secret.)
- What's the rotation story? (Goal: automated, with overlap.)
- What's logged? (Goal: nothing sensitive; verified by sample of logs.)
- What's the blast radius if one is compromised? (Goal: scoped, audited, revocable per-instance.)
- Is there a leak-detection tripwire? (Goal: pre-commit + CI scan + provider scan.)
- Is the local-dev story safe? (Goal: bootstrap from the manager; no shared `.env`.)
- Who has read access in production? (Goal: list it; prove least privilege.)
