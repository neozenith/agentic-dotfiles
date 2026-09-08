# Design Tokens: Tooling & File-Convention Layer

Research date 2026-08-30. Every claim carries a source URL. Confirmed absences are flagged **[NO PRIOR ART]**.

---

## 1. DTCG standards — status (headline correction)

The DTCG shipped **2025.10 on 28 Oct 2025 as its first stable release**, covering **three separate modules**: Format, Color, and **Resolver**. All three carry the identical banner: *"Final Community Group Report … published by the DTCG as a Candidate Recommendation … This specification is considered stable."*
- Index: <https://www.designtokens.org/tr/2025.10/> · Announcement: <https://www.w3.org/community/design-tokens/2025/10/28/design-tokens-specification-reaches-first-stable-version/>

**The "do-not-implement" warning is real but applies only to the *next-version preview drafts*,** not to 2025.10:
- <https://www.designtokens.org/tr/drafts/resolver/> — *"⚠️ This is a preview draft of in progress changes. Do not refer to this document directly, and do not implement anything in this document."* Same banner on <https://www.designtokens.org/tr/drafts/format/>.
- **Trap:** bare `tr.designtokens.org/format/` 301-redirects to the *draft*. Always cite the versioned path `/tr/2025.10/…`.

| Module | Status | URL |
|---|---|---|
| Format | Stable, Final CG Report, 2025.10 | <https://www.designtokens.org/tr/2025.10/format/> |
| Color | Stable, Final CG Report, 2025.10 (split out of Format) | <https://www.designtokens.org/tr/2025.10/color/> |
| Resolver | **Stable, Final CG Report, 2025.10** — adoptable today | <https://www.designtokens.org/tr/2025.10/resolver/> |

### 1.1 Format Module normative rules
- **`$type` inheritance** (§5.2.2): if unset, type = resolved type of the referenced token; else *"inherited from the closest parent group with a `$type` property"*; else the token *"MUST be considered invalid."* And: *"Tools MUST NOT attempt to guess the type of a token by inspecting the contents of its value."* — <https://www.designtokens.org/tr/2025.10/format/>
- **Aliases** (§7): two syntaxes. `{group.token}` *"always resolves to the `$value` property of the target token"* (whole values only). `$ref` JSON Pointer (RFC 6901) reaches sub-paths, e.g. `#/colors/blue/$value/components/0`. Chained aliases allowed — *"tools MUST follow each reference until they find a token with an explicit value"*; circular chains MUST NOT exist.
- **Colour `$value` is an OBJECT, not a hex string, as of 2025.10** — breaking change. Required `colorSpace` + `components` (numbers or `'none'`), optional `alpha` (0–1, default 1) and `hex` (6-digit CSS fallback). Example: `{"colorSpace":"srgb","components":[0,0.4,0.8],"hex":"#0066cc"}`. — <https://www.designtokens.org/tr/2025.10/color/>. The pre-2025.10 editor's draft required a plain hex string; the migration gap is live in real tools, e.g. <https://github.com/penpot/penpot/issues/9305>.
- **`$extensions`** (§5.2.3): *"each tool MUST use a vendor-specific key … reverse domain name notation is recommended … Tools that process design token files MUST preserve any extension data they do not themselves understand."* Also: extension data SHOULD be *"optional meta-data that is not crucial to understanding that token's value."*

### 1.2 Does the Format Module say anything about modes/themes/multi-brand?
**No — confirmed absence.** Full-text search of the stable Format Module returns **zero** occurrences of "mode", "modes", "theme", "themes", "multi-brand". The Format spec models a single context only.
- The native/inline proposal — **issue #210 "Native modes and theming support"** (opened 2023-03-22, milestone "Next Draft Priority") — is **still OPEN**: <https://github.com/design-tokens/community-group/issues/210>. On it (2025-09-02) Drew Powers routes the requirement elsewhere: *"We have added a proposal … It's called the 'Resolver module'."*
- **Conclusion:** DTCG's answer to multi-brand/multi-mode is a *sibling file*, not token syntax. This is normative-by-omission and it is the single most load-bearing finding for the on-disk decision.

