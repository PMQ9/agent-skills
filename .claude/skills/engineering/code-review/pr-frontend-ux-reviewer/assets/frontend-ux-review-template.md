## 🎨 Frontend / UI / UX Review

**Reviewer:** Frontend / UI / UX Reviewer
**Model:** <!-- the model running this review, e.g. Claude Opus 5 / Claude Sonnet 5 / DeepSeek-V3 -->
**PR / Diff:** <!-- PR #, URL, or file/branch reviewed -->
**Visual check:** <!-- REQUIRED. One of:
  performed — <harness + what you rendered + widths, e.g. "Storybook, Button/Modal stories at 375/768/1440, keyboard walk, axe clean"
  attempted — <why it failed, e.g. "dev server needs a DATABASE_URL; static review only">
  not applicable — <why, e.g. "diff is CSS tokens only, no renderable surface changed"> -->
**Design system:** <!-- what you held the diff to, e.g. "CSS vars in src/styles/tokens.css + shadcn ui/ primitives" or "no token system found in repo" -->
**Verdict:** <!-- Blocks merge (Critical findings) | Fix before merge (Major) | Merge OK, minor notes | No frontend concerns -->

**Summary:** <!-- One or two sentences: the headline. What's the worst thing a real user hits, and does it block merge? -->

---

### Findings

<!--
Group findings under the four questions below; within each group, order by
severity (Critical → Major → Minor → Nit). Repeat the finding block per finding.
Omit any question-group with no findings — do not pad it.
Tag any finding you could not confirm without rendering: (unverified — needs visual check)
If there are no findings at all, delete this whole section and keep the summary + checklist.
Out of scope here: DB/server performance, module architecture, security. One line and a hand-off, no more.
-->

#### 1. Will the user see the right thing?

##### [SEVERITY] — [Category] — `path/to/file.tsx:LINE`

**What:** <!-- the user-facing defect, concretely: what renders wrong, what state is unhandled, what can't be operated -->
**Who it hurts:** <!-- keyboard user / screen reader user / phone user at 375px / anyone on a slow connection / the next dev who touches this -->
**Fix:** <!-- the concrete change: which element, which token, which existing component, which prop -->
**Evidence:** <!-- optional: "screenshot 375px shows the action row clipped" or "axe: color-contrast, 2.9:1" — only if you actually observed it -->

```
// before (only when it makes the fix unmistakable)

// after
```

#### 2. Is it consistent with the rest of the app?

<!-- same finding block -->

#### 3. Will it feel fast?

<!-- same finding block; quantify where you can — "≈70KB added to the dashboard chunk" beats "this is heavy" -->

#### 4. Will it work for everyone, on any device?

<!-- same finding block -->

---

### Checklist coverage

<!-- Mark every row so the author knows it was actually looked at. ✅ clean / ⚠️ finding / – not applicable -->

- State & data correctness:
- State coverage (loading / empty / error / disabled / focus):
- Design-system adherence (tokens, variants, no one-offs):
- Shared-primitive blast radius (callers checked):
- Bundle & load cost:
- Runtime & rendering cost (CLS, thrash, waterfalls):
- Accessibility (semantics, keyboard, focus, contrast, ARIA):
- Responsive & interaction UX (320→1440px, touch, error copy):

### Visual evidence

<!-- Omit this section entirely if no visual pass was performed.
Otherwise list what you rendered and where the files are — screenshots can't be
inlined in a gh comment, so describe each one next to the finding it supports. -->

- <!-- e.g. `screens/375-approvals.png` — action row clipped at the right edge -->
- <!-- e.g. `screens/1440-approvals-focus.png` — focus ring not visible on the gold primary button -->

### Deferred to other reviewers

<!-- Optional, one line each, only for things you genuinely noticed and are out of scope. Delete if empty. -->

- <!-- e.g. "The /api/approvals endpoint looks like an N+1 — pr-performance-reviewer." -->
