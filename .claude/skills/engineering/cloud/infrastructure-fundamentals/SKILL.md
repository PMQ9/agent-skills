---
name: infrastructure-fundamentals
description: Use this skill for cloud-agnostic infrastructure and networking questions — DNS, TLS, load balancing, CDNs, reverse proxies, firewalls, VPNs, private connectivity, service meshes, certificate management, IP addressing, and HTTP-layer behavior. Trigger on anything involving traffic flow, latency, connectivity issues, "why is this slow," TLS errors, certificate renewal, choosing between L4 and L7 load balancers, designing public/private network topology, or understanding what sits between a user and a service. This skill complements aws and azure (which cover provider-specific implementations) by focusing on the underlying concepts.
---

# Infrastructure Fundamentals

Most cloud "issues" are networking issues wearing a costume. A request that fails between two services is failing somewhere in DNS, routing, TLS, a security group, a proxy, or a queue depth that filled up. The same primitives show up in AWS, Azure, GCP, and on-prem with different names. This skill is about the primitives.

## DNS

DNS is the most common source of "intermittent" production issues. A few rules:

- **TTL matters.** A 24-hour TTL means a 24-hour window of mixed routing during cutovers. Lower TTLs *before* a planned change, not during.
- **Negative TTLs exist.** A failed lookup gets cached too. If you fix a missing record, clients may still see NXDOMAIN until their resolver's negative cache expires.
- **`/etc/hosts` overrides DNS.** When debugging, check it. When demoing, check it. When something works only on one machine, check it.
- **Resolver behavior varies.** Some Java versions cache DNS forever by default (`networkaddress.cache.ttl`). Some Node libraries don't honor TTL. Long-running processes may cling to a stale IP for days.
- **CNAME at the apex doesn't work** in standard DNS (you can't `CNAME` `example.com` to something else). Most providers expose `ALIAS` / `ANAME` / "alias record" as a workaround.

Common record types:

| Type | Purpose |
|---|---|
| A / AAAA | Name → IPv4 / IPv6 |
| CNAME | Name → another name (not at apex) |
| ALIAS / ANAME | Apex-friendly alias (provider-specific) |
| MX | Mail exchanger |
| TXT | Free-form (SPF, DKIM, domain verification) |
| SRV | Service location (host + port) |
| CAA | Authorize which CAs can issue certs |
| NS | Delegation |

For services across regions or clouds, consider DNS-based traffic management (Route 53, Azure Traffic Manager, NS1) — but understand that DNS is an *eventual* steering mechanism, not a load balancer. Connection pools, resolver caches, and clients with pinned IPs make DNS-based failover slow.

## TLS / certificates

The minimum competent setup:

