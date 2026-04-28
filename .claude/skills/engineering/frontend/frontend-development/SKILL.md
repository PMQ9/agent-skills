---
name: frontend-development
description: Use this skill for any browser-facing UI work that isn't tied to a specific framework — HTML/CSS/JS fundamentals, browser APIs, web performance, asset loading, forms, state on the client, error boundaries, build tooling (Vite, esbuild, Turbopack, webpack), package management, monorepos, design systems, theming, internationalization, browser compatibility, progressive enhancement, and the general shape of a frontend codebase. Trigger this for "the page is slow," "the bundle is too big," "why is the image laying out wrong," "set up a frontend project," "browser support," "form validation," CSS architecture questions, or any frontend question that doesn't name React/Vue/Svelte/etc. Prefer the framework-specific skill (`frontend-react-next`, etc.) when the user names a framework.
---

# Frontend Development

A frontend's job is to render data the user cares about, accept input, and stay out of the way. Almost every frontend problem in production is one of three things: **the wrong thing is on screen** (state bug), **it's too slow** (performance), or **it doesn't work for someone** (compat / a11y / network). Most of this skill is about how to avoid those three failure modes structurally rather than fix them later.

Framework-specific guidance lives in skills like `frontend-react-next`. This skill covers what's true regardless of framework.

## The platform is the foundation

Before reaching for a library, know what the browser already does. The platform in 2026 covers far more than it did when the prevailing wisdom about frontends was set:

- **CSS** has nesting, container queries, `:has()`, subgrid, anchor positioning, `@layer`, `color-mix()`, view transitions, scroll-driven animations.
- **HTML** has `<dialog>`, `popover`, `<details>`/`<summary>`, native lazy-load (`loading="lazy"`), `inert`, form validation, `<input type="...">` with rich semantics on mobile.
- **JS** has structured clone, `AbortController`, `Intl.*` for everything localization-shaped, `URL`/`URLSearchParams`, top-level `await`, `Array.prototype.at`/`groupBy`, native fetch, `requestIdleCallback`.
- **Browser APIs** — `IntersectionObserver`, `ResizeObserver`, `MutationObserver`, `BroadcastChannel`, `View Transitions`, `Web Locks`, `File System Access`.

A surprising amount of code in a typical codebase is reimplementing platform features. Before you import `react-modal`, check `<dialog>`. Before `react-intersection-observer`, check the API directly. Before a CSS-in-JS framework with theme tokens, check `@property` and CSS custom properties.

## Project shape

A reasonable default for a new app:

```
src/
  app/                  # routing & top-level shell
  features/             # vertical slices — feature owns its UI + data + state
    students/
      api.ts            # network calls
      hooks.ts          # data hooks (useStudents, etc.)
      components/       # feature-specific components
      types.ts
  components/           # cross-feature, app-aware components (AppHeader, etc.)
  ui/                   # design-system primitives, no app knowledge (Button, Input)
  lib/                  # framework-free helpers (formatDate, parseDuration)
  styles/               # tokens, globals, resets
public/
```

Two patterns to follow consistently:

1. **Vertical feature folders, not horizontal type folders.** `features/students/` beats `components/`, `hooks/`, `api/` at the top level. Code that changes together lives together.
2. **`ui/` knows nothing about the app.** A `Button` doesn't import `useUser`. If you find yourself wanting that, the component belongs in `components/`, not `ui/`.

Avoid the "everything goes in `components/`" pattern. After 200 components it's unsearchable, and the import graph becomes an undirected blob.

## Build tooling

For most new projects in 2026, the choice is **Vite** (with esbuild + Rollup under the hood) or the framework's blessed bundler (Turbopack for Next.js, etc.). Webpack is a legacy choice; `create-react-app` is dead. Reasons Vite is the default-good answer:

- Native ESM in dev — no bundling on every save, just a transform.
- Fast cold start, fast HMR.
- Sane production builds via Rollup with code splitting that mostly works without configuration.

