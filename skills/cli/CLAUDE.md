# Maintaining the `cli` skill

Read the **ADR log** below before changing this skill — each entry carries a **Lens**, a
forward-looking rule to apply to the next decision so you don't re-litigate it. This file
is rationale only; operating detail lives in [SKILL.md](SKILL.md) and the resources, and
the human explainer in [README.md](README.md).

## Development contract

This is a **knowledge skill** (no `scripts/`, no Makefile `fix`/`ci`). The gates are
documentation gates, run from the repo root (never `cd`):

```bash
# regenerate the README TOC after editing headings
uvx --from md-toc md_toc --in-place --no-list-coherence github --header-levels 4 \
  .claude/skills/cli/README.md
# both must exit 0 (README diagrams)
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_contrast.ts   .claude/skills/cli/README.md
bun run .claude/skills/mermaidjs_diagrams/scripts/mermaid_complexity.ts .claude/skills/cli/README.md
```

Every file must stay **≤ 500 lines** (the `claude_skills/index.md` invariant) and
**brand-agnostic** (`agnostic_examples.md`).

## File map

| File | Role |
|------|------|
| `SKILL.md` | agent runtime: trigger frontmatter, route-by-intent table, the non-negotiable conventions, resource pointers |
| `README.md` | human explainer: purpose, quickstart, architecture diagram, pattern catalog, troubleshooting |
| `CLAUDE.md` | this file — decision lenses, file map, extension checklist, gotchas |
| `resources/cli-foundations.md` | the shared CLI skeleton everything builds on |
| `resources/static-spa-viewer.md` | static HTML SPA viewer (the largest pattern) |
| `resources/gha-templating.md` | workflow templating + glob distillation |
| `resources/git-worktrees.md` | cross-ref worktree lifecycle |
| `resources/svg-diagrams.md` | stencil-pack diagram generation |
| `resources/pr-comments.md` | sticky PR comments + CI-artifact embed |

## Architecture principles

- **Hub-and-spoke.** `cli-foundations` is the base; each feature resource is independent
  and loaded on demand. The always-loaded surface (`SKILL.md`) only *routes*.
- **One pattern family per resource**, each self-contained and cohesive. A resource that
  needs two unrelated halves is a split candidate (rebalance the tree, don't trim).
- **Skeletons, not copies.** Each resource carries the minimal *load-bearing* skeleton
  (≈20–60 lines) to paste and adapt — never a verbatim dump of a real 1000-line
  implementation (which would be brand-tied and would drift).
- **The cross-cutting conventions live once** in `SKILL.md` (fail-loud, root discovery,
  packaged assets, output discipline) and are referenced, not repeated, by resources.

## ADR log

### ADR-0001 — A knowledge skill, not a code tool
- **Status:** accepted.
- **Context:** the source material is a set of *patterns* spread across several working
  CLIs. Shipping a `scripts/` harness would mean a Makefile, tests, and the eval kit for
  code that only exists to be copied-and-adapted anyway — and any concrete script would
  bake in one project's choices.
- **Decision:** ship docs + copy-pasteable skeletons only; no `scripts/`.
- **Consequences:** no `make ci`; the gates are mdtoc + the two mermaid scripts on the
  README. Lower maintenance, no code-rot.
- **Lens:** when a skill's value is *transferable judgment* rather than a runnable
  operation, make it a knowledge skill — a half-tested helper script is worse than a
  precise skeleton the reader adapts with eyes open.

### ADR-0002 — Brand-agnostic distillation
- **Status:** accepted.
- **Context:** every pattern was distilled from named, project-specific tools. The
  `agnostic_examples.md` rule forbids project nouns leaking into skills/rules.
- **Decision:** generalise every example — generic command names, `<pack>/<name>`
  stencil ids, placeholder hex codes, `tool`/`app` rather than real names.
- **Consequences:** the skeletons read like OSS docs and transfer to any repo.
- **Lens:** when distilling from a real implementation, rename to the *role*
  ("a per-slice workflow", "the gate CLI"), never the instance — if a reader can tell
  which project it came from, it isn't distilled yet.

### ADR-0003 — Re-skin via design tokens is the anti-repetition lever
- **Status:** accepted.
- **Context:** the most-repeated work is rebuilding a viewer for a new look. A viewer's
  JS/HTML is large; forking it per brand is the trap.
- **Decision:** make the viewer read a `design-tokens.json` at runtime (palette/fonts/
  brand) and treat re-skinning as *editing that one file*, never forking the renderer.
- **Consequences:** one viewer implementation serves many brands; the skill's headline
  guidance is "re-skin, don't rebuild".
- **Lens:** when a generated asset varies only cosmetically across uses, externalise the
  cosmetics into one declarative file the artifact reads at runtime — the asset becomes
  build-once, re-skin-forever.

### ADR-0004 — Fail-loud is a cross-cutting invariant, stated once
- **Status:** accepted.
- **Context:** every source tool shares the same discipline (no silent degradation,
  fail-loud root discovery, loud missing-dep), echoing the repo's escalators-not-stairs
  rule. Repeating it in six resources would bloat them and drift.
- **Decision:** state the conventions once in `SKILL.md`; resources reference them.
- **Consequences:** resources stay focused on their mechanism; the contract is DRY.
- **Lens:** a convention that applies to *every* pattern belongs in the always-loaded
  router, stated once — not re-derived in each leaf.

## Extension checklist

- [ ] New pattern? Add `resources/<pattern>.md` (problem, mechanism, minimal skeleton,
      pitfalls), link it up to `SKILL.md` and laterally where it cross-references.
- [ ] Add a row to the `SKILL.md` route-by-intent table **and** the README pattern catalog.
- [ ] Generic names only; placeholder hex/identifiers; no project nouns.
- [ ] Every touched file ≤ 500 lines; split at a seam if it would exceed.
- [ ] README headings changed → regenerate the TOC (mdtoc).
- [ ] README diagrams → `mermaid_contrast.ts` and `mermaid_complexity.ts` both exit 0.
- [ ] Any skeleton that claims to run was sanity-checked, not invented.

## Known gotchas

- **Diagram gate failures:** a same-hue darker *stroke* on a primary fill fails the
  border-AA check; teal-600 under white text fails text-AA (use teal-700). Pair every
  `fill:` with an explicit `color:`. Primary = 600–700 fill + `stroke:#fff,color:#fff`;
  secondary = 100-shade fill + 500 stroke + `color:#1e293b`.
- **TOC markers:** the README's `<!--TOC-->` pair must stay; mdtoc fills between them.
  Hand-editing the TOC drifts from the headings.
- **Resource bloat:** `static-spa-viewer.md` is the densest and closest to the ceiling;
  if it grows, split the renderer-specific (Cytoscape vs Plotly) detail into a child
  rather than trimming the shared skeleton.
- **Skeleton drift:** these are *distilled* skeletons, not synced copies — when a source
  pattern genuinely evolves (e.g. a new verified artifact schema), update the skeleton
  deliberately; don't auto-track an implementation.
