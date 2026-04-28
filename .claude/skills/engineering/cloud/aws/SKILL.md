---
name: aws
description: Use this skill for any work on Amazon Web Services — choosing services, designing architecture, IAM and policy authoring, VPC/networking design, compute selection (EC2/ECS/EKS/Lambda/Fargate), data store selection (S3/RDS/Aurora/DynamoDB), messaging (SQS/SNS/EventBridge/Kinesis), security (KMS/Secrets Manager/GuardDuty), observability (CloudWatch/X-Ray), cost optimization, account structure (Organizations/Control Tower), and Well-Architected reviews. Trigger on requests involving AWS services by name, AWS architecture diagrams, AWS-specific errors, AWS CLI/SDK questions, or "deploy to AWS" tasks. Use alongside iac-terraform when provisioning AWS resources as code.
---

# AWS

AWS rewards understanding its primitives more than memorizing its services. Most well-architected systems on AWS are five or six services composed thoughtfully, not twenty assembled from a marketing diagram. This skill is about how to think on AWS, with enough specifics to stay out of the common traps.

## Account structure (do this before anything else)

Use **AWS Organizations** with multiple accounts, not one account with stages mixed together. The account is AWS's hardest blast-radius boundary; a compromised IAM role in `prod` cannot reach `dev` if they're separate accounts.

A reasonable starting layout:

```
Organization
├── Management account (billing, SCPs, no workloads)
├── Log archive account (centralized CloudTrail, immutable)
├── Audit / security account (Security Hub, GuardDuty aggregator)
├── Shared services account (DNS, CI/CD, central tooling)
├── Workload accounts: dev, staging, prod (per team or per app)
└── Sandbox accounts (per developer, low budget, auto-cleanup)
```

**Control Tower** sets this up with guardrails. **AFT (Account Factory for Terraform)** is the codified version. For new orgs, start with Control Tower; for existing orgs, retrofit as you can.

**SCPs (Service Control Policies)** enforce coarse rules across accounts: "no one can disable CloudTrail," "no IAM users with console access in prod," "no resources outside us-east-1 and us-west-2." SCPs are deny-rails, not grants.

## IAM is the only security model that matters

Everything in AWS is IAM under the hood. Get this right.

### Identities

- **IAM users** — long-lived credentials. Avoid them outside legacy edge cases. No human should get an IAM user.
- **IAM roles** — temporary credentials, assumed by a principal. Use these for everything: services, EC2 instances, Lambda, ECS tasks, CI runners.
- **IAM Identity Center (formerly SSO)** — federate human access from your IdP (Okta, Entra, Google). Humans get role sessions, not access keys.
- **OIDC federation** — for CI systems. GitHub Actions → AWS via OIDC means no static AWS keys in GitHub secrets.

### Policies

Five places policies attach; understand the evaluation order:

1. **SCP** (org-level) — sets the maximum.
2. **Resource policy** (e.g., S3 bucket policy, KMS key policy) — can grant cross-account.
3. **Identity policy** (attached to user/role) — what this principal can do.
4. **Permission boundary** — caps what an identity *could* be granted.
5. **Session policy** — narrows a specific assumed-role session.

A request is allowed only if every applicable layer allows it (with explicit denies winning everywhere). When debugging, the **IAM Policy Simulator** and **CloudTrail's `errorCode: AccessDenied`** events plus the new IAM Access Analyzer findings tell you what got blocked and where.

### Writing policies that don't get you fired

- **Least privilege.** Start with `Deny *`, grant specific actions on specific resources. Don't reach for `"Action": "*"` on `"Resource": "*"`.
- **Use `Condition`.** `aws:SourceVpc`, `aws:SourceIp`, `aws:PrincipalOrgID`, `aws:RequestTag`, `kms:ViaService`. Conditions tighten access without breaking it.
- **Avoid wildcards in `Resource`** for sensitive services (KMS, IAM, Secrets Manager).
- **Use `iam:PassRole` carefully.** Whoever can pass a role to a service can effectively *become* that role.
- **Read CloudTrail** before designing a least-privilege policy. Use **IAM Access Analyzer "policy generation"** which builds a policy from observed CloudTrail activity.

### Roles for workloads

Every workload assumes a role. The role is the identity. Examples:

- EC2 → instance profile.
- ECS task → task role.
- Lambda → execution role.
- EKS pod → IAM Roles for Service Accounts (IRSA) via OIDC, or **EKS Pod Identity** (newer, simpler).

Never give an EC2 instance broad access "for now." Either it's needed or it isn't.

## Networking: VPC

A VPC is a private network in one region. Design considerations:

