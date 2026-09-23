# Open questions

No decision question remains open (DT-PROV-1 closed 2026-09-24). Everything settled is in
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

## ~~Q10~~ — closed by DT-ACCENT-1 (revised)

The secondary drives selected, active, focus and hover state through `color.background.selected`,
`color.border.selected`, `color.border.focused` and `color.text.selected`. It is derived from the brand
hue at low chroma and can be overridden in the seed.

---

## ~~Q7~~ — closed by DT-CONTRAST-1

Imputed values are pushed until every text-on-background pairing passes, within each role's tier.
Stated values are never pushed.

---

## ~~Q8~~ — closed by DT-CONTRAST-1

Text on a background colour is what gets checked. Defaults must pass; a miss caused by a stated seed
parameter is the user's choice, reported as information and never as a failure.

---

## ~~DT-PROV-1~~ — closed 2026-09-24 by DT-PROV-1 in DECISIONS.md

Each IR value keeps what curation derived for it; a value that differs is a stated hand edit.
The original question is kept below for its history.

### DT-PROV-1 (as asked) — how does curation tell an imputed value from a stated one?

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

## Low-stakes items, resolved 2026-09-24

Each was settled as a pragmatic default (evidence or a recorded lens points one way, and it is cheap
to reverse), not put to the maintainer. Reopen any of them with evidence.

- **~~A `contrastLevel` dial~~ — not adopted.** DT-WALK-2 already said "add only if a brand needs
  it", and no brand does: every hue-only seed round the wheel scores zero contrast defects (worst
  pairing 4.50:1, `color.link` on `surface.sunken` at hue 255). Add it the day a brand asks for a
  global high- or low-contrast variant.
- **~~Alpha support per surface~~ — every projection flattens alpha onto its ground.** Probed in the
  showcase: Mermaid 11.4.1 passes an 8-digit hex through for `lineColor` but drops it for
  `primaryColor`, and draw.io expresses alpha as a separate `opacity` style, not in the colour. So
  the DTCG keeps `color.border`'s alpha, and any surface projection composites it over the ground it
  sits on, as the richdocs projection already does (`border`, `grid`, `compoundBorder`).
- **~~`.design-profiles/` spelling~~ — kept.** It is the name every decision and doc already uses,
  matches the `.claude/` and `.codex/` dot-directory convention, and a rename is a string change.
- **~~The rest of the seed~~ — the seed is exactly the `DEFAULTS` keys in `prototype/pipeline.py`**,
  every one optional except `brand.hue`. A scraped brand typically states its accents (`brand.*`,
  `brand.dark.*`) and nothing else; everything else is a tuning knob with a sourced default.
- **~~Hand-authored osakanights' pastel light series~~ — the brand's choice.** Its light-mode series
  sit at 1.6–2.0:1 as outlines on white. The pack is hand-authored, so under DT-CONTRAST-1 that is a
  stated value and information only. Its generated sibling `hue-osakanights` passes.
- **~~The Tune seed drawer ignores IR edits~~ — it now keeps them.** The generator manifest carries
  the profile's stated values (DT-PROV-1) as `context`, so live tuning keeps hand edits exactly as
  `curate` does (richdocs ADR-022).

## Still open: the build, not a decision

- **Migration.** Both skills' packs need a rename to the DT-ROLES-1 vocabulary, and the real curation
  tool replaces the prototype. `richdocs` ADR-004's two-palette split (chrome CSS vars + canvas JS
  palette) survives; only the keys change. Sequenced in [`MIGRATION.md`](MIGRATION.md).
