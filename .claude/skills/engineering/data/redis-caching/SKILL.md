---
name: redis-caching
description: Use this skill for any work involving Redis or Redis-compatible stores (Valkey, KeyDB, Dragonfly, Upstash, ElastiCache, MemoryDB, Azure Cache for Redis) — caching strategies (cache-aside, write-through, write-behind), TTLs, eviction policies (`allkeys-lru`, `volatile-ttl`), key design, data structures (strings, hashes, sets, sorted sets, streams, HyperLogLog, bitmaps, geo), pub/sub, Redis Streams, distributed locks, rate limiting (token bucket, sliding window), session stores, idempotency keys, leaderboards, queues, Lua scripts, pipelining, transactions (`MULTI`/`EXEC`/`WATCH`), persistence (RDB/AOF), replication, Sentinel, Cluster, sharding, hot keys, big keys, memory tuning, cache stampedes, and the licensing landscape (Redis 7.4+ source-available vs Valkey/KeyDB BSD forks).
---

# Redis & Caching

A Redis is a fast, in-memory data structure server you can talk to over the network. The default temptation is to think of it as "a cache" and stop there. That's underselling it: Redis is a small, fast database with rich primitives — sorted sets, streams, atomic counters, pub/sub — that solve specific problems no relational DB solves cleanly. The skill is in (a) using the right primitive for the problem, and (b) caching well, because most caching bugs are subtle and most people get them wrong.

## The licensing landscape (2026 context)

