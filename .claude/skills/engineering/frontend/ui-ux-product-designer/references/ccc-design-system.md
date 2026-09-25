# CCC House Style — Design System Reference

The shared design language across Vanderbilt College of Connected Computing (CCC) tools, extracted from the `vandy-ccc-research-admin` monorepo (`@vandy/ui2`, shadcn + Tailwind v4) and `secondary-appointment-helper` (hand-rolled primitives on Tailwind v3). Where the two differ, this file gives the current, shipped convention and notes the variant. Copy-ready token definitions live in `../assets/design-tokens.css`.

**Contents:** 1) Foundations & philosophy · 2) Color tokens (light/dark) · 3) Typography · 4) Spacing, radii, shadows, motion · 5) Component conventions · 6) House rules (the non-obvious ones).

---

## 1. Foundations & philosophy

- **Brand:** Vanderbilt gold + black, on a **cool neutral (Zinc) gray scale**. The gray is pure/near-chroma-zero, not warm.
- **Tooling:** Tailwind for utilities. New code uses **shadcn/ui on Radix primitives**, with variants via **`cva`** and class-merge via **`cn()`** (`twMerge(clsx(...))`). Older code hand-rolls the same looks with `@apply` component classes and `Record<Variant,string>` maps — same visual result, choose whichever matches the project you're in.
- **Tokens are semantic and CSS-variable-based.** Components reference `bg-card`, `text-muted-foreground`, `border`, not raw hex. This is what makes light/dark and density retuning possible from one place. Never hardcode a hex in a component.
- **Accessibility is a hard gate**, not a finish. Contrast ratios are documented next to tokens and enforced by a check script; focus rings are universal; motion respects `prefers-reduced-motion`; rows are de-emphasized with color, never `opacity`.

---

## 2. Color tokens

Two token dialects exist in the wild. Prefer the **shadcn semantic set** (`background`, `foreground`, `card`, `primary`, `muted-foreground`, `border`, …) for new work. The older project uses a `theme-*` set (`theme-canvas`, `theme-elevated`, `theme-text-primary`, …) with identical intent. Both resolve to the same Zinc-based palette below.

### Core semantic tokens (shadcn dialect)

| Token | Light (hex ≈) | Dark (hex ≈) | Role |
|---|---|---|---|
| `background` | `#FFFFFF` | `#09090B` | page canvas |
| `foreground` | `#18181B` | `#F4F4F5` | primary text (16:1 on card) |
| `card` / `popover` | `#FFFFFF` | `#18181B` | elevated surfaces (cards, modals, header) |
| `card-foreground` | `#18181B` | `#F4F4F5` | text on cards |
| `primary` | `#18181B` (near-black) | `#EDEDED` | primary buttons, active pills, badges |
| `primary-foreground` | `#FAFAFA` | `#18181B` | text on primary |
| `secondary` / `muted` / `accent` | `#F4F4F5` | `#27272A` | subtle fills, washes, hover rows |
| `muted-foreground` | `#71717A` | `#A1A1AA` | secondary/caption text (~5:1 on white, AA) |
| `border` / `input` | `#E4E4E7` | `#3F3F46` | hairlines, control borders |
| `ring` | `#71717A` | `#82828C` | focus ring (≥3:1 non-text) |
| `destructive` | `#DC2626` | `#F87171` | error/danger control |

The Zinc scale these draw from: `50 #FAFAFA · 100 #F4F4F5 · 200 #E4E4E7 · 300 #D4D4D8 · 400 #A1A1AA · 500 #71717A · 600 #52525B · 700 #3F3F46 · 800 #27272A · 900 #18181B`.

> The older `theme-*` dialect maps 1:1: `theme-canvas`=background, `theme-elevated`=card, `theme-fill`=secondary/muted, `theme-text-primary`=foreground, `theme-text-secondary`=`#3F3F46`, `theme-text-tertiary`=`#52525B` (captions/labels, 7.6:1), `theme-border`=border, `theme-border-strong`=`#71717A` (form borders).