Don't fight the bundler. If you find yourself writing custom webpack plugins to make basic things work, you're either doing something exotic (sometimes legitimate) or working around a project shape problem (more often).

## Package management

`npm`, `pnpm`, or `yarn berry`. Pick one and never let two coexist. **`pnpm` is the most defensible choice today**: faster, disk-efficient, strict about phantom dependencies. The strictness catches a real class of bug — accidentally relying on a transitive dep you don't declare.

Lockfile is committed. Lockfile is **respected** in CI (`npm ci`, `pnpm install --frozen-lockfile`). A floating dep (`"react": "^18"`) in CI is a flake waiting to happen.

## TypeScript

Use it. The argument against TS in 2026 is harder to make than the argument for. Keep `strict: true`. The cost of strictness is paid once when you set the project up; the cost of *not* having strictness compounds for the project's lifetime.

```jsonc
// tsconfig.json — sensible defaults
{
  "compilerOptions": {
    "target": "ES2022",
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "strict": true,
    "noUncheckedIndexedAccess": true,    // arr[0] is T | undefined
    "exactOptionalPropertyTypes": true,
    "noImplicitOverride": true,
    "skipLibCheck": true,                // fast; libs aren't your problem
    "verbatimModuleSyntax": true,        // forces explicit `import type`
    "jsx": "react-jsx"
  }
}
```

Two specific habits matter more than "use TypeScript":

- **Type the API boundary.** Whatever your network response shape is, parse it (Zod, Valibot, Effect Schema) at the edge. Don't let `unknown` from `fetch().json()` propagate as `any` through your app — that's how runtime crashes ship.
- **Don't `as` your way out of problems.** Type assertions are escape hatches. Each one is a place where the type system is lying. Audit them.

## CSS architecture

Pick **one** primary approach. Mixing four CSS approaches in one app is the most common reason a frontend feels "messy" even when individual pages look fine.

| Approach | When |
|---|---|
| **Tailwind** | Default-good for new apps. Constrains the design space, eliminates CSS-naming bikeshedding, ships only used utilities. Pair with a tokens layer. |
| **CSS Modules** | When you want real CSS, scoped, with no runtime. Excellent for component libraries. |
| **Plain CSS + cascade layers (`@layer`)** | When the team is comfortable with CSS and the design is bespoke. Requires discipline. |
| **CSS-in-JS (styled-components, emotion)** | Avoid for new projects. Runtime cost; SSR complexity; the ergonomic edge is gone now that Tailwind / CSS Modules / vanilla extract exist. |
| **Vanilla Extract / PandaCSS** | When you want type-safe styles + zero runtime. Great choice if it fits your team. |

Whatever you pick, define **design tokens** centrally (colors, spacing, type scale, radii, shadows, motion) and reference them everywhere. Hard-coded `#3b82f6` and `padding: 12px` scattered across files is the texture of an unmaintainable design.

## Layout: pick the right tool

- **Flexbox** — one-dimensional layouts, anything where content size determines layout (toolbars, button groups, simple stacks).
- **Grid** — two-dimensional layouts, anywhere the layout is fixed and content fits in (page shells, card grids, dashboards).
- **`gap`** is your friend — beats margins for spacing flex/grid children.
- **Container queries** (`@container`) — when a component should respond to its container's width, not the viewport's. This is what you actually wanted from media queries half the time.
- **`aspect-ratio`** — kill the padding-bottom hack.
- **Logical properties** (`margin-inline`, `padding-block`) — better for i18n, and consistently shorter to type.

Avoid `position: absolute` for layout. It's for overlays, tooltips, popovers — things outside flow. Using it to "just put the thing where I want it" produces fragile layouts that break with content changes.

## Forms

The single most under-appreciated thing about HTML: **forms work without JavaScript.** A `<form action="..." method="post">` submits. Inputs have `name`, validation attributes, mobile keyboards based on `type`, and labels via `<label for="...">`. Use them.

Then enhance with JS for: client-side validation feedback, partial submission, optimistic UI, multi-step flows. The base case still works.

Validation: do it in three places, with the same rules.

