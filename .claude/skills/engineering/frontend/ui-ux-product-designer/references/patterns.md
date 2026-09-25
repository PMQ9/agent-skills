# UI Pattern Catalog

Established solutions for the screen types you'll design most. Prefer these to inventing something novel — a pattern the user already knows is a usability head start. Each entry gives the shape, the key decisions, and the failure modes to avoid. These reflect the CCC house conventions; swap tokens for a different brand but keep the structure.

**Contents:** 1) Dashboards & work queues · 2) Data tables & lists · 3) Forms & the prefill doctrine · 4) Navigation & app shell · 5) Mobile & responsive · 6) AI / chat / assistant interfaces · 7) States (loading/empty/error).

---

## 1. Dashboards & work queues

**The landing screen is the user's work, not a menu.** For an operational tool, open on a queue of things to act on — pending approvals, items assigned to me, overdue records — not a hub of links.

- **Stat tiles** across the top: a big `tabular-nums` number (~28px bold), an uppercase caption, optional trend chip. **Every tile links** to the filtered view it counts ("12 pending" → the pending queue). A tile that doesn't drill in is decoration.
- Below the tiles, the **primary queue**: a table/list of actionable rows with the most decision-relevant columns and inline actions.
- Order tiles/sections by what the user acts on most, left-to-right, top-to-bottom.
- Charts are for *understanding trends*, not for operational work — put them below the queue or on a separate analytics view. Resolve chart colors in JS (Recharts can't read the theme class); label axes; never rely on color alone to distinguish series (also vary via legend/labels).
- Failure modes: a wall of charts with nothing to click; vanity metrics nobody acts on; a landing page that's just navigation.

## 2. Data tables & lists

The default for showing many records. Get the columns and density right and it does most of the work.

- **Anatomy:** header (title + count + primary action) → filter row (search + facets, auto-submitting, with dismissible chips showing active filters) → rows → actionable empty state.
- **Columns:** show only decision-relevant fields; push the rest into a row expand or a detail drawer. Left-align text, right-align/`tabular-nums` numbers, keep the primary identifier first and sticky if it scrolls.
- **Row interaction:** inline action for a single-field decision (approve/reject); click-through to a URL-addressable **detail drawer** (`?sel=`/`[id]`) for review; row expand for a few more fields. Pick one primary interaction per row and be consistent.
- **Quiet headers:** `text-xs font-medium text-muted-foreground`, uppercase optional. Rows `border-b hover:bg-accent`, selected `bg-accent`. De-emphasize rows with muted tokens, **never opacity**.
- **Mobile:** collapse to **stacked cards below `lg`**, each cell keeping its label (`data-label`). If you must keep a table, let it scroll horizontally at natural width with a visible scrollbar rather than crushing columns.
- **Bulk actions:** checkbox column → a sticky action bar that appears on selection; keep keyboard support (`j/k` to move, `a`/`r` to act) for power queues.
- Failure modes: 15 columns nobody reads; pagination when a filter was wanted; a table that becomes an unreadable 2px-column mess on a phone.

## 3. Forms & the prefill doctrine

Forms are where tools are won or lost. Minimize what the user has to type and make every field trustworthy.

- **Prefill doctrine.** Fill what you can know: deterministic values are prefilled and tagged with a **provenance chip** (`record | computed | directory | parsed`) so the user knows where a value came from and whether to trust it. AI-drafted values ride a **draft banner** behind an explicit accept/confirm gate — never silently commit a model guess. Money/amounts are **never** model-drafted. Identity fields use **person/unit pickers**, never raw ID text entry.
- **Layout:** single logical column for flow; a responsive `minmax(230px, 1fr)` grid where fields are naturally paired (city/state). Group with section headers; don't exceed what fits the task. Label above the field.
- **Validation:** schema-driven (react-hook-form + Zod in the house stack). Validate on blur/submit, show errors inline in a `role="alert"`, specific and recoverable, and move focus to the first error. Keep the submit button enabled and explain what's missing rather than disabling it silently.
- **One primary action.** "Save" / "Create & submit" as the filled primary button; "Cancel" as a ghost/link. The action keeps its verb into the confirmation toast ("Submit" → "Submitted").
- **Long forms:** break into steps with a visible progress indicator; save drafts; don't lose input on error or navigation.
- Failure modes: asking for what you already know; placeholder-as-label; a disabled submit with no hint; destructive actions with no confirm (use type-to-confirm for irreversible ones).

## 4. Navigation & app shell

- **One shell** across an app family: a grouped, role-filtered **left sidebar** (≤16 visible items, ≤7 per group, one nesting level) + a **top bar** with breadcrumbs, a **⌘K command palette** (entity search + recents/favorites), a "+ New" quick-create, and an inbox/notification count.
- Active item: filled/`bg-accent` pill + `aria-current="page"`. Keep the current location obvious at all times.
- **URL is the state:** tabs are validated `?tab=` params (not parallel component state), drawers are addressable (`?sel=`), depth budget ≤3 route segments. This makes everything linkable and back-button-correct.
- **Collapse** the sidebar to a wrapping top bar / hamburger below ~860px; keep the mobile nav within a bounded scroll band.
- Failure modes: deep nested menus; a nav that hides the primary task; state that isn't in the URL so links and back button break.

## 5. Mobile & responsive

- **Design the content priority, then let it reflow.** Decide the one thing that matters most per screen and keep it above the fold at 360px.
- Breakpoints (Tailwind): `sm 640 · md 768 · lg 1024 · xl 1280`. Tables → cards at `lg`; multi-column forms → single column; sidebar → top bar around 860px.
- **Touch:** targets ≥44×44px, spaced so fat fingers don't misfire; no hover-only affordances (hover doesn't exist on touch — put the action inline or in a menu); bottom-reachable primary actions on tall screens.
- Test at 200% zoom and 320–360px width; never let a fixed element clip or a horizontal scroll appear unintentionally.

