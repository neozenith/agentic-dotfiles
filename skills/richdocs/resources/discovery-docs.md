# Upgrading Discovery Docs to Rich HTML

Recipes for turning this repo's root `*.md` discovery documents (and docs
like them) into high-fidelity HTML companions. The markdown stays canonical
and committed; the HTML companion is generated into `tmp/richdocs/`, served
locally, and regenerated at will.

## The three archetypes (from this repo's root docs)

| Archetype | Examples here | Dominant elements | Rich-HTML win |
|-----------|---------------|-------------------|---------------|
| Diagram-driven architecture | `ARCHITECTURE.md`, `TARGET_ARCHITECTURE.md`, `PLATFORM_SOLUTIONS.md` | 4-5 mermaid flowcharts with classDef palettes | interactive cytoscape twin of the key diagram; provider icons |
| Table-driven analysis | `COST_MODEL.md`, `IAP_ON_AWS.md`, `PRIOR_ART.md` | 16-35 table rows, cited rates | plotly charts fed by data files; sortable-feel wide-table scroll |
| Prose review | `REVIEW.md` | narrative verdicts, blockquotes | typography + theme only — resist adding charts to prose |

## Recipe: diagram-driven docs

1. Render as-is first: `md2html.py TARGET_ARCHITECTURE.md` + `serve.py`.
   Mermaid blocks already upgrade to theme-aware interactive renders — often
   this alone is the deliverable.
2. For the **one** load-bearing diagram, add a cytoscape twin as a fenced
   block *below* the mermaid original (don't replace it — the mermaid stays
   readable on GitHub). Compound nodes map to mermaid subgraphs; keep the
   node count within the complexity budget the vendored gate enforces
   (`vendor/mermaidjs_diagrams/scripts/mermaid_complexity.ts`).
3. Where the doc names concrete services, drop tinted stencils into prose or
   tables: `stencil.py extract "mxgraph.aws4/lambda" --color '#ED7100'`,
   reference the SVG with a normal markdown image. Icons render on GitHub
   *and* in the companion — a pure win.

## Recipe: table-driven docs

1. Keep the tables (they're the citable record). Add a fenced `plotly` block
   per table that benefits from shape — cost curves, comparison bars.
2. Prefer the **data pointer** form: emit `tmp/richdocs/data/<name>.json`
   from the real source (pricing API script, terraform plan) and reference
   `{ "data": "data/<name>.json" }`. The doc then updates by re-running the
   data script, not by editing prose. Never hand-type numbers into both a
   table and a chart — one of them will rot.
3. GitHub degradation is graceful *by construction*: a fenced `plotly` block
   renders on GitHub as a JSON code block — visible, inspectable, obviously
   "the chart's data" — not broken markup.

## Recipe: prose reviews

Render with `md2html.py --inline` and stop. The value is typography, theme,
and a single shareable file for review circulation. Adding canvases to a
verdict document buries the verdicts.

## Distribution modes

| Need | Mode |
|------|------|
| Author/iterate locally | multi-file + `serve.py` (edit copied `.md`, refresh) |
| Share with a colleague / attach to PR | `--inline` single file |
| Publish for the team | `--inline` output to an Artifact or static host |
| Keep in repo | don't — companions are generated; commit the `.md` and any data scripts, gitignore `tmp/richdocs/` |

## Fidelity ladder (stop at the lowest rung that answers the question)

1. Plain markdown (GitHub renders it) —
2. → `md2html.py` companion (theme, typography, live mermaid) —
3. → + fenced cytoscape/plotly blocks (interaction, data-driven) —
4. → full SPA viewer with routing/sidebar/views — a real standalone
   sub-project with its own build, not a companion; out of richdocs' scope.

Jumping to rung 4 for a document that needed rung 2 is how viewers become
unmaintained apps. The companion's job is *high-fidelity information
processing*, not product UI.