1. **HTML attributes** (`required`, `pattern`, `minlength`) for cheap baseline.
2. **Schema-based** (Zod / Valibot) for the rich case — same schema in client and server.
3. **Server**, always, because the client is untrusted.

Never trust client-side validation alone. The form library is for UX, not security.

For accessibility: every input has a label, errors are announced, and submit failures move focus to the first error. The full a11y picture lives in the `accessibility-wcag` skill.

## State on the client

Categorize state before deciding how to manage it:

| Kind | Example | Where it lives |
|---|---|---|
| **Server state** | List of students, current user | A query cache (TanStack Query, SWR). Don't put it in a Redux store. |
| **URL state** | Filters, pagination, selected tab | The URL. Search params. Survives reload, sharable. |
| **Local UI state** | Is the menu open, current input value | Component-local (`useState`, framework equivalent). |
| **Cross-component UI state** | Theme, sidebar open, toast queue | Lifted to a small store (Zustand, jotai, signals, framework context). |
| **Persistent client state** | Drafts, "remember me" | `localStorage` / `IndexedDB`, hydrated on load. |

Most "state management" library debates are between people who've conflated these categories. Once you split them, server state is a query cache, URL state is the URL, and almost nothing remains for a global store. The global store gets tiny.

The default *wrong* answer: putting fetched data into a global Redux store and re-implementing caching, deduplication, and refetch-on-focus by hand. Use a query cache.

## Performance: the budget mindset

Pick a **performance budget** at project start and enforce it in CI. Vague "let's make it fast" loses to concrete "JS bundle for the homepage is < 150 KB gzipped, LCP < 2.5s on slow 4G."

The numbers that matter (Core Web Vitals, 2026 thresholds):

- **LCP** (Largest Contentful Paint) — < 2.5s. Hero image, hero text. Ship it eagerly.
- **INP** (Interaction to Next Paint) — < 200ms. Replaced FID. The thing users feel.
- **CLS** (Cumulative Layout Shift) — < 0.1. Reserve space for images, ads, late-loaded content.

Measure on the **75th percentile of real users**, not your dev machine. Use the web-vitals library + a real-user monitoring tool (Sentry, Datadog RUM, SpeedCurve, or DIY into your analytics).

### The big levers

In rough order of impact:

1. **Don't ship JS the page doesn't need yet.** Code-split by route. Code-split by interaction (modal contents, charts, rich editors load when opened). Server-render or SSG where you can. Move logic to the server.
2. **Optimize the LCP element.** Usually a hero image. Serve it as AVIF/WebP at the right size with `srcset`. Preload it. Don't lazy-load above-the-fold images.
3. **Don't block the main thread.** Long tasks > 50ms are the cause of bad INP. Break them up; move CPU-bound work to a Web Worker.
4. **Cache aggressively at the edge.** Static assets `Cache-Control: public, max-age=31536000, immutable` (with content-hashed filenames). HTML often `s-maxage` with stale-while-revalidate.
5. **Compress.** Brotli for text. Image formats appropriate to content. Subset fonts (or use `font-display: swap` and a system fallback).
6. **Minimize layout shift.** Width + height on images. `aspect-ratio` on media. Reserved space for late content.

### Things that don't help as much as people think

- React rendering optimizations (memo, useMemo) when the actual problem is bundle size or network waterfalls.
- Switching frameworks. Most "X is slow" problems aren't X.
- Service workers. Useful for offline; rarely the right first lever for perf.

### Things to actually measure

Open DevTools → Performance → record a real interaction, look at the flame graph. Network tab → see the waterfall. Lighthouse for synthetic, RUM for real. Don't optimize blind.

## Images

The largest source of bytes in most pages.

```html
<!-- Modern responsive image -->
<img
  src="/hero-1280.jpg"
  srcset="/hero-640.avif 640w, /hero-1280.avif 1280w, /hero-2560.avif 2560w"
  sizes="(min-width: 1024px) 50vw, 100vw"
  width="1280"
  height="720"
  alt="..."
  loading="lazy"        <!-- but NOT for above-the-fold/LCP image -->
  decoding="async"
/>
```

