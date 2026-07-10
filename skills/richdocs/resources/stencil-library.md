# The Vendored Stencil Library

An on-hand library of rich provider SVG icons (AWS, GCP, Azure, Kubernetes)
extracted from draw.io's stencil packs, vendored as one compressed JSON, and
tinted on demand into custom diagrams. Companion to `scripts/stencil.py`.

## What's in the pack

`assets/stencils.json.zip` — a single-entry ZIP (entry `stencils.json`,
~6.3 MB uncompressed, ~3.4 MB in the repo). One JSON object keyed by draw.io
stencil id `"<pack>/<name>"`:

```json
"mxgraph.aws4/lambda": {
  "w": 44.0, "h": 44.0,
  "svg": "<path d=\"M44 11 …\" fill=\"currentColor\" stroke=\"none\"/>",
  "stencil_b64": "nZjRd…"
}
```

| Field | Meaning |
|-------|---------|
| `w`, `h` | native shape bounds; the fragment's coordinate space is `0..w / 0..h` |
| `svg` | inner SVG fragment — **every paint not explicitly set is `currentColor`** |
| `stencil_b64` | draw.io `shape=stencil(…)` payload (urlencode → raw-deflate → base64 of the `<shape>` XML) — embed in an mxCell style to make an SVG re-openable/editable in draw.io |

Packs vendored in full: `mxgraph.aws4`, `mxgraph.gcp2`, `mxgraph.azure`,
`mxgraph.mscae*`, `mxgraph.kubernetes*`. Provenance and trademark notes:
`assets/NOTICE` (shapes are Apache-2.0 from diagrams.net; the product logos
remain the providers' trademarks — fine for internal architecture docs).

## The tint mechanism (the whole trick)

`currentColor` is the single theming placeholder. Two ways to use it:

1. **Inherit** — extract without `--color`; the standalone SVG paints
   `currentColor`, so inlined into HTML it takes the parent's CSS `color`.
   This is what makes icons theme-flip for free inside `md2html.py` output.
2. **Bake** — `--color '#ED7100'` string-replaces `currentColor` before
   writing. Use for committed artifacts and renderers with uneven
   `currentColor` support (some raster paths). String-replace is deliberately
   chosen over CSS: it works in *every* renderer.

```bash
uv run --no-project .claude/skills/richdocs/scripts/stencil.py \
  extract "mxgraph.aws4/lambda" --color '#ED7100' --size 64 --out lambda.svg
```

## Composing a custom diagram from stencils

The pipeline (from the proven `tfs diagrams` implementation):

```
data → Graph(nodes, edges) → deterministic layout → SVG compositor → (cairosvg PNG)
```

1. **Registry is the single editable seam.** Map your domain types to
   `(stencil_id, category)` and categories to accent colours. Adding a node
   type or rebranding touches only these dicts:

   ```python
   STENCIL_BY_TYPE = {
       "aws_lambda_function": ("mxgraph.aws4/lambda", "Compute"),
       "aws_s3_bucket":       ("mxgraph.aws4/simple_storage_service", "Storage"),
   }
   CATEGORY_COLOR = {"Compute": "#ED7100", "Storage": "#7AA116"}
   ```

   The default `assets/design-tokens.json` ships the same palette under
   `categoryColours` so diagrams and HTML companions stay colour-consistent.

2. **Deterministic layout, no graphviz.** Cluster by category left-to-right;
   grid nodes top-down, wrap past ~6 rows; sort every collection. Determinism
   is what makes a `--check` drift gate possible (re-render and byte-diff in
   CI). Never embed timestamps in the SVG.

3. **Inline each icon, don't `<use>`.** Scale to icon size with
   `scale = ICON / max(w, h)`, tint, wrap:

   ```python
   frag = stencil["svg"].replace("currentColor", CATEGORY_COLOR[cat])
   parts.append(f'<g transform="translate({x},{y}) scale({s})">{frag}</g>')
   ```

   Icon-less types fall back to a plain coloured chip — visible, never
   silently dropped.

4. **Optional draw.io round-trip.** Set the root `<svg content="…">`
   attribute to an `<mxfile>` model whose node styles carry
   `shape=stencil({stencil_b64})`. The one file is then both the rendered
   image *and* re-openable in draw.io for hand-editing. Escape with
   `xml.sax.saxutils.quoteattr`.

5. **PNG only when required**: `cairosvg` as a lazy library import; missing
   libcairo crashes loudly at call time (PNG was the requirement — no silent
   SVG-only "success").

Full treatment — drift gates, README marker-upsert, font pitfalls — lives in
the `cli` skill: `.claude/skills/cli/resources/svg-diagrams.md`. Read it
before building a committed, CI-gated diagram artifact.

## Refreshing the pack

The pack is regenerated (rarely) from draw.io's `stencils.min.js` by the
extractor in the source project
(`~/play/tools/tools-tfs/scripts/extract_stencils.py`): base64 → raw-DEFLATE
(`wbits=-15`) → urldecoded stencil XML, transcribed verb-by-verb to SVG with
unset paints promoted to `currentColor`. Re-vendor by copying the rebuilt
zip + NOTICE here; `stencil.py` has no other coupling to the source repo.

## Pitfalls

- **IDs contain spaces** (`"mxgraph.gcp2/Cloud Run"`) — always quote the ID.
- **Some stencils are image-only** → empty `svg` fragment; `extract` warns
  and the compose pattern falls back to a chip.
- **Don't unzip into the repo** — the loader reads the zip in memory
  (`io.BytesIO`); a stray 6 MB `stencils.json` sitting next to it is bloat.
- **Tint before raster** — never rely on `currentColor` surviving a PNG
  pipeline.
