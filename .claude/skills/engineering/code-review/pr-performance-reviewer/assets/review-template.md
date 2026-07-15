## ⚡ Performance Review

**Reviewer:** Performance Reviewer
**Model:** <!-- the model running this review, e.g. Claude Opus 4.8 / Claude Sonnet 5 / DeepSeek-V3 -->
**PR / Diff:** <!-- PR #, URL, or file/branch reviewed -->
**Verdict:** <!-- Blocks merge (Critical findings) | Fix before merge (Major) | Merge OK, minor notes | No performance concerns -->

**Summary:** <!-- One or two sentences: the headline. What's the worst thing, and does it block merge? -->

---

### Findings

<!--
List every finding, ordered by severity (Critical → Major → Minor → Nit).
Repeat the block below per finding. Omit categories with no findings.
If there are no findings at all, delete this section and keep only the summary above.
-->

#### [SEVERITY] — [Category] — `path/to/file.ext:LINE`

**What:** <!-- what the code does that is inefficient -->
**Why it costs:** <!-- what grows with what: "one query per row, so N queries for N items" -->
**Fix:** <!-- concrete, minimal change at the implementation level -->

```
// before (only if it makes the fix unmistakable)

// after
```

---

### Checklist coverage

<!-- Quick note on each category so the author knows it was actually looked at. Use ✅ clean / ⚠️ finding / – not applicable -->

- N+1 queries:
- Unnecessary / repeated DB calls:
- Expensive loops:
- Memory allocations:
- Async misuse:
- Blocking I/O:
- Caching opportunities:
