# Grounding dossier — design-token indirection (extraction only)

## 1. External reference: `/Users/jpeak/foss/diagram-design/`

Layout (token-relevant): `skills/diagram-design/{SKILL.md,references/,scripts/,assets/}`.
Token layers live entirely in **markdown**, not JSON/CSS. Relevant references:
`references/style-guide.md` (140 ln), `references/onboarding.md`, `references/profiles.md`.

`skills/diagram-design/references/style-guide.md:3` — "**The single source of truth for colors, typography, and tokens.** Every diagram draws from this — not from hex values inlined in other reference files. If you want to change the visual skin of Diagram Design, change this file."

`style-guide.md:11-15` — `## Tokens` → `### Semantic roles`: "Every token is referred to by **semantic role**, not by its hex value. Type references (`type-*.md`) and SKILL.md say `accent`, not `#f7591f`."

Role names, `style-guide.md:17-28` (table cols: Role | Purpose | Default (light) | Default (dark)):
`paper`, `paper-2`, `ink`, `muted`, `soft`, `rule`, `rule-solid`, `accent`, `accent-tint`, `link`.

`style-guide.md:30` — "> **Brand palette source:** this skin maps to a five-color brand palette — `jet-black #2d3142`, `silver #bfc0c0`, `white-smoke #f5f5f5`, `atomic-tangerine #eb6c36`, `blue-slate #4f5d75`. The `soft`, `rule`, and `link` tokens are derived …"

Further token tiers in the same file:
- `style-guide.md:34-36` `### Inversion rule (light → dark)` — "Any `rgba(28,25,23, X)` in light becomes `rgba(250,247,242, X)` in dark. Same opacities, RGB flipped."
- `style-guide.md:38-40` `### Series palette (multi-series chart types only)` — tokens `series-1`…`series-5`; ":50 — "**Don't backfill these tokens to non-chart types** …"
- `style-guide.md:52-54` `### Terminal skin (opt-in alternate)` — `terminal-page`, `terminal-paper`, `terminal-bar`, `terminal-border`, `terminal-ink`, `terminal-muted`, `terminal-soft`, `terminal-accent`, `terminal-accent-tint`; "It does not replace the default skin above and isn't affected by onboarding; it's a second, fixed skin you opt into per-diagram."
- `style-guide.md:74-81` `## Typography` roles: `title`, `node-name`, `sublabel`, `eyebrow`, `arrow-label`, `callout`.
- `style-guide.md:95-103` `## Stroke, radius, spacing`: `stroke-thin`, `stroke-default`, `stroke-strong`, `radius-sm`, `radius-md`, `radius-lg`, `grid`.
- `style-guide.md:111-119` `## Node type → treatment`: `focal`, `backend`, `store`, `external`, `input`, `optional`, `security` (each = fill/stroke combination of the semantic roles).

Stated override/selection rules, `style-guide.md:123-130` `## Customizing the skin` — "Four options: 1. **Run onboarding** … Drop a URL; the skill extracts the palette + fonts and rewrites this file. 2. **Edit by hand** … 3. **Brand handoff** — paste your existing design-token JSON into a new section here and map its tokens to the semantic roles above. 4. **Client profiles** — save and switch named skins, or bind one to a project, using [`profiles.md`](profiles.md)."

`style-guide.md:132-138` `### Constraints (don't break these)` — "**Contrast**: `ink` must hit WCAG AA on `paper` …"; "**One accent**: pick one color for `accent`. Two accents erases the focal signal."; "**No rainbow palette**: if your brand ships 8 colors, pick 3 (paper, ink, accent). The rest become `muted` variants."; "**Serif + sans + mono**: three families, not more."; "**Paper is warm-neutral, not pure white**".

`skills/diagram-design/SKILL.md:164` — "**The design system is skinnable.** All colors, typography, and tokens live in a single source of truth — `references/style-guide.md`. This file describes semantic roles (`paper`, `ink`, `muted`, `accent`, `link`, …)."
`SKILL.md:166` — "> When specs below or in type references mention 'ink', 'accent', 'muted', etc., look up the current hex value in `style-guide.md`."
`SKILL.md:21` — "Don't silently ship default-skinned diagrams into a branded project."
`SKILL.md:25-27` — first-run gate: "check the default tokens. If they're still the shipped defaults (paper `#f5f5f5`, ink `#2d3142`, accent `#eb6c36` atomic-tangerine), **pause and ask the user**" with options (a) URL, (b) installed skill, (c) local folder, (d) paste tokens, (e) default, (f) saved client profile.

Profiles layer, `references/profiles.md:3` — "Named profiles let one Diagram Design install serve several clients without repeatedly editing the installed `style-guide.md`. A profile is a complete style guide stored outside the install, so managed plugin updates cannot erase it."
`profiles.md:9-13` — "**Profile library:** `~/.diagram-design/profiles/`"; "**Profile:** `~/.diagram-design/profiles/<slug>.md`"; "**Working copy:** the current install's `references/style-guide.md`"; "**Project marker:** `<project-root>/.diagram-design`"; "**Effective style guide:** the profile or working copy selected for the current generation".
`profiles.md:15` — "Never place profiles inside an installed plugin: those directories may be replaced during updates."
`profiles.md:27` — "Each file is the full body of `style-guide.md` with one metadata comment prepended" (`<!-- diagram-design-profile / name / slug / source-url / created / updated / notes -->`, `profiles.md:30-37`).
`profiles.md:47` — "Except for the schema backfill described below, copy the body byte-for-byte. Saving and loading never reinterpret, normalize, reorder, or rewrite token values."
`profiles.md:51` — "`default.md` is the recovery copy of the current package's pristine shipped `references/style-guide.md`."
`profiles.md:67` — "Resolve the effective style guide again for every diagram; do not cache a selection across projects."
`profiles.md:74` — project marker grammar is exactly `profile: <slug>`; `:79` — "resolve only `~/.diagram-design/profiles/<slug>.md` … Do not copy it over the installed working copy."

Ingest/mapping heuristics, `references/onboarding.md:3` — "point the skill at a design source — a website, an installed skill, or a local folder — and have it extract the palette + typography, then rewrite `style-guide.md`".
`onboarding.md:228-235` — name→role heuristic table: `background|bg|paper|surface|canvas`→`paper`; `foreground|text|body|ink|on-surface`→`ink`; `muted|subtle|secondary|caption`→`muted`; `accent|brand|primary|cta|highlight`→`accent`; `border|rule|divider|outline`→`rule`; `mono|code|pre`→`sublabel` font.
`onboarding.md:237` — "If the JSON follows Style Dictionary format (`{ \"color\": { \"brand\": { \"value\": \"#…\" } } }`), flatten the path and apply heuristics to the leaf key."
`onboarding.md:215-216` — token source precedence: 1 `*.css`, `colors*.css`, `tokens.css` (`:root { --color-*: …; }`); 2 `tokens.json`, `design-tokens.json`, `*.tokens.json`.
`onboarding.md:105-111,116-122` — Step 3 emits a `Role | Detected | Confidence` table; constraint checks: AA contrast for `ink`/`muted` on `paper`, "Accent is the most saturated color", "paper ≠ pure white".

## 2. `skills/richdocs/`

Packs on disk: `/Users/jpeak/play/agentic-dotfiles/skills/richdocs/resources/themes/{freshgreens,locomotif,osakanights,v2ai}/`.
Plus default neutral pack `skills/richdocs/assets/design-tokens.json` (SKILL.md:225 — "| `assets/design-tokens.json` | Default neutral brandpack |").

