# richdocs — maintainer guide

Read the ADR log below before changing anything; every structural choice here
was deliberate. Dev loop:

```bash
make -C .claude/skills/richdocs/scripts fix   # mutate: format + lint-fix
make -C .claude/skills/richdocs/scripts ci    # gate: must exit 0 before handoff
```

## File map

| File | Role |
|------|------|
| `SKILL.md` | agent operating manual: route-by-intent, command reference, block contract |
| `README.md` | human explainer: diagram, quickstart, troubleshooting |
| `resources/serving.md` | `file://` failure mode, no-store contract, pinned CDN table |
| `resources/stencil-library.md` | pack schema, tint mechanism, compose pattern, refresh procedure |
| `resources/rich-blocks.md` | fenced block contract, design-tokens schema, two-palette theming |
| `resources/discovery-docs.md` | per-archetype upgrade recipes, fidelity ladder |
| `resources/prose-style.md` | global-audience standard for **authored** prose (no em-dash, Australian English, short clauses, inclusive language, standard vocabulary); self-contained copy (ADR-015) |
| `scripts/serve.py` | no-store localhost server (stdlib) |
| `scripts/stencil.py` | stencil query/extract CLI (stdlib, in-memory zip load) |
| `scripts/themecheck.py` | **brandpack contrast gate** — part of `make ci`. Checks the pairings the CSS actually renders (ADR-012) |
| `scripts/showcase.py` | **theme showcase** generator — gallery of every brand, or one brand alone (`--theme`). Composes architecture diagrams from the stencil pack as drawio-editable SVG (ADR-011) |
| `assets/showcase.{html,css,js}` | the showcase page. Placeholder-free JS/CSS; only `showcase.html` carries `{{...}}` |
| `scripts/md2html.py` | markdown → HTML companion **generator** (stdlib). Contains no HTML/CSS/JS source — it assembles the `assets/viewer.*` files (ADR-008) |
| `assets/viewer.html` | the page shell — the **only** file carrying `{{...}}` placeholders |
| `assets/viewer.css` | viewer chrome; all colour/font via `--rd-*` custom properties |
| `assets/viewer.js` | runtime renderer (marked → fenced-block upgrades → theme flip). **Placeholder-free by contract** — reads generation-time values from the `#rd-config` JSON block |
| `assets/viewer-cytoscape.js` | graph styling + render (`rdRenderCytoscape`). Inlined *before* `viewer.js` so its functions are hoisted. Placeholder-free (ADR-008) |
| `assets/viewer-deckgl.js` | 3D / geographic render (`rdRenderDeckGL`) + the OKLab/OKLCH maths and colour-space projections. Inlined *before* `viewer.js`, same hoisting contract (ADR-014) |
| `resources/themes/<name>/` | a named brand theme: `design-tokens.json` (required) + `theme.css` (optional). Selected with `--theme` (ADR-009) |
| `scripts/Makefile` | fix/ci contract per `.claude/rules/claude_skills/scripts.md` |
| `assets/stencils.json.zip` | vendored draw.io icon packs (~3.4 MB; see `assets/NOTICE`) |
| `assets/design-tokens.json` | default neutral brandpack (schema in `rich-blocks.md`) |
| `resources/learned/` | self-curated adjudications/facts (statefulness Pathway 2) — read before re-litigating a past failure |
| `vendor/mermaidjs_diagrams/` | wholesale vendored mermaid toolchain (parse/complexity + contrast gates, theming references) — refresh per ADR-007, never cherry-pick |

## Invariants

- Every prose file ≤500 lines (`.claude/rules/claude_skills/index.md`).
- Scripts are Tier B (stdlib-only, PEP-723, `uv run --no-project`); network
  is only consumed by the *browser* loading pinned CDN libs, never by the
  Python. Missing inputs crash loudly (escalators-not-stairs).
  Exception: `vendor/mermaidjs_diagrams/` is Tier A (bun + frozen lockfile)
  — it is vendored wholesale, not authored here (ADR-007).
- Self-contained: no file under this skill instructs the agent to run or
  read another skill's files (ADR-007).
- Outputs go to project-local `tmp/richdocs/`, never system `/tmp`.
- Anything embedded in a `<script>` escapes `</` → `<\/`.
- Same input → same output modulo `{{BUILD_ID}}`.