### 1.3 Resolver Module — the problem shape it defines
Abstract: *"describes a method to work with design tokens in multiple contexts (such as 'light mode' and 'dark mode' color themes)."* File contract: `.resolver.json` (SHOULD), `application/json`, `version: "2025.10"`, `$schema: https://www.designtokens.org/schemas/2025.10/resolver.json`.

Vocabulary:
- **Set** — an unconditional collection; `sources` is an array of inline tokens and/or `$ref` file references, merged in array order, last-wins.
- **Modifier** — *"similar to a set, but allows for conditional inclusion via the `contexts` map."* Has `contexts` (name → source array) and optional `default`. MUST have ≥2 contexts; MAY reference a Set inside a context but **MUST NOT reference another modifier** (so the axes stay one level deep).
- **`resolutionOrder`** — root array of sets/modifiers. *"The order is significant, with tokens later in the array overriding any tokens that came before them."*
- **Input** — the caller's per-modifier context selection, e.g. `{"theme":"dark","size":"large"}`. Values MUST be strings (`true` is invalid, `"true"` is not); SHOULD be case-insensitive.
- **Permutation** — one input; total count = product of each modifier's context count (2 modifiers × 2 contexts = 4 outputs).
- **Orthogonality** (non-normative, §2.1) — whether two modifiers touch disjoint tokens; non-orthogonal modifiers make the result order-dependent.
- **Resolution is 4-staged** (§6): validate input → order/flatten (selecting only the matched context per modifier) → resolve aliases *after* flattening → emit.

```jsonc
{ "$schema": "https://www.designtokens.org/schemas/2025.10/resolver.json",
  "modifiers": { "theme": { "contexts": {
      "light": [{ "$ref": "theme/light.json" }],
      "dark":  [{ "$ref": "theme/dark.json" }],
      "darkHighContrast": [{ "$ref": "theme/dark.json" }, { "$ref": "theme/dark-high-contrast.json" }]
    }, "default": "light" } } }
```
With `resolutionOrder: [sets/size, sets/typography, modifiers/theme]`, input `{"theme":"dark"}` deterministically flattens to `size.json → typography.json → dark.json`. — <https://www.designtokens.org/tr/2025.10/resolver/>

**Takeaway on the model:** brand and mode are *modifiers* — orthogonal named axes over a shared foundation set — not nested folders and not `$extensions`. N brands × light/dark is 2 modifiers, not 2N files.

---

## 2. Style Dictionary & Tokens Studio — the de-facto conventions

### 2.1 Style Dictionary (latest **5.5.2** per `https://registry.npmjs.org/-/package/style-dictionary/dist-tags`)
Config keys: `source` (glob array), `include` (base collection), `platforms` -> per-platform `transformGroup`/`transforms`, `buildPath`, and a `files[]` array of `{destination, format, filter}`. DTCG is opt-in via `usesDtcg` (`$value`/`$type`). *"Style Dictionary uses this as a base collection of design tokens. The tokens found using the `source` attribute will overwrite tokens found using `include`."* — <https://styledictionary.com/reference/config/>

**There is NO first-class theme or mode concept.** The configuration axis is *platform*, not theme; multi-brand is a **build loop the user writes**. The official example `examples/advanced/multi-brand-multi-platform` is the canonical shape:

