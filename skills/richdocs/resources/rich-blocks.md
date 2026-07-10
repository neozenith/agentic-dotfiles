# Fenced Rich Blocks & the Design-Tokens Brandpack

The contract for interactive blocks inside a markdown doc rendered by
`md2html.py`, and the token file that brands them. Pattern lineage: the
data-driven cytoscape viewer with injected brandpack (adaf `sdag`), made
generic.

## Block contract

Standard markdown renders as usual (marked, pinned). Three fence languages
get special treatment; each block's body is either **inline JSON** or a
**data pointer** `{ "data": "relative/path.json" }` fetched at render time
with `cache: no-store` + `?v=<BUILD_ID>`.

### ` ```mermaid `

Rendered by mermaid 11.x. Theme follows the document theme (`default` /
`dark`), re-initialised and re-rendered on every theme flip. Complexity and
contrast rules from the `mermaidjs_diagrams` skill still apply to the source.

### ` ```cytoscape `

```json
{
  "elements": [
    { "data": { "id": "api", "label": "API", "parent": "vpc" } },
    { "data": { "id": "db",  "label": "DB" } },
    { "data": { "source": "api", "target": "db", "label": "reads" } }
  ],
  "layout": { "name": "dagre", "rankDir": "LR" },
  "height": 420
}
```

- `elements` follows Cytoscape's element JSON (compound nodes via `parent`).
- `layout` optional; default `dagre` left-to-right. `height` optional px.
- Stylesheet is built from `canvas.cytoscape.<theme>` tokens — never author
  per-node colours unless they encode *data* (status, category), in which
  case put them in `data.colour` and they survive theme flips unchanged.
- Node tap → detail is intentionally not in the packaged viewer; when a doc
  needs routing/detail panels, graduate to the full SPA pattern
  (`.claude/skills/cli/resources/static-spa-viewer.md`).

### ` ```plotly `

```json
{ "data": [ { "type": "scatter", "x": [1,2,3], "y": [4,1,7] } ],
  "layout": { "title": "Cost by month" } }
```

Rendered with `Plotly.react`. The theme's `canvas.plotly.<theme>` tokens set
`paper_bgcolor`, `plot_bgcolor`, font colour, gridlines, and `colorway`
(series palette) — author traces colour-free unless the colour is data.
Prefer `type: "scatter"` over `scattergl` when points must be clickable or
e2e-addressable.

### The data pointer (data-driven mode)

```json
{ "data": "graphs/full_graph.json", "height": 520 }
```

The heart of the pattern: generate the JSON from a real source (terraform
plan, dbt manifest, AWS pricing API) with a script, and the *document* never
changes — refresh re-fetches fresh data. Paths are relative to the served
directory. This only works over `http://` (see `serving.md`); in `--inline`
mode a data pointer that can't be resolved renders a loud error block, not a
blank space.

## The brandpack: `design-tokens.json`

One JSON file, copied verbatim into the output dir, fetched at runtime.
Re-brand = edit the copy, refresh. Schema (all keys required):

```json
{
  "fonts": { "body": "…", "mono": "…" },
  "themes": {
    "light": { "bg": "…", "fg": "…", "muted": "…", "accent": "…", "surface": "…", "border": "…" },
    "dark":  { "…same keys…" }
  },
  "canvas": {
    "cytoscape": { "light": { "nodeFill": "…", "nodeLabel": "…", "edge": "…",
                              "compoundBg": "…", "compoundBorder": "…" },
                   "dark": { "…" } },
    "plotly":    { "light": { "paper": "…", "plot": "…", "font": "…", "grid": "…",
                              "series": ["…", "…", "…", "…", "…"] },
                   "dark": { "…" } }
  },
  "categoryColours": { "Compute": "#ED7100", "Storage": "#7AA116", "…": "…" }
}
```

### Why two palettes (the load-bearing design fact)

**Canvas renderers cannot read CSS custom properties.** So theming is split:

- `themes.*` → CSS variables under `:root[data-theme=…]` — styles the HTML
  chrome (text, tables, code, header).
- `canvas.*` → a parallel JS palette fed directly into Cytoscape stylesheets
  and Plotly layouts.

A theme flip must therefore do **two** things: restamp `data-theme` (chrome
re-themes instantly via CSS) *and* re-feed the canvas palette + re-render
every fenced block. The generated JS does both; if you fork the template,
keep both or dark mode will half-apply — the classic symptom is a dark page
with blinding white charts.

### Rules that keep brandpacks sane

- **Data-encoding colours are not branded.** Status red/amber/green and
  `categoryColours` stay constant across brands and themes; only chrome and
  accent re-skin. A rebrand must never change what the colours *mean*.
- **WCAG AA (≥4.5:1)** for all fg/bg pairs in both themes. The default pack
  is pre-checked; verify any replacement.
- **`FALLBACK_TOKENS`** baked into the generated JS is a fetch-failure safety
  net that console.errors when used. It is not a place to customise.
- **Pre-paint theme bootstrap**: an inline `<head>` script resolves
  `localStorage` → `prefers-color-scheme` → light and stamps `data-theme`
  before first paint. Moving it to the external JS reintroduces the
  light-flash (FOUC).
