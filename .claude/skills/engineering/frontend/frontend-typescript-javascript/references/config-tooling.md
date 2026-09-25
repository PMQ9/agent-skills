# Config & Tooling

Read when setting up a project, tightening an existing one, debugging why the build passes but production breaks, or wiring type safety into CI.

## Contents

- [The load-bearing idea: build ≠ typecheck](#the-load-bearing-idea-build--typecheck)
- [tsconfig, option by option](#tsconfig-option-by-option)
- [The strict family](#the-strict-family)
- [Module resolution](#module-resolution)
- [Linting: what types can't catch](#linting-what-types-cant-catch)
- [Formatting](#formatting)
- [CI: making types load-bearing](#ci-making-types-load-bearing)
- [Monorepos and project references](#monorepos-and-project-references)
- [Performance when tsc gets slow](#performance-when-tsc-gets-slow)
- [Publishing a package](#publishing-a-package)

## The load-bearing idea: build ≠ typecheck

Every fast modern toolchain — esbuild, SWC, Vite, Bun, Next's compiler — **strips types without checking them**. They delete annotations and move on. This is why builds are fast, and it means a green `vite build` proves your code parsed, not that it type-checks.

The consequence: `tsc --noEmit` must run somewhere it can fail the pipeline. If it only runs in your editor, types are a suggestion. This single step is the difference between a codebase where types are trustworthy and one where they've quietly rotted.

## tsconfig, option by option

```jsonc
{
  "compilerOptions": {
    // — Output target —
    "target": "ES2022",            // what syntax to emit; match your runtime floor
    "lib": ["ES2023", "DOM", "DOM.Iterable"],  // what globals exist (omit DOM for server-only)
    "module": "ESNext",
    "moduleResolution": "Bundler", // or "NodeNext" — see below
    "jsx": "react-jsx",            // no React import needed in scope

    // — Correctness —
    "strict": true,                      // the whole family; non-negotiable for new code
    "noUncheckedIndexedAccess": true,    // arr[i] is T | undefined
    "exactOptionalPropertyTypes": true,  // `?: string` ≠ `| undefined`
    "noImplicitOverride": true,          // `override` keyword required
    "noFallthroughCasesInSwitch": true,
    "noImplicitReturns": true,
    "useUnknownInCatchVariables": true,  // included in strict; catch (e: unknown)

    // — Module semantics —
    "verbatimModuleSyntax": true,  // explicit `import type`; preserves side effects
    "isolatedModules": true,       // required by esbuild/SWC/Babel single-file transpile
    "esModuleInterop": true,
    "resolveJsonModule": true,

    // — Emit —
    "noEmit": true,                // a bundler emits; tsc only checks
    "skipLibCheck": true,          // don't typecheck node_modules .d.ts — big speed win
    "incremental": true,

    // — Ergonomics —
    "baseUrl": ".",
    "paths": { "@/*": ["./src/*"] }  // must be mirrored in the bundler's config too
  },
  "include": ["src", "*.config.ts"],
  "exclude": ["node_modules", "dist"]
}
```

Notes on the ones people get wrong:

- **`skipLibCheck: true`** is right for apps. Your dependencies' type errors are not your problem and checking them is slow. Library authors publishing types may want it off in a dedicated check.
- **`target` vs `lib`**: `target` controls emitted *syntax*, `lib` controls which *globals* the compiler believes exist. Setting `target: "ES2022"` but running on a runtime without `Object.groupBy` gives a runtime error the compiler allowed, because `lib` said it was there.
- **`paths`** only affects type resolution. The bundler, the test runner, and Node all need their own alias config, or you get "works in the editor, fails at runtime." `vite-tsconfig-paths` and equivalents exist to keep them in sync.
- **`allowImportingTsExtensions`** is needed when you write `.ts` in import specifiers (with `noEmit` or `rewriteRelativeImportExtensions`).

## The strict family

`strict: true` enables all of these; knowing what each does helps when migrating a codebase one flag at a time:

| Flag | Catches |
|---|---|
| `noImplicitAny` | Parameters and variables silently typed `any` |
| `strictNullChecks` | The big one — `null`/`undefined` no longer assignable everywhere |
| `strictFunctionTypes` | Unsound function parameter assignment (property syntax only) |
| `strictBindCallApply` | Wrong arguments to `.bind`/`.call`/`.apply` |
| `strictPropertyInitialization` | Class fields never assigned in the constructor |
| `useUnknownInCatchVariables` | `catch (e)` as `any` |
| `alwaysStrict` | Emits `"use strict"` |

Beyond the family, the two highest-value additions are `noUncheckedIndexedAccess` and `exactOptionalPropertyTypes`.

`noUncheckedIndexedAccess` is the one people disable in frustration. It's telling the truth — `arr[5]` on a 3-element array *is* `undefined` — and the friction it causes is mostly in code that was already assuming too much. The escape when you know better is a `!` at one audited spot, or destructuring with a default.

`exactOptionalPropertyTypes` distinguishes "property absent" from "property present and `undefined`," which matters for anything that iterates keys or spreads into an API payload — sending `{ name: undefined }` is not the same request as omitting `name`.

## Module resolution

Pick by **who resolves your imports at runtime**:

- **`"Bundler"`** — Vite, webpack, Next, esbuild resolve. Write extensionless imports (`./utils`). Easiest, and correct for app code.
- **`"NodeNext"`** — Node resolves, honoring `exports` maps and `"type"`. You must write extensions, and you write `.js` even in `.ts` source because you're naming the emitted file. Correct for published libraries and plain Node services.
- **`"Node10"`** (formerly `"Node"`) — legacy; ignores `exports` maps. Only for old projects you're not touching.

Symptoms of a mismatch: "Relative import paths need explicit file extensions" (you're on NodeNext, drop back to Bundler or add extensions), or an import that resolves in the editor but 404s in the built output (bundler alias not mirroring `paths`).

## Linting: what types can't catch

Types don't know about floating promises, `await` on a non-promise, `any` leaking through a call chain, an unhandled union member, or a `React.useEffect` with a wrong dependency array. Type-aware lint rules do.

```js
// eslint.config.js (flat config)
import tseslint from "typescript-eslint";

export default tseslint.config(
  ...tseslint.configs.strictTypeChecked,
  ...tseslint.configs.stylisticTypeChecked,
  {
    languageOptions: { parserOptions: { projectService: true } },
    rules: {
      "@typescript-eslint/no-floating-promises": "error",
      "@typescript-eslint/no-misused-promises": "error",     // async fn passed where void expected
      "@typescript-eslint/switch-exhaustiveness-check": "error",
      "@typescript-eslint/no-unnecessary-condition": "warn", // finds checks the types prove dead
      "@typescript-eslint/consistent-type-imports": "error",
    },
  },
);
```

`strictTypeChecked` is noisy on a codebase that's never had it; introducing it as warnings and ratcheting to errors per-directory works better than a 3,000-problem first run that everyone learns to ignore.

`projectService: true` (typescript-eslint v8+) replaces the old `project` array and is substantially faster and less fussy about which files are included.

**Biome** is the fast alternative: one binary for lint + format, ~10-25x quicker, no config archaeology. It does not do type-aware linting, so it can't catch floating promises. A common arrangement is Biome for format and syntactic rules on every save, typescript-eslint with type-aware rules in CI.

## Formatting

Pick one, enforce it mechanically, stop discussing it. Prettier is the default everyone recognizes; Biome is faster and nearly compatible; `dprint` is another fast option. Run it in a pre-commit hook (`lint-staged` + `husky`, or `simple-git-hooks` for something lighter) so formatting never appears in a review diff.

Turn off stylistic lint rules that overlap the formatter — fighting between the two produces commits that flip back and forth.

## CI: making types load-bearing

A minimal pipeline that actually protects the codebase:

```yaml
- run: pnpm install --frozen-lockfile   # fail on lockfile drift, don't resolve fresh
- run: pnpm typecheck                   # tsc --noEmit  ← the one people forget
- run: pnpm lint
- run: pnpm test
- run: pnpm build
```

`--frozen-lockfile` (or `npm ci`) is what makes CI reproducible; a floating range resolving differently than it did locally is a classic Friday-afternoon mystery.

Worth adding as the project grows: `publint` and `attw` for published packages, a bundle-size check on the client entry, and `tsc --noEmit` on test files too (they're the code most likely to be quietly `any`).

## Monorepos and project references

For a workspace with shared packages, **project references** let `tsc` build and check each package independently and cache the results:

```jsonc
// apps/web/tsconfig.json
{ "references": [{ "path": "../../packages/ui" }, { "path": "../../packages/schemas" }] }
```

Referenced projects need `composite: true` and emit declarations. `tsc --build` then does incremental, dependency-ordered builds. The payoff arrives at a few packages and grows from there; below that it's ceremony.

Turborepo or Nx on top handles task orchestration and remote caching. The pattern that matters regardless of tool: a shared `tsconfig.base.json` that each package extends, so strictness is defined once.

For internal packages, publishing raw TS (`"exports": { ".": "./src/index.ts" }`) and letting the consuming app's bundler compile it avoids a build step entirely — good for app-only monorepos, not for anything published externally.

## Performance when tsc gets slow

Diagnose before optimizing: `tsc --noEmit --extendedDiagnostics` shows where time goes, and `--generateTrace trace/` produces a profile you can open in `chrome://tracing`.

Usual culprits, in rough order of frequency: `skipLibCheck` off; a giant union or deeply recursive conditional type (check-time explodes non-linearly); `include` pulling in test fixtures or generated files; missing project references in a monorepo; and inferred return types on large exported functions (annotating them explicitly can cut work dramatically, since the compiler otherwise re-derives them at every call site).

TypeScript's native-port compiler (`tsgo`) offers order-of-magnitude speedups and is worth trying on large projects as it stabilizes; the config surface is the same.

## Publishing a package

The details that break consumers:

```jsonc
{
  "type": "module",
  "exports": {
    ".": { "types": "./dist/index.d.ts", "import": "./dist/index.js", "require": "./dist/index.cjs" }
  },
  "files": ["dist"],
  "sideEffects": false     // lets bundlers tree-shake aggressively — only if true!
}
```

`types` must come first in each condition block, the paths must actually exist, and `sideEffects: false` is a lie that silently drops your CSS imports or polyfills if the package does have side effects. Run `publint` and `attw --pack` in CI; between them they catch nearly every shape of broken package.
