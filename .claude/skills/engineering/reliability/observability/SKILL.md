---
name: observability
description: Use this skill for any work involving logs, metrics, traces, alerting, dashboards, SLOs, or monitoring — including instrumenting a service with OpenTelemetry, Prometheus, structured logging, or distributed tracing; writing or critiquing alerts; designing dashboards; defining SLIs/SLOs/error budgets; investigating an incident with telemetry; setting up Grafana / Loki / Tempo / Jaeger / Datadog / Honeycomb / New Relic; debugging a high-cardinality metrics blow-up; or deciding what to log and what not to. Trigger on "instrument", "trace", "metrics", "logs", "alert", "PagerDuty", "Prometheus", "Grafana", "OTel", "SLO", "p99 latency", "what should we monitor". Also trigger when a user describes a production problem and is about to debug without telemetry — push them to look at the data first.
---

# Observability

Observability is the property of being able to ask questions about your system's behavior — including questions you didn't anticipate when you built it — and get answers from data the system already emits. Monitoring is checking known unknowns. Observability is being equipped to investigate unknown unknowns.

The goal is not "more telemetry." It's *useful* telemetry: the right signals, at the right cardinality, with the right context, retained for the right window, surfaced where humans look.

## The three pillars (and the limits of that framing)

Metrics, logs, and traces are the standard taxonomy. Each is good at something:

- **Metrics** — cheap to store, fast to query, good for trends and SLOs and alerting. Bad at "why is *this specific request* slow?"
- **Logs** — high-fidelity per-event detail, expensive at scale, the place you go when metrics tell you something is wrong and you need to know what.
- **Traces** — the causal graph of a single request across services. Indispensable for distributed systems; the answer to "where did the time go?"

The pillars are not mutually exclusive — a modern stack correlates them. A trace ID in every log line lets you jump from a metric anomaly to the slow trace to the exact log lines. **Wide structured events** (the Honeycomb model) collapse logs and traces into a single high-cardinality store and are arguably the most useful primitive of the three; if you're starting fresh, give that model a serious look.

## OpenTelemetry is the default

Pick OpenTelemetry (OTel) for instrumentation. It's the vendor-neutral standard, supported everywhere, and saves you from per-vendor SDKs that go obsolete.

- **Auto-instrumentation** for popular frameworks (Express, FastAPI, Django, Flask, Spring, gRPC, net/http) gets you 80% of the way for free.
- **Manual instrumentation** for the business-logic spans that actually answer your questions — "render template", "compute eligibility", "publish event". One well-named span around a business operation is worth ten generic HTTP spans.
- **OTLP** is the wire protocol. Send to an **OTel Collector**, not directly to a vendor — the Collector lets you swap or fan out backends without touching app code.

## Metrics

### Instrument the four golden signals first

For every user-facing service:

- **Latency** — split successful vs failed. Use histograms, not gauges.
- **Traffic** — RPS, requests per minute, queue arrival rate.
- **Errors** — rate and ratio. Distinguish 4xx (client) from 5xx (server) — they mean different things.
- **Saturation** — how full is your most constrained resource? CPU, memory, DB connection pool, thread pool, queue depth.

For batch and async workloads, the equivalents are: queue depth, processing rate, failure rate, age of oldest unprocessed item.

### Histograms, not averages

Averages lie. A service with p50=10ms and p99=2s has the same average as one with p50=200ms and p99=300ms, but the user experience is wildly different. **Always export latency as a histogram** (Prometheus `histogram` or OTel `Histogram`). Query `histogram_quantile(0.99, ...)` for p99.

Default buckets are usually wrong for your service. If your normal latency is 1–50 ms, the default bucket boundaries (often 5ms, 10ms, 25ms, 50ms, 100ms, 250ms, 500ms, 1s, 2.5s, 5s, 10s) cluster signal in 1–2 buckets. Choose buckets that put your p50, p95, p99 in distinct buckets. Native histograms (Prometheus) and exponential histograms (OTel) eliminate this tuning if your stack supports them.