## ADR log

### ADR-017 — A map may opt into a real basemap; a page may compute its own data in-browser

Status: Accepted. Context: the showcase geo map "still showed no dark tiles" and the
user wanted the vector dark basemap their reference app uses, plus a way to prove the
DATA→TRANSFORM half of the pipeline (query complex data, feed the result to a block).
Decision, two opt-ins that keep the defaults untouched: (1) a `map`-view deckgl block
gains `basemap` (raster, a deck `TileLayer`) and `basemapStyle` (a **vector GL style** —
MapLibre owns the map + camera, deck rides as a `MapboxOverlay`). Both are free + keyless;
the vector path is preferred because MapLibre's tile pipeline is robust where a hand-rolled
raster layer can silently blank. (2) a page may run **duckdb-wasm** (in-browser OLAP SQL,
CDN ESM, mvp/eh bundle so no COOP/COEP) and drive any block from the result rows. Lens: a
basemap and a data engine are both **environment degradations, never requirement ones** —
default to no-dependency (brand canvas, seeded data), let a caller opt into the heavier,
more capable path explicitly; and when a raster tile layer "works for me" but blanks for a
user, reach for the library whose loader is battle-tested (MapLibre) before hand-tuning tiles.

### ADR-016 — A stated stylistic identity waives a gate via an explicit per-theme waiver

Status: Accepted. Context: OsakaNights' `Ghibli Pastel` series (L0.80/C0.11) is a
defining identity, used identically Day/Night; on the light plot its marks are ~1.7:1,
under the 3:1 mark-contrast rule. The maintainer ruled the palette higher priority than
that gate (three times); marks are always legended and clear CVD adjacency (ΔE 9.3).
Decision: a pack may declare `waivers.seriesContrast` (a required justification string);
`check_series` then skips mark-contrast for the PRIMARY series only, prints a visible
`[note]`, still enforces CVD adjacency, and still checks `seriesAlt` strictly. No waiver
= the strict rule for every other pack. Lens: when a deliberate stated identity conflicts
with a gate, the identity wins — but only via an explicit, self-printing, per-artifact
waiver, never a silent global loosen; waive the negotiable check (contrast, mitigated by
labels), never the non-negotiable one (CVD distinguishability).

### ADR-015 — Authored prose follows a global-audience standard; rendered content stays verbatim

- **Status:** accepted (2026-07)
- **Decision:** `resources/prose-style.md` holds the standard for prose this
  skill **authors** (showcase copy, UI/error strings, this skill's own docs, a
  discovery doc it is explicitly asked to upgrade): no em-dash, Australian
  English, short coherent clauses, ESL/translator readability, inclusive
  language, standardised vocabulary. The user's canonical markdown is the source
  of truth (ADR-001), so faithfully-rendered content is **never** rewritten to
  satisfy a style rule. ESL/translator readability is an evaluable check (proxy
  metrics or a round-trip translation), not an adjective. Detection is
  tooling-agnostic: the file names *what* to find, never *which* command.
- **Consequences:** SKILL.md gained one cross-cutting convention and a resources
  row.
- **Lens:** separate the prose you **author** from the prose you **render**;
  apply the standard to the former, preserve the latter verbatim. When enforcing
  a prose rule, describe the target, not the tool.

### ADR-014 — A 3D block is a *projection*, and a visual claim must carry its own referent

- **Status:** accepted
- **Context:** two needs arrived together. A doc had to explain **why a palette
  documented as "uniform chroma" was not uniform** — a 2D swatch row cannot show it,
  because the answer lives in a 3D space (a colour's chroma ceiling depends on its
  hue *and* its lightness). And the block set was capped at graph (cytoscape) and
  chart (plotly), with no way to render a spatial or geographic argument at all.
