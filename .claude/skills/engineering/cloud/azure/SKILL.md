---
name: azure
description: Use this skill for any work on Microsoft Azure — choosing services, designing architecture, Entra ID and RBAC, networking (VNet/NSG/Front Door), compute selection (VMs/App Service/AKS/Container Apps/Functions), data stores (Azure SQL/Cosmos DB/Storage), messaging (Service Bus/Event Grid/Event Hubs), security (Key Vault/Defender for Cloud), observability (Monitor/Application Insights/Log Analytics), cost optimization, subscription/management group structure, and Well-Architected reviews. Trigger on requests involving Azure services by name, Azure architecture diagrams, Azure-specific errors, Azure CLI/PowerShell/SDK questions, or "deploy to Azure" tasks. Use alongside iac-bicep or iac-terraform when provisioning Azure resources as code.
---

# Azure

Azure has three things to know up front that don't translate from AWS or GCP: identity is Entra ID and it's its own universe, the resource hierarchy is unusual (management groups → subscriptions → resource groups → resources), and many services come in "Standard" and "Premium" SKUs where the gap matters more than the price difference suggests. This skill covers the primitives well enough to design and avoid the common traps.

## The hierarchy

```
Tenant (one Entra ID directory)
└── Management groups (nested, policy + RBAC inheritance)
    └── Subscriptions (billing + isolation boundary)
        └── Resource groups (lifecycle boundary)
            └── Resources
```

Important properties:

- **Tenant** = identity boundary. One per organization, normally.
- **Management groups** = nest them to apply policies / RBAC at the right scope. Create at minimum `root → platform / landing zones / sandboxes`.
- **Subscriptions** = the real isolation and billing boundary. *This* is Azure's equivalent to an AWS account. Use multiple per workload tier (prod/non-prod), per business unit, or per app — not just one giant subscription.
- **Resource groups** = a logical group whose members usually have the same lifecycle. Delete the RG → delete its contents. Don't put unrelated things in the same RG.

A subscription is bound to a single tenant. Moving subscriptions between tenants is supported but a real operation; plan tenancy carefully.