- **CIDR sizing** — `/16` for the VPC, `/19` or `/20` per subnet. Don't squeeze; you can't easily expand.
- **No overlapping CIDRs** with anything you might peer to: other VPCs, on-prem, partners.
- **Three AZs** — anything HA spans three AZs. Two-AZ leaves you exposed during AZ events.
- **Subnet tiers** — public, private (NAT egress), isolated (no egress). Per AZ.

### Internet egress

`Private subnet → NAT Gateway → Internet Gateway`. NAT Gateways are **per-AZ** and **expensive at scale** (per-GB processing fees). Two ways to spend less:

- One NAT Gateway shared across AZs — cheaper but cross-AZ data charges; loss of one AZ takes egress with it.
- One NAT Gateway per AZ — more cost, real HA. Default to this for production.

Better: **VPC endpoints** for AWS services so traffic to S3, DynamoDB, ECR, CloudWatch, Secrets Manager, etc., never traverses NAT.

### VPC endpoints

Two flavors:

- **Gateway endpoints** — S3 and DynamoDB only. Free. Add a route in your route table.
- **Interface endpoints (PrivateLink)** — for everything else. Paid per endpoint per AZ + per-GB. But they replace NAT traffic and are usually cheaper at scale, plus traffic stays inside AWS.

Rule of thumb: any production VPC should have endpoints for at least S3, DynamoDB, ECR (api + dkr), CloudWatch Logs, STS, Secrets Manager, KMS — assuming you use them.

### Connectivity options

- **VPC peering** — two VPCs talk. Non-transitive. Fine for 2–3 VPCs.
- **Transit Gateway** — hub-and-spoke for many VPCs and on-prem. Use this beyond a handful of VPCs.
- **PrivateLink** — expose one service privately. Best when only specific endpoints need to be reachable.
- **Site-to-Site VPN** — IPsec to on-prem. Cheap, modest bandwidth.
- **Direct Connect** — dedicated circuit. Expensive, predictable.

## Compute: choosing the right one

| Option | Use when | Avoid when |
|---|---|---|
| **Lambda** | Event-driven, sporadic traffic, glue, < 15 min runs | Long-running, stateful, latency-critical (cold starts), heavy CPU/RAM |
| **Fargate (ECS or EKS)** | Containers without managing nodes | Special hardware needs, very tight cost control at scale |
| **ECS on EC2** | Containers with control over node fleet, GPUs, lower cost at scale | When you don't need that control — Fargate is simpler |
| **EKS** | Already standardized on Kubernetes, polyglot teams, complex orchestration | Single-app deployments, small teams new to K8s |
| **EC2** | Legacy, special hardware, custom kernels, niche workloads | Anything that fits the above |
| **App Runner / Lightsail** | Trivial web apps, demos | Anything production-critical |
| **Batch** | Long-running batch jobs with queueing | Real-time work |

Default for a new web service: **ECS Fargate**, behind an ALB, deployed via CodeDeploy or your own pipeline. EKS is justified when team scale demands it; for a single-app team, EKS is overkill and a permanent operational tax.

### Lambda specifics

- Cold starts: tens to hundreds of ms for most runtimes; >1s for Java/.NET unless tuned. **SnapStart** helps for Java. **Provisioned concurrency** eliminates them at a cost.
- 15 min hard limit. 10 GB memory hard limit. 6 MB sync invoke payload (26 MB async). 250 MB unzipped artifact (10 GB if container image).
- Don't `import boto3` and not reuse the client — clients live across invocations on the same warm container; reuse them.
- VPC-attached Lambdas have improved cold starts vs the bad old days, but every VPC Lambda needs ENI capacity. Don't VPC-attach unless you need to reach VPC resources.
- **Lambda + RDS = pool exhaustion** unless you put **RDS Proxy** in between. Concurrent Lambda execution × connections per Lambda will blow past the DB's limit.

### ECS Fargate specifics

- Task definition = image + resources + IAM role + log config. Service = how many tasks, behind what load balancer.
- **Use the awsvpc network mode** (Fargate forces this anyway). Each task gets an ENI in your subnet.
- ALB target group health check needs to point at `/healthz` or similar; default `/` often works incidentally and breaks later.
- **Capacity providers** for spot mix. **CodeDeploy blue/green** for safer deploys (linear/canary on the ALB target groups).

### EKS specifics

- Use **managed node groups** or **Karpenter** for autoscaling. Karpenter is far better than Cluster Autoscaler for most cases — bin-packs better, faster, supports more instance shapes.
- **IRSA or Pod Identity** for pod-level IAM. Don't give the node IAM the union of every pod's needs.
- **Fargate profiles** for serverless pods. Good for control-plane add-ons; expensive for everything-Fargate.
- **Add-ons** (`coredns`, `kube-proxy`, `vpc-cni`, `aws-ebs-csi-driver`) — install via the EKS add-on API, not raw manifests, so they upgrade cleanly.
- **VPC CNI** assigns real VPC IPs to pods. Watch your subnet capacity — pods burn IPs fast.
- The EKS control plane costs ~$73/month per cluster. Don't run "one cluster per app." Multi-tenant clusters are the norm; isolate with namespaces, RBAC, NetworkPolicy, and (for stronger isolation) separate node groups.

