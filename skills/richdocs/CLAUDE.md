# richdocs — maintainer guide

Read the ADR log in [`resources/adr-log.md`](resources/adr-log.md) before changing
anything; every structural choice here was deliberate. Dev loop:

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
| `resources/prose-style.md` | global-audience standard for **authored** prose (no em-dash, Australian English, short clauses, inclusive language, standard vocabulary); self-contained copy (ADR-015) |
| `scripts/serve.py` | no-store localhost server (stdlib) |
| `scripts/stencil.py` | stencil query/extract CLI (stdlib, in-memory zip load) |
| `scripts/themecheck.py` | **brandpack contrast gate** — part of `make ci`. Checks the pairings the CSS actually renders (ADR-012) |
| `scripts/showcase.py` | **theme showcase** generator — gallery of every brand, or one brand alone (`--theme`). Composes architecture diagrams from the stencil pack as drawio-editable SVG (ADR-011) |
| `assets/showcase.{html,css,js}` | the showcase page. Placeholder-free JS/CSS; only `showcase.html` carries `{{...}}` |
| `scripts/md2html.py` | markdown → HTML companion **generator** (stdlib). Contains no HTML/CSS/JS source — it assembles the `assets/viewer.*` files (ADR-008) |
| `assets/viewer.html` | the page shell — the **only** file carrying `{{...}}` placeholders |
| `assets/viewer.css` | viewer chrome; all colour/font via `--rd-*` custom properties |
| `assets/viewer.js` | runtime renderer (marked → fenced-block upgrades → theme flip). **Placeholder-free by contract** — reads generation-time values from the `#rd-config` JSON block |
| `assets/viewer-cytoscape.js` | graph styling + render (`rdRenderCytoscape`). Inlined *before* `viewer.js` so its functions are hoisted. Placeholder-free (ADR-008) |
| `assets/viewer-deckgl.js` | 3D / geographic render (`rdRenderDeckGL`) + the OKLab/OKLCH maths and colour-space projections. Inlined *before* `viewer.js`, same hoisting contract (ADR-014) |
| `resources/themes/<name>/` | a built-in brand theme: `design-tokens.json` (required) + `theme.css` (optional). Selected with `--theme`; default brand is `osakanights` (ADR-009, ADR-018) |
| `tmp/richdocs/theme/<name>/` | **optional** project-local theme override (cwd-relative, gitignored). Shadows the built-in of the same name and adds project-only themes; absent ⇒ built-in set only (ADR-018) |
| `scripts/Makefile` | fix/ci contract per `.claude/rules/claude_skills/scripts.md` |
| `assets/stencils.json.zip` | vendored draw.io icon packs (~3.4 MB; see `assets/NOTICE`) |
| `assets/design-tokens.json` | default neutral brandpack (schema in `rich-blocks.md`) |
| `resources/adr-log.md` | the **ADR log** (ADR-001…018) — decision lenses; split out of this file for the 500-line invariant |
| `resources/learned/` | self-curated adjudications/facts (statefulness Pathway 2) — read before re-litigating a past failure |
| `vendor/mermaidjs_diagrams/` | wholesale vendored mermaid toolchain (parse/complexity + contrast gates, theming references) — refresh per ADR-007, never cherry-pick |

## Invariants

- Every prose file ≤500 lines (`.claude/rules/claude_skills/index.md`).
- Scripts are Tier B (stdlib-only, PEP-723, `uv run --no-project`); network
  is only consumed by the *browser* loading pinned CDN libs, never by the
  Python. Missing inputs crash loudly (escalators-not-stairs).
  Exception: `vendor/mermaidjs_diagrams/` is Tier A (bun + frozen lockfile)
  — it is vendored wholesale, not authored here (ADR-007).
- Self-contained: no file under this skill instructs the agent to run or
  read another skill's files (ADR-007).
- Outputs go to project-local `tmp/richdocs/`, never system `/tmp`.
- Anything embedded in a `<script>` escapes `</` → `<\/`.
- Same input → same output modulo `{{BUILD_ID}}`.

## ADR log

The full decision log (ADR-001 … ADR-018), each entry carrying its **Lens**, lives in
[`resources/adr-log.md`](resources/adr-log.md). Read it before changing anything and
apply each ADR's Lens to the next related decision. It was promoted to its own node to
keep this file under the 500-line invariant (`.claude/rules/claude_skills/index.md`); it
is the same log, just split out.

## Known gotchas

