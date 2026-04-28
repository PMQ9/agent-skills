---
name: accessibility-wcag
description: Use this skill for any work involving web accessibility — WCAG 2.1/2.2/3.0, Section 508, ADA Title II/III, EN 301 549, the European Accessibility Act, ARIA, semantic HTML, keyboard navigation, focus management, screen readers (NVDA, JAWS, VoiceOver, TalkBack), color contrast, motion preferences, accessible names, accessible forms, accessible data tables, accessible modals/dialogs/menus/tabs/comboboxes, accessibility testing (axe, Lighthouse, Pa11y, manual testing with AT), VPAT/ACR documents, and remediation of inaccessible interfaces. Trigger when the user mentions a11y, accessibility, screen readers, keyboard navigation, WCAG, contrast, ARIA, focus management, or any specific assistive technology — and proactively when reviewing any UI work where accessibility hasn't been addressed.
---

# Accessibility & WCAG

Accessibility is not an extra feature you add to a finished product. It's a property of the structure of the UI — there for free if you build the right thing, expensive to bolt on if you didn't. About 1 in 4 adults in the US has some form of disability; on the web that translates to people using screen readers, screen magnifiers, switch devices, voice control, eye tracking, keyboard-only navigation, high-contrast modes, reduced motion, captions, and a long tail of assistive tech you've never seen. A site that doesn't work for them is broken for them, fully.

The legal frame in 2026: **ADA Title II** (now applies to state and local government digital services with WCAG 2.1 AA conformance required by April 2026/2027 depending on entity size), **ADA Title III** (private business; courts continue to find websites are places of public accommodation), **Section 508** (US federal procurement; WCAG 2.0 AA), **EN 301 549** + **European Accessibility Act** (EU; effective June 2025 for many products including e-commerce). For higher education in the US, Title II of the ADA plus Section 504 of the Rehabilitation Act apply — Vanderbilt's clinical and university web properties have WCAG 2.1 AA as the operating target.

The technical baseline is **WCAG 2.1 AA** for almost everyone. WCAG 2.2 added 9 success criteria in 2023 and is the current published version; conformance to 2.2 is the ambitious target. WCAG 3.0 is in draft and won't be a regulatory standard for years.

## How to think about WCAG

WCAG organizes around four principles (POUR):

- **Perceivable** — users can perceive the content. Text alternatives for images, captions for audio, sufficient contrast, content not conveyed by color alone.
- **Operable** — users can operate the interface. Keyboard works, time limits aren't punitive, no seizure-inducing flashing, navigable.
- **Understandable** — users can understand the content and operation. Language declared, predictable behavior, helpful error messages.
- **Robust** — content works with current and future assistive tech. Valid markup, status messages programmatically determined.

Each principle has guidelines, each guideline has success criteria graded A / AA / AAA. **AA is the legal target.** AAA is aspirational and sometimes impossible by design (e.g., AAA contrast for non-text is harder).

You don't need to memorize the criteria. You need to internalize the patterns — and run an automated tool to catch what falls through.

## The first six things, in order

If you do nothing else in a sprint where accessibility comes up, do these:

1. **Use real semantic HTML.** `<button>` for buttons, `<a href>` for links, `<input>` for inputs, `<nav>`/`<main>`/`<header>`/`<footer>` for landmarks, `<h1>`–`<h6>` in order. Half of all accessibility bugs come from `<div onClick>` masquerading as a button.
2. **Every form control has a label.** `<label for>`, `aria-label`, or `aria-labelledby`. Placeholder is not a label.
3. **Every image has appropriate `alt`.** Meaningful images describe content; decorative images have `alt=""` (empty, not missing).
4. **Color contrast meets AA.** 4.5:1 for normal text, 3:1 for large text (18pt+ or 14pt+ bold) and UI components/graphics.
5. **Keyboard works.** Tab through every interactive element in a sensible order; activate with Enter/Space; Escape closes overlays; focus is always visible.
6. **Focus management on dynamic UI.** When a modal opens, focus moves into it; when it closes, focus returns to the trigger.

These six cover ~70% of real-world a11y issues. None of them require a library.

## Semantic HTML: the foundation

The reason semantic HTML matters: it carries an **accessible name**, an **accessible role**, and **accessible state** automatically, exposed via the platform's accessibility tree to screen readers, voice control, switch devices, and everything else.

