# Performance Detection Guide

Language-agnostic detection cues and worked before/after examples for the seven
categories the performance reviewer hunts. Examples use pseudo-code that reads
like Python/JS/TS; translate the pattern to whatever the diff is written in — the
shape of the problem is the same across languages and ORMs.

Every fix here is implementation-level. If the only fix you can think of is a
redesign, that's out of scope — note the hot path is structurally expensive and
move on.

## Table of contents

1. N+1 queries
2. Unnecessary / repeated DB calls
3. Expensive loops
4. Memory allocations
5. Async misuse
6. Blocking I/O
7. Caching opportunities

---

## 1. N+1 queries

**Tell:** a query, ORM access, or remote call *inside* a loop over a collection;
lazy-loaded relations accessed while iterating; a "get by id" called per element.

**Cost:** 1 query to fetch the list + N queries for N elements. Linear DB round
trips where one batched query would do. Devastating on list endpoints.

```
# before — one query per order
orders = Order.all()
for o in orders:
    customer = Customer.get(o.customer_id)   # N queries
    print(customer.name)

# after — one extra query total
orders = Order.all()
customers = Customer.where(id in [o.customer_id for o in orders])  # 1 query
by_id = {c.id: c for c in customers}
for o in orders:
    print(by_id[o.customer_id].name)
```

Also look for ORM eager-loading that's available but unused: `select_related` /
`prefetch_related` (Django), `.includes` (Rails), `JOIN FETCH` / `@EntityGraph`
(JPA), `include` (Prisma), `joinedload` (SQLAlchemy). If the ORM offers it and
the code loops over a relation without it, that's the fix — name the mechanism.

## 2. Unnecessary / repeated DB calls

**Tell:** the same row fetched more than once; a query inside a loop for data that
doesn't change per iteration; `SELECT *` when a couple of columns are used;
loading full rows just to count them or check existence.

```
# before — count re-runs every iteration, and full fetch just to count
for item in items:
    if Order.where(user_id=item.user_id).all().length > 0:   # fetches rows, per item
        ...

# after — existence check, hoisted, batched
user_ids_with_orders = set(Order.where(user_id in ids).pluck(:user_id))  # 1 query
for item in items:
    if item.user_id in user_ids_with_orders:
        ...
```

Other forms: fetching a config/lookup row inside a request that could be loaded
once; calling `.save()` per element instead of a bulk insert/update; re-querying
right after a write when the object is already in hand.

## 3. Expensive loops

**Tell:** nested iteration doing a linear lookup that could be O(1) (accidental
O(n²)); recomputing an invariant every pass; building a collection only to read
its length; sorting or regex-compiling inside a loop.

```
# before — O(n*m): linear search per element
for a in list_a:
    if a.id in [b.id for b in list_b]:   # rebuilds + scans list_b every iteration
        ...

# after — O(n+m): build the set once
b_ids = {b.id for b in list_b}
for a in list_a:
    if a.id in b_ids:
        ...
```

Also: `len([x for x in items if pred(x)])` when you only need "is there any"
(short-circuit with `any`); compiling the same regex each call (hoist it);
repeated string concatenation in a loop (accumulate then join).

## 4. Memory allocations

**Tell:** materializing an entire collection when you only iterate once; reading a
whole file/response into memory; building a large intermediate list that's
immediately consumed; unbounded caches or accumulators that grow with input.

```
# before — whole file in memory
lines = open(path).read().split("\n")
for line in lines:
    process(line)

# after — stream it
for line in open(path):
    process(line)
```

Prefer generators/iterators/streaming over list materialization when the data is
consumed once. Watch for `.all()` / `list(...)` / `.toArray()` on something large
that's only iterated. Flag accumulators (dicts, lists, caches) that grow with
request volume and are never bounded or evicted.

## 5. Async misuse

**Tell:** `await` inside a loop that serializes independent calls; awaiting
independent operations one after another instead of concurrently; blocking calls
inside async functions; fire-and-forget that swallows errors.

```
# before — serial: total time = sum of all calls
results = []
for url in urls:
    results.append(await fetch(url))   # each awaits the previous

# after — concurrent: total time ≈ slowest call
results = await gather(*[fetch(url) for url in urls])   # or Promise.all
```

Only parallelize genuinely independent work — if call N depends on call N-1's
result, serial is correct. Also flag: a blocking/synchronous call (CPU-bound work,
sync file read, `time.sleep`) inside an async handler, which stalls the event
loop; `async` on a function that never awaits (pointless overhead).

## 6. Blocking I/O

**Tell:** synchronous file, network, disk, or subprocess calls on a request path,
inside an event loop, or in a hot function; sync DB drivers in async code; sync
`requests.get` / `fs.readFileSync` / blocking socket reads where an async variant
exists.

```
# before — sync HTTP inside an async request handler blocks the event loop
async def handler(req):
    data = requests.get(url).json()   # blocks the whole loop
    return data

# after — non-blocking client
async def handler(req):
    data = await async_client.get(url)
    return data
```

Distinguish hot paths from one-time startup: a blocking read at process boot is
usually fine; the same read per request is not. For unavoidable blocking CPU/I/O
in async code, the implementation-level fix is to offload it to a thread/executor
(`run_in_executor`, worker thread) — not to redesign the service.

## 7. Caching opportunities

**Tell:** a pure, deterministic, expensive computation or fetch repeated with the
same inputs; the same value recomputed across calls within a request; an existing
cache layer that's available but bypassed.

```
# before — recomputes / refetches the same thing every call
def get_rate(currency):
    return db.query("SELECT rate FROM fx WHERE currency = ?", currency)  # hit per call

# after — memoize the pure lookup
@lru_cache
def get_rate(currency):
    return db.query("SELECT rate FROM fx WHERE currency = ?", currency)
```

Only suggest caching when the result is stable enough that staleness is
acceptable, and when the computation is actually expensive and repeated. Flag the
opportunity and the key; do **not** design an invalidation strategy or a
distributed cache — that's architecture. If correctness depends on freshness, say
caching is risky here rather than recommending it.
