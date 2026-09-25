---
name: frontend-typescript-javascript
description: Use this skill for TypeScript and JavaScript as languages — type design (discriminated unions, generics, narrowing, branded types, making illegal states unrepresentable), runtime validation at boundaries (Zod/Valibot/ArkType), modern JS and async (ESM vs CJS, promise concurrency, AbortController, iterators, error handling), tsconfig and lint setup, type-checking in CI, and incremental JS→TS migration. Trigger whenever work touches .ts/.tsx/.js/.jsx/.mjs files, a tsconfig.json, a type error, `any`/`as`/`!` cleanup, "how should I type this", "why won't TypeScript narrow this", parsing an API response, ESM/CJS interop failures, unhandled rejections, or converting a JS codebase to TypeScript — even when the user frames it as a React, Node, or framework question, because most "framework type problems" are really language problems wearing a framework costume. Pairs with `frontend-development` (platform) and `frontend-react-next` (framework); this skill owns the language.
---

# TypeScript & JavaScript

TypeScript is a **claims-checking system for JavaScript that runs only at build time**. Every type is a promise about what will exist at runtime, and the compiler verifies those promises against each other — never against reality. Reality enters through a handful of doors: network responses, `JSON.parse`, `process.env`, form inputs, `localStorage`, third-party SDKs, and any `as`. Everything downstream of those doors is only as true as what you asserted at the door.

That single fact organizes almost all good TS practice. Put real checking at the doors, model the domain honestly inside, and the compiler does enormous work for free. Skip the door checks and you get a codebase that type-checks perfectly and crashes in production — the worst of both worlds, because now the types are actively lying and people trust them.

Work from this order when a question lands:

1. **Where does this data enter the program?** That's where validation belongs.
2. **What states can this thing actually be in?** Model those, not a bag of optional fields.
3. **What does the compiler already know here?** Most type errors are the compiler being right.
4. Only then reach for generics, conditional types, or an assertion.

## Reference map

Keep this file in context; read a reference when the work is actually in that area.

| Read | When |
|---|---|
| `references/type-design.md` | Generics, conditional/mapped types, branded types, variance, `satisfies`, declaration merging, type-level puzzles |
| `references/boundaries.md` | Validating API responses, env vars, forms; typed fetch clients; sharing contracts across client/server |
| `references/async-idioms.md` | Promise concurrency, cancellation, ESM/CJS interop, iterators/generators, modern built-ins, error handling |
| `references/config-tooling.md` | tsconfig options explained, lint setup, CI type-checking, monorepo project references, build vs typecheck |
| `references/migration.md` | Incremental JS→TS migration, `any` cleanup, typing untyped dependencies |

## Model states, not fields

The highest-leverage habit in TypeScript is refusing to represent impossible states. Most bugs in typed code live in the gap between "what the type allows" and "what can actually happen."

The tell is a group of optional fields that are secretly correlated:

```ts
// Allows 16 combinations. Four are real.
interface RequestState {
  loading?: boolean;
  data?: User;
  error?: Error;
}

if (state.data) { /* is it still loading? is there also an error? types say maybe */ }
```

A discriminated union collapses that to exactly the real states, and the compiler starts enforcing that you handle each one:

```ts
type RequestState =
  | { status: "idle" }
  | { status: "loading" }
  | { status: "success"; data: User }
  | { status: "error"; error: Error };

switch (state.status) {
  case "success": return render(state.data);   // data is User, not User | undefined
  case "error":   return renderError(state.error);
  case "loading": return <Spinner />;
  case "idle":    return null;
}
```

This pattern generalizes far past request state — form validity, auth sessions, feature flags with payloads, parser results, job status, anything with a "kind." Whenever you find yourself writing `if (a && !b)` to figure out what situation you're in, that situation deserves a name in the type.

Two things make it pay off:

**Exhaustiveness checking.** Add a case tomorrow and every unhandled switch becomes a compile error instead of a silent fallthrough. This is how a union stays trustworthy as the domain grows:

```ts
function assertNever(x: never): never {
  throw new Error(`Unhandled case: ${JSON.stringify(x)}`);
}
// in the default branch:
default: return assertNever(state);
```

**Nullability that means something.** `T | null` for "this genuinely can be absent," `T | undefined` for "not provided." Picking one convention per codebase and sticking to it matters more than which you pick — mixing them turns every check into a coin flip about whether `?.` or `!= null` is right.

## Let the compiler narrow; don't shout over it

Narrowing is TypeScript's best feature and the thing people most often bulldoze. When a type won't narrow, it's usually reporting a real gap rather than being obtuse.