### Brand — Vanderbilt gold & black

Gold is a **bright metal, not a text color.** Use it for brand marks, and on dark surfaces for rails/accents; for gold *text on light*, use the darkened `gold-ink`.

| Token | Value | Use |
|---|---|---|
| `gold` (bright) | `#F2CC0C` / oklch(0.75 0.13 85) | logo, dark-surface rails/rings — **not** body text on light |
| `gold-ink` (text-safe) | `oklch(0.545 0.11 85)` ≈ `#B08900` | gold text on light: 5.0:1 on white, 4.5:1 on gray washes |
| `gold-wash` | `#F4F4F5` (neutralized) | selected/hover row wash — currently a neutral gray; name kept for compat |
| black | `#000000` | Vanderbilt Black; `primary` is a near-black `#18181B` for buttons/chrome |

The full gold ramp (secondary-appointment-helper) runs amber at the high end — `50 #FFFBEB · 500 #F2CC0C · 600 #D97706 · 700 #B45309 · 900 #78350F`. Navy `#6366F1` serves as a secondary/info accent there.

### Status colors (each has a text tone + a paired tint background)

All AA-checked ≥4.5:1 on white.

| Status | Text tone | Tint bg |
|---|---|---|
| success / ok | green-700 `#15803D` / oklch(0.527 0.154 150) | green-50 `#F0FDF4` |
| error / danger | red-700 `#B91C1C` / oklch(0.505 0.213 27.5) | red-50 `#FEF2F2` |
| info | blue-700 `#1D4ED8` / oklch(0.488 0.243 264) | blue-50 `#EFF6FF` |
| warning | amber-700 `#B45309` / oklch(0.555 0.163 49) | amber-50 `#FFFBEB` |

Workflow-status pills (application states) map to these: e.g. submitted=info/blue, in-review=warning/amber, approved/complete=success/green or neutral gray, rejected=error/red, action-needed=amber. Keep a single status→color map in one file (`utils/status.ts`) rather than inline per badge.

### Charts

Recharts can't read the theme class, so resolve chart colors in JS: grid `#E4E4E7`/dark `#3F3F46`, ticks `#71717A`/`#A1A1AA`, tooltip bg `#FFFFFF`/`#27272A`. Categorical series palette: `#E8703A`, `#3AA0A0`, `#2E5C8A`, `#E0B23A`, `#D98A3A` (oklch chart-1..5).

### Dark mode

`darkMode: 'class'` (v3) / `@custom-variant dark` (v4). Toggle by adding `.dark` to `<html>`. In the shipped monorepo dark mode is defined but has **no live toggle**; the standalone app has a full `system/light/dark` toggle with a pre-paint init script to avoid FOUC and persists to `localStorage`. Cards drop their shadow in dark mode (`dark:shadow-none`); surfaces get lighter with elevation (canvas `#09090B` → card `#18181B`).

---

## 3. Typography

| Role | Face | Weights | Size / classes |
|---|---|---|---|
| UI / body | **Public Sans** (monorepo) or **Inter** (standalone) | 400/500/600 | `text-sm` (14px) — the workhorse |
| Display / hero | **Source Serif 4** or **Poppins** — opt-in only | 600/700 | page hero `text-3xl/4xl font-bold` |
| Data / mono | **IBM Plex Mono** | 400/500 | record IDs, tokens, ⌘K kbd — `font-mono` |

Loaded via `next/font/google` (monorepo) or Google Fonts `@import`/`<link>` (standalone), wired to `--font-sans` / `--font-serif` / `--font-mono` with system fallbacks.

**Type scale by role:**

