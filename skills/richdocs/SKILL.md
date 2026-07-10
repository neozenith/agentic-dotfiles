---
name: richdocs
description: "Generate and serve rich HTML companions to markdown discovery documents: paired markdown→HTML rendering (marked + mermaid + data-driven cytoscape/plotly fenced blocks), a vendored draw.io stencil library (~AWS/GCP/Azure/K8s SVG icons) for composing custom architecture diagrams, an injectable design-tokens brandpack, and a reliable localhost server for HTML that pulls pinned CDN libraries. Use when turning a review/architecture/cost markdown doc into an interactive HTML view, when a diagram needs real cloud provider icons, when serving local HTML that file:// breaks, or when building a data-driven graph/chart view. Skip for plain mermaid-in-markdown work (use mermaidjs_diagrams) and for Python-rendered architecture diagrams (use mingrammer_diagrams)."
argument-hint: "[markdown-file | stencil-search-term]"
user-invocable: true
---

# richdocs — rich HTML companions for discovery docs

Markdown stays the source of truth. This skill generates an HTML *companion*
that renders the same `.md` with higher fidelity — interactive graphs, tinted
provider icons, branded theming — and serves it reliably on localhost.

## Route by intent

| Intent | Do this |
|--------|---------|
| "Make an HTML version of DOC.md" | `md2html.py DOC.md` then `serve.py` (multi-file, live-editable) |
| "One file I can open / attach" | `md2html.py DOC.md --inline` (self-contained, opens over `file://`) |
| "I need an AWS/GCP/Azure/K8s icon" | `stencil.py search TERM` → `stencil.py extract ID --color HEX` |
| "Build a custom SVG diagram with real icons" | read `resources/stencil-library.md` (registry + compose pattern) |
| "Interactive graph / chart in the doc" | fenced ` ```cytoscape ` / ` ```plotly ` block — see `resources/rich-blocks.md` |
| "HTML looks broken opened from Finder" | `file://` blocks fetch — run `serve.py` (see `resources/serving.md`) |
| "Re-brand the output" | edit `design-tokens.json` in the output dir, refresh — no rebuild |
| "Upgrade one of this repo's root docs" | read `resources/discovery-docs.md` (per-archetype recipes) |

## Quickstart

```bash
# 1. Render a markdown doc into a rich HTML companion (multi-file, live mode)
uv run --no-project .claude/skills/richdocs/scripts/md2html.py TARGET_ARCHITECTURE.md

# 2. Serve it (no-store headers, CDN libs load fine over http://localhost)
uv run --no-project .claude/skills/richdocs/scripts/serve.py tmp/richdocs --open

# 3. Or produce one self-contained file (no server needed)
uv run --no-project .claude/skills/richdocs/scripts/md2html.py REVIEW.md --inline

# 4. Grab a tinted provider icon
uv run --no-project .claude/skills/richdocs/scripts/stencil.py search lambda
uv run --no-project .claude/skills/richdocs/scripts/stencil.py extract "mxgraph.aws4/lambda" \
  --color '#ED7100' --out diagrams/lambda.svg
```

Run everything from the repo root. Never `cd`.

## Command reference

### `md2html.py DOC.md [--out DIR] [--inline] [--tokens FILE] [--title T]`

- **Multi-file (default, `--out` = `tmp/richdocs`)** — writes `<stem>.html`
  plus a copy of the `.md` and `design-tokens.json`. The HTML fetches the
  paired markdown at runtime (`?v=<BUILD_ID>`, `cache: no-store`) and renders
  client-side. Edit the copied `.md`, refresh the browser: live authoring
  loop. **Requires `serve.py`** — `file://` blocks fetch by design.
- **`--inline`** — one self-contained HTML with the markdown embedded on
  `window.__DOC_MD__` and tokens on `window.__DOC_TOKENS__`. Opens over
  `file://`. Network still needed for the pinned CDN libraries.
- **`--tokens FILE`** — swap the brandpack (see schema in
  `resources/rich-blocks.md`). Default: `assets/design-tokens.json`.

### `serve.py [DIR] [--port 8642] [--open]`