Prefer control flow the compiler understands:

```ts
// typeof / instanceof / in / literal comparison / truthiness — all narrow
if (typeof id === "string") { /* id: string */ }
if (err instanceof HttpError) { /* err: HttpError */ }
if ("cursor" in page) { /* page has cursor */ }
```

When narrowing has to cross a function boundary, a **type predicate** carries it:

```ts
function isNonEmpty<T>(arr: T[]): arr is [T, ...T[]] {
  return arr.length > 0;
}
```

Predicates are a promise you're making by hand — the compiler trusts the signature and never checks the body. A wrong predicate is as dangerous as `as`, so keep the body trivially obviously correct.

### The escape hatches, ranked by cost

- **`satisfies`** — free. Checks a value against a type without widening it, so you keep literal inference *and* get validation. This is what most `as const as Config` code actually wanted.
- **`as unknown as T`** — loud on purpose. If you need it, the surrounding design is usually wrong.
- **`as T`** — a claim the compiler can't verify. Every one is a place your types might be lying. Acceptable at real boundaries you've just validated, or for test fixtures. Not acceptable as a way to end an argument with the compiler.
- **`!` (non-null assertion)** — the same lie, compressed to one character, which is why it spreads. `arr.find(...)!` is the single most common source of "cannot read property of undefined" in typed codebases.
- **`any`** — not an escape hatch but a hole in the floor: it disables checking for everything it touches downstream. Use `unknown` instead and narrow. `unknown` forces the check `any` lets you skip.

When you do use one, a one-line comment saying *why it's safe here* is worth more than the assertion itself — it's the thing the next reader needs and the thing that becomes false first.

## Validate at the doors

