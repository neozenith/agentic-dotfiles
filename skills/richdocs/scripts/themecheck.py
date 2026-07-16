#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Contrast gate for brandpacks. Fails loudly; never "fixes" a theme silently.

This exists because a theme once shipped that was contrast-clean and completely
off-brand: V2 AI's accent is a bright yellow, but `accent` was the token used for
BOTH heading/link text AND button fills. Yellow is 1.64:1 on white, so it cannot
be text. Faced with an impossible token, the pack quietly substituted a cyan that
V2 does not own — and every check passed, because nothing was checking the thing
that mattered.

Two lessons are encoded here:

1. **`accent` has three jobs** and they must be separate tokens:
   - `accent`   — the FILL (surfaces, CTAs, rules). No text-contrast duty.
   - `onAccent` — the text that sits ON that fill.
   - `link`     — the TEXT-SAFE accent (headings, links). Falls back to `accent`.
2. **Check the pairings the CSS actually renders**, not a plausible-looking list.
   Each row below names the real rule it guards.
"""

from __future__ import annotations

import argparse
import json
import sys
from typing import Any

from md2html import THEMES_DIR, available_themes

AA_TEXT = 4.5  # WCAG AA, normal-size text
AA_UI = 3.0  # WCAG 1.4.11, non-text (chart marks against their plot surface)


def _lin(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def luminance(hex_colour: str) -> float:
    h = hex_colour.lstrip("#")
    r, g, b = (int(h[i : i + 2], 16) for i in (0, 2, 4))
    return 0.2126 * _lin(r) + 0.7152 * _lin(g) + 0.0722 * _lin(b)


def contrast(a: str, b: str) -> float:
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def roles(theme: dict[str, str]) -> dict[str, str]:
    """Resolve the accent's three jobs, applying the same fallbacks the viewer does."""
    return {
        **theme,
        "onAccent": theme.get("onAccent", theme["bg"]),
        "link": theme.get("link", theme["accent"]),
    }


# (label, fg-token, bg-token, floor, the CSS rule this guards)
CHECKS: list[tuple[str, str, str, float, str]] = [
    ("body text", "fg", "bg", AA_TEXT, "body { color: fg; background: bg }"),
    ("body on surface", "fg", "surface", AA_TEXT, "card/table/pre"),
    ("muted text", "muted", "bg", AA_TEXT, "captions, .sc-eyebrow"),
    ("heading / link", "link", "bg", AA_TEXT, "h2, main a { color: --rd-link }"),
    ("link on surface", "link", "surface", AA_TEXT, "links inside a card"),
    ("text on accent fill", "onAccent", "accent", AA_TEXT, ".sc-btn, active tab"),
]


CVD_TARGET = 12.0  # Machado-2009 ΔE — the separation a colourblind reader needs
CVD_RELIEF = 8.0  # 8–12 is legal ONLY with an icon/sign carrying the meaning too
DL_FLOOR = 0.06  # minimum OKLab lightness step between ordinal ramp steps


