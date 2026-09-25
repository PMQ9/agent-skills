# JS → TS Migration

Read when converting an existing JavaScript codebase, turning on `strict` in a mature project, or cleaning up accumulated `any`.

The failure mode is always the same: a migration framed as a rewrite. It stalls at 40%, the codebase now has two conventions, and everyone hates types. The alternative is boring and works — coexist first, convert leaves upward, ratchet strictness, never block a feature on the migration.

## Contents

- [Phase 0: type-check the JavaScript you already have](#phase-0-type-check-the-javascript-you-already-have)
- [Phase 1: let both coexist](#phase-1-let-both-coexist)
- [Phase 2: convert leaves upward](#phase-2-convert-leaves-upward)
- [Phase 3: ratchet strictness](#phase-3-ratchet-strictness)
- [Honest placeholders](#honest-placeholders)
- [Untyped dependencies](#untyped-dependencies)
- [Cleaning up `any`](#cleaning-up-any)
- [Keeping it from sliding back](#keeping-it-from-sliding-back)

## Phase 0: type-check the JavaScript you already have

Before converting a single file, you can get a large share of the value. TypeScript checks `.js` files with `checkJs`, using JSDoc for annotations:

```jsonc
{ "compilerOptions": { "allowJs": true, "checkJs": true, "noEmit": true, "strict": false } }
```

```js
/**
 * @param {string} id
 * @param {{ includeDeleted?: boolean }} [opts]
 * @returns {Promise<import("./types").User>}
 */
export async function getUser(id, opts) { /* ... */ }
```

This finds real bugs — typos in property names, wrong argument counts, `undefined` arithmetic — with zero file churn, and it gives the team a preview of what strictness will feel like. It's also the right permanent answer for build scripts and config files nobody wants to convert.

Expect a large error count on first run. Don't fix them yet; the list is your map.

## Phase 1: let both coexist

`allowJs: true` means `.ts` and `.js` import each other freely. Confirm the build works with both before converting anything — a bundler or Jest config that only globs `.js` will silently skip your first `.ts` file and you'll debug the wrong thing.

Check, in order: bundler resolve extensions, test runner transform, path aliases, and the lint config's parser overrides. Convert one trivial file (a constants module), get it through CI, then continue. Proving the pipeline on a file with no logic separates toolchain problems from typing problems.

## Phase 2: convert leaves upward

Order by dependency depth, not by importance:

1. **Constants, enums, pure utilities** — no imports, easy types, immediate payoff everywhere they're used.
2. **Domain types and schemas** — define the shapes once, ideally as Zod schemas with inferred types (see `boundaries.md`). This is the highest-leverage step: once `User` exists as a real type, every subsequent conversion gets easier.
3. **Data access / API clients** — where boundary parsing goes. Converting these turns a whole layer of `any` into real types.
4. **Business logic** — now mostly mechanical, since its inputs and outputs are typed.
5. **UI components** — last; they have the most dependencies and the least logic.

Converting a leaf usually improves its consumers immediately, still in `.js`, because `checkJs` picks up the new types through imports. That's the compounding effect that makes bottom-up worth it.

Rename `.js` → `.ts`, then fix what the compiler reports. Resist restructuring at the same time: a diff that is *both* a conversion and a refactor is unreviewable, and when something breaks nobody can tell which half did it.

`ts-migrate` (Airbnb) and similar codemods can do a bulk pass and insert suppressions. They get you a compiling codebase quickly at the cost of a large backlog of `@ts-expect-error`. Reasonable for very large codebases; for anything under a few hundred files, hand conversion produces better types.

## Phase 3: ratchet strictness

Turning on `strict` globally in a mature codebase yields thousands of errors and nothing gets fixed. Ratchet instead, in this order — each flag is roughly independent and the early ones cost least:

1. `noImplicitAny` — usually the biggest batch, mostly mechanical.
2. `strictNullChecks` — the expensive one and the one that finds the most real bugs. Expect this to take the longest.
3. `strictFunctionTypes`, `strictBindCallApply`, `strictPropertyInitialization`.
4. `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes` — after `strict` is fully on.

Two ways to scope it. Per-directory `tsconfig` files that extend a base and override flags let converted areas be strict while legacy areas aren't. Or keep one config and track a **suppression count** — the number of `@ts-expect-error` comments — as a number that may only go down. A CI check on that count is a ratchet with almost no process cost.

Prefer `@ts-expect-error` over `@ts-ignore` everywhere: it *errors when the underlying problem is fixed*, so the suppressions clean themselves up as the code improves. Always with a reason on the same line:

```ts
// @ts-expect-error legacy-widget has no types; tracked in PLAT-482
widget.mount(el);
```

## Honest placeholders

While converting, you'll hit shapes you don't understand yet. The temptation is to invent a type that looks plausible. Don't — a wrong type is worse than a missing one, because it stops anyone from looking again and it lies to every consumer.

- **`unknown`** when you don't know the shape. It forces the caller to narrow, so the gap stays visible.
- **`any` with a comment** when `unknown` would cascade into too much work right now: `// TODO(PLAT-482): shape unknown, see legacy/report.js`.
- **A narrow partial type** covering only the fields actually used, which is honest and usually enough.

The difference between a migration that improves the codebase and one that just changes file extensions is whether the types ended up *true*.

## Untyped dependencies

In order of preference: install `@types/x` if it exists; check whether a newer version of the package ships its own types; write a minimal `.d.ts` covering only what you call; last resort, `declare module "x";` which types the whole module as `any` and should carry a TODO.

```ts
// types/legacy-charts.d.ts — only what we actually use
declare module "legacy-charts" {
  export interface ChartOptions { width?: number; height?: number; theme?: "light" | "dark" }
  export function render(el: HTMLElement, data: number[], opts?: ChartOptions): void;
}
```

Point `typeRoots` or an `include` at the folder so these get picked up. Keep them narrow — three honest functions beat a hallucinated full surface.

## Cleaning up `any`

Not all `any` is equal. Triage by blast radius:

1. **`any` in exported signatures of shared modules** — worst. Poisons every call site invisibly. Fix first.
2. **`any` in data-access / boundary code** — second. This is where a real type buys the most, and it's usually a schema away.
3. **`any` in local variables** — contained; fix opportunistically.
4. **`any` in tests and fixtures** — lowest priority. Often fine to leave.

Find them with `@typescript-eslint/no-explicit-any` as a warning plus `no-unsafe-assignment` / `no-unsafe-member-access` / `no-unsafe-call` / `no-unsafe-return` to find *implicit* spread — the `any`s you didn't write, which flowed in from an untyped dependency. Those four rules reveal a lot more than a grep for the word `any`.

When replacing an `any`, start from what the code actually does with the value rather than from what you assume it is. Hover types and a quick `console.log` of the real payload beat guessing.

## Keeping it from sliding back

The migration is done when nothing reintroduces the problem:

- `tsc --noEmit` in CI, blocking merge.
- `allowJs` off once the last `.js` is gone, so a new one can't appear silently.
- `no-explicit-any` at error level for new code (an eslint override scoped to migrated directories works well).
- The suppression count as a ratchet in CI.
- `strict: true` with no per-directory overrides left.

Each of these is cheap once true and prevents a specific way the codebase slides back. Turning them on *as* each becomes true — rather than at the end — is what keeps the migration from having a long tail.
