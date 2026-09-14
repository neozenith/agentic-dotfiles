#!/usr/bin/env -S uv run python
"""Illustrate Q11 x Q3 for the categorical walk as one 2x2 choice.

Q11 is the chroma axis:    one chroma for every slot, or each hue's own maximum.
Q3 is the lightness axis:  one stated lightness for every slot, or a lightness solved per slot
                           and per mode to hit a contrast target.

They overlap because the chroma available to a hue depends on its lightness, so the chroma rule
cannot be judged until the lightness rule is known.

Everything is computed from osakanights' seed accent and the locked DT-REF-1 grounds. Writes
docs/plans/refactor-design-tokens/Q11-Q3-walk.md for md2html.py --inline.
"""

from __future__ import annotations

import itertools
import json
import logging
import math
from pathlib import Path

log = logging.getLogger(__name__)

OUT = Path("docs/plans/refactor-design-tokens/Q11-Q3-walk.md")

SEED_HEX = "#5c4295"  # osakanights light accent
SLOTS = 12
GOLDEN = 137.5
GRAPHIC = 3.0  # WCAG 2.2 SC 1.4.11, a chart mark or node border against its ground
TINT_ALPHA = 0.16  # how this page draws a node fill; illustration only, not a decision

GROUNDS = {
    "dark": {"surface.sunken": 0.10, "surface": 0.15, "surface.raised": 0.20, "text": 1.00},
    "light": {"surface.sunken": 0.85, "surface": 0.90, "surface.raised": 0.95, "text": 0.00},
}
GROUND_KEYS = ("surface.sunken", "surface", "surface.raised")

RGB = tuple[int, int, int]

_LMS_FROM_LAB = ((1.0, 0.3963377774, 0.2158037573), (1.0, -0.1055613458, -0.0638541728),
                 (1.0, -0.0894841775, -1.2914855480))
_RGB_FROM_LMS = ((4.0767416621, -3.3077115913, 0.2309699292), (-1.2684380046, 2.6097574011, -0.3413193965),
                 (-0.0041960863, -0.7034186147, 1.7076147010))
_LMS_FROM_RGB = ((0.4122214708, 0.5363325363, 0.0514459929), (0.2119034982, 0.6806995451, 0.1073969566),
                 (0.0883024619, 0.2817188376, 0.6299787005))
_LAB_FROM_LMS = ((0.2104542553, 0.7936177850, -0.0040720468), (1.9779984951, -2.4285922050, 0.4505937099),
                 (0.0259040371, 0.7827717662, -0.8086757660))


def _mul(m: tuple, v: tuple) -> tuple[float, float, float]:
    return tuple(sum(row[i] * v[i] for i in range(3)) for row in m)  # type: ignore[return-value]


def _to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def oklch_to_lin(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    rad = math.radians(hue)
    lms = _mul(_LMS_FROM_LAB, (lightness, chroma * math.cos(rad), chroma * math.sin(rad)))
    return _mul(_RGB_FROM_LMS, tuple(x**3 for x in lms))


def oklab(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    rad = math.radians(hue)
    return (lightness, chroma * math.cos(rad), chroma * math.sin(rad))


def in_gamut(lightness: float, chroma: float, hue: float) -> bool:
    return all(-1e-4 <= c <= 1 + 1e-4 for c in oklch_to_lin(lightness, chroma, hue))


def max_chroma(lightness: float, hue: float) -> float:
    lo, hi = 0.0, 0.4
    for _ in range(26):
        mid = (lo + hi) / 2
        lo, hi = (mid, hi) if in_gamut(lightness, mid, hue) else (lo, mid)
    return lo


def rgb(lightness: float, chroma: float, hue: float) -> RGB:
    return tuple(round(_to_srgb(c) * 255) for c in oklch_to_lin(lightness, chroma, hue))  # type: ignore[return-value]


def grey(lightness: float) -> RGB:
    v = round(_to_srgb(max(min(lightness, 1.0), 0.0) ** 3) * 255)
    return (v, v, v)


def hexof(c: RGB) -> str:
    return "#{:02x}{:02x}{:02x}".format(*c)


def lum(c: RGB) -> float:
    r, g, b = (_to_lin(x / 255) for x in c)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a: RGB, b: RGB) -> float:
    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def over(fg: RGB, alpha: float, bg: RGB) -> RGB:
    return tuple(round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg))  # type: ignore[return-value]