Types describe; they do not check. `await res.json()` is `any` (or `unknown` if you're lucky), and casting it to `User` doesn't make it a `User` — it just moves the crash later, into code that has no idea what went wrong.

Parse instead, with a schema library, at the exact point data enters:

```ts
import { z } from "zod";

const User = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  role: z.enum(["admin", "member"]),
  createdAt: z.coerce.date(),
});
type User = z.infer<typeof User>;   // one source of truth: schema generates the type

export async function getUser(id: string): Promise<User> {
  const res = await fetch(`/api/users/${id}`);
  if (!res.ok) throw new HttpError(res.status, await res.text());
  return User.parse(await res.json());   // throws here, where the context is
}
```

Deriving the type from the schema (rather than declaring both) is what keeps them from drifting. When they're declared separately, one of them is wrong within a month and nothing tells you.

The doors worth guarding in nearly every app: HTTP responses, request bodies on the server, `process.env` (validate once at startup and export a typed object — a missing env var should crash on boot, not at 3am in a code path nobody exercised), URL/search params, `localStorage` and cookies, webhook payloads, and anything crossing a worker or IPC boundary.

Inside those doors, don't re-validate. Parsing at the edge is what buys you the right to trust the types everywhere else; validating in the middle is a symptom that you didn't parse at the edge.

Zod is the default here because it's ubiquitous and the ecosystem assumes it. Valibot wins when bundle size is the constraint (tree-shakeable, much smaller); ArkType wins on raw validation speed and TS-native syntax. Any of them beats hand-written guards, which rot.

`references/boundaries.md` has typed fetch clients, error-return vs throw at boundaries, `safeParse` handling, and sharing schemas between client and server.

## Async: the failure modes that actually happen

Four bugs account for most async pain:

**Sequential awaits in a loop.** `for (const id of ids) { await fetch(id) }` is N round trips where one would do. Use `Promise.all` when you need everything, `Promise.allSettled` when partial failure is acceptable and you want to report it, and a bounded pool (`p-limit`, or a small semaphore) when N is large enough to melt the target. Unbounded `Promise.all` over 10,000 items is its own outage.

**Floating promises.** A promise nobody awaits is an error nobody sees; in Node it can kill the process. `@typescript-eslint/no-floating-promises` catches these and is worth turning on for that rule alone. If a promise is intentionally fire-and-forget, say so — `void doThing()` with a `.catch()` attached.

**No cancellation.** When a component unmounts or a newer request supersedes an older one, the old work should stop. `AbortController` is the standard mechanism and threads through `fetch`, most modern APIs, and your own functions if you accept a `signal`. Without it you get race conditions where a slow response overwrites a fast one.

**Errors that lose their context.** `catch (e)` types `e` as `unknown` — correctly, since JS lets you throw anything. Narrow it rather than assuming `e.message` exists. When rethrowing, preserve the chain with `cause`:

```ts
try {
  return await chargeCard(order);
} catch (cause) {
  throw new PaymentError(`charge failed for order ${order.id}`, { cause });
}
```

Typed error unions (returning `Result<T, E>` instead of throwing) are a reasonable choice for expected, recoverable failures — a validation failure isn't exceptional. Reserve throwing for genuinely unexpected states. Mixing both incoherently is worse than either.

`references/async-idioms.md` covers concurrency patterns, cancellation plumbing, async iterators for streaming, and the JS built-ins worth knowing.

## Modules: ESM is the destination

Most weird build errors in Node projects are ESM/CJS interop. The short version:

- `"type": "module"` in package.json makes `.js` files ESM. `.mjs` is always ESM, `.cjs` always CJS.
- ESM can import CJS (usually — default export interop is where it breaks). CJS cannot `require` ESM. This asymmetry is the source of `ERR_REQUIRE_ESM`.
- With `moduleResolution: "Bundler"` you don't write file extensions; with `"NodeNext"` you must write `.js` even in `.ts` source. Pick based on whether a bundler or Node resolves your imports, and don't fight the one you picked.
- `verbatimModuleSyntax: true` forces explicit `import type` for type-only imports, which prevents a class of "import erased at runtime, module never evaluated" bugs.

New code: ESM. Existing CJS that works: leave it unless it's blocking something. A half-migrated module system costs more than either whole one.

## Config is where bugs get caught for free

A `tsconfig.json` without `strict: true` is a linter with opinions. Strictness costs one afternoon at project setup and pays continuously; adding it to a mature codebase is a migration (see `references/migration.md`).

```jsonc
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,   // arr[i] is T | undefined — the honest type
    "exactOptionalPropertyTypes": true, // `?: string` no longer silently allows undefined
    "noImplicitOverride": true,
    "verbatimModuleSyntax": true,
    "skipLibCheck": true,               // your deps' type errors aren't your job
    "isolatedModules": true,            // required by every modern transpiler
    "noEmit": true                      // when a bundler does the emitting
  }
}
```

`noUncheckedIndexedAccess` is the one people turn off first and shouldn't. It's the difference between types that model arrays accurately and types that assume every index hits.

Two habits beyond config:

- **Type-check in CI as its own step.** Bundlers (esbuild, SWC, Vite) strip types without checking them, so a green build proves nothing. `tsc --noEmit` in CI is what makes the types load-bearing.
- **Let the linter own what types can't.** Types don't catch floating promises, `await` on non-promises, unsafe `any` flowing through, or unhandled union members. `typescript-eslint` with type-aware rules does. Biome is faster and simpler for formatting and syntactic rules but doesn't do type-aware linting — many teams run both.

## Migration: make it boring

Converting a JS codebase works when it's incremental and mechanical, and fails when it's a rewrite. The reliable path: `allowJs: true` so both coexist, turn on `checkJs` to get value from JSDoc types before converting anything, then convert leaf modules (utilities, types, constants) upward toward entry points — leaves have fewer inbound dependencies, so each conversion is contained.

Use `unknown` and honest `any` with a `// TODO` during conversion rather than inventing types you haven't verified; a wrong type is worse than a missing one because it stops anyone from looking. Ratchet strictness per-directory rather than flipping it globally on day one. Full sequencing in `references/migration.md`.

## Anti-patterns worth naming

- **`as` at the boundary instead of a parse.** The single most common way typed codebases crash.
- **Interface soup of optionals** where a discriminated union belongs.
- **`any` in a shared utility.** It poisons every call site, and it's invisible at those call sites — that's what makes it worse than a local `any`.
- **Enums over unions.** TS `enum` has runtime output, awkward ESM behavior, and no benefit over `"a" | "b"` or `as const` objects for most uses. `const enum` is worse (breaks under isolated transpilation).
- **Type gymnastics in application code.** A deeply recursive conditional type that takes an hour to read is a liability in app code, though it can be right in a library's public API. If a type needs a comment explaining how it works, consider whether a simpler shape and a runtime check would serve better.
- **`@ts-ignore`** without an explanation, and over `@ts-expect-error` — the latter errors when the underlying problem is fixed, so it cleans itself up.
- **Types declared alongside a schema** instead of inferred from it. They drift; the schema is the one that's true.
- **`Function`, `object`, `{}` as types.** They mean less than they look like they mean; `{}` in particular means "anything but null/undefined."

## What good looks like

A reviewer reading a well-built TS module can answer, without running it: what states can this be in, what happens when the network returns garbage, what's checked at build time versus runtime, and where the unsafe parts are (because they're few, labeled, and at the edges). The types tell the truth about runtime, and a type error is information rather than an obstacle to route around.
