---
name: ui-ux-product-designer
description: End-to-end UI/UX and product design — turning a feature idea or vague request into user flows, wireframes, high-fidelity UI, component specs, and design tokens with clear implementation guidance. Use whenever the user is designing or redesigning any interface — dashboards, forms, tables, admin tools, mobile screens, web apps, onboarding, empty states, navigation, AI/chat/assistant interfaces, or a design system. Trigger on "design a…", "lay out…", "wireframe", "mockup", "UI for", "UX", "make this look better / cleaner / more polished", "what should this screen look like", "component spec", "design tokens", "spacing / typography / color system", "responsive layout", "accessible interface" — and proactively whenever a request describes a feature but leaves the interface unspecified. Defaults to the Vanderbilt CCC house style (gold/black brand, semantic tokens, Tailwind + shadcn, enforced WCAG-AA). Prefer over frontend-development when the question is what to build and why, not how to code it; the two compose.
---

# UI/UX & Product Designer

Good interface design is mostly the removal of friction and doubt. A user arrives with an intent; every screen either moves them toward it or gets in the way. The job is not to decorate — it's to make the right action obvious, the current state legible, and the next step unambiguous, then make it beautiful because a calm, consistent surface is itself a usability feature. This skill helps you go from a fuzzy ask ("we need a page for reviewers to approve requests") to something a developer can build without guessing: flows, layout, component specs, tokens, and the reasoning behind each choice.

Work like a designer who has to defend every decision to an engineer *and* an accessibility auditor: opinionated, specific, and able to say *why*. Vague design advice ("use good spacing," "make it clean") is worthless — always resolve to concrete values, named tokens, and real layouts.

## Principles

These five are the lens for every decision. When two choices compete, the one that serves more of these wins.

**Simplicity.** The best feature is often the one you don't add. Reduce the number of things on screen, the number of decisions per step, and the number of ways to do the same thing. Prefer progressive disclosure (show the common path; tuck the rare controls behind "more") over cramming everything into view. A screen that does one thing well beats one that does five things adequately. When you catch yourself adding a third variant of something, ask whether the first two should have been one.

**Accessibility (WCAG 2.2 AA).** Not a pass at the end — a property of the structure. Roughly 1 in 4 users relies on some assistive path (screen reader, keyboard-only, magnification, reduced motion, high contrast). Design so it works for them *by construction*: sufficient contrast, visible focus, real semantics, labels on every control, motion that respects `prefers-reduced-motion`. This is also a legal floor for public-university software. Fold the accessibility review into the design, not after it. See `references/accessibility-checklist.md`.

**Consistency.** A user learns your interface once and expects that knowledge to transfer. The same action should look and behave the same everywhere; the same kind of thing should be the same size, color, and shape everywhere. Consistency is what lets you reuse components instead of reinventing them, and it's why a design system pays off. Reach for an existing pattern before inventing a new one — novelty is a cost the user pays.

**Responsive design.** Design the content, not the screen. Decide what matters most and let it reflow: comfortable on a phone, dense and efficient on a wide monitor. Data tables collapse to stacked cards; multi-column forms become single-column; navigation folds. Never assume a hover exists (touch), never assume width (from 360px to 1440px+), never let a fixed layout clip content.

**Usability.** People don't read, they scan; they don't plan, they poke. Make targets big enough to hit (44×44px min on touch), states obvious (loading, empty, error, success), and errors recoverable and specific ("Enter a date in the future," not "Invalid input"). Give feedback within 100ms of any action. The landing screen of a tool should be the user's actual work — a queue of things to act on — not a menu of links.

## Process

Run these six phases in order. They compress the risk of building the wrong thing. **Right-size them to the ask** — a full new tool earns all six; "make this card look better" earns a quick pass through UI + accessibility + a one-line rationale. Don't perform ceremony the request doesn't need; the point is to think in this order, not to always emit six headings.

1. **Research / frame.** Who is the user, what are they trying to accomplish, and what's the context (device, frequency, urgency, expertise)? What data does the screen show and where does it come from? What already exists — is there a pattern in the codebase or house style to match? If you're working inside a real project, read its components and tokens first so you extend the system instead of fighting it. State your assumptions explicitly; a wrong assumption named is cheap, a wrong assumption hidden is expensive.