- **Decision:** add a ` ```deckgl ` block whose `layers[].type` is looked up on
  deck's global — so **every deck.gl layer works with no code change here**; the
  block is open by construction. The specific part is one idea: **a colour space is
  just a function `rgb -> [x, y, z]`.** Swap the projection and every mark moves;
  the data never changes. That is why one block serves both a gamut study
  (`OrbitView`) and a map (`MapView`) — a layer only ever asks *where does this
  datum live*. A datum carrying `hex` therefore needs **neither position nor
  colour**: it is its own coordinate. `map` view ships **no basemap by default** —
  the brand canvas is the basemap, no vendor key required (opt into real tiles via
  ADR-017's `basemap`/`basemapStyle`).
- **Consequences:** the first render was *correct and told the wrong story* — spokes
  to the gamut ring read as "chroma denied" but actually measured **unused headroom**
  (the clipped colours sat **on** the ring, spoke-less). A hex records what was
  **granted**, not what was **asked for**, so the spec now carries the intent
  (`targetChroma`) and draws **two** rings: the requested circle against sRGB's lumpy
  blob. Clipping is where the circle escapes the blob, and it reads without a caption.
- **Lens:** when a visualisation implies a *shortfall*, check what it is measuring
  the distance **from**. A rendering can only show the values it is given; if the
  claim is "you did not get what you asked for", then **the request is data and must
  be in the spec** — never inferred from the result, which by definition only knows
  the outcome. And when adding a renderer, expose the *library's* type system rather
  than a hand-rolled whitelist; keep your own cleverness to the one transform the
  library lacks.

### ADR-001 — Companion, not replacement

- **Status:** accepted
- **Context:** discovery docs must stay readable on GitHub and reviewable as plain
  diffs; earlier attempts replaced markdown with HTML apps that rotted.
- **Decision:** the `.md` is canonical and committed; HTML is generated into
  gitignored `tmp/richdocs/` and regenerated at will. Fenced rich blocks
  degrade on GitHub to visible JSON code blocks.
- **Consequences:** no committed HTML to drift; sharing uses `--inline`.
- **Lens:** when a feature tempts you to add authoring state to the HTML side, put it
  in the markdown or a data `.json` instead — the HTML must always be regenerable.

### ADR-002 — Packaged scripts here; teaching patterns stay in the `cli` skill

- **Status:** partially superseded by ADR-007 — the *scope* decision stands
  (richdocs ships packaged tools; rung-4 SPA builds are out of scope), but
  the lateral links from runtime surfaces to the `cli` skill were removed;
  richdocs surfaces no longer reference sibling skills.
- **Decision:** `richdocs` ships runnable, generic tools; its resources cover only
  what's new (stencil pack, block contract, serving, recipes). A doc that outgrows the
  companion (routing, sidebar, views) graduates to a full SPA build — see the fidelity
  ladder in `discovery-docs.md`.
- **Lens:** before adding a feature to `md2html.py`'s template, ask "is this rung 4?"
  — if yes, it belongs in a standalone SPA project, not here.

### ADR-003 — Vendored stencil zip, loaded in memory

- **Status:** accepted
- **Context:** the tfs `diagrams` module proved the draw.io extraction; the
  user wants the icon library on-hand without depending on the tools-tfs
  repo. GitHub renders SVG; icons work in markdown *and* HTML.
- **Decision:** copy `stencils.json.zip` + `NOTICE` into `assets/`;
  `stencil.py` unzips in memory (`io.BytesIO`, `functools.cache`), located
  relative to `__file__`. The extractor script is *not* vendored — refresh
  procedure documented in `stencil-library.md`.
- **Consequences:** ~3.4 MB in the repo (accepted); no runtime coupling to
  tools-tfs; re-extraction requires the source repo.
- **Lens:** when the pack needs new shapes, re-vendor the whole zip from the
  source extractor — never hand-edit entries or unzip into the repo.

### ADR-013 — If a brand ships a ramp, the schema must hold it and the gate must check it

- **Status:** accepted (extends ADR-012)
- **Context:** the showcase "did not reflect the true colour palette" because it
  could not — `canvas.plotly.<mode>` held only `series`, so **five sixths** of a
  documented data-viz system (muted, sequential, diverging ×2, status) had nowhere
  to live. The palette was not wrong, it was *absent*, and nothing failed because
  nothing was looking.
- **Decision:** the schema now carries `muted`, `sequential`, `diverging`
  (`good`/`zero`/`bad`), optional `divergingAlt`, and a top-level `status`
  (`colours` + `labels`). `themecheck.py` gates every one of them:
  sequential must be **monotone in OKLab lightness** with ΔL ≥ 0.06 (else the steps
  cannot be ranked); the diverging **poles must separate by ΔE ≥ 12 under simulated
  deuteranopia**; the midpoint must be **achromatic** (a hue at zero reads as a
  value); status colours must clear AA **and carry a label** (colour never alone);
  adjacent categorical slots must clear the CVD relief floor.
- **Consequences:** **green↔red diverging is now structurally impossible to ship** —
  its poles collapse to ΔE ≈ 1–3 and the gate rejects them. The gate found a real
  defect on its first run: V2's categorical slots 4/5 separated by only ΔE 7.7; the
  order was re-optimised to 13.8. V2 ships **no** `divergingAlt`, because no
  green-adjacent hue survives against its pink (scan: hue 160 → ΔE 1.8; only ≥220,
  which is blue, clears 12) — the honest answer was to omit it, not invent one.
- **Lens:** a token schema is a *contract about what can be expressed*. When a brand
  documents something the schema cannot hold, the schema is the bug — and the moment
  a ramp becomes expressible, it becomes renderable, so it must simultaneously become
  **checkable**. Ship the field and the gate in the same change, or you have just
  built a new way to be silently wrong.

### ADR-012 — `accent` has three jobs; a gate checks the pairings CSS actually renders

- **Status:** accepted
- **Context:** the V2 AI theme shipped **contrast-clean and completely off-brand**.
  Its `#FFC000` yellow accent served BOTH text AND fills, but yellow is **1.64:1 on
  white** — legal as a surface, impossible as text. Unable to satisfy that token, the
  pack quietly substituted a cyan V2 does not own, and every check passed. **The gate
  was green because it was measuring the wrong thing.**