- **TLS 1.2+ only.** Disable TLS 1.0 and 1.1 (and SSL anything).
- **Modern cipher suites.** Use the cloud / load-balancer "modern" or "intermediate" preset. Don't hand-curate unless you know exactly why.
- **Automated renewal.** Manual cert renewal is an outage scheduler. Use ACME (Let's Encrypt, ZeroSSL) or your cloud's managed certificates.
- **Wildcards or SAN-rich certs.** Decide consciously. Wildcards are convenient but compromise blast radius is wider.
- **HSTS.** `Strict-Transport-Security: max-age=31536000; includeSubDomains; preload` once you're confident HTTPS is everywhere.
- **OCSP stapling enabled.** Reduces client-side validation latency.

Common cert errors and what they actually mean:

- **`SSL_ERROR_BAD_CERT_DOMAIN` / "doesn't match"** — SAN list doesn't include the hostname being requested. Often a load balancer config mismatch.
- **`UNABLE_TO_VERIFY_LEAF_SIGNATURE`** — missing intermediate. Server isn't sending the full chain. Add intermediates to the bundle.
- **`CERTIFICATE_VERIFY_FAILED` in older clients** — system trust store missing newer roots (Let's Encrypt root rotation has bitten many).
- **mTLS failures** — usually one side missing the CA, or clock skew on a cert with tight `notBefore`.

Time matters. Certificates have `notBefore` and `notAfter`; a host with significant clock skew (>5 min) will fail TLS for unobvious reasons. NTP isn't optional.

## HTTP at the edge: L4 vs L7

| Layer | What it sees | Examples | Use when |
|---|---|---|---|
| L4 (TCP) | IP, port, bytes | NLB, Azure LB (Standard), HAProxy in TCP mode | Non-HTTP protocols, lowest latency, TLS passthrough, raw throughput |
| L7 (HTTP) | Method, path, headers, body | ALB, App Gateway, Front Door, CloudFront, NGINX, Envoy | HTTP routing, path-based rules, header manipulation, WAF, auth, response caching |

Most public services want L7. Internal high-throughput service-to-service (especially gRPC) often does fine with L4 + client-side load balancing.

L7 load balancers terminate TLS and re-encrypt to the backend (or not). Two choices:

- **TLS termination at LB, plaintext to backend** — simplest. Fine inside a private network you trust.
- **End-to-end TLS** — LB terminates, opens a new TLS connection to backend (which has its own cert). Required for compliance (PCI, HIPAA-ish architectures) and "zero trust" stances.
- **TLS passthrough** — LB doesn't terminate at all (it's L4 in this case). Backends see the original handshake. Required for client-cert auth (mTLS).

## Reverse proxies and the "in front of" problem

A reverse proxy (NGINX, Envoy, Caddy, Traefik, HAProxy) sits between clients and services and does some combination of: terminate TLS, route by path/host, inject headers, cache, rate-limit, authenticate, retry, observe.

Things that go wrong with proxies:

- **`X-Forwarded-For` / `X-Forwarded-Proto`** — backend code that thinks it's reading the client's IP is reading the proxy's. Trust these headers only from known proxies; don't trust them from arbitrary clients (header injection).
- **Body size limits.** NGINX `client_max_body_size` defaults to 1MB. Files larger than that 413 mysteriously.
- **Idle timeout mismatches.** Proxy idles a connection at 60s; backend at 120s; clients see connection-resets from the LB sending RST on a connection the backend still thinks is alive.
- **Buffering.** Some proxies buffer the entire response before sending. Bad for streaming endpoints (SSE, large downloads, gRPC).

## CDN

A CDN is a globally-distributed reverse proxy with caching. Use it for:

- Static assets (images, JS, CSS).
- Public API responses that are cacheable and have a stable shape.
- TLS termination near the user (latency win even with no caching).
- WAF / DDoS absorption.
- Origin shielding (one CDN PoP fronts your origin, fanning out to others).

Cache key design is the heart of CDN behavior. The cache key is some normalization of (host, path, query string, headers, cookies). Get this wrong and you either serve user A's data to user B (catastrophic) or have a 0% hit rate (useless). Defaults from your CDN are usually safe; go custom only with care.

`Cache-Control` directives that matter:

- `public` / `private` — can shared caches store this?
- `max-age=N` — fresh for N seconds.
- `s-maxage=N` — same, but for shared caches; overrides `max-age`.
- `stale-while-revalidate=N` — serve stale for N seconds while refreshing in background.
- `no-cache` — must revalidate before reuse (NOT "don't cache").
- `no-store` — don't cache at all.
- `immutable` — content at this URL never changes; don't even revalidate.

Hash-named static assets (`app.a3f9c2.js`) + `Cache-Control: public, max-age=31536000, immutable` is the canonical setup.

## Network topology: public vs private

A reasonable default:

```
Internet
   │
   ▼
[ Public LB ]  ← public subnet, has internet-routable IP
   │
   ▼
[ App tier ]   ← private subnet, no public IP, egress via NAT
   │
   ▼
[ DB tier ]    ← private subnet, no internet egress
```

Subnet conventions:

- **Public subnet** — has a route to an internet gateway. Hosts here are reachable from the internet. Reserve for load balancers, bastions, NAT gateways.
- **Private subnet** — no internet route directly. Hosts here reach the internet (if at all) via NAT.
- **Isolated subnet** — no internet egress at all. For databases, sensitive workloads.

Three or more **availability zones** for HA. Subnets are usually per-AZ; replicate the structure across AZs.

CIDR planning matters and is hard to redo. Allocate generously: `/16` for a VPC, `/20` or larger for subnets. Don't pick `10.0.0.0/24` and discover six months later you can't grow.

Avoid overlapping CIDRs across VPCs/networks if there's any chance you'll peer them later. `10.0.0.0/16` in two accounts that need to talk = forced re-IP.

## NAT, egress, and "why can't this server reach the internet"

A host in a private subnet reaches the internet through a **NAT gateway** (managed) or **NAT instance** (DIY). NAT is expensive at scale (per-GB charges in clouds), and surprisingly often the answer to "why is our cloud bill so high."

For service-to-service traffic to managed cloud services (S3, Azure Storage, etc.), use **VPC endpoints / private endpoints / private link** to keep traffic off the internet and out of NAT entirely. Faster, cheaper, more secure.

Egress filtering: in a security-sensitive setup, restrict outbound destinations (egress firewall, DNS firewall) so a compromised host can't exfiltrate freely. This is where a **NAT instance running a forward proxy** earns its keep.

## Firewalls, security groups, NACLs

- **Stateful firewall / security group** — tracks connection state. A rule allowing inbound on :443 implicitly allows the response. Apply to the workload (instance, ENI, pod).
- **Stateless ACL / NACL** — explicit per-direction rules; subnet-level. Useful as a coarse blast-radius control; awkward for app-level rules because you must allow ephemeral ports back.

Default-deny inbound. Open the minimum. Document why each rule exists. Audit periodically — security groups accrete cruft fast.

For east-west traffic between services, prefer **identity-based** rules (this service can call that service) over IP-based when the platform supports it (security group → security group references in AWS, NSG application security groups in Azure, NetworkPolicy in K8s).

## VPN, peering, private link

To connect networks that aren't on the public internet:

- **Site-to-site VPN** — IPsec tunnel between two networks. Cheap, slow-ish, encrypted, sometimes flaky.
- **Direct connect / ExpressRoute** — dedicated circuit between your on-prem and cloud. Expensive, fast, predictable.
- **VPC peering / VNet peering** — connect two cloud networks in the same provider. Fast, no traversal of the internet. Non-transitive: A↔B and B↔C does *not* give you A↔C.
- **Transit gateway / virtual WAN** — hub for many networks. Use when peering becomes a mess (>5 networks).
- **Private link / private endpoint / VPC endpoint** — expose a single service privately into a network. Most surgical option; preferred when only one or two endpoints need to be reachable.

For client (laptop/user) access, **modern zero-trust gateways** (Tailscale, Cloudflare Access, Twingate, Zscaler, AWS Verified Access) have largely displaced traditional VPN appliances for new builds. They're identity-aware and don't require putting the user on the network.

## Service mesh

A service mesh (Istio, Linkerd, Consul Connect) gives you, for east-west service traffic:

- mTLS by default
- Retries, timeouts, circuit breaking at the platform
- Traffic shifting (canary by percentage)
- Per-call telemetry

Cost: operational complexity, latency overhead, debugging mystery (where did my header go?). Linkerd is the lighter option; Istio is full-featured but heavy.

A service mesh isn't free magic. Most small services do fine with library-level retries/timeouts and metrics. Adopt a mesh when you have many polyglot services and you're feeling the pain of inconsistent behavior across them, not before.

## "Why is this slow?" — a checklist

Latency problems compound. Trace through each hop:

1. **Client → DNS** — first lookup is the slowest. Resolver close? Cached?
2. **Client → edge (CDN/LB)** — TCP handshake + TLS handshake. Connection reuse helps.
3. **Edge → origin** — geographic distance, peering quality, idle TCP slow-start.
4. **Origin → service** — internal network, security group hops.
5. **Service work** — CPU, lock contention, GC pauses.
6. **Service → DB** — network + query + lock + index.
7. **DB → service → ... → client** — response trip.

Distributed tracing pays for itself the first time you have to answer "why was this request slow" and a single trace tells you which hop is at fault.

## IPv4 vs IPv6

For new public-facing services, dual-stack (IPv4 + IPv6) is increasingly default. Mobile networks especially are heavily IPv6 inside. IPv6-only is still a path with sharp edges (third-party APIs that don't have AAAA records, legacy clients).

Inside private networks, most teams stick with IPv4 + RFC 1918 for now. AWS, Azure, etc., support IPv6 internally if you want it; benefit is mostly avoiding RFC 1918 overlap headaches.

## The "always-on" anti-patterns

- One enormous flat network where everything can reach everything. The first compromise becomes the only compromise.
- A "temporary" `0.0.0.0/0` rule that's been there for two years.
- Manual cert renewals tracked on a calendar.
- Long DNS TTLs on records that change.
- A single load balancer for everything, with all the routing rules tangled together.
- Trusting `X-Forwarded-For` from the public internet.
- Hairpinning internal traffic through a public load balancer because nobody wired up internal routing.
- Peering networks with overlapping CIDRs and "just NATting between them" — works until it doesn't.
- One cloud account / one subscription / one project for everything. Blast radius is the entire org.
