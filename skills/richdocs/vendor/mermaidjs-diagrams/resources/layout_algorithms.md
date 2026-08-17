# Layout Algorithms

How to pick and configure Mermaid's layout engine. Upstream references:

- <https://mermaid.js.org/intro/syntax-reference.html#how-to-select-a-layout-algorithm> — YAML frontmatter syntax, ELK tuning keys
- <https://mermaid.js.org/config/layouts.html> — catalogue of all registered layout engines
- <https://mermaid.js.org/config/tidy-tree.html> — tidy-tree engine (mindmaps)

## Which algorithm to use

Mermaid registers four layout engines out of the box:

| Engine | Strengths | Weaknesses | When to pick it |
|--------|-----------|-----------|-----------------|
| **dagre** *(default)* | Ships with every Mermaid build; fast; predictable for small graphs | Edge crossings multiply quickly past ~20 nodes; hierarchical-only; limited long-edge routing | Simple flowcharts, quick docs, anything that renders well without tuning |
| **elk** (Eclipse Layout Kernel) | Cleaner routing on dense graphs; orthogonal edges; configurable node placement; handles nested subgraphs gracefully | Not bundled in every Mermaid build; slightly slower; some looks render differently | Architecture overviews, stateful graphs with many crossings, nested subgraph-heavy diagrams |
| **tidy-tree** | Hierarchical, non-overlapping tree with auto-adjusted spacing | Only useful when the graph really is a tree | Mindmaps and strict parent-child hierarchies |
| **cose-bilkent** | Force-directed simulation ("Cose Bilkent layout for force-directed graphs") | Non-deterministic across runs; less predictable for docs | Organic / relationship graphs where no single node is "the root" |

`dagre` and `elk` are the two engines you will reach for ~95% of the time.
`tidy-tree` is effectively auto-selected for `mindmap` diagrams, and
`cose-bilkent` is a specialty pick for force-directed layouts.

### Diagram-type compatibility matrix

The `config.layout` key is only honored by a subset of diagram types. Where a
diagram type isn't listed, it uses its own built-in algorithm and silently
ignores `layout`.

| Diagram type | Honors `layout`? | Default engine | Notes |
|--------------|------------------|----------------|-------|
| `flowchart` | Yes | dagre | Full `dagre`/`elk` support |
| `stateDiagram-v2` | Yes | dagre | Full `dagre`/`elk` support |
| `mindmap` | Yes | tidy-tree | Tidy-tree is the natural fit |
| `classDiagram` | No | built-in | — |
| `sequenceDiagram` | No | built-in | Positions are time-ordered, not layout-driven |
| `erDiagram` | No | built-in | — |
| `gantt` | No | built-in | — |
| `architecture-beta` | No | built-in | Uses its own group/service placer |

**Takeaway.** If you are authoring a flowchart or state diagram, `config.layout`
is your lever. For anything else, style/theme tweaks are what's available.

## Configuration surface

Mermaid reads these top-level keys from the diagram's YAML frontmatter:

| Key | Values | Meaning |
|-----|--------|---------|
| `layout` | `dagre` *(default)*, `elk`, `tidy-tree`, `cose-bilkent` | Which engine runs the layout pass |
| `look` | `classic` *(default)*, `handDrawn`, `neo` | Rendering style for nodes and edges |
| `handDrawnSeed` | integer *(default `0` = random)* | Seed for the `handDrawn` sketch jitter — pin it for reproducible renders / visual-regression tests |

> **Spelling gotcha.** The Mermaid intro / marketing page uses the hyphenated
> form `hand-drawn`. The **actual config schema** enumerates `classic`,
> `handDrawn`, `neo` (camelCase). Only the camelCase form is honored by the
> renderer — `look: hand-drawn` silently falls back to `classic`.

Both are expressed as a leading YAML block **before** the diagram keyword:

```yaml
---
config:
  layout: elk
  look: handDrawn
  handDrawnSeed: 1
  theme: forest
---
flowchart LR
  A[Start] --> B{Choose Path}
  B -->|1| C[Path 1]
  B -->|2| D[Path 2]
```

The frontmatter travels with the diagram source, so the same `.mmd` or
```` ```mermaid ```` fence renders identically in `mmdc`, GitHub, GitLab, and
the Mermaid Live Editor — no per-renderer config needed.

### `look` values

| Look | Appearance | Best for |
|------|-----------|---------|
| `classic` | Crisp rectangles, clean arrows | Technical docs, architecture diagrams, print |
| `handDrawn` | Rough-sketch strokes (rough.js under the hood) | Brainstorming boards, design-phase diagrams, informal slides |
| `neo` | Modern aesthetic — drop shadows, gradient fills, consistent enhanced borders across all 50+ shape renderers. Added March 2026 (PR #7501, sponsored by MermaidChart). | Marketing, landing pages, polished presentations, anywhere "classic" feels too flat |

#### `neo` companion config

`look: neo` alone produces only a subtle border tweak. To get the full
gradient + shadow styling, pair it with these theme-level config keys (added
alongside the feature):

```yaml
---
config:
  look: neo
  useGradient: true
  gradientStart: "#ede9fe"
  gradientStop: "#a78bfa"
  dropShadow: true