```
tokens/globals/**/*.json                       # shared foundation
tokens/brands/{brand-1,brand-2,brand-3}/*.json
tokens/platforms/{web,ios,android}/*.json
build.js                                       # one config per (brand, platform)
```
```js
source: [ `tokens/brands/${brand}/*.json`, 'tokens/globals/**/*.json', `tokens/platforms/${platform}/*.json` ],
// ['brand-1','brand-2','brand-3'].map(brand => ['web','ios','android'].map(platform =>
//    new StyleDictionary(getStyleDictionaryConfig(brand, platform)).buildPlatform(platform)))
```
— <https://github.com/style-dictionary/style-dictionary/tree/main/examples/advanced/multi-brand-multi-platform> (`build.js`, read verbatim). Output lands at `build/<platform>/<brand>/`. Layering is **source-array order + deep merge, last-wins** — i.e. the Resolver's `resolutionOrder` semantics, hand-rolled.

### 2.2 Tokens Studio — the most-used multi-brand convention in practice
Multi-file GitHub sync writes one JSON per token set plus two sidecar files:
```
tokens/core.json  tokens/brand-a.json  tokens/light.json  tokens/dark.json
$themes.json      $metadata.json
```
- **`$themes.json`** — an array of theme records. It *"contains metadata about which theme dimensions exist (noted by `group` property) and which variations exist within each dimension (noted by `name` property). Each variation has a `selectedTokenSets` … showing which tokensets are enabled for this theme variation."* Set states are `"source"` / `"enabled"` / `"disabled"` — `source` sets are resolvable-but-not-emitted (reference-only), `enabled` sets are emitted. — <https://github.com/tokens-studio/lion-example>
- **`$metadata.json`** — carries `tokenSetOrder`, the array fixing set precedence. — <https://github.com/tokens-studio/figma-plugin/issues/1164>
- **Theme groups = dimensions.** *"Multiple Themes can be applied at the same time to create a matrix of possible concepts that a single design element can be styled with. This is also known as multi-dimensional theming."* A `brand` group x a `mode` group is exactly the N-brands x light/dark shape. — <https://docs.tokens.studio/manage-themes/themes-overview>

```jsonc
[{ "id": "…", "name": "light", "group": "mode",
   "selectedTokenSets": { "core": "source", "brand-a": "source", "light": "enabled" } }]
