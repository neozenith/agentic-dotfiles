# `-beta` Diagram Types and GitHub-Flavored Markdown

Mermaid ships new diagram types under a `-beta` suffix. Host renderers pin a
Mermaid version and lag upstream, so **a `-beta` fence that renders locally
will often fail to render on GitHub, GitLab, and other GFM hosts** — usually as
a raw code block or an error box, not as a diagram.

Treat local render success as *no evidence at all* about the host.

## The affected types

Everything carrying the suffix:

`architecture-beta`, `block-beta`, `packet-beta`, `radar-beta`, `sankey-beta`,
`treemap-beta`, `xychart-beta`

Non-beta types (`flowchart`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`,
`journey`, `mindmap`, `timeline`, `gitGraph`, `classDiagram`, `pie`,
`quadrantChart`, `gantt`, `requirementDiagram`) are broadly safe to inline as
live fences.

## The rule

| Fence uses | Ship as |
|---|---|
| A non-beta type | A live ` ```mermaid ` fence, inline. |
| A `-beta` type | A **rendered PNG or SVG**, embedded, with the `.mmd` source kept as a sibling file. |

Never inline a `-beta` fence in a document destined for a GFM host and hope.
Either render it, or choose a non-beta type that answers the same question.

## The sibling-source pattern

Keep the source next to the image so the diagram stays editable and reviewable.
The image is a build artifact that happens to be committed.

```
docs/
├── architecture.md               <- embeds the image
└── diagrams/
    ├── infrastructure.mmd        <- source of truth, edit this
    ├── infrastructure.png        <- rendered, committed
    └── data-volume.mmd
```

Embed with a caption and an explicit link back to the source, so a reader who
wants to change it knows where to go:

```markdown
![Infrastructure lens](diagrams/infrastructure.png)
*Infrastructure lens - deployed topology* | [source](diagrams/infrastructure.mmd)
```

## Rendering a `.mmd` file

`scripts/render_mermaid.sh` takes a **markdown** file and renders the fences
inside it. It does **not** accept a bare `.mmd` path — it rejects it with
`Output file must end with ".md"/".markdown", ".svg", ".png" or ".pdf"`.

For a standalone `.mmd`, call `mmdc` directly:

```bash
# Light variant for README and print
bunx -p @mermaid-js/mermaid-cli mmdc \
  -i docs/diagrams/infrastructure.mmd \
  -o docs/diagrams/infrastructure.png \
  -t default -b white

# Dark transparent variant for dark UIs and slides
bunx -p @mermaid-js/mermaid-cli mmdc \
  -i docs/diagrams/infrastructure.mmd \
  -o docs/diagrams/infrastructure.dark.png \
  -t dark -b transparent
```

Verify the output is a real image rather than a zero-byte artifact:

```bash
file docs/diagrams/infrastructure.png   # expect: PNG image data, WxH, ...
```

Prefer **SVG** where the host allows it — it scales, stays legible when zoomed,
and diffs less catastrophically than a binary PNG. Use PNG where the host
refuses inline SVG (some wikis) or where the image is destined for a slide deck.

## The gates still apply

Both analyzers read `.mmd` files directly, so a diagram does not escape the
density and contrast budgets by moving out of markdown:

```bash
bun run scripts/mermaid_complexity.ts docs/diagrams/
bun run scripts/mermaid_contrast.ts   docs/diagrams/
```

`mermaid_complexity.ts` counts nodes in `-beta` types correctly — a 16-node
`treemap-beta` trips `NodeCountExceedsAcceptable` under `--preset low` exactly
as a flowchart would. Moving a diagram to a `.mmd` sibling changes where it
lives, never what it must satisfy.

## Choosing a non-beta alternative

Rendering costs a build step and a committed binary. Before paying it, check
whether a stable type answers the same question:

| `-beta` type | Question it answers | Non-beta alternative |
|---|---|---|
| `architecture-beta` | What is deployed where? | `flowchart` with grouping subgraphs; Iconify icons where supported |
| `block-beta` | How do fixed regions align? | `flowchart` with subgraphs |
| `treemap-beta` | Where does mass concentrate? | A sorted table; `pie` for a handful of categories |
| `sankey-beta` | How much flows where? | `flowchart` with volume in edge labels |
| `xychart-beta` | How does a value trend? | A table, or a chart rendered outside Mermaid |
| `radar-beta` | How do items compare across axes? | A table |

The alternative is often *better* for a document that must survive in many
renderers. Reach for a `-beta` type when its specific visual encoding is the
point — not for novelty.
