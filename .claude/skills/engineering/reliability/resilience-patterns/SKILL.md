---
name: resilience-patterns
description: Use this skill any time the user is designing, implementing, or debugging behavior under failure — including timeouts, retries, backoff, jitter, circuit breakers, bulkheads, rate limiting, load shedding, idempotency, graceful degradation, fallbacks, queues and back-pressure, deadlines, the saga pattern, dead-letter queues, or chaos engineering. Trigger on phrases like "what if X is down", "should I retry", "this is timing out", "we got a thundering herd", "cascading failure", "exponential backoff", "circuit breaker", "is this idempotent", or when reviewing code that calls a remote system without obvious failure handling. Also trigger when the user asks "how do I make this reliable" — that's almost always a resilience-patterns question.
---

# Resilience Patterns

Distributed systems fail. The network is unreliable, dependencies misbehave, machines die, deploys roll out half-broken, traffic spikes, clocks drift. Resilience isn't avoiding failure — it's designing the system to absorb it gracefully.

The core insight: **you cannot make calls to remote systems reliable. You can only make your service's response to their failures predictable.** Every remote call is a place where a failure mode can leak into your system. The patterns here are the toolkit for putting boundaries around those failure modes.

## The mindset

- **Assume every dependency will fail.** Not "could." *Will.* Plan for it.
- **Latency is a failure mode.** A call that takes 30 seconds is worse than one that fails fast — it ties up resources and cascades.
- **Failures love to be correlated.** When one thing breaks, lots of things break together. Patterns that protect against one isolated failure may collapse under correlated failure.
- **The remedy can be worse than the disease.** Naive retries cause thundering herds. Naive failovers cause split-brain. Every pattern below has a failure mode of its own.
- **Test the failure path.** Code that's never been exercised is broken; the failure path is the most-untested code in the system. Inject failures and watch what happens.

## Timeouts — the foundation

Without timeouts, nothing else matters. A request without a timeout is a resource leak waiting to happen.

- **Every remote call has a timeout.** HTTP, RPC, DB, cache, queue, DNS. Yes, DNS — `getaddrinfo` blocks the calling thread.
- **Timeouts cascade upward.** If service A's timeout to B is 30s, but A's caller has a 5s budget, A is going to be holding the bag while its caller has already given up. Use **deadlines** propagated from the inbound request, not fixed timeouts.
- **Connection vs. read vs. total.** Most clients let you set these separately. Total/request-deadline is the one that matters most; connect timeout should be small (1–2 s) so you fail fast on a dead host.
- **The default is wrong.** Many SDKs default to "infinite" or "5 minutes." Set timeouts explicitly, every time.

In Go, propagate `context.Context` everywhere; it carries the deadline. In Python's async stack, use `asyncio.wait_for` or pass timeouts; in Django/requests use `timeout=(connect, read)`. In gRPC, use deadlines, not timeouts (they propagate over the wire).

## Retries — useful, but loaded

Retries fix transient failures. They also amplify outages. The rules:

- **Only retry idempotent operations**, or operations explicitly designed to be retryable. POST creating a payment is *not* safe to retry without an idempotency key. GET, PUT, DELETE are typically safe; POST is not unless you've done the work.
- **Retry only on retryable errors.** 5xx (sometimes), connection reset, timeout — yes. 4xx — no, the client is wrong; retrying won't fix it. 401/403 — no. 429 — yes, but respect `Retry-After`.
- **Exponential backoff with jitter.** Without jitter, all retrying clients synchronize and hammer the recovering server in lockstep — the thundering herd. With "full jitter" (`sleep = random_between(0, base * 2^attempt)`) you spread retries out.
- **Bounded.** Cap attempts (3 is often plenty) and cap total elapsed time. Better to fail fast and let the upstream caller's own retry handle it than to retry for 60 seconds while connections pile up.
- **Retry budgets.** A more sophisticated pattern: track the ratio of retries to original requests; if it exceeds (say) 10%, *stop retrying*. The dependency is having a bad time and you're making it worse.

```python
# Sketch in Python with `tenacity`
from tenacity import retry, wait_random_exponential, stop_after_attempt, retry_if_exception_type

@retry(
    wait=wait_random_exponential(multiplier=0.1, max=2.0),  # full jitter
    stop=stop_after_attempt(3),
    retry=retry_if_exception_type((ConnectionError, TimeoutError)),
    reraise=True,
)
def fetch_inventory(sku: str) -> Inventory:
    ...
```

```go
// Sketch in Go with a small loop
for attempt := 0; attempt < maxAttempts; attempt++ {
    res, err := callOnce(ctx)
    if err == nil { return res, nil }
    if !isRetryable(err) { return nil, err }
    if ctx.Err() != nil { return nil, ctx.Err() } // deadline exceeded
    backoff := time.Duration(rand.Int63n(int64(base * (1 << attempt))))
    select {
    case <-time.After(backoff):
    case <-ctx.Done(): return nil, ctx.Err()
    }
}
```

## Idempotency

If retries are a hammer, idempotency is the nail's strength. An operation is idempotent if applying it twice has the same effect as applying it once.

