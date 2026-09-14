# Decisions — design-token refactor

Maintainer decisions taken during the `ce-brainstorm` run started 2026-08-30.
Each entry records the choice **and the reasoning as a four-clause lens**, so a later
session can tell when the decision stopped applying.

Status of the five topics is tracked in [`README.md`](README.md). Research dossiers that
ground these decisions are in [`research/`](research/).

---

## DT-LOC-1 — the curated profile store is shared across skills

- **Status:** decided 2026-09-02 (user-directed, chosen over per-skill and hybrid stores)
- **Decision:** the two **user-curated** tiers are a single shared store that every skill
  in this family reads. `{skill_name}` does **not** appear in their paths. The
  **shipped** tiers stay inside each skill, unchanged, and remain skill-scoped by
  construction.

  ```text
  1  <project>/.design-profiles/<name>/          shared, project-local
  2  ~/.design-profiles/<name>/                  shared, user-global
  3  <project>/.{codex,claude}/skills/<skill>/resources/profile/<name>/
  4  ~/.{codex,claude}/skills/<skill>/resources/profile/<name>/
  5  <skill>/resources/themes/<name>/            shipped backstop (always terminates)
  ```

  Lookup **cascades on miss**: a named profile absent from a tier is sought in the next.
  The directory name `.design-profiles/` is provisional — the *scope* is decided, the
  spelling is not.

- **Rejected alternatives:**
  - **Per-skill stores** (`.richdocs_cache/`, `.mermaidjs-diagrams_cache/`) — simple and
    keeps each skill in its own lane, but a brand must be curated twice and kept in sync
    by hand, and the vendored `skills/richdocs/vendor/mermaidjs-diagrams/` copy has no
    defined store to read.
  - **Hybrid cascade** (per-skill tiers *then* shared tiers, 7 deep) — allows a
    skill-specific tweak to shadow a shared brand, at the cost of more locations to keep
    in sync and machinery to sync them.

- **Lens:**
  - **Given** the maintainer uses `richdocs` and `mermaidjs-diagrams` together often, and
    a curated brand profile is written rarely and then read many times,
  - **we prefer** one shared, set-and-forget profile repository **over** per-skill stores
    or a hybrid cascade,
  - **because** a single location makes sharing simpler by construction rather than by
    discipline, and removes the need for any sync machinery — which for these use cases
    is not a value add,
  - **unless** the two skills' profile schemas diverge far enough that one profile can no
    longer satisfy both, at which point the shared store stops being set-and-forget.

- **Consequences:**
  - `richdocs`' vendored mermaid toolchain resolves to the same store as its host —
    the ambiguity that per-skill stores left open does not arise.
  - One profile must satisfy **both** skills' needs, so the schema is a superset; a
    surface that does not use a group ignores it.
  - Curation (topic 4) is **one act**, not one per skill.
  - Ripple (topic 5) generates **one** artifact covering every surface, not one per skill.
  - ADR-009's no-symlink portability contract is untouched — it binds tier 5 only.
  - `richdocs` ADR-018's two-root search (`tmp/richdocs/theme/` → built-in) is superseded
    by the five-tier cascade above; its *lens* (an optional additive override dir resolved
    by precedence, degrading to fully self-contained when absent) is preserved and
    extended.

### Derived rule — one resolver, used twice

Applied as a pragmatic default under DT-LOC-1's lens, not separately asked:
`.default-profile` resolves its named profile through **the same cascade** as an explicit
`--theme`. There is one lookup function; the default path and the explicit path differ
only in where the name comes from. A `.default-profile` naming a profile that resolves in
a later tier is a hit, not an error; a name that resolves nowhere fails loudly.

---

## DT-PIPE-1 — three artifacts, two transforms; only DTCG is read at runtime

- **Status:** stated by the maintainer 2026-09-02 and confirmed on playback. This is the
  maintainer's own model, not an agent proposal.
- **Supersedes:** the framing of DT-OVR-1, which was withdrawn. There is no patch layer
  and no fork command; override is a position in this pipeline, not a separate mechanism.

### The pipeline

```text
  SEED                    IR                        DTCG JSON
  ────                    ──                        ─────────
  very small set     ──▶  complete spec        ──▶  the only artifact
  primary + secondary     every permutation:        skills read at
  accent, plus a few      golden walk,              runtime
  more (not locked)       cytoscape, deck.gl,
                          drawio, light/dark
       │                       │                         │
   scrapeable              hand-editable            hand-editable
   from a website          iterate here             fine-tune here
                                │                         │
                        curation script            build / templating
                        maximises WCAG + CVD       script
                        pragmatically
```

### The rules

1. **Only the final DTCG JSON is read at runtime.** Skills never see the seed or the IR.
2. **DTCG is fully regenerable from a valid IR.** The IR is what the user keeps and
   iterates on, project-local or user-global.
3. **A valid DTCG carries values for every permutation.** No gaps, nothing computed at
   load.
4. **WCAG and CVD checks do not run when loading a DTCG.** Editing it is a hard choice
   the user made; the system does not second-guess it.
5. **The gates run at curation time instead** — seed → IR maximises WCAG and CVD to a
   *pragmatic*, not necessarily optimum, level.