- Page title: `text-xl font-semibold tracking-tight` (~20px)
- Card/section title: `font-semibold leading-none` (~16px)
- Body / table / buttons: `text-sm` (14px) — dominant
- Labels / captions / table headers / breadcrumbs: `text-xs` (12px), `font-medium`, `text-muted-foreground`; headers add `uppercase tracking-wider`
- Stat/metric number: `text-[28px] font-bold tabular-nums`, label `text-xs uppercase tracking-wide`
- KBD hint: `text-[10px] font-mono`

Use `.tnum { font-variant-numeric: tabular-nums lining-nums; }` on money/date/aligned-number columns. A `data-font-size` on `<html>` scales the whole rem-based UI (compact ~15px / default 16px / large ~18px) in the standalone app.

---

## 4. Spacing, radii, shadows, motion

**Spacing** — standard 4px Tailwind scale used on an 8px rhythm (`gap-2`=8, `gap-4`=16, `gap-6`=24, `gap-8`=32). Card interior `py-6`/`px-6` (24px). Sidebar `232px` wide, padding `20px 14px`. Main content `padding: 28px 32px; max-width: 1200px`. Form grid: `repeat(auto-fit, minmax(230px,1fr))`, `gap: 10px`. The standalone app abstracts spacing behind density tokens (`--card-p`, `--stack`, `--row-gap`) so a compact/cozy toggle can retune everything — mirror that if density matters.

**Control heights:** default `h-9` (36px), `sm h-8` (32px), `xs h-6` (24px), `lg h-10` (40px). Inputs `h-9`. Icon buttons `size-9/8/6`.

**Border radius:** base `--radius: 0.5rem`. Cards `rounded-xl`; buttons/inputs `rounded-md`; badges/pills/avatars `rounded-full`; small chips `rounded-lg`. (Standalone app is rounder: cards/modals `rounded-2xl`, buttons/inputs `rounded-xl`.)

**Shadows:** deliberately minimal. Cards use **`shadow-xs` at most — no heavy drops.** (Standalone app uses soft custom shadows `shadow-soft`/`shadow-medium` with a `hover:-translate-y-0.5` lift and a gold-glow `shadow-vanderbilt` on active nav; either is fine, but keep it subtle.)

**Motion:** 150ms ease-out for hover/expand, ~200ms for drawer slides. Everything behind `@media (prefers-reduced-motion: reduce)`, which neutralizes transitions/animations entirely. Entrance animations (`fade-in`, `slide-up`) are fine but short.

---

## 5. Component conventions

Design from this kit; specify variants + states, not pixels.

**Button** — `inline-flex items-center justify-center gap-2 rounded-md text-sm font-medium`, focus `ring-[3px] ring-ring/50`, `disabled:opacity-60`.
Variants: `default` (bg-primary/near-black, white text), `destructive` (red), `outline` (border + `bg-background` + `shadow-xs`, hover `bg-accent`), `secondary` (`bg-secondary`), `ghost` (hover `bg-accent` only), `link` (underline on hover). Sizes `h-9 px-4` default, `h-8`, `h-6`, `h-10 px-6`, plus icon-only sizes. Primary brand button in the standalone app is **gold with black text** (`bg-gold-500 text-black`) — use that when a page wants a Vanderbilt-forward CTA. Icon-only buttons **require** an `aria-label`. Loading state shows an inline spinner + `aria-busy` and disables.

**Card** — `rounded-xl border bg-card py-6 shadow-xs`, `flex flex-col gap-6`. Subparts: `CardHeader` (with optional action slot), `CardTitle` (`font-semibold leading-none`), `CardDescription` (`text-sm text-muted-foreground`), `CardContent` (`px-6`), `CardFooter`. Interactive cards add `hover:bg-accent cursor-pointer` (and a subtle lift in the standalone app).