| Bad | Good | Why |
|---|---|---|
| `<div onClick={...}>Save</div>` | `<button onClick={...}>Save</button>` | Button has role, focusable, Enter/Space activates, screen reader announces "button". |
| `<div onClick={() => navigate(...)}>Profile</div>` | `<a href="/profile">Profile</a>` | Link semantics, right-click works, opens in new tab works, screen reader announces "link". |
| `<span>Required field</span>` (visual asterisk) | `<input required aria-describedby="hint">` + `<span id="hint">Required</span>` | The state is in the platform tree, not in pixels. |
| `<table>` for layout | CSS grid or flex | Tables tell screen readers "data ahead, row 1 of 12". Lying about that is hostile. |
| `<div>` stack of options | `<ul><li>...</li></ul>` | "List with 5 items" announces; arbitrary divs don't. |

The rule of thumb: if you're about to add `role="button"` or `role="link"` or `role="checkbox"`, you should be using `<button>`, `<a>`, or `<input type="checkbox">` instead. ARIA is for cases where no native element fits — not for replacing native elements.

### Headings

Heading structure is how screen-reader users navigate a page (NVDA's `H` key, JAWS's `H`, VoiceOver's rotor). Get it right:

- One `<h1>` per page (the main topic).
- No skipped levels — `<h2>` after `<h1>`, not `<h4>`.
- Don't use heading tags for visual size. Use a heading at the right level, style it however.
- Section headings nested logically: `<h1>` page → `<h2>` major sections → `<h3>` subsections.

Run a screen reader and tab through headings as the only navigation. If the page is comprehensible that way, headings are right.

### Landmarks

Use the landmark elements: `<header>`, `<nav>`, `<main>`, `<aside>`, `<footer>`, `<section>` (with an accessible name). Screen readers let users jump between them.

A page should have **exactly one `<main>`**. Multiple navigations get distinguishing labels: `<nav aria-label="Primary">` and `<nav aria-label="Footer">`.

## ARIA: when and how

The **first rule of ARIA**: don't use ARIA. Use native HTML. ARIA can only fail to do what native HTML does for free, and badly applied ARIA is worse than none.

When you do need ARIA, common useful applications:

- `aria-label` and `aria-labelledby` — give an accessible name to an element that doesn't have visible text (icon buttons).
- `aria-describedby` — supplementary description (form field hint, error message).
- `aria-expanded` — disclosure state on a button that controls a collapsible region.
- `aria-controls` — association from control to controlled element.
- `aria-live` — announce dynamic changes that aren't focused (toasts, status messages).
- `aria-current="page"` / `aria-current="step"` — current item in a navigation/wizard.
- `aria-hidden="true"` — hide from accessibility tree (decorative icon next to a label).

Common mistakes:

- **`aria-label` on a `<div>` with no role**. The label is ignored — there's nothing to label. Add a role, or use a real element.
- **Conflicting labels** — `<button aria-label="Close">X</button>` is fine because the visible text is just "X". `<button aria-label="Close">Close menu</button>` overrides the visible text, which confuses voice control users who say "click close menu".
- **`aria-hidden` on an interactive element**. Hides it from screen readers but keeps it in the keyboard tab order — confusing. Use `inert` on the container instead.
- **Reinventing widgets with ARIA**. A custom listbox, combobox, tree, or grid built with ARIA is one of the hardest things in web development. Use a vetted library (Radix, React Aria, headless-ui, Reach UI's successors) or use `<select>`, `<datalist>`, `<details>`, `<dialog>` where you can.

The **ARIA Authoring Practices Guide** documents the keyboard interaction patterns expected for each widget type. Read the relevant section before building anything custom.

## Keyboard

Every interactive element on the page must be reachable and operable by keyboard. The mental model: tab through the entire page; could you do everything?

- **Tab order** follows DOM order by default. Don't fight this; restructure DOM if visual order should change. Avoid positive `tabindex` (e.g., `tabindex="3"`) — it's almost always a bug.
- **`tabindex="0"`** makes a non-interactive element focusable. Rarely necessary if you used real elements.
- **`tabindex="-1"`** removes from tab order but allows programmatic focus. Common for modal dialogs (focus the dialog title programmatically when opened).
- **Skip link** — first focusable element on the page jumps to `<main>`. Spares keyboard users from tabbing through the nav on every page. Hide it visually until focused.

```html
<a href="#main" class="skip-link">Skip to main content</a>
...
<main id="main" tabindex="-1">...</main>
```

```css
.skip-link {
  position: absolute;
  left: -9999px;
}
.skip-link:focus {
  left: 0; top: 0; padding: 1rem;
  background: white; z-index: 100;
}
```

### Focus visible

Never `outline: none` without replacing it. The default browser outline isn't pretty, but invisible focus is a barrier. Use `:focus-visible` to show focus only for keyboard users and not on mouse click:

```css
*:focus { outline: none; }   /* OK if you do the next line */
*:focus-visible {
  outline: 2px solid var(--focus-color);
  outline-offset: 2px;
}
```

### Keyboard traps

Focus must always be able to leave any region via standard keys (Tab, Shift+Tab, Escape). The only legitimate "trap" is a modal dialog while it's open — focus stays inside until dismissed, but Escape closes it.

## Forms

Forms are where accessibility either lives or dies for many real users.

```html
<div class="field">
  <label for="email">Email address</label>
  <input
    id="email"
    name="email"
    type="email"
    autocomplete="email"
    required
    aria-describedby="email-hint email-error"
    aria-invalid="false"
  />
  <p id="email-hint" class="hint">We'll never share your email.</p>
  <p id="email-error" class="error" hidden>Please enter a valid email.</p>
</div>
```

Things this gets right:

- `<label for>` linked to the input — clicking the label focuses the input, screen reader announces the label.
- Real `type="email"` — mobile keyboards adapt, browser provides validation.
- `autocomplete="email"` — browsers and password managers fill correctly. Use the [HTML autocomplete tokens](https://html.spec.whatwg.org/multipage/form-control-infrastructure.html#autofill).
- `required` — communicated to AT.
- `aria-describedby` — links hint and error to the field. AT reads them after the label.
- `aria-invalid` — toggled to `"true"` when validation fails. AT announces "invalid".

Error handling:

- **Don't submit and silently fail.** If the user submits an invalid form, focus moves to the first error and the error region is announced.
- **Errors are next to the field** they refer to, programmatically associated.
- **Error text is descriptive** ("Email must include @"), not generic ("Invalid").
- **A summary** at the top of the form is helpful for long forms — a list of errors with anchor links to the fields.

Avoid:

- Placeholder as label (vanishes on focus, low contrast, doesn't announce as a label).
- Required indicated only by color (red asterisk). Use `required` attribute and a textual marker.
- Disabling the submit button with no explanation. People can't tell why it's disabled.
- Auto-submitting on input change without a way for the user to undo.

## Color and contrast

The minimum text contrast for AA: **4.5:1** for normal text, **3:1** for large text (≥ 18pt or ≥ 14pt bold). Non-text contrast for UI components, graphics, and focus indicators: **3:1**.

Tools:

- Browser DevTools (Chrome, Firefox) show contrast in the color picker.
- axe DevTools, WAVE, Lighthouse all report contrast.
- Manually: use a contrast checker (WebAIM, Stark).

The **APCA** (Advanced Perceptual Contrast Algorithm) is the WCAG 3 candidate and a more accurate model for actual perception, but until WCAG 3 is normative, AA is what you must meet. Some design systems already check both.

### Don't convey by color alone

A required field marked only with red text. A graph using only color to distinguish lines. A "select" state shown only by a different background tint. All fail for low-vision users, color-blind users, and screen reader users.

Use color **and** a second cue: an icon, a label, an underline, a pattern.

## Images and media

```html
<!-- Meaningful image: describe the content -->
<img src="/chart.png" alt="Enrollment dropped 12% from 2024 to 2025">

<!-- Decorative image: empty alt (NOT missing) -->
<img src="/divider.svg" alt="">

<!-- Complex image / chart: alt + longer description -->
<figure>
  <img src="/chart.png" alt="Enrollment 2020-2025">
  <figcaption>
    Enrollment grew steadily from 2020 to 2024, then dropped 12% in 2025.
    See <a href="/data/enrollment.csv">underlying data</a>.
  </figcaption>
</figure>
```

Rules of thumb:

- **`alt` text describes the function**, not the appearance. An image of a magnifying glass that triggers search has `alt="Search"`, not `"Magnifying glass icon"`.
- **No `alt` on functional images** — every linked image and image button must have alt text describing what it does.
- **Decorative is `alt=""`**, not omitted. Missing `alt` causes screen readers to read the filename, which is awful.
- **CSS background images** are decorative by definition (no AT exposure). If the image conveys meaning, it should be a real `<img>`.
- **SVG**: inline SVGs need `<title>` (and optionally `<desc>`) plus `role="img"` to be exposed as images, or `aria-hidden="true"` to be ignored.

Audio and video:

- **Captions** for any video with speech (WCAG 1.2.2 — A level, baseline).
- **Audio description** or transcript for videos that convey meaning visually (1.2.5 — AA).
- **Transcripts** for audio-only content (1.2.1 — A).
- **No autoplay with sound.** It's a mute spot for screen reader users; the screen reader voice and the autoplay video collide.

## Modals, menus, and other custom widgets

The hardest patterns to get right. Use a vetted library when possible:

- **React**: Radix UI, React Aria (Adobe), Headless UI. All maintained, all accessible by default.
- **Vue**: Radix Vue, Headless UI for Vue.
- **Vanilla**: a11y-dialog, Reach UI patterns.

If you must build one yourself, the WAI-ARIA Authoring Practices Guide is the spec. The patterns are precise: which keys do what, what ARIA attributes are required, how focus moves.

For **modals/dialogs**, the requirements:

- `<dialog>` element if you can use it (now well-supported and accessible by default).
- Focus moves into the dialog when it opens — typically to the first focusable element or the dialog's heading (with `tabindex="-1"`).
- Focus is trapped inside while the dialog is open (Tab cycles within).
- Escape closes the dialog.
- The page behind is `inert` (use the `inert` attribute on a parent container) — focus, click, and AT can't reach it.
- On close, focus returns to the element that opened the dialog.
- The dialog has an accessible name (e.g., the title element via `aria-labelledby`).

For **dropdown menus**, **comboboxes**, **tabs**, **accordions**: the keyboard contract is non-trivial (arrow keys, Home/End, type-to-search). Don't reinvent unless you have to.

## Live regions and dynamic content

When content changes without focus moving (a search filter updating results, a toast appearing, a save indicator changing), AT users need to know.

```html
<div aria-live="polite" aria-atomic="true">
  Showing 12 results for "biology"
</div>
```

- `aria-live="polite"` — announce when AT is idle. Default for most things.
- `aria-live="assertive"` — interrupt to announce. Use sparingly: errors, time-sensitive alerts.
- `aria-atomic="true"` — read the whole region on change, not just the diff. Usually what you want for short status messages.

The live region must exist in the DOM **before** the content changes — adding both at the same time isn't reliably announced. Render an empty live region on mount; update its text content when announcements fire.

Frameworks:

- React: render the region, update children.
- Use a **toast library** that handles `role="status"` / `role="alert"` correctly (react-hot-toast, Sonner have AT-correct implementations).

## Motion and animation

WCAG 2.3.3 (AAA) and the broader vestibular-disorder concern: large or parallax motion can trigger nausea or dizziness. **Respect `prefers-reduced-motion`**.

```css
@media (prefers-reduced-motion: reduce) {
  *, *::before, *::after {
    animation-duration: 0.01ms !important;
    animation-iteration-count: 1 !important;
    transition-duration: 0.01ms !important;
  }
}
```

For meaningful motion (a loading spinner, a fade), keep it. For decorative parallax, scroll-jacking, or autoplaying animation, disable it under reduced-motion.

WCAG 2.3.1 (A) — no content flashes more than three times per second. This is a seizure prevention requirement. Don't make a flashing red error indicator.

## Tables

Real data tables, not layout tables.

```html
<table>
  <caption>Enrollment by department, Fall 2025</caption>
  <thead>
    <tr><th scope="col">Department</th><th scope="col">Students</th></tr>
  </thead>
  <tbody>
    <tr><th scope="row">Biology</th><td>342</td></tr>
    <tr><th scope="row">Chemistry</th><td>278</td></tr>
  </tbody>
</table>
```

`scope="col"` and `scope="row"` link headers to cells. `<caption>` provides the table's accessible name.

For complex tables with merged cells or two header dimensions, use `headers` and `id` to associate. Or simplify the table.

## Testing

### Automated tools (catch ~30-40% of issues)

- **axe DevTools** (browser extension and library `@axe-core/react`, `@axe-core/playwright`). The most accurate ruleset.
- **Lighthouse** — built into Chrome DevTools. Less detailed than axe, fine as a first pass.
- **WAVE** — browser extension, visual overlay of issues.
- **Pa11y** — CLI, integrates with CI.

Wire one into CI. axe-core in Playwright tests catches regressions on the parts of the app that have tests. Run a site-wide scan periodically.

Automated tools cannot detect:

- Whether `alt` text is *correct* (only that it exists).
- Whether reading order matches visual order on a complex layout.
- Whether keyboard navigation makes sense.
- Whether content is understandable.
- Whether ARIA semantics are correct in context.

For those, you need manual testing.

### Manual testing (catches the rest)

- **Tab through every page.** Sensible order? Visible focus? Everything reachable? Anything that shouldn't be reachable (decorative)?
- **Use the page with a screen reader** for at least one full flow per release. NVDA on Windows (free), VoiceOver on Mac/iOS, TalkBack on Android, JAWS if you have a license.
- **Zoom to 200% and 400%.** Does anything overflow, become unreadable, or lose function? (WCAG 1.4.4 / 1.4.10.)
- **High contrast / forced colors mode** (Windows). Are borders/backgrounds still distinguishable?
- **Voice control** — Voice Control on Mac, Voice Access on Windows. Can you say "click Save"? If not, your accessible name is wrong.

Don't be intimidated by screen readers. The basics:

- **NVDA**: download free, Insert+Space toggles browse/focus mode, Insert+F7 lists landmarks/headings/links, Tab/Shift+Tab navigates focusable elements, H/Shift+H moves by heading.
- **VoiceOver**: Cmd+F5 toggles, VO+U opens the rotor, VO+arrow navigates.

You don't have to be fluent. You have to be able to start it and notice when something is unintelligible.

## Documentation: VPATs and ACRs

A **VPAT** (Voluntary Product Accessibility Template) filled out becomes an **ACR** (Accessibility Conformance Report). Procurement teams (especially government, education, large enterprise) require these. The VPAT format you'll most often see is **VPAT 2.5 INT** — covers WCAG 2.1, Section 508, and EN 301 549 in one document.

If you ship software anyone procures, you'll be asked for a VPAT eventually. The honest VPAT is more valuable than an inflated one — claiming "Supports" when the product doesn't comes back as a real legal/contractual problem.

For Vanderbilt: VPATs are typically required for procured software through ITS / VUMC IT before purchase.

## Common anti-patterns

- `<div onClick>` instead of `<button>`. The original sin.
- Missing `<label>` on form fields, with placeholder used as visual label.
- `outline: none` with no replacement focus indicator.
- Modal that doesn't trap focus, doesn't return focus on close, and isn't dismissed with Escape.
- "Read more" links — eight of them on a page, all saying "Read more". Screen reader user navigating by links sees "read more, read more, read more". Use descriptive link text, or `aria-label` to disambiguate.
- Icon-only buttons with no accessible name.
- Hover-only interactions. Keyboard-only and touch users can't hover.
- `aria-label` overriding visible text in confusing ways for voice control.
- ARIA roles slapped on the wrong element (`role="button"` on a span that doesn't have keyboard handling).
- `aria-live` regions added at the moment of update, so the announcement doesn't fire.
- Disabled buttons with no explanation of why.
- Captchas with no audio alternative or no alternative at all (use hCaptcha/reCAPTCHA accessible variants, or rate limiting + reasonable risk scoring).
- "Inaccessible" widgets fixed by adding `role="application"` to dodge AT semantics. That's not fixing it; it's silencing the screen reader.
- Color-only state ("required fields are red"). Add a second cue.
- Auto-playing carousels with no pause control. WCAG 2.2.2 — control is required for content that auto-updates.
- Time limits on forms with no warning or extension. WCAG 2.2.1.
- Skipping headings (`<h1>` then `<h4>`).
- Tables used for layout. Don't.
- Generic alt text like `alt="image"` or `alt="photo"`.
- `tabindex="3"`, `tabindex="5"`. Always a bug.
- Custom select dropdowns with no keyboard support — arrow keys, Home, End, type-to-search.
- Toasts that announce assertively for routine confirmations. Save politely.
- Long content with no headings, no landmarks — just one big div soup.

## What good looks like in practice

- Every interactive element is the right HTML element. Buttons are buttons.
- Every form field has a real label and clear error association.
- Every page has a `<main>`, an `<h1>`, and a logical heading outline.
- Tab through any page and you can do everything; focus is always visible; order makes sense.
- Modals trap focus and return it; Escape closes them; the page behind is inert.
- Color contrast meets AA everywhere. No information conveyed by color alone.
- Images have correct alt; decorative ones have empty alt.
- Dynamic updates either move focus (when expected) or announce via live regions.
- `prefers-reduced-motion` is respected.
- An axe scan in CI is part of the build, and it's green.
- Someone on the team has actually used the site with a screen reader within the last 90 days.

The framing that helps teams adopt this: accessibility is **functionality**, not a checklist. A button that doesn't work for keyboard users is a broken button, the same way a button that doesn't work in Safari is a broken button. Treat regressions accordingly.
