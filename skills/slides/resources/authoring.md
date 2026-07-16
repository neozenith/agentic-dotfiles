# Authoring a deck

Read this before editing a scaffolded deck's Makefile, theme, or slide structure.
`SKILL.md` carries the command surface; this carries the depth.

## Slide structure

A slide breaks on a line that is exactly `---`, **except inside a fenced code
block**. Per-slide directives are HTML comments; a leading underscore means "this
slide only".

| Directive | Effect |
|---|---|
| `_class: lead` | Centred hero card. Oversized `h1`, no underline. |
| `_class: divider` | Section break. Deeper bleed, accent `h1`, centred. |
| `_class: lead bar-x` | Classes compose. Space-separated. |
| `_paginate: false` | Hide the page number (pair with `lead` on a title card). |
| `_footer: '...'` | Override the deck-wide footer for one slide. |
| `@tier <name>` | This slide's audience. The only progress input. |

Deck-wide config (`theme`, `paginate`, `footer`) is the YAML frontmatter.

Theme helpers: `<div class="columns">` (two-column grid), `<div class="box">`
(accent-ruled callout), `<span class="badge">` (the one line they must remember).
Markdown inside a `<div>` needs blank lines around it or it will not parse.

**`make template` renders the full reference**, every construct beside its source.
It is a real deck, so it cannot lie about what the theme supports. Adding a helper
to the theme means demonstrating it there in the same change.

## The tier progress bar

The deck is structured top-down by audience, each dropping off after their tier.
The bar shows which tier is being addressed and how far through it the deck is.

**Everything is derived from one marker per slide.** `tiers.toml` declares the
audiences in the order the deck addresses them; `make progress` writes a managed
`<style>` block holding a `--p` rule per slide **and** the bar's gradient.

The gradient is generated, not themed, because the segment count is the project's
choice. Two to six tiers read well. Past that the segments get too narrow to tell
apart on a projector. Give each tier a distinct **hue**, not a shade of the
accent: the bar's job is to say which audience is addressed, and shades of one hue
do not survive a projector or a GIF's 256-colour palette.

Validation is loud by design. Unknown tier, tiers out of declared order, tiers
interleaved, or two markers on one slide all stop the build. Monotonic progress is
the bar's premise, so a deck that violates it does not get a bar.

### Why the block is committed into the deck

The deck stays a self-contained artifact: plain `marp slides.md` and the VS Code
Marp extension both render the bar with no plumbing, and a fresh clone is correct
before anything runs. The rules key on `section[id="N"]` because Marp numbers
slides in document order and emits that id. The attribute selector is required:
`section#3` is invalid CSS, since an ident cannot start with a digit.

## The media pipeline

`make gif` renders one PNG per slide natively with Marp (`--images png`, 2x),
computes each slide's hold time from its own word count, then stitches an mp4
(ffmpeg concat demuxer) and a two-pass palette GIF.

```
seconds = clamp(READ_BASE + words / WPM * 60, SLIDE_MIN, SLIDE_MAX)
```

A dense bullet slide dwells longer than a title card, with no edit. Clamp
overrides are flagged in the printed table, never applied silently.

**Reading-speed profiles** build from one frame render: `readable` (180 wpm, for a
self-running explainer), `punchy` (260, the default), `teaser` (340, motion
preview). `make variants` builds all three; `DEFAULT_PROFILE` picks the canonical
GIF that `make publish` copies out.

Ad-hoc tuning: `make gif WPM=220 SLIDE_MAX=8`, `make gif GIF_HEIGHT=360 GIF_FPS=3`.

## Diagrams

Marp has **no Mermaid runtime**: a fenced mermaid block renders as a code listing.
Write the diagram as `assets/<name>.md`, run `make diagrams`, embed the PNG
(`mmdc` appends the fence index, so `foo.md` becomes `foo-1.png`). Sources are
committed; the PNGs are git-ignored build outputs.

An SVG in `assets/` embeds directly, and is the better choice for architecture
diagrams: it stays editable, and a transparent canvas sits on any slide
background. If light labels must also read on a white editing canvas, give each
node its own dark chip rather than relying on the slide's background.

Both `assets/*.md` and `assets/*.svg` are wired into the build DAG, so editing one
rebuilds only what changed. **Anything the deck embeds must be a prerequisite of
the frame stamp**, or the render silently serves stale frames.

## Gotchas that cost real time

- **`make` caches file timestamps.** A recipe that rewrites the deck mid-run is
  invisible to rules that already stat'd it, so frames get served from the
  pre-retune deck. That is why the tier sync is a parse-time `$(shell ...)` and
  not a prerequisite. Never "simplify" it into a prerequisite.
- **A `.PHONY` prerequisite is perpetually newer.** Adding one to the frame stamp
  forces a full Marp re-render on every call and destroys the stamp's purpose,
  which is rendering once for three variants.
- **A `---` inside a fenced code block is not a slide break.** Marp resolves
  fences before horizontal rules. A splitter without fence tracking counts a
  phantom slide, and every fraction after it lands on the wrong slide, silently.
  Any deck documenting its own syntax hits this.
- **The generated block must never contain a literal `@tier <name>`.** It lives
  inside slide 1, so the parser would read it back as a real marker, and a nested
  `-->` would close the comment early and leak text onto the slide.
- **Two decks, one build dir.** Frames are namespaced `build/frames/$(NAME)`. A
  shared frames dir lets one deck's PNGs sit behind a stamp the other treats as
  its own: a GIF of the wrong deck, with no warning.
- **Marp comments shaped `key: value` are parsed as directives.** That is why the
  marker is `@tier name`, with no colon.
- **`--pptx-editable` needs LibreOffice**, not just Chrome. The target checks and
  fails with an install hint rather than quietly emitting a raster deck.
- **Frames and slides must be 1:1.** The pacing script refuses a playlist when the
  counts disagree, because a misaligned playlist pairs the wrong duration with the
  wrong frame and nothing looks broken.

## Theming

The scaffold derives the palette from a project's design-tokens JSON
(`themes.dark`, or `themes.<defaultTheme>`), so the deck and the product read as
one system. Without `--tokens` it writes an obvious placeholder palette and says
so in the theme's header.

The theme owns the bar's **geometry**; the generated block owns its **segments**.
Keep that split. It is what lets a project change its audiences without touching
CSS.
