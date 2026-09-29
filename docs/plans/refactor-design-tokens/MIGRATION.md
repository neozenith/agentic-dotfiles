# Migration: from the prototype to both skills

Topics 1–4 are closed. What remains is **build**, sequenced below. Surveyed 2026-09-24; paths are
relative to `skills/`.

> **Parked 2026-09-28, mid-way through a `concise-decisions` loop** whose goal is a migration with
> zero open questions. DT-TOOL-1 is decided (DECISIONS.md, with its cascade). **One question is left:
> DT-DTCG-1**, below, now narrowed to D vs A after an `explain`. Resume by re-asking it; everything
> else is settled. (Re-parked 2026-09-30.)

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
| M3 | Ship the four brands' exact-accent seeds as `design-profiles` examples | M2 | DT-TOOL-1 cascade |
| M4 | `richdocs` reads a profile first, else its built-ins | M1, M2, DT-DTCG-1 | DT-TOOL-1, DT-PIPE-1 |
| M5 | `mermaidjs-diagrams` reads a profile first, else its palettes; re-vendor into `richdocs` | M1, M2, DT-DTCG-1 | DT-TOOL-1, ADR-007 |
| M6 | Retire the prototype's projection | M4, M5 | DT-TOOL-1 cascade |

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

**History.** First asked 2026-09-28 with options A (one file, `light`/`dark` groups), B (the
2025.10 resolver set, three files) and C (both). The maintainer answered **`explain`**: *"is option A
(also impacts option C) the design-tokens.json a valid DTCG document still? I recall discussing
implementing our own custom schema which is part of the DTCG loader conventions just not out of the
box."* The explanation, researched and verified on 2026-09-28:

| Question | Answer |
|---|---|
| Is A valid DTCG? | **Yes, syntactically** (validates against `format.json` 2025.10). But the Format module defines no modes: a DTCG tool reads `light.color.text.default` and `dark.color.text.default` as two unrelated tokens, and aliases must be rewritten with the mode prefix. |
| The "custom schema via DTCG conventions" | **`$extensions`** under our reverse-domain key `dev.agentic-dotfiles.curation`. Tools *must* preserve extensions they don't understand. In a resolver document it may sit on sets and modifiers (and inside token trees), **not at the root**. |
| Does the standard need several files? | **No.** Resolver 2025.10 lets a set or context carry its tokens **inline**, so one file can be a complete multi-mode document. |

That made C's premise wrong and B dominated, leaving two options. Both are built from the real
osakanights profile and schema-validated, in [`scripts/dtcg1/`](scripts/dtcg1/)
(`uv run docs/plans/refactor-design-tokens/scripts/dtcg1/validate.py`):

| Option | File | Valid DTCG | A DTCG tool sees modes | Aliases | Reader |
|---|---|---|---|---|---|
| **D (recommended):** one resolver document, both modes inline under `modifiers.mode.contexts` | `D.design-tokens.json` | yes, `resolver.json` | yes | unchanged | about 10 lines to walk contexts |
| A: one format document, `light`/`dark` as plain groups | `A.design-tokens.json` | yes, `format.json` | no, two token sets | mode-prefixed | a dictionary lookup |

**Resume here:** re-ask the revised binary (D vs A) through `concise-decisions`; the second asking
was interrupted by the maintainer before an answer. Sources:
[Resolver Module 2025.10](https://www.designtokens.org/tr/drafts/resolver/),
[Format Module 2025.10](https://www.designtokens.org/tr/drafts/format/).

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

*Revised by DT-TOOL-1's cascade:* freshgreens, locomotif, osakanights and v2ai **stay in richdocs**
as its fallback, hand-authored and gated by `themecheck.py`. `design-profiles` ships their
exact-accent seeds as examples, so any of them can be curated into a profile by choice.

### M4 — `richdocs` reads a profile first, else its built-ins

- Add the profile lookup (its own copy of the M2 resolver) ahead of `theme_search_dirs`/
  `load_theme`/`resolve_brand`; with no profile, those run exactly as today, and the output says
  which was used.
- A profile is mapped on read onto richdocs' internal keys (`themes`/`canvas`/`status`), a rename
  with no design knowledge, so `viewer.js`, `viewer-cytoscape.js`, `viewer-deckgl.js` and
  `showcase.js` keep their current schema.
- `themecheck.py` keeps gating the built-in themes and never runs on a profile (DT-PIPE-1 rule 4).
- Tests pinned to the internal schema stay valid; new tests cover the profile-first lookup and the
  mapping. The survey's list, kept for reference:
  - `test_themecheck.py`: 12 tests (:26, :32, :41, :61, :72, :95, :105, :130, :141, :158, :169, :192)
  - `test_md2html.py`: 7 key-level tests (:118, :148, :185, :206, :299, :348, :362) plus the
    path-based ones at :171–200 and :319–337
  - `test_showcase.py`: the lineage fixture's file name only (:244)

### M5 — `mermaidjs-diagrams` reads the DTCG

- `render_mermaid.sh` passes the profile's `surface.mermaid` `themeVariables` as an mmdc config.
- `mermaid_contrast.ts --design-profile <name>` takes its grounds from the profile's surfaces;
  `--profile` (host: GitHub, MkDocs) and its hard-coded grounds remain the fallback.
- `color_theming.md` points at profiles; the prose palettes become examples.
- Re-vendor wholesale into `richdocs/vendor/` (ADR-007, ADR-020).

### M6 — retire the prototype's projection

- Delete `project_richdocs()`: M4's on-read mapping replaces it.
- A profile's categorical slots feed richdocs' `categoryColours` by cluster order (DT-CAT-1).
- Status: `serious` and `critical` both read `color.text.danger` (pragmatic default above).