- **For HTTP APIs that mutate state**, accept an `Idempotency-Key` header (UUID supplied by the client). Server-side: store `(key, response)` for some TTL (24h typical). On a retry with the same key, return the stored response without re-executing.
- **For queue consumers**, design for at-least-once delivery: every message handler must be idempotent. Use a dedup table keyed by message ID, or design the operation to be naturally idempotent (`SET x = 5` is, `INCREMENT x` is not).
- **For database writes**, prefer `INSERT ... ON CONFLICT DO NOTHING/UPDATE` (Postgres) or `MERGE` semantics over read-modify-write loops.
- **For external side effects** (charging cards, sending emails), keep an outbox or a dedup record so a crash mid-flight doesn't cause a double-charge.

Saying "we have at-least-once delivery and idempotent consumers" is shipping. Saying "we have exactly-once" is, in 99% of cases, a misunderstanding.

## Circuit breakers

A circuit breaker wraps a remote call. When failures exceed a threshold, it *opens* — calls fail fast without hitting the dependency, for a cooldown window. Then it *half-opens* — lets a few calls through to test recovery — and *closes* if those succeed.

- **The point isn't to protect the dependency** (rate limiting does that). It's to **protect the caller** from spending its threads, connections, and request budget on a known-broken dependency.
- **The threshold matters.** "Open after 50% failures over the last 20 requests" is a reasonable starting heuristic. Pure absolute counts cause flapping.
- **Per-dependency, sometimes per-endpoint.** One slow endpoint shouldn't open the breaker for everything that hits the same host.
- **Visibility.** The breaker's state must be a metric. An open breaker that nobody knows about is just a silent outage.

Libraries: `resilience4j` (JVM), `gobreaker` or `sony/gobreaker` (Go), `pybreaker` (Python). Service meshes (Istio, Linkerd) and platforms (Envoy) provide breakers at the proxy layer — often a better place to put them, since policy is centralized.

## Bulkheads

The metaphor is a ship's hull: compartments so a leak in one doesn't sink the whole vessel.

- **Separate connection pools per dependency.** If service A and service B share a single HTTP connection pool of 100, a slowdown in B can starve A. Two pools of 50 each isolate the damage.
- **Separate thread/worker pools per concern.** "Webhook delivery" and "user requests" should not be in the same pool — a spike of slow webhooks shouldn't degrade user requests.
- **Separate hosts/clusters for different tenants** in a multi-tenant system, when one tenant's bad day shouldn't affect others. (Costly; reserved for the most critical isolation.)

## Rate limiting and load shedding

Two related but distinct things:

- **Rate limiting** — refuse traffic above a contract. Per-API-key, per-IP, per-tenant. Token bucket or leaky bucket. Returns 429 with `Retry-After`. Defends *the dependency* (often you).
- **Load shedding** — refuse traffic to *protect yourself* when overloaded. The trigger is your own saturation (CPU, queue depth, p99 latency), not a per-tenant quota. Drop the lowest-priority traffic first.

Both should return responses fast. The worst thing you can do under load is queue work indefinitely — slow responses tie up upstream resources and make the problem worse. Fail fast is a form of mercy.

A useful pattern: **adaptive concurrency limits.** Pick a starting concurrency, watch latency. If latency degrades, lower the limit. If latency is healthy, raise it. Netflix's `concurrency-limits` library is the canonical implementation.

## Back-pressure

In a pipeline (producer → queue → consumer), back-pressure is what tells the producer to slow down when the consumer can't keep up. Without it, queues grow unbounded → memory exhaustion → crash.

- **Bounded queues.** Always. An "unbounded" queue is a memory leak that hasn't happened yet.
- **Reject vs. block at full.** A bounded queue that *blocks* the producer is back-pressure (the producer feels the slowdown). One that *rejects* (and surfaces the error to the caller) is also back-pressure, of a different shape. Both are fine; "silently drop" is not.
- **Async I/O frameworks** (Go channels with capacity, asyncio with `Queue(maxsize=N)`, reactive streams) make this explicit. Use it.

## Graceful degradation and fallbacks

When a non-essential dependency fails, the right answer is often "carry on without it."

- **Recommendation engine down?** Show a default carousel.
- **Avatars service down?** Show initials.
- **Search service down?** Fall back to a cached or simplified result set.
- **Personalization service down?** Serve the unpersonalized page.

The discipline is to design the degraded path *deliberately*. Fallbacks that trigger only in incidents are the ones nobody tested. Make the degraded path a regular part of the system — periodic forced degradation, feature-flag-gated — so it's exercised.

A fallback that calls another remote service is a fallback that can also fail. Each layer of fallback is more code, more failure modes. Two layers is usually plenty; beyond that, default to a static response.

## Cache as a resilience tool

A cache isn't just a perf trick; it's a resilience layer.

