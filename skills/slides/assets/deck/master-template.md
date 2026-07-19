---
marp: true
theme: {{DECK_NAME}}
paginate: true
footer: 'Master template: every layout this deck offers'
---

<!--
MASTER TEMPLATE: the reference for what you can use in slides.md.

This is a REAL, BUILDABLE deck, not a snippet dump:

    make template          # -> build/master-template.html, then open it

Every slide shows a construct AND its source, so what you read is what renders.
If a construct is not here, it is not supported. Add it to the theme and document
it here in the same change, or each deck will invent its own markup.

Escaping note: source examples sit in fenced code blocks, and the fences write
Marp directives WITHOUT their comment brackets. A real directive inside a fence
still applies to the slide, and a real `@tier` marker there would be read as this
slide's tier. The fences say `_class: lead`; you write it wrapped in a comment.
-->

<!-- _class: lead -->
<!-- _paginate: false -->

# Master template

## Every layout, style and directive available

**Build it, read it, copy from it.**
`make template`

---

<!-- _class: divider -->
<!-- @tier exec -->

# Slide anatomy

### Breaks, directives, and the two derived things

---

<!-- @tier exec -->

## The mechanics

- **Slides break on a lone `---`**: that exact line, nothing else on it. Both
  helper scripts parse the deck with this rule.
- **Per-slide directives are HTML comments** starting `_` (underscore = this
  slide only): `_class`, `_paginate`, `_footer`, `_backgroundColor`.
- **Deck-wide config is the YAML front-matter** at the top: `theme`, `paginate`,
  `footer`.
- **Audience tier is one marker per slide**: the comment `@tier exec`, naming a
  tier from `tiers.toml`. The bar derives from it. You never write a fraction.

```markdown
---

_class: lead          <- as an HTML comment
_paginate: false      <- as an HTML comment
@tier mgmt            <- as an HTML comment

# Slide title
```

---

<!-- @tier exec -->

## What is derived, never typed

| Derived | From | Command |
|---|---|---|
| Progress-bar fraction and segments | each slide's `@tier` marker, plus `tiers.toml` | `make progress` |
| GIF and video hold time | each slide's readable word count | `make durations` |

<div class="box">

**Both fail loudly rather than guess.** An unknown or out-of-order tier stops the
build. A frame/slide count mismatch refuses to emit a pacing playlist.

</div>

---

<!-- _class: divider -->
<!-- @tier mgmt -->

# Slide classes

### `lead` · `divider` · default

---

<!-- @tier mgmt -->

## Class: default

The workhorse. `h1` takes the accent underline. Use it for anything with a title
and content.

```markdown
# Class: default        <- no _class directive at all
```

**`lead`**: centred hero, oversized `h1`, no underline. Slide 1 of this deck.
**`divider`**: section break, deeper bleed, accent `h1`, centred. Slide 2.

<div class="box">

Combine directives freely: `_class: lead` plus `_paginate: false` is the standard
title-card pairing.

</div>

---

<!-- _class: divider -->
<!-- @tier mgmt -->

# This is `divider`

### A section break, with `h3` as the subtitle

---

<!-- @tier lead -->

## Inline text styles

- **Bold** is the accent colour. Use it to carry the point, not to decorate.
- *Italic* renders muted and upright. It de-emphasises, it does not stress.
- `inline code` is accent-on-deep, in the mono face.
- [Links](https://marp.app) take the accent, without an underline.
- Bullet markers take the accent. Nest sparingly: one level reads, two does not.

1. Ordered lists work the same
2. Numbers inherit the body colour

> Blockquote: accent left-rule, light weight. Good for a **claim** you want to
> sit apart from the argument.

---

<!-- @tier lead -->

## Two columns

<div class="columns">
<div>

### Left
Any markdown works inside a column: lists, code, images.

- one
- two

</div>
<div>

### Right
The grid is 1fr 1fr with a 1.2em gap.

**Blank lines matter.** Without them, markdown inside a `<div>` does not parse.

</div>
</div>

```markdown
<div class="columns">
<div>

### Left

</div>
<div>

### Right

</div>
</div>
```

---

<!-- @tier lead -->

## Boxes and badges

<div class="columns">
<div class="box">

### `.box`
Surface fill, accent left-rule. The callout for a claim, caveat or definition.

</div>
<div class="box">

### Nesting
A `.box` inside `.columns` is the standard two-up card layout.

</div>
</div>

<span class="badge">.badge: for the one line they must remember</span>

```markdown
<div class="box">...</div>
<span class="badge">...</span>
```

---

<!-- @tier ic -->

## Tables

| Construct | Use it for | Avoid when |
|---|---|---|
| Table | short enumerable facts | prose belongs in the cells |
| `.box` | one claim that must sit apart | the whole slide is the claim |
| Columns | two parallel things | the second column is filler |

The header row is dark-on-accent. Keep tables to about 4 columns at 22px, or they
compress past readability.

---

<!-- @tier ic -->

## Code blocks

```python
def slide_seconds(words: int, *, wpm: float, base: float) -> float:
    """Fenced blocks: bordered, 20px, mono, syntax-highlighted."""
    return base + words / wpm * 60.0
```

- **Keep them under about 12 lines.** A slide is not a file viewer.
- The pacing script strips code from its word count, so a code slide holds at the
  floor (`SLIDE_MIN`) in the GIF unless it has prose too. Give it a sentence.

---

<!-- @tier ic -->

## Diagrams: Mermaid, pre-rendered

![w:880](assets/build-pipeline-1.png)

That image is **rendered from `assets/build-pipeline.md`**, which is committed;
the PNG is not. Marp has no Mermaid runtime, so a fenced mermaid block inside a
slide renders as a code listing. Edit the source, then rebuild.

```markdown
![w:880](assets/build-pipeline-1.png)   <- mmdc appends the -1
```

---

<!-- @tier ic -->

## Diagrams: editable draw.io SVG

![w:820](assets/example-architecture.svg)

One file, two jobs: the image above, **and** a real draw.io document. The
`content` attribute carries an `<mxfile>`, so diagrams.net reopens movable shapes.

- **Mermaid** for flows, where the layout should solve itself.
- **draw.io SVG** for architecture, where you want icons and hand placement.

---

<!-- @tier ic -->

## How a diagram reaches a slide

Both paths are wired into the build DAG, and that wiring is the point:

- **Content is the source.** A Mermaid `.md` or an SVG is committed and diffable.
  The `-1.png` renders are git-ignored build outputs.
- **`make diagrams` renders only what changed**, through a pattern rule.
- **Every render depends on the diagram**, so editing one rebuilds the deck.
  Leave a diagram out of `SVG_SRC`/`MMD_SRC` and the deck ships a stale picture
  with no warning.
- **The palette came from the project's design tokens** at scaffold time, so a
  diagram matches the theme without anyone picking a colour.

<span class="badge">A diagram is content, not an attachment. Generate it, wire it, never paste it.</span>

---

<!-- @tier ic -->

## The progress bar you have been watching

<div class="columns">
<div class="box">

### The rule
Tiers run top-down and contiguous, in the order `tiers.toml` declares. Out of
order or interleaved is a build error.

</div>
<div class="box">

### The maths
`p = (tier_index + (i+1)/n) / T` for slide `i` of a tier of `n`, across `T`
tiers. Computed, then written into the managed `<style>` block.

</div>
</div>

<span class="badge">Tag the slide. Run make progress. Never touch a fraction.</span>
