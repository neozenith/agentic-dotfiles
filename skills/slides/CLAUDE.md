# CLAUDE.md: the `slides` skill

Read the ADR log before changing anything here. Each entry carries a **Lens**: a
forward-looking rule to apply to the next decision of that kind, so a question
that looks new is usually already answered.

Usage lives in [SKILL.md](SKILL.md) and [README.md](README.md). This file holds
only rationale.

## The development contract

Run from the repo root. Never `cd`.

```bash
make -C .claude/skills/slides/scripts fix   # mutates: formats + auto-fixes lint
make -C .claude/skills/slides/scripts ci    # the gate: 0-exit before any handoff
```

`ci` is free, offline and deterministic: no model call, no network, no browser.

## File map

| Path | Role |
|---|---|
| `SKILL.md` | Agent operating manual: triggers, routes, the command surface |
| `README.md` | Human explainer: quickstart, architecture, troubleshooting |
| `resources/authoring.md` | Depth for writing a deck; read before touching a deck's Makefile or theme |
| `resources/prose.md` | The prose standard this skill's own copy of; gated by `prose_check.py` |
| `scripts/scaffold_deck.py` | Writes a deck from `assets/deck/`, derives the theme palette from tokens |
| `scripts/tier_progress.py` | Derives the progress bar (fractions **and** segments) from `@tier` markers |
| `scripts/slide_durations.py` | Derives per-slide media hold times from word counts |
| `scripts/prose_check.py` | Gates the mechanical prose rules |
| `assets/deck/` | The deck template. Every file is copied and `{{PLACEHOLDER}}`-rendered |

## Architecture principles

1. **A scaffolded deck depends on nothing outside itself**, including this skill.
2. **Anything a human would retype is derived**, and the deriver refuses rather
   than guesses.
3. **Every gate is free and offline.** A gate that spends money gets skipped.
4. **The generic surface is the deck's;** the project-specific parts (palette,
   tiers) are inputs, never code changes.

## ADR log

### ADR-0001: The deck is self-contained, and the helpers are copied into it

**Status:** Accepted

**Context.** A deck could call this skill's scripts directly. That is DRY and it
is wrong: the deck would stop building the moment the skill moved, was renamed or
was absent, and a consumer could not fix a script without editing a skill.

**Decision.** `scaffold_deck.py` **copies** the three helpers into the deck's
`scripts/`, alongside a Makefile that references only its own directory. The same
files serve as the skill's tools and the deck's, so one fix reaches both, but the
deck holds its own copy at scaffold time.

**Consequences.** A deck survives the skill's deletion, and a consumer owns their
copy outright. The cost is drift: a fix here does not reach decks already
scaffolded, and re-scaffolding is the consumer's decision. That is the accepted
trade, matching this repo's skill-isolation rule.

**Lens.** When something you generate could either *call* you or *carry* a copy,
give it the copy. Ask what happens when this skill is deleted. If the answer is
"the artifact breaks", the artifact was not self-contained.

### ADR-0002: Derived values are generated into the artifact, never hand-written

**Status:** Accepted

**Context.** The pattern this skill was distilled from hand-maintained a `--p`
fraction per slide, with a comment reading "reorder slides then retune here". It
fails silently: the deck still renders and the bar simply lies. The same is true
of a GIF's per-slide frame timing.

**Decision.** One marker per slide names its audience; everything else is
computed. `make progress` writes a managed block into the deck. Timing is computed
from each slide's readable word count.

**Consequences.** Adding or moving a slide is a one-marker edit, and reviewers see
a semantic diff rather than a wall of changed decimals. The build writes to a
source file, which is unusual; the generator is idempotent and writes only on
change.

**Lens.** If a human would have to retype a number after an unrelated edit, that
number is derived, not authored. Generate it, and make the generator refuse when
its inputs are inconsistent.

### ADR-0003: The generator owns the bar's segments; the theme owns its geometry

**Status:** Accepted

**Context.** The source pattern hard-coded four segments into the theme's CSS
gradient, which forced the tier list and the theme to change together. A skill
cannot ship that: tiers are per-project, and every consumer would be editing CSS
to add an audience.

**Decision.** `tier_progress.py` computes the gradient for the configured tier
count and writes it into the same managed block as the fractions. The theme
declares only the bar's position, height and unreached track. `tiers.toml` is the
single input.

**Consequences.** Two to six tiers work with no CSS edit. The coupling the source
pattern recorded as an unavoidable consequence is gone. The generated block now
carries a rule the theme cannot override, so a theme wanting a different bar must
change the generator.

**Lens.** When distilling a pattern, look for the couplings its ADRs call
"unavoidable". They are usually unavoidable only for one instance. Generalising
is the moment to break them, not to inherit them.

### ADR-0004: The scaffold is born green

**Status:** Accepted

**Context.** The first working scaffold produced a deck whose own `make ci`
failed: the gate asserts the committed progress block matches the markers, and no
block existed until the consumer ran `make progress`.

**Decision.** `scaffold_deck.py` generates every deck's block before it returns,
and fails loudly if a template deck cannot pass its own check.

**Consequences.** A fresh deck is committable and green. The scaffold now depends
on `tier_progress` as a module, which is also what keeps the two honest: a
template that breaks the generator fails the scaffold.