- **Stale-while-revalidate.** Serve stale on a hit, refresh in the background. If the origin is down, you serve stale longer rather than failing.
- **Negative caching.** Cache "not found" / "error" responses for a short window so a flood of misses doesn't hammer the origin. Watch out for caching sensitive errors longer than they're true.
- **Singleflight / request coalescing.** When 1000 requests for the same key arrive simultaneously and the cache is cold, send *one* request to the origin and let the others wait on the result. (`golang.org/x/sync/singleflight`, `coalesce` in some Python caches.) Prevents cache stampedes.

## Saga / compensating transactions

For multi-step distributed transactions, two-phase commit is generally not available across heterogeneous services. The saga pattern is the practical alternative:

- Each step has a forward action and a compensating action ("reserve seat" / "release seat", "charge card" / "refund card").
- Run forward actions in order; if one fails, run the compensating actions for completed steps in reverse.
- Make every step idempotent and persist saga state (so a crash mid-saga can resume).
- A saga orchestrator (Temporal, AWS Step Functions, custom code over a state table) is much easier to operate than a choreography of events for non-trivial flows.

Sagas work; they require care. Plan for compensations to fail too — what's the human-intervention runbook?

## Dead-letter queues and poison messages

In any queue-driven system, some messages will be poison — they fail every time you retry. Without a DLQ, they back up the queue and starve healthy traffic.

- After N retries (typically 3–5), move the message to a **dead-letter queue**.
- Alert on DLQ depth. Don't let it silently fill.
- Build tooling to inspect, fix, and replay DLQ messages.
- Tag with the original error so root cause is obvious.

## Rolling deploys and the failure model they create

Half your fleet is on the new code, half on the old, for some window. Patterns:

- **Backwards-compatible schemas.** Don't drop a column or change a field type in the same deploy that starts using the new shape. Two-deploy migrations: (1) add the new field, write to both, read from old; (2) read from new, stop writing old; (3) drop old.
- **Feature flags.** Deploy code dark, flag-gate the new behavior, ramp the flag at a time decoupled from the deploy.
- **Health checks gate the rollout.** A pod that fails readiness shouldn't get traffic; a deploy that fails health checks should auto-rollback (or at least pause).

These aren't "deploys are scary" — they're "your code lives in two versions for a while, and you need to handle that explicitly."

## Chaos engineering

The discipline of injecting failure on purpose to verify the system handles it.

- **Game days** — scheduled exercises where the team takes down a dependency in staging (or, when mature, prod) and watches what happens.
- **Continuous fault injection** — tools like Chaos Mesh, Litmus, or AWS Fault Injection Simulator that run regular experiments.
- **The point isn't breaking things.** It's *verifying that what you believe about your system is true.* Beliefs that don't survive a chaos experiment were lies anyway.

Start small. "What happens if the cache is unreachable for 60 seconds?" is a good first experiment. Don't run experiments without a kill switch, and don't run them when you're already on fire.

## Patterns specific to common technologies

- **HTTP clients:** always set timeout; always set max-conns-per-host; pool reuse is on by default in most clients but disabled by some (`requests.get` per-call creates a new connection).
- **Database connection pools:** size based on workers × concurrency, not by guessing. Max connections at the DB sets a hard ceiling on the *sum* of pool sizes across all instances. Hitting that ceiling means new connections fail; bound and tune.
- **gRPC:** use deadlines, not timeouts; enable keepalive on long-lived connections; configure client-side load balancing (round-robin or weighted) when you have many backends.
- **Kafka/SQS/Pub/Sub:** consumer must be idempotent (at-least-once is the only realistic guarantee); long-running handlers should heartbeat / extend visibility timeout to avoid duplicate delivery.

## Anti-patterns to push back on

- **No timeouts** anywhere. The most common, most damaging gap.
- **Retries with no backoff or jitter.** Synchronizes thundering herds; turns a blip into an outage.
- **Retries on POST without idempotency keys.** Creates ghost orders, duplicate charges.
- **`if err != nil { time.Sleep(1*time.Second); continue }`-style infinite retry loops.** Cap attempts. Cap time. Surface the error eventually.
- **A single shared connection pool for all destinations.** No bulkheading; one bad neighbor poisons everything.
- **Health checks that call downstream dependencies.** A DB blip cascades into mass restarts. Liveness should reflect *this process*, not the world.
- **"Just add a retry"** as the default fix to a flaky integration. The retry hides the underlying instability and increases the bill.
- **Unbounded queues.** Replace with bounded queues + back-pressure.
- **Caches with no TTL and no invalidation strategy.** Stale data forever; correctness bugs that surface weeks later.
- **Fallbacks that have never run in production.** Untested code; will not work when needed.

## A short checklist when reviewing a remote call site

- Is there a timeout, set explicitly, propagated from the caller's deadline?
- Is the operation idempotent? If retried, would the world be wrong?
- If yes (idempotent), is there bounded, jittered retry?
- What happens when this fails? (A specific answer — exception, fallback, error response — not "uhh.")
- Is the error rate / latency observable? (Metrics, traces, logs at the call site.)
- Is there a circuit breaker or equivalent for repeated-failure mode?
- Is the connection pool sized and isolated from unrelated traffic?
- If this dependency is gone for an hour, what does the user experience look like? Acceptable?

If the answer to any of these is "I don't know," that's the work item.