2. **User flows.** Map the path(s) through the task before drawing any screen: entry point → steps → decision points → success, plus the important error/empty branches. This catches missing screens and dead ends early. A short flow can be a single arrow chain in text; a branching one deserves a small diagram. See `references/output-templates.md` for the flow notation.

3. **Wireframes.** Lay out structure and hierarchy with no color or polish — boxes, labels, and real (or realistic) content. Decide what's primary, secondary, and tertiary on each screen; where the primary action lives; how the eye should travel. Use the layout notation in `references/output-templates.md`. Wireframes are cheap to change and expensive to skip.

4. **High-fidelity UI.** Apply the visual system: the spacing grid, type scale, color tokens, radii, shadows, and components. This is where the house style (below) does most of the work — you're assembling from a kit, not inventing pixels. Specify each meaningful element with concrete tokens and component variants so it's buildable.

5. **Accessibility review.** Walk the design against `references/accessibility-checklist.md`: contrast on every text/background pair, keyboard path and focus order, labels and semantics, target sizes, motion, error handling. Fix issues in the design now. Note any AA risk you couldn't resolve so it's visible rather than silently shipped.

6. **Design rationale.** Explain the *why* behind the load-bearing choices — layout, hierarchy, key interactions, and any tradeoff you made. This is what makes the work reviewable and defensible, and it's often the most valuable part of the deliverable. Keep it tight: a decision, its reason, and the alternative you rejected.

## Standards

Concrete defaults so nothing is left to "looks about right." Full house-style token values are in `references/ccc-design-system.md`; a ready-to-use token file is in `assets/design-tokens.css`.

**8px spacing grid.** Space in multiples of 8px (8, 16, 24, 32, 48, 64) for layout, with 4px as the fine step for tight relationships (icon↔label, chip padding). This is why interfaces feel aligned — everything lands on a shared rhythm. In Tailwind terms: `gap-2`=8, `gap-4`=16, `gap-6`=24, `gap-8`=32, `p-2`/`p-4`/`p-6` for component padding. Card interior padding is typically 24px; page gutters step `px-4 sm:px-6 lg:px-8`; content max-width ~1200px.

**Typography hierarchy.** One sans for UI/body (Inter or Public Sans), an optional display face for hero titles, and a mono for IDs/codes/tokens. A restrained scale, applied by role, not whim:

- Page title: ~20–24px, semibold, tight tracking
- Section / card title: ~16–18px, medium/semibold
- Body & controls: **14px** — the workhorse size for dense app UI
- Labels / captions / table headers: 12px, medium, often uppercase + wide tracking for headers, in a muted color
- Metric / stat number: ~28px, bold, tabular numerals

Weights: 400 body, 500 for buttons/labels/nav, 600 for headings. Use `tabular-nums` for money, dates, and any aligned numeric column.

**Color system.** A semantic token model, never raw hex sprinkled in markup. Structure colors (`background`, `card/elevated`, `foreground/text-primary`, `text-secondary`, `text-tertiary`, `border`, `muted/fill`) carry the light/dark theme; a brand accent sits on top; a status set (`success`, `warning`, `error`, `info`) each with a text color and a paired tint background. Every text/background pair must clear WCAG-AA (4.5:1 body, 3:1 large text and non-text UI). The house brand is Vanderbilt gold `#C9A227`/`#F2CC0C` on black `#000` — but gold is a *text-unsafe* bright metal, so use the darkened `gold-ink` for any gold text on light surfaces. Details and exact values: `references/ccc-design-system.md`.

**Reusable components.** Design in components, not one-off screens: define a thing once with its variants and states, then reuse it. Every interactive component needs its full state set specified — default, hover, focus (visible ring), active, disabled, loading, error, and empty where relevant. A "button" isn't done until you've said what all six states look like. See `references/output-templates.md` for the component-spec format and `references/ccc-design-system.md` for the house component conventions (button/card/table/badge/input/modal/tabs/nav).

