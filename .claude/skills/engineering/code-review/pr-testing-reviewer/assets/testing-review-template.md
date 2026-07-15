# 🧪 Test Review — QA Engineer's Eye

**Reviewer role:** Test Reviewer
**Model:** <!-- e.g. Claude Opus 4.8 / Claude Sonnet 5 / DeepSeek-V3 / GPT-5 — the model performing this review -->
**PR / change:** <!-- #123 — title, or file/branch reviewed -->
**Date:** <!-- YYYY-MM-DD -->

## Verdict

**<!-- ✅ Approve | 💬 Comment | 🔴 Request changes -->**

<!-- One or two sentences: is this change adequately tested to merge, and if not,
what's the biggest gap? -->

## Summary

<!-- 2-4 sentences. What the change does and what behaviors it introduces (in your
words, to show you understood what needs testing), and the headline test result:
well-covered, or N gaps including M critical. Say plainly whether a regression of
this change would be caught by the suite. -->

## Findings

<!-- One entry per issue, ordered by severity (Critical first). If there are no
findings, write "No testing gaps found." and rely on the coverage map below to show
what was examined. Delete the example. -->

### 🔴 Critical | 🟠 Major | 🟡 Minor | 🔵 Question — <short title>

- **Category:** <!-- Untested behavior | Missing edge case | Uncovered failure mode | Weak/vacuous assertion | Brittle test | Regression risk | Test design -->
- **Location:** `path/to/code.ext:LINE` <!-- the behavior at risk --> / `path/to/test.ext:LINE` <!-- the test, if one exists -->
- **Gap:** <!-- What behavior is unguarded, or why the existing test doesn't actually protect it. -->
- **Why it slips through:** <!-- The concrete demonstration: the input/branch with no failing test, or "flip line 42 >= to > and every test still passes". -->
- **Regression risk:** <!-- What could break later without the suite going red. -->
- **Suggested test:** <!-- Specific case to add or assertion to strengthen. Code snippet if helpful. -->

<!-- Example:
### 🔴 Critical — Empty-cart branch has no test
- **Category:** Untested behavior
- **Location:** `checkout/pricing.py:42` / no test
- **Gap:** The new `if not items: return 0` branch (the fix this PR is about) has no test entering it.
- **Why it slips through:** Deleting the guard entirely leaves all tests green — only the non-empty path is exercised.
- **Regression risk:** A future refactor drops the guard, empty-cart checkout divides by zero again, and CI stays green.
- **Suggested test:** `test_price_of_empty_cart_is_zero(): assert price([]) == 0`
-->

## Coverage map — behaviors vs. tests

<!-- The heart of a QA review: list the distinct behaviors the change introduces and
whether each has a test that would fail if it broke. Builds trust and makes gaps
obvious. Delete the example rows. -->

| Behavior / branch | Covered? | Test that guards it |
|---|---|---|
| <!-- normal price calc --> | ✅ | `test_price_basic` |
| <!-- empty cart --> | ❌ | none — see Critical finding |
| <!-- item over stock limit --> | ⚠️ weak | `test_over_limit` asserts only "no crash" |

## What I checked

<!-- The testing lenses you traced, to show the review was thorough. -->
- [ ] Behavior coverage — each new branch/path has a test that would fail if it regressed
- [ ] Edge cases and boundaries (empty, single, at-limit, zero, negative, null, large)
- [ ] Failure modes (exceptions, timeouts, malformed input, rollback, cleanup)
- [ ] Assertions are meaningful (would go red if the code were wrong)
- [ ] Tests aren't brittle (no time/order/network/float/private-internal coupling)
- [ ] Regression resistance (a reintroduced bug would be caught)
- [ ] Test design / maintainability

## Open questions for the author

<!-- Anything you couldn't confirm from the diff alone — fixtures, helpers, or
coverage config you couldn't see. Omit if none. -->