### Cardinality is your budget

Every unique combination of label values is a separate time series. A `user_id` label on a metric with 10M users is 10M time series. This will kill your TSDB.

Hard rules:

- Never label by user_id, request_id, trace_id, full URL, or anything user-supplied without bounded enumeration.
- Status code: yes. HTTP method: yes. Route template (`/users/:id`): yes. Full path (`/users/12345`): no.
- A useful sanity check: `count by (__name__) (...)` — if a single metric has more than ~10k series, investigate.

If you need high-cardinality slicing, that's a logs/traces job, not a metrics job. Use exemplars — Prometheus and OTel both support attaching a trace ID to a histogram bucket — to bridge.

### RED and USE

Two complementary frameworks, both worth applying:

- **RED** (Rate, Errors, Duration) — for **request-driven** services. What every API needs.
- **USE** (Utilization, Saturation, Errors) — for **resources** (CPU, memory, disk, queue, DB pool). What every infra component needs.

The combination tells you both "what's the user experiencing?" and "what's the system doing?"

## Structured logging

If you take one thing from this section: **logs are events, not strings.** Emit them as structured records (JSON or logfmt) with fields, not as concatenated text.

```json
{"ts":"2024-01-15T10:23:45Z","level":"info","msg":"order.created","order_id":"o_8f3","user_id":"u_412","amount_cents":1999,"trace_id":"4bf92f3577b34da6a3ce929d0e0e4736"}
```

Why this matters: you can later filter, group, or join on `user_id` or `order_id`. With unstructured logs (`"Order o_8f3 created for user u_412"`) you're reduced to regex archaeology.

### Log levels — actually apply them

- **ERROR** — something the service cannot recover from for this request, *and* a human should see it. This should page in aggregate.
- **WARN** — degraded but recovered: retry succeeded, fell back to cache. Useful as a rate signal.
- **INFO** — significant business events: a request handled, a job completed. Sampled or aggregated in high-volume services.
- **DEBUG** — detailed local state. Off by default in prod, opt-in per-request via a header.
- **TRACE** — extremely detailed; rarely on.

If everything is ERROR, nothing is. If your dashboard's error count is dominated by validation 400s, the noise will mask the real outages.

### What not to log

- **Secrets, tokens, full credit-card numbers, full SSNs.** Redact at the logger, not at the developer's discretion.
- **Full request/response bodies** by default. Sample, or log only on error.
- **PII without legal review.** Logs persist longer than you think; GDPR and friends apply.
- **`fmt.Println` / `print()` / `console.log` in production code.** Always go through the structured logger.

### Volume and cost

Logs at scale are expensive. Two levers:

- **Sampling** — keep all errors, sample 1-in-N successes. Tail-based sampling (decide *after* the trace completes whether to keep it) is much smarter than head-based for traces.
- **Tiered retention** — recent logs in hot/queryable storage (Loki, Elastic), older logs in object storage with slower access (S3 + Athena, or just gzipped). Most queries hit the last 24 hours.

A log line is ~1 KB. 10k RPS × 1 line per request × 86400 s/day ≈ 860 GB/day. Plan for it before the bill arrives.

## Distributed tracing

Tracing's superpower is showing you the *causal* shape of a request — what called what, in what order, taking how long, with what attributes. In a microservices system, that's the difference between "the API is slow" and "the API is slow because the auth service's DB is exhausting its connection pool when called with a particular tenant ID."

### Instrumentation guidance

- **Propagate context everywhere.** W3C Trace Context (`traceparent` header) is the standard. Auto-instrumentation handles HTTP/gRPC; you must handle queues, background jobs, and any custom RPC yourself.
- **Span the right things.** Every external call (HTTP, DB, cache, queue), every meaningful unit of business work. Don't span every function; you'll drown in noise.
- **Span attributes carry context.** `db.statement`, `http.route`, `messaging.destination`, your own `tenant_id`, `feature_flag.x.enabled`. Use OTel semantic conventions where they exist.
- **Errors on spans:** record exceptions on the span (`span.RecordError`) and set status, but don't pollute the trace tree with synthetic error spans.