def seed_oklch() -> tuple[float, float, float]:
    h = SEED_HEX.lstrip("#")
    lin = tuple(_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    lms = _mul(_LMS_FROM_RGB, lin)
    lab = _mul(_LAB_FROM_LMS, tuple(math.copysign(abs(x) ** (1 / 3), x) for x in lms))
    return lab[0], math.hypot(lab[1], lab[2]), math.degrees(math.atan2(lab[2], lab[1])) % 360


SEED_L, SEED_C, SEED_H = seed_oklch()
HUES = [(SEED_H + i * GOLDEN) % 360 for i in range(SLOTS)]


def min_ground_contrast(colour: RGB, mode: str) -> float:
    return min(contrast(colour, grey(GROUNDS[mode][g])) for g in GROUND_KEYS)


def solve_lightness(hue: float, mode: str, chroma_for: callable) -> float:
    """Nearest lightness to the seed that clears 3:1 against every ground of the mode."""
    for step in range(0, 201):
        for sign in (1, -1):
            lightness = SEED_L + sign * step * 0.005
            if not 0.0 <= lightness <= 1.0:
                continue
            if min_ground_contrast(rgb(lightness, chroma_for(lightness, hue), hue), mode) >= GRAPHIC:
                return lightness
    return SEED_L


def build(option: str, mode: str) -> list[tuple[float, float, float]]:
    """Return (L, C, H) per slot for one option in one mode."""
    solved, per_slot_max = option in ("C", "D", "E"), option in ("B", "D")
    if option == "E":  # each hue at its own maximum, but never above the seed's chroma
        def capped(lightness: float, hue: float) -> float:
            return min(max_chroma(lightness, hue), SEED_C)

        return [(lt, capped(lt, h), h) for h in HUES for lt in [solve_lightness(h, mode, capped)]]
    if not solved:
        lights = [SEED_L] * SLOTS
    else:
        lights = [solve_lightness(h, mode, max_chroma) for h in HUES]
    if per_slot_max:
        return [(lt, max_chroma(lt, h), h) for lt, h in zip(lights, HUES)]
    equal = min(max_chroma(lt, h) for lt, h in zip(lights, HUES))
    if solved:  # lower chroma shifts luminance slightly, so re-solve at the equal chroma
        lights = [solve_lightness(h, mode, lambda _lt, _h: equal) for h in HUES]
        equal = min(max_chroma(lt, h) for lt, h in zip(lights, HUES))
    return [(lt, equal, h) for lt, h in zip(lights, HUES)]


OPTIONS = {
    "A": ("One lightness, one chroma", "stated", "equal"),
    "B": ("One lightness, each hue at its own maximum chroma", "stated", "per-slot max"),
    "C": ("Lightness solved per mode, one chroma", "solved", "equal"),
    "D": ("Lightness solved per mode, each hue at its own maximum chroma", "solved", "per-slot max"),
    "E": ("Lightness solved per mode, each hue at its own maximum chroma capped at the seed's",
          "solved", "per-slot max, capped at seed"),
}


def metrics(option: str, mode: str) -> dict[str, float]:
    slots = build(option, mode)
    colours = [rgb(*s) for s in slots]
    marks = [min_ground_contrast(c, mode) for c in colours]
    text = grey(GROUNDS[mode]["text"])
    surface = grey(GROUNDS[mode]["surface"])
    labels = [contrast(text, over(c, TINT_ALPHA, surface)) for c in colours]
    labs = [oklab(*s) for s in slots]
    separation = min(math.dist(a, b) for a, b in itertools.combinations(labs, 2))
    return {
        "mark_min": min(marks),
        "mark_fail": sum(m < GRAPHIC for m in marks),
        "label_min": min(labels),
        "chroma_mean": sum(s[1] for s in slots) / SLOTS,
        "sep": separation,
        "l_span": max(s[0] for s in slots) - min(s[0] for s in slots),
    }


def panel(option: str, mode: str) -> str:
    slots = build(option, mode)
    surface = grey(GROUNDS[mode]["surface"])
    text = hexof(grey(GROUNDS[mode]["text"]))
    bars, nodes = [], []
    for i, s in enumerate(slots):
        c = rgb(*s)
        ratio = min_ground_contrast(c, mode)
        flag = "" if ratio >= GRAPHIC else "&#10007;"
        height = 38 + (i * 37) % 70
        bars.append(
            f'<div style="flex:1;display:flex;flex-direction:column;justify-content:flex-end;align-items:center">'
            f'<div style="width:100%;height:{height}px;background:{hexof(c)};border-radius:3px 3px 0 0"></div>'
            f'<div style="font:10px system-ui;color:{text};opacity:.75;margin-top:3px">{ratio:.1f}{flag}</div></div>'
        )
    for i, name in enumerate(("Apples", "Mandarins", "Peaches", "Pears", "Plums", "Figs")):
        c = rgb(*slots[i])
        fill = over(c, TINT_ALPHA, surface)
        nodes.append(
            f'<div style="flex:1;background:{hexof(fill)};border:2px solid {hexof(c)};border-radius:8px;'
            f'padding:8px 6px;text-align:center;font:600 12px system-ui;color:{text}">{name}</div>'
        )
    return (
        f'<div style="background:{hexof(surface)};padding:14px;border-radius:10px;margin:8px 0 4px">'
        f'<div style="display:flex;gap:4px;height:130px">{"".join(bars)}</div>'
        f'<div style="display:flex;gap:6px;margin-top:12px">{"".join(nodes)}</div></div>'
    )


def deck_block(option: str) -> str:
    """An OKLCH orbit scene: both modes' slots, the seed, sRGB gamut rings and the seed-chroma circle."""
    points = [{"hex": SEED_HEX, "label": "seed accent"}]
    lightnesses = {round(SEED_L, 2)}
    for mode in ("dark", "light"):
        for i, s in enumerate(build(option, mode), start=1):
            points.append({"hex": hexof(rgb(*s)), "label": f"{mode} slot {i}"})
            lightnesses.add(round(s[0], 2))
    rings = sorted(lightnesses)
    if len(rings) > 3:
        rings = [rings[0], rings[len(rings) // 2], rings[-1]]
    payload = {
        "view": "orbit",
        "space": "oklch",
        "height": 480,
        "gamut": rings,
        "targetChroma": round(SEED_C, 3),
        "layers": [{"type": "PointCloudLayer", "pointSize": 12, "data": points}],
    }
    return f"```deckgl\n{json.dumps(payload, indent=1)}\n```"


def summary_row(option: str) -> str:
    d, lt = metrics(option, "dark"), metrics(option, "light")
    fails = d["mark_fail"] + lt["mark_fail"]
    return (
        f"| **{option}** | {OPTIONS[option][1]} | {OPTIONS[option][2]} | "
        f"{d['mark_min']:.2f} / {lt['mark_min']:.2f} | **{fails}** of 24 | "
        f"{d['chroma_mean'] / SEED_C:.0%} / {lt['chroma_mean'] / SEED_C:.0%} | "
        f"{d['sep']:.3f} / {lt['sep']:.3f} |"
    )


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    sections = []
    for key, (title, light_rule, chroma_rule) in OPTIONS.items():
        d, lt = metrics(key, "dark"), metrics(key, "light")
        sections.append(f"""
---

## Option {key}: {title}

Lightness **{light_rule}**, chroma **{chroma_rule}**.

### Dark
{panel(key, "dark")}

Weakest bar against the grounds **{d['mark_min']:.2f}:1**, bars under 3:1 **{d['mark_fail']}**,
lightness varies across slots by **{d['l_span']:.2f}**, chroma kept **{d['chroma_mean'] / SEED_C:.0%}** of the seed.

### Light
{panel(key, "light")}

Weakest bar against the grounds **{lt['mark_min']:.2f}:1**, bars under 3:1 **{lt['mark_fail']}**,
lightness varies across slots by **{lt['l_span']:.2f}**, chroma kept **{lt['chroma_mean'] / SEED_C:.0%}** of the seed.

### In OKLCH space

All 24 slots from both modes, plus the seed accent. Rings are the sRGB gamut edge at the listed
lightnesses; the circle is the seed's chroma, and a spoke marks every slot that falls short of it.

{deck_block(key)}
""")

    doc = f"""# Q11 and Q3: how the categorical walk gets its lightness and chroma

Q11 and Q3 are two axes of one choice about the 12 `color.chart.categorical.<N>` slots.

| | Chroma: **one value for every slot** | Chroma: **each hue at its own maximum** |
|---|---|---|
| Lightness: **one stated value** | **A** | **B** |
| Lightness: **solved per mode** | **C** | **D** |

**E** is D with a ceiling: each hue takes its own maximum chroma, but never more than the seed
accent's chroma, so no categorical colour is louder than the brand.

- **Q11 is the chroma axis.** One chroma keeps every slot equally saturated, but the whole walk is
  limited by its weakest hue. Each hue's maximum is vivid but uneven, and can exceed the brand's own
  chroma unless capped.
- **Q3 is the lightness axis.** A stated lightness is one number in the seed. A solved lightness is
  found per slot and per mode, as the value nearest the seed's that keeps the colour at 3:1 against
  every ground.
- **Why they overlap:** how much chroma a hue can have depends on its lightness, so the chroma rule
  cannot be judged until the lightness rule is fixed.

Categorical slots are assigned in sequence purely for visual separation (DT-CAT-1). The nodes below
are labelled with fruit to keep that in view.

### How to read each panel

- **Bars** are solid slot colours on `color.surface`. The number under each bar is its weakest
  contrast against the three grounds. A cross marks a bar under 3:1 (WCAG 2.2 SC 1.4.11).
- **Nodes** show text on a background colour: `color.text` on the slot colour at
  {TINT_ALPHA:.0%} over the surface, with a solid slot border. The tint is only how this page draws a
  node, not a decision.

Seed: `osakanights` accent `{SEED_HEX}`, OKLCH `L {SEED_L:.3f}  C {SEED_C:.3f}  H {SEED_H:.1f}°`.
Grounds are the locked DT-REF-1 values.
{"".join(sections)}
---

## Compare

Values are given as **dark / light**.

| Option | Lightness | Chroma | Weakest bar | Bars under 3:1 | Chroma kept | Closest pair ΔE<sub>OK</sub> |
|---|---|---|---|---|---|---|
{summary_row("A")}
{summary_row("B")}
{summary_row("C")}
{summary_row("D")}
{summary_row("E")}

- **Closest pair ΔE<sub>OK</sub>** is the distance between the two most similar slots in OKLab. It
  measures visual separation, which is what the walk is for, so larger is better.
- **Text on the node fills** passes AAA in every option, so the options differ on the bars rather
  than on text.

## What Q3 means outside the walk

For the neutral roles, Q3 changes nothing you can see. The DT-REF-1 offsets already give every text
pairing AAA (worst 9.69:1), so solving them against a target would produce the same values. The
overlap with Q11 is entirely in the walk.
"""
    OUT.write_text(doc, encoding="utf-8")
    for key in OPTIONS:
        log.info("%s dark %s light %s", key, metrics(key, "dark"), metrics(key, "light"))
    log.info("wrote %s", OUT)


if __name__ == "__main__":
    main()
