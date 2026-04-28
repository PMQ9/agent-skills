---
description: Move skills from a staging directory into the right .claude/skills/<domain>/<subdomain>/ location and update the README catalog.
argument-hint: "[optional source dir, defaults to .claude/skills/new-skills]"
---

# Organize new skills into the catalog

The user has dropped one or more `<skill-name>/SKILL.md` directories into a staging folder and wants them filed under `.claude/skills/<domain>/<subdomain>/<skill>/SKILL.md` with the [README.md](README.md) catalog updated to match.

Source directory: `$ARGUMENTS` if non-empty, otherwise `.claude/skills/new-skills/`.

The library is not engineering-only — anything could live at the top level (e.g. `engineering/`, `design/`, `product/`, `research/`, `writing/`, `ml/`). Today only `engineering/` exists, but a new skill may legitimately warrant a brand-new top-level domain. **Do not force-fit skills under `engineering/` if they don't belong there.**

## Procedure

**Step 1 — Inventory.** List the source directory. For each `<skill>/SKILL.md`, read enough of the file (frontmatter + the first section or two) to know what it's about. Skip anything that is not a `SKILL.md` directory.

**Step 2 — Survey existing categories.** List `.claude/skills/` (top-level domains) and each existing subdomain underneath, then read [README.md](README.md) to see how the catalog is currently scoped. The README's "Picking rules" and the existing per-skill "Use when" cells tell you what belongs where.

**Step 3 — Categorize.** For each new skill, pick the most specific existing path that fits:
- Prefer an existing `<domain>/<subdomain>/` over creating a new one.
- Create a new **subdomain** under an existing top-level domain when the skill is clearly in that domain but no subdomain fits (examples already in use: `reliability/`, `security/` under `engineering/`).
- Create a new **top-level domain** only when the skill genuinely doesn't belong under any existing top-level (e.g. a UX-research skill probably shouldn't live under `engineering/`). Surface this judgment call to the user explicitly in your summary.
- If two new skills overlap heavily with each other or with an existing skill, flag it rather than silently filing both — the README's convention is "bias toward fewer, broader skills."

**Step 4 — Move with `git mv`.** Use `git mv` (not `mv`) so history is preserved. Create any new directories with `mkdir -p` first. After all moves, remove the now-empty source directory with `rmdir` (it should be empty — if it isn't, stop and ask).

**Step 5 — Update the catalog.** Edit [README.md](README.md):
- Add a row in the matching `### <Domain> / <Subdomain>` table for each moved skill.
- If a new subdomain was created, add a new `### <Domain> / <Subdomain>` section (header + table) in the same style as existing sections. Place it where it reads naturally relative to neighboring sections.
- If a new top-level domain was created, add a top-level grouping for it as well — match the structure used for `Engineering / *` today.
- Each row's "Use when" cell is **one sentence** with concrete trigger keywords drawn from the skill's frontmatter `description` — do not paste the full description. Match the tone of existing rows (terse, keyword-dense, no marketing language).
- Use the same clickable-link format as existing rows: `[skill-name](.claude/skills/<domain>/<subdomain>/<skill>/SKILL.md)`.

**Step 6 — Verify.** Run `git status --short` and confirm: every new skill appears as a rename (`R`) or add under its new home, the source directory is gone, and `README.md` is modified. Report the placements back to the user as a short list (skill → destination), call out any new subdomains or top-level domains you created, and flag any judgment calls they may want to override.

## Rules

- Read each new SKILL.md's frontmatter before placing it. Do not categorize by directory name alone — names can be misleading.
- Do not edit the SKILL.md files themselves. This command only moves and catalogs.
- Do not invent catalog sections that don't have at least one skill in them.
- If the source directory is empty or missing, say so and stop. Don't fabricate skills to move.
