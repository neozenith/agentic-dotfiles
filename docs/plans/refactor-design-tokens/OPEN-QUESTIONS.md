# Open questions

Two questions, ranked by what each unblocks. Everything settled is in
[`DECISIONS.md`](DECISIONS.md); do not reopen those without evidence.

**How to ask these.** Route every one through the `concise-decisions` skill and its Claude Code
adapter — full briefing in the message body, then one single-select picker with a `preview` on every
option and a "not a decision yet" route. A bare options list has been rejected twice. Previews must
carry real computed values, not illustrative fragments; `scripts/` exists so they can.

---

## ~~Q6~~ — closed by DT-CAT-1. Do not reopen.

Categorical classes are sequentially assigned `color.chart.categorical.<N>` slots for visual
separation only. This was never an open design question.

---

## ~~Q11~~ and ~~Q3~~ — closed by DT-WALK-2

Walk lightness is solved per slot and mode. Chroma is one rule with a ceiling: default `"floor"`
gives every slot the same chroma, and `"seed"` lets each hue reach its maximum up to the brand's.

---

## ~~Q9~~ — resolved by DT-BORDER-1

`color.border` is the text colour at 14% alpha; `color.border.bold` is opaque at a 0.35 offset
toward text. See `DECISIONS.md`.

---

## Q10 — a reserved highlight token

The research's own recommendation, and not yet a decision. `research/research-accent-in-dataviz.md`
found that what the system is actually missing is not a second brand hue but a **reserved,
walk-excluded highlight**.

Emphasis / highlight / selection is a real distinct colour role: Highcharts
`--highcharts-highlight-color-*` (a fourth family alongside categorical, neutral and status),
Cytoscape `:selected` `#0169D9`, deck.gl `highlightColor`, mxGraph `HIGHLIGHT_COLOR`, Plotly
`activeshape.fillcolor`. Every one is picked to sit **outside** the content palette.

But chart libraries do emphasis as a **modifier**, not a hue — ECharts `liftColor()`, Carbon
`-hovered` at −7% lightness, Highcharts hover `brightness`. Vega, Observable Plot and Excalidraw
have no such role at all.

The likely split: **`selection`** as a reserved hue for interactive chrome (the cytoscape viewer,
deck.gl), and **`emphasis`** as a lightness modifier for static content focus (mermaid, plotly
images, draw.io). A reserved hue must be excluded from the 12-slot walk or it collides with a
category.

---

## ~~Q7~~ — closed by DT-CONTRAST-1

Imputed values are pushed until every text-on-background pairing passes, within each role's tier.
Stated values are never pushed.

---

## ~~Q8~~ — closed by DT-CONTRAST-1

Text on a background colour is what gets checked. Defaults must pass; a miss caused by a stated seed
parameter is the user's choice, reported as information and never as a failure.

---

## DT-PROV-1 — how does curation tell an imputed value from a stated one?

**Parked by the maintainer**, not deferred by ranking: *"too early to answer this. we should define
the curation process of generating from seed to ir before we can contemplate what re-computing
means."*

**DT-CONTRAST-1 now requires it:** a contrast miss is a defect only when the value was imputed, and
the user's choice when it was stated, so the report is only correct if provenance is tracked.

It has to come back before curation is finished, because DT-BUILD-1 depends on it: curation must be
**idempotent and additive** — imputing what is absent and never overwriting what is stated — or
re-running it destroys the hand edits that are the whole point of the IR.

The three candidate mechanisms, for when it reopens:

1. **Provenance per value** — record imputed-vs-stated (DTCG reserves `$extensions` for exactly
   this); re-impute any imputed value whose inputs changed. Sub-choice: group-level or value-level
   granularity.
2. **Opt-in re-derive** — never overwrite anything present; `--rederive <group>` is explicit.
3. **Report only** — curation reports staleness and writes nothing.

The live trap either way: edit `color.background.brand.bold` and the 12-slot walk anchored on it is
now stale, with nothing reporting it.

---

## Also unresolved, low stakes

- **A `contrastLevel` dial.** M3 ships a system-wide −1 to 1 shift of every contrast target.
  Not adopted by DT-WALK-2; add only if a brand needs a global high- or low-contrast variant.

- **Alpha support per surface.** DT-BORDER-1 makes `color.border` translucent. Cytoscape and deck.gl
  accept alpha; mermaid `themeVariables` and draw.io stencil styles are unverified. A surface that
  cannot composite needs a baked opaque value per ground.

- **`.design-profiles/` spelling.** DT-LOC-1 fixed the *scope* of the shared store, not its name.
- **The rest of the seed.** Beyond the brand hue and the neutral parameters, what else does
  `seed.json` carry? Deliberately not locked; the maintainer wants it small.
- **Migration.** Both skills' packs need a rename to the DT-ROLES-1 vocabulary. `richdocs` ADR-004's
  two-palette split (chrome CSS vars + canvas JS palette) survives — only the keys change.