**Lens.** Anything you scaffold must pass its own gates on the first run. A
generated repo that starts red teaches the consumer to ignore the gate before
they have written a line.

### ADR-0005: Validation refuses; it does not warn

**Status:** Accepted

**Context.** Both derived values fail *plausibly*. A mis-numbered bar still
renders; a misaligned playlist still produces a video. Nothing looks broken, and
the reader cannot tell.

**Decision.** Unknown tier, out-of-order tiers, interleaved tiers, two markers on
one slide, a frame/slide count mismatch, a missing tier config, an unresolved
template placeholder: each is an error that stops the build with the reason.

**Consequences.** A structural problem surfaces at build time instead of in a
meeting. Some errors are strict about things a warning could tolerate, which is
deliberate.

**Lens.** Decide by the failure mode, not the severity. If the wrong answer is
indistinguishable from the right one at a glance, refuse. Warn only when the
reader can see the problem themselves.

### ADR-0006: The prose standard is a gate, and the copy lives here

**Status:** Accepted

**Context.** Prose rules that live in a doc decay. In the source project, 126
em-dashes had accumulated across ten files while the standard sat one directory
away. Separately, this repo requires a skill to depend on no sibling skill.

**Decision.** `resources/prose.md` is this skill's own copy of the standard, and
`prose_check.py` gates the mechanically decidable subset in a scaffolded deck's
`ci`. It skips code fences, inline code spans and generated regions, because an
identifier is a name and not prose. It judges nothing else: clause count, reading
grade and tone need a reader.

**Consequences.** The rule holds without anyone remembering it. The copy may drift
from other copies, which the repo's isolation rule accepts on purpose.

**Lens.** A checker earns trust by never firing on a judgement call. When adding a
rule, ask whether a machine can decide it from the text alone. If not, it belongs
in the read, not the gate.

### ADR-0007: A starter deck's tier markers are derived too, at scaffold time

**Status:** Accepted

**Context.** Both starter decks ship tagged with the template's own tier names. A
project whose audiences differ got two decks that failed their own build before
it had written a slide, on its first customisation. The error was loud and
correct, which made it worse: the gate fired on the tool's own output.

**Decision.** `--tiers <file>` supplies the project's audiences at scaffold time.
The config is validated, then both starter decks are retagged by spreading their
slides evenly across the declared tiers, in order. The marker names in a starter
deck exist only to demonstrate the bar, so they carry no meaning and are
derivable like everything else.

**Consequences.** Any tier config produces two green decks. Editing `tiers.toml`
AFTER scaffolding still requires retagging by hand, because by then the markers
are the consumer's own text and rewriting them would be destroying authored
content. The error names the fix, and the README says so.

**Lens.** When a gate fires on your own generated output, the generator is wrong,
not the gate. Ask what the artifact must look like to pass on the first run, and
generate that.

## Extension checklist

- [ ] `make -C .claude/skills/slides/scripts fix ci` green (90% coverage holds).
- [ ] A new derived value follows ADR-0002: generated, idempotent, refuses on bad input.
- [ ] A new deck-template file is `{{PLACEHOLDER}}`-rendered and passes the
      unresolved-placeholder check.
- [ ] A new file the deck **embeds** is a prerequisite of the frame stamp, or renders go stale.
- [ ] Scaffolded a deck and ran its `make ci` (born green, ADR-0004).
- [ ] README diagrams pass the contrast and complexity gates.
- [ ] Every doc ≤ 500 lines; brand-agnostic (no project nouns, palettes or names).
- [ ] Prose follows `resources/prose.md`.

## Known gotchas

Each cost real time. The symptom is the part worth recognising.

- **Make caches file timestamps.** *Symptom:* you edit a slide's tier, the bar
  retunes, and the frames render from the pre-retune deck. A recipe rewriting the
  deck mid-run is invisible to rules that already stat'd it. Hence the parse-time
  `$(shell ...)` sync in the deck Makefile. Never make it a prerequisite.
- **A `.PHONY` prerequisite is perpetually newer.** *Symptom:* every `make frames`
  re-renders in a browser even when nothing changed, and three variants cost three
  renders.
- **A `---` inside a fenced code block is not a slide break.** *Symptom:* a deck
  that documents its own syntax gets one phantom slide, and every fraction after
  it lands on the wrong slide. Both parsers track fences; they must agree.
- **The generated block must never contain a literal `@tier <name>`.** *Symptom:*
  the second run reports an unknown tier named `NAME`, or text leaks onto slide 1
  because a nested `-->` closed the comment early. `strip_managed()` removes the
  region before parsing, which kills the class of bug.
- **`section#3` is invalid CSS.** *Symptom:* the bar silently never fills. An
  ident cannot start with a digit, so the rules use `section[id="3"]`.
- **Marp parses a `key: value` comment as a directive.** *Symptom:* an unknown
  directive warning, or a marker that does nothing. The marker is `@tier name`,
  with no colon, so it stays inert.
- **Two decks, one frames dir.** *Symptom:* a GIF of the wrong deck. Frames are
  namespaced by `$(NAME)`; keep every per-deck artifact keyed the same way.