## 6. AI / chat / assistant interfaces

Designing an LLM-powered surface adds trust, latency, and error concerns ordinary UI doesn't have. The through-line: **make the AI's contributions visible, correctable, and never silently authoritative.**

- **Streaming & latency:** stream tokens so the user sees progress; show a thinking/typing state within 100ms; make long operations cancellable. Never leave a blank screen while the model works.
- **Provenance & trust:** mark AI-generated content distinctly (a draft banner, a subtle badge, a different surface tint), and show sources/citations when the answer rests on retrieved data. Let the user tell your text from the model's.
- **Human-in-the-loop:** any consequential action the AI proposes (send, submit, delete, spend, change a record) goes behind an explicit **confirm/accept gate** — surface the diff/draft, let the user edit, then commit. This is the prefill doctrine applied to generated values.
- **Editable drafts, not fait accompli:** put model output into editable fields with an accept step, not directly into the record. Show what changed.
- **Errors & uncertainty:** design for the model being wrong or refusing — a clear fallback, a retry, an easy path to a human. Let the model express low confidence rather than bluff.
- **Input affordances:** a roomy multiline composer, submit on ⌘/Ctrl-Enter (Enter for newline in long-form, or the reverse for quick chat — pick and label it), attachment/context chips, and a visible token/character ceiling if one exists.
- **Conversation UI:** clear author attribution (user vs assistant), timestamps on demand, copy/regenerate/feedback (👍/👎) affordances per message, and a way to reference or branch prior turns for longer sessions.
- **Feedback loop:** capture thumbs/edits/corrections — they're the signal for improving prompts and models.
- Failure modes: a spinner with no output; generated text written straight to the record; no way to correct a wrong answer; hiding that content is AI-made; irreversible AI actions with no confirm.

> For the engineering side of these (model choice, structured output, retries, cost/latency, prompt-injection defense, HITL economics), compose with the `llm-application-engineering`, `agent-design`, `human-in-the-loop-workflows`, and `prompt-injection-defense` skills.

## 7. States — design all four, every time

An element isn't designed until its non-happy states are.

- **Loading:** prefer **skeletons** (layout-shaped placeholders) for content areas over spinners; spinners are fine for buttons/inline. Keep perceived structure stable so nothing jumps.
- **Empty:** say what would be here and offer the next action ("No pending requests. New requests appear here as they're submitted." + a "Create" button if relevant). An empty state is an onboarding opportunity, not a dead end.
- **Error:** say what happened and how to recover, specifically; offer retry; don't blame the user or apologize hollowly. Never a raw stack trace.
- **Success:** confirm with a toast that echoes the action verb; update the UI to reflect the new state rather than making the user refresh.