For new Azure setups, follow **Azure Landing Zones** (the Cloud Adoption Framework's prescriptive starting point). It gives you platform-managed identity, networking, governance, observability scaffolding, and a place to drop workload subscriptions cleanly. Either deploy via the official Bicep/Terraform modules or use the **Enterprise-Scale** reference architecture.

## Identity: Entra ID, RBAC, and managed identities

### Entra ID (formerly Azure AD)

Entra ID is the identity plane for Azure resources, M365, and any app you onboard. The objects:

- **Users** — humans.
- **Groups** — collections of users (or other groups). Assign RBAC to groups, not users, almost always.
- **Service principals** — non-human identities for apps. The thing that gets a client ID + secret/cert.
- **Managed identities** — service principals that Azure manages for you (no secret to rotate). Use these for any Azure-resident workload that needs to call other Azure resources.
- **App registrations** — define an application that needs Entra-issued tokens (OAuth flows, custom APIs).

Conditional Access is where modern Azure security lives. MFA, device compliance, location-based access — express them as Conditional Access policies, not as duct-taped network rules.

### Azure RBAC

RBAC is layered on top of Entra ID. A role assignment is `(security principal, role definition, scope)`:

- **Scope** — management group / subscription / resource group / resource.
- **Role definition** — `Reader`, `Contributor`, `Owner`, plus hundreds of built-ins, plus your customs.
- **Security principal** — user, group, service principal, managed identity.

Role assignments inherit *down* the scope tree. A `Contributor` at the subscription level is a `Contributor` on every RG and resource within.

A few rules:

- **Avoid `Owner`.** It can grant other people roles (privilege escalation). Use `Contributor` + a separate `User Access Administrator` for the rare role-management need.
- **Custom roles** for least privilege when built-ins are too broad.
- **Privileged Identity Management (PIM)** for just-in-time elevation of high-power roles. Audit trail + approval flow.
- **Don't conflate Entra ID roles with Azure RBAC roles.** "Global Administrator" (Entra) and "Owner" (RBAC) are different.

### Managed identities

Two types:

- **System-assigned** — lifecycle bound to the resource (deleted when resource is deleted).
- **User-assigned** — standalone resource, can be attached to many resources.

Use user-assigned for shared identities (e.g., one identity for an AKS pod identity setup or a fleet of VMs). Use system-assigned for one-off resources where you'll never share the identity.

Workloads should never have client secrets in code or config. Use managed identity → request token → call resource. The Azure SDKs do this transparently via `DefaultAzureCredential`.

For workloads outside Azure (e.g., GitHub Actions, on-prem) calling Azure: **workload identity federation** — federate via OIDC, no secret to store.

## Networking

### Virtual networks (VNets)

A VNet is a private network within a region. Subnets within a VNet:

- A subnet has one CIDR.
- Some subnets are reserved by services (`AzureBastionSubnet` must be exactly that name; `GatewaySubnet` for VPN/ExpressRoute; etc.).
- **Service endpoints** add a route from a subnet to specific Azure services over the Microsoft backbone.
- **Private endpoints** put a service behind a private IP in your VNet (the modern, preferred approach for most services).

Connectivity:

- **VNet peering** — two VNets exchange traffic. Non-transitive. Cheap.
- **Hub-and-spoke** with **Azure Firewall** in the hub — the canonical enterprise topology. Spokes peer to hub; hub does east-west and egress filtering.
- **Virtual WAN** — managed hub-and-spoke for many regions and on-prem. The right choice at scale; overkill for a couple of VNets.
- **VPN Gateway** — site-to-site IPsec to on-prem.
- **ExpressRoute** — dedicated circuit. Expensive, predictable, fast.
- **Private Link** — private connectivity to PaaS services (Azure SQL, Storage, Key Vault, etc.) over your VNet.

### Network Security Groups (NSGs) and Application Security Groups (ASGs)

- **NSG** — stateful firewall, attaches to NIC or subnet. Default rules at the bottom; explicit ones above.
- **ASG** — a label you put on NICs; reference the ASG in NSG rules instead of IP ranges. The Azure equivalent of "security group references": rules become `web → app` instead of `10.x.x.x → 10.y.y.y`.
- **Azure Firewall** — managed L4/L7 firewall with FQDN filtering, threat intel feeds. Sits in the hub. Costs real money; justified at enterprise scope.
- **WAF** (in Application Gateway / Front Door) — L7 protection.

### Public ingress

| Service | What it is | Use when |
|---|---|---|
| **Load Balancer** (Standard) | L4 | Non-HTTP, raw TCP/UDP, lowest cost |
| **Application Gateway** | Regional L7 + WAF | HTTP traffic in a single region |
| **Azure Front Door** | Global L7 + CDN + WAF | Multi-region, edge-cached, global anycast |
| **API Management** | API gateway with policies, dev portal, throttling | Public APIs needing more than routing |
| **Traffic Manager** | DNS-level traffic steering | Cross-region failover at DNS layer (slower than Front Door) |

Default for a new public web app: **Front Door + Application Gateway** (or Front Door alone with Private Link to backends). Don't expose AKS / VMs / App Service directly with their default public hostnames.

### Private endpoints

For nearly every PaaS service (Azure SQL, Storage, Key Vault, Cosmos DB, etc.), a **private endpoint** gives that service a private IP in your VNet. Combined with disabling public network access on the service, this is the cleanest way to keep PaaS data plane traffic off the internet.

Pair with **Private DNS Zones** (`privatelink.database.windows.net`, `privatelink.blob.core.windows.net`, etc.) so the service's hostname resolves to the private IP from inside the VNet. Get the DNS wrong and your app will helpfully resolve to the public IP and fail to connect.

## Compute

### Choosing a compute platform

| Option | Use when | Avoid when |
|---|---|---|
| **Azure Container Apps** | Containers, scale-to-zero, KEDA-driven scaling, simple | Need fine K8s control, persistent workloads at scale |
| **Azure Functions** | Event-driven, glue, light HTTP | Long-running, heavy workloads, predictable high traffic |
| **App Service** | Web apps, simple deploys, Linux/Windows, slot-based blue/green | Containers with custom networking, fine resource control |
| **AKS** (Kubernetes) | Complex orchestration, polyglot, already on K8s | Single-app teams, simple workloads (use Container Apps) |
| **Virtual Machines** | Legacy, niche OSes, GPU/specialty hardware | Anything that fits the above |
| **Azure Batch** | Large-scale batch jobs | Real-time work |
| **Service Fabric** | Existing Service Fabric apps | Greenfield (use AKS or Container Apps) |

Default for a new cloud-native service: **Container Apps**. It's the Azure-native answer to "I have a container, give me HTTPS and autoscaling and don't make me think about Kubernetes." Behind the scenes it runs on AKS managed by Microsoft.

### App Service

- Always use **deployment slots** for blue/green-style swaps. The swap is a config swap, not a redeploy — fast and reversible.
- **Application settings** become environment variables; **connection strings** behave similarly with type metadata.
- **VNet integration** to reach private resources; **private endpoint** to expose the App Service privately.
- **Always On** — turn on for any production app; otherwise the worker idles out.
- Free / Shared tiers are toys; B1 minimum for non-prod, P1v3 minimum for prod.

### AKS specifics

- **Node pools** — separate system pool and user pool(s). Use **spot node pools** for fault-tolerant workloads.
- **Use managed identities** for cluster identity; **Workload Identity** (the OIDC-based one, federated through Entra) for pods that need to call Azure resources. The older "AAD Pod Identity" is deprecated.
- **Azure CNI** vs **Azure CNI Overlay** vs **kubenet** — Azure CNI Overlay is the right default for new clusters. Each pod gets an IP from a separate overlay range, not from the VNet, avoiding IP exhaustion.
- **Cluster autoscaler** handles node scaling. **KEDA** (now built into AKS as an add-on) for event-driven workload scaling.
- **Azure Policy add-on** for cluster-level guardrails.
- **AKS upgrades** — node OS image upgrades + Kubernetes version upgrades. Both must happen regularly. Plan for them.

### Functions specifics

- Hosting plans matter:
  - **Consumption** — true serverless, scale-to-zero, cold starts.
  - **Premium / Flex Consumption** — warm workers, VNet integration, longer runtimes.
  - **Dedicated (App Service plan)** — predictable cost, no cold starts.
- The same cold-start traps as Lambda, plus a few Azure-specific ones (storage account dependency, large package sizes).
- **Durable Functions** for stateful orchestrations — Azure's answer to Step Functions, in-process.

## Data stores

### Azure SQL Database / Managed Instance

- **Azure SQL Database** — fully managed, single database, serverless or provisioned. The default for new SQL Server-style workloads.
- **Managed Instance** — almost-full SQL Server feature parity, for migrations from on-prem.
- **vCore + DTU** are two purchasing models. vCore is more flexible and easier to reason about; default to it.
- **Hyperscale** for very large databases or when you need rapid restores.
- **Always-on backups** included; configure retention.
- Use **AAD authentication** (Entra ID) instead of SQL logins. Managed identity → token → connect.

### Azure Database for PostgreSQL / MySQL

- **Flexible Server** is the modern offering. The older **Single Server** is being retired; don't start there.
- HA with zone-redundant standby.
- Connection pooling not built in; use PgBouncer (or app-level) for high-concurrency workloads.
- Read replicas for scale-out reads.

### Cosmos DB

- Globally distributed, multi-API (NoSQL/SQL API, MongoDB, Cassandra, Gremlin, Table). Default API: **Cosmos DB for NoSQL**.
- **Partition key choice is everything.** Pick something with high cardinality, evenly distributed, and aligned with your dominant query pattern. Bad partition key = throttled "hot partitions" with otherwise-fine total throughput.
- **RU/s** (request units) — the cost unit. Provisioned vs autoscale vs serverless. Serverless is great for low/variable traffic; autoscale is the workhorse for prod.
- **Consistency levels** — default is **Session** (per-client read-your-writes); options run from **Strong** to **Eventual**. Match to your needs; stronger = higher latency or cost across regions.
- **Change feed** for event sourcing / CQRS / replication patterns.

### Storage accounts

- One storage account contains blob, file, queue, and table services.
- **Block public network access** by default; expose via private endpoint.
- **Disable shared key access** where possible; use Entra ID (RBAC) auth instead.
- **Tiers**: Hot, Cool, Cold, Archive. Lifecycle policies move blobs between tiers.
- **ZRS / GZRS** for redundancy. ZRS = zone-redundant in one region; GZRS = geo + zone-redundant. Default to ZRS for prod single-region.
- **SAS tokens** are convenient and dangerous. They don't get revoked when an employee leaves. Prefer Entra-based auth; if you must use SAS, use **user-delegation SAS** (signed with a user's Entra credentials), not account-key SAS.

