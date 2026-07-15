## 🏛️ Architecture Review

**Reviewer:** Architecture Reviewer
**Model:** <!-- the model running this review, e.g. Claude Opus 4.8 / Claude Sonnet 5 / DeepSeek-V3 -->
**PR / Diff:** <!-- PR #, URL, or file/branch reviewed -->
**Verdict:** <!-- Blocks merge (Critical findings) | Fix before merge (Major) | Merge OK, minor notes | No architectural concerns -->

**Summary:** <!-- One or two sentences: the headline. What's the biggest structural risk, and does it block merge? -->

---

### Findings

<!--
List every finding, ordered by severity (Critical → Major → Minor → Nit).
Repeat the block below per finding. Omit blocks for categories with no findings.
If there are no findings at all, delete this section and keep only the summary above.
Do NOT include micro-optimization or line-level performance notes — those are out of scope for this review.
-->

#### [SEVERITY] — [Category] — `path/to/file.ext:LINE`

**What:** <!-- the structural problem: what responsibility is misplaced / which dependency points the wrong way / where the boundary leaks -->
**Why it costs:** <!-- what gets harder to change, test, or understand, and for whom -->
**Fix:** <!-- concrete design change: which responsibility moves where, which dependency flips, which seam to introduce -->

```
// before (sketch — only if it makes the fix unmistakable)

// after
```

---

### Checklist coverage

<!-- Quick note on each category so the author knows it was actually looked at. Use ✅ clean / ⚠️ finding / – not applicable -->

- Separation of concerns:
- Layering:
- Responsibilities:
- Coupling:
- Abstraction boundaries:
- API / contract design:
- Code organization:
- Maintainability & change cost:
