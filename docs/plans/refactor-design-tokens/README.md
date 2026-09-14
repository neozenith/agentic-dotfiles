# Design-token refactor

> **Status:** parked 2026-09-09, mid-way through curation. Requirements-only; no code written yet.
> **Read this file, then [`DECISIONS.md`](DECISIONS.md), then [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md).**
> Everything needed to resume is in this directory. Nothing assumes the prior session.

## What this is

Formalising one design-token architecture shared by two agent skills — `skills/richdocs/` and
`skills/mermaidjs-diagrams/` — so a brand profile is curated once and paints every surface those
skills render: chrome CSS, cytoscape, plotly, mermaid, deck.gl, draw.io, in light and dark.

Inspiration was taken from `~/foss/diagram-design/`, which uses semantic-role indirection. It was
**not copied**; its naming was evaluated and rejected (see DT-ROLES-1).

## The architecture in one diagram

```text
  seed.json              ir.json                   design-tokens.json (DTCG)
  ─────────              ───────                   ────────────────────────
  OPTIONAL               the root artifact    ──▶   the ONLY file skills
  a few parameters  ──▶  semantically              read at runtime
  + one brand hue        complete: every
                         role, every surface,
                         light + dark
       │                      │                          │
   scrapeable             hand-editable              hand-editable
   from a website         iterate here               fine-tune here
                              │                          │
                     curation script              build script
                     imputes what is absent,      pure transform,
                     maximises WCAG               no design knowledge
```

Three artifacts, two transforms. The gates run at **curation** time, never at load. A stated value
is final; rules only impute what a profile does not state.

## The five topics, and where each stands

The work was framed as five topics. Two are closed, one is active, two are downstream.

| # | Topic | The question | Status |
|---|-------|--------------|--------|
| 1 | **Structure** | What are the layers, and what does indirection mean? | **Mostly closed** — DT-ROLES-1 locks 15 role names; DT-PIPE-1 locks the three-artifact model |
| 2 | **Location** | Where does a profile live, how is it found? | **Closed** — DT-LOC-1 |
| 3 | **Override** | How does a project override, and where is the authoring boundary? | **Closed** — DT-PIPE-1; override *is* editing the IR or the DTCG |
| 4 | **Curation** | How is a profile authored? What is stated vs imputed? | **Active** — 5 of 6 open questions live here |
| 5 | **Ripple** | How does one value reach every surface, and what stays consistent? | **Downstream** — expected to fall out of topics 1 and 4 |

**Out of scope:** `pytest-xharness-eval` usage on either skill. Dropped by the maintainer.

## Files

| Path | What it holds |
|---|---|
| [`DECISIONS.md`](DECISIONS.md) | The eleven locked decisions, each with a four-clause lens and its rejected alternatives. **Canonical.** |
| [`OPEN-QUESTIONS.md`](OPEN-QUESTIONS.md) | The six parked questions, ranked, with what each blocks. |
| [`CURATION.md`](CURATION.md) | The seed → IR pipeline, stage by stage. Partly settled, partly draft — each stage says which. |
| [`research/`](research/) | Six sourced dossiers plus a grounding quote-sheet. Every claim carries a URL. **Do not re-derive.** |
| [`scripts/`](scripts/) | Three runnable measurement scripts. The numbers in `DECISIONS.md` came from these. |

## Locked decisions at a glance

| ID | Decision |
|---|---|
| **DT-LOC-1** | One shared curated profile store; five-tier cascade; `{skill_name}` is *not* in the path |
| **DT-PIPE-1** | seed → IR → DTCG; only the DTCG is read at runtime; gates run at curation |
| **DT-BUILD-1** | Curation bakes every surface into the IR; build only serialises |
| **DT-NEUTRAL-1** | Neutrals are pure greys (chroma 0, hue 0) stated as lightness |
| **DT-CVD-1** | CVD safety is a very low priority and is not an objection to a design choice |
| **DT-REF-1** | One reference per mode plus parameterised offsets, in **OKLCH**. Dark `bg` 0.15, light `bg` 0.90 |
| **DT-ROLES-1** | Semantic role names follow **Atlassian's** `foundation · property · modifier` grammar |
| **DT-ACCENT-1** | One required brand hue; a second is imputed as walk slot 1 and overridable |
| **DT-WALK-1** | The categorical walk ships **12** pre-computed slots |
| **DT-BORDER-1** | `border` is the text colour at 14% alpha; `border.bold` is opaque at 0.35 toward text |
| **DT-CAT-1** | Categorical classes are sequentially assigned categorical slots, for visual separation only. **Never re-ask.** |

## The role vocabulary

Locked by DT-ROLES-1. Both skills' existing names are retired.

```text
color.surface.sunken            color.text                  color.border
color.surface                   color.text.subtle           color.border.bold
color.surface.raised            color.text.subtlest          color.border.brand
                                color.text.inverse
color.background.brand.bold     color.link                  color.chart.categorical.1…12
color.background.brand.subtlest                             color.text.danger / .warning / .success
```

`accent` is **retired as a role name** — it named three different jobs across the two skills.

## Ground rules that earned their place

- **Never ask how categorical classes get colour.** Storage, compute, network, Input, Process and
  every other class are like apples and pears: sequentially assigned `color.chart.categorical.<N>`
  slots, for visual separation only. No named class roles, ever. This has been re-asked across
  many sessions and is the single most frustrating mistake to repeat. See DT-CAT-1.

Carried from the [retro](../../retros/plan-gap/design-thinking.md) that restarted this work, and
reinforced during the session:

- **Ask, do not present.** The maintainer holds the model. Surface it, reflect it back, let them
  correct it cheaply.
- **Source code is evidence about the present, never about intent.** A token's *purpose* is always
  a question for the maintainer. Reading call sites is how `categoryColours` was misdefined twice.
- **Confirm the frame before working inside it.** Any model drafted on the maintainer's behalf gets
  confirmed before decisions are spent within it.
- **On design-convention questions, research first.** The maintainer is an engineer, not a designer,
  and says so. Asking him to rule on what the literature already answers just launders a guess.
  Questions about *his* system and priorities go straight to him.
- **Put decisions through `concise-decisions`.** A bare options list with no briefing corners him
  into a frame he did not agree to; it was rejected twice for exactly that.
- **Measure, don't assert.** Every colour claim in `DECISIONS.md` has a script behind it. Two agent
  claims were wrong until computed.

## Prior artifacts

The superseded `docs/plans/mermaid-design-tokens/` and `docs/plans/HANDOFF-design-token-evals.md`
have been removed from the repo. Nothing here depends on them. The retro that explains *why* that
attempt was restarted is at [`docs/retros/plan-gap/design-thinking.md`](../../retros/plan-gap/design-thinking.md).