In 2024 Redis Inc. relicensed Redis 7.4+ to a source-available license (RSAL/SSPL dual), prompting the community to fork. The Linux Foundation backed **Valkey**, which is the BSD-licensed continuation most clouds and distros now ship by default (AWS ElastiCache and MemoryDB offer Valkey; Azure Cache for Redis remained Redis through Microsoft's separate agreement). **KeyDB** (multithreaded) and **Dragonfly** (different architecture, Redis-compatible wire protocol) are also viable.

For new projects: **Valkey is the safest default** unless you specifically need a Redis Inc. enterprise feature. The wire protocol and command set are compatible. Code in this document calls "Redis" but applies to all of them.

## When Redis is the right answer

| Problem | Redis primitive |
|---|---|
| Cache for expensive computations or DB reads | String + TTL |
| Session store | Hash + TTL |
| Rate limiting | Sorted set or counter + Lua |
| Distributed lock | `SET NX PX` + token, or Redlock for multi-node |
| Idempotency key | `SET NX EX` |
| Leaderboard / top-N by score | Sorted set (ZSET) |
| Job queue (simple) | List with `BLPOP` |
| Job queue (durable, fanout) | Streams (`XADD`/`XREADGROUP`) |
| Pub/sub fanout (no durability) | `PUBLISH`/`SUBSCRIBE` |
| Unique counter (approximate) | HyperLogLog |
| Feature flags / boolean grids | Bitmaps |
| Geo radius search | Geo (built on ZSET) |
| Token bucket | String + Lua, or `INCR` + `EXPIRE` |

When Redis is **not** the right answer:

- You need durability with the same guarantees as a relational DB. Redis can be configured durably, but it's not a replacement for Postgres.
- The dataset doesn't fit in RAM. It's an in-memory store — RAM is the size limit, not disk.
- You need rich querying (joins, secondary indexes on arbitrary fields). Use a real database.
- Long-term log retention. Streams have caps; for analytics, ship to a real warehouse.

## Caching: the core patterns

### Cache-aside (lazy loading) — the default

```
1. Read from cache.
2. Hit?  Return.
3. Miss? Read from source of truth, write to cache (with TTL), return.
```

```python
def get_student(id: str) -> Student:
    key = f"student:{id}"
    cached = redis.get(key)
    if cached:
        return Student.model_validate_json(cached)
    student = db.fetch_student(id)
    if student:
        redis.set(key, student.model_dump_json(), ex=300)  # 5 min TTL
    return student
```

This is the right default. It's simple, the cache is optional (you can survive Redis being down), and the source of truth is unambiguous: the database.

The catch: invalidation. After an update, the cache is stale until TTL expires. Two options:

- **Live with TTL staleness** if eventual consistency is acceptable. Often it is.
- **Invalidate on write** — on update, `DEL student:{id}`. Don't try to update the cache value on write; re-derive it on next read.

### Write-through

Application writes to cache, cache writes to DB synchronously, then returns. Strong consistency between cache and DB. Slower writes; cache is always populated.

Useful when reads vastly outnumber writes and write latency isn't critical. Less useful than people think because it requires the cache to know how to talk to the DB.

### Write-behind (write-back)

Application writes to cache, returns. A background process flushes to the DB asynchronously. Fast writes, risk of data loss on Redis failure.

Use sparingly. For cases where the source of truth genuinely is the cache (Redis with AOF persistence) and the DB is just for offline analytics — fine. For cases where the DB is the source of truth, this is a footgun.

### Read-through

The cache itself fetches from the DB on miss. Requires a cache that supports it (some Redis modules / caching libraries do). Less common in Redis deployments — usually cache-aside in app code.

## TTLs and eviction

**Always set a TTL.** A key without a TTL is a key that lives until you remember to delete it, or until you hit `maxmemory` and start evicting unpredictably.

```bash
SET student:42 "..." EX 300        # 5 minutes
EXPIRE student:42 300              # set TTL on existing key
TTL student:42                     # check remaining
PERSIST student:42                 # remove TTL (rarely the right call)
```

`maxmemory-policy` determines what happens when memory fills:

| Policy | Behavior |
|---|---|
| `noeviction` | Reject writes. Default for some setups. Not what you want for a cache. |
| `allkeys-lru` | Evict least-recently-used keys. The classic cache choice. |
| `allkeys-lfu` | Evict least-frequently-used. Better when access patterns are skewed and recency lies. |
| `volatile-lru` / `volatile-lfu` | Same, but only evict keys with a TTL. |
| `volatile-ttl` | Evict shortest-TTL first. |
| `allkeys-random` | Random. Cheap, sometimes appropriate when access is uniform. |

For a pure cache: **`allkeys-lru` or `allkeys-lfu`**. Set `maxmemory` to ~75% of available memory to leave headroom for COW during BGSAVE.

For a mixed store (sessions + cache + state): **`volatile-lru`** so non-TTL keys (sessions you want to keep until logout) stick around, and only cache-style keys (which all have TTLs) evict.

## Key design

Keys are flat strings. Treat them like a namespace:

```
student:{id}                       # primary entity
student:{id}:enrollments           # related collection
session:{token}                    # session
ratelimit:{user_id}:{endpoint}     # rate limit bucket
lock:resource:{id}                 # distributed lock
```

Conventions worth following:

- **Colon-delimited segments**, prefix-first. Tooling expects this.
- **Predictable, not opaque.** You'll want to `SCAN MATCH student:*` someday.
- **Versioned schema.** When you change the shape of a cached value, change the key prefix (`student_v2:{id}`) so you don't try to deserialize old data with new code. Old keys age out via TTL.
- **No spaces, no PII you don't want logged.** Slow-query logs and monitoring will show keys.
- **Reasonable length.** Keys are stored in memory too. `student:42` not `university_student_record_with_full_details:42`.

## Data structures (the actually useful tour)

### Strings — caching, counters, locks

```bash
SET key value EX 300
GET key
INCR counter
DECRBY counter 5
SET lock:thing token NX PX 30000   # NX = only if not exists, PX = ms TTL
```

`INCR`/`INCRBY` are atomic, which makes Redis the easiest counter you'll ever build.

### Hashes — record-shaped data

```bash
HSET student:42 name "Alice" gpa 3.8 year 3
HGET student:42 name
HGETALL student:42
HINCRBY student:42 enrollment_count 1
```

Use a hash when you want to update individual fields without serializing the whole record. For session data, profile data, anything record-shaped, hashes beat JSON-blobbed strings.

### Sets — uniqueness, membership

```bash
SADD course:cs101:students 42 43 44
SISMEMBER course:cs101:students 42
SCARD course:cs101:students
SINTER course:cs101:students course:math201:students
```

Set operations (`SINTER`, `SUNION`, `SDIFF`) are atomic and fast. Useful for "students in both courses," "tags applied to anything," etc.

### Sorted sets — leaderboards, time-ordered queues, priority queues

```bash
ZADD leaderboard 95.5 alice 87.0 bob 92.3 carol
ZRANGE leaderboard 0 9 REV WITHSCORES        # top 10
ZRANGEBYSCORE leaderboard 90 100             # range query
ZINCRBY leaderboard 1.5 alice
ZRANK leaderboard alice                      # rank
```

The most powerful primitive Redis ships. Score-ordered, O(log N) ops, rich query language. Use it for:

- Leaderboards, ranked lists.
- Scheduled jobs (score = unix timestamp; pop where score ≤ now).
- Sliding-window rate limiters (score = timestamp, ZREMRANGEBYSCORE for old, ZCARD for current count).
- Top-N anything.

### Streams — durable logs, fanout queues with consumer groups

```bash
XADD events * type signup user_id 42
XREADGROUP GROUP processors worker1 COUNT 10 STREAMS events >
XACK events processors 1729...
```

Streams replaced pub/sub for any case where you actually want delivery guarantees. They're durable, support consumer groups (load balancing across workers), allow replay from any point, and have built-in pending-entry tracking for at-least-once processing.

For job queues with retry/durability/observability, prefer Streams over List+`BLPOP` for any new system.

### Lists — simple FIFO queues

```bash
LPUSH queue:emails "{...}"
BRPOP queue:emails 0    # blocking pop, 0 = wait forever
```

Quick to set up, no durability, no consumer groups. Fine for "hand a job to a worker, fire and forget." Outgrown quickly in production. For real job queues use Streams or a higher-level system (Sidekiq, BullMQ, RQ, Celery with Redis backend).

### Pub/Sub

```bash
SUBSCRIBE channel
PUBLISH channel "message"
```

**Fire-and-forget broadcast.** A subscriber not connected when you publish never gets the message. There's no replay, no durability, no per-subscriber ack. Use cases:

- Cache invalidation broadcast across app servers.
- Real-time notifications where missing one doesn't matter.
- Internal coordination where loss is acceptable.

For anything that must not be lost: Streams.

## Cache stampedes

The pattern: a popular key expires; 1,000 requests all hit the cache, all miss, all hit the DB simultaneously. The DB falls over. This is also called the "thundering herd" or "dog-pile" problem.

Fixes, ranked by elegance:

### 1. Probabilistic early expiration (XFetch)

Before TTL strictly expires, randomly start refreshing some requests early so the renewal load is spread out. Algorithm:

```
ttl_remaining = redis.ttl(key)
if ttl_remaining < beta * delta * ln(random())   # XFetch formula
    refresh_async()
return cached_value
```

Practical and elegant. Most real-world implementations are simpler approximations.

### 2. Lock-on-miss (single-flight)

Only one process refreshes; others wait briefly and re-read the cache.

```python
def get_with_lock(key, fetch):
    val = redis.get(key)
    if val: return val
    lock_key = f"lock:{key}"
    if redis.set(lock_key, "1", nx=True, ex=10):
        try:
            val = fetch()
            redis.set(key, val, ex=300)
            return val
        finally:
            redis.delete(lock_key)
    else:
        time.sleep(0.05)
        return redis.get(key) or fetch()  # fallback
```

Bulletproof but adds latency for the losers of the lock.

### 3. Stale-while-revalidate

Serve stale cache for a short window after expiry while a background task refreshes. Common in HTTP caching; works well in Redis if you store `(value, hard_expiry)` and let TTL be longer than logical expiry.

### 4. Don't all expire at once

If you cache 10,000 items at the same time (e.g., warming the cache), they'll all expire simultaneously. Add jitter: `ex=300 + random(0, 60)`.

## Distributed locks

The simple case (single-Redis):

```bash
SET lock:resource:42 <unique_token> NX PX 30000
```

`NX` = only if not exists. `PX 30000` = 30 second TTL. If you got `OK`, you have the lock. To release, **only delete if you still own it** — use a Lua script that checks the value matches your token:

```lua
if redis.call("GET", KEYS[1]) == ARGV[1] then
    return redis.call("DEL", KEYS[1])
else
    return 0
end
```

If you skip the check-and-delete, you can release a lock someone else acquired after yours expired.

Critical caveats:

- **Locks are not safe across Redis failover** with the simple pattern. If the master holding your lock fails before replicating to a replica, the replica is promoted, and someone else can take "your" lock.
- **Lock duration must exceed the work duration**, or you'll lose your lock mid-work and someone else will start. Pick TTLs generously, or implement lock extension (heartbeat).
- **Redlock** (Antirez's algorithm using N independent Redis nodes) addresses some of this, but Martin Kleppmann's analysis showed it's not safe under all GC/network assumptions. For correctness-critical locking, Redis is rarely the right tool — use Postgres advisory locks, Zookeeper, or etcd.
- For "best-effort" coordination (avoid duplicate work most of the time), a Redis lock is fine. For "guarantee mutual exclusion always," it isn't.

## Rate limiting

### Fixed window (cheapest, has burst issue)

```python
def check_fixed_window(user_id: str, limit: int, window_s: int) -> bool:
    key = f"rl:{user_id}:{int(time.time() // window_s)}"
    count = redis.incr(key)
    if count == 1:
        redis.expire(key, window_s)
    return count <= limit
```

Edge problem: a user can do `limit` requests in the last second of one window and `limit` more in the first second of the next.

### Sliding window via sorted set (most accurate)

```python
def check_sliding(user_id: str, limit: int, window_s: int) -> bool:
    key = f"rl:{user_id}"
    now_ms = int(time.time() * 1000)
    cutoff = now_ms - window_s * 1000
    pipe = redis.pipeline()
    pipe.zremrangebyscore(key, 0, cutoff)
    pipe.zadd(key, {f"{now_ms}-{uuid4()}": now_ms})
    pipe.zcard(key)
    pipe.expire(key, window_s)
    _, _, count, _ = pipe.execute()
    return count <= limit
```

Memory cost is O(requests in window) per user. Fine for low-volume rate limits, expensive for very high.

### Token bucket via Lua

The accurate and efficient choice for high-volume rate limiting. One Lua script per check, atomic.

```lua
-- KEYS[1] = bucket key
-- ARGV[1] = capacity, ARGV[2] = refill rate per ms, ARGV[3] = now ms, ARGV[4] = cost
local bucket = redis.call("HMGET", KEYS[1], "tokens", "ts")
local tokens = tonumber(bucket[1]) or tonumber(ARGV[1])
local ts = tonumber(bucket[2]) or tonumber(ARGV[3])
local elapsed = math.max(0, tonumber(ARGV[3]) - ts)
tokens = math.min(tonumber(ARGV[1]), tokens + elapsed * tonumber(ARGV[2]))
local allowed = tokens >= tonumber(ARGV[4])
if allowed then tokens = tokens - tonumber(ARGV[4]) end
redis.call("HMSET", KEYS[1], "tokens", tokens, "ts", ARGV[3])
redis.call("EXPIRE", KEYS[1], 3600)
return allowed and 1 or 0
```

For most applications, use a library (`redis-cell` module, `node-rate-limiter-flexible`, `slowapi`) instead of writing this yourself.

## Idempotency keys

```python
def process_payment(idempotency_key: str, amount: int) -> dict:
    key = f"idem:payment:{idempotency_key}"
    cached = redis.get(key)
    if cached:
        return json.loads(cached)

    # Reserve the key first to prevent races
    if not redis.set(f"{key}:lock", "1", nx=True, ex=30):
        # Someone else is processing the same key
        time.sleep(0.1)
        return json.loads(redis.get(key) or "{}")

    result = charge_card(amount)
    redis.set(key, json.dumps(result), ex=86400)  # remember for 24h
    redis.delete(f"{key}:lock")
    return result
```

The point: for any operation a client may retry (network blip, timeout-and-retry pattern), accept an idempotency key from the client and remember the result long enough to cover plausible retries.

## Pipelining and transactions

### Pipelining — batched round trips

```python
pipe = redis.pipeline()
pipe.get("a")
pipe.get("b")
pipe.get("c")
results = pipe.execute()
```

This sends all three commands in one network round trip. **Pipelining is not a transaction** — commands aren't atomic together; other clients can interleave. Pure latency optimization.

If you're doing more than 2-3 commands per request and they don't depend on each other, pipeline them. Easy 5-10x speedup.

### Transactions — `MULTI`/`EXEC`

```bash
MULTI
INCR counter:a
INCR counter:b
EXEC
```

All commands queued and executed atomically as a unit. **No rollback** — if a command fails at runtime (wrong type), the others still run. Rollback isn't a Redis concept.

### `WATCH` for optimistic concurrency

```python
with redis.pipeline() as pipe:
    while True:
        try:
            pipe.watch("balance:42")
            current = int(pipe.get("balance:42"))
            if current < 10: raise InsufficientFunds()
            pipe.multi()
            pipe.decrby("balance:42", 10)
            pipe.execute()
            break
        except WatchError:
            continue   # retry
```

`WATCH` aborts the transaction if the watched key changed. Compare-and-swap loop.

For truly atomic read-modify-write logic, **Lua scripts are usually cleaner.** Single round trip, atomic by definition.

## Lua scripting

```python
INCR_IF_LESS = """
local v = tonumber(redis.call("GET", KEYS[1]) or "0")
if v < tonumber(ARGV[1]) then
    return redis.call("INCR", KEYS[1])
end
return -1
"""
script = redis.register_script(INCR_IF_LESS)
result = script(keys=["counter"], args=[100])
```

Lua scripts run atomically (no other commands interleave). They're the right tool when:

- You need a multi-step atomic operation that `MULTI`/`EXEC` can't express (because step 2 depends on step 1's value).
- You want to reduce round-trip count for a complex operation.

Don't run slow Lua scripts. They block the entire Redis instance — Redis is single-threaded for command execution. Keep scripts short.

## Persistence

Two mechanisms:

- **RDB** — periodic point-in-time snapshots. Compact, fast restart, **loses data between snapshots**.
- **AOF** — append-only log of every write. With `fsync everysec`, you lose at most 1 second on crash. Slower writes, larger files, slightly slower restart.

For a pure cache: **no persistence needed** (or RDB only). On restart, the cache rebuilds.

For Redis as a primary store (sessions, queue state, anything you can't lose): **AOF with `everysec`**, plus replication, plus periodic RDB for backup.

`save ""` disables RDB snapshots if you don't want them. `appendonly yes` enables AOF.

## Replication, Sentinel, Cluster

| Setup | When |
|---|---|
| Single node | Dev, low-traffic, non-critical caches. Simplest. |
| Master + replicas | Read scaling, basic HA via promotion. |
| **Sentinel** | Automatic failover. Sentinels watch master, promote replica if it dies. Single logical master. |
| **Cluster** | Sharding. 16,384 hash slots distributed across nodes. Required when data exceeds one machine's RAM. |

Cluster constraints worth knowing:

- Multi-key commands (`MGET a b c`) only work if all keys hash to the same slot. Use **hash tags**: `student:{42}:profile` and `student:{42}:enrollments` both hash on `42`, land on the same slot.
- Lua scripts must declare keys; all keys in a script must be in the same slot.
- Transactions (`MULTI`/`EXEC`) — same constraint.

For most teams: managed Redis (ElastiCache, MemoryDB, Upstash, Azure Cache for Redis) and let the provider handle Sentinel/Cluster. Self-hosting is fine if you have ops capacity, expensive in mistakes if you don't.

## Hot keys and big keys

### Hot keys

A single key receiving disproportionate traffic. Symptoms: one shard CPU-pegged while others are idle.

Detection: `redis-cli --hotkeys` (uses LFU). In production, instrument the client side — track per-key access counts in your app, sample.

Mitigation:

- **Local in-process cache** in front of Redis for hot reads. Even 1-second TTL on a 10k-rps key turns 10k Redis calls into a handful.
- **Read replicas** + read-from-replica for that key.
- **Shard the key** — split a hot counter into N counters, sum on read.

### Big keys

A single key with disproportionate memory or operation cost. A 1GB hash, a 10M-element list. Symptoms: slow `DEL` (blocking), slow replication, slow snapshots.

Detection: `redis-cli --bigkeys`. `MEMORY USAGE key`.

Mitigation:

- **Don't build them.** Cap collection sizes; shard by some hash.
- **`UNLINK`** instead of `DEL` for large keys (async deletion).
- **Iterate, don't `HGETALL`** — `HSCAN`, `SSCAN`, `ZSCAN` for large structures.

## Memory tuning

`INFO memory` is your friend. Key metrics:

- `used_memory` — what Redis thinks it's using.
- `used_memory_rss` — what the OS thinks. RSS / used_memory = fragmentation ratio. > 1.5 is a yellow flag.
- `mem_fragmentation_ratio` — same idea. `activedefrag yes` helps.
- `maxmemory` and `maxmemory_policy` — set both deliberately.

Memory-efficient choices:

- Use hashes with small fields (`hash-max-listpack-entries`, `hash-max-listpack-value`) so they stay in compact listpack encoding.
- Use integer values where possible (Redis stores integers compactly).
- Compress large blobs at the application layer if it makes sense (zstd) — but only if values are big enough to win after CPU cost.

## Operational basics

Things to wire up before going to prod:

- **Monitoring**: `INFO`, `LATENCY`, `SLOWLOG`. Most providers expose these as metrics.
- **Slow log**: `CONFIG SET slowlog-log-slower-than 10000` (10 ms). `SLOWLOG GET` to inspect.
- **Latency monitoring**: `LATENCY DOCTOR`, `LATENCY HISTORY`.
- **Client-side metrics**: per-command latency, error rate, connection pool saturation.
- **Connection pooling**: never open a fresh connection per request. Use a pool. Size it for your concurrency, not larger.
- **Timeouts** on all client calls. Default to 100-500ms; longer for blocking commands. Network hangs without timeouts hang your app.
- **Backups** if Redis is a primary store. Test restore.

## Common anti-patterns

- **`KEYS *` in production.** Blocks the server. Use `SCAN` for iteration.
- **No TTL on cache keys.** Memory creeps up forever; eviction policy decides what dies, not you.
- **Caching without invalidation strategy.** Either set short TTLs and accept staleness, or invalidate on write — pick one, document it.
- **Using `FLUSHALL` to "fix" a problem.** That's deleting prod data. There's almost always a better way.
- **Storing huge JSON blobs as strings instead of hashes.** Wastes serialization round-trips on every partial update.
- **Tight loop of single commands instead of pipelining.** Network round-trips dominate.
- **Treating Redis as durable when running with no AOF and no replicas.** A restart wipes it. If that's surprising, your assumptions are wrong.
- **Using `SUBSCRIBE` for at-least-once delivery.** Pub/sub is fire-and-forget. Use Streams.
- **Distributed locks across a Sentinel failover for correctness-critical mutex.** Use a real coordinator.
- **One giant Redis cluster shared by everything.** Noisy-neighbor city. Split caches from queues from session stores when scale demands it.
- **Cache values that are cheaper to recompute than to fetch from Redis.** Profile before caching trivial things.
- **No connection pool.** Every request opening a fresh TCP connection. Latency death.
- **Putting secrets in Redis without ACL or network isolation.** Redis assumes a trusted network by default.
- **`SAVE` (synchronous) instead of `BGSAVE`.** Blocks the entire instance.

## Sensible defaults for a new deployment

```conf
# redis.conf or equivalent
maxmemory 4gb
maxmemory-policy allkeys-lru
appendonly yes                    # if data matters
appendfsync everysec
save 900 1                        # RDB backup every 15min if 1+ keys changed
save 300 10
slowlog-log-slower-than 10000     # 10ms
slowlog-max-len 1024
tcp-keepalive 60
timeout 0                         # let clients manage their own
requirepass <strong-password>     # always
```

Plus: TLS on the wire (`tls-port`), an ACL with named users, network policy that only allows your app subnet to reach the port. Redis defaults assume a trusted network — if it's reachable from anything that isn't your app, that's your bug, not Redis's.

## Sensible defaults for a client

- Pool size: 10-50 connections per app instance, tuned to concurrency.
- Connect timeout: 1-2 seconds.
- Command timeout: 100-500 ms (longer for blocking commands).
- Retry: 1-2 retries on connection errors with backoff. Don't retry on application-level errors.
- Circuit breaker if Redis is fronting a fallback path. Cache being down shouldn't take the app down — degrade to source of truth.