## Data stores

### S3

The most reliable distributed system AWS sells. A few rules:

- **Block public access at the account level.** Then exempt buckets that genuinely need it.
- **Bucket policy + KMS key policy** define who can read/write. Use SSE-S3 or SSE-KMS; never unencrypted.
- **Versioning + MFA delete** for anything you'd cry to lose. **Object Lock** for compliance / ransomware-resistant.
- **Lifecycle policies** — move infrequently accessed objects to IA, then to Glacier classes; expire old versions; abort multipart uploads after 7 days (forgotten parts cost money).
- **Intelligent-Tiering** is often cheaper than guessing access patterns yourself.
- **No `s3:*`** on `*`. Scope by prefix.
- **Strong read-after-write consistency** is now universal. Old "eventually consistent" caveats don't apply.
- **Don't use S3 as a key-value store with millions of tiny objects** — listing and per-request cost dominate. Use DynamoDB.

### RDS / Aurora

- **Aurora over RDS** for new Postgres / MySQL workloads. Better failover, better storage, better performance. Aurora Serverless v2 for variable workloads.
- **Multi-AZ.** Always for prod. Failover is in the tens of seconds.
- **Backups** — automated with point-in-time recovery; tune retention. **Snapshot before any major change.**
- **RDS Proxy** for connection pooling, especially in front of Lambda/Fargate fleets. Don't skip this.
- **Performance Insights** — turn it on. It's the easiest way to find slow queries.
- **Don't run prod on db.t* burstable instances** unless the workload is truly low. T-class throttles in ways that look like outages.
- **Read replicas** for read scale-out, but app needs to know which queries can go to a replica (replicas are slightly stale).
- **Parameter groups** — managed but tunable. Things like `log_min_duration_statement` for Postgres slow log are off by default.

### DynamoDB

- Schema design is **partition key + sort key** plus secondary indexes. Get this wrong and the table will be expensive or slow.
- **Single-table design** is a real pattern, not just AWS hype, but only when access patterns warrant it. For a single-domain app, multiple tables can be clearer.
- **On-demand** capacity for variable / unknown workloads; **provisioned** when you know the pattern and want lower cost.
- **TTL** field for automatic expiry — cheaper than scheduled deletes.
- **DynamoDB Streams + Lambda** for event sourcing or replication.
- **Global tables** for active-active multi-region (eventually consistent).
- **Watch hot partitions.** A partition key that puts 80% of traffic on one partition will throttle even if total capacity is fine.

### ElastiCache (Redis / Memcached / Valkey)