One pack's files — `resources/themes/osakanights/`: `DESIGN.md` (37,919 B), `design-tokens.json` (5,853 B), `theme.css` (2,018 B). (`v2ai` also has DESIGN.md; `locomotif`/`freshgreens` ship only `design-tokens.json` + `theme.css`.)

`resources/themes/osakanights/design-tokens.json:1-36` (head):
```
{ "defaultTheme": "dark",
  "waivers": { "seriesContrast": "Ghibli Pastel L0.80/C0.11 is a defining stylistic identity of OsakaNights … Do not darken the palette or the chart bed to satisfy the gate." },
  "fonts": { "display": "'Fraunces', Georgia, serif", "body": "'Fira Sans', …", "mono": "'JetBrains Mono', …" },
  "themes": { "light": { "bg": "#faf8f9", "fg": "#1c1a20", "muted": "#57525e", "accent": "#5c4295",
                          "surface": "#ffffff", "border": "#d6ccd2", "onAccent": "#ffffff",
                          "link": "#5c4295", "radius": "12px", "pill": "999px" },
              "dark": { … "bg": "#101010", "fg": "#dddddd", "accent": "#c3b0fd", … } },
```
Top-level groups (`design-tokens.json:2,3,6,11,37,205,214`): `defaultTheme`, `waivers`, `fonts`, `themes` (`light`/`dark`), `canvas` (`cytoscape`:38, `plotly`:68), `categoryColours` (206-212: Compute, Storage, Database, Networking, Security, Integration, General), `status` (`light`:215 / `dark`:229).
Default pack `assets/design-tokens.json:2,6,24,58` has only `fonts`, `themes`, `canvas`, `categoryColours`.

`resources/themes/osakanights/DESIGN.md` headings: `# OsakaNights — Style Reference`; `## The origin story`(66); `## Scope`(78); `## The two mechanisms`(92); `## Modes — Night and Day`(104); `## Tokens — Colour`(121) with `### The names, in context`(123), `### The Street — neutral spine`(157), `### Neon — the accents`(192), `### Bloom`(231), `### Reflection`(237), `### Signals — **RESERVED**`(243), `### Encore — the one saturated colour`(269); `## Tokens — Typography`(277); `## Tokens — Spacing & Shapes`(328); `## Data Visualisation`(348) with `### Ghibli Pastel`(352), `### Dotonbori … (seriesAlt)`(360), `### Concrete`(410), `### Bundle of Fibres`(422), `### Sequential`(436), `### Diverging`(441), `### Chart rules`(456); `## Hospitality Contract`(466); `## Motion`(487); `## Iconography`(501); `## Voice & Tone`(509); `## Do's and Don'ts`(531); `## Decision Log`(552); `## Similar Brands`(573); `## Quick Start`(582) incl. `### Deriving a new colour`(661).

Pack selection / injection — `skills/richdocs/SKILL.md`:
- `:26` — "| \"Render it in a brand theme\" | default is `osakanights`; `md2html.py DOC.md --theme NAME` for another (see `--help` for installed themes) |"
- `:28` — "| \"Override a theme for this project\" | drop `tmp/richdocs/theme/<name>/design-tokens.json` (+ optional `theme.css`) — shadows the built-in of that name |"
- `:29` — "| \"Add a new brand theme\" | `resources/themes/<name>/design-tokens.json` (+ optional `theme.css`) |"
- `:30` — "| \"Is this theme readable?\" | `themecheck.py` — contrast gate over every brandpack; part of `make ci` |"
- `:102-104` — "**`--theme NAME`** — a named brand theme. Supplies both the brandpack (`design-tokens.json`) *and* its `theme.css` — which is the only place a webfont can actually be `@import`ed …"
- `:107-109` — "**Default theme is `osakanights`** — a plain `md2html.py DOC.md` renders branded, not neutral. … or `--tokens FILE` (with no `--theme`) for the raw-brandpack escape hatch."
- `:110-113` — "**Themes resolve from two roots, project first**: `tmp/richdocs/theme/<name>/` … `resources/themes/<name>/`. A project theme shadows the built-in of the same name and can add project-only themes."
- `:124-126` — "**`--tokens FILE`** — raw-brandpack escape hatch … Applies only when passed **and** `--theme` is not; otherwise the default `osakanights` theme wins."
- `:187-188` — "Canvas colours come from `design-tokens.json` (`canvas.cytoscape.*`, `canvas.plotly.*`), never CSS — canvases can't read CSS variables."
- `:200` — "**Brandpack is data, not code**: re-skin = edit `design-tokens.json` in the …"

