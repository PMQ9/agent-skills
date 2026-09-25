# Async & Modern JavaScript

Read when the work involves promises, concurrency, cancellation, streaming, module interop, or "which built-in should I use here."

## Contents

- [Concurrency: pick the right combinator](#concurrency-pick-the-right-combinator)
- [Bounded concurrency](#bounded-concurrency)
- [Cancellation with AbortController](#cancellation-with-abortcontroller)
- [Floating promises and fire-and-forget](#floating-promises-and-fire-and-forget)
- [Error handling](#error-handling)
- [Result types vs throwing](#result-types-vs-throwing)
- [Async iterators and streaming](#async-iterators-and-streaming)
- [Event loop: microtasks and starvation](#event-loop-microtasks-and-starvation)
- [ESM and CJS interop](#esm-and-cjs-interop)
- [Built-ins worth reaching for](#built-ins-worth-reaching-for)
- [Equality, copying, and other footguns](#equality-copying-and-other-footguns)

## Concurrency: pick the right combinator

```ts
// WRONG: N sequential round trips
for (const id of ids) results.push(await getUser(id));

// All must succeed; rejects on the first failure (others keep running, uncancelled)
const users = await Promise.all(ids.map(getUser));

// Partial failure is acceptable and you want to report it
const settled = await Promise.allSettled(ids.map(getUser));
const ok = settled.filter(r => r.status === "fulfilled").map(r => r.value);
const failed = settled.filter(r => r.status === "rejected").map(r => r.reason);

// First success wins; rejects with AggregateError only if all fail
const fastest = await Promise.any([fromCache(k), fromOrigin(k)]);

// First settle wins, success or failure — the classic timeout race
const value = await Promise.race([work(), rejectAfter(5_000)]);
```

Two things people miss about `Promise.all`: it **rejects fast but doesn't cancel** — the other requests still run to completion and their rejections can go unhandled — and it's **unbounded**, so `Promise.all` over 50,000 IDs opens 50,000 sockets. `allSettled` avoids the first problem; a pool avoids the second.

When independent async work happens to be in the same function, start it before awaiting:

```ts
const userP = getUser(id);        // both in flight
const ordersP = getOrders(id);
const [user, orders] = await Promise.all([userP, ordersP]);
```

## Bounded concurrency

For large N, cap in-flight work. `p-limit` is the standard answer; the hand-rolled version is small enough to inline when you can't add a dependency:

```ts
async function mapLimit<T, R>(
  items: readonly T[],
  limit: number,
  fn: (item: T, index: number) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length);
  let next = 0;
  const workers = Array.from({ length: Math.min(limit, items.length) }, async () => {
    while (next < items.length) {
      const i = next++;
      results[i] = await fn(items[i]!, i);
    }
  });
  await Promise.all(workers);
  return results;
}
```

Pick the limit from what the *target* tolerates (a database connection pool size, an API's rate limit), not from what your machine can open. When the target rate-limits, pair this with retry-with-jitter — retrying a whole batch on the same schedule recreates the spike that caused the limit.

## Cancellation with AbortController

Work that outlives its reason to exist causes races: a stale response overwrites a fresh one, an unmounted component setState-s, a superseded search renders old results.

```ts
const controller = new AbortController();
const res = await fetch(url, { signal: controller.signal });
controller.abort();   // rejects the fetch with an AbortError
```

Accept a `signal` in your own async functions and thread it through — a function that can't be cancelled makes everything calling it uncancellable:

```ts
async function search(q: string, { signal }: { signal?: AbortSignal } = {}) {
  signal?.throwIfAborted();                       // bail before starting
  const res = await fetch(`/search?q=${encodeURIComponent(q)}`, { signal });
  return SearchResults.parse(await res.json());
}
```

Useful statics: `AbortSignal.timeout(ms)` for a self-aborting deadline, and `AbortSignal.any([a, b])` to combine a caller's signal with your own timeout. Distinguish aborts from real failures when catching — `if (err instanceof DOMException && err.name === "AbortError") return;` — because reporting a deliberate cancellation as an error trains people to ignore the error channel.

## Floating promises and fire-and-forget

An un-awaited promise that rejects produces an unhandled rejection, which in Node terminates the process by default. The lint rule `@typescript-eslint/no-floating-promises` catches these, and it's one of the highest-value type-aware rules.

When you genuinely don't want to wait, say so explicitly and handle the failure:

```ts
void analytics.track("checkout_started", { orderId })
  .catch(err => logger.warn({ err }, "analytics failed"));
```

The related trap: **`forEach` does not await**. `items.forEach(async i => await save(i))` returns immediately with every save still in flight and every rejection floating. Use `for...of` with `await`, or `Promise.all(items.map(...))`.

## Error handling

`catch (e)` gives `unknown`, because JS lets you throw anything — strings, numbers, `null`, DOM exceptions. Narrow before using:

```ts
function toMessage(e: unknown): string {
  if (e instanceof Error) return e.message;
  if (typeof e === "string") return e;
  return JSON.stringify(e);
}
```

Preserve context when rethrowing. `cause` keeps the chain intact so the stack trace tells the whole story:

```ts
try {
  await db.insert(row);
} catch (cause) {
  throw new StorageError(`failed to insert order ${row.id}`, { cause });
}
```

Custom error classes are worth it when callers need to branch on the kind of failure. Set `name` explicitly — class names get mangled by minifiers, so `instanceof` works locally and fails in production bundles if that's all you rely on:

```ts
export class HttpError extends Error {
  readonly name = "HttpError";
  constructor(readonly status: number, message: string, options?: ErrorOptions) {
    super(message, options);
  }
}
```

Retries belong around *transient* failures only — network errors, 429, 5xx. Retrying a 400 just wastes time and quota. Exponential backoff with jitter; a cap on total attempts; and respect `Retry-After` when the server sends it.

## Result types vs throwing

For failures that are expected and recoverable, returning them is often cleaner than throwing — the type system then forces the caller to deal with it:

```ts
type Result<T, E = Error> =
  | { ok: true; value: T }
  | { ok: false; error: E };

const r = await parseUpload(file);
if (!r.ok) return showFieldError(r.error);
use(r.value);   // narrowed to T
```

The tradeoff is real: `Result` is explicit and composable but verbose, and it doesn't compose with code that throws (most of the ecosystem). A workable line is **throw for bugs and unexpected states, return for domain outcomes** — validation failures, "not found," "insufficient balance." What matters most is consistency; a codebase where both appear at random forces every caller to defend twice.

## Async iterators and streaming

When results arrive over time, `for await` reads like a loop and handles backpressure:

```ts
async function* paginate<T>(fetchPage: (cursor?: string) => Promise<{ items: T[]; next?: string }>) {
  let cursor: string | undefined;
  do {
    const page = await fetchPage(cursor);
    yield* page.items;
    cursor = page.next;
  } while (cursor);
}

for await (const item of paginate(fetchUsers)) {
  process(item);   // one page in memory at a time
}
```

Same shape works for SSE, log tails, and LLM token streams. Web Streams (`ReadableStream`, `TransformStream`) are the platform primitive underneath and are now in Node too; use them when you need to pipe or tee rather than just consume.

Note that `break`ing out of a `for await` calls the generator's `return()`, which is your chance to clean up in a `finally`.

## Event loop: microtasks and starvation

Promise callbacks are microtasks: they drain completely before the next macrotask (timers, I/O, rendering). A recursive promise chain with no yield starves everything, including paint:

```ts
// Yield to let the browser render / the loop breathe
await new Promise(r => setTimeout(r, 0));          // macrotask
await scheduler.yield();                            // better, where available
```

For CPU-heavy work in the browser the answer is a Worker, not a yield — `async` doesn't create parallelism, it only interleaves. A tight numeric loop in an `async` function blocks the main thread exactly as much as a sync one.

## ESM and CJS interop

The rules that resolve most "it works in dev but not in prod" module errors:

- **What makes a file ESM**: `"type": "module"` in the nearest package.json, or a `.mjs` extension. `.cjs` is always CJS.
- **ESM importing CJS** usually works; the CJS `module.exports` object becomes the default import. Named imports from CJS work only when Node's static analysis can detect them — which it sometimes can't, giving "does not provide an export named X."
- **CJS `require`-ing ESM** fails with `ERR_REQUIRE_ESM` on older Node. Newer Node (22.12+) permits `require()` of synchronous ESM, which removes much of the pain, but don't rely on it if you support older runtimes.
- **`__dirname` / `__filename` don't exist in ESM.** Use `import.meta.dirname` (Node 20.11+) or derive from `import.meta.url`.
- **Dual packages** publish both builds via the `exports` map. Getting `types`, `import`, and `require` conditions right is fiddly; `publint` and `arethetypeswrong` check it in CI and catch the common mistakes.
- **`moduleResolution`**: `"Bundler"` when a bundler resolves (no extensions in imports); `"NodeNext"` when Node resolves (write `.js` extensions even in `.ts` files — you're naming the *output*).
- **`verbatimModuleSyntax: true`** makes type-only imports explicit. Without it, a transpiler can erase an import whose bindings are all types, skipping a module's side effects, which produces mysteriously absent behavior.

## Built-ins worth reaching for

Modern and widely available — reaching for lodash or a hand-rolled version for these is a tell that the codebase's baseline is stale:

```ts
arr.at(-1)                      // last element, no length math
arr.findLast(fn) / findLastIndex(fn)
arr.flat(depth) / flatMap(fn)
arr.toSorted(cmp) / toReversed() / toSpliced() / with(i, v)   // non-mutating (ES2023)
Object.groupBy(items, i => i.type)     // Map.groupBy for a real Map
Object.fromEntries(map)
Object.hasOwn(obj, key)                // replaces hasOwnProperty.call
structuredClone(value)                 // real deep clone: Maps, Dates, cycles
Array.from({ length: n }, (_, i) => i)
str.replaceAll(a, b)
new Intl.NumberFormat(locale, { style: "currency", currency: "USD" })
new Intl.RelativeTimeFormat(locale)    // "3 days ago" without a date library
crypto.randomUUID()
```

`toSorted` and friends matter more than they look: `arr.sort()` mutating in place is a recurring source of "why did my props change" bugs in UI code.

For dates, `Temporal` is the eventual answer; until it's broadly available, `date-fns` (tree-shakeable) beats keeping `moment` around. Note `Date` parsing of non-ISO strings is implementation-defined — always parse explicitly.

## Equality, copying, and other footguns

- `structuredClone` is the deep copy. Spread is shallow; `JSON.parse(JSON.stringify(x))` silently destroys `Date`, `Map`, `Set`, `undefined`, and cycles.
- `Object.is` for `NaN` and `-0` edge cases; `===` otherwise. `==` only for the `== null` idiom (catches both `null` and `undefined`), which is genuinely useful.
- `??` and `??=` for "default when nullish" — `||` treats `0` and `""` as missing, which is the bug in `const limit = opts.limit || 10`.
- `?.` short-circuits the whole chain, including calls (`obj.fn?.()`) and indexes (`arr?.[0]`).
- Sorting numbers needs a comparator: `[10, 9, 1].sort()` gives `[1, 10, 9]` because the default is lexicographic.
- `parseInt` without a radix, and `parseInt` on a float string, both bite. `Number(x)` or `Number.parseFloat` are usually what you meant.
- Numbers are float64: `0.1 + 0.2 !== 0.3`. Money goes in integer minor units or a decimal library — never a float.