- **Symptom: page loads, data never arrives, console CORS error** — opened
  multi-file output over `file://`. Expected; use `serve.py` or `--inline`.
- **Symptom: a `<script>` written inside a markdown doc never runs** — by design.
  The doc is rendered into `innerHTML`, and browsers never execute scripts
  inserted that way (XSS mitigation). `<style>` blocks *do* apply. To pin a
  doc's initial theme, set `defaultTheme` in its brandpack — not a script.
- **Symptom: the showcase does not show a palette the brand clearly documents** —
  the schema cannot express it. Check `canvas.plotly.<mode>` for `muted` /
  `sequential` / `diverging`, and the top-level `status` (ADR-013).
- **Symptom: a Plotly heatmap renders with `height="NaN"`** — layout objects were
  shared between charts. **Plotly mutates the layout you hand it** (it writes
  computed ranges onto `xaxis`/`yaxis`), so an `Object.assign({}, base, …)` shallow
  copy leaks the bar chart's numeric y-range into the heatmap's categorical axis.
  Build a **fresh layout per chart**. Vector traces survive this; rasters do not.
- **Symptom: a theme passes every check but looks nothing like the brand** — the
  brandpack substituted a colour the brand does not own, because one token was
  asked to be both a fill and a text colour. Run `themecheck.py`; split
  `accent` / `onAccent` / `link` (ADR-012).
- **Symptom: a brandpack names a webfont but the page renders in system fonts** —
  the pack *chooses* faces, it cannot *load* them. Use `--theme`, whose `theme.css`
  does the `@import`. (A doc can also `@import` in its own `<style>` block.)
- **Symptom: a doc renders in another doc\'s brand** — pre-ADR-010 behaviour, or a
  hand-rolled output dir with a stale shared `design-tokens.json`. Each doc now
  owns `<stem>.tokens.json`; delete any leftover `design-tokens.json`.
- **Symptom: two docs with the same stem overwrite each other** — `write_multi`
  keys everything off `doc.stem`, so `a/DESIGN.md` and `b/DESIGN.md` collide.
  Render them to different `--out` dirs.
- **Symptom: a `plotly` chart renders squashed into a sliver** — `.rd-canvas` has no
  height in CSS, and `responsive: true` makes Plotly size itself to that
  content-driven parent, which collapses. **Every block renderer owes its container
  an explicit height** (`payload.height`, defaulting to 420); cytoscape and deckgl
  always did, plotly did not. Never "fix" this by putting a height on `.rd-canvas` —
  that would force one height on all three block types.
- **Symptom: a `deckgl` orbit scene renders correctly but is the size of a postage
  stamp** — deck's OrbitView `zoom` is `log2(pixels per world unit)`, **not** a map
  zoom. The spaces are normalised to a ~1-unit extent, so they need `zoom ≈ 9`; a
  map-like `zoom: 2` gives ~4 px of scene. A gamut study is also a horizontal *slab*
  at some lightness, so the camera must target `y = L - 0.5`, or the subject drifts
  to the top of the frame.
- **Symptom: a `deckgl` gamut scene shows spokes on the colours that are FINE and
  none on the colours that are broken** — the spoke is measuring distance to the
  sRGB ceiling, which is *unused headroom*, not clipping. A clipped swatch sits
  **on** the ring, so its headroom is zero. Set `targetChroma` (the requested value);
  clipping is `ceiling < target`, and it cannot be inferred from the hex alone
  (ADR-014).
- **Symptom: `deckgl` dots render darker / muddier than the swatch of the same
  hex** — deck.gl's lit layers (`PointCloudLayer`, `ColumnLayer`, …) shade each mark
  as a 3D solid under ambient+directional light, so the fill darkens and no longer
  matches its own colour. In a colour-space visualiser the mark *is* a colour claim;
  a lit mark makes it false. `rdBuildLayers` defaults `material: false` (lighting off)
  for exactly this reason — an author wanting shaded geometry opts back in per layer.
- **Symptom: a `deckgl` map with `basemapStyle` shows arcs but no basemap** —
  MapLibre was not loaded, so `rdRenderDeckGL` fell through to the plain-Deck path
  (which draws no tiles). The block only takes the MapLibre-overlay path when
  `maplibregl` is defined; load `cdn.maplibre` (+ its CSS) before rendering (ADR-017).
- **Symptom: duckdb-wasm dies with a cross-origin worker error** — a CDN worker URL
  cannot go straight to `new Worker`. Wrap it in a same-origin Blob that
  `importScripts` it (`new Blob(['importScripts("'+bundle.mainWorker+'");'])`). Pin
  the **stable** duckdb version — npm `latest` is a `-dev` build. 64-bit aggregates
  return as **BigInt**; coerce to `Number` before Plotly or `toFixed` (ADR-017).