Schema + rules — `resources/rich-blocks.md:129-132` "## The brandpack: `design-tokens.json` / One JSON file, copied verbatim into the output dir, fetched at runtime. Re-brand = edit the copy, refresh. Schema (all keys required):" (block at `:134-151` lists `fonts`, `themes.light|dark {bg,fg,muted,accent,surface,border}`, `canvas.cytoscape.*{nodeFill,nodeLabel,edge,compoundBg,compoundBorder}`, `canvas.plotly.*{paper,plot,font,grid,series[5]}`, `categoryColours`).
`rich-blocks.md:153-155` — "### Why two palettes (the load-bearing design fact) / **Canvas renderers cannot read CSS custom properties.** So theming is split:" → `themes.*` → CSS vars under `:root[data-theme=…]`; `canvas.*` → parallel JS palette.
`rich-blocks.md:168-176` — "### Rules that keep brandpacks sane": "**Data-encoding colours are not branded.** Status red/amber/green and `categoryColours` stay constant across brands and themes; only chrome and accent re-skin. A rebrand must never change what the colours *mean*."; "**WCAG AA (≥4.5:1)** for all fg/bg pairs in both themes."; "**`FALLBACK_TOKENS`** … is a fetch-failure safety net … not a place to customise."

ADR log `resources/adr-log.md` titles (file order): ADR-019 — Output report is worktree-aware and prints absolute paths (:10); ADR-018 — A project-local override dir supplies themes; the default brand is a named theme (:33); ADR-017 — A map may opt into a real basemap; a page may compute its own data in-browser (:63); ADR-016 — A stated stylistic identity waives a gate via an explicit per-theme waiver (:79); ADR-015 — Authored prose follows a global-audience standard; rendered content stays verbatim (:93); ADR-014 — A 3D block is a *projection*, and a visual claim must carry its own referent (:111); ADR-001 — Companion, not replacement (:143); ADR-002 — Packaged scripts here; teaching patterns stay in the `cli` skill (:155); ADR-003 — Vendored stencil zip, loaded in memory (:168); ADR-013 — If a brand ships a ramp, the schema must hold it and the gate must check it (:183); ADR-012 — `accent` has three jobs; a gate checks the pairings CSS actually renders (:211); ADR-011 — A showcase is a gallery OR a single brand, never a mixture (:237); ADR-010 — The brandpack is paired with the doc, not with the output directory (:260); ADR-009 — Named themes are a directory, and `theme.css` is part of the contract (:277); ADR-008 — The generator holds no template; `assets/viewer.*` is the page (:304); ADR-004 — Two-palette brandpack (chrome CSS vars + canvas JS palette) (:333); ADR-005 — Pinned CDN, lazy canvas loads, no vendoring of JS libs (:351); ADR-006 — Evals deferred (:365); ADR-007 — Self-contained: vendor the mermaid toolchain, never reference sibling skills (:377).

