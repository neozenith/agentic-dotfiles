# Migration: from the prototype to both skills

Topics 1–4 are closed. What remains is **build**, sequenced below. One decision gates it (M0); every
other step follows from locked decisions. Surveyed 2026-09-24; paths are relative to `skills/`.

## Where things stand

| Consumer | Reads today | Lookup |
|---|---|---|
| `richdocs` | its own `design-tokens.json` schema: `themes.{light,dark}`, `canvas.{cytoscape,plotly,deckgl}`, `categoryColours`, `status`, `fonts`, `defaultTheme`, `waivers` | `md2html.py`: `theme_search_dirs` (:111), `load_theme` (:142), `resolve_brand` (:162); `tmp/richdocs/theme/` then 4 built-ins |
| `mermaidjs-diagrams` | **nothing**: palettes are prose (`resources/color_theming.md`, `color_palette_recipes.md`); `mermaid_contrast.ts` hard-codes host grounds (:53, :65); `render_mermaid.sh` passes mmdc's `-t`/`-b` only | none |
| `richdocs/vendor/mermaidjs-diagrams/` | byte-identical theming to upstream | none |

The prototype (`prototype/pipeline.py`) already produces seed → IR → DTCG plus a *projection* onto
richdocs' current schema. That projection is the stand-in this plan retires.

## Sequence

| # | Step | Depends on | Decided by |
|---|---|---|---|
| **M0** | **Decide where the curation tool lives** (DT-TOOL-1, below) | — | open |
| M1 | Surface expansion into the IR (CURATION stage 6) | M0 | DT-BUILD-1 |
| M2 | Promote the prototype to the real tool and the shared store | M0 | DT-LOC-1, DT-PROV-1 |
| M3 | Port the four built-in brands to IRs, every value stated | M2 | DT-BUILD-1, DT-PROV-1 |
| M4 | `richdocs` reads the DTCG | M1, M3 | DT-PIPE-1, DT-ROLES-1 |
| M5 | `mermaidjs-diagrams` reads the DTCG; re-vendor into `richdocs` | M1, M2 | DT-LOC-1, ADR-007 |
| M6 | Retire the legacy keys and the projection | M4, M5 | DT-ROLES-1, DT-CAT-1 |

### M0 — DT-TOOL-1: where does the curation tool live? (open)

Curation is **one act** for both skills (DT-LOC-1), but a skill may not depend on a sibling
(`skills/CLAUDE.md`). Candidates, to be put through `concise-decisions`:

1. **Its own skill** (e.g. `design-profiles`): curates into the shared store; both skills only read.
2. **Inside `richdocs`**, which already hosts the showcase and the live generator (ADR-022).
3. **A repo-level tool** outside `skills/`, since it writes a store no single skill owns.

### M1 — surface expansion into the IR

DT-BUILD-1 puts every surface in the IR; today `project_richdocs()` builds them at projection time.
Move each surface into curation as IR groups, so the DTCG carries them and no skill computes one:
`surface.plotly` (layout, `colorway`, ramps), `surface.cytoscape` (`{selector, style}` values),
`surface.mermaid` (`themeVariables`, alpha flattened per the low-stakes resolution),
`surface.deckgl` (RGBA), `surface.drawio` (container and stencil fill/stroke), `surface.css`
(chrome custom properties). The lineage Sankey's second stage then reads IR → DTCG directly.

### M2 — the real tool and the store

- Promote `curate_profile()`, `score_contrast()` and the build to the M0 location; drop the
  `hue-` prototype profiles.
- Store layout per DT-BUILD-1: `.design-profiles/<name>/{seed.json, ir.json, design-tokens.json}`.
- One resolver for the five-tier cascade (DT-LOC-1) and `.default-profile`; each skill carries its
  **own copy** of it (self-containment), never an import.

### M3 — the built-in brands

freshgreens, locomotif, osakanights and v2ai become IRs with **every value stated** (DT-PROV-1), so
porting is lossless and curation never rewrites them; each keeps its `theme.css` and `DESIGN.md`.
Their seeds (exact accents) stay available for regeneration by choice.

### M4 — `richdocs` reads the DTCG

- Replace `theme_search_dirs`/`load_theme`/`resolve_brand` with the M2 resolver copy.
- `viewer.js`, `viewer-cytoscape.js`, `viewer-deckgl.js` and `showcase.js` read DT-ROLES-1 roles and
  M1 surface groups instead of `themes`/`canvas`/`categoryColours`/`status`.
- `themecheck.py` shrinks: its gates moved to curation (DT-PIPE-1 rule 4, DT-CONTRAST-1), and
  ADR-016's `waivers` are redundant.
- Tests pinned to the old schema, to be rewritten against roles:
  - `test_themecheck.py`: 12 tests (:26, :32, :41, :61, :72, :95, :105, :130, :141, :158, :169, :192)
  - `test_md2html.py`: 7 key-level tests (:118, :148, :185, :206, :299, :348, :362) plus the
    path-based ones at :171–200 and :319–337
  - `test_showcase.py`: the lineage fixture's file name only (:244)

### M5 — `mermaidjs-diagrams` reads the DTCG

- `render_mermaid.sh` passes the profile's `surface.mermaid` `themeVariables` as an mmdc config.
- `mermaid_contrast.ts --profile <name>` takes its grounds from the profile's surfaces instead of the
  hard-coded host constants; the host profiles remain as fallbacks.
- `color_theming.md` points at profiles; the prose palettes become examples.
- Re-vendor wholesale into `richdocs/vendor/` (ADR-007, ADR-020).

### M6 — retire the legacy

- Delete `project_richdocs()` and the showcase's projection path.
- Named `categoryColours` go (DT-CAT-1: sequential slots only). The Cytoscape cluster tint reads
  `color.chart.categorical.<N>` by cluster order.
- `status` has four levels (`good`/`warning`/`serious`/`critical`) and DT-ROLES-1 three
  (`success`/`warning`/`danger`). The projection maps `serious` and `critical` to `danger`; confirm
  or add a role when M4 reaches `viewer-deckgl.js` and `showcase.js`.