### Cache: Azure Cache for Redis

- **Standard / Premium / Enterprise** tiers. Premium adds VNet injection, persistence, clustering. Enterprise adds Redis modules and active geo-replication.
- For new workloads, the **Azure Managed Redis** offering is the modern replacement; it merges Premium + Enterprise capabilities.
- Always TLS in transit. Enable AAD auth where supported.

## Messaging and events

| Service | Use when |
|---|---|
| **Service Bus** | Enterprise messaging, queues + topics, sessions, transactions, dead-lettering. The default for asynchronous backend communication. |
| **Event Grid** | Pub/sub at scale, reactive workflows, fan-out from Azure resource events to handlers. |
| **Event Hubs** | High-throughput event ingestion (Kafka-protocol-compatible). Telemetry, IoT, log streams. |
| **Storage Queues** | Cheap simple queue. Use Service Bus instead unless you have a reason. |
| **Logic Apps** | Workflow / iPaaS, hundreds of connectors. Good for integrations; not a code platform. |

For "process work async" in code: **Service Bus + a worker** (Container Apps, Functions, AKS pod) is the canonical Azure pattern.

## Security baseline

Per subscription, on day one:

- **Microsoft Defender for Cloud** enabled with the relevant plans (Defender for Servers, App Service, Storage, SQL, etc.). Free tier is just the security posture; paid plans are what add real protection.
- **Activity log** exported to a central Log Analytics workspace.
- **Azure Policy** initiative assigned (`Azure Security Benchmark` or **Microsoft Cloud Security Benchmark**). Enforce critical rules with `Deny` or `DeployIfNotExists`.
- **Resource locks** on critical resource groups (`CanNotDelete` or `ReadOnly`).
- **Soft delete + purge protection** on Key Vault.
- **Diagnostic settings** sending key resource logs to Log Analytics + (optionally) a long-term storage account.
- **MFA enforced** for all human accounts via Conditional Access.
- **Break-glass accounts** — at least two emergency-access accounts excluded from Conditional Access, with very long random passwords stored offline.

