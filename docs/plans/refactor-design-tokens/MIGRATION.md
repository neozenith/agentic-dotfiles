# Migration: from the prototype to both skills

Topics 1–4 are closed. What remains is **build**, sequenced below. Surveyed 2026-09-24; paths are
relative to `skills/`.

> **Parked 2026-09-28, mid-way through a `concise-decisions` loop** whose goal is a migration with
> zero open questions. DT-TOOL-1 is decided (DECISIONS.md, with its cascade). **One question is left:
> DT-DTCG-1**, below. Resume by asking it; everything else is settled.

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
| **M0** | Where the curation tool lives: **`skills/design-profiles/`** | — | DT-TOOL-1 |
| M1 | Surface expansion into the IR (CURATION stage 6) | M0 | DT-BUILD-1 |
| M2 | Promote the prototype to the real tool and the shared store | M0 | DT-LOC-1, DT-PROV-1 |
| M3 | Port the four built-in brands to IRs, every value stated | M2 | DT-BUILD-1, DT-PROV-1 |
| M4 | `richdocs` reads the DTCG | M1, M3 | DT-PIPE-1, DT-ROLES-1 |
| M5 | `mermaidjs-diagrams` reads the DTCG; re-vendor into `richdocs` | M1, M2 | DT-LOC-1, ADR-007 |
| M6 | Retire the legacy keys and the projection | M4, M5 | DT-ROLES-1, DT-CAT-1 |

### M0 — decided: `skills/design-profiles/` (DT-TOOL-1)

An independent skill is the only producer. `richdocs` and `mermaidjs-diagrams` look for a profile in
`.design-profiles/` first and use it by preference, falling back to what they do today and saying
which they used. See DT-TOOL-1's cascade for cutover, shipped copies, DT-ROLES-1's scope,
`themecheck.py`, `slides`/`cli` (out of scope) and the built-in brands.

### Pragmatic defaults applied in the loop (reversible; reopen with evidence)

- **Status levels:** richdocs' `serious` and `critical` both read `color.text.danger`; the glyph
  distinguishes them, since status is never shown by colour alone.
- **`mermaid_contrast.ts`:** the new flag is `--design-profile <name>`; `--profile` keeps meaning the
  host (GitHub, MkDocs).
- **Fonts:** a profile carries `font.family.{display,body,mono}` as DTCG `fontFamily` tokens plus an
  optional web-font stylesheet URL (a typeface is a brand value, richdocs ADR-018).
- **`.default-profile`:** a one-line text file inside `.design-profiles/` naming the default
  profile, resolved through the same cascade (DT-LOC-1's derived rule).

### Open — DT-DTCG-1: the file layout a consumer reads

The only remaining ambiguity; it changes a stored data shape, so it goes to the maintainer.
DT-BUILD-1 names one `design-tokens.json` as "the only file skills read", but the prototype writes
the DTCG 2025.10 resolver layout (`dtcg/{light,dark}.tokens.json` + `profile.resolver.json`).
Drafted options, same read in each (`color.text` light for osakanights → `#010101`):

| Option | Files a consumer reads | Outside DTCG tools | Matches DT-BUILD-1 | Main cost |
|---|---|---|---|---|
| A: one `design-tokens.json` with `light`/`dark` groups | 1 | need the mode convention | yes | no standard layout |
| B: the 2025.10 resolver set only | 3 | yes | no | a resolver in 3 languages; 3 copies per richdocs doc |
| **C (recommended):** both, built from the same IR; consumers read the single file | 1 | yes (`dtcg/`) | yes | a second serialisation + an agreement test |

Useful spike if unsure: does Style Dictionary read the 2025.10 resolver today? If nothing does, C's
second form buys nothing and A wins.

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
