# Frontend Review Detection Guide

Per-category tells, greppable signals, and worked fixes for the eight categories
in the SKILL. Examples are React/TSX because that's the common case; the tells
translate directly to Vue, Svelte, Angular, and plain templates.

Use this to confirm a suspicion and to find precise language. Every entry follows
the same shape: **the tell** (what you see in the diff), **why it hurts** (the
user consequence — this is what makes it a finding rather than a preference), and
**the fix** (concrete, minimal, using the platform or the repo's existing parts).

## Contents

**Q1 — right thing on screen:** 1. State & data correctness · 2. State coverage
**Q2 — consistency:** 3. Design-system adherence · 4. Shared-primitive blast radius
**Q3 — feels fast:** 5. Bundle & load cost · 6. Runtime & rendering cost
**Q4 — works for everyone:** 7. Accessibility · 8. Responsive & interaction UX
Plus: greppable signal list, and false-alarm guards.

---

## 1. State & data correctness

**Effect-syncing server data into local state.** The tell: `useEffect(() => {
setItems(data) }, [data])`, or a fetch in an effect that writes to `useState` with
no cancellation. Why it hurts: two sources of truth that drift — the user sees the
previous page's rows for a beat, or forever after an error. Fix: let the query
cache own it (`useQuery`) and derive what you render; if there's no query library,
at least don't duplicate — render from the fetched value directly.

**Fetch with no abort.** The tell: `useEffect(() => { fetch(url).then(setData) },
[url])`. Why it hurts: type fast in a search box and the slowest response wins —
the user sees results for a query they've already replaced. Fix:

```ts
useEffect(() => {
  const ac = new AbortController();
  fetch(url, { signal: ac.signal }).then(r => r.json()).then(setData)
    .catch(e => { if (e.name !== 'AbortError') setError(e); });
  return () => ac.abort();
}, [url]);
```

**Index as key.** The tell: `items.map((item, i) => <Row key={i} …>)` on a list
that can reorder, filter, or delete. Why it hurts: React reuses the wrong DOM
node — a half-typed input or a checked checkbox jumps to a different row. Fix:
`key={item.id}`. (Index keys are fine on a static, never-reordered list; say so
rather than flagging reflexively.)

**Optimistic update with no rollback.** The tell: `setRows(next)` before `await
save()`, with no `catch` restoring the previous value. Why it hurts: the request
fails and the UI keeps claiming success until reload — the worst kind of bug,
because the user acts on false information. Fix: snapshot, mutate, restore in
`catch`, and surface the failure.

**Derived state stored.** The tell: `const [total, setTotal] = useState(0)` plus
an effect recomputing it from `items`. Why it hurts: an extra render pass and a
window where `total` disagrees with `items`. Fix: `const total = useMemo(() =>
sum(items), [items])` — or just compute inline.

**Stale closure in a callback.** The tell: an interval/subscription/`setTimeout`
set up once (`[]` deps) reading a state variable. Why it hurts: it reads the
first-render value forever; the UI freezes on old data. Fix: functional updates
(`setX(prev => …)`) or a ref.

**URL/route state ignored.** See §8 — it lands as a UX finding, but the mechanism
is state placement.

## 2. State coverage

The most common real finding in frontend PRs. A new async surface owes the user
four answers; a new interactive control owes six visual states.

**No error branch.** The tell: `if (isLoading) return <Spinner/>` followed
straight by the success render, with `error` unused (or destructured and ignored).
Why it hurts: a failed request leaves a spinner forever or a blank region — the
user cannot tell whether to wait, retry, or leave. Fix: render an error state with
a retry, and keep the rest of the page usable.

```tsx
if (isLoading) return <Skeleton rows={5} />;
if (error) return <ErrorState message="Couldn't load approvals." onRetry={refetch} />;
if (!data.length) return <EmptyState title="No approvals waiting" action={…} />;
```

**No empty state.** The tell: a table/list/grid that maps over data with no
zero-length branch. Why it hurts: the user sees headers over a void and can't tell
"nothing here yet" from "it broke." Fix: an empty state that says what would put
something here, ideally with the action that does it.

**No loading state, or a spinner where a skeleton belongs.** A spinner for a whole
content region reads as "frozen"; a skeleton that matches the eventual layout reads
as "coming" and prevents shift. Minor-to-Major depending on how long the wait is.

**Button that doesn't reflect submitting.** The tell: `onClick={submit}` with no
`disabled`/pending state. Why it hurts: the user clicks twice and creates two
records. Fix: disable + label change (`Saving…`) while in flight; re-enable on
error.

**Missing interactive states.** New component with `hover:` but no
`focus-visible:`, or `disabled` styled the same as enabled. Why it hurts: keyboard
users lose their place; users click dead controls and think the app is broken. Fix:
specify all six (default, hover, focus-visible, active, disabled, loading) — or
use the repo's `Button`, which already has them.

**No error boundary around a new widget.** The tell: a new dashboard card /
chart / third-party embed rendered directly into a page tree with no boundary. Why
it hurts: one widget's render error blanks the whole route. Fix: wrap the region;
fallback should offer a retry, not just an apology.

**Unhandled partial failure.** Three cards, three requests, one fails — does the
page show two cards and one error, or nothing? Per-region states beat one global
one.

## 3. Design-system adherence

Read `design-system-recon.md` first; findings here are only real if the repo has
conventions to deviate from.

**Hard-coded color where a token exists.** Tell: `#2563EB`, `rgb(37 99 235)`,
`bg-[#2563EB]`, `color: blue`. Why it hurts: doesn't flip in dark mode, doesn't
follow a brand change, and teaches the next dev that hard-coding is normal here.
Fix: name the actual token — `bg-primary` / `var(--color-primary)`.

**Off-scale spacing / type.** Tell: `padding: 13px`, `mt-[7px]`, `font-size: 15px`
in a repo on a 4/8px grid and a fixed type scale. Why it hurts: things stop
aligning across components; the surface reads subtly "off." Fix: the nearest scale
step, named.

**A second implementation of an existing primitive.** Tell: a local `Modal`,
`Dropdown`, `Spinner`, `Toast`, `Tooltip`, or `Table` in a feature folder while
`ui/` already has one. Why it hurts: two things to fix for every future a11y or
visual change, and they will drift. Fix: use the shared one; if it genuinely can't
do the job, extend it there (new variant) rather than forking.

**Variant-by-className-override.** Tell: `<Button className="bg-red-600
hover:bg-red-700 …">` where the component has a `variant` prop. Why it hurts: the
override skips the variant's disabled/focus/dark handling, so the new button
misbehaves in states nobody tested. Fix: `<Button variant="destructive">`, or add
the variant to the component.

**`!important` / specificity war / magic z-index.** Tell: `!important`,
`z-index: 9999`, `div > div > .thing` selectors. Why it hurts: the next component
needs 10000; overlays start fighting; nobody can safely restyle anything. Fix: the
named layer scale, or fix the selector that made the override necessary.

**Global CSS leakage.** Tell: a bare element selector (`button { … }`, `input
{ … }`) or a generic class (`.card`) added to a global stylesheet from a
feature PR. Why it hurts: silently restyles unrelated screens — a change nobody in
this PR reviewed. Fix: scope it (module, component, or a specific class).

**Mixed styling approaches in one place.** Tell: Tailwind utilities plus an inline
`style` object plus a styled-component in the same file. Why it hurts: the
override order becomes folklore. Fix: pick the repo's primary approach.

**Dark-mode blind spot.** Tell: any new literal light color, or `text-black` /
`bg-white`, in a project with a dark theme. Why it hurts: a white block in a dark
page, or invisible text. Fix: semantic tokens that carry both themes.

## 4. Shared-primitive blast radius

**Changed prop contract.** Tell: a prop renamed, removed, made required, or given
a new default inside `ui/`, `components/`, or a design-system package. Why it
hurts: other screens break — or worse, silently change appearance. Fix: check the
callers and say who's affected:

```bash
rg -n '<Button\b' --glob '*.{tsx,jsx,vue,svelte}' | wc -l
rg -n '<Button\b[^>]*\bsize=' --glob '*.{tsx,jsx}' | head -20
```

Then write it concretely: "`size` default changed `md`→`sm`; 34 call sites don't
pass `size`, so every one of them shrinks. Either keep the default and set `sm`
where you need it, or list the screens you checked."

**Token value edited in place.** Tell: `--color-primary` or a Tailwind theme value
changed. Why it hurts: global visual change riding in a feature PR; contrast pairs
that were verified may now fail. Fix: separate PR, or state the audit ("checked
against text-on-primary: 5.1:1, still AA").

**Shared component gains app knowledge.** Tell: `ui/Button.tsx` importing
`useUser`, a router, or a feature type. Why it hurts: the primitive can no longer
be reused or tested in isolation; Storybook breaks. Fix: move it to
`components/` (app-aware) or pass what it needs as props.

**Behavior change with no visual diff.** Tell: focus trap, portal target,
`aria-*`, or keyboard handling altered inside a shared overlay. Why it hurts: the
regression is invisible in review and only shows for keyboard/AT users. Fix: name
the affected consumers and ask for a keyboard check on each.

## 5. Bundle & load cost

**Heavy dependency for a small job.** Tell: new `moment` (~70KB, no
tree-shaking), full `lodash`, `chart.js`/`d3` for one sparkline, an entire icon
package. Why it hurts: every user on every visit downloads and parses it. Fix:
`Intl.DateTimeFormat` / `date-fns` submodule / `lodash/groupBy` / a hand-rolled
four-liner / individual icon imports.

**Namespace and barrel imports.** Tell: `import * as Icons from 'lucide-react'`,
`import { Button } from '../../components'` (index re-export barrel). Why it
hurts: defeats tree-shaking, so the whole barrel lands in the chunk; also slows
dev rebuilds. Fix: import the specific module path.

**Eager-loading a rare, heavy surface.** Tell: a modal body, rich-text editor,
map, PDF viewer, or chart imported at module top level in a route component. Why
it hurts: everyone pays for a feature few open. Fix: `lazy(() => import(…))` /
dynamic import at the interaction, with a `Suspense` fallback.

**Fonts.** Tell: a new `@font-face`/Google Fonts link, extra weights, no
`font-display`. Why it hurts: blocking text render, layout shift on swap, hundreds
of KB. Fix: subset + `font-display: swap` + preload the critical face, or use the
system stack. Variable font when 3+ weights.

**Duplicate or overlapping libraries.** Tell: the diff adds a second date, state,
form, or icon library. Why it hurts: two of everything, both shipped. Fix: use the
one already present; if the new one is better, that's a migration, not a feature
PR.

**Dead polyfills / legacy targets.** Tell: `core-js` imports, `regenerator`, an ES5
build target in a repo whose browserslist is modern. Fix: check `browserslist`
before shipping the shims.

Quantify when you can (see `visual-verification.md` §7), and say what your number
is based on. "≈70KB min (lodash full build) into the dashboard chunk" is
actionable; "this is heavy" is not.

## 6. Runtime & rendering cost

**Unsized media → layout shift.** Tell: `<img src>` / `<video>` / `<iframe>`
without `width`+`height` or `aspect-ratio`. Why it hurts: content jumps as it
loads; users mis-click. Fix: intrinsic dimensions (or `aspect-ratio` + `w-full`).
Guard: a 16px icon won't shift anything.

**Lazy-loading the LCP image.** Tell: `loading="lazy"` on a hero/above-the-fold
image. Why it hurts: delays the largest paint — the metric users feel as "slow."
Fix: eager + `fetchpriority="high"`, and preload it.

**Request waterfalls.** Tell: a child component fetching from a prop the parent
just fetched; sequential `await`s of independent calls. Why it hurts: latency
adds up serially; the user watches spinners in sequence. Fix: hoist and
parallelize (`Promise.all`), or fetch the joined view.

**Layout thrash.** Tell: `offsetHeight` / `getBoundingClientRect` /
`scrollHeight` read inside a loop, a scroll/resize handler, or on every render
right after a style write. Why it hurts: forced synchronous reflow — janky
scrolling, bad INP. Fix: batch reads before writes, cache measurements, or use
`ResizeObserver`/`IntersectionObserver`.

**Non-composited animation.** Tell: transitions/keyframes on `top`, `left`,
`width`, `height`, `margin`, or `box-shadow` spread. Why it hurts: relayout each
frame; visible stutter on mid-range phones. Fix: animate `transform` and
`opacity`; add `will-change` only where measured.

**Unthrottled high-frequency handler.** Tell: `onScroll` / `onMouseMove` /
`onResize` doing real work each event, or a search input firing a request per
keystroke. Fix: `requestAnimationFrame`, debounce/throttle, or an observer.

**Expensive work in render.** Tell: sorting/filtering/parsing thousands of items
inline in the component body, `JSON.parse` of a large blob per render, a new
`Date`/`Intl` formatter constructed per row. Fix: hoist formatters to module
scope, memoize on real inputs. Guard: don't demand `useMemo` on cheap work —
over-memoization is a Nit at most.

**Unbounded list.** Tell: rendering every row of a list that can reach thousands.
Fix: pagination or virtualization — but only if the size is plausibly large; say
so honestly.

**Console noise / debug left in.** Tell: `console.log`, `debugger`, a commented-out
block. Nit, but easy.

## 7. Accessibility

**Non-semantic interactive element.** Tell: `<div onClick>`, `<span onClick>`,
`<li onClick>` with no `role`/`tabIndex`/key handler. Why it hurts: unreachable by
keyboard, invisible to screen readers, no Enter/Space — the control simply does not
exist for those users. Fix:

```tsx
// before
<div className="row-action" onClick={onApprove}>Approve</div>
// after — native semantics: focusable, Enter/Space, announced as a button
<button type="button" className="row-action" onClick={onApprove}>Approve</button>
```

Same for navigation: `<a href>`, not a div with `onClick={() => navigate(…)}` —
users lose middle-click, copy-link, and "open in new tab."

**Unlabeled input.** Tell: `<input placeholder="Email" />` with no `<label
for>`/`aria-label`, or a label not associated with the control. Why it hurts: the
placeholder disappears on typing and isn't announced as a name; the field is
anonymous to AT. Fix: real `<label htmlFor>`; placeholders are hints, not labels.

**Icon-only control with no name.** Tell: `<button><TrashIcon/></button>`. Why it
hurts: announced as "button," nothing more. Fix: `aria-label="Delete request"` (or
visually-hidden text), plus `aria-hidden="true"` on the decorative icon.

**Focus indicator removed.** Tell: `outline: none`, `focus:outline-none`,
`*:focus { outline: 0 }` with no replacement. Why it hurts: keyboard users lose
their position entirely. Fix: a visible `focus-visible` ring at ≥3:1 against its
background — the repo probably has a `ring` token.

**Modal/overlay without focus management.** Tell: a new dialog/drawer/menu built
from divs, or a portal with no focus handling. Why it hurts: focus stays behind the
overlay; keyboard users tab into hidden content and can't reach or dismiss the
dialog. Fix: `<dialog>` or the repo's Radix/shadcn Dialog — move focus in on open,
trap it, close on `Escape`, restore focus to the trigger, mark the rest `inert` or
`aria-hidden`.

**ARIA patching a wrong element.** Tell: `role="button"` on a div,
`aria-label` on a wrapper instead of the control, `role="list"` on a `<ul>`,
`aria-hidden` on something focusable. Why it hurts: ARIA doesn't add behavior —
only a promise the element now has to keep. Redundant roles are noise; wrong roles
actively mislead. Fix: the native element. First rule of ARIA: don't use ARIA.

**Contrast failure.** Tell: light gray text (`text-gray-400` on white ≈ 2.8:1),
brand-yellow text, low-contrast placeholder or disabled text carrying real
information, an input border you can't see. Thresholds: 4.5:1 body, 3:1 large
(≥24px or ≥18.66px bold), 3:1 non-text UI. Measure it
(`visual-verification.md` §6a) and quote the number.

**Heading structure.** Tell: `<div class="title">`, or an `h4` under an `h2`. Why
it hurts: screen-reader users navigate by heading; a broken outline erases the
page's map. Fix: real heading levels in order; style with classes.

**Error announced only visually.** Tell: red border + red helper text with no
`aria-invalid`/`aria-describedby`, or a toast in a non-live region. Fix:
`aria-invalid`, associate the message via `aria-describedby`, use
`role="alert"`/`aria-live="polite"` for async updates, and move focus to the first
error on submit failure.

**Images.** Tell: no `alt`, `alt="image"`, `alt="chart"` on a meaningful chart, or
a decorative icon with a description. Fix: describe the *information* (`alt="Q3
approvals up 12%"`), or `alt=""` when decorative.

**Motion without an escape.** Tell: new animation/auto-carousel/parallax with no
`@media (prefers-reduced-motion: reduce)` branch. Why it hurts: vestibular
disorders — real nausea, not an inconvenience. Fix: reduce or remove motion under
the query.

**Positive `tabIndex`.** Tell: `tabIndex={1}` or higher. Why it hurts: hijacks the
whole page's tab order. Fix: fix the DOM order; `tabIndex={0}` / `-1` only.

**Also worth a look:** `<table>` without `<th scope>` for data tables; a custom
select/combobox/tabs widget hand-rolled instead of using the library (each rewrite
ships an a11y bug); `autoFocus` yanking focus on page load; `title` used as the
only accessible name; a skip link missing on a new full-page layout; language not
set on new standalone pages.

## 8. Responsive & interaction UX

**Fixed widths / viewport units.** Tell: `width: 1200px`, `min-width: 900px`,
`h-screen`/`100vh` on a scrolling mobile page. Why it hurts: horizontal scroll and
clipped content on a phone; `100vh` is taller than the visible area under mobile
browser chrome, so the CTA hides under the toolbar. Fix: `max-width` + fluid
widths; `100dvh` or a flex layout.

**Table with no narrow story.** Tell: a new multi-column table, no responsive
handling. Why it hurts: at 375px it either overflows or squeezes to unreadable
slivers. Fix: the repo's pattern — collapse to stacked cards, or an explicit
horizontal-scroll container with a shadow affordance and sticky first column.

**Hover-only affordance.** Tell: `opacity-0 group-hover:opacity-100` on row
actions, information available only in a `title`/tooltip, a menu that opens on
hover. Why it hurts: touch has no hover — the feature is invisible and unreachable
on phones and tablets. Fix: always-visible (or focus-visible) actions on small
screens; never put unique information in a hover.

**Small targets.** Tell: `h-6 w-6` icon buttons, tightly stacked links, a 32px
row-action. Why it hurts: mis-taps, especially for motor-impaired users.
Threshold: 44×44px effective (padding counts). Fix: grow the hit area, or add
spacing.

**Overflow and reflow.** Tell: long unbroken strings (emails, IDs, URLs) with no
`truncate`/`break-words`; a flex row that can't wrap; content that clips at 320px
or 200% zoom. Fix: truncate with a title/tooltip *plus* an accessible full value,
`min-w-0` on flex children, `flex-wrap`.

**Destructive action with no guardrail.** Tell: a delete/reject/revoke button
wired straight to the mutation. Why it hurts: one mis-tap, unrecoverable data. Fix:
a confirmation naming the object ("Delete request #2481?"), or better, optimistic
delete plus a 5-second Undo toast. Match the repo's existing pattern.

**Validation timing.** Tell: `onChange` validation showing errors as the user
types the first character. Why it hurts: yelling at someone mid-thought. Fix:
validate on blur and on submit; clear errors as they're fixed.

**Submit failure with no focus move.** Tell: server errors rendered above the form
with focus left on the button. Why it hurts: keyboard and AT users don't know
anything happened. Fix: focus the summary or the first invalid field; announce via
a live region.

**Ephemeral view state.** Tell: filters, tab selection, search text, sort, or an
open detail panel held in `useState`. Why it hurts: reload loses the user's place
and they can't share a link to what they're looking at. Fix: search params
(`URLSearchParams`, `nuqs`, the router's query API).

**Unhelpful error copy.** Tell: "Invalid input," "Something went wrong," "Error
422." Why it hurts: the user can't act. Fix: say what's wrong and what to do —
"Enter a date after today," "Couldn't save — check your connection and retry."

**Unsaved-changes trap.** Tell: a new multi-field form or editor with no dirty
guard on navigate/close. Fix: confirm before discarding, or autosave a draft.

**No feedback within ~100ms.** Tell: a click that triggers an async action with no
immediate state change. Fix: pending state on the control itself, immediately.

---

## Greppable signals

Fast first pass on a big diff. Every hit is a *candidate*, not a finding — read the
context before you write it up.

```bash
# a11y
rg -n '<div[^>]*onClick|<span[^>]*onClick|onKeyPress' --glob '*.{tsx,jsx}'
rg -n 'outline:\s*(none|0)|focus:outline-none' --glob '*.{css,scss,tsx,jsx}'
rg -n 'placeholder=' --glob '*.{tsx,jsx}'          # then check each for a label
rg -n 'aria-|role=' --glob '*.{tsx,jsx}'           # check each is on the right element
rg -n 'tabIndex=\{?[1-9]' --glob '*.{tsx,jsx}'
rg -n '<img(?![^>]*alt=)' -P --glob '*.{tsx,jsx,html}'

# design system
rg -n '#[0-9a-fA-F]{3,8}\b|rgba?\(' --glob '*.{tsx,jsx,css,scss}'
rg -n '\[[0-9]+px\]|:\s*[0-9]{1,3}px' --glob '*.{tsx,jsx,css,scss}'
rg -n '!important|z-index:\s*[0-9]{3,}|z-\[[0-9]{3,}\]'
rg -n 'style=\{\{' --glob '*.{tsx,jsx}'

# bundle
rg -n "^\+.*from '(moment|lodash|chart\.js|d3|jquery)'" --glob '*.{ts,tsx,js,jsx}'
rg -n 'import \* as' --glob '*.{ts,tsx,js,jsx}'
git diff origin/main -- package.json | rg '^\+\s+"'

# responsive / perf
rg -n '100vh|h-screen|min-w-\[|w-\[[0-9]{3,}px\]'
rg -n 'group-hover:opacity|hover:opacity-100|hover:block'
rg -n '<img|<video|<iframe' --glob '*.{tsx,jsx,html}'   # check width/height
rg -n 'offsetHeight|getBoundingClientRect|scrollHeight'

# state coverage — the highest-yield grep in this file
rg -n 'isLoading|isPending|isFetching' --glob '*.{tsx,jsx}' -A6 | rg -n 'error' -c
rg -n '\.map\(' --glob '*.{tsx,jsx}'    # then check for a zero-length branch
rg -n 'catch\s*\(\s*\w*\s*\)\s*\{\s*\}|catch\s*\{\s*\}'
```

## False-alarm guards

Credibility is the reviewer's only currency. Do not raise:

- A hard-coded value in a repo with no token layer — note it once, don't itemize.
- `useMemo`/`React.memo` "missing" on cheap computations over small data.
- Virtualization for a list that's bounded at 20 items.
- `100vh` in a desktop-only internal tool.
- Index keys on a static, never-reordered list.
- Missing `alt` on a genuinely decorative icon that already has `aria-hidden`.
- A `div` with a click handler *inside* a real `<button>` or `<a>`.
- Redundant `role` that's harmless (say "unnecessary" as a Nit, not "broken").
- Bundle impact from a dev dependency, or a lazy route the user rarely hits.
- Anything you'd have to redesign the feature to fix — one line, then defer.

And when the diff is clean, say it's clean. "No frontend concerns — visual check
performed at 375/768/1440, keyboard path clean, no token deviations" is a real
result that builds exactly the trust you need for the next review that isn't.
