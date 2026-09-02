# Host-Themed Renderers: Translucent Dual-Theme Fills

Part of the **Mermaid color theming** family — see
[`color_theming.md`](color_theming.md) for the baseline model (the GitHub/`mmdc`
case: opaque `fill` + explicit `color:`). This file covers the advanced case
where that model breaks: renderers whose **host page theme controls the Mermaid
label text** and re-themes it when the reader flips light/dark. **Material for
MkDocs** is the common one.

The baseline assumes **you** control the text colour. Some integrations break
that assumption — the host injects its own CSS variables into Mermaid, so

- the label text is forced to `--md-mermaid-label-fg-color` (dark in light mode,
  light in dark mode) and **overrides any `color:`** you set on a `classDef`;
- your `fill:` *is* respected.

This voids the
[§3 rule](color_theming.md#3-light-mode--dark-mode-safety) ("always pair `fill:`
with `color:`"): your text colour is ignored, so a fill chosen for white text
turns unreadable the instant the host flips the text. A dark fill under dark
forced-text (light mode), or a light fill under light forced-text (dark mode),
vanishes.

## The fix: let the page background bleed through a translucent fill

Don't fight the host. **Drop `color:`** (anchor to the host's theme text) and make the
**fill translucent** with 8-digit hex alpha. The page background then composites *through*
the fill, so a single constant colour auto-tints to the right side of the forced text:

- light theme → fill over a light page → a **pale** box → the forced **dark** text reads;
- dark theme → fill over a dark page → a **dark** box → the forced **light** text reads.

Carry the category hue in an **opaque stroke** — the fill is only a faint tint, so the
border does the visual identification.

```
%% Host forces the text colour per theme; we deliberately set NO color:.
%% Translucent fill (alpha ~0x33 ≈ 20%) tints with the page bg in BOTH themes;
%% the opaque stroke carries the hue. Verified AAA light + dark (see math below).
classDef entity  fill:#1d4ed836,stroke:#3b82f6,stroke-width:2px
classDef danger  fill:#dc262636,stroke:#ef4444,stroke-width:2px
classDef neutral fill:#52525b36,stroke:#71717a,stroke-width:1px
```

## The compositing math

Browsers composite opacity in gamma-encoded sRGB ("simple alpha over"). For a fill `F` at
alpha `a` on page background `B`, with host text `T` at alpha `a_t`:

```
box   = a*F   + (1-a)*B        # the visible box colour (per theme, since B differs)
text  = a_t*T + (1-a_t)*box    # the text sits ON the box
ratio = WCAG21(text, box)      # standard relative-luminance contrast
```

Two constraints (light **and** dark), two knobs per hue (base hue `F`, alpha `a`). Because
`B` differs by theme, one `(F, a)` gives a lighter box on light and a darker box on dark —
which is exactly what tracks the host's flipped text. **Lower alpha → higher contrast** (box
closer to the page bg) but a fainter tint; **higher alpha → more vivid** but risk of failing
one theme. Solve for the **highest alpha whose worst-of-both-themes contrast still clears the
target**: AAA (7:1) is typically reachable at `a ≈ 0.18–0.21`; AA (4.5:1) opens up to
`a ≈ 0.50`.

## Anchor the host text + bg — extract, don't guess

The forced colours depend on the host's theme config, so read them rather than assume. With
the site open in a browser, read the CSS variables off `document.body` in each theme:

| Value | Material CSS variable |
|-------|------------------------|
| Page background | `--md-default-bg-color` |
| Mermaid label text | `--md-mermaid-label-fg-color` |

Material's stock theme resolves to roughly **light**: text `#36464e` on `#ffffff`; **dark**:
a ~86%-light grey at `α0.82` over a `~rgb(30,33,41)` slate. Treat these as the anchored `T`
and `B` per theme, then solve `a` per hue. (`scripts/mermaid_contrast.ts --profile
mkdocs-material` bakes these in and runs the both-theme check for you.)

## Verifying — gotchas that cost time

- **Toggle themes via the real palette control**, not by setting the `data-md-color-scheme`
  attribute in JS — Material re-renders Mermaid on a genuine palette switch; a scripted
  attribute change tears the diagram down *without* re-rendering, leaving an empty node.
- **The rendered Mermaid DOM is awkward to query** and renders on a delay / on scroll-into-view.
  The reliable ground truth is a **screenshot per theme** plus the CSS-variable read above —
  not `getComputedStyle` on individual nodes.
- `color_contrast.ts` compares two *opaque* colours; for a translucent fill, composite it over
  the page bg first (`box = a*F+(1-a)*B`) and pass the resulting opaque `box` (and composited
  `text`).
- 8-digit-hex alpha fills need a modern Mermaid (v10+); Material's bundled Mermaid is fine.