Serves DIR (default `tmp/richdocs`) on `127.0.0.1` with `Cache-Control:
no-store` on every response, so a browser refresh always re-fetches fresh
markdown/JSON. Busy port and missing dir fail loudly. `--open` launches the
browser. This is the answer to "reliably serve localhost HTML that pulls
Tailwind / Google Fonts / Cytoscape / deck.gl / plotly / mermaid" — third-party
CDNs load fine over `http://localhost`; only `file://` breaks fetch.

### `stencil.py packs | list | search | extract`

Vendored draw.io stencil library (`assets/stencils.json.zip`, thousands of
provider icons keyed `"<pack>/<name>"`, packs: `mxgraph.aws4`, `mxgraph.gcp2`,
`mxgraph.azure`, `mxgraph.mscae*`, `mxgraph.kubernetes*`).

```bash
stencil.py packs                       # pack prefixes + counts
stencil.py list --pack mxgraph.gcp2 --limit 40
stencil.py search "cloud run"
stencil.py extract "mxgraph.aws4/lambda" --color '#ED7100' --size 64 --out lambda.svg
```

Every stencil paints `currentColor`; `--color` tints by string-replace (works
in every renderer). Omit `--color` and the SVG inherits its parent's
`color` — ideal for inlining into themed HTML. Unknown ID exits 1 with
close-match suggestions.

## Fenced rich blocks (in the rendered markdown)

Beyond standard markdown + ` ```mermaid `, the HTML companion renders:

````markdown
```cytoscape
{ "elements": [ {"data": {"id": "a", "label": "API"}},
                {"data": {"id": "b", "label": "DB"}},
                {"data": {"source": "a", "target": "b"}} ],
  "height": 420 }
```

```plotly
{ "data": "cost_series.json" }
```
````

- Payload is either **inline JSON** or `{ "data": "relative/path.json" }` —
  the external file is fetched with cache-busting: the data-driven mode.
  Generate the `.json` from real sources (terraform plan, dbt manifest,
  pricing API) and the doc stays current on refresh.
- Canvas colours come from `design-tokens.json` (`canvas.cytoscape.*`,
  `canvas.plotly.*`), never CSS — canvases can't read CSS variables. Theme
  toggle re-feeds the palette and re-renders.
- Full block contract + token schema: `resources/rich-blocks.md`.

## Cross-cutting conventions

- **Escalators, not stairs**: a missing hard requirement (input file, busy
  port, unknown stencil id) crashes loudly with the reason. No silent skips.
- **Determinism**: same input → same output modulo `{{BUILD_ID}}`. Cache-bust
  every runtime fetch with `?v=<BUILD_ID>`.
- **Inline-embed safety**: anything embedded in a `<script>` escapes `</` as
  `<\/` — a stray `</script>` in doc content must not terminate the tag.
- **Brandpack is data, not code**: re-skin = edit `design-tokens.json` in the
  output dir and refresh. `FALLBACK_TOKENS` baked into the JS is a soft-fail
  net only, never the source of truth.
- Outputs land in project-local `tmp/richdocs/` (gitignored), never system
  `/tmp`.

## Resources

| File | Content |
|------|---------|
| `resources/serving.md` | Localhost serving contract, pinned CDN table (Tailwind, fonts, cytoscape, deck.gl, plotly, mermaid), `file://` vs `http://` failure modes |
| `resources/stencil-library.md` | Stencil pack schema, tint mechanism, registry pattern, composing full custom SVG diagrams from icons |
| `resources/rich-blocks.md` | Fenced block contract, design-tokens schema, two-palette (chrome vs canvas) theming |
| `resources/discovery-docs.md` | Recipes for upgrading each discovery-doc archetype (diagram-driven, table-driven, prose review) to rich HTML |
| `scripts/serve.py` | No-store localhost server |
| `scripts/stencil.py` | Stencil library query/extract CLI |
| `scripts/md2html.py` | Paired markdown → rich HTML generator |
| `assets/stencils.json.zip` | Vendored draw.io icon library (see `assets/NOTICE`) |
| `assets/design-tokens.json` | Default neutral brandpack |

Deep prior art (linked, not duplicated): the sibling `cli` skill's
`resources/static-spa-viewer.md` (full SPA viewer: routing, sidebar,
`--archive`) and `resources/svg-diagrams.md` (layout + drift-gated committed
diagrams). `richdocs` packs those patterns as runnable scripts; the `cli`
skill teaches you to build them into your own CLI.
