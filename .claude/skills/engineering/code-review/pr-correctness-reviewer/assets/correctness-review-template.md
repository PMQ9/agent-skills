# 🐛 Correctness Review — Bug Hunter

**Reviewer role:** Correctness Reviewer
**Model:** <!-- e.g. Claude Opus 4.8 / Claude Sonnet 5 / DeepSeek-V3 / GPT-5 — the model performing this review -->
**PR / change:** <!-- #123 — title, or file/branch reviewed -->
**Date:** <!-- YYYY-MM-DD -->

## Verdict

**<!-- ✅ Approve | 💬 Comment | 🔴 Request changes -->**

<!-- One or two sentences: is this safe to merge, and if not, what's the blocker? -->

## Summary

<!-- 2-4 sentences. What the change does (in your words, to show you understood
intent), and the headline correctness result: clean, or N findings including M
critical. -->

## Findings

<!-- One entry per issue, ordered by severity (Critical first). If there are no
findings, write "No correctness issues found." and rely on the checklist below to
show what was examined. Delete the example. -->

### 🔴 Critical | 🟠 Major | 🟡 Minor | 🔵 Question — <short title>

- **Category:** <!-- Logic error | Edge case/boundary | Null/undefined | State management | Validation | Error handling | Business rule | Regression -->
- **Location:** `path/to/file.ext:LINE` <!-- or function name -->
- **Problem:** <!-- What is wrong. -->
- **Trigger:** <!-- The concrete input or sequence that makes it fail, e.g. "when `items` is empty" or "if two requests arrive before the first commits". -->
- **Consequence:** <!-- What breaks: wrong result / crash / data loss / broken caller. -->
- **Suggested fix:** <!-- Specific, minimal change. Code snippet if helpful. -->

<!-- Example:
### 🔴 Critical — Division by zero on empty cart
- **Category:** Edge case/boundary
- **Location:** `checkout/pricing.py:42`
- **Problem:** `average = total / len(items)` runs before the empty-cart guard.
- **Trigger:** User checks out with an empty cart (`items == []`).
- **Consequence:** `ZeroDivisionError`, request 500s, checkout fails.
- **Suggested fix:** Return early when `not items`, or guard: `total / len(items) if items else 0`.
-->

## What I checked and considered fine

<!-- Builds trust and shows the review was thorough. Note the correctness lenses
you traced that held up, e.g.: -->
- [ ] Logic matches the described intent
- [ ] Edge cases / boundaries (empty, single, limits, zero, negatives)
- [ ] Null / undefined / missing-data handling
- [ ] State management (mutation, ordering, races, async)
- [ ] Input validation
- [ ] Error handling and resource cleanup
- [ ] Business rules / domain invariants
- [ ] Regressions for existing callers and data

## Open questions for the author

<!-- Anything you couldn't confirm from the diff alone (unclear intent, callers
you couldn't see). Omit if none. -->