- Always `width` and `height`. Even with responsive layouts. They establish aspect ratio and prevent CLS.
- `loading="lazy"` for below-the-fold. Native, no JS.
- `<picture>` only when you need *art direction* (different crop per breakpoint). For "same image, different size," `srcset` + `sizes` is enough.
- AVIF > WebP > JPEG for photos. SVG for vectors. PNG only when AVIF/WebP would lose alpha transparency you need.
- Use an image CDN (Cloudinary, imgix, Cloudflare Images, Vercel Image Optimization) so you stop hand-tuning sizes. Pay the bytes you'd pay anyway, get the variants for free.

## Fonts

Web fonts are a perf trap. Each weight you load is bytes and a re-flow.

- **Self-host** woff2 for control. Use a service only for prototyping.
- **Subset** to the characters you actually use. Latin only? `unicode-range`.
- **`font-display: swap`** (or `optional`) — never the default `block`. Show the system font first.
- **Preload** the critical font: `<link rel="preload" href="..." as="font" type="font/woff2" crossorigin>`.
- **Variable fonts** when you ship 3+ weights of the same family — one file replaces several.

Often the right answer is "use the system font stack." `font-family: ui-sans-serif, system-ui, ...` — fast, native, free.

## Network and data fetching

Frontend fetch patterns, ranked by how much pain they cause when wrong:

1. **Waterfalls.** Component A fetches, then component B (a child) fetches based on A's result. This serializes things that should be parallel. Hoist the fetches up, or use a framework that handles this (Next.js parallel data fetching, Relay).
2. **N+1 on the client.** A list of 50 items, each component fetches its details. Batch on the server, or fetch the joined view.
3. **No abort handling.** User navigates away, in-flight request resolves and writes to a now-unmounted component or stale state. Use `AbortController`; pass `signal` to fetch.
4. **No caching.** Same query refetched on every mount. A query cache solves this for free.
5. **No error boundary.** A network failure in one card crashes the page. Scope error boundaries per region.
6. **No retry, no backoff.** First transient failure surfaces as "something went wrong" forever. Query libraries do this for you.

```ts
// Minimum-decent fetch with abort + parse + typed errors
async function getStudent(id: string, signal?: AbortSignal): Promise<Student> {
  const res = await fetch(`/api/students/${id}`, { signal });
  if (!res.ok) throw new ApiError(res.status, await res.text());
  return StudentSchema.parse(await res.json());
}
```

## Routing

Three rough archetypes:

- **Server-rendered routes** (Next.js, Remix, SvelteKit, Astro) — the framework owns routing, data loaders run server-side. Default-good for content sites and most apps.
- **Client-side router** (React Router) — when the app is fully a SPA behind auth. Combine with a query cache.
- **Hash routing** — only for static-host environments where you can't control rewrites. Otherwise, real URLs.

URL state is your friend: filters, sort, pagination, selected tab, modal-open state — all of it goes in search params if it should survive reload or be sharable. Use `URLSearchParams` directly or a wrapper like `nuqs`.

## Errors

A frontend that crashes is one component's bug becoming the whole app's outage. Defend in layers:

- **Error boundaries** around large regions (per route, per major widget). The fallback shows a useful message and a retry, not a blank page.
- **Network errors** caught at the data layer with typed error objects (`new ApiError(status, message)`), not stringly-typed `catch (e)`.
- **Validation errors** shown inline next to the field, not in a global toast.
- **Unexpected errors** reported to Sentry (or equivalent) with sourcemaps uploaded so the stack trace is readable.
- **`onerror`** and **`onunhandledrejection`** handlers as a final net.

Don't swallow errors. `catch {}` is how silent corruption ships.

## Browser support

Decide early, write it down. "Last 2 versions of Chrome/Firefox/Safari/Edge + iOS 16+" is a reasonable default for a 2026 consumer app. Internal/enterprise apps may need older.

Set browserslist accordingly; let the build target it. Don't ship ES5 if you don't need to — the size savings of modern output are real.

