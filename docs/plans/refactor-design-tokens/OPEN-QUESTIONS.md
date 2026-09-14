# Open questions

Six questions, ranked by what each unblocks. Everything settled is in
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

## Q11 — equal chroma across the walk, or each hue's own maximum?

Arose from measuring DT-WALK-1. Run `scripts/walk_12.py` to reproduce.

At `osakanights`' accent (`L 0.4498  C 0.1312  H 295.04°`), holding one chroma for all 12 slots
means taking the minimum over hues — `0.0779`, **59.4% of the seed's chroma**. The binding hue is
210.04°. Per-slot maximum chroma gives vivid colours that do not match each other.

Tableau deliberately broke equal-lightness for exactly this reason. Note DT-CVD-1: CVD is not an
argument here.

**Blocks:** the final walk values, and therefore every surface that consumes them.

---

## Q3 — contrast targets per role, and is there a `contrastLevel` dial?

DT-REF-1 fixed the reference and the offsets but not the *targets* those offsets are meant to hit.
M3 models a role as `(palette, defaultTone(isDark), ContrastCurve, backgroundRef)` and **solves**
for tone — `Contrast.lighter/darker` return `−1` when a ratio is unachievable. It also ships a
system-wide `contrastLevel` dial from `−1` to `1`.

Currently the offsets are stated numbers that happen to measure well (every pairing AAA, worst
9.69:1 — see `scripts/verify_chosen_ref.py`). The question is whether they stay stated, or become
solved against declared targets.

**Related:** an earlier attempt to ask this (as "which roles are stated vs solved") was rejected as
unclear. Reframe around the maintainer's own stated preference: *set one reference, relative ratios
are the defaults, specify little and gain a lot.*

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

## Q7 — what does "pragmatic" mean as a WCAG stopping rule?

DT-PIPE-1 rule 5 says curation maximises WCAG *"to a pragmatic, not necessarily optimum level"* —
the maintainer's words. The stopping rule is undefined.

Candidates: hit a fixed floor and stop; maximise subject to holding every stated value; iterate a
bounded number of times. Not chosen.

---

## Q8 — where does `mermaid_contrast.ts` fire?

Flagged by the maintainer as important-but-unplaced. It is a **different gate** from pack validity,
which DT-PIPE-1 rule 4 explicitly turns off at load:

- Pack validity asks *are these colours contrasty?* — answered at curation, never at load.
- `mermaid_contrast.ts` checks a **finished diagram against a host background**
  (`Profile = "github" | "mkdocs-material"`). A perfect pack does not guarantee that, because the
  author may bind the wrong role to a node, or the host's page background may differ from the
  profile's own.

Worse, some failures the pack cannot express at all: `htmlLabels:false` makes flowchart edge labels
fail WCAG on light hosts, and the contrast gate cannot see it (see repo memory).

**No longer blocked:** DT-CAT-1 settles that diagram classes use sequential categorical slots, so
the values the gate checks exist.

---

## DT-PROV-1 — how does curation tell an imputed value from a stated one?

**Parked by the maintainer**, not deferred by ranking: *"too early to answer this. we should define
the curation process of generating from seed to ir before we can contemplate what re-computing
means."*

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

- **Alpha support per surface.** DT-BORDER-1 makes `color.border` translucent. Cytoscape and deck.gl
  accept alpha; mermaid `themeVariables` and draw.io stencil styles are unverified. A surface that
  cannot composite needs a baked opaque value per ground.

- **`.design-profiles/` spelling.** DT-LOC-1 fixed the *scope* of the shared store, not its name.
- **The rest of the seed.** Beyond the brand hue and the neutral parameters, what else does
  `seed.json` carry? Deliberately not locked; the maintainer wants it small.
- **Migration.** Both skills' packs need a rename to the DT-ROLES-1 vocabulary. `richdocs` ADR-004's
  two-palette split (chrome CSS vars + canvas JS palette) survives — only the keys change.