ADR-016 in full (`adr-log.md:79-91`):
> ### ADR-016 — A stated stylistic identity waives a gate via an explicit per-theme waiver
> Status: Accepted. Context: OsakaNights' `Ghibli Pastel` series (L0.80/C0.11) is a defining identity, used identically Day/Night; on the light plot its marks are ~1.7:1, under the 3:1 mark-contrast rule. The maintainer ruled the palette higher priority than that gate (three times); marks are always legended and clear CVD adjacency (ΔE 9.3). Decision: a pack may declare `waivers.seriesContrast` (a required justification string); `check_series` then skips mark-contrast for the PRIMARY series only, prints a visible `[note]`, still enforces CVD adjacency, and still checks `seriesAlt` strictly. No waiver = the strict rule for every other pack. Lens: when a deliberate stated identity conflicts with a gate, the identity wins — but only via an explicit, self-printing, per-artifact waiver, never a silent global loosen; waive the negotiable check (contrast, mitigated by labels), never the non-negotiable one (CVD distinguishability).

ADR-013 in full (`adr-log.md:183-209`):
> ### ADR-013 — If a brand ships a ramp, the schema must hold it and the gate must check it
> - **Status:** accepted (extends ADR-012)
> - **Context:** the showcase "did not reflect the true colour palette" because it could not — `canvas.plotly.<mode>` held only `series`, so **five sixths** of a documented data-viz system (muted, sequential, diverging ×2, status) had nowhere to live. The palette was not wrong, it was *absent*, and nothing failed because nothing was looking.
> - **Decision:** the schema now carries `muted`, `sequential`, `diverging` (`good`/`zero`/`bad`), optional `divergingAlt`, and a top-level `status` (`colours` + `labels`). `themecheck.py` gates every one of them: sequential must be **monotone in OKLab lightness** with ΔL ≥ 0.06 (else the steps cannot be ranked); the diverging **poles must separate by ΔE ≥ 12 under simulated deuteranopia**; the midpoint must be **achromatic** (a hue at zero reads as a value); status colours must clear AA **and carry a label** (colour never alone); adjacent categorical slots must clear the CVD relief floor.
> - **Consequences:** **green↔red diverging is now structurally impossible to ship** — its poles collapse to ΔE ≈ 1–3 and the gate rejects them. The gate found a real defect on its first run: V2's categorical slots 4/5 separated by only ΔE 7.7; the order was re-optimised to 13.8. V2 ships **no** `divergingAlt`, because no green-adjacent hue survives against its pink (scan: hue 160 → ΔE 1.8; only ≥220, which is blue, clears 12) — the honest answer was to omit it, not invent one.
> - **Lens:** a token schema is a *contract about what can be expressed*. When a brand documents something the schema cannot hold, the schema is the bug — and the moment a ramp becomes expressible, it becomes renderable, so it must simultaneously become **checkable**. Ship the field and the gate in the same change, or you have just built a new way to be silently wrong.

ADR-007 in full (`adr-log.md:377-400`):
> ### ADR-007 — Self-contained: vendor the mermaid toolchain, never reference sibling skills
> - **Status:** accepted (user adjudication; partially supersedes ADR-002)
> - **Context:** a companion shipped with an unparseable `mindmap` fence (quoted labels + `&amp;` entity → 0 nodes); `md2html.py` passes fences through verbatim, so the breakage surfaced only in the browser. A mermaid parse + contrast gate exists as prior art. The first fix pointed richdocs at the sibling skill's scripts; the user overruled it: **richdocs must stand on its own — it must not rely on or be aware of sibling skills.**
> - **Decision:** vendor a wholesale copy of the mermaid toolchain at `vendor/mermaidjs-diagrams/` (scripts, tests, Makefile, resources — same vendoring posture as the stencil zip, ADR-003). SKILL.md mandates running the *vendored* `mermaid_complexity.ts` + `mermaid_contrast.ts` on the source markdown before `md2html.py`; non-zero exit is a blocker. All cross-skill links in SKILL.md and `resources/*.md` were removed. The case is in `resources/learned/mermaid-syntax-gate.md`.
> - **Consequences:** ~1.5 MB duplicated; drift from upstream is accepted and managed by re-vendoring (see refresh below). Gate needs `bun` + `bun install --cwd vendor/mermaidjs-diagrams/scripts --frozen-lockfile` once. Maintainer docs (this file) may name the upstream for provenance; runtime surfaces (SKILL.md, resources) must not.
> - **Refresh procedure:** re-vendor wholesale — `rsync -a --exclude node_modules --exclude '.*cache*'` from the upstream skill dir, re-run `bun install --frozen-lockfile` and `make -C …/vendor/mermaidjs-diagrams/`