```

### 2.3 Interop: `@tokens-studio/sd-transforms` (latest **2.0.3**)
First-party, maintained by Tokens Studio: custom SD transforms (math resolution, dimension/opacity, typography), a preprocessor, and composite-token expansion. **v1.0.0+ requires Style Dictionary v4.0.0+** (v0.15–0.16 targeted the v4 prereleases). — <https://github.com/tokens-studio/sd-transforms>

The canonical multi-brand loop is **`permutateThemes`**: feed it `$themes.json` and it returns *"an object with all the different permutations"* — combination name -> array of token-set filenames — which you hand to `source`/`include` (`source`-state sets become `include`, `enabled`-state sets become `source`) and build one output file per permutation. This helper is the closest thing the ecosystem has to a Resolver implementation, and it predates the spec. — <https://github.com/tokens-studio/sd-transforms>, <https://github.com/tokens-studio/lion-example>

---

## 3. Terrazzo (successor to cobalt-ui)

- Direct rename of **Cobalt / cobalt-ui** (same maintainers, not a rewrite; renamed 2024). — <https://terrazzo.app/docs/reference/about/>, <https://github.com/terrazzoapp/terrazzo/issues/201>. Migration: `tokens.config.js` → `terrazzo.config.js`, `cobalt`/`co` → `terrazzo`/`tz` (<https://terrazzo.app/docs/cli/migrating/>).
- Active: `@terrazzo/cli` **2.7.1**, published 2026-08-11 (2.4.0→2.7.1 across Jun–Aug 2026). — <https://registry.npmjs.org/@terrazzo/cli>
- Config: `defineConfig({ tokens: [...], outDir, plugins: [...], lint })`. — <https://terrazzo.app/docs/reference/config/>
- **First-party plugins (verified against `packages/`, <https://api.github.com/repos/terrazzoapp/terrazzo/contents/packages>):** `plugin-css`, `plugin-sass`, `plugin-js`, `plugin-css-in-js`, `plugin-tailwind`, `plugin-vanilla-extract`, `plugin-swift`, `plugin-token-listing`. **No `-vue` plugin; no Figma *output* plugin** (Figma is import-only).
- **Plugin hooks:** two-phase, Rollup-inspired — `transform({resolver, setTransform})` populates a queryable value DB; `build({getTransforms, outputFile})` queries and writes. **There is no `buildEnd` hook** in the current API (checked against `plugin-css/src/index.ts`). `outputFile` may be called any number of times, so **one run emits many files for many targets**. — <https://terrazzo.app/docs/reference/plugin-api/>
- **Modes:** cobalt-ui's `$extensions.mode` is **deprecated but still honoured** (auto-mapped to a synthetic `tzMode` modifier). The current documented mechanism is **DTCG resolvers** — Terrazzo consumes `.resolver.json` directly. A plugin declares a `permutations` option, each with an `input` (modifier→context) and a `prepare(contents)` wrapper — e.g. `plugin-css` emits `:root{…}` for light and `@media (prefers-color-scheme: dark){:root{…}}` for dark. Docs' best practice: **one modifier per `$type`** to avoid order-dependent merges. — <https://raw.githubusercontent.com/terrazzoapp/terrazzo/main/www/src/pages/docs/guides/resolvers.md>

**This is the most important tooling fact in the report:** Terrazzo already implements the stable Resolver spec, and its `permutations`+`prepare` shape is exactly "one source → many surface renderings."

---

## 4. Non-CSS output targets: chart / graph / diagram libraries

**[NO PRIOR ART] — confirmed absence.** No real project generates config for any of these from a DTCG / Style Dictionary / Terrazzo token source:

| Target | Finding |
|---|---|
| Vega / Vega-Lite | <https://github.com/vega/vega-themes> ships Carbon-matching themes via [`carbongen.ts`](https://github.com/vega/vega-themes/blob/main/src/carbongen.ts) — but its `TOKENS` object is **hand-transcribed hex literals**, not generated from `@carbon/themes`. |
| Chart.js | Nothing (`charts-theme-chartjs` on npm is unrelated, ~12y stale). |
| ECharts | ECharts 6.0 added its *own internal* token system (`registerTokens()`, <https://github.com/apache/echarts-theme-builder>) — token vocabulary adopted internally, not fed from an external source. |
| Plotly | Only the generic template system <https://plotly.com/python/templates/>. |
| Cytoscape.js · deck.gl · D3 · Highcharts | Nothing found. |
| draw.io | <https://github.com/ehsky/drawIo-Salesforce> claims a Salesforce-tokens basis but is **manually maintained**, no build step. |
| Mermaid | Nothing found. |
| Excalidraw | Only LLM-prompt palette files (e.g. <https://github.com/coleam00/excalidraw-diagram-skill>) — not a build pipeline. |

Directories checked: Style Dictionary's official examples list (<https://github.com/style-dictionary/style-dictionary/blob/master/docs/examples.md>) has **no** chart/diagram example; no "awesome-style-dictionary" list exists; Terrazzo's 8-plugin roster has none visualization-targeted and no community plugin directory lists one.

**These targets are trivially generatable — the gap is adoption, not format:**
- Mermaid `themeVariables` is a documented flat hex-only object (`primaryColor`, `lineColor`, …) — <https://mermaid.js.org/config/theming.html>
- Vega theme = a plain config object of mark/axis/legend defaults; 14 built-ins ship that way — <https://github.com/vega/vega-themes>
- Cytoscape.js stylesheet = an array of `{selector, style}` objects — <https://js.cytoscape.org/#style>

**Nearest real prior art (all same-vendor or bespoke, none a pipeline):**
- **IBM Carbon Charts** — first-party D3 library consuming `@carbon/themes` directly (<https://github.com/carbon-design-system/carbon-charts>, <https://www.npmjs.com/package/@carbon/themes>); still frictional (<https://github.com/carbon-design-system/carbon-charts/issues/1002>).
- **shadcn/ui + Recharts** — a bespoke 5-slot CSS-variable convention `--chart-1…--chart-5` wired into Recharts and mirrored into a Figma kit (<https://ui.shadcn.com/docs/components/base/chart>). Real and shipping, but not DTCG.
- **Recharts** itself is still *debating* token theming as an open proposal — <https://github.com/recharts/recharts/discussions/6928>.
- Adobe Spectrum (<https://github.com/adobe/spectrum-design-data>): no distinct dataviz token subset found. Shopify `@shopify/polaris-tokens` is **deprecated** (<https://github.com/Shopify/polaris-tokens>).

---

## 5. Conventions: named-profile discovery & precedence

### 5.1 The base spec
XDG Base Directory: *"The order of base directories denotes their importance; the first directory listed is the most important. When the same information is defined in multiple places the information defined relative to the more important base directory takes precedent."* `XDG_CONFIG_HOME` defaults to `$HOME/.config`, `XDG_DATA_HOME` to `$HOME/.local/share`, and `$XDG_*_HOME` is *"more important than any of the base directories defined by `$XDG_*_DIRS`"*. — <https://specifications.freedesktop.org/basedir/latest/>

### 5.2 Real tools that resolve a *named profile* across a directory ladder

| Tool | Lookup ladder (first/highest wins) | Source |
|---|---|---|
| **Ansible roles** | *"in a directory called `roles/`, relative to the playbook file"* → configured `roles_path`, default `~/.ansible/roles:/usr/share/ansible/roles:/etc/ansible/roles` → the playbook's own directory | <https://docs.ansible.com/projects/ansible/latest/playbook_guide/playbooks_reuse_roles.html> |
| **pandoc templates** | explicit relative path from cwd → *"the `templates` subdirectory of the user data directory"* (`$XDG_DATA_HOME/pandoc`) → built-in default | <https://pandoc.org/MANUAL.html> |
| **Ghostty themes** | *"the `themes` subdirectory of your Ghostty configuration directory … `$XDG_CONFIG_HOME/ghostty/themes`"* → shipped resources dir; user theme of the same name shadows the built-in | <https://ghostty.org/docs/config/reference> |
| **oclif themes** | user `theme.json` in `~/.config/<CLI>` (`%LOCALAPPDATA%\<CLI>` on Windows) overrides the CLI's shipped `theme.json`; **per-property override**, not whole-file | <https://oclif.io/docs/themes/> |
| **Codex CLI profiles** | *"Config profile files live next to `config.toml` as `$CODEX_HOME/profile-name.config.toml`; select one with `--profile profile-name`"* — user-global store only; project `.codex/config.toml` explicitly **cannot** override profile *selection* | <https://learn.chatgpt.com/docs/config-file/config-reference> |
| **delta features** | named groups `[delta "my-feature"]` selected by `delta.features`; `DELTA_FEATURES` env with a `+` prefix **composes** rather than replaces. Inherits git's cascade, so `.git/config` beats `~/.gitconfig` | <https://dandavison.github.io/delta/features-named-groups-of-settings.html> |
| **bat themes** | user themes only: `$(bat --config-dir)/themes` + `bat cache --build`; no project-local tier | <https://github.com/sharkdp/bat/blob/master/README.md> |

### 5.3 Real tools that publish a project-local → user-global *config* ladder

| Tool | Documented precedence (high → low) | Source |
|---|---|---|
| **git** | `.git/config` → `~/.gitconfig` → `/etc/gitconfig`; *"read in the order given above, with last value found taking precedence"* | <https://git-scm.com/docs/git-config> |
| **npm** | CLI flags → env → project `.npmrc` → user `$HOME/.npmrc` → global `$PREFIX/etc/npmrc` → npm builtin | <https://docs.npmjs.com/cli/v11/using-npm/config> |
| **WP-CLI** | *"1. Command-line arguments. 2. `wp-cli.local.yml` … in the current working directory (or upwards). 3. `wp-cli.yml` … (or upwards). 4. `~/.wp-cli/config.yml` … 5. WP-CLI defaults."* | <https://make.wordpress.org/cli/handbook/references/config/> |
| **mise** | `mise.local.toml` → `mise.toml` → `.config/mise.toml` → … → `~/.config/mise/config.toml` → `/etc/mise/config.toml`; *"These files recurse upwards"* | <https://mise.jdx.dev/configuration.html> |
| **EditorConfig** | walks up from the file's directory; *"stop if the root filepath is reached or an EditorConfig file with `root=true` is found"*; *"properties in closer files take precedence"* | <https://editorconfig.org/> |
| **starship** | **counter-example**: `STARSHIP_CONFIG` env → `~/.config/starship.toml`. No project-local tier at all | <https://github.com/starship/starship/blob/master/docs/config/README.md> |
| **Claude Code skills** | **inverted counter-example**: *"enterprise overrides personal, and personal overrides project"* — a `~/.claude/skills/deploy` shadows `.claude/skills/deploy` | <https://code.claude.com/docs/en/skills> |

**Synthesis of the published rules:** the overwhelming convention is *most-specific-wins* (project beats user beats system), with two design levers worth copying — EditorConfig's `root=true` **stop marker** for the upward walk, and oclif's **per-property merge** (a local profile overrides only the keys it names) versus Ghostty/pandoc's **whole-file shadow**. delta adds a third: `+`-prefixed **composition** rather than replacement.

---

## 6. Direct answers

**Q1 — Most common on-disk shape for "N brands × light/dark"?**
Two, in this order of prevalence:
1. **Tokens Studio's flat token-set files + `$themes.json` + `$metadata.json`** — by far the most-used *in practice*, because it is what Figma users' GitHub sync writes. Themes are records with `group` (the axis, e.g. `brand` / `mode`) and a `selectedTokenSets` map of `source`/`enabled`/`disabled`.
2. **Style Dictionary's directory-per-brand + build loop** — `tokens/globals/` plus `tokens/brand-a/`, `tokens/brand-b/`, with a Node script iterating brands × platforms. Style Dictionary has **no first-class theme/mode concept**; the loop is the convention.
The **standards-blessed** shape is neither: it is a `.resolver.json` with `brand` and `mode` as two orthogonal modifiers over one foundation set (<https://www.designtokens.org/tr/2025.10/resolver/>). Terrazzo implements it today; Style Dictionary does not.

**Q2 — Established convention for project-local overrides over a user-global profile store?**
**Yes, well established outside the token ecosystem, and absent inside it.**
- Outside: git / npm / WP-CLI / mise all publish the same *most-specific-wins* ladder (§5.3), and Ansible + pandoc apply it to *named artefact* lookup, not just scalar config (§5.2). The default precedence to copy is: CLI flag → project-local dir → user-global dir → shipped built-in.
- Inside the token ecosystem: **[NO PRIOR ART]**. Neither Style Dictionary nor Terrazzo has any user-global config or profile store — both are project-root-config-only (<https://styledictionary.com/reference/config/>, <https://terrazzo.app/docs/reference/config/>). Cross-project brand sharing in this ecosystem is done by **publishing a token npm package**, not by a `~/.config` store. A user-global brand-profile directory would be a genuine novelty here; the precedent to borrow is Ghostty/oclif/Ansible, not any token tool.

**Q3 — Prior art for generating chart/graph/diagram library config from design tokens?**
**[NO PRIOR ART] — confirmed negative** for Vega, Vega-Lite, Chart.js, ECharts, Plotly, Cytoscape.js, deck.gl, D3, Highcharts, draw.io, Mermaid, and Excalidraw (§4, with the searches enumerated there). The closest real things are same-vendor first-party integrations (**IBM Carbon Charts** ← `@carbon/themes`), a bespoke non-DTCG CSS-variable convention (**shadcn/ui `--chart-1…5`** → Recharts), and hand-transcribed palettes (vega-themes' Carbon variants, drawIo-Salesforce). None is automated from a token file. Recharts' own maintainers are still debating whether to support it at all.

---

## 7. Note on the existing local convention

This repo's `skills/richdocs/resources/themes/<name>/design-tokens.json` already implements a directory-per-named-profile store with a `themes.{light,dark}` axis and **per-surface sections** (`canvas`, `cytoscape.{light,dark}`, `plotly.{light,dark}`, `categoryColours`, `status`) — i.e. it independently arrived at the modifier model *and* at the chart/graph output targets that §4 shows nobody else generates. Four profiles exist: `freshgreens`, `locomotif`, `osakanights`, `v2ai`. It is project-local only; there is no user-global tier and no upward walk.
