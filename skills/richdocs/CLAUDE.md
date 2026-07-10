# richdocs — maintainer guide

Read the ADR log below before changing anything; every structural choice here
was deliberate. Dev loop:

```bash
make -C .claude/skills/richdocs/scripts fix   # mutate: format + lint-fix
make -C .claude/skills/richdocs/scripts ci    # gate: must exit 0 before handoff
```

## File map

| File | Role |
|------|------|
| `SKILL.md` | agent operating manual: route-by-intent, command reference, block contract |
| `README.md` | human explainer: diagram, quickstart, troubleshooting |
| `resources/serving.md` | `file://` failure mode, no-store contract, pinned CDN table |
| `resources/stencil-library.md` | pack schema, tint mechanism, compose pattern, refresh procedure |
| `resources/rich-blocks.md` | fenced block contract, design-tokens schema, two-palette theming |
| `resources/discovery-docs.md` | per-archetype upgrade recipes, fidelity ladder |
| `scripts/serve.py` | no-store localhost server (stdlib) |
| `scripts/stencil.py` | stencil query/extract CLI (stdlib, in-memory zip load) |
| `scripts/md2html.py` | markdown → HTML companion generator (stdlib; template embedded) |
| `scripts/Makefile` | fix/ci contract per `.claude/rules/claude_skills/scripts.md` |
| `assets/stencils.json.zip` | vendored draw.io icon packs (~3.4 MB; see `assets/NOTICE`) |
| `assets/design-tokens.json` | default neutral brandpack (schema in `rich-blocks.md`) |

## Invariants

- Every prose file ≤500 lines (`.claude/rules/claude_skills/index.md`).
- Scripts are Tier B (stdlib-only, PEP-723, `uv run --no-project`); network
  is only consumed by the *browser* loading pinned CDN libs, never by the
  Python. Missing inputs crash loudly (escalators-not-stairs).
- Outputs go to project-local `tmp/richdocs/`, never system `/tmp`.
- Anything embedded in a `<script>` escapes `</` → `<\/`.
- Same input → same output modulo `{{BUILD_ID}}`.

## ADR log

### ADR-001 — Companion, not replacement

- **Status:** accepted
- **Context:** the repo's discovery docs must stay readable on GitHub and
  reviewable as plain diffs; earlier attempts elsewhere replaced markdown
  with HTML apps that rotted.
- **Decision:** the `.md` is canonical and committed; HTML is generated into
  gitignored `tmp/richdocs/` and regenerated at will. Fenced rich blocks
  degrade on GitHub to visible JSON code blocks.
- **Consequences:** no committed HTML to drift; sharing uses `--inline`.
- **Lens:** when a new feature tempts you to add authoring state to the HTML
  side, put it in the markdown or a data `.json` instead — the HTML must
  always be regenerable from scratch.

### ADR-002 — Packaged scripts here; teaching patterns stay in the `cli` skill

- **Status:** accepted
- **Context:** `cli/resources/static-spa-viewer.md` and `svg-diagrams.md`
  already teach these patterns for building into *your own* CLI; duplicating
  them here would violate the never-duplicate rule.
- **Decision:** `richdocs` ships runnable, generic tools; its resources cover
  only what's new (stencil pack, block contract, serving, recipes) and link
  laterally to the `cli` skill for the deep patterns.
- **Consequences:** a doc that outgrows the companion (needs routing,
  sidebar, views) graduates to the `cli` skill's SPA pattern — see the
  fidelity ladder in `discovery-docs.md`.
- **Lens:** before adding a feature to `md2html.py`'s template, ask "is this
  rung 4?" — if yes, it belongs in a project built via the `cli` skill, not
  here.

### ADR-003 — Vendored stencil zip, loaded in memory

- **Status:** accepted
- **Context:** the tfs `diagrams` module proved the draw.io extraction; the
  user wants the icon library on-hand without depending on the tools-tfs
  repo. GitHub renders SVG; icons work in markdown *and* HTML.
- **Decision:** copy `stencils.json.zip` + `NOTICE` into `assets/`;
  `stencil.py` unzips in memory (`io.BytesIO`, `functools.cache`), located
  relative to `__file__`. The extractor script is *not* vendored — refresh
  procedure documented in `stencil-library.md`.