`scripts/themecheck.py:6-23` docstring:
> """Contrast gate for brandpacks. Fails loudly; never "fixes" a theme silently.
> This exists because a theme once shipped that was contrast-clean and completely off-brand: V2 AI's accent is a bright yellow, but `accent` was the token used for BOTH heading/link text AND button fills. Yellow is 1.64:1 on white, so it cannot be text. Faced with an impossible token, the pack quietly substituted a cyan that V2 does not own — and every check passed, because nothing was checking the thing that mattered.
> Two lessons are encoded here:
> 1. **`accent` has three jobs** and they must be separate tokens: `accent` — the FILL (surfaces, CTAs, rules). No text-contrast duty. / `onAccent` — the text that sits ON that fill. / `link` — the TEXT-SAFE accent (headings, links). Falls back to `accent`.
> 2. **Check the pairings the CSS actually renders**, not a plausible-looking list. Each row below names the real rule it guards."""

`themecheck.py:64-70` `CHECKS` rows (name, fg, bg, threshold, rule): "body text" fg/bg; "body on surface" fg/surface; "muted text" muted/bg; "heading / link" link/bg; "link on surface" link/surface; "text on accent fill" onAccent/accent.
`themecheck.py:74-76` — `CVD_TARGET = 12.0  # Machado-2009 ΔE`; `CVD_RELIEF = 8.0`; `DL_FLOOR = 0.06`.
Check/helper functions (`themecheck.py`): `luminance`, `contrast`, `roles`(:54), `lightness`, `simulate_cvd`, `cvd_distance`, `check_ramps`(:171), `check_status`(:235), `check_series`(:255), `check_theme`(:298), `main`, `build_parser`.

## 3. `skills/mermaidjs-diagrams/`

`resources/color_theming.md` headings: `# Mermaid Color Theming Reference`; `## 1. Core Syntax Recap`(17) [`### classDef + class`, `### Shorthand ::: operator`, `### Direct style directive`, `### Available style properties`]; `## 2. HSL-Based Color Encoding System`(58) [`### Theory: Three Visual Channels`, `### Mapping to Diagram Roles`(70), `### Converting to Hex for classDef`]; `## 3. Light Mode + Dark Mode Safety`(95) [`### The Core Problem`, `### The Rule: Always Pair fill: with color:`, `### Safe Background + Text Pairings`, `### WCAG Contrast Minimums`]; `## 4. Visual Hierarchy Techniques`(170); `## 5. Subgraph Coloring`(216); `## 6. Color Palette Recipes`(284); `## 7. Complete Worked Example`(294); `## 8. Gotchas and Renderer Differences`(301); `## 9. Tailwind v3 Hex Reference (Subset for Diagrams)`(365); `## 10. linkStyle for Edge Coloring`(378); `## 11. Host-Themed Renderers: Translucent Dual-Theme Fills`(406); `## Sources`(419).

