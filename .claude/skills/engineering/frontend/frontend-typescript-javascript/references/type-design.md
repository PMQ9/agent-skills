# Type Design

Deeper modeling techniques. Read when the shape of a type is the problem — generics that fight you, inference that widens, a union that won't narrow, or an API surface you want to make hard to misuse.

## Contents

- [Generics: parameterize what varies](#generics-parameterize-what-varies)
- [`satisfies` vs annotation vs `as const`](#satisfies-vs-annotation-vs-as-const)
- [Branded types](#branded-types)
- [Mapped and conditional types](#mapped-and-conditional-types)
- [Template literal types](#template-literal-types)
- [Variance and function parameters](#variance-and-function-parameters)
- [Utility types worth knowing](#utility-types-worth-knowing)
- [Designing APIs that resist misuse](#designing-apis-that-resist-misuse)
- [When to stop](#when-to-stop)

## Generics: parameterize what varies

A generic is justified when the *relationship* between inputs and outputs is the point. If a type parameter appears exactly once in a signature, it isn't doing anything a plain type couldn't:

```ts
// Pointless: T appears once. This is just `(x: unknown) => void`.
function log<T>(x: T): void {}

// Earns it: the return type depends on the input type.
function first<T>(arr: readonly T[]): T | undefined { return arr[0]; }

// Earns it: two parameters related to each other.
function pluck<T, K extends keyof T>(items: readonly T[], key: K): T[K][] {
  return items.map(i => i[key]);
}
```

Constrain with `extends` to get autocomplete and better errors. `K extends keyof T` above means a typo in the key name is a compile error with a useful message, rather than `undefined` at runtime.

**Inference direction matters.** TypeScript infers type parameters from arguments left to right, so put the argument that should drive inference first. When inference goes wrong, the fix is usually a constraint or a default (`<T = string>`), not an explicit call-site type argument everywhere.

Two patterns that come up constantly:

```ts
// Preserve literal types through a helper
function defineRoutes<const T extends Record<string, string>>(routes: T): T {
  return routes;
}
const routes = defineRoutes({ home: "/", user: "/u/:id" });
// routes.home is "/" not string — `const` type parameter (TS 5.0+)

// Distribute over a union
type Arrayify<T> = T extends unknown ? T[] : never;
type R = Arrayify<string | number>;  // string[] | number[], not (string|number)[]
```

## `satisfies` vs annotation vs `as const`

These three do different jobs and get confused constantly:

```ts
type Config = Record<string, string | number>;

// Annotation: checks, but widens. cfg.port is string | number.
const a: Config = { port: 3000, host: "localhost" };

// as const: preserves literals, but no checking against Config.
const b = { port: 3000, host: "localhost" } as const;

// satisfies: checks AND preserves. b.port is 3000, and a typo is still an error.
const c = { port: 3000, host: "localhost" } satisfies Config;
```

Reach for `satisfies` by default on configuration objects, route tables, theme tokens, and anywhere you want both validation and precise inference. Use annotation when you want the wider type (a mutable array you'll push to). Use `as const` alone when there's no type to check against.

## Branded types

Two values with the same primitive type are interchangeable to the compiler even when they're not interchangeable in the domain. A `UserId` and an `OrderId` are both `string`, so passing one where the other belongs compiles fine — and that's a real class of production bug.

```ts
declare const brand: unique symbol;
type Brand<T, B> = T & { readonly [brand]: B };

type UserId = Brand<string, "UserId">;
type OrderId = Brand<string, "OrderId">;

// The only way in is through a function that does the checking.
function toUserId(raw: string): UserId {
  if (!/^u_[a-z0-9]{12}$/.test(raw)) throw new Error(`bad user id: ${raw}`);
  return raw as UserId;
}

declare function getUser(id: UserId): Promise<User>;
getUser(orderId);        // error, as it should be
getUser("u_abc123def456"); // error too — must go through toUserId
```

The `as` inside the constructor is the one legitimate assertion: it's the single audited place where the claim gets checked. Worth doing for IDs, validated email addresses, sanitized HTML, currency amounts in minor units, and anything where mixing up two strings causes a silent wrong result rather than a crash.

Zod supports this directly with `.brand<"UserId">()`, which pairs the brand with the runtime check.

## Mapped and conditional types

Mapped types transform every key of a type:

```ts
type Nullable<T> = { [K in keyof T]: T[K] | null };
type Getters<T> = { [K in keyof T as `get${Capitalize<string & K>}`]: () => T[K] };
type Mutable<T> = { -readonly [K in keyof T]: T[K] };   // strip readonly
type Required2<T> = { [K in keyof T]-?: T[K] };          // strip optionality
```

The `as` clause inside a mapped type (key remapping) also filters — map a key to `never` and it disappears:

```ts
type OnlyFunctions<T> = {
  [K in keyof T as T[K] extends Function ? K : never]: T[K]
};
```

Conditional types (`T extends U ? X : Y`) distribute over unions when `T` is a naked type parameter. Wrap in a tuple to stop distribution when you want the union treated as a whole:

```ts
type IsUnion<T, U = T> = T extends unknown ? ([U] extends [T] ? false : true) : never;
```

`infer` extracts a type from a position:

```ts
type ElementOf<T> = T extends readonly (infer E)[] ? E : never;
type Awaited2<T> = T extends Promise<infer V> ? V : T;
type Params<T> = T extends (...args: infer A) => unknown ? A : never;
```

## Template literal types

Useful for string patterns the compiler should enforce:

```ts
type Hex = `#${string}`;
type Route = `/api/${string}`;
type EventName = `on${Capitalize<"click" | "focus">}`;   // "onClick" | "onFocus"

// Parse a route's params out of its path
type Params<T extends string> =
  T extends `${string}:${infer P}/${infer Rest}` ? P | Params<Rest>
  : T extends `${string}:${infer P}` ? P
  : never;
type P = Params<"/users/:userId/posts/:postId">;   // "userId" | "postId"
```

This is genuinely valuable in a router, an event emitter, or a query builder — places where the string *is* the API. It's overkill in application code.

## Variance and function parameters

Function parameters are bivariant for methods and contravariant for function properties, which explains a confusing class of error:

```ts
interface A { handle(e: MouseEvent): void }   // method — bivariant, laxer
interface B { handle: (e: MouseEvent) => void } // property — contravariant, stricter
```

Under `strictFunctionTypes`, the property form catches unsound assignments the method form allows. Prefer the property form for callbacks and handlers where you want the check.

For generics, `in` / `out` variance annotations (TS 4.7+) are mostly a compile-speed optimization for large unions — correctness-wise the compiler infers variance fine. Don't add them speculatively.

## Utility types worth knowing

Built in, used constantly: `Partial`, `Required`, `Readonly`, `Pick`, `Omit`, `Record`, `Exclude`, `Extract`, `NonNullable`, `ReturnType`, `Parameters`, `Awaited`, `NoInfer` (TS 5.4+, stops a parameter from participating in inference).

Worth writing yourself because the built-ins don't cover them:

```ts
// Omit that errors on a key that doesn't exist (real Omit silently accepts typos)
type StrictOmit<T, K extends keyof T> = Omit<T, K>;

// At least one key required
type AtLeastOne<T, K extends keyof T = keyof T> =
  K extends unknown ? Required<Pick<T, K>> & Partial<Omit<T, K>> : never;

// Deep readonly for config objects
type DeepReadonly<T> = T extends (infer E)[] ? readonly DeepReadonly<E>[]
  : T extends object ? { readonly [K in keyof T]: DeepReadonly<T[K]> }
  : T;

// Flatten an intersection so hover shows a clean object instead of `A & B & C`
type Prettify<T> = { [K in keyof T]: T[K] } & {};
```

`Prettify` is a quality-of-life win on any library type — it changes nothing semantically but makes editor tooltips readable, which is most of how people learn an API.

## Designing APIs that resist misuse

The goal is that the wrong call doesn't compile:

- **Overloads for related-but-distinct call shapes**, not a union parameter with runtime branching. `query(sql)` and `query(sql, params)` as overloads give each form its own return type.
- **Options objects over positional booleans.** `render(el, { animate: true })` reads at the call site; `render(el, true, false)` does not, and nothing catches a swap.
- **Builders that change type as they're built** — a `QueryBuilder<Selected>` where `.select()` narrows what `.execute()` returns.
- **`never` to close doors.** A function parameter typed `never` in one overload branch makes that combination uncallable.
- **Return `readonly` arrays and `Readonly<T>`** from anything the caller shouldn't mutate. Mutating a returned array is a classic action-at-a-distance bug.

## When to stop

Type-level programming has a cost that's easy to underweight: compile time, error message quality (a failed constraint deep in a recursive conditional produces an unreadable error), and the number of people on the team who can safely change the code.

A useful test: if the type needs a comment explaining *how it works* rather than *what it means*, it's probably too clever for application code. In a library's public API, where the type is the product and thousands of call sites benefit, the same complexity can be the right call.