- **Decision:** split the accent into three tokens, with fallbacks so older packs
  keep working:
  - `accent` — the **fill** (CTAs, rules, active states). No text-contrast duty.
  - `onAccent` — the text that sits **on** that fill (defaults to `bg`).
  - `link` — the **text-safe** accent for headings and links (defaults to `accent`).
  Geometry joins them (`radius`, `pill`), because "square corners" is a brand rule
  that CSS defaults were silently overriding. Then `themecheck.py` — wired into
  `make ci` — validates **the pairings the CSS actually renders**, each check naming
  the rule it guards. It fails the build; it never "helpfully" adjusts a colour.
- **Consequences:** a brand with no text-safe accent (V2 has none) declares
  `link` = its ink and lets the accent reach text as a **rule** (a yellow underline),
  never as a glyph — which is what the brand does in real life. No invented colours
  remain in the V2 pack: every hex is one V2 actually owns.
- **Lens:** when a design token cannot satisfy every job it is asked to do, the
  token is wrong — **split it**. And a contrast check that does not mirror the CSS
  is theatre: check `onAccent`-on-`accent`, not `fg`-on-`bg`, because the button is
  what the reader has to read.

### ADR-011 — A showcase is a gallery OR a single brand, never a mixture

- **Status:** accepted
- **Context:** two different jobs were being asked of one artifact: *compare brands*
  (needs every brand in one page, switchable) and *hand someone a brand reference*
  (must contain that brand and nothing else — shipping a client a page with a
  competitor's palette inside it is not acceptable, even if it is not displayed).
- **Decision:** `showcase.py` with no `--theme` emits a **gallery**: every installed
  brand embedded, a brand switcher, and a light/dark toggle; each brand honours its
  own `defaultTheme` on selection. `--theme NAME` emits that brand **alone** — the
  switcher element is removed and no other brand's tokens or CSS are in the file. A
  test asserts the other brand's name does not appear anywhere in the artifact.
- **Consequences:** every brand's `theme.css` must be **scoped** to
  `:root[data-brand="<name>"]` so brands cannot leak in a gallery. `@import` cannot be
  scoped (legal only at the top of a sheet), so imports are hoisted out and emitted
  once. The scoper is a regex — fine for hand-written `theme.css`, not arbitrary CSS.
- **Architecture diagrams** are composed from the vendored stencils and carry their
  own `mxfile` source in the SVG's `content` attribute, so they re-open in
  diagrams.net as **real AWS shapes**, not a flattened picture. A missing stencil id
  fails the build (escalators-not-stairs) rather than rendering an empty box.
- **Lens:** when one artifact is asked to serve two audiences with incompatible
  containment rules, emit two artifacts. Do not hide content and call it isolation.

### ADR-010 — The brandpack is paired with the doc, not with the output directory

- **Status:** accepted
- **Context:** multi-file mode wrote one `design-tokens.json` per output dir, fetched
  by a fixed name — so a second doc rendered with a different `--theme` into the same
  dir **silently overwrote the first doc's brandpack**, and both then loaded the
  survivor's palette. A shared mutable filename in a dir designed to hold many docs
  was the bug.
- **Decision:** the pack is paired with the doc, exactly as the markdown already
  is: `<stem>.md` · `<stem>.html` · **`<stem>.tokens.json`**. The filename travels
  in `#rd-config` as `tokensSource`, so the viewer fetches its own pack.
- **Consequences:** one output dir can now hold any mix of themes. The
  "edit the tokens in the output dir and refresh" loop still works — the file is
  just named after the doc. `--inline` was never affected (tokens are embedded).
- **Lens:** in a directory that holds N of something, nothing may have a fixed
  singular name. If a file is *about* a doc, name it after the doc.

### ADR-009 — Named themes are a directory, and `theme.css` is part of the contract

- **Status:** accepted
- **Context:** a brandpack can *name* a font family but cannot **load** one — the
  first OsakaNights render fell back to system fonts because nothing `@import`ed Fira
  Sans. Nor can it say "headings use the display face" without reinventing CSS as
  tokens. And `--tokens path/to/pack.json` made the caller track where each brand
  lived, which does not scale past one brand.
- **Decision:** a theme is a **directory** at `resources/themes/<name>/` holding
  `design-tokens.json` (required) and `theme.css` (optional). Both are **real
  files inside the skill — never symlinks out to a project.** `.claude/` must stay
  isolated and portable: copy it anywhere and every theme still resolves. A brand
  that also lives in the wider repo is a *deliberate dual copy*; a symlink would
  be a co-dependency. A test asserts no theme file is a symlink. The pack chooses the
  faces (`fonts.display`/`body`/`mono`); `theme.css` only `@import`s the webfiles and
  expresses layout JSON cannot. `--theme NAME` resolves both; `theme.css` is injected
  *after* `viewer.css`, so a brand can override anything. Unknown names crash loudly
  and list the installed set. `--tokens` survives for ad-hoc packs, but a named theme
  supersedes it.
- **Consequences:** brands are now additive — drop in a directory, no code change.
  The token schema stays small (it only holds what canvas renderers need, which
  genuinely cannot read CSS); everything expressible in CSS stays in CSS.
- **Lens:** when a config format starts growing fields that are really just CSS,
  stop — give the brand a stylesheet instead. Tokens exist for the values CSS
  **cannot** reach (the canvas palettes, ADR-004). Everything else belongs in
  `theme.css`.

### ADR-008 — The generator holds no template; `assets/viewer.*` is the page

- **Status:** accepted (supersedes the `FALLBACK_TOKENS` half of ADR-004)
- **Context:** `md2html.py` had grown to 641 lines, **334 (58%) a triple-quoted
  `TEMPLATE`** holding the whole HTML/CSS/JS — no linting, Python-escaped regexes,
  and 241 lines of real logic buried in noise. Separately, `FALLBACK_TOKENS` was a
  55-line hand-copy of `design-tokens.json` guarded by an equality test — and a test
  asserting two things are identical means there should only be one of them.
- **Decision:** split at three seams — `assets/viewer.html` (shell, 44 lines),
  `assets/viewer.css` (chrome, 80), `assets/viewer.js` (renderer, 261).
  `md2html.py` (274) is now purely a generator: read assets, substitute, write.
  **All generation-time values (build id, source, CDN pins, fallback tokens) are
  delivered in one `<script type="application/json" id="rd-config">` block**, so
  `viewer.js` carries **zero placeholders** and is real, lintable JavaScript.
  `viewer.html` is the only file with `{{...}}`. `FALLBACK_TOKENS` is now *read*
  from `design-tokens.json` at import — the duplicate literal is deleted, and the
  hazard is retired rather than policed.
- **Consequences:** the browser behaviour is untestable by the Python suite
  (ADR-006 still bites), so a browser smoke-test of **both** output modes is
  mandatory after any asset edit. Missing/corrupt asset files now crash at import
  — correct (escalators-not-stairs). Two tests enforce the seam:
  `test_viewer_js_has_no_template_placeholders` and
  `test_assembled_html_inlines_the_css_and_js_assets`.
- **Lens:** when a generator starts carrying the artifact it generates, split
  them. Code that is *data to this program but source to another language*
  belongs in a file of that language, where its own tooling can see it. And when
  you find yourself writing a test that asserts two copies are equal, **delete a
  copy** — don't police the duplication, remove it.

### ADR-004 — Two-palette brandpack (chrome CSS vars + canvas JS palette)

- **Status:** accepted; the `FALLBACK_TOKENS` hand-sync hazard is **retired by
  ADR-008** (the fallback is now read from the asset, not re-declared)
- **Context:** proven in the adaf sdag viewer; canvas renderers (cytoscape,
  plotly) cannot read CSS custom properties.
- **Decision:** one `design-tokens.json` carries both palettes; the template
  applies `themes.*` as CSS vars and feeds `canvas.*` into renderers; theme
  flip does both. Data-encoding colours (`categoryColours`, status) are
  brand- and theme-invariant.
- **Consequences:** ~~one hand-sync hazard remains~~ — retired by ADR-008.
  `FALLBACK_TOKENS` is now read from `assets/design-tokens.json`, so there is
  only one copy of the default palette.
- **Lens:** any new themable surface gets a token in *one* of the two
  palettes by asking "can CSS reach it?" — never a hardcoded hex in
  `viewer.css` or `viewer.js`. (The sole exception is `.rd-error`, which must
  stay visible when token loading is the thing that failed.)

### ADR-005 — Pinned CDN, lazy canvas loads, no vendoring of JS libs

- **Status:** accepted
- **Context:** vendoring cytoscape/plotly/mermaid (~5 MB+) into every output
  dir was rejected; local viewing has network; offline is announced
  degradation.
- **Decision:** exact-version jsdelivr pins (table in `serving.md`);
  cytoscape/plotly injected only when a doc uses their blocks; fetch failures
  console.error and render visible error blocks.
- **Consequences:** fully-offline viewing is out of scope for v1; revisit
  with a `--vendor` flag if it becomes a real requirement.
- **Lens:** bump a pin deliberately (test all three block types), never by
  floating a major.

### ADR-006 — Evals deferred

- **Status:** accepted (deferred work)
- **Context:** `.claude/rules/claude_skills/evals.md` defines the golden/eval
  contract; building the harness now would have doubled the initial scope.
- **Decision:** ship v1 with the free deterministic gate only (`make ci`,
  ≥90% coverage). Eval goldens (render a fixture doc headlessly, assert
  blocks render) are the first follow-up.
- **Lens:** when the first regression slips past `ci` (likely a template/JS
  behaviour Python tests can't see), that's the trigger to build the eval
  suite — don't wait for a second.

### ADR-007 — Self-contained: vendor the mermaid toolchain, never reference sibling skills

- **Status:** accepted (user adjudication; partially supersedes ADR-002)
- **Context:** a companion shipped with an unparseable `mindmap` fence
  (quoted labels + `&amp;` entity → 0 nodes); `md2html.py` passes fences
  through verbatim, so the breakage surfaced only in the browser. A mermaid
  parse + contrast gate exists as prior art. The first fix pointed richdocs
  at the sibling skill's scripts; the user overruled it: **richdocs must
  stand on its own — it must not rely on or be aware of sibling skills.**
- **Decision:** vendor a wholesale copy of the mermaid toolchain at
  `vendor/mermaidjs_diagrams/` (scripts, tests, Makefile, resources — same
  vendoring posture as the stencil zip, ADR-003). SKILL.md mandates running
  the *vendored* `mermaid_complexity.ts` + `mermaid_contrast.ts` on the
  source markdown before `md2html.py`; non-zero exit is a blocker. All
  cross-skill links in SKILL.md and `resources/*.md` were removed. The case
  is in `resources/learned/mermaid-syntax-gate.md`.
- **Consequences:** ~1.5 MB duplicated; drift from upstream is accepted and
  managed by re-vendoring (see refresh below). Gate needs `bun` +
  `bun install --cwd vendor/mermaidjs_diagrams/scripts --frozen-lockfile`
  once. Maintainer docs (this file) may name the upstream for provenance;
  runtime surfaces (SKILL.md, resources) must not.
- **Refresh procedure:** re-vendor wholesale — `rsync -a --exclude
  node_modules --exclude '.*cache*'` from the upstream skill dir, re-run
  `bun install --frozen-lockfile` and `make -C …/vendor/mermaidjs_diagrams/
  scripts test-cov`. Never cherry-pick individual files.
- **Lens:** when richdocs needs a capability that lives in another skill,
  vendor a wholesale copy into `vendor/` — never link to, invoke, or
  instruct the agent to read a sibling skill's files. Self-containment
  outranks the never-duplicate rule for anything richdocs *operates with*.

## Known gotchas

- **Symptom: page loads, data never arrives, console CORS error** — opened
  multi-file output over `file://`. Expected; use `serve.py` or `--inline`.
- **Symptom: a `<script>` written inside a markdown doc never runs** — by design.
  The doc is rendered into `innerHTML`, and browsers never execute scripts
  inserted that way (XSS mitigation). `<style>` blocks *do* apply. To pin a
  doc's initial theme, set `defaultTheme` in its brandpack — not a script.
- **Symptom: the showcase does not show a palette the brand clearly documents** —
  the schema cannot express it. Check `canvas.plotly.<mode>` for `muted` /
  `sequential` / `diverging`, and the top-level `status` (ADR-013).
- **Symptom: a Plotly heatmap renders with `height="NaN"`** — layout objects were
  shared between charts. **Plotly mutates the layout you hand it** (it writes
  computed ranges onto `xaxis`/`yaxis`), so an `Object.assign({}, base, …)` shallow
  copy leaks the bar chart's numeric y-range into the heatmap's categorical axis.
  Build a **fresh layout per chart**. Vector traces survive this; rasters do not.
- **Symptom: a theme passes every check but looks nothing like the brand** — the
  brandpack substituted a colour the brand does not own, because one token was
  asked to be both a fill and a text colour. Run `themecheck.py`; split
  `accent` / `onAccent` / `link` (ADR-012).
- **Symptom: a brandpack names a webfont but the page renders in system fonts** —
  the pack *chooses* faces, it cannot *load* them. Use `--theme`, whose `theme.css`
  does the `@import`. (A doc can also `@import` in its own `<style>` block.)
- **Symptom: a doc renders in another doc\'s brand** — pre-ADR-010 behaviour, or a
  hand-rolled output dir with a stale shared `design-tokens.json`. Each doc now
  owns `<stem>.tokens.json`; delete any leftover `design-tokens.json`.
- **Symptom: two docs with the same stem overwrite each other** — `write_multi`
  keys everything off `doc.stem`, so `a/DESIGN.md` and `b/DESIGN.md` collide.
  Render them to different `--out` dirs.
- **Symptom: a `plotly` chart renders squashed into a sliver** — `.rd-canvas` has no
  height in CSS, and `responsive: true` makes Plotly size itself to that
  content-driven parent, which collapses. **Every block renderer owes its container
  an explicit height** (`payload.height`, defaulting to 420); cytoscape and deckgl
  always did, plotly did not. Never "fix" this by putting a height on `.rd-canvas` —
  that would force one height on all three block types.
- **Symptom: a `deckgl` orbit scene renders correctly but is the size of a postage
  stamp** — deck's OrbitView `zoom` is `log2(pixels per world unit)`, **not** a map
  zoom. The spaces are normalised to a ~1-unit extent, so they need `zoom ≈ 9`; a
  map-like `zoom: 2` gives ~4 px of scene. A gamut study is also a horizontal *slab*
  at some lightness, so the camera must target `y = L - 0.5`, or the subject drifts
  to the top of the frame.
- **Symptom: a `deckgl` gamut scene shows spokes on the colours that are FINE and
  none on the colours that are broken** — the spoke is measuring distance to the
  sRGB ceiling, which is *unused headroom*, not clipping. A clipped swatch sits
  **on** the ring, so its headroom is zero. Set `targetChroma` (the requested value);
  clipping is `ceiling < target`, and it cannot be inferred from the hex alone
  (ADR-014).
- **Symptom: `deckgl` dots render darker / muddier than the swatch of the same
  hex** — deck.gl's lit layers (`PointCloudLayer`, `ColumnLayer`, …) shade each mark
  as a 3D solid under ambient+directional light, so the fill darkens and no longer
  matches its own colour. In a colour-space visualiser the mark *is* a colour claim;
  a lit mark makes it false. `rdBuildLayers` defaults `material: false` (lighting off)
  for exactly this reason — an author wanting shaded geometry opts back in per layer.
- **Symptom: a `deckgl` map with `basemapStyle` shows arcs but no basemap** —
  MapLibre was not loaded, so `rdRenderDeckGL` fell through to the plain-Deck path
  (which draws no tiles). The block only takes the MapLibre-overlay path when
  `maplibregl` is defined; load `cdn.maplibre` (+ its CSS) before rendering (ADR-017).
- **Symptom: duckdb-wasm dies with a cross-origin worker error** — a CDN worker URL
  cannot go straight to `new Worker`. Wrap it in a same-origin Blob that
  `importScripts` it (`new Blob(['importScripts("'+bundle.mainWorker+'");'])`). Pin
  the **stable** duckdb version — npm `latest` is a `-dev` build. 64-bit aggregates
  return as **BigInt**; coerce to `Number` before Plotly or `toFixed` (ADR-017).
- **Symptom: dark chrome, light charts after theme toggle** — a template fork
  dropped the canvas re-feed half of the flip (ADR-004). A `deckgl` block holds a
  **WebGL context**: it must be `finalize()`d and rebuilt on flip, never re-styled.
  The MapLibre-overlay path instead holds a `maplibregl.Map`, `remove()`d on rebuild.
- **Symptom: stale content despite edits** — something is caching; confirm
  the server sends `Cache-Control: no-store` and fetches carry `?v=`.
- **Symptom: `stencil.py` slow on first call** — 6.3 MB JSON parse on first
  load; cached for the process thereafter. Don't "fix" by unzipping to disk.
- **Symptom: mermaid renders once then blanks on re-theme** — mermaid must be
  re-initialised *and* the source re-inserted before `mermaid.run` (rendered
  SVG is not re-renderable).
- **Symptom: one mermaid block shows an error/blank in the companion, the
  rest render fine** — invalid mermaid syntax in the source fence (mindmaps
  reject quoted labels, leading parens, HTML entities). Run the vendored
  parse gate on the source `.md` (ADR-007); details in
  `resources/learned/mermaid-syntax-gate.md`.

## Extension checklist

- [ ] New fenced block type: add lazy loader + renderer in **`assets/viewer.js`**,
      token sub-palette if themable, contract section in `rich-blocks.md`,
      degradation behaviour on GitHub noted in `discovery-docs.md`.
- [ ] New stencil pack: re-vendor zip per `stencil-library.md`, smoke-test
      `packs`/`extract`, update NOTICE if provenance changed.
- [ ] Any `assets/viewer.*` change: run all three block types + theme flip in a
      real browser, in **both** `--inline` and multi-file mode. `make ci` cannot
      see browser behaviour (ADR-006).
- [ ] New generation-time value: add it to `build_config()` → the `#rd-config`
      block. **Never** add a `{{...}}` placeholder to `viewer.js` (ADR-008) — a
      test will fail, and the file stops being valid JS.
- [ ] Any authored prose (showcase copy, UI/error strings, this skill's docs, an
      upgraded discovery doc) follows `resources/prose-style.md` (ADR-015): no
      em-dash, Australian English, inclusive language. User markdown is rendered
      as written, never corrected.

## Related (maintainer provenance only — never cite from runtime surfaces)

- `../mermaidjs_diagrams/` — upstream source of `vendor/mermaidjs_diagrams/`, re-vendor per ADR-007
- `.claude/rules/claude_skills/index.md` — 500-line invariant, tree structure