6. **The seed exists to make scraping useful.** Grab a brand's colours from their
   website, extrapolate to a full IR. Candidate seed attributes are drawn from
   `diagram-design`'s semantic roles; the exact set is **not locked yet**.
7. **Both the IR and the DTCG are hand-editable.** Editing either is legitimate — the IR
   regenerates, the DTCG does not.

### Consequences

- **Topic 3 (override) is closed.** Override *is* editing your IR and rebuilding, or
  editing the DTCG directly. "Eject" has a precise meaning: eject from the seed by
  editing the IR; eject from the IR by editing the DTCG.
- **The gates become generative, not policing** — consistent with the maintainer's
  standing ruling that rules impute what a pack does not state and never police what it
  does. Imputation happens in curation; after that the values are stated, and stated
  values are final.
- **`themecheck.py`'s pack-validity role moves to curation.** ADR-016's per-theme
  `waivers.seriesContrast` mechanism becomes unnecessary — nothing gates the thing a
  waiver was written to excuse.
- **Neither skill needs a shared gate**, which sidesteps `skills/CLAUDE.md`
  self-containment entirely: each skill reads a complete DTCG file. The complexity lives
  in a curation tool, not in either skill.

### Open, explicitly not decided

Both items below have moved on since this entry was written; see
[`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) for their live state.

- **Seed contents** — the role vocabulary is now locked by DT-ROLES-1, and the neutral and accent
  parameters by DT-REF-1 and DT-ACCENT-1. What *else* the seed carries is still deliberately small
  and unlocked.
- **Render-time contrast gates** — `scripts/mermaid_contrast.ts` must survive; where it fires is
  Q8.

---

## DT-BUILD-1 — curation bakes every surface into the IR; build only serialises

- **Status:** decided 2026-09-02 (user-directed, chosen over build-time expansion and
  load-time skill mapping)
- **Decision:** curation produces a **semantically complete `ir.json`** — every surface
  present: golden-walk categorical colours, cytoscape, plotly, deck.gl, draw.io, mermaid,
  light and dark. The build step is a pure transform: IR → DTCG, adding no design
  knowledge. Per-surface tuning happens by editing the IR, which is the durable editing
  surface.

- **The seed is optional.** `seed.json` is an on-ramp — it exists so a scraped brand can
  be extrapolated into a full IR. A hand-authored `ir.json` with no seed at all is a
  first-class, fully valid profile. The **IR is the root of the system**, not the seed.

  ```text
  ~/.design-profiles/<name>/
    seed.json            OPTIONAL — the scrape on-ramp
    ir.json              the root artifact; semantically complete; hand-editable
    design-tokens.json   DTCG; built from ir.json; the only file skills read
  ```

- **Rejected alternatives:**
  - **Build expands per-surface** (IR holds roles + walk params only) — a new surface
    would be free for every profile, but per-surface tuning would have to happen in the
    DTCG, the one file a rebuild overwrites. Contradicts iterating on the IR.
  - **Each skill maps roles at load** (industry norm, Style Dictionary platforms) —
    breaks DT-PIPE-1 rule 3, reintroduces load-time computation, and duplicates mapping
    logic across two self-contained skills.

- **Lens:**
  - **Given** the maintainer iterates on a profile by hand over time, and a profile's
    value is that every surface it paints stays consistent,
  - **we prefer** a semantically complete IR that curation fills and build merely
    serialises, **over** an IR of parameters expanded at build time,
  - **because** it makes the file the user edits the same file that holds every value
    they might want to change — tuning is direct, and nothing they tune is overwritten by
    a rebuild,
  - **unless** curation stops being additive-only, at which point re-running it would
    destroy the hand edits that are the whole point of the IR.

- **Consequences:**
  - **Curation must be idempotent and additive** — it imputes what is absent and never
    overwrites what is stated. This is the maintainer's standing ruling #2, now
    load-bearing rather than advisory. A new surface is added by re-running curation on
    an existing IR: the absent group is imputed, the stated groups are untouched.
  - **The build step holds no design knowledge.** It converts a compact hand-editable
    shape into the spec-conformant DTCG serialisation and validates completeness.
  - "A valid profile" means a valid **IR**; a valid DTCG is what falls out of it.
  - `mermaid_contrast.ts` has mermaid values to check in both the IR and the DTCG —
    placement is still open, but not for lack of a checkable surface.

---

## DT-NEUTRAL-1 — neutrals are pure greys stated as lightness

> **Superseded in part by DT-REF-1**, which moves the colour space to OKLCH and re-anchors the
> bases. The chroma-0 / hue-0 ruling and the fixed-increment model below still stand; the HSL
> percentages quoted in this entry do not. Read DT-REF-1 for the live values.

- **Status:** stated by the maintainer 2026-09-02, corrected the same day
- **Decision:** neutrals lock **hue 0 and saturation 0** — pure greys, not hue-tinted.
  Roles are stated as HSL lightness percentages. The step size (5%) may be exposed as an
  optional `seed.json` parameter.

  ```text
  role          dark    light
  bg-dark         0%     100%
  bg              5%      95%
  bg-light       10%      90%
  text-muted     70%      30%
  text           95%       5%
  ```

- **Supersedes** two earlier drafts: `CURATION.md` stage 1's hue-tinted warm neutral (the
  agent's guess, following `diagram-design`; not the maintainer's model), and an earlier
  transcription of this ramp as 5/10/15 + 85/90/95, which the maintainer corrected.

- **Verified** by `tmp/check_neutral_ramp.py`:
  - Every stated pairing reaches **AAA (7:1)** except one — `text-muted` on `bg-light` in
    **light** mode, at 6.80:1 (AA only). Dark mode's same pairing is 8.30:1.
  - **The light/dark mirror is NOT contrast-exact.** Only `bg × text` matches (17.43:1
    both ways, because it is the same two values swapped). Every pairing involving the
    interior value differs: `bg × text-muted` is 9.23:1 dark but 7.63:1 light. Relative
    luminance is not symmetric under `L → 100−L` — sRGB's transfer function means a given
    lightness step near black moves far less luminance than the same step near white.
    **Light mode is systematically weaker under a lightness mirror.**
  - The 60-point gap between `bg-light` and `text-muted` has **ample room for a border**
    at 3:1 — dark needs 35–40%, light needs 51–58%, all inside the gap.
  - `text-muted` is conservative: AAA needs only 59–65% in dark mode against the stated
    70%, so there is headroom to go softer.

  *(An earlier claim in this session that "the mirror is exact" was wrong; it was measured
  on the superseded ramp, where every tested pair was the same two numbers swapped.)*

## DT-CVD-1 — CVD safety is low priority

- **Status:** stated by the maintainer 2026-09-02
- **Decision:** colour-vision-deficiency safety is **important but a very low priority**,
  and is not to be raised again as an objection to a design choice.
- **Consequence:** the research finding that a fixed-lightness hue ring cannot be CVD-safe
  is recorded in `CURATION.md` stage 4 as context, not as a constraint. CVD scoring may
  inform curation's ordering step, but never blocks a palette or reopens a decision.

---

## DT-REF-1 — the neutral ramp is one reference plus parameterised offsets, in OKLCH

- **Status:** decided 2026-09-03 (user-directed, chosen after seeing all three rendered)
- **Colour space:** **OKLCH**, not HSL. Neutrals are chroma 0, hue 0 — pure greys. For an
  achromatic colour the OKLab transform collapses to `L = cbrt(Y)`, so relative luminance
  is exactly `Y = L³` and WCAG contrast is closed-form without a colour library.

### The parameters

Every value below is a **`seed.json` input with the stated default**. Specifying nothing
yields the full ramp; specifying one value shifts everything relative to it.

| Parameter | Default | What it does |
|---|---|---|
| `L-dark-bg` | **0.15** | the dark mode reference |
| `L-light-bg` | **0.90** | the light mode reference |
| `offset.bg-dark` | **−0.05** | absolute lightness; darker surface in *both* modes |
| `offset.bg-light` | **+0.05** | absolute lightness; lighter surface in *both* modes |
| `offset.text-muted` | **+0.65** | measured *toward the text end*, so mode-independent |
| `offset.text` | **+0.90** | measured *toward the text end*, so mode-independent |

Two kinds of offset, and the distinction is load-bearing: **absolute** offsets keep their
direction in absolute lightness (`bg-dark` is darker in both modes), while **toward-text**
offsets flip direction with the mode, which is what makes one number serve both.

### What it resolves to

```text
role          dark L       hex   | light L       hex
bg-dark         0.10   #030303   |    0.85   #cecece
bg              0.15   #0b0b0b   |    0.90   #dedede
bg-light        0.20   #161616   |    0.95   #eeeeee
text-muted      0.80   #bebebe   |    0.25   #222222
text            1.00   #ffffff   |    0.00   #000000
```

- **Every pairing is AAA** (worst 9.69:1). Verified in `tmp/verify_chosen_ref.py`.
- Both bg triples are clearly separated — dark 8-bit `[3, 11, 22]` (gaps 8, 11), light
  `[206, 222, 238]` (gaps 16, 16).
- Dark `text` clamps to 1.00 and light `text` to 0.00; both modes reach the extreme.
- Worst dark/light contrast divergence is 7.31, which is accepted: every pairing clears
  AAA regardless, so parity was not worth optimising for.

### Rejected alternatives

- **Dark `bg` at 0.05** (the originally stated value, carried over from an HSL sketch) —
  `Y = 0.000125` becomes sRGB channel 0.41, which rounds to **0**, so `bg-dark` and `bg`
  both render `#000000`. Three specified dark surfaces collapse to one visible colour.
  This is the HSL→OKLCH trap: HSL 5% grey is roughly **OKLCH 0.16**, so the increments
  carry over but the base cannot.
- **Symmetric mirror** (dark 0.15 / light 0.85) — one number generates both modes, but
  light mode's lightest surface is `#dedede`, reading as grey paper rather than a page,
  and it measured the worst divergence at 9.35.

### Lens

- **Given** OKLCH is perceptually uniform but sRGB's 8-bit grid is not, and the dark and
  light ends of the gamut have genuinely different usable range,
- **we prefer** two independently stated references with shared relative offsets, **over**
  a single reference plus a mirror rule,
- **because** paying one extra number buys three visible dark surfaces *and* keeps light
  mode near enough to white to leave headroom above `bg-light` for a bright-white border,
- **unless** the target medium is not 8-bit sRGB, at which point the dark-end collapse
  that forced the asymmetry no longer applies.

### Consequences

- **The seed carries parameters, not just colours.** `seed.json` is a set of knobs with
  sane defaults, which is the maintainer's stated aim: specify little, gain a lot.
- The same pattern — one reference plus parameterised, defaulted offsets — is the template
  for the remaining stages.
- Light `bg-light` at `#eeeeee` leaves exactly `0.05 L` of headroom to pure white, kept
  deliberately for top-border highlights.
- A 3:1 border role still has no name. Measured positions: dark `L 0.47–0.50`
  (`#5b5b5b`–`#636363`), light `L 0.55–0.63` (`#717171`–`#898989`).

---

## DT-ROLES-1 — semantic role names follow Atlassian's grammar

- **Status:** decided 2026-09-09 (user-directed, chosen over `richdocs`' `bg`/`fg`/`surface` and
  `diagram-design`'s `paper`/`ink`/`paper-2`, both of which the maintainer rejected)
- **Decision:** adopt **Atlassian Design System's** token grammar and role vocabulary as the
  canonical semantic layer. Neither existing skill's naming survives; both migrate to this.

### The grammar

Three slots — **foundation · property · modifier** — verbatim from
[Atlassian's spec](https://atlassian.design/foundations/tokens/design-tokens):

> **Foundation**: the type of visual design attribute — `color`, `elevation`, `space`.
> **Property**: the UI element the token applies to — `border`, `background`, `text`.
> **Modifier**: additional detail — colour role, emphasis level, interaction state.
> *"Not every token has a modifier. For example, `color.text` is our default body text color."*

Emphasis ladders `subtlest → subtle → (default) → bold → boldest`.

### The locked role names

| Job | Canonical name | was (`richdocs`) | was (`diagram-design`) |
|---|---|---|---|
| recessed ground | `color.surface.sunken` | — | — |
| page ground | `color.surface` | `bg` | `paper` |
| raised ground | `color.surface.raised` | `surface` | `paper-2` |
| primary text | `color.text` | `fg` | `ink` |
| secondary text | `color.text.subtle` | `muted` | `muted` |
| tertiary text | `color.text.subtlest` | — | `soft` |
| text on a focal fill | `color.text.inverse` | `onAccent` | — |
| hairline border | `color.border` | `border` | `rule` |
| strong border | `color.border.bold` | — | `rule-solid` |
| focal fill | `color.background.brand.bold` | `accent` | — |
| focal tint | `color.background.brand.subtlest` | — | `accent-tint` |
| focal stroke | `color.border.brand` | — | `accent` |
| link | `color.link` | `link` | `link` |
| categorical channel | `color.chart.categorical.<N>` | `categoryColours` | `series-<N>` |
| status | `color.text.danger` / `.warning` / `.success` | `status.*` | — |

Verified against the shipped artifact
[`@atlaskit/tokens@16.10.0` `atlassian-light.js`](https://cdn.jsdelivr.net/npm/@atlaskit/tokens@16.10.0/dist/cjs/artifacts/themes/atlassian-light.js):
`--ds-surface{,-sunken,-raised,-overlay,-container}`, `--ds-text{,-subtle,-subtlest,-inverse}`,
`--ds-border{,-bold,-focused,-input}`, `--ds-link{,-visited}`,
`--ds-background-brand-{subtlest,bold,boldest}`, `--ds-chart-categorical-1…8`.

### Rejected alternatives

- **`richdocs`' current names** (`bg`/`fg`/`surface`/`muted`/`onAccent`) — 8 colour roles, missing
  a third text tier, a second border tier and a focal tint; `link` duplicates `accent`'s hex.
- **`diagram-design`'s names** (`paper`/`paper-2`/`ink`/`soft`/`rule`/`rule-solid`/`accent-tint`) —
  10 roles, but no name for text sitting on a focal fill, and only two grounds.
- **GitHub Primer's grammar** (`fgColor-default`/`bgColor-accent-emphasis`) — the closest
  competitor and a genuinely published grammar, but its variant vocabulary is closed at three
  (`default`/`muted`/`emphasis`) and it **deprecated `subtle` in favour of `muted`** to shrink
  variant count, so the third text tier has no home.
- **DTCG** — defines **no** role vocabulary at all; it is a format spec (`$type`, `$value`,
  aliases, `$extensions`) plus the Resolver's own nouns. No prior art to inherit.
- **Tailwind v4** — ships **no** semantic layer; grepping its `theme.css` for
  `primary|secondary|accent|brand` returns zero matches. The primary/secondary framing is
  entirely downstream (shadcn, daisyUI, Preline).

### Lens

- **Given** two in-house vocabularies that overlap on six roles and disagree on what `accent`
  means, and an industry where only Atlassian and Polaris publish a complete grammar,
- **we prefer** Atlassian's `foundation · property · modifier` grammar **over** either in-house
  set or Primer's `<element>Color-<variant>` form,
- **because** it is the only surveyed vocabulary that already carries three text tiers, two
  border tiers, a three-deep surface stack, *and* a published separation between a singular
  `brand` hue and a meaningless-by-design `accent` palette — which is precisely this system's
  accent-versus-categorical split,
- **unless** Atlassian deprecates the ladder wholesale, in which case the grammar still stands
  and only the modifier words move.

### Consequences

- **`accent` is retired as a role name.** It named three different jobs across the two skills:
  richdocs' fill (`background.brand.bold`), diagram-design's stroke (`border.brand`), and its
  tint (`background.brand.subtlest`). The collision is now impossible to write.
- **`link` becomes a documented alias of the brand hue**, not an independent role — Primer makes
  this explicit, and `osakanights` already ships both as the same hex (`#5c4295` / `#c3b0fd`).
- **DTCG forbids a group from carrying a value**, so Atlassian's bare `--ds-text` serialises as
  `color.text.default` in nested DTCG — `text` must be a group to hold `subtle`. Flattened CSS
  output restores the bare name.
- The three grounds map straight onto DT-REF-1: `surface.sunken` / `surface` / `surface.raised`
  are `bg-dark` / `bg` / `bg-light`. `text` and `text.subtle` are the two stated foreground
  offsets; `text.subtlest` is a third offset still to be set.
- **`color.border` has no value yet** — measured at `L 0.47–0.50` dark, `L 0.55–0.63` light for
  3:1. `color.border.bold` is a second, stronger step above it.
- Both skills' existing packs need a rename migration; `richdocs` ADR-004's two-palette split
  (chrome CSS vars + canvas JS palette) is unaffected — only the keys change.

---

## DT-ACCENT-1 — one required brand hue; a second is imputed as walk slot 1 and overridable

- **Status:** decided 2026-09-09. The requirement (optional override of an imputed default) is
  the maintainer's; the imputation rule is the agent's, drawn from research and accepted.
- **Decision:** `seed.json` requires **one** brand hue. A second is **imputed, never demanded** —
  and because DT-ROLES-1 leaves no `secondary` role, it has exactly one home:
  **`color.chart.categorical.1`**, imputed at `primary + 137.5°`.

  A stated seed value **overrides that slot**, letting a brand that genuinely owns two colours
  place its second one without inventing anything. This is mermaid's own mechanism:

  ```js
  // vendored mermaid, verified in skills/richdocs/vendor/…/mermaid.esm.min
  this.secondaryColor = this.secondaryColor || adjust(this.primaryColor, {h: -120})
  this.cScale1        = this.cScale1        || this.secondaryColor
  ```

- **Why a stated second hue is safe here:** it lands in a **categorical** slot, not a second
  focal role. `color.background.brand.*` stays singular, so the focal signal cannot be split.

- **Rejected alternatives:**
  - **Two required accents** — the shape *no* surveyed system uses. Most scraped brands yield
    only one colour, so the seed would routinely be invalid.
  - **A separate `secondary` role imputed at `hue + 60°` (M3's tertiary)** — the only second-hue
    offset shipped as a default by a major system, but Google never published why 60, and
    DT-ROLES-1 gives it nowhere to live.
  - **`+180°` (complementary) or `+120°` (triad)** — measured *less* harmonious than random hue
    pairs when tested in CIE LCh (Tan, Echevarria & Gingold, IEEE TVCG 2025: complementary
    40.7–44.2%, triad 40.5–44%, both losing to a randomised control).

- **What the research established** (`research/research-secondary-accent.md`,
  `research-accent-derivation.md`, `research-accent-in-dataviz.md`):
  - "Primary + secondary accent" traces to **Bootstrap's `$secondary`, which is `$gray-600`** —
    a grey. In 5.3 `--bs-secondary-color` absorbed the deprecated `.text-muted`. Downstream
    copied the names and kept the greys: shadcn's entire default palette is chroma 0.
  - **Nine of ten surveyed systems ship exactly one accent hue.** Polaris ships none; Spectrum 2
    *removed* accent to reserve it; Atlassian states *"Avoid mixing different accent colors."*
  - **M3's `secondary` is the same hue at lower chroma** (C16 vs primary's C36) — a desaturated
    primary, not a second colour. It is a different *hue* in only 2 of 9 variants.
  - Neither **DTCG** nor **Tailwind** offers prior art: DTCG defines no role vocabulary at all,
    and Tailwind ships no semantic layer (`primary|secondary|accent|brand` returns zero matches
    in its `theme.css`).

- **Lens:**
  - **Given** the evidence that a second brand hue is folklore rather than a load-bearing role,
    and that some brands nonetheless genuinely own two colours,
  - **we prefer** imputing the second hue into a categorical slot with a stated override
    **over** requiring it, omitting it entirely, or giving it its own role,
  - **because** it costs nothing when a brand has one colour, gives a two-colour brand a real
    place to put its second, and keeps the focal signal singular by construction,
  - **unless** a use case appears that needs two *simultaneous* focal roles, which no surveyed
    system supports and which would reopen DT-ROLES-1 rather than this decision.

- **Consequence:** resolves `CURATION.md`'s "[OPEN] one walk or two?" to **one**.

## DT-WALK-1 — the categorical walk ships 12 pre-computed slots

- **Status:** decided 2026-09-09 (user-directed)
- **Decision:** the golden-angle walk computes and ships **12 slots**, `color.chart.categorical.1`
  through `.12`. All are present in every IR and DTCG whether or not a given document uses them.
  Pre-computed, not lazily derived — consistent with DT-PIPE-1 rule 3.

- **Verified free** by `tmp/walk_12.py`, seeded on `osakanights`' light accent `#5c4295`
  (`L 0.4498  C 0.1312  H 295.04°`):
  - The chroma-binding hue is **210.04° at slot 2**, `maxC 0.0779` — already inside the first
    seven slots. `min` over 7 slots and over 12 slots are **identical**, so extending to 12
    costs nothing in gamut.
  - Effective chroma for the whole walk is `0.0779` — **59.4%** of the seed's chroma, the price
    of holding chroma constant across every hue.
  - Adjacency at 12 slots is uneven: smallest gap **20.00°**, largest **52.50°**, against
    `30.00°` for even spacing.

- **Context, not a constraint:** research puts the distinguishable ceiling around 7 (Healey:
  "seven isoluminant colours is the maximum") and the hard cap around 12 (Ware: "between six and
  twelve"; ColorBrewer caps at 12). Shipping 12 makes them **available**, and says nothing about
  how many a document should use. Per DT-CVD-1, CVD does not gate this.

- **Lens:**
  - **Given** the walk is deterministic and its gamut cost is set by the single worst hue, which
    already falls inside the first seven slots,
  - **we prefer** pre-computing all 12 **over** shipping 7 and deriving more on demand,
  - **because** the extra five are free, and a complete DTCG cannot leave values to be computed
    at load,
  - **unless** the chroma model changes to per-slot maximum, at which case slot count and
    saturation stop being independent.

- **Resolved by DT-WALK-2:** chroma is one rule with a ceiling, defaulting to one uniform chroma
  (`walk.chromaCeiling: "floor"`), and lightness is solved per slot and mode.

---

## DT-BORDER-1 — `color.border` is a translucent text tint; `color.border.bold` is opaque and solved

- **Status:** decided 2026-09-15 (user-directed, option B, chosen after seeing both options rendered
  on the locked ramp in `Q9-borders`)
- **Decision:** the two border roles do **different jobs**, and each gets the mechanism that suits
  its job.

| Role | Job | Mechanism | Default |
|---|---|---|---|
| `color.border` | decorative divider: table rules, card edges | the mode's `color.text` at a fixed **alpha**, composited over whatever ground it sits on | `alpha.border` = **0.14** |
| `color.border.bold` | functional boundary: an input's edge, a focusable outline | **opaque** grey, solved as the nearest lightness reaching 3:1 against *every* ground | `offset.border.bold` = **0.35** toward text |

Both defaults are `seed.json` parameters, following the DT-REF-1 pattern.

### What it resolves to

```text
color.border        dark   #ffffff at 14%  ->  #262626 / #2d2d2d / #373737   1.36 / 1.43 / 1.52 : 1
                    light  #000000 at 14%  ->  #b1b1b1 / #bfbfbf / #cdcdcd   1.36 / 1.37 / 1.37 : 1
color.border.bold   dark   L 0.50  #636363   3.43 / 3.28 / 3.01 : 1   hardest ground: surface.raised
                    light  L 0.55  #717171   3.10 / 3.63 / 4.21 : 1   hardest ground: surface.sunken
                    (ratios listed on surface.sunken / surface / surface.raised)
```

Reproduce with `scripts/build_q9_doc.py`.

### The two findings that framed it

- **The two roles are not a weak and a strong version of one thing.** WCAG 2.2 SC 1.4.11 requires
  3:1 only for boundaries *needed to identify* a component or state; decorative dividers are exempt.
  Atlassian's shipped tokens split exactly here: `--ds-border` is `#0B120E24` (near-black at 14%,
  **1.35:1** on its white surface) while `--ds-border-bold` is opaque `#7D818A` (**3.90:1**).
  An earlier framing in `OPEN-QUESTIONS.md` put the 3:1 target on `color.border`; that was wrong,
  and a 3:1 divider would be a visible grey rule on every row.
- **The hardest ground for `border.bold` differs by mode** — `surface.raised` in dark,
  `surface.sunken` in light — which is why both modes land on the **same 0.35 offset**. An earlier
  estimate of `+0.35` dark / `−0.27` light assumed `raised` was hardest in both.

### Rejected alternative

- **Opaque `color.border`**, one grey matched to option B on `surface` — its contrast spread across
  the three grounds is **0.42** (1.17–1.58:1) against the tint's **0.16**. In light mode it nearly
  disappears on `surface.sunken` at 1.17:1. Staying consistent would need one border per ground.

### Lens

Maintainer, verbatim: *"I liked option B because we could derive it RELATIVE to text and it
looked the nicer of the 2 options."*

- **Given** the neutral ramp is built as one reference plus relative derivations (DT-REF-1), and
  dividers sit on three grounds with no contrast floor,
- **we prefer** a translucent tint of `color.text` **over** an opaque grey,
- **because** it is **derived relative to text** rather than being another independently picked
  value, which keeps the ramp's "specify little, derive the rest" shape; and rendered side by side
  it **looked the nicer of the two**. The measurements agree: one token keeps nearly the same
  relationship to every ground (spread 0.16 vs 0.42),
- **unless** a render surface cannot composite alpha, in which case that surface needs a baked opaque
  fallback per ground.

### Consequences

- `color.border` is the first role whose rendered colour depends on its ground. It is still a
  **stated** value, so DT-PIPE-1's "nothing computed at load" holds: compositing happens at paint.
- The IR cannot state `color.border`'s contrast in isolation. Curation can report it per ground.
- **Surface support for alpha must be verified** before stage 6 is final: cytoscape and deck.gl accept
  it; mermaid `themeVariables` and draw.io are unverified. Logged in `OPEN-QUESTIONS.md`.
- `color.border.brand` (DT-ROLES-1) is unaffected; its value belongs with the brand roles (Q3).

---

## DT-CAT-1 — categorical classes are sequentially assigned categorical slots. Nothing else.

- **Status:** decided, and **not open to re-asking**. Stated by the maintainer 2026-09-15 after the
  question was raised again despite being settled across many prior sessions:

  > *"CATEGORICAL CLASSES like storage, network, compute... should be treated like Apples,
  > Mandarins, Peaches, Pears. They are categorical things and they get SEQUENTIALLY ASSIGNED FROM
  > THE CATEGORICAL CLASSES. THE WHOLE POINT IS VISUAL COLOUR SEPARATION. NOTHING ELSE."*

- **Decision:** any categorical class — infrastructure kinds (`Storage`, `Compute`, `Network`,
  `Database`, `Security` …) or diagram node kinds (`Input`, `Process`, `Output` …) — takes its colour
  by **sequential assignment** from `color.chart.categorical.<N>`. The only purpose is visual colour
  separation between classes.

- **There is no `color.diagram.<class>` role.** Never is, never will be. Classes get no named roles,
  no per-class hue, no aliases, and no "meaning" or "colourability" analysis.

- **Supersedes** `skills/mermaidjs-diagrams/resources/color_theming.md`'s fixed per-role hue
  families (Input blue 217°, Process violet 271°, Storage amber 38° …) and `richdocs`'
  name-keyed `categoryColours` map (`Compute`, `Storage`, `Database` …). Both become sequential
  assignment in the migration.

- **Standing rule for every future session:** do not raise, frame, or offer options about how
  categorical classes get their colour. If a document or question carries that framing, close it by
  citing this entry. Status colours (DT-ROLES-1's `color.text.danger` / `.warning` / `.success`) are
  a separate, already-locked channel and are not a reason to reopen this.

- **Lens:**
  - **Given** categorical classes are nominal, with no inherent order or colour,
  - **we prefer** sequential assignment from the categorical channel **over** any per-class naming
    or hue binding,
  - **because** the categorical channel exists to separate categories visually, and that is the
    whole job,
  - **unless** never; unconditional.

---

## DT-CONTRAST-1 — defaults must maximise text contrast; a user's stated deviation is a choice, never a failure

- **Status:** decided 2026-09-15 (user-directed). Closes Q8 and Q7.
- **The maintainer, verbatim:**

  > *"The most important thing to check is text on a background colour. All of our defaults when I
  > specify only a Hue in the seeds and leave everything else default, then it should maximise the
  > contrast. IF ANY OTHER SEED PARAMETER IS SPECIFIED THAT THEN CONTRADICTS the WCAG contrast
  > ratios, it becomes a CHOICE by the user. It is an informational warning at best but they have
  > chosen to ignore the WCAG contrast ratios BY CHOICE and that is their artistic license and we
  > will NEVER flag the WCAG contrast as a failure after that."*

### The rule

| What was stated in the seed | A WCAG contrast miss is… | Reported as |
|---|---|---|
| Only a hue; every other parameter defaulted | a **defect in our defaults** | a failure of curation, to be fixed in the defaults |
| Any other parameter that causes the miss | the **user's deliberate choice** | informational only, **never** a failure |

- **What is checked:** **text on a background colour** is the pairing that matters. Every text role
  against every ground or fill it can sit on (`color.text*` on `color.surface*`,
  `color.text.inverse` on `color.background.brand.bold`, text on categorical fills).
- **The default path must maximise contrast.** A hue-only seed is the guarantee: every text pairing
  the defaults produce clears WCAG.
- **After any stated deviation, the system never fails on contrast.** The user has exercised artistic
  licence. At most, curation tells them which pairings dropped below which threshold.

### Where `mermaid_contrast.ts` fits

It keeps its job, checking **text on a background colour** in a finished diagram. Its **severity**
follows the table above: a miss caused only by defaults is a failure, and a miss caused by a stated
parameter is informational.

### Lens

- **Given** defaults are the system's promise and every stated parameter is the user's own decision,
- **we prefer** guaranteeing contrast on the default path and treating stated deviations as
  information **over** gating every profile on WCAG,
- **because** a user who changes a colour has made a deliberate artistic choice, and failing their
  work for it would police a value they stated,
- **unless** never; unconditional. This restates DT-PIPE-1's standing rule — a stated value is final;
  rules impute, never police — for contrast specifically.

### Consequences

- **DT-PROV-1 now has a hard requirement.** Telling "defect in our defaults" from "user's choice"
  requires knowing whether each value was **imputed or stated**. The report is only correct if
  provenance is tracked.
- ADR-016's per-theme `waivers` mechanism is fully redundant: a stated deviation needs no waiver,
  because it never fails.
- **Closes Q7, the "pragmatic" stopping rule.** DT-PIPE-1 rule 5's *"pragmatic, not necessarily
  optimum"* now has a definition. **Imputed values** are pushed until every text-on-background
  pairing passes, and "maximise" means clearing the target within each role's own tier, so
  `color.text.subtle` stays distinct from `color.text` rather than being driven to the same
  extreme. **Stated values** are never pushed toward any threshold. There is no iteration budget
  or fixed floor to choose, because the DT-REF-1 defaults already clear AAA (worst 9.69:1).

---

## DT-WALK-2 — walk lightness is solved; chroma is one rule with a ceiling, defaulting to uniform

- **Status:** decided 2026-09-15 (user-directed, after comparing options A–E rendered with OKLCH
  scenes). Closes Q11 and Q3.

### The maintainer's reasoning, verbatim

> *"I want the lightness to be solved for by default and not stated."*
>
> *"I can see how Option C would shrink all colours to fit the circle evenly inside the perceptible
> region. This is at the cost of not being true to the original accent. Option D adjusts the
> lightness and almost over saturates. Option E tries to derive the lightness whilst staying true to
> the original colour wheel as close as possible."*
>
> *"I prefer C since it has a much more uniform appearance and no categorical colour on the walk is
> competing. I feel like there is some seed parameter that should be set to allow the option for
> option E though."*

### Lightness: solved per slot, per mode

Each slot's lightness is **solved**, never stated: the value nearest the seed's lightness that keeps
the slot at **3:1 against every ground** of the mode (WCAG 2.2 SC 1.4.11). On `osakanights` the solve
moves dark-mode lightness by at most 0.05 and leaves light mode unchanged.

A stated lightness was rejected: the seed's lightness (0.45) puts all 12 dark-mode bars under 3:1, and
a hue-only seed is exactly the default path DT-CONTRAST-1 says must maximise.

### Chroma: one rule, one parameter

```text
chroma(slot) = min( max in-gamut chroma at that slot's lightness and hue,  walk.chromaCeiling )
```

| `walk.chromaCeiling` | Behaviour | Was option |
|---|---|---|
| **`"floor"`** (default) | the walk's gamut floor, the lowest maximum across all 12 hues, so every slot takes the **same** chroma | **C** |
| `"seed"` | the seed accent's chroma, so each hue reaches its own maximum but never exceeds the brand | E |
| a number | an explicit ceiling; a high enough value is uncapped | D, as a limit |

`tmp/probe_chroma_ceiling.py` confirms the single rule reproduces C, E and D **exactly** (worst
difference 0.00000 in both modes). This is the seed parameter the maintainer anticipated for E.

Measured on `osakanights` (`scripts/build_q11_q3_doc.py`), dark / light:

| Ceiling | Weakest bar | Bars under 3:1 | Chroma kept | Closest pair ΔE_OK |
|---|---|---|---|---|
| `"floor"` (C, default) | 3.00 / 4.54 | 0 | 65% / 59% | 0.030 / 0.027 |
| `"seed"` (E) | 3.01 / 4.52 | 0 | 89% / 85% | 0.035 / 0.031 |

Every ceiling clears 3:1 on every ground because lightness is solved in all of them, so choosing a
ceiling never costs contrast.

### Rejected alternatives

- **A stated lightness (A, B)** — fails 3:1 for all 12 dark-mode slots on a hue-only seed.
- **Uncapped per-slot chroma (D) as default** — reaches 128% of the brand accent's chroma; it
  *"almost over saturates"*.
- **Seed-capped chroma (E) as default** — truest to the original colour wheel, but uneven: six slots
  at brand intensity, six below. Kept as `walk.chromaCeiling: "seed"`.

### Lens

- **Given** the walk exists only to separate categories visually (DT-CAT-1), and every slot sits among
  the others,
- **we prefer** a solved lightness and one uniform chroma by default **over** stated lightness or
  per-hue chroma,
- **because** a uniform walk looks even and no categorical colour competes with another, while the
  solve keeps every slot legible against the ground,
- **unless** a brand needs its categorical colours truer to its own accent, which is what
  `walk.chromaCeiling: "seed"` is for.

### Consequences

- **Q3 closes.** Its only visible effect was on the walk. The DT-REF-1 neutral offsets already give
  every text pairing AAA, so solving them against a target would produce the same values.
- **Applied by cascade, not separately asked:** the brand roles (`color.background.brand.*`,
  `color.border.brand`, `color.link`) follow the same default: lightness solved against their
  grounds, a stated value never pushed (DT-CONTRAST-1). Reopen only if this is wrong.
- The `contrastLevel` dial (M3's system-wide −1 to 1 target shift) is not adopted by this decision;
  logged as low stakes.
- DT-WALK-1's "12 slots cost nothing over 7" still holds: the floor is set by the 210° hue, which is
  already in the first seven.