**Input / Field** — `h-9 w-full rounded-md border border-input bg-transparent px-3 py-1 text-base md:text-sm shadow-xs`, focus `border-ring ring-[3px] ring-ring/50`, `aria-invalid` → red border/ring. Label `text-sm font-medium mb-1` with a red `*` for required. Wire `aria-invalid`, `aria-describedby` (hint + error ids), and put the error in a `role="alert"` `<p>`. Forms use **react-hook-form + Zod**; validation is schema-driven (don't rely on the native `required` attribute alone).

**Badge** — `rounded-full border px-2 py-0.5 text-xs font-medium`. Variants `default` (near-black pill), `secondary`, `destructive`, `outline`. For workflow status, drive tone from the shared status map (tone keys `neutral/green/red/blue/amber` → status tint bg + text tone).

**Table** — wrap in `overflow-x-auto`. `TableHead`: `h-10 px-2 text-xs font-medium text-muted-foreground` (quiet headers, uppercase optional). `TableRow`: `border-b hover:bg-accent`, selected row `data-[state=selected]:bg-accent`. `TableCell`: `p-2 align-middle`. Opt-in `responsive` prop collapses to **stacked cards below `lg`** using `data-label` per cell. Numeric columns get `tabular-nums`.

**Tabs** — canonical look is an **underline rail, not pills**: transparent track, inactive `text-foreground/60` → active `text-foreground` with a 2px underline (`gold-ink` on the shadcn component, black on the class-based `.tab-rail`). Tabs are URL state: validated `?tab=` searchParams, not parallel routes.

**Modal / Dialog / Sheet** — portaled, background made `inert` + `aria-hidden`, focus trap, Escape + backdrop close (when dismissible), focus restored to trigger, body-scroll locked. `role="dialog" aria-modal="true"`, named via `title`/`aria-label`. Sizes `sm→xl` (`max-w-md`…`max-w-4xl`), `max-h-[90vh] overflow-y-auto`, backdrop `bg-black/50` (`/70` dark). Drawers are URL-addressable Sheets (`?sel=`/`[id]`).

**App shell** — grouped, role-filtered left sidebar (≤16 visible items, ≤7 per group, 1 nesting level) + top bar with breadcrumbs, a ⌘K command palette (entity search + recents/favorites), a "+ New" quick-create, and an inbox/notification count. One shell for all apps. Sidebar collapses to a wrapping top bar at ~860px. Active nav item: `bg-sidebar-accent font-medium`, `aria-current="page"`.

---

## 6. House rules (the non-obvious ones)

- **Gold is a metal, not ink.** Never put bright `gold` on body text or chrome; it fails contrast. Use `gold-ink` for gold text, reserve bright gold for the logo and dark-surface accents. In v3 of the monorepo, gold is restricted to legacy text links only — chrome is neutral.
- **Semantic tokens only in markup.** `bg-card`, not `bg-white`; `text-muted-foreground`, not `text-zinc-500`. This keeps dark mode and density free.
- **Never dim with opacity.** De-emphasize a row/element with muted foreground + muted background (`.row-muted`), because opacity drops contrast below AA. Same for disabled text — use a token, not `opacity`.
- **Landing = work queue.** The first screen of a tool is the list of things the user must act on, with stat tiles that link into filtered views — not a hub of navigation links.
- **Forms follow the prefill doctrine.** Deterministic values are server-prefilled with a provenance chip (`record | computed | directory | parsed`); AI-drafted values sit behind an explicit accept/confirm gate with a draft banner; identity fields use person/unit pickers, never raw ID text; money is never model-drafted. (Full detail in `patterns.md`.)
- **Copy register:** sentence case, plain verbs; an action keeps its name through the flow ("Publish" → toast "Published"); errors state what happened + how to fix, no apologies.
- **Contrast is documented and gated.** When you pick a new color pair, note the ratio and keep body text ≥4.5:1, large text / UI components ≥3:1. The monorepo runs a `contrast-check` script over token pairs.
- **Match the project you're in.** These are defaults. Inside a real CCC repo, read `packages/ui2/src/styles.css` (or the app's `tailwind.config.js` / `src/index.css`) and its `components/` and extend exactly what's there.
