# Learned: mermaid label boxes clip against a webfont theme

- **Date:** 2026-07-17
- **Case:** a handoff doc rendered with `--theme v2ai` showed every flowchart label
  cut mid-word: `Cloud Run: dev` → `Cloud Run: de`, `aurizon-buildathon-dev` →
  `aurizon-buildathon-de`, subgraph title `Aurizon Entra tenant` → `Aurizon Entra
  tenan`. The same markdown rendered with `--tokens` (no theme, so no webfont) was
  perfect, which is what made the theme the suspect.

## Root cause

Mermaid measures each label, sizes a `<foreignObject>` to that measurement, and
paints the text inside it. A `<foreignObject>` establishes a new SVG viewport and
**clips its content by default**. The measurement runs a few percent short against a
brand webfont, so the tail of the label is clipped away.

Measured on the real DOM, which is the only way this was settled:

```
shortfall=  8  foW=169  inkW=177  shapeW=229   "App registration / aurizon-buildathon-dev"
shortfall=  5  foW=105  inkW=110  shapeW=165   "Cloud Run: dev"
```

`foW` is the box mermaid sized, `inkW` is what the text actually paints, `shapeW` is
the node shape drawn around it. **The node has ~50px of spare room**: the text is not
too big for the node, only for the invisible box mermaid wrapped around it. So the
fix does not need the measurement to be correct, it needs the box to stop clipping.

## The fix

`viewer.css`:

```css
.rd-mermaid foreignObject { overflow: visible; }
```

Plus, in `viewer.js`, `mermaid.initialize({ fontFamily: TOKENS.fonts.body })` so
mermaid measures the face it actually renders in (this narrows the shortfall and
makes diagrams on-brand, but does **not** close the gap on its own).

## Three fixes that look right and are not

Each was implemented, rendered and measured before being rejected. Do not re-try them.

| Attempt | Why it fails |
|---|---|
| `document.fonts.ready` before rendering | Sound reasoning (a `display=swap` face could swap in after measurement) but the shortfall is identical with the barrier in place. Kept only as cheap correctness, it is not the fix. |
| `mermaid.initialize({ fontFamily })` alone | Makes mermaid measure and render in the same face. The shortfall stays at 8px, so mermaid's measurement is short even in the correct font. |
| `flowchart: { wrappingWidth: 340 }` | The label div's `max-width` did move from 200px to 340px, confirmed in the DOM, and the clip did not move a pixel. `max-width` was never the clipper. It also changes where every diagram wraps, so it is a layout regression for no gain. |

## The transferable lesson

**Measure the DOM before theorising.** Three plausible font-race hypotheses each
survived a code reading and died against one `getBoundingClientRect` comparison. The
probe that settled it (`foW` vs `inkW` vs `shapeW`) took minutes and would have
saved all three attempts had it come first. When a rendering bug is visual, the
browser holds the answer, and reasoning about CSS cascade from the source does not.

## Author-side corollary

`overflow: visible` rescues a label that overshoots its box by a few percent, because
the node shape has room. It cannot rescue a **cluster/subgraph title** that is long
enough to wrap, because that one is clipped vertically and the cluster header has no
spare height. Keep subgraph titles short (`GCP project`, not `GCP project
v2-aurizon-buildathon`).