- **Consequences:** ~3.4 MB in the repo (accepted); no runtime coupling to
  tools-tfs; re-extraction requires the source repo.
- **Lens:** when the pack needs new shapes, re-vendor the whole zip from the
  source extractor — never hand-edit entries or unzip into the repo.

### ADR-004 — Two-palette brandpack (chrome CSS vars + canvas JS palette)

- **Status:** accepted
- **Context:** proven in the adaf sdag viewer; canvas renderers (cytoscape,
  plotly) cannot read CSS custom properties.
- **Decision:** one `design-tokens.json` carries both palettes; the template
  applies `themes.*` as CSS vars and feeds `canvas.*` into renderers; theme
  flip does both. Data-encoding colours (`categoryColours`, status) are
  brand- and theme-invariant.
- **Consequences:** one hand-sync hazard remains: `FALLBACK_TOKENS` in the
  template JS mirrors the JSON. A test asserts they stay aligned.
- **Lens:** any new themable surface gets a token in *one* of the two
  palettes by asking "can CSS reach it?" — never a hardcoded hex in the
  template.

### ADR-005 — Pinned CDN, lazy canvas loads, no vendoring of JS libs

- **Status:** accepted
- **Context:** vendoring cytoscape/plotly/mermaid (~5 MB+) into every output
  dir was rejected; local viewing has network; offline is announced
  degradation.
- **Decision:** exact-version jsdelivr pins (table in `serving.md`);
  cytoscape/plotly injected only when a doc uses their blocks; fetch failures
  console.error and render visible error blocks.
- **Consequences:** fully-offline viewing is out of scope for v1; revisit
  with a `--vendor` flag if it becomes a real requirement.
- **Lens:** bump a pin deliberately (test all three block types), never by
  floating a major.

### ADR-006 — Evals deferred

- **Status:** accepted (deferred work)
- **Context:** `.claude/rules/claude_skills/evals.md` defines the golden/eval
  contract; building the harness now would have doubled the initial scope.
- **Decision:** ship v1 with the free deterministic gate only (`make ci`,
  ≥90% coverage). Eval goldens (render a fixture doc headlessly, assert
  blocks render) are the first follow-up.
- **Lens:** when the first regression slips past `ci` (likely a template/JS
  behaviour Python tests can't see), that's the trigger to build the eval
  suite — don't wait for a second.

## Known gotchas

- **Symptom: page loads, data never arrives, console CORS error** — opened
  multi-file output over `file://`. Expected; use `serve.py` or `--inline`.
- **Symptom: dark chrome, light charts after theme toggle** — a template fork
  dropped the canvas re-feed half of the flip (ADR-004).
- **Symptom: stale content despite edits** — something is caching; confirm
  the server sends `Cache-Control: no-store` and fetches carry `?v=`.
- **Symptom: `stencil.py` slow on first call** — 6.3 MB JSON parse on first
  load; cached for the process thereafter. Don't "fix" by unzipping to disk.
- **Symptom: mermaid renders once then blanks on re-theme** — mermaid must be
  re-initialised *and* the source re-inserted before `mermaid.run` (rendered
  SVG is not re-renderable).

## Extension checklist

- [ ] New fenced block type: add lazy loader + renderer in the template,
      token sub-palette if themable, contract section in `rich-blocks.md`,
      degradation behaviour on GitHub noted in `discovery-docs.md`.
- [ ] New stencil pack: re-vendor zip per `stencil-library.md`, smoke-test
      `packs`/`extract`, update NOTICE if provenance changed.
- [ ] Any template change: run all three block types + theme flip manually;
      `make ci` cannot see browser behaviour (ADR-006).

## Related

- `../cli/resources/static-spa-viewer.md` — full SPA viewer pattern (rung 4)
- `../cli/resources/svg-diagrams.md` — committed, drift-gated diagram artifacts
- `../mermaidjs_diagrams/` — mermaid complexity/contrast gates
- `.claude/rules/claude_skills/index.md` — 500-line invariant, tree structure
