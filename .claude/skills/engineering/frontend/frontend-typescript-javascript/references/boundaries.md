# Boundaries & Runtime Safety

Read when data is entering or leaving the program: HTTP, env, forms, storage, workers, third-party SDKs. The organizing rule is **parse, don't cast** — turn unknown input into a known type by checking it, once, at the edge.

## Contents

- [Why casting fails](#why-casting-fails)
- [Schema as the single source of truth](#schema-as-the-single-source-of-truth)
- [Choosing a validation library](#choosing-a-validation-library)
- [A typed fetch client](#a-typed-fetch-client)
- [`parse` vs `safeParse`: throw or return](#parse-vs-safeparse-throw-or-return)
- [Environment variables](#environment-variables)
- [Server request bodies and forms](#server-request-bodies-and-forms)
- [Sharing contracts across the wire](#sharing-contracts-across-the-wire)
- [Storage, URL params, and other quiet doors](#storage-url-params-and-other-quiet-doors)
- [Third-party SDKs and untyped modules](#third-party-sdks-and-untyped-modules)
- [What not to validate](#what-not-to-validate)

## Why casting fails

```ts
const user = await res.json() as User;
```

This compiles, and it is a lie the compiler can't detect. Three things go wrong in production, all of them far from this line:

1. The API renames a field. Every downstream `user.email` is `undefined`; nothing throws until something renders "Welcome, undefined."
2. The API returns an error envelope with a 200. `user.id` is undefined, and the crash surfaces in whatever component happened to touch it.
3. A date arrives as an ISO string but the type says `Date`. `user.createdAt.getTime()` throws in a totally unrelated module.

In each case the stack trace points at innocent code. Parsing at the door moves the failure to the door, where the error message can say *which field, from which endpoint, was wrong*.

## Schema as the single source of truth

Declare the schema; derive the type. Never maintain both by hand.

```ts
import { z } from "zod";

export const User = z.object({
  id: z.string().uuid(),
  email: z.string().email(),
  displayName: z.string().min(1).max(80),
  role: z.enum(["admin", "member", "viewer"]),
  createdAt: z.coerce.date(),           // accepts ISO string, yields Date
  deletedAt: z.coerce.date().nullable(),
});
export type User = z.infer<typeof User>;
```

`z.coerce.date()` is doing real work: it absorbs the string→Date impedance mismatch at the boundary instead of leaving it for every consumer. Do the same for numeric IDs arriving as strings, booleans arriving as `"true"`, and anything else JSON can't represent natively.

For unions, discriminate — the error messages are dramatically better and validation is faster:

```ts
const Event = z.discriminatedUnion("type", [
  z.object({ type: z.literal("click"), x: z.number(), y: z.number() }),
  z.object({ type: z.literal("keypress"), key: z.string() }),
]);
```

**Unknown keys.** Zod strips unknown keys by default, which is usually right (forward compatibility — the API adding a field shouldn't break you). Use `.strict()` where an unexpected key means something is genuinely wrong, like your own config file. Use `.passthrough()` almost never.

## Choosing a validation library

| | Zod | Valibot | ArkType |
|---|---|---|---|
| Ecosystem | Largest; tRPC, React Hook Form, Hono, drizzle all assume it | Growing | Smaller |
| Bundle | Largest of the three | Modular, tree-shakes to a few kB | Small |
| Speed | Fine | Fine | Fastest |
| Syntax | Chained builders | Composed functions | TS-like string syntax |

Code in this file uses Zod 4 APIs (`z.stringbool()`, `z.prettifyError()`, `treeifyError()`). On Zod 3 the equivalents are a manual string transform and `error.format()` — check the installed major before copying, since the two majors differ in more than names.

Default to **Zod** unless you have a specific reason — the integration surface is worth more than the bytes for most apps. Switch to **Valibot** when client bundle size is a measured constraint. **ArkType** when validation is hot-path and you like the syntax. They're all conceptually identical, so the choice is reversible.

Hand-written type guards are the option to avoid: they're a second implementation of the type that drifts silently, and nothing tells you when a field is added.

## A typed fetch client

Centralize the parse so no call site can forget it:

```ts
export class HttpError extends Error {
  constructor(readonly status: number, readonly body: string, readonly url: string) {
    super(`HTTP ${status} from ${url}`);
    this.name = "HttpError";
  }
}

export async function apiGet<S extends z.ZodTypeAny>(
  path: string,
  schema: S,
  init?: RequestInit,
): Promise<z.infer<S>> {
  const res = await fetch(`${BASE_URL}${path}`, {
    ...init,
    headers: { accept: "application/json", ...init?.headers },
  });

  if (!res.ok) throw new HttpError(res.status, await res.text().catch(() => ""), path);

  const json: unknown = await res.json();
  const parsed = schema.safeParse(json);
  if (!parsed.success) {
    // The message names the endpoint and the failing path — that's the whole point.
    throw new Error(`Bad response from ${path}: ${parsed.error.issues
      .map(i => `${i.path.join(".")}: ${i.message}`).join("; ")}`);
  }
  return parsed.data;
}

// usage — the return type is inferred from the schema, no annotation needed
const users = await apiGet("/users", z.array(User));
```

The signature is what makes this work: taking the schema as a parameter means you *cannot* call it without deciding what shape you expect. A client with an `as T` inside it just relocates the lie.

Add `signal` passthrough for cancellation, and a `timeout` via `AbortSignal.timeout(ms)` — a fetch with no timeout hangs forever when a proxy swallows the connection.

## `parse` vs `safeParse`: throw or return

Rule of thumb: **throw for programmer errors, return for user errors.**

- A malformed API response is a bug (yours or theirs) — throwing is right; it should reach an error boundary and get reported.
- A user typing an invalid email is expected — returning a result you render as field-level feedback is right. Throwing means building exception plumbing for the normal path.

```ts
const result = LoginForm.safeParse(formData);
if (!result.success) {
  return { errors: result.error.flatten().fieldErrors };  // render these
}
await login(result.data);
```

`flatten()` gives `{ formErrors, fieldErrors }`, which maps directly onto form UI. `treeifyError()` handles nested objects.

## Environment variables

`process.env.FOO` is `string | undefined`, and every access site either checks it or lies. Validate once at startup and export a typed object:

```ts
// env.ts — imported for its side effect early in the entry point
const Env = z.object({
  NODE_ENV: z.enum(["development", "test", "production"]).default("development"),
  DATABASE_URL: z.string().url(),
  PORT: z.coerce.number().int().positive().default(3000),
  SESSION_SECRET: z.string().min(32),
  FEATURE_X: z.stringbool().default(false),   // "true"/"1"/"yes" → boolean
});

const parsed = Env.safeParse(process.env);
if (!parsed.success) {
  console.error("Invalid environment:\n", z.prettifyError(parsed.error));
  process.exit(1);
}
export const env = parsed.data;
```

Failing at boot is the entire value: a missing `SESSION_SECRET` should stop the deploy, not surface as a login bug next Tuesday. Keep client-exposed vars in a separate schema so a server secret can never be bundled by accident.

## Server request bodies and forms

Every handler validates its input — the client's validation is a UX affordance, not a security control.

```ts
export async function POST(req: Request) {
  const body = CreateOrder.safeParse(await req.json().catch(() => null));
  if (!body.success) {
    return Response.json({ errors: body.error.flatten() }, { status: 400 });
  }
  // body.data is CreateOrder — fully typed, actually checked
}
```

`FormData` needs conversion first (`Object.fromEntries(formData)`), and note that multi-value fields collapse — use `formData.getAll()` for those. `z.coerce` handles the everything-is-a-string problem.

## Sharing contracts across the wire

Ranked by how much the compiler can help:

1. **tRPC** — types flow from server to client automatically; no codegen, no drift. Best when both ends are TypeScript in one repo.
2. **OpenAPI + codegen** (`openapi-typescript`, `orval`) — generate types from a spec. The right call when the server isn't TS or the API is public. The spec is the contract; regenerate in CI so drift is a failing build.
3. **A shared schema package** — a workspace package exporting Zod schemas both sides import. Simple and explicit; works when both ends are TS but not tRPC.
4. **Hand-copied interfaces** — drift is a matter of when.

Whichever you pick, the client still parses at runtime if the server is a separate deployment, because "the types agree" only proves the two repos agreed at build time, not that the deployed version matches.

## Storage, URL params, and other quiet doors

`localStorage`, `sessionStorage`, cookies, `IndexedDB`, and URL search params all return strings someone else wrote — possibly an older version of your own app. Treat them as untrusted:

```ts
function readPrefs(): Prefs {
  try {
    return Prefs.parse(JSON.parse(localStorage.getItem("prefs") ?? "null"));
  } catch {
    return DEFAULT_PREFS;   // old shape, corrupt, or disabled storage
  }
}
```

The `try` also covers Safari private mode and blocked-cookie contexts, where the accessor itself throws. For search params, `z.coerce` plus `.catch(default)` gives you a total function from URL to state, which is what a filterable list page actually wants.

`postMessage` between windows or workers is the same problem with a security dimension — check `event.origin` before parsing, and parse before using.

## Third-party SDKs and untyped modules

When a package ships no types, don't `any` it into your app. Write a minimal declaration covering only what you use:

```ts
// types/legacy-widget.d.ts
declare module "legacy-widget" {
  export function mount(el: HTMLElement, opts?: { theme?: "light" | "dark" }): () => void;
}
```

This is a claim you're making, so keep it narrow — typing three functions you actually call is honest; typing the whole surface from memory is fiction. If the package has community types, `@types/x` first.

For SDKs that return `any` (older AWS/Firebase clients, some CMS clients), parse their output at your boundary too. `any` from a dependency is the same hole in the floor as `any` you wrote.

## What not to validate

Parsing at the edge buys the right to trust types internally. Re-validating in the middle of the app is a smell:

- It's slow and noisy, and it trains people to ignore validation errors.
- It suggests the edge parse doesn't exist or isn't trusted — fix that instead.
- Internal invariants belong in assertions or the type system, not in a schema re-check.

The exception is a genuine trust boundary in the middle: a plugin system, user-supplied code, or a message queue whose producers you don't control. Those are doors too, even though they don't touch the network.
