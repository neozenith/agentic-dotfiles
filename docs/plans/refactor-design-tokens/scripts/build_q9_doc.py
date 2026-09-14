#!/usr/bin/env -S uv run python
"""Generate the Q9 decision document: opaque vs alpha `color.border`, and `color.border.bold`.

Every colour is computed from the locked DT-REF-1 ramp (OKLCH, chroma 0), never typed by
hand. Alpha is composited in 8-bit sRGB, which is what browsers do, before contrast is
measured, so every ratio on the page is the ratio a reader actually sees.

Writes docs/plans/refactor-design-tokens/Q9-borders.md for md2html.py --inline.
"""

from __future__ import annotations

import logging
from pathlib import Path

log = logging.getLogger(__name__)

OUT = Path("docs/plans/refactor-design-tokens/Q9-borders.md")

# DT-REF-1 locked ramp, OKLCH L.
GROUNDS = ("surface.sunken", "surface", "surface.raised")
RAMP = {
    "dark": {"surface.sunken": 0.10, "surface": 0.15, "surface.raised": 0.20, "text.subtle": 0.80, "text": 1.00},
    "light": {"surface.sunken": 0.85, "surface": 0.90, "surface.raised": 0.95, "text.subtle": 0.25, "text": 0.00},
}

ALPHA = 0.14  # Atlassian --ds-border ships #0B120E24, i.e. 14%
GRAPHIC = 3.0  # WCAG 2.2 SC 1.4.11

RGB = tuple[int, int, int]


def lin_to_srgb(v: float) -> float:
    v = min(max(v, 0.0), 1.0)
    return v * 12.92 if v <= 0.0031308 else 1.055 * v ** (1 / 2.4) - 0.055


def srgb_to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def grey(lightness: float) -> RGB:
    """Achromatic OKLCH: Y = L**3."""
    v = round(lin_to_srgb(max(min(lightness, 1.0), 0.0) ** 3) * 255)
    return (v, v, v)


def hexof(rgb: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*rgb)


def lum(rgb: RGB) -> float:
    r, g, b = (srgb_to_lin(c / 255) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: RGB, b: RGB) -> float:
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def over(fg: RGB, alpha: float, bg: RGB) -> RGB:
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))  # type: ignore[return-value]


def solve_bold(mode: str) -> float:
    """Nearest L that reaches 3:1 on EVERY ground, walking toward the text end."""
    grounds = [grey(RAMP[mode][g]) for g in GROUNDS]
    steps = range(0, 101) if mode == "light" else range(100, -1, -1)
    ok = [i / 100 for i in steps if all(contrast(grey(i / 100), g) >= GRAPHIC for g in grounds)]
    # dark mode wants the darkest passing L, light mode the lightest passing L
    return min(ok) if mode == "dark" else max(ok)


def border_models(mode: str) -> dict[str, dict[str, RGB]]:
    ink = grey(RAMP[mode]["text"])
    alpha = {g: over(ink, ALPHA, grey(RAMP[mode][g])) for g in GROUNDS}
    opaque_value = alpha["surface"]  # fair fight: identical on `surface`
    return {"alpha": alpha, "opaque": {g: opaque_value for g in GROUNDS}}


def strip(mode: str, model: str, bold_l: float) -> str:
    models = border_models(mode)
    text, subtle = hexof(grey(RAMP[mode]["text"])), hexof(grey(RAMP[mode]["text.subtle"]))
    bold = hexof(grey(bold_l))
    cells = []
    for g in GROUNDS:
        bg = grey(RAMP[mode][g])
        line = models[model][g]
        ratio = contrast(line, bg)
        cells.append(f"""<div style="flex:1;background:{hexof(bg)};padding:14px;border-radius:8px;font:13px system-ui,sans-serif">
  <div style="color:{subtle};font-size:11px;letter-spacing:.06em;text-transform:uppercase">{g}</div>
  <div style="color:{text};padding:9px 0;border-bottom:1px solid {hexof(line)}">Row one</div>
  <div style="color:{text};padding:9px 0;border-bottom:1px solid {hexof(line)}">Row two</div>
  <div style="margin-top:10px;border:1px solid {bold};border-radius:5px;padding:6px 8px;color:{subtle}">Search&hellip;</div>
  <div style="color:{subtle};font-size:11px;margin-top:8px">divider <code>{hexof(line)}</code> {ratio:.2f}:1</div>
</div>""")
    return f'<div style="display:flex;gap:10px;margin:10px 0 18px">{"".join(cells)}</div>'


def ratio_table(model: str) -> str:
    rows = ["| mode | ground | divider renders | contrast |", "|---|---|---|---:|"]
    for mode in ("dark", "light"):
        m = border_models(mode)[model]
        for g in GROUNDS:
            rows.append(f"| {mode} | `{g}` | `{hexof(m[g])}` | {contrast(m[g], grey(RAMP[mode][g])):.2f}:1 |")
    return "\n".join(rows)


