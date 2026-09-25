# Accessibility Design Review (WCAG 2.2 AA)

Run this during process phase 5, and whenever accessibility is in question. It's a *design-time* checklist — things you decide before a line of code. For deep WCAG conformance, screen-reader/AT testing, VPAT/ACR work, or remediation, hand off to the `accessibility-wcag` skill; this is the subset a designer owns.

The frame: about 1 in 4 users relies on an assistive path. AA is also the legal floor for public-university (ADA Title II) software. Design so access is structural, not bolted on.

## Contrast

- **Body text ≥ 4.5:1** against its actual background. Large text (≥24px, or ≥19px bold) and **non-text UI** (icons, control borders, focus rings, chart strokes) **≥ 3:1**.
- Check every real text/background *pair*, including text on tint backgrounds (a status label on its `-50` tint), placeholder text, disabled text, and text over images/gradients.
- The house `muted-foreground` (#71717A) is ~5:1 on white — the floor for secondary text. Don't go lighter for anything a user must read.
- **Never encode meaning by color alone** (1.4.1). A red "overdue" pill needs a label or icon too; a required field needs the `*` and a programmatic `aria-required`, not just a color.

## Focus & keyboard

- **Every interactive element is reachable and operable by keyboard** in a logical order (Tab/Shift-Tab), and there are no traps (except an intentional modal focus trap that Escape releases).
- **Visible focus indicator** on every focusable element, ≥3:1 against its surroundings, not clipped. The house pattern is a universal `focus-visible` ring (`ring-[3px] ring-ring/50`, or a 2px outline + gold halo). Don't remove outlines without replacing them.
- Focus order matches reading/visual order. When a modal/drawer opens, focus moves into it; when it closes, focus returns to the trigger (2.4.3).
- Provide a **skip link** to main content as the first focusable element on full pages.
- WCAG 2.2 additions to watch: **focus not obscured** (2.4.11 — sticky headers/toasts must not cover the focused element), **dragging alternatives** (2.5.7 — anything drag-to-reorder needs a click/keyboard alternative), **target size ≥ 24×24px** (2.5.8; aim for 44×44 on touch), and **consistent help placement** (3.2.6).

## Semantics & labels

- Use **real semantic elements**: `<button>` for actions, `<a href>` for navigation, `<h1>`–`<h6>` in order (one `<h1>` per page), lists for lists, `<table>` for tabular data, `<nav>`/`<main>`/`<header>` landmarks.
- **Every control has an accessible name.** Visible `<label>` bound to its input; icon-only buttons get an `aria-label`; a search field with only a placeholder is unlabeled — fix it.
- Prefer native HTML over ARIA. Reach for ARIA only to fill gaps (`aria-current="page"`, `aria-invalid`, `aria-describedby`, `aria-live` for async status). Wrong ARIA is worse than none.
- Images/icons that carry meaning need alt text; decorative ones are `alt=""`/`aria-hidden`.

## Forms

- Label every field (not placeholder-as-label — it vanishes on input and often fails contrast).
- Mark required fields both visually (`*`) and programmatically (`aria-required`).
- On error: set `aria-invalid`, link the message with `aria-describedby`, render it in a `role="alert"` region, and keep it **specific and recoverable** ("Enter a date after today," not "Invalid"). Move focus to the first error on submit.
- Don't rely on color alone for the error state; pair the red with an icon or text.
- Group related fields with `<fieldset>`/`<legend>` (radio sets, address blocks).

## Motion & sensory

- Honor `prefers-reduced-motion`: neutralize non-essential animation/transition/parallax/auto-scroll. Keep essential motion (e.g., a loading indicator) but calm.
- No content that flashes more than 3×/second (2.3.1).
- Don't convey information only through sound, shape, or spatial position.

## Common widget patterns (ARIA authoring practices)

- **Modal/Dialog:** `role="dialog" aria-modal="true"`, labelled by its title, focus trapped, Escape closes, background `inert`.
- **Tabs:** `role="tablist"`/`tab`/`tabpanel`, roving `tabindex`, Arrow/Home/End keys, `aria-selected`, panel labelled by its tab.
- **Menu / dropdown / combobox:** follow the APG keyboard model (Arrow keys, Enter/Escape, `aria-expanded`, `aria-activedescendant`); prefer a vetted primitive (Radix) over hand-rolling.
- **Toast:** `aria-live="polite"` (or `role="status"`); don't put the only copy of critical info in a toast that auto-dismisses.
- **Data table:** real `<th scope>`; if it collapses to cards on mobile, keep each value's label associated with it (`data-label`/visually-hidden label).

## Quick self-audit before you call a design done

1. Can I do the whole task with only the keyboard, and always see where I am?
2. Does every text/bg pair pass (4.5:1 / 3:1)? Did I check tints, placeholders, disabled?
3. Does every control have a name a screen reader would announce?
4. Are loading, empty, error, and success states all designed — and are errors specific?
5. Does it survive `prefers-reduced-motion`, 200% zoom, and a 360px-wide screen?
6. Is any meaning carried by color/shape/position *alone*? If so, add a second cue.