---
```

| Key | Type | Meaning |
|-----|------|---------|
| `useGradient` | bool | Render node fills as a gradient rather than a flat color |
| `gradientStart` | CSS color | Start color of the gradient (typically a light tint) |
| `gradientStop` | CSS color | End color of the gradient (typically a saturated accent) |
| `dropShadow` | bool | Enable drop shadows on nodes for depth |

> **Caveat.** These keys are theme-aware. The stock `default` theme does not
> yet ship gradient-aware CSS selectors, so in some `mmdc` versions a
> `neo`-looked diagram with gradients enabled still renders close to `classic`.
> The visible effect is strongest when the diagram is rendered inside the
> Mermaid Live Editor or a browser Mermaid build that includes the neo
> themes. If you must have the full aesthetic in a CI pipeline, budget time
> to pin a newer `mmdc` version.

`look` is orthogonal to `layout` — any combination is valid
(`dagre`+`handDrawn`, `elk`+`classic`, `elk`+`neo`, etc.).

### Making `handDrawn` reproducible

The sketch style adds randomized jitter to every stroke. Without a seed, every
render differs, which breaks visual-regression tests and produces noisy diffs
when you re-render docs. Pin it with `handDrawnSeed`:

```yaml
---
config:
  look: handDrawn
  handDrawnSeed: 1
---
```

Any non-zero integer works — pick one per diagram and keep it stable.

## Dagre configuration

Dagre is the default; specifying it explicitly is only useful when you want to
pin against a future default change, or when you want `look: classic` documented
in the file:

```yaml
---
config:
  layout: dagre
  look: classic
  theme: default
---
flowchart LR
  A[Start] --> B{Choose Path}
  B -->|1| C[Path 1]
  B -->|2| D[Path 2]
```

Dagre has no `layout`-scoped tuning keys — direction is set via the diagram
keyword (`flowchart TB|LR|RL|BT`), and spacing comes from the top-level
`flowchart.nodeSpacing` / `flowchart.rankSpacing` keys.

## ELK configuration

ELK accepts a nested `elk:` block for engine-specific tuning:

```yaml
---
config:
  layout: elk
  elk:
    mergeEdges: true
    nodePlacementStrategy: LINEAR_SEGMENTS
---
flowchart LR
  A[Start] --> B{Choose Path}
  B -->|1| C[Path 1]
  B -->|2| D[Path 2]
```

### ELK tuning keys

| Key | Values | Effect |
|-----|--------|--------|
| `mergeEdges` | `true` / `false` *(default `false`)* | Bundle parallel edges between the same two nodes into a single visual edge. Reduces clutter in high-fan-in/fan-out graphs. |
| `nodePlacementStrategy` | `BRANDES_KOEPF` *(default)*, `LINEAR_SEGMENTS`, `NETWORK_SIMPLEX`, `SIMPLE` | Algorithm used to position nodes within each rank. See table below. |

#### `nodePlacementStrategy` trade-offs

| Strategy | Characteristics | Use when |
|----------|----------------|---------|
| `BRANDES_KOEPF` | Balances symmetry and compactness; default and usually the best starting point | General use |
| `LINEAR_SEGMENTS` | Keeps long chains straight; fewer bends on critical paths | Pipelines, request flows, anything read as a linear story |
| `NETWORK_SIMPLEX` | Global optimization for edge-length sum | Dense graphs where minimizing total edge length matters more than symmetry |
| `SIMPLE` | Fastest; minimal heuristics | Very large graphs where layout time is the bottleneck and you accept a less polished result |

## Caveats

- **ELK availability in `mmdc`.** The bundled `@mermaid-js/mermaid-cli` ships
  with ELK registered in recent versions (>= 10.9). If `mmdc` reports
  `Unknown layout elk`, upgrade the CLI (`npx -p @mermaid-js/mermaid-cli@latest
  mmdc ...`) or fall back to `layout: dagre`. The `render_mermaid.sh` wrapper
  uses `npx -p @mermaid-js/mermaid-cli`, which resolves the latest published
  version on first run.
- **`look` value must be camelCase.** The intro docs show `look: hand-drawn`
  but the schema enum is `handDrawn`. Hyphenated spelling silently falls back
  to `classic` — if the sketch look is missing, this is almost always the
  culprit.
- **`handDrawn` is non-deterministic without a seed.** Re-rendering the same
  diagram produces different pixel output each time. Set `handDrawnSeed: <int>`
  if you commit PNGs to version control or run visual regression tests.
- **ELK ignores direction hints from some diagram keywords.** `flowchart LR`
  still biases ELK toward left-to-right, but nested subgraph direction
  (`direction TB` inside a subgraph) may be overridden. Verify visually.
- **No `%%{init: ...}%%` directive equivalent.** Layout selection is YAML-only.
  The older `%%{init: {"flowchart": {"defaultRenderer": "elk"}} }%%` directive
  is superseded — prefer the `config.layout` frontmatter for forward
  compatibility.
- **Theme and look compose, not conflict.** `theme` (dark/default/forest/etc.)
  chooses colors; `look` chooses stroke style. Both can be set together.
- **Complexity analysis is layout-independent.** The
  [`mermaid_complexity.py`](../scripts/mermaid_complexity.py) script scores
  structural complexity (node count, edge count, VCS) regardless of which
  layout engine renders the diagram. Switching to ELK does not change the
  score — it changes how readable the rendered image is at that score.

## Picking defaults for this skill

A reasonable project-wide default for architecture and data-flow diagrams:

```yaml
---
config:
  layout: elk
  look: classic
  elk:
    mergeEdges: true
    nodePlacementStrategy: BRANDES_KOEPF
---
```

Reasons:

1. `elk` handles the dense overview diagrams this skill is usually asked to
   produce better than dagre.
2. `classic` look keeps rendered PNGs crisp for README embedding.
3. `mergeEdges: true` cuts visual clutter when a service has many upstream or
   downstream edges.
4. `BRANDES_KOEPF` is the upstream default and produces the most balanced
   result across a wide range of graph shapes.

For overview / simplified diagrams that are already well under the complexity
threshold, **dagre is fine** — keep configuration minimal and let the default
run.
