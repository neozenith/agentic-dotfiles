# mermaidjs_diagrams

Render and maintain Mermaid.JS diagrams with **visual-clarity enforcement**.

## Features

- **Render** `.md` files containing ```` ```mermaid ```` fences to PNG/SVG
  (dark+transparent and default+white variants by default).
- **Complexity lint** — ruff-style findings on node count, visual-complexity
  score, and subgraph depth. Cognitive-load-calibrated thresholds (Huang
  2020, 50-node cap). Uses Mermaid's canonical parser.
- **Contrast audit (required, not optional)** — every diagram with custom
  colors MUST derive its palette from `resources/color_theming.md` and pass
  `scripts/mermaid_contrast.ts` (WCAG 2.x + APCA). Ad-hoc pair checker also
  ships for sampling (hex, rgb, oklch, named).
- **Layout engines** — dagre / elk / tidy-tree / cose-bilkent, selectable per
  diagram via YAML frontmatter. `look: classic | handDrawn | neo`.
- **Icon packs** — Iconify (logos, mdi, cloud, saas) for `architecture-beta`;
  Font Awesome for flowcharts.

## How it fits together

```mermaid
flowchart LR
    subgraph author["Authoring"]
        fence["mermaid fence<br/>in .md"]:::ingressPrimary
        mmd[".mmd file"]:::ingressPrimary
    end

    subgraph gates["Mandatory Quality Gates"]
        palette["Palette<br/>from reference"]:::computePrimary
        complexity["mermaid_complexity.ts<br/>nodes / VCS / depth"]:::computePrimary
        contrast["mermaid_contrast.ts<br/>WCAG AA fill+text+stroke"]:::computePrimary
    end

    subgraph optional["Optional Tooling"]
        layout["Layout engine<br/>dagre / elk / tidy-tree"]:::dataSecondary
        icons["Iconify packs<br/>logos / mdi / cloud"]:::dataSecondary
        render["render_mermaid.sh<br/>PNG / SVG variants"]:::dataPrimary
    end

    subgraph refs["Reference Docs"]
        rColor["color_theming.md"]:::infraSecondary
        rLayout["layout_algorithms.md"]:::infraSecondary
        rOrg["diagram_organization.md"]:::infraSecondary
    end

    fence --> palette
    mmd --> palette
    palette --> complexity
    palette --> contrast
    complexity -- pass --> render
    contrast -- pass --> render

    layout -. configures .-> fence
    icons -. enriches .-> fence

    rColor -. informs .-> palette
    rLayout -. informs .-> layout
    rOrg -. structures .-> fence

    classDef ingressPrimary    fill:#2563eb,stroke:#0f172a,color:#fff,stroke-width:2px
    classDef computePrimary    fill:#7c3aed,stroke:#0f172a,color:#fff,stroke-width:2px
    classDef dataPrimary       fill:#0f766e,stroke:#0f172a,color:#fff,stroke-width:2px
    classDef dataSecondary     fill:#99f6e4,stroke:#0f766e,color:#1e293b,stroke-width:1px
    classDef infraSecondary    fill:#cbd5e1,stroke:#334155,color:#1e293b,stroke-width:1px

    classDef sgBlue   fill:#dbeafe,stroke:#1e40af,color:#1e293b
    classDef sgViolet fill:#ede9fe,stroke:#5b21b6,color:#1e293b
    classDef sgTeal   fill:#ccfbf1,stroke:#0f766e,color:#1e293b
    classDef sgSlate  fill:#f1f5f9,stroke:#334155,color:#334155

    class author sgBlue
    class gates sgViolet
    class optional sgTeal
    class refs sgSlate
```

*Mermaid source flows left-to-right through two mandatory gates — structural
complexity and color contrast — before rendering. Reference docs (dotted)
supply the rules each stage enforces.*

## Quick start

```bash
bash .claude/skills/mermaidjs_diagrams/scripts/render_mermaid.sh path/to/doc.md
make -C .claude/skills/mermaidjs_diagrams/scripts cli-demo
```

See [`SKILL.md`](SKILL.md) for usage, [`resources/`](resources/) for deep dives,
and [`scripts/CLAUDE.md`](scripts/CLAUDE.md) for the maintenance guide.