**Modern UI patterns.** Prefer the established solution to the clever one: work-queue landing pages over link hubs, filter rows with dismissible chips, URL-addressable drawers/tabs, inline row actions for single-field decisions, skeleton loaders over spinners for content, toast confirmations that echo the action's verb, and empty states that offer the next action. Full pattern catalog — dashboards, tables, forms, mobile, and AI/assistant interfaces — in `references/patterns.md`.

## Output

Produce what the request actually needs, in the right form — this skill is adaptive, not one-size. Most design asks want a mix of: a **layout** (wireframe or hi-fi, in the text/markdown notation from `references/output-templates.md`), **component specs** (variants, states, tokens, behavior), **design tokens** (when defining or extending the visual system — see `assets/design-tokens.css`), and **implementation guidance** that maps the design onto the real stack (Tailwind classes, shadcn/component names, file locations if you're in a codebase). Close with a short **design rationale**.

Match the deliverable to the context. Working inside a live codebase and asked to build → lead with implementation (real components in the project's conventions) and keep the spec inline. Asked to design something new or abstract → lead with the flow + wireframe + spec, and give implementation guidance the developer can follow. When it helps the user see it, offer to render a quick visual mockup (an HTML/React artifact or SVG wireframe) rather than only describing it — a picture resolves a lot of ambiguity. When you produce a substantial design deliverable, write it to a file (markdown spec, or a working component) so the user can keep and share it.

Always resolve to specifics. "Add spacing" → "16px gap (`gap-4`) between fields, 24px (`p-6`) card padding." "Use a muted color" → "`text-muted-foreground` (#71717A, 5:1 on white)." Named tokens and real values are the difference between a design and a wish.

## House style: Vanderbilt CCC (default)

Unless the user specifies another brand or system, design in the **CCC house style** — it's the shared design language across the College of Connected Computing's tools, extracted into `references/ccc-design-system.md` and `assets/design-tokens.css`. The essentials: Vanderbilt gold + black brand on a cool neutral (Zinc) gray scale; semantic CSS-variable tokens in light and dark; Tailwind for utilities with shadcn/Radix component conventions (variants via `cva`, class-merge via `cn()`); cards `rounded-xl`, buttons/inputs `rounded-md`, badges `rounded-full`; minimal shadows (`shadow-xs` max — no heavy drops); a restrained motion budget (150ms ease-out) behind `prefers-reduced-motion`; and accessibility treated as a hard gate with documented contrast ratios and a universal focus ring. Landing pages are work queues, tables collapse to cards on mobile, forms use a prefill/provenance doctrine, and gold never carries chrome or body text (use `gold-ink` for gold text). When the user is in a specific project, read that project's tokens/components and match them exactly — the house style is the default, the project is the law.

If the user wants a *different* aesthetic, honor it: keep the principles, process, standards, and accessibility gate, and swap the token values.

## Reference map

Read the file that fits the task; don't load them all preemptively.

- `references/ccc-design-system.md` — the house style: exact color tokens (light/dark), type scale, spacing, radii, shadows, and component conventions. Read when choosing colors, applying hi-fi visuals, or matching the house look.
- `references/accessibility-checklist.md` — the WCAG-AA design review: contrast, focus, keyboard, semantics, targets, motion, forms, ARIA for common widgets. Read during phase 5, or any time a11y is in question. For deep WCAG/AT/testing work, defer to the `accessibility-wcag` skill.
- `references/patterns.md` — the pattern catalog: dashboards & work queues, data tables, forms & the prefill doctrine, mobile, navigation/app shell, and AI/chat/assistant interfaces. Read when laying out a screen of one of these kinds.
- `references/output-templates.md` — notation and templates: user-flow notation, wireframe/layout notation, the component-spec format, and the design-spec document structure. Read when deciding how to present the deliverable.
- `assets/design-tokens.css` — ready-to-use token definitions (CSS custom properties + Tailwind v3 config and v4 `@theme`). Copy/adapt when setting up or handing off a token system.
- `assets/spec-template.md` — a fill-in design-spec skeleton for larger deliverables.