### Sampling

You cannot trace 100% at scale. Sample:

- **Head-based** sampling (decide at the root) is simple and what most stacks default to. 1–10% baseline is typical.
- **Tail-based** sampling (collected at the OTel Collector, decide after the full trace arrives) lets you keep "interesting" traces — anything with an error, anything over a latency threshold — and sample the boring ones aggressively. Worth the operational complexity for high-volume services.

Always **keep all error traces** — those are the ones you'll look at.

## Wide structured events

The "fourth pillar" some teams skip the others for. Instead of separate metrics/logs/traces, emit one wide event per unit of work containing every dimension you care about: durations, status, user-tier, region, feature-flags, app version, db-query-count, etc.

```json
{"trace_id":"4bf...","span_id":"a1b...","name":"http.request","duration_ms":234,
 "http.status_code":200,"http.route":"/orders/:id","user.tier":"pro","db.query_count":12,
 "cache.hits":3,"cache.misses":1,"feature.new_pricer":true,"region":"us-east-1"}
```

You then do BI-style group/filter/aggregate on these events at query time, deriving metrics on the fly. Honeycomb popularized this; OTel logs/spans-as-events are the open-source path. The benefit is investigating *unknown unknowns*: you can ask a question you didn't define a metric for, six months after the fact.

## SLIs, SLOs, error budgets

Get this right and the rest of monitoring becomes coherent.

- **SLI** — a Service Level *Indicator*. A measurable thing: "fraction of HTTP requests that return 2xx/3xx within 200 ms."
- **SLO** — a Service Level *Objective*. A target on the SLI: "99.9% of requests over a rolling 30 days."
- **Error budget** — what you're allowed to fail. 99.9% over 30 days = 43.2 minutes of downtime budget. Spend it.

### How to choose SLIs

- **User-facing.** "What does the user experience?" If your SLI doesn't degrade when the user notices a problem, it's the wrong SLI.
- **Specific.** "Latency" isn't an SLI; "p95 latency of `GET /search` measured at the load balancer" is.
- **Few.** 3–5 SLOs per service is plenty. More than 10 and nobody pays attention.

### Burn-rate alerts beat threshold alerts

Don't alert "p99 > 200ms for 5 minutes." Alert on **error budget burn rate**:

- Fast burn (consuming 2% of monthly budget in an hour) → page now.
- Slow burn (consuming 10% of monthly budget over 3 days) → ticket, fix this week.

Multi-window, multi-burn-rate alerts (the SRE workbook pattern) are the gold standard. They catch fast outages quickly without paging on every transient blip.

## Alerting

Most paging fatigue is self-inflicted. The principles:

- **Alert on symptoms, not causes.** "User-facing latency is bad" is an alert. "CPU > 80%" is not — high CPU might be fine; the user-facing impact is what matters. Causes belong on dashboards, not in PagerDuty.
- **Every alert must be actionable.** If the on-call's response is "I dunno, let's see if it goes away," delete the alert.
- **Every alert needs a runbook link.** What does this mean? What are likely causes? What do I do? Maintain runbooks; they go stale.
- **Page on burning the error budget, not on individual metric thresholds.**
- **Tickets for slow-burn issues.** Not everything pages. A capacity warning at 3 AM is a Tuesday-morning ticket.
- **Maintenance windows** suppress alerts during planned work. Build the mechanism early.

### Alert hygiene checklist

- Owner clearly identified.
- Runbook link.
- Severity matches user impact.
- Tested in staging (synthetic failure verifies the alert fires).
- Auto-resolves when the condition clears.
- Reviewed quarterly — kill stale alerts.

## Dashboards

Two kinds. Don't conflate them.

