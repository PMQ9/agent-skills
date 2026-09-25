# Design-System Recon

Read this before judging consistency (step 3 of the workflow). The point is
simple: **"deviates from the design system" is only a finding if the design system
exists and the diff actually deviates from it.** Ten minutes of recon is what
separates a grounded review from a reviewer imposing personal taste on someone
else's codebase.

The standard you hold the diff to is *this repository's* conventions. If the repo
hard-codes hex everywhere and has no tokens, a new hard-coded hex is at most a
Nit with a note that a token layer would help — not a Major.

## What to find, in priority order

### 1. The token layer

Where the project's colors, spacing, type, radii, shadows, and motion live. Look
for, in rough order of likelihood:

```bash
# CSS custom properties / theme files
ls src/styles src/app 2>/dev/null
rg -l --glob '*.{css,scss}' -e '^\s*--[a-z-]+:' -e '@theme' -e ':root'

# Tailwind config (v3) or CSS-first theme (v4)
cat tailwind.config.{js,ts,cjs,mjs} 2>/dev/null
rg -n '@theme|@layer|--color-' src/**/*.css 2>/dev/null

# JS/TS token objects, vanilla-extract, panda, stitches
rg -l 'createTheme|defineConfig|tokens\s*=|theme\s*=\s*\{' src/

# Design-system package as a dependency
rg -n '"(@[\w-]+/(ui|design-system|tokens))"' package.json
```

Extract: the named color tokens (and whether there's a light/dark pair), the
spacing scale (is it 4px? 8px? Tailwind default?), the type scale, the radius
scale, and the shadow set. You don't need to memorize values — you need to know
that `--color-danger` exists so you can say "use `--color-danger` instead of
`#dc2626`" with the real token name.

### 2. The component library

The primitives the diff should be reusing instead of reinventing.

```bash
# Common homes for shared primitives
ls src/components/ui src/ui packages/ui components/ui 2>/dev/null

# shadcn/Radix signature (cva variants + cn() class merge)
rg -l 'class-variance-authority|cva\(' src/
rg -n 'from .*@radix-ui' package.json src/ | head

# What already exists — before flagging a "new one-off Modal"
rg -l --glob '*.{tsx,jsx,vue,svelte}' -e 'export (default )?function (Button|Modal|Dialog|Drawer|Toast|Spinner|Skeleton|Table|Badge|Input|Select)'
```

Extract: the list of available primitives and, for the ones the diff touches,
their variant/size prop names. This is what lets you write `use <Button
variant="destructive">` instead of the vague "reuse the shared button."

### 3. The conventions the repo has already chosen

- **Styling approach** — Tailwind / CSS Modules / plain CSS + layers / CSS-in-JS /
  vanilla-extract. Mixing approaches in one file is a legitimate finding; using
  the repo's chosen one is not.
- **Theming** — is there dark mode? Class-based (`.dark`) or media-query? If dark
  mode exists, every new color the diff introduces needs a dark counterpart, and
  a hard-coded light-only value is a real bug.
- **Icons** — which library, and imported individually or as a namespace?
- **Z-index / layering** — is there a named scale (`--z-modal`)? If so, `9999` is
  a finding. If not, it's a suggestion.
- **Motion** — is there a duration/easing token and a `prefers-reduced-motion`
  block already? New animation should follow it.
- **Breakpoints** — the project's actual breakpoints, so "no mobile story" cites
  the right widths.
- **Lint enforcement** — `eslint-plugin-jsx-a11y`, `eslint-plugin-tailwindcss`,
  stylelint, a token-lint rule. If a rule exists and the diff violates it, that's
  not a style opinion, it's a broken build waiting to happen — raise severity.
- **Existing test/story coverage** — a `*.stories.tsx` next to components means
  Storybook is available for the visual pass, and means a new component without a
  story is a real (Minor) gap in this repo's conventions.

### 4. Prior art for the thing being built

Find one or two existing components of the same kind as the diff's subject —
another table, another form, another drawer — and read them. This is the fastest
way to know what "consistent" means here, and it makes findings concrete:

> "`ApprovalsTable` builds its own sort header; `RequestsTable.tsx:40` already has
> a `SortableHeader` doing exactly this. Reuse it — the two tables will otherwise
> drift."

## How to phrase a consistency finding

Ground it in the repo, name the token or component, and say what the one-off
costs. The cost is almost always the same and worth stating plainly: a hard-coded
value doesn't respond to theme changes, doesn't get updated when the brand does,
and quietly teaches the next person that hard-coding is fine here.

**Good:**
> `Card.tsx:18` — `background: #FFFFFF` bypasses `--color-card`, so this card
> stays white in dark mode while everything around it flips. Use
> `bg-card`/`var(--color-card)`.

**Bad:**
> Don't hard-code colors. Use design tokens.

## When there is no design system

Say so in the template's **Design system** field ("no token layer found; styles
are per-component CSS") and adjust:

- Don't invent tokens or propose a design system in a PR review. That's a project
  decision and belongs in `ui-ux-product-designer` or an issue, not here.
- Still flag *internal* inconsistency: the same diff using `#f5f5f5` in one file
  and `#f4f4f5` in another, or three different border radii on sibling cards.
  That's a real defect regardless of whether tokens exist.
- Still flag anything with a *functional* consequence — a light-only color in an
  app with dark mode, a magic z-index that fights an existing overlay.

## When the project is Vanderbilt CCC

If the repo is a CCC project (or the tokens match the CCC house style — Vanderbilt
gold `#C9A227`/`#F2CC0C` on black, Zinc neutrals, `rounded-xl` cards,
`shadow-xs` max), the `ui-ux-product-designer` skill's
`references/ccc-design-system.md` documents the intended system, and its
`assets/design-tokens.css` has exact values. Read it when you need to check
whether a value is the house token or a drift. The one CCC rule that catches
people: **gold is text-unsafe** — gold text on light surfaces must use the
darkened `gold-ink`, and gold never carries chrome or body text. A diff putting
`#F2CC0C` text on white is a contrast Critical, not a taste note.

Even then: the project is the law, the house style is only the default. If the
repo's committed tokens differ from the house doc, the repo wins.