def spread(model: str) -> float:
    vals = [
        contrast(border_models(mode)[model][g], grey(RAMP[mode][g]))
        for mode in ("dark", "light")
        for g in GROUNDS
    ]
    return max(vals) - min(vals)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    bold = {mode: solve_bold(mode) for mode in ("dark", "light")}
    bold_offset = {mode: abs(bold[mode] - RAMP[mode]["surface"]) for mode in bold}

    bold_rows = ["| mode | `border.bold` L | hex | offset from `surface` | " + " | ".join(f"on `{g}`" for g in GROUNDS) + " |",
                 "|---|---:|---|---:|" + "---:|" * len(GROUNDS)]
    for mode in ("dark", "light"):
        cells = " | ".join(f"{contrast(grey(bold[mode]), grey(RAMP[mode][g])):.2f}:1" for g in GROUNDS)
        bold_rows.append(f"| {mode} | {bold[mode]:.2f} | `{hexof(grey(bold[mode]))}` | "
                         f"{bold_offset[mode]:.2f} toward text | {cells} |")

    doc = f"""# Q9: borders

Two border roles are locked by DT-ROLES-1 but have no values. This page decides both, using
the locked DT-REF-1 ramp. Every colour and ratio here is computed, not typed.

**The decision:** is `color.border` an **opaque** grey or a **translucent** tint of the text
colour? And what value does `color.border.bold` take?

## Two roles, two jobs

They are not a weak and a strong version of one thing. Atlassian's shipped tokens make the
split explicit:

| Token | Value | Job | Contrast rule |
|---|---|---|---|
| `color.border` | `#0B120E24`, near-black at 14% | decorative divider: table rules, card edges | **exempt.** WCAG 2.2 SC 1.4.11 only covers boundaries *needed to identify* a component |
| `color.border.bold` | `#7D818A`, opaque | functional boundary: an input's edge, a focusable outline | **3:1 required** |

Measured on Atlassian's white surface, `border` renders `#dddedd` at **1.35:1** and
`border.bold` renders at **3.90:1**. A 3:1 divider would not be a hairline; it would be a
visible grey rule on every row.

In every card below, the **rows** use `color.border` and the **search box** uses
`color.border.bold`.

---

## Option A: opaque divider

One grey, chosen so it matches Option B exactly on `surface`. Then placed on all three grounds.

### Dark
{strip("dark", "opaque", bold["dark"])}

### Light
{strip("light", "opaque", bold["light"])}

{ratio_table("opaque")}

**Spread across grounds: {spread("opaque"):.2f}.** The same grey reads differently on each
surface, because its contrast depends on how far each ground is from it.

---

## Option B: translucent divider (text colour at {ALPHA:.0%})

The text colour for the mode, at {ALPHA:.0%} alpha, composited over whatever it sits on.

### Dark
{strip("dark", "alpha", bold["dark"])}

### Light
{strip("light", "alpha", bold["light"])}

{ratio_table("alpha")}

**Spread across grounds: {spread("alpha"):.2f}.** A tint travels with the surface beneath it,
so the divider keeps nearly the same relationship to every ground.

---

## `color.border.bold`: solved, not chosen

Solved as the nearest lightness that reaches 3:1 against **every** ground at once. The hardest
ground differs by mode: in dark mode it is `surface.raised` (lightest, closest to a mid grey);
in light mode it is `surface.sunken` (darkest, closest to a mid grey).

{chr(10).join(bold_rows)}

The two modes land on the **same offset** from `surface`, so `border.bold` fits DT-REF-1 as one
more toward-text parameter with a single default.

---

## Compare

| | A: opaque | B: translucent |
|---|---|---|
| Spread across the three grounds | {spread("opaque"):.2f} | {spread("alpha"):.2f} |
| Variants needed to look consistent | one per ground, or accept drift | one |
| Light to dark rule | re-solve the grey | flip the RGB, keep the alpha |
| Contrast known in the IR | yes, exactly | only once the ground is known |
| Surfaces that must support alpha | none | cytoscape, deck.gl yes; mermaid `themeVariables` and draw.io to verify |
| Precedent | none found for dividers | Atlassian `#0B120E24`; diagram-design `rgba(ink, 0.12)` |

Neither option touches `border.bold`: it is opaque and solved in both.
"""
    OUT.write_text(doc, encoding="utf-8")
    log.info("wrote %s", OUT)
    for mode in ("dark", "light"):
        log.info("border.bold %s L %.2f %s offset %.2f", mode, bold[mode], hexof(grey(bold[mode])), bold_offset[mode])
    log.info("spread opaque %.2f alpha %.2f", spread("opaque"), spread("alpha"))


if __name__ == "__main__":
    main()