### Key Vault

- **Soft delete + purge protection** on. Without these, an accidental delete is unrecoverable.
- **RBAC permission model** preferred over the legacy access policies model.
- Three object types: **secrets**, **keys**, **certificates**. Don't store keys as secrets — keys (HSM-backed if you care about FIPS) live as keys.
- **Rotation policy** on certificates and (where supported) secrets.
- Apps fetch via managed identity. No secret to store *to access the secret store*.

## Observability

The Azure observability stack is **Azure Monitor**, which is an umbrella for:

- **Log Analytics workspaces** — the log + KQL query plane. The single most important thing. Most teams use one workspace per environment.
- **Application Insights** — APM for code (request rates, dependencies, exceptions, distributed traces). Now stores in Log Analytics by default ("workspace-based").
- **Metrics** — platform metrics, custom metrics. Lower cardinality, faster alerts than logs.
- **Diagnostic settings** — per-resource toggle to ship logs/metrics into Log Analytics, Storage, or Event Hubs.
- **Alerts** — fire on metric thresholds, log queries (KQL), or activity log events. Action groups handle the notification side.

KQL (Kusto Query Language) is mandatory knowledge for anyone operating on Azure. It's pleasant once you've spent a day with it.

For deeper APM and product-grade dashboards, many teams pair Azure Monitor with Datadog / Grafana Cloud / New Relic; Application Insights is competent but limited at scale.

## Cost

The patterns that move the needle:

1. **Reservations / Savings Plans** — 1 or 3-year commitments save 30–60% on compute, SQL, Cosmos DB, etc. Compute Savings Plans are flexible across VM families.
2. **Right-size VMs and PaaS tiers.** Azure Advisor surfaces this.
3. **Spot VMs** for fault-tolerant batch (AKS spot pools, VM scale sets with spot priority).
4. **Auto-shutdown** on dev/test VMs.
5. **Storage tiering** — Hot → Cool → Cold → Archive via lifecycle.
6. **Log Analytics retention** — default is 30 days; set deliberately. Archive tier for compliance retention is much cheaper.
7. **Network egress** — cross-region replication, internet egress, ExpressRoute charges. Watch them.
8. **Idle resources** — orphaned managed disks, unused public IPs, app service plans with no apps.

**Azure Cost Management + Tags** + **Microsoft Cost Management exports to a storage account** + (for big estates) Power BI on top. Tagging discipline is enforceable through Azure Policy (`Append` and `Modify` effects).

## Well-Architected on Azure

Same pillars as the AWS framework: Reliability, Security, Cost Optimization, Operational Excellence, Performance Efficiency. Microsoft's [Azure Well-Architected Review](https://learn.microsoft.com/en-us/assessments/azure-architecture-review/) is a real checklist; run it on production workloads at least annually.

The questions that catch the most issues:

- Do you have multi-region failover, and have you actually tested it?
- Are managed identities used everywhere, or is there still a service principal with a secret?
- Are diagnostic settings enabled on every resource? Without them you have no logs.
- Is every resource tagged with owner, environment, cost center?
- Is Defender for Cloud enabled on the things that matter (servers, App Service, SQL, Storage, Key Vault, containers)?

## Common Azure anti-patterns

- One subscription for everything.
- One resource group for everything.
- App Services, AKS, etc., with public network access enabled and no private endpoints.
- SQL logins / shared keys instead of Entra-based auth.
- Storage accounts with shared key access enabled because "the SDK examples use it."
- Service principals with long-lived client secrets where managed identity would have worked.
- App Insights connection strings in code instead of pulled from Key Vault / config.
- Diagnostic settings missing — you'll only notice during an incident.
- Log Analytics ingestion runaway — verbose logging on a chatty service can cost five figures a month before anyone looks.
- Using the consumption-plan Function for a steady workload (it's optimized for bursty).
- "Run on the latest" — pinning to specific Kubernetes versions, App Service runtimes, and Bicep API versions matters for reproducibility.
- Skipping Azure Policy because "we'll enforce stuff later." The cost of retrofitting is high.
