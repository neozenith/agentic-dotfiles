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
`dark`), re-initialised and re-rendered on every theme flip. The source must
pass the vendored gates (`vendor/mermaidjs_diagrams/scripts/
mermaid_complexity.ts` + `mermaid_contrast.ts`) — see the "Mermaid gate"
section in `SKILL.md`.

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
  needs routing/detail panels, it has outgrown the companion — build it as a
  standalone SPA sub-project (rung 4 of the fidelity ladder in
  `discovery-docs.md`).

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

`height` sizes the canvas (default 420), same as the other blocks. Set it on the
payload, **not** in `layout` — the container is what Plotly's responsive mode
measures.

### ` ```deckgl `

3D and geographic scenes (deck.gl, lazy-loaded — it is the heaviest CDN lib, so
a doc that never uses it never pays for it).

```json
{ "view": "orbit", "space": "oklch", "height": 520,
  "gamut": [0.65], "targetChroma": 0.19,
  "layers": [ { "type": "PointCloudLayer", "pointSize": 11,
                "data": [ { "hex": "#7180fe", "label": "series 1" } ] } ] }
```

| Key | Meaning |
|-----|---------|
| `view` | `"orbit"` (3D, default) or `"map"` (geographic; positions are `[lng, lat]`) |
| `space` | orbit only — `"oklch"` (default), `"oklab"`, `"rgb"`. The projection applied to `hex` data |
| `layers[].type` | **any** deck.gl layer name, looked up on the global (`PointCloudLayer`, `ArcLayer`, `GeoJsonLayer`, …) |
| `gamut` | orbit only — draw the sRGB boundary ring at each listed lightness |
| `targetChroma` | orbit only — draw the *requested* chroma as a circle, and spoke every swatch that could not reach it |
| `basemap` | map only — `true` (OSM) or a raster tile URL template; a deck `TileLayer` under the scene |
| `basemapStyle` | map only — a **vector** GL style URL (e.g. CartoDB dark-matter); MapLibre owns the map, deck rides as a `MapboxOverlay`. Preferred over `basemap` (robust tiles) |
| `height` | canvas height in px (default 460) |

**`type` is looked up on deck's global, so every deck.gl layer works with no code
change here.** The block is open by construction; only the colour-space sugar
below is specific.

**The sugar — a datum that carries `hex` needs neither a position nor a colour.**
Both are derived from the colour itself: the datum *is* its own coordinate. That
is what lets a palette be authored as a plain list of hex strings. Supply
`getPosition`/`getColor` explicitly to override.

**Lighting is OFF by default** (`material: false` on every layer). deck.gl's lit
layers shade marks as 3D solids, which *darkens the fill* — a swatch would render
muddier than its own hex, and in a colour-space scene the mark is a colour claim.
Flat/unlit is the only colour-correct default; put `material` on a layer spec to opt
into shaded geometry.

`map` view draws **no basemap by default** — the brand canvas *is* the basemap, so no
vendor token is required. Opt into real tiles with `basemap` (raster) or `basemapStyle`
(vector, via MapLibre); both are free and keyless. Supply `initialViewState` to frame it.
The vector path needs MapLibre GL loaded (`cdn.maplibre` + its CSS) before the block renders.

> **Orbit framing gotcha:** deck's `zoom` here is `log2(pixels per world unit)`,
> **not** a map zoom. Every space is normalised to a ~1-unit extent, so a scene
> needs `zoom ≈ 9`; framing it like a map (`zoom: 2`) renders a perfectly correct
> scene the size of a postage stamp. The defaults handle this — override with care.

Theming reads `canvas.deckgl.<theme>` (`background`, `ink`, `text`, `warn`) when
present, and otherwise derives them from tokens every brandpack already ships, so
**no brandpack change is needed to adopt the block**.

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