def _srgb_to_linear(c: float) -> float:
    c /= 255
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _oklab(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    r, g, b = (_srgb_to_linear(int(h[i : i + 2], 16)) for i in (0, 2, 4))
    lo = (0.4122214708 * r + 0.5363325363 * g + 0.0514459929 * b) ** (1 / 3)
    mo = (0.2119034982 * r + 0.6806995451 * g + 0.1073969566 * b) ** (1 / 3)
    so = (0.0883024619 * r + 0.2817188376 * g + 0.6299787005 * b) ** (1 / 3)
    return (
        0.2104542553 * lo + 0.7936177850 * mo - 0.0040720468 * so,
        1.9779984951 * lo - 2.4285922050 * mo + 0.4505937099 * so,
        0.0259040371 * lo + 0.7827717662 * mo - 0.8086757660 * so,
    )


def lightness(hex_colour: str) -> float:
    """Perceptual (OKLab) lightness — NOT HSL's, which is a maths convenience."""
    return _oklab(hex_colour)[0]


# Machado-2009 CVD simulation matrices, applied to LINEAR rgb.
MACHADO: dict[str, tuple[tuple[float, float, float], ...]] = {
    "protan": (
        (0.152286, 1.052583, -0.204868),
        (0.114503, 0.786281, 0.099216),
        (-0.003882, -0.048116, 1.051998),
    ),
    "deutan": (
        (0.367322, 0.860646, -0.227968),
        (0.280085, 0.672501, 0.047413),
        (-0.011820, 0.042940, 0.968881),
    ),
    "tritan": (
        (1.255528, -0.076749, -0.178779),
        (-0.078411, 0.930809, 0.147602),
        (0.004733, 0.691367, 0.303900),
    ),
}


def _linear_rgb(hex_colour: str) -> tuple[float, float, float]:
    h = hex_colour.lstrip("#")
    r, g, b = (_srgb_to_linear(int(h[i : i + 2], 16)) for i in (0, 2, 4))
    return r, g, b


def _cielab(rgb: tuple[float, float, float]) -> tuple[float, float, float]:
    """CIELAB (D65) — the space ΔE is defined in. NOT OKLab."""
    r, g, b = rgb
    x = 0.4124564 * r + 0.3575761 * g + 0.1804375 * b
    y = 0.2126729 * r + 0.7151522 * g + 0.0721750 * b
    z = 0.0193339 * r + 0.1191920 * g + 0.9503041 * b

    def f(t: float) -> float:
        return t ** (1 / 3) if t > 0.008856 else 7.787 * t + 16 / 116

    fx, fy, fz = f(x / 0.95047), f(y / 1.0), f(z / 1.08883)
    return 116 * fy - 16, 500 * (fx - fy), 200 * (fy - fz)


def simulate_cvd(hex_colour: str, kind: str) -> tuple[float, float, float]:
    """What a protanope / deuteranope / tritanope sees, in linear rgb."""
    r, g, b = _linear_rgb(hex_colour)
    m = MACHADO[kind]
    return tuple(  # type: ignore[return-value]
        max(0.0, min(1.0, row[0] * r + row[1] * g + row[2] * b)) for row in m
    )


def cvd_distance(a: str, b: str) -> float:
    """Worst-case CIELAB ΔE between two colours across all three CVD types.

    **This is CIE76 ΔE in CIELAB** — deliberately the same metric the design docs
    were derived with. An earlier version used OKLab-Euclidean×100, which is a
    DIFFERENT SCALE: it scored the documented golden-angle palette at 9.2 where the
    authority scored it 18.2, so the palette looked broken, and the "fix" scrambled
    a hue order that was correct. A ruler you have not calibrated against the spec
    is worse than no ruler.
    """
    worst = float("inf")
    for kind in MACHADO:
        la = _cielab(simulate_cvd(a, kind))
        lb = _cielab(simulate_cvd(b, kind))
        worst = min(
            worst, sum((x - y) ** 2 for x, y in zip(la, lb, strict=True)) ** 0.5
        )
    return float(worst)


def check_ramps(name: str, mode: str, plot: dict[str, Any]) -> list[str]:
    """Gate the ramps a brand ships beyond its categorical series.

    These exist because a brand can define a full data-viz system and have five
    sixths of it be unrepresentable — which is exactly what happened. If a ramp is
    in the pack, it is rendered, so it must be checked.
    """
    failures: list[str] = []

    # Sequential encodes MAGNITUDE. If lightness is not monotone, the reader cannot
    # rank the steps, and the ramp is decoration.
    seq = plot.get("sequential")
    if seq:
        ls = [lightness(c) for c in seq]
        if not (
            all(x < y for x, y in zip(ls, ls[1:], strict=False))
            or all(x > y for x, y in zip(ls, ls[1:], strict=False))
        ):
            failures.append(
                f"{name}/{mode}: sequential ramp is not monotone in lightness — "
                "the steps cannot be ranked"
            )
        for i, (x, y) in enumerate(zip(ls, ls[1:], strict=False)):
            if abs(x - y) < DL_FLOOR:
                failures.append(
                    f"{name}/{mode}: sequential steps {i + 1}/{i + 2} differ by "
                    f"ΔL {abs(x - y):.3f} (needs {DL_FLOOR}) — they will read as one"
                )

    # Muted greys must also be rankable, or "de-emphasised" becomes "indistinguishable".
    mut = plot.get("muted")
    if mut:
        ls = [lightness(c) for c in mut]
        if not (
            all(x < y for x, y in zip(ls, ls[1:], strict=False))
            or all(x > y for x, y in zip(ls, ls[1:], strict=False))
        ):
            failures.append(f"{name}/{mode}: muted greys are not monotone in lightness")

    # Diverging: the two POLES must survive colourblindness. This is what makes
    # green↔red structurally impossible to ship — its poles collapse to ΔE ~1-3.
    for key, floor in (("diverging", CVD_TARGET), ("divergingAlt", CVD_RELIEF)):
        div = plot.get(key)
        if not div:
            continue
        good_pole, bad_pole = div["good"][-1], div["bad"][-1]
        got = cvd_distance(good_pole, bad_pole)
        if got < floor:
            failures.append(
                f"{name}/{mode}: {key} poles {good_pole} ↔ {bad_pole} separate by only "
                f"ΔE {got:.1f} under deuteranopia (needs {floor}) · "
                "green↔red fails here by design — pick a CVD-safe pole"
            )
        # A hue at zero makes "no change" look like a value.
        zero = div["zero"]
        _, a, b = _oklab(zero)
        if (a * a + b * b) ** 0.5 > 0.03:
            failures.append(
                f"{name}/{mode}: {key} midpoint {zero} is not neutral — "
                "a hue at zero reads as a value"
            )
    return failures


def check_status(name: str, mode: str, status: dict[str, Any], bg: str) -> list[str]:
    """Status colours are TEXT and must be readable. They are never a chart series."""
    failures: list[str] = []
    for role, colour in status["colours"].items():
        got = contrast(colour, bg)
        if got < AA_TEXT:
            failures.append(
                f"{name}/{mode}: status '{role}' {colour} on {bg} = {got:.2f}:1 "
                f"(needs {AA_TEXT})"
            )
    # Colour must never carry meaning alone.
    missing = set(status["colours"]) - set(status["labels"])
    if missing:
        failures.append(
            f"{name}/{mode}: status {sorted(missing)} have no label — "
            "colour may never carry meaning alone"
        )
    return failures


def check_series(
    name: str,
    mode: str,
    plot: dict[str, Any],
    key: str,
    *,
    waive_contrast: bool = False,
) -> list[str]:
    """A categorical palette: every mark visible on the plot surface, and adjacent
    slots tellable apart by a colourblind reader.

    `series` is the default; `seriesAlt` is an optional deeper/alternate palette. If a
    pack ships `seriesAlt` it is selectable and therefore rendered, so it is gated
    identically — the same lesson as the ramps (ADR-013): shipped means checked.

    `waive_contrast` honours an explicit, documented per-theme waiver: a brandpack may
    declare that its default series is a deliberate low-contrast stylistic identity
    (e.g. a pastel band) that outranks the mark-contrast rule FOR THAT THEME. The
    waiver skips ONLY the mark-vs-plot contrast check, and ONLY for the primary series.
    Adjacent CVD is never waived — a categorical palette must still be distinguishable
    by a colourblind reader, which is what the always-present legend then reinforces
    (ADR-016). No waiver = the strict 3:1 rule, unchanged, for every other pack.
    """
    failures: list[str] = []
    series = plot[key]
    if not waive_contrast:
        for i, colour in enumerate(series):
            got = contrast(colour, plot["plot"])
            if got < AA_UI:
                failures.append(
                    f"{name}/{mode}: {key} {i + 1} — {colour} on {plot['plot']} "
                    f"= {got:.2f}:1 (needs {AA_UI}) · a mark you cannot see is not a mark"
                )
    for i, (a, b) in enumerate(zip(series, series[1:], strict=False)):
        got = cvd_distance(a, b)
        if got < CVD_RELIEF:
            failures.append(
                f"{name}/{mode}: {key} {i + 1}/{i + 2} — {a} vs {b} separate by "
                f"ΔE {got:.1f} under deuteranopia (needs {CVD_RELIEF})"
            )
    return failures


def check_theme(name: str, tokens: dict[str, Any]) -> list[str]:
    """Return a list of failure lines. Empty means the theme is compliant."""
    failures: list[str] = []
    for mode in ("light", "dark"):
        t = roles(tokens["themes"][mode])
        for label, fg, bg, floor, rule in CHECKS:
            got = contrast(t[fg], t[bg])
            if got < floor:
                failures.append(
                    f"{name}/{mode}: {label} — {t[fg]} on {t[bg]} = {got:.2f}:1 "
                    f"(needs {floor}) · guards `{rule}`"
                )

        # Chart marks must be discernible on their plot surface AND tellable apart by
        # a colourblind reader. `seriesAlt` (if shipped) is gated identically. A
        # documented `waivers.seriesContrast` lets a theme keep a deliberate
        # low-contrast identity palette (ADR-016) — printed as a note, never silent.
        plot = tokens["canvas"]["plotly"][mode]
        waive = bool(tokens.get("waivers", {}).get("seriesContrast"))
        if waive:
            low = [
                f"{c} {contrast(c, plot['plot']):.2f}:1"
                for c in plot["series"]
                if contrast(c, plot["plot"]) < AA_UI
            ]
            if low:
                print(
                    f"[note] {name}/{mode}: series mark-contrast waived by design "
                    f"({len(low)} marks below {AA_UI}:1) — CVD adjacency still enforced"
                )
        failures += check_series(name, mode, plot, "series", waive_contrast=waive)
        if plot.get("seriesAlt"):
            failures += check_series(name, mode, plot, "seriesAlt")

        failures += check_ramps(name, mode, plot)

        if "status" in tokens:
            failures += check_status(name, mode, tokens["status"][mode], t["bg"])

        # A graph node's label must be readable on its own fill.
        cy = tokens["canvas"]["cytoscape"][mode]
        got = contrast(cy["nodeLabel"], cy["nodeFill"])
        if got < AA_TEXT:
            failures.append(
                f"{name}/{mode}: graph node label — {cy['nodeLabel']} on {cy['nodeFill']} "
                f"= {got:.2f}:1 (needs {AA_TEXT}) · guards viewer-cytoscape.js"
            )
    return failures


def main(args: argparse.Namespace) -> None:
    names = [args.theme] if args.theme else available_themes()
    if not names:
        print(f"error: no themes installed under {THEMES_DIR}", file=sys.stderr)
        raise SystemExit(1)

    all_failures: list[str] = []
    for name in names:
        pack = THEMES_DIR / name / "design-tokens.json"
        if not pack.is_file():
            print(f"error: unknown theme {name!r}", file=sys.stderr)
            raise SystemExit(1)
        failures = check_theme(name, json.loads(pack.read_text(encoding="utf-8")))
        status = "FAIL" if failures else "pass"
        print(f"[{status}] {name}")
        for line in failures:
            print(f"       {line}")
        all_failures += failures

    if all_failures:
        print(
            f"\n{len(all_failures)} contrast failure(s). "
            "Fix the brandpack — do NOT loosen the check.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    print(f"\nall {len(names)} theme(s) compliant")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="themecheck.py",
        description="Fail if any brandpack renders text that cannot be read.",
    )
    parser.add_argument("--theme", help="Check one theme (default: all installed)")
    return parser


if __name__ == "__main__":  # pragma: no cover
    main(build_parser().parse_args())
