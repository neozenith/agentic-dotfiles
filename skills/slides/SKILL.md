---
name: slides
description: Build and maintain presentation decks as version-controlled Markdown (Marp), rendered to HTML/PDF/PPTX and to self-running mp4/GIF whose per-slide timing is computed from each slide's word count. Use when asked to create a slide deck, pitch deck or presentation from a repo; add slides to an existing deck; render a deck to PDF/PowerPoint/GIF/video; build an audience-tiered deck (executives through to engineers) with a progress bar; or theme a deck from a project's design tokens. Also use when a deck's timing, progress bar or prose gate needs fixing. Skip for one-off diagrams (no deck), for a document that is prose rather than slides, and for editing an existing PowerPoint binary (this authors decks as Markdown, it does not parse .pptx).
user-invocable: true
---

# slides

Author decks as Markdown. Everything that could rot is **derived**: the progress
bar from per-slide audience markers, the GIF's per-slide timing from word counts.
A number a human types is a number that lies after the next edit.

Requires **bun** (`bunx`) and **uv**. Chrome or Chromium for PDF, PPTX, diagrams
and frames; **ffmpeg** only for video and GIF. First build fetches the Marp CLI
from npm.

## Route by intent

| Intent | Do this |
|--------|---------|
| "Make a deck for this repo" | `scaffold_deck.py --out docs/slides --tokens <design-tokens.json>` |
| "My audiences are not the defaults" | Pass `--tiers <file>` at scaffold time: both starter decks are retagged to match |
| "What layouts can I use?" | `make -C docs/slides template`: the buildable reference deck |
| "Add or reorder slides" | Edit the deck, tag each slide `@tier <name>`, `make progress` |
| "Change the audiences" | Edit `tiers.toml`, `make progress`. No CSS edit: the bar's segments are generated |
| "Render it" | `make -C docs/slides html` / `pdf` / `pptx` / `gif` |
| "It should loop on a screen" | `make -C docs/slides variants`: three pacings from one render |
| "Is the deck sound?" | `make -C docs/slides ci`: free and offline, checks bars and prose |
| "Why is the bar wrong?" | Read `resources/authoring.md`; never hand-edit the generated block |
| "Diagrams in slides" | `resources/authoring.md`. Marp has no Mermaid runtime, so pre-render |

## Quickstart

```bash
# 1. Scaffold a self-contained deck (theme derived from the project's tokens)
uv run --no-project .claude/skills/slides/scripts/scaffold_deck.py \
  --out docs/slides --name product-pitch --tokens frontend/src/design-tokens.json

# 2. See every layout available, as a real rendered deck
make -C docs/slides template

# 3. Write slides.md, then build
make -C docs/slides html          # fastest; no browser needed
make -C docs/slides gif           # frames -> per-slide timing -> mp4 -> GIF
make -C docs/slides ci            # gate: bars current, prose clean
```

Run everything from the repo root. Never `cd`.

## What the scaffold writes

A deck that depends on nothing outside its own directory, including this skill.
The helper scripts are **copied in**, not referenced, so the deck keeps building
if the skill is gone and a consumer can edit them freely.

```
docs/slides/
├── Makefile              # build / render / media / ci. `make help` lists all
├── slides.md             # the deck. Edit this
├── master-template.md    # buildable reference: every layout, with its source
├── tiers.toml            # the audiences, in the order the deck addresses them
├── themes/<name>.css     # theme, palette derived from the project's tokens
├── assets/               # diagram sources (*.md) and images the deck embeds
└── scripts/              # tier_progress · slide_durations · prose_check
```

## The two derived things

Never hand-write either. If you are typing a number the deck could compute, stop.

| Derived | From | Command |
|---|---|---|
| Progress-bar fraction **and** the bar's segments | each slide's `@tier` marker, plus `tiers.toml` | `make progress` |
| Per-slide GIF/video hold time | each slide's readable word count | `make durations` |

`p = (tier_index + (i + 1) / n) / T` for slide `i` (0-based) of a tier holding
`n`, across `T` tiers. `seconds = clamp(BASE + words / WPM * 60, MIN, MAX)`.

Both refuse rather than guess. An unknown tier, tiers out of order, tiers
interleaved, or two markers on one slide stops the build. A frame/slide mismatch
refuses to emit a pacing playlist. A progress bar over a non-monotonic deck is a
lie, and a misaligned playlist pairs the wrong duration to the wrong frame.

## Authoring rules (the short version)

- **One `@tier` marker per slide**: an HTML comment wrapping `@tier <name>`,
  naming a tier from `tiers.toml`. It is the only progress input.
- **Tiers run top-down and contiguous**, in the order `tiers.toml` declares.
- **Never hand-edit the `BEGIN/END GENERATED PROGRESS BAR` region.**
- **Slides break on a lone `---`**, except inside a fenced code block.
- **Prose rules apply to slide copy** and are gated by `make ci`: no em-dash,
  Australian spelling, inclusive terms. See `resources/prose.md`.
- **Diagrams are pre-rendered.** Marp has no Mermaid runtime.

Full detail, including the layout classes and the media pipeline:
`resources/authoring.md`. Read it before editing a deck's Makefile or theme.

## Scripts

Each is stdlib-only and runs anywhere `python3` exists; `uv` is the launcher.
All print their table to stderr and keep stdout clean.

```bash
uv run --no-project scripts/scaffold_deck.py --out DIR [--name N] [--tokens F] [--tiers F] [--force]
uv run --no-project scripts/tier_progress.py --deck slides.md --tiers tiers.toml [--check]
uv run --no-project scripts/slide_durations.py --deck slides.md --frames-dir build/frames/N --out P
uv run --no-project scripts/prose_check.py [--files ...]
```

`--check` (tier_progress) writes nothing and exits 1 if the committed block is
stale. That is what `make ci` runs.

## Resources

| File | Read it when |
|------|--------------|
| `resources/authoring.md` | Writing slides, editing the theme, or touching the build |
| `resources/prose.md` | Writing any copy this skill will ship |