- **Valkey** (the open-source fork) is now the default Redis-compatible engine on ElastiCache; cheaper than Redis OSS license-restricted versions.
- Use cluster mode for sharding; replication groups for HA reads.
- Set `maxmemory-policy` deliberately (`allkeys-lru` is a sane default for cache; `noeviction` for primary store — only if you're actually using it as one).
- Encryption in transit + at rest, both off by default for backwards compat. Turn them on.

### Other databases

- **OpenSearch** — for search and log analytics. Operational nightmare at scale; serverless OpenSearch is the path of less pain for new builds.
- **Neptune** — graph workloads only.
- **Timestream** — time-series. Niche.
- **Keyspaces** (Cassandra) — only if you're already on Cassandra.

## Messaging and events

| Service | Use when |
|---|---|
| **SQS standard** | Decouple producer from consumer. At-least-once. Default. |
| **SQS FIFO** | Strict ordering and exactly-once dedup within group. Lower throughput. |
| **SNS** | Pub/sub fan-out to many subscribers (lambda, SQS, HTTP, email). |
| **EventBridge** | Cross-service event bus, schema registry, pattern-matching routing, third-party SaaS sources. The default for new event-driven architectures. |
| **Kinesis Data Streams** | Ordered log of high-throughput events; multiple consumers, replay. |
| **MSK** (Managed Kafka) | Already standardized on Kafka, complex stream processing. |
| **Step Functions** | Workflow orchestration with retries, parallel branches, long-running coordination. Pays for itself the first time you'd otherwise hand-roll a state machine. |

Default pattern for "process work asynchronously": **SQS + Lambda** (or ECS service polling SQS). Set a **Dead Letter Queue** and *actually monitor it.*

For "broadcast to many consumers": **EventBridge** (or SNS). EventBridge is the modern choice unless you already have an SNS thing.

## Storage gotchas

- **EBS gp3** over gp2 — better performance per dollar. Switch.
- **EFS** is convenient but slow for small files; latency is much higher than EBS. Don't host a database on EFS.
- **FSx** for specialized workloads (Lustre for HPC, NetApp ONTAP for migrations, Windows for SMB).
- **S3 Express One Zone** for ultra-low-latency, single-AZ — niche; only if you've actually measured S3 standard as your bottleneck.

## Security baseline

Per account, on day one:

- **CloudTrail** enabled, logs to a centralized log archive account, with log file integrity validation.
- **Config** enabled, with conformance pack (CIS or AWS Foundational).
- **GuardDuty** enabled in every region you use; aggregated to security account.
- **Security Hub** with CIS / AWS Foundational Best Practices standards.
- **IAM Access Analyzer** enabled.
- **S3 block public access** at account level.
- **Default EBS encryption** on.
- **VPC Flow Logs** to S3 or CloudWatch.
- **Root account**: MFA, no access keys, no daily use, contact info correct.
- **Cost anomaly detection** enabled; budget alerts wired to a real channel.

KMS key policy hygiene: a CMK that lets `"AWS": "*"` is effectively a public key. Be explicit about who can `Encrypt` / `Decrypt` / `GenerateDataKey`. Use **separate CMKs per data domain** so blast radius is bounded.

**Secrets Manager** for secrets (with rotation). **SSM Parameter Store** for non-secret config (it's cheaper). Don't put secrets in environment variables stored in plaintext task definitions.

## Observability

- **CloudWatch Logs** — default sink. **Log Insights** for ad-hoc queries.
- **CloudWatch Metrics** — namespace per service, low-cardinality dimensions.
- **CloudWatch Alarms** — on SLO-meaningful signals (5xx rate, latency p99), not on every metric.
- **X-Ray / OpenTelemetry** — tracing. Use OTel; X-Ray supports it natively now.
- **CloudWatch Container Insights / Lambda Insights** — managed deep telemetry; usually worth the cost.
- **Athena over CloudTrail / VPC flow logs / ALB logs** — query S3-stored logs without standing up a stack.

For prod, consider sending logs/metrics to a third-party observability system (Datadog, Honeycomb, Grafana Cloud, etc.). CloudWatch is fine for foundational telemetry but its UX and aggregation get painful at scale.

## Cost: the patterns that move the needle

The 80/20 of AWS bills:

1. **Right-size compute.** Look at actual CPU/memory; downsize. Compute Optimizer surfaces this.
2. **Savings Plans / Reserved Instances** for steady-state. Compute Savings Plans (1-year, no upfront) cover ~30% of compute cost easily.
3. **Spot** for fault-tolerant batch and stateless workloads. Karpenter handles spot interruption gracefully.
4. **Kill data transfer.** Cross-AZ traffic, NAT egress, cross-region replication — these accrete unnoticed. VPC endpoints cut NAT egress for AWS services.
5. **S3 lifecycle.** Move cold data to IA / Glacier. Expire incomplete multipart uploads.
6. **Idle resources.** Unattached EBS volumes, idle NAT gateways, unused ELBs, sandbox accounts.
7. **CloudWatch Logs retention.** Default is "never expire." Set to 14/30/90 days as appropriate.
8. **Right-size databases.** RDS at 5% CPU is over-provisioned.

**Cost Explorer + tags** are your eyes. Without consistent tagging, you can't allocate cost to a team or product. Enforce tags via SCPs and `aws:RequestTag` conditions.

## The Well-Architected Framework, condensed

Six pillars: Operational Excellence, Security, Reliability, Performance Efficiency, Cost Optimization, Sustainability. The framework is more useful as a question list than a doctrine:

- Are deploys automated and reversible?
- Is every credential temporary?
- Can you lose any one AZ and stay up?
- Are you measuring against an SLO, or just "is the dashboard green"?
- Is there a documented owner for every running resource?
- Have you actually done a restore from backup recently?

If you can't answer those, the framework's deeper questions don't matter yet.

## Common AWS anti-patterns

- One AWS account for the whole company.
- IAM users with long-lived access keys for human use.
- Long-lived access keys *anywhere* (CI, scripts, laptops). OIDC + roles instead.
- `0.0.0.0/0` security group rules on production.
- Manual changes in the console on prod resources (drift from IaC).
- "We'll add CloudTrail later."
- Lambda + RDS without RDS Proxy.
- One giant VPC for the whole org.
- A NAT Gateway with no VPC endpoints, then surprise at the egress bill.
- Building on EKS because "everyone uses Kubernetes" without the team or the workload to justify it.
- Hardcoded region (`us-east-1`) everywhere — when you finally need multi-region, the rewrite is painful.
- Ignoring AZ failures because "we have multi-AZ" — on paper. Test it.