- **Overview / health dashboard** — for at-a-glance "is this service OK?" One per service. The SLOs, the four golden signals, recent deploy markers. Five panels, no scrolling. The on-call's home page.
- **Investigation dashboard** — for digging in during an incident. Many panels, drill-downs, links to traces and logs. Built for breadth, not first-glance clarity.

Tips:

- **Annotate deploys.** A spike that lines up with a deploy is a different problem than one that doesn't. Almost every dashboard tool supports deploy annotations.
- **Use templating** (variables for service, environment, route) so one dashboard serves many.
- **Link out:** every metric panel should link to the relevant logs query and the relevant traces query, scoped to the same time range and labels. This is the highest-leverage thing you can do.

## Stack choices

Roughly grouped:

- **Open-source self-hosted, "cloud-native" flavor:** Prometheus + Grafana + Loki + Tempo (or Jaeger) + Alertmanager. OTel Collector to glue everything. Free, ubiquitous, you operate it. Sensible default if you have platform capacity.
- **Open-source-lite:** VictoriaMetrics (Prometheus-compatible, drastically lower resource cost at scale), ClickHouse for logs/traces, Grafana on top.
- **Commercial all-in-one:** Datadog, New Relic, Splunk, Honeycomb, Lightstep. You pay for the storage, scale, and UX. Datadog gives breadth; Honeycomb gives the wide-events model with a query UX nothing else matches; New Relic and Splunk dominate in enterprise.
- **Cloud-native:** CloudWatch / Cloud Logging / Azure Monitor — free with the platform, often weakest UX, fine as a starting point or for low-stakes services.

For most teams shipping on Kubernetes, the path is: OTel SDKs in apps → OTel Collector in cluster → metrics to Prometheus/VictoriaMetrics, logs to Loki, traces to Tempo, all visualized in Grafana. Add a commercial backend for the high-stakes service or for tracing if Tempo's UX feels limiting.

## Investigating an incident — the standard moves

1. **Look at the SLO dashboard first.** What changed and when?
2. **Correlate with deploys, feature flags, infra changes.** The annotation tracks usually answer "what changed."
3. **Drill from the symptom (RED) to the resource (USE).** Latency up → which dependency? DB? Cache? Network?
4. **Pivot to traces.** Find a representative slow trace. Read the span tree. Where's the time?
5. **Pivot to logs of the slow span.** Errors? Lock waits? Retries?
6. **Pivot to the dependency's metrics/logs.** Repeat as needed.

If you find yourself SSHing onto a box, *first* check whether the data you want is already in your telemetry stack. Most of the time it is.

## Anti-patterns to push back on

- **"We'll add observability later."** Adding it post-incident is when you most need it and least have it.
- **"More dashboards = more observability."** No — fewer, better dashboards beat 200 unmaintained ones.
- **High-cardinality labels on metrics.** Will eventually take down your TSDB.
- **`logger.error("something went wrong")`** — useless. Include the operation, the inputs (sanitized), the actual error.
- **Alerts for every condition you can think of.** Each alert added without removing one is a step toward fatigue.
- **Throwing telemetry into separate, uncorrelated stores.** If you can't go from a metric to a trace to a log in two clicks, you're going to investigate by guessing.
- **Tracing only the happy path.** Errors should always be sampled in.
- **`time.Now()` everywhere instead of histograms.** That's not metrics, that's vibes.

## Quick checklist for a "production-ready" service

- Structured logs to stdout, with trace_id on every line.
- RED metrics exported (latency histogram, RPS, error rate).
- USE metrics for the resources you depend on (or for your runtime: GC, goroutines, threads, FD count).
- Distributed tracing on, with context propagation through every transport.
- 3–5 SLOs defined, with multi-burn-rate alerts.
- One health dashboard per service, one investigation dashboard.
- Alerts page only on user-impacting symptoms, each with a runbook.
- Telemetry retention sized for at least 14–30 days for logs and metrics, sampled traces longer for known-bad cases.
- Costs reviewed monthly. (Logs are usually the surprise.)