Role/palette naming block, `color_theming.md:70-85` `### Mapping to Diagram Roles` — "Assign each **category** (input, process, output, storage, external) a distinct **hue family**. Within each family, vary saturation and lightness to encode **prominence** (primary vs. secondary vs. background)" then the code block whose rows are `Input/Source | Blue (210-220)`, `Process/Logic | Violet (270)`, `Output/Sink | Emerald (160)`, `Storage/Data | Amber (38-45)`, `Error/Danger | Red (0-4)`, `External/API | Slate (215)`, each with Primary / Secondary / Background hsl() values.
Palette source, `color_theming.md:90-92` — "HSL values must be converted to hex for Mermaid. The Tailwind CSS palette provides pre-converted values … Throughout this document, all hex values are sourced from Tailwind v3 for consistency."
`color_theming.md:284-290` — "Four ready-to-use palette recipes — **A** Software Architecture (cool tones), **B** Data Flow / ETL (warm tones), **C** State / Workflow (semantic colors), and **D** High-Density Knowledge Graph (8 distinct hues) — now live in **`color_palette_recipes.md`**."
Channel table, `color_theming.md:64-68` — Hue → "Category/type (nominal)"; Saturation → "Importance/prominence (ordinal)"; Lightness → "Rank/depth within category (ordinal)".

`scripts/mermaid_contrast.ts` vocabulary — no semantic token roles; it works on raw Mermaid CSS properties and profile/theme enums:
- `mermaid_contrast.ts:49` `export type Profile = "github" | "mkdocs-material";`
- `:60-61` `export type PairKind = "text" | "border";` / `export type Theme = "light" | "dark";`
- `:101-102` `const AA_NORMAL = 4.5; // text rule` / `const AA_NON_TEXT = 3.0; // UI-component / border rule`
- Directives come from `color_contrast.ts:44-50`: `interface StyleDirective { kind: "classDef" | "style" | "linkStyle" | "inlineClass"; selector; class_name?; properties: Record<string,string>; // { fill: "#2563eb", color: "#fff", stroke: "..." } ; line }`
- `color_contrast.ts:141-148` — parsed forms `classDef NAME fill:#X,stroke:#Y,color:#Z,stroke-width:2px`; `style NODEID …`; `linkStyle 0,1 stroke:#X,…`; "check (fill×color for text, fill×stroke for border)".

CLAUDE.md / ADR presence: **no** `skills/mermaidjs-diagrams/CLAUDE.md`; **yes** `skills/mermaidjs-diagrams/scripts/CLAUDE.md`. No ADR or decision-log file anywhere under this skill (`find … -iname '*adr*' -o -iname '*decision*'` returned none).

## 4. Cross-cutting

- `/Users/jpeak/play/agentic-dotfiles/skills/cli/CLAUDE.md:77` — "### ADR-0003 — Re-skin via design tokens is the anti-repetition lever"; `:81` — "**Decision:** make the viewer read a `design-tokens.json` at runtime (palette/fonts/…"
- `/Users/jpeak/play/agentic-dotfiles/skills/cli/resources/static-spa-viewer.md:101` — "## Rebrandable theming via `design-tokens.json`"; `:104` — "Tokens (palette, fonts, thresholds, optionally a `brands` map) are fetched at runtime and…"; `:26` — "**`design-tokens.json` is copied verbatim — never templated**".
- `/Users/jpeak/play/agentic-dotfiles/skills/cli/SKILL.md:60` — "JS/HTML — edit `design-tokens.json` (palette/fonts/brand) and re-serve."
- `/Users/jpeak/play/agentic-dotfiles/skills/slides/resources/authoring.md:126` — "The scaffold derives the palette from a project's design-tokens JSON".
- `/Users/jpeak/play/agentic-dotfiles/skills/slides/README.md:42` — "--out docs/slides --name product-pitch --tokens frontend/src/design-tokens.json \".
- `/Users/jpeak/play/agentic-dotfiles/skills/setup-fullstack/resources/frontend/CLAUDE.md` — mentions design tokens (frontend scaffold guidance).
- `/Users/jpeak/foss/diagram-design/tmp/richdocs/skill-patterns.tokens.json` — a richdocs-format brandpack sitting inside the external repo's `tmp/`.
- Mirrors: `/Users/jpeak/play/agentic-dotfiles/.claude/skills/{cli,slides,richdocs,mermaidjs-diagrams}/…` duplicate the above paths (installed copies).
