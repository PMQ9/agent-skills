# Visual Verification Playbook

Rendering the UI is what makes this reviewer worth more than a careful read. A
diff can tell you `outline: none` was added; only a browser tells you the
replacement ring is invisible, the action row clips at 375px, the modal traps
focus behind the overlay, or the page shifts 0.3 CLS while the avatar loads.

This playbook is a ladder. Climb as far as the environment lets you, then stop and
report honestly where you got to. **A static review is a fine outcome; a vague
review is not.**

## Contents

1. Is a visual pass worth it?
2. Trust check before you run anything
3. Pick the cheapest harness
4. Start the harness
5. Drive the browser
6. The five checks that need a browser
7. Bundle cost without guessing
8. Screenshots and evidence
9. When to give up, and how to say so

---

## 1. Is a visual pass worth it?

Yes when the diff changes something that renders: components, templates, CSS,
tokens, layout, icons, a new screen or route. Also yes when a finding hinges on
something invisible in code — contrast, focus order, overflow, shift.

No when the diff is types, tests, config, a data hook with no visual change, or a
pure refactor with identical output. Mark **Visual check: not applicable** and say
why. Don't burn five minutes booting an app to look at a screen the diff didn't
touch.

Budget: **roughly three minutes of honest setup effort.** You are reviewing a PR,
not fixing someone's toolchain.

## 2. Trust check before you run anything

`npm install` and `npm run dev` execute code from the branch — install scripts,
config files, dev-server plugins. That's fine for your own repo or a colleague's
branch. It is **not** fine for a fork from an unknown external contributor, where
the diff itself may be the attack.

Before running anything, check whether the PR comes from a fork by an untrusted
author:

```bash
gh pr view 123 --json headRepositoryOwner,author,isCrossRepository
```