Test on real devices and slow networks. BrowserStack, Sauce Labs, or a drawer of old phones. The dev machine is a lie.

## Accessibility (briefly here, more in `accessibility-wcag`)

The non-negotiables, even at MVP:

- Real semantic HTML. `<button>`, not `<div onClick>`. `<a href>`, not `<div onClick>` styled like a link.
- Labels on every form input.
- Color contrast meets WCAG AA (4.5:1 for body text).
- Focus is visible. Don't `outline: none` without replacing it.
- Keyboard works. Tab through the whole page; use the app without a mouse.
- Images have meaningful `alt` (or `alt=""` if decorative).

These are cheap if you design them in, expensive to retrofit. The full skill is `accessibility-wcag`.

## Internationalization

If there's any chance you'll go beyond one language:

- Use `Intl.*` for dates, numbers, currency, relative time, list/plural formatting. It's been there for years; people still pull in heavy libraries to do what `Intl.NumberFormat` does in one line.
- Externalize strings from day one. `t("students.title")`, not `"Students"` in JSX. Even if you only have English, the cost is tiny and the conversion later is enormous.
- Use a real i18n library (i18next, FormatJS, Lingui) for plurals and interpolation. Don't roll your own.
- Plan for **RTL**. Use logical properties (`margin-inline-start`, not `margin-left`), `dir` attribute on `<html>`, and test with Arabic or Hebrew before claiming support.

## Common anti-patterns

- Using `useEffect` (or framework equivalent) to sync server data into local state. Use a query cache.
- "Isomorphic" `window` access without a guard, breaking SSR.
- Storing JWTs in `localStorage` (vulnerable to XSS exfiltration). Use HTTP-only cookies for session tokens.
- One giant CSS file at 12,000 lines that nobody dares touch.
- Dozens of `z-index: 9999`s competing for the top of the stacking context. Define a small set of named layers (`--z-modal: 100`).
- Shipping the entire icon set when you use 12 icons. Tree-shakable icon libs (lucide, heroicons via individual imports).
- Re-implementing `<dialog>`, `<details>`, `<select>` from divs. Each rewrite ships an a11y bug.
- A "loading" state that is just a spinner for 3 seconds because data fetches in series. Fix the waterfall, not the spinner.
- Treating mobile as an afterthought. Most users are on phones; design and test mobile-first.
- 47 `console.log`s left in production. Use a logger that ships nothing in prod, or a build step that strips them.
- Pulling in a 90 KB date library to format one date. `Intl.DateTimeFormat`. Or `date-fns` (tree-shakable). Avoid moment.

## Tooling defaults worth keeping

- **Formatter**: Biome or Prettier. Pick one, run on save and in CI.
- **Linter**: ESLint or Biome. Wire `eslint-plugin-jsx-a11y` if doing React.
- **Type checker** in CI as a separate, required step.
- **Lighthouse CI** or equivalent on every PR for the homepage and one or two key flows. Fail the build on regressions past your budget.
- **Bundle visualizer** (`rollup-plugin-visualizer`, `@next/bundle-analyzer`) — run it monthly. Surprises are the norm.
- **Sourcemaps** uploaded to your error tracker. A stack trace into minified `a.b.c` is useless.
- **`pre-commit`** for fast checks (format, lint, typecheck on changed files).

## When to reach for a framework

Plain HTML/CSS/JS is the right answer more often than a typical 2020-era frontend developer was trained to believe. For:

- A landing page → Astro or plain HTML.
- A blog or marketing site → Astro, 11ty, or framework SSG.
- A docs site → Docusaurus, Nextra, Astro Starlight.
- A form-heavy internal app → server-rendered (Rails, Django, Phoenix, Next.js with server actions). The interactivity is small.
- A rich SPA (canvas editor, dashboard with live data, complex stateful UI) → React/Vue/Svelte/Solid. This is what they're for.

The mistake is reaching for the SPA hammer for problems where the platform has already solved 90% of it. Choose the lightest tool that meets the requirement.