- **Symptom: dark chrome, light charts after theme toggle** — a template fork
  dropped the canvas re-feed half of the flip (ADR-004). A `deckgl` block holds a
  **WebGL context**: it must be `finalize()`d and rebuilt on flip, never re-styled.
  The MapLibre-overlay path instead holds a `maplibregl.Map`, `remove()`d on rebuild.
- **Symptom: stale content despite edits** — something is caching; confirm
  the server sends `Cache-Control: no-store` and fetches carry `?v=`.
- **Symptom: `stencil.py` slow on first call** — 6.3 MB JSON parse on first
  load; cached for the process thereafter. Don't "fix" by unzipping to disk.
- **Symptom: mermaid renders once then blanks on re-theme** — mermaid must be
  re-initialised *and* the source re-inserted before `mermaid.run` (rendered
  SVG is not re-renderable).
- **Symptom: one mermaid block shows an error/blank in the companion, the
  rest render fine** — invalid mermaid syntax in the source fence (mindmaps
  reject quoted labels, leading parens, HTML entities). Run the vendored
  parse gate on the source `.md` (ADR-007); details in
  `resources/learned/mermaid-syntax-gate.md`.
- **Symptom: a flowchart node shows "Unsupported Markdown: list" instead of its
  label** — the label starts with a list marker (`1. `, `- `, `* `, `+ ` at the
  front of the quoted text, e.g. `S1["1. Renumber ADRs<br/>…"]`). The pinned
  mermaid 11.4.1 lexes every plain label as markdown (v11 regression, upstream
  issue #5824; fixed after 11.4.1 by PR #7276), and no `mermaid.initialize`
  option gates it. Authoring fix only: `"Step 1: …"`, `"1) …"`, or
  `"1&#46; …"`. The vendored parse gate does NOT catch this (the fence parses;
  only label rendering fails). Details:
  `resources/learned/mermaid-list-label-pitfall.md`.
- **Symptom: mermaid labels are cut mid-word (`Cloud Run: dev` → `Cloud Run: de`),
  but only under a `--theme` that carries a webfont** — mermaid sizes each label's
  `<foreignObject>` from its own measurement, which runs a few percent short against
  a brand face, and a `foreignObject` **clips by default**. The node shape has ample
  spare room, so the cure is to stop the clip, not to fix the measurement:
  `viewer.css` `.rd-mermaid foreignObject { overflow: visible; }`. Do **not** reach
  for `flowchart.wrappingWidth` (moves `max-width`, clip unaffected, wraps every
  other diagram) or a `document.fonts.ready` barrier (shortfall is identical) —
  both were tried and measured. Full autopsy, including the probe that settled it:
  `resources/learned/mermaid-foreignobject-clipping.md`.
- **Symptom: a subgraph/cluster TITLE is still cut after the above** — a cluster
  header has no spare height, so a title long enough to wrap loses its second line.
  This one is authored, not systemic: shorten the title.

## Extension checklist

- [ ] New fenced block type: add lazy loader + renderer in **`assets/viewer.js`**,
      token sub-palette if themable, contract section in `rich-blocks.md`,
      degradation behaviour on GitHub noted in `discovery-docs.md`.
- [ ] New stencil pack: re-vendor zip per `stencil-library.md`, smoke-test
      `packs`/`extract`, update NOTICE if provenance changed.
- [ ] Any `assets/viewer.*` change: run all three block types + theme flip in a
      real browser, in **both** `--inline` and multi-file mode. `make ci` cannot
      see browser behaviour (ADR-006).
- [ ] New generation-time value: add it to `build_config()` → the `#rd-config`
      block. **Never** add a `{{...}}` placeholder to `viewer.js` (ADR-008) — a
      test will fail, and the file stops being valid JS.
- [ ] Any authored prose (showcase copy, UI/error strings, this skill's docs, an
      upgraded discovery doc) follows `resources/prose-style.md` (ADR-015): no
      em-dash, Australian English, inclusive language. User markdown is rendered
      as written, never corrected.

## Related (maintainer provenance only — never cite from runtime surfaces)

- `../mermaidjs_diagrams/` — upstream source of `vendor/mermaidjs_diagrams/`, re-vendor per ADR-007
- `.claude/rules/claude_skills/index.md` — 500-line invariant, tree structure