If it's a cross-repository PR from someone outside the org, prefer static review
and say so in the Visual check field ("attempted — external fork, not building
untrusted branch locally"). Reviewing a diff never requires executing it.

## 3. Pick the cheapest harness

In order of preference — the goal is the smallest thing that renders the changed
component.

```bash
# 0. Is something already running? Cheapest possible win.
lsof -iTCP -sTCP:LISTEN -P -n 2>/dev/null | grep -E ':(3000|3001|4200|5173|5174|6006|8080|8000)'

# 1. What does the project offer?
cat package.json | jq '.scripts'

# 2. Storybook / component playground — best harness for a component-level diff:
#    isolated, no auth, no database, states already enumerated as stories.
ls .storybook 2>/dev/null; rg -l '\.stories\.(tsx|jsx|ts|js|mdx)$' --files | head

# 3. Dev server (vite/next/nuxt/sveltekit/CRA)
#    Fast, but may need env vars, auth, or an API.

# 4. Static build + preview (vite build && vite preview, next build && next start)
#    Slower; only worth it if you also want real bundle numbers.

# 5. A one-off harness: render the changed component in a scratch page or an
#    existing test that mounts it (Playwright component test, Vitest browser mode).
```

If the component needs props you don't have, a scratch story or a small harness
page with realistic mock data beats giving up — but time-box it. Two minutes, not
twenty.

## 4. Start the harness

Start it in the background, wait for the port, and keep the log so you can quote
build errors instead of guessing:

```bash
cd "$REPO"
# Prefer the project's package manager: pnpm > yarn > npm, per its lockfile
(pnpm install --frozen-lockfile || npm ci || npm install) > /tmp/install.log 2>&1

nohup pnpm dev > /tmp/dev.log 2>&1 &        # or: pnpm storybook, npm run dev
for i in $(seq 1 30); do
  curl -sf http://localhost:5173 >/dev/null && echo "UP" && break
  sleep 2
done
tail -20 /tmp/dev.log
```

Common blockers and the right response:

| Blocker | Response |
|---|---|
| Missing env vars (`DATABASE_URL`, API keys) | Try Storybook instead; else fall back to static |
| Needs auth to reach the screen | Storybook, or a direct component harness |
| Install needs private registry creds | Fall back to static, note it |
| Build fails **on the base branch too** | Not the PR's fault — fall back, note it |
| Build fails **only on the PR branch** | That *is* a finding. Report it as Critical with the error from the log |

That last row matters: a branch that doesn't build is the most user-facing defect
there is. Verify against base before blaming the PR.

## 5. Drive the browser

Any of these work; use what's available. If the tools are deferred, load them with
ToolSearch in a single call.

**Playwright MCP** (preferred — has an accessibility snapshot):
`browser_navigate`, `browser_resize`, `browser_take_screenshot`,
`browser_snapshot` (a11y tree), `browser_press_key`, `browser_click`,
`browser_hover`, `browser_evaluate`, `browser_console_messages`,
`browser_network_requests`, `browser_close`.

**Claude in Chrome**: `navigate`, `resize_window`, `computer` (screenshot),
`read_page`, `javascript_tool`, `read_console_messages`.

**Plain Playwright** when no browser MCP is available:

```bash
npx --yes playwright@latest install chromium >/dev/null 2>&1
cat > /tmp/shots.mjs <<'EOF'
import { chromium } from 'playwright';
const url = process.argv[2], out = process.argv[3] || '/tmp/screens';
const widths = [{w:375,h:812,n:'375-mobile'},{w:768,h:1024,n:'768-tablet'},{w:1440,h:900,n:'1440-desktop'}];
const b = await chromium.launch();
for (const {w,h,n} of widths) {
  const p = await b.newPage({ viewport:{width:w,height:h}, deviceScaleFactor:2 });
  await p.goto(url, { waitUntil:'networkidle' });
  await p.screenshot({ path:`${out}/${n}.png`, fullPage:true });
  await p.close();
}
await b.close();
EOF
mkdir -p /tmp/screens && node /tmp/shots.mjs http://localhost:5173/approvals /tmp/screens
```

Widths to check: **375** (phone), **768** (tablet), **1440** (desktop), plus
**320** when the diff has dense content or a table — 320px is where reflow
actually breaks. Screenshot each. Look for clipping, horizontal scroll, overlapping
text, a table running off-screen, controls stacked into unusable slivers.

## 6. The five checks that need a browser

### a. Contrast — measure, don't estimate

```js
// browser_evaluate / javascript_tool — report computed pairs, then compute ratio
() => [...document.querySelectorAll('button, a, [class*="badge"], input, label, h1, h2, p')]
  .slice(0, 60)
  .map(el => {
    const s = getComputedStyle(el);
    let bgEl = el, bg = s.backgroundColor;
    while (bgEl && (bg === 'rgba(0, 0, 0, 0)' || bg === 'transparent')) {
      bgEl = bgEl.parentElement;
      bg = bgEl ? getComputedStyle(bgEl).backgroundColor : 'rgb(255,255,255)';
    }
    return { el: el.tagName + (el.className ? '.' + String(el.className).slice(0,40) : ''),
             text: el.textContent?.trim().slice(0, 30),
             color: s.color, bg, size: s.fontSize, weight: s.fontWeight };
  })
```

Then compute the ratio (WCAG relative luminance) for each pair and compare
against **4.5:1** for body text, **3:1** for text ≥18.66px bold or ≥24px, and
**3:1** for non-text UI (borders of inputs, icon-only buttons, focus rings). Report
the measured number — "2.9:1, needs 4.5:1" is an unarguable finding; "looks low
contrast" is not.

### b. Keyboard walk

Tab from the top of the changed region to the bottom, recording each stop:

```
browser_press_key "Tab"  → browser_evaluate:
  () => { const a = document.activeElement;
          const r = a.getBoundingClientRect();
          const s = getComputedStyle(a);
          return { tag:a.tagName, name:a.getAttribute('aria-label')||a.textContent?.trim().slice(0,40),
                   role:a.getAttribute('role'), outline:s.outlineWidth+' '+s.outlineColor,
                   boxShadow:s.boxShadow, visible:r.width>0 && r.height>0, rect:[r.x|0,r.y|0,r.width|0,r.height|0] }; }
```

What you're looking for: every interactive element gets a stop; nothing is
skipped; nothing is reachable but invisible; the order matches visual order; each
focused element has a *visible* indicator (outline or box-shadow, ≥3:1 against
its background); target rects meet 44×44 where touch matters. In a modal: focus
moves in on open, `Tab` cycles inside, `Escape` closes, focus returns to the
trigger. Screenshot a focused state — it's the most persuasive evidence there is.

### c. Automated a11y sweep

Cheap and high-yield when it works. Inject axe if network allows, else use the
accessibility snapshot:

```js
// If a CDN is reachable
await import('https://cdn.jsdelivr.net/npm/axe-core@4/axe.min.js')
  .then(() => axe.run()).then(r => r.violations.map(v => ({ id:v.id, impact:v.impact, n:v.nodes.length,
    nodes: v.nodes.slice(0,3).map(n => n.target.join(' ')) })));
```

```bash
# Or locally, if the repo already has it
rg -n '"@axe-core|jest-axe|axe-playwright' package.json
npx --yes @axe-core/cli http://localhost:5173/approvals --exit 0
```

No network and no local axe? `browser_snapshot` gives the accessibility tree —
scan it for controls with no accessible name, `generic` where a landmark or button
should be, and inputs with no label. Treat axe as a floor, not a ceiling: it
catches maybe a third of real issues and can't judge focus order or whether the
name makes sense.

### d. Layout shift and load feel

```js
// Run before navigation completes, then read after
() => new Promise(res => {
  let cls = 0;
  new PerformanceObserver(l => { for (const e of l.getEntries()) if (!e.hadRecentInput) cls += e.value; })
    .observe({ type:'layout-shift', buffered:true });
  setTimeout(() => {
    const nav = performance.getEntriesByType('navigation')[0];
    const lcp = performance.getEntriesByType('largest-contentful-paint').pop();
    res({ cls:+cls.toFixed(3), lcpMs: lcp && Math.round(lcp.startTime),
          transferKB: Math.round(performance.getEntriesByType('resource')
            .reduce((a,r)=>a+(r.transferSize||0),0)/1024) });
  }, 3000);
})
```

CLS > 0.1 is a real finding; pair it with the element that shifted (usually an
unsized image or late-loading content). `browser_network_requests` shows the
waterfall — a child request that only starts after a parent response is the
waterfall finding, visible right there in the timings.

### e. Theme and motion emulation

```js
// Playwright MCP: browser_evaluate won't change the media query — use the plain script:
// const p = await b.newPage({ colorScheme:'dark', reducedMotion:'reduce' });
```

Check dark mode if the project has it (a hard-coded light color will show up
instantly as a white box in a dark page), and check that new animation actually
stops under `prefers-reduced-motion: reduce`. Also try 200% zoom (or a 640px
viewport at `deviceScaleFactor: 2`) for the reflow requirement.

## 7. Bundle cost without guessing

Don't assert a number you didn't measure. Three tiers, in order of cost:

1. **Read the diff.** A new dependency in `package.json` plus how it's imported is
   often enough to say "this pulls the whole library; import the submodule." Say
   "≈" and name your basis ("lodash full build is ~70KB min").
2. **Ask the registry** (no build needed):
   ```bash
   npm view <pkg> dist.unpackedSize version
   ```
   Unpacked size overstates gzipped bundle impact — say which you're quoting.
3. **Measure both branches** when the build is fast and the claim is load-bearing:
   ```bash
   git stash -u; git checkout -q "$BASE"; pnpm build >/dev/null 2>&1
   du -sk dist .next/static 2>/dev/null | tee /tmp/base-size
   git checkout -q -; pnpm build >/dev/null 2>&1
   du -sk dist .next/static 2>/dev/null | tee /tmp/head-size
   ```
   Two builds is a few minutes — worth it for a suspected hundreds-of-KB
   regression on a critical route, not for a Minor.

## 8. Screenshots and evidence

Save under a predictable path and name by width + screen + state so the review can
cite them:

```
/tmp/pr-<N>-screens/375-approvals.png
/tmp/pr-<N>-screens/375-approvals-overflow.png
/tmp/pr-<N>-screens/1440-approvals-focus-primary.png
/tmp/pr-<N>-screens/dark-approvals.png
```

In the review, describe what each shows next to the finding it supports —
`gh pr comment` can't upload images, so the description is what travels. Tell the
user the directory so they can attach files themselves. And say plainly which
findings came from the render and which from reading the code; the author will
trust the whole review more for the distinction.

## 9. When to give up, and how to say so

Stop when: the time-box is spent, the app needs infrastructure you don't have, the
branch is untrusted, or the harness fails on base too. That's not a failure of the
review — it's a bounded reviewer being honest.

Fill the template's **Visual check** field with the real state, and tag the
findings that stayed unconfirmed:

```
**Visual check:** attempted — dev server needs DATABASE_URL and Storybook isn't
set up in this repo; review is static. Contrast and focus-ring findings below are
marked unverified.
```

```
##### Major — Accessibility — `Button.tsx:31` (unverified — needs visual check)
**What:** `focus:outline-none` with no replacement ring in the class list, so
keyboard users likely lose the focus indicator on the primary action.
```

That gives the author exactly what they need: what you found, how confident you
are, and what a human should still put eyes on.
