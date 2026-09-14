# Curation: seed → IR

The pipeline that turns a small set of stated parameters into a semantically complete `ir.json`.
Per DT-BUILD-1, curation bakes **every** surface into the IR; the build step is a pure transform to
DTCG and holds no design knowledge.

**Each stage below is marked ✅ settled or 🟡 draft.** Settled stages cite their decision in
[`DECISIONS.md`](DECISIONS.md). Draft stages are the agent's proposal and should be overwritten
wherever they mismatch the maintainer's model. Open questions are in
[`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) and are *not* restated here.

Two invariants hold across every stage:

- **Curation imputes what is absent and never overwrites what is stated** (DT-BUILD-1). This makes
  re-running it safe, which is what lets a new surface be added to an existing profile.
- **A stated value is final and unconstrained.** The rules exist to impute, never to police. A brand
  may choose green for `danger`.

---

## Stage 0 — the seed ✅ partly settled

`seed.json` is **optional**. A hand-authored `ir.json` with no seed is a first-class, fully valid
profile — the IR is the root of the system, not the seed. The seed exists so a scraped brand can be
extrapolated into a full IR.

| Parameter | Required | Default | Decision |
|---|---|---|---|
| brand hue | **yes** | — | DT-ACCENT-1 |
| second brand hue | no | imputed at `primary + 137.5°` | DT-ACCENT-1 |
| `L-dark-bg` | no | **0.15** | DT-REF-1 |
| `L-light-bg` | no | **0.90** | DT-REF-1 |
| `offset.surface.sunken` | no | **−0.05** | DT-REF-1 |
| `offset.surface.raised` | no | **+0.05** | DT-REF-1 |
| `offset.text.subtle` | no | **+0.65** | DT-REF-1 |
| `offset.text` | no | **+0.90** | DT-REF-1 |
| fonts | no | a fallback stack | 🟡 |

Name→role heuristics for the scrape path are already worked out in
`~/foss/diagram-design/references/onboarding.md:228-235` — `background|bg|surface|canvas` → ground,
`accent|brand|primary|cta|highlight` → brand hue, and so on. That table is directly reusable.

Everything else the brand states is imputed. Whether the seed carries more than the above is
deliberately not locked; the maintainer wants it small.

---

## Stage 1 — the neutral ramp ✅ settled (DT-NEUTRAL-1, DT-REF-1)

Colour space is **OKLCH**. Neutrals are chroma 0, hue 0 — pure greys, not hue-tinted. For an
achromatic colour the OKLab transform collapses to `L = cbrt(Y)`, so relative luminance is exactly
`Y = L³` and WCAG contrast is closed-form with no colour library.

One reference per mode, plus offsets. Two *kinds* of offset, and the distinction is load-bearing:
**absolute** offsets keep their direction in absolute lightness (`surface.sunken` is darker in both
modes), while **toward-text** offsets flip with the mode, which is what lets one number serve both.

```text
role                     dark L    hex     |  light L    hex
color.surface.sunken       0.10  #030303   |     0.85  #cecece
color.surface              0.15  #0b0b0b   |     0.90  #dedede
color.surface.raised       0.20  #161616   |     0.95  #eeeeee
color.text.subtle          0.80  #bebebe   |     0.25  #222222
color.text                 1.00  #ffffff   |     0.00  #000000
```

Verified by `scripts/verify_chosen_ref.py`: every pairing clears **AAA** (worst 9.69:1); both bg
triples are clearly separated (dark 8-bit `[3, 11, 22]`, light `[206, 222, 238]`); light
`surface.raised` at `#eeeeee` leaves exactly `0.05 L` of headroom to pure white for a top-border
highlight.

**The trap this stage exists to record:** HSL 5% grey is roughly **OKLCH 0.16**. Increments transfer
between the two spaces; *bases* do not. At OKLCH `bg = 0.05`, `Y = 0.000125` becomes sRGB channel
`0.41`, which rounds to **0** — `surface.sunken` and `surface` both render `#000000`, collapsing
three specified surfaces into one visible colour. Any value carried over from an HSL sketch needs
re-anchoring, not re-labelling.

`color.text.subtlest` is a third toward-text offset, not yet set.

---

## Stage 2 — borders ✅ settled (DT-BORDER-1)

Two roles with two different jobs, so two different mechanisms.

- **`color.border`** — decorative divider, exempt from WCAG 2.2 SC 1.4.11. The mode's `color.text`
  at `alpha.border` (default **0.14**), composited over whichever ground it sits on. One token stays
  consistent across all three grounds: contrast 1.36–1.52:1 in both modes.
- **`color.border.bold`** — functional boundary, 3:1 required. Opaque, solved as the nearest
  lightness that reaches 3:1 against **every** ground. The hardest ground is `surface.raised` in dark
  and `surface.sunken` in light, so both modes land on the same `offset.border.bold` (default
  **0.35** toward text): dark `L 0.50 #636363`, light `L 0.55 #717171`.

Reproduce with `scripts/build_q9_doc.py`.

---

## Stage 3 — the brand hue in context 🟡 draft

The brand hue comes *from the brand*, so unlike neutrals it is not fully derivable. Its lightness
mirrors between modes so it stays legible on each ground — real anchor, `osakanights`: light accent
`#5c4295`, dark `#c3b0fd`, same hue, mirrored tone.

Roles to produce: `color.background.brand.bold`, `color.background.brand.subtlest`,
`color.border.brand`, `color.text.inverse`, `color.link`.

- `color.background.brand.subtlest` is the brand hue blended toward the ground. `richdocs` already
  computes this at render via `rdMix(category, bg, 0.84)` in `viewer-cytoscape.js`; under
  DT-BUILD-1 it must be **baked** instead.
- `color.link` is an **alias** of the brand hue, not an independent role — Primer makes this
  explicit, and `osakanights` already ships both as the same hex.
- Where a stated brand hue and a contrast floor conflict, M3's published escape hatch is to pin the
  brand colour verbatim and buy contrast from the *foreground* side instead
  (`FIDELITY`/`CONTENT` variants). That matches the standing rule that a stated value is final.

Contrast targets for these roles are Q3.

---

## Stage 4 — the categorical walk ✅ settled (DT-WALK-1, DT-ACCENT-1)

`color.chart.categorical.1` … `.12`, all pre-computed.

1. Convert the brand hue to OKLCH; its hue is slot 0.
2. Walk by **137.5°** for each subsequent slot.
3. Gamut-map by **reducing chroma, holding L and H** (CSS Color 4 binary search). Never vary
   lightness — that would destroy the contrast guarantee.
4. A **stated** second brand hue overrides slot 1.

Measured on `osakanights` (`scripts/walk_12.py`): the chroma-binding hue is **210.04° at slot 2**
(`maxC 0.0779`), which is already inside the first seven slots — so `min` over 7 and over 12 are
identical and **extending to 12 costs nothing**. Adjacency is uneven: smallest gap `20.00°`, largest
`52.50°`, against `30.00°` for even spacing.

Whether the walk holds one chroma for all slots or takes each hue's maximum is Q11.

**Three mechanical facts worth keeping in view**, from `research/research-accent-derivation.md`:

- **Hue constancy ≠ hue spacing uniformity.** OKLCH was fitted so hue does not *drift* when L or C
  change. Ottosson never claimed equal hue-angle steps are equal perceptual steps — his own picker
  tables mark Okhsl "Varies Evenly: **no**". So the walk's *separation* is not uniform even though
  its *angles* are.
- **Hue angle is not a perceptual distance until chroma-weighted** — CIEDE2000 has
  `ΔH′ = 2√(C₁C₂)·sin(Δh/2)`. A 137.5° step at C 0.02 and at C 0.25 are different events.
- **Constant-L, constant-C rotation is the operation most likely to leave sRGB.** Which is exactly
  what this walk does, hence step 3.

Per DT-CVD-1, CVD does not gate this stage. Recorded for completeness only: a fixed-lightness hue
ring cannot be CVD-safe (ColorBrewer flags zero qualitative schemes safe at ≥5 classes; ggplot2's
`hue_pal()` says so of itself).

---

## Stage 5 — status colours 🟡 draft

`color.text.danger` / `.warning` / `.success`, per mode. **Not from the walk** — roles carrying
conventional meaning get conventional hues, then solve for contrast.

Precedent: M3 imputes secondary, tertiary and both neutrals from one seed but **hard-codes error at
hue 25 / chroma 84**. Theory backs the split — Setlur & Stone require a system to first determine a
category's *"colorability"*; the practical rule is **pin the colourable, rotate the rest**.

Real anchor: `osakanights` already does this, with a `status` group carrying per-mode
`good/warning/serious/critical` alongside `categoryColours`.

Where mermaid's semantic *node* roles draw from is Q6, and it is the last structural question.

---

## Stage 6 — surface expansion 🟡 draft

Curation writes all of these into the IR; build only serialises them.

| Surface | Shape emitted |
|---|---|
| cytoscape | `{selector, style}[]` — node fill/border/label, edge, compound, selected |
| plotly | layout + `colorway` arrays |
| mermaid | `themeVariables` — a flat hex object |
| deck.gl | RGBA arrays |
| draw.io | stencil fill/stroke per shape class |
| CSS | custom properties for chrome (`theme.css` territory, `richdocs` ADR-009) |

**No prior art exists for any of this** — a confirmed negative across Vega, Chart.js, ECharts,
Plotly, Cytoscape, deck.gl, D3, Highcharts, draw.io, Mermaid and Excalidraw
(`research/research-tooling.md`). The targets are trivially generatable — mermaid's
`themeVariables` is a flat hex object, cytoscape is `{selector, style}[]` — so the gap is adoption,
not format. This is the most novel part of the work and the part with nothing to copy.

One verified detail that shapes the mermaid mapping: mermaid derives everything from
`primaryColor` by hue rotation, and its own "secondary" is a walk slot.

```js
// verified in skills/richdocs/vendor/…/mermaid.esm.min
this.secondaryColor = this.secondaryColor || adjust(this.primaryColor, {h: -120})
this.tertiaryColor  = this.tertiaryColor  || adjust(this.primaryColor, {h: -160})
this.cScale1 = this.cScale1 || this.secondaryColor
this.cScale2 = this.cScale2 || this.tertiaryColor
```

---

## Stage 7 — scoring, not gating 🟡 draft

Curation maximises WCAG **pragmatically, not optimally** (DT-PIPE-1 rule 5), then records what it
achieved. Nothing downstream re-checks: loading a DTCG runs no WCAG or CVD gate, because editing
that file is a hard choice the user made.

The stopping rule is Q7. Where `mermaid_contrast.ts` fires is Q8 — and it is a *different* gate from
pack validity, since it checks a finished diagram against a **host** background.
