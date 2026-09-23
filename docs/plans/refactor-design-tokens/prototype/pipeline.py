#!/usr/bin/env -S uv run --no-project python
"""Prototype seed -> IR -> DTCG pipeline for the design-token refactor.

A throwaway spike that walks the locked decisions end to end from a seed carrying only the brand accent
(its OKLCH lightness, chroma and hue), so the defaults can be seen propagating before the real curation
tool is designed. Stdlib only.

    seed.json              {"brand.hue": 295.044, ...}           what the user states
    ir.json                every role, both modes, with provenance what curation imputes
    dtcg/*.tokens.json     DTCG 2025.10 colour objects + resolver the only runtime artifact
    design-tokens.json     projection onto richdocs' current schema so showcase.py can render it

Every default parameter carries its source: a decision ID from ../DECISIONS.md, or "prototype" when the
value is not decided yet and exists only so the pipeline can run.

Subcommands: init-seeds, curate, build, install, doc, all.
"""

from __future__ import annotations

import argparse
import itertools
import json
import logging
import math
from pathlib import Path
from typing import Any, Callable

log = logging.getLogger(__name__)

HERE = Path(__file__).resolve().parent
PROFILES = HERE / "profiles"
RICHDOCS_THEMES = Path("skills/richdocs/resources/themes")
PROJECT_THEMES = Path("tmp/richdocs/theme")
SOURCE_THEMES = ("osakanights", "v2ai", "locomotif", "freshgreens")
EXT = "dev.agentic-dotfiles.curation"
MODES = ("light", "dark")
STEP = 0.005

# --------------------------------------------------------------------------------------------------
# Default parameters. Key -> (value, source). A seed overrides any key; everything else is imputed.
# --------------------------------------------------------------------------------------------------
DEFAULTS: dict[str, tuple[Any, str]] = {
    "brand.hue": (None, "DT-ACCENT-1 (required)"),
    "brand.chroma": ("cusp", "CURATION stage 3 (hue-only fallback: the hue's most colourful in-gamut point)"),
    "brand.lightness": ("cusp", "CURATION stage 3 (hue-only fallback; a stated value pins the light accent)"),
    "brand.dark.hue": (None, "DT-ACCENT-1 (defaults to brand.hue)"),
    "brand.dark.chroma": (None, "DT-ACCENT-1 (defaults to brand.chroma)"),
    "brand.dark.lightness": (None, "DT-ACCENT-1 (stated: pins the dark accent verbatim; else solved)"),
    "L-dark-bg": (0.15, "DT-REF-1"),
    "L-light-bg": (0.97, "DT-REF-1 (revised 2026-09-24, was 0.90)"),
    "offset.surface.sunken": (-0.05, "DT-REF-1"),
    "offset.surface.raised": (0.05, "DT-REF-1"),
    "offset.text": (0.90, "DT-REF-1"),
    "offset.text.subtle": (0.65, "DT-REF-1"),
    "target.text.subtlest": (4.5, "WCAG 2.2 SC 1.4.3 (AA: the lowest text tier still reads)"),
    "alpha.border": (0.14, "DT-BORDER-1"),
    "offset.border.bold": (0.35, "DT-BORDER-1 (search start; solved to 3:1)"),
    "target.graphic": (3.0, "WCAG 2.2 SC 1.4.11"),
    "target.text.inverse": (7.0, "DT-CONTRAST-1 (maximise: WCAG 2.2 SC 1.4.6 AAA on the brand fill)"),
    "target.link": (4.5, "WCAG 2.2 SC 1.4.3 (AA text)"),
    "alpha.brand.subtlest": (0.16, "richdocs rdMix 0.84 (the tint already shipped)"),
    "secondary.hue": (None, "DT-ACCENT-1 (defaults to brand.hue)"),
    "secondary.chromaRatio": (0.444, "DT-ACCENT-1 (M3 chroma 16/36)"),
    "offset.background.selected": (0.07, "DT-ACCENT-1 (M3 secondaryContainer sits 0.068 L from its surface)"),
    "walk.slots": (12, "DT-WALK-1"),
    "walk.angle": (137.5, "DT-WALK-1"),
    "walk.lightness": ("brand", "DT-WALK-2 (the seed's lightness: each mode's accent)"),
    "walk.chromaCeiling": ("floor", "DT-WALK-2"),
    "status.hue.danger": (25.0, "CURATION stage 5 (Primer danger.fg 24.6, Tailwind red-600 27.3, M3 error 28.7)"),
    "status.hue.warning": (75.0, "CURATION stage 5 (Primer attention.fg 75.0, a text role)"),
    "status.hue.success": (148.0, "CURATION stage 5 (Primer success.fg 148.0, Tailwind green-600 149.2)"),
    "status.chromaCap": (0.18, "CURATION stage 5 (M3 error chroma 0.178)"),
    "target.status": (4.5, "WCAG 2.2 SC 1.4.3 (AA text)"),
}

# Live-control ranges for the richdocs showcase (generator.json). A key may take a number in
# [min, max], one of its keywords, or both. `walk.slots` is fixed: the projection needs 12 slots.
_HUE = {"min": 0, "max": 360, "step": 0.5}
CONTROLS: dict[str, dict[str, Any]] = {
    "brand.hue": _HUE,
    "brand.chroma": {"keywords": ["cusp"], "min": 0.0, "max": 0.37, "step": 0.005},
    "brand.lightness": {"keywords": ["cusp"], "min": 0.05, "max": 0.95, "step": 0.005},
    "brand.dark.hue": {"keywords": [None], **_HUE},
    "brand.dark.chroma": {"keywords": [None], "min": 0.0, "max": 0.37, "step": 0.005},
    "brand.dark.lightness": {"keywords": [None], "min": 0.05, "max": 0.95, "step": 0.005},
    "L-dark-bg": {"min": 0.0, "max": 0.5, "step": 0.005},
    "L-light-bg": {"min": 0.5, "max": 1.0, "step": 0.005},
    "offset.surface.sunken": {"min": -0.2, "max": 0.2, "step": 0.005},
    "offset.surface.raised": {"min": -0.2, "max": 0.2, "step": 0.005},
    "offset.text": {"min": 0.3, "max": 1.0, "step": 0.01},
    "offset.text.subtle": {"min": 0.2, "max": 0.9, "step": 0.01},
    "target.text.subtlest": {"min": 1.0, "max": 7.0, "step": 0.1},
    "alpha.border": {"min": 0.0, "max": 0.5, "step": 0.01},
    "offset.border.bold": {"min": 0.1, "max": 0.7, "step": 0.01},
    "target.graphic": {"min": 1.0, "max": 7.0, "step": 0.1},
    "target.text.inverse": {"min": 1.0, "max": 21.0, "step": 0.1},
    "target.link": {"min": 1.0, "max": 7.0, "step": 0.1},
    "alpha.brand.subtlest": {"min": 0.0, "max": 0.6, "step": 0.01},
    "secondary.hue": {"keywords": [None], **_HUE},
    "secondary.chromaRatio": {"min": 0.0, "max": 1.0, "step": 0.01},
    "offset.background.selected": {"min": 0.0, "max": 0.4, "step": 0.005},
    "walk.angle": {"min": 1.0, "max": 359.0, "step": 0.5},
    "walk.lightness": {"keywords": ["brand"], "min": 0.2, "max": 0.9, "step": 0.005},
    "walk.chromaCeiling": {"keywords": ["floor", "seed"], "min": 0.0, "max": 0.37, "step": 0.005},
    "status.hue.danger": _HUE,
    "status.hue.warning": _HUE,
    "status.hue.success": _HUE,
    "status.chromaCap": {"min": 0.0, "max": 0.37, "step": 0.005},
    "target.status": {"min": 1.0, "max": 7.0, "step": 0.1},
}

# --------------------------------------------------------------------------------------------------
# Colour maths: OKLCH <-> sRGB (Ottosson matrices), gamut, WCAG contrast, alpha compositing.
# --------------------------------------------------------------------------------------------------
_LMS_FROM_LAB = ((1.0, 0.3963377774, 0.2158037573), (1.0, -0.1055613458, -0.0638541728),
                 (1.0, -0.0894841775, -1.2914855480))
_RGB_FROM_LMS = ((4.0767416621, -3.3077115913, 0.2309699292), (-1.2684380046, 2.6097574011, -0.3413193965),
                 (-0.0041960863, -0.7034186147, 1.7076147010))
_LMS_FROM_RGB = ((0.4122214708, 0.5363325363, 0.0514459929), (0.2119034982, 0.6806995451, 0.1073969566),
                 (0.0883024619, 0.2817188376, 0.6299787005))
_LAB_FROM_LMS = ((0.2104542553, 0.7936177850, -0.0040720468), (1.9779984951, -2.4285922050, 0.4505937099),
                 (0.0259040371, 0.7827717662, -0.8086757660))

LCH = tuple[float, float, float]


def _mul(m: tuple, v: tuple) -> tuple[float, float, float]:
    return tuple(sum(row[i] * v[i] for i in range(3)) for row in m)  # type: ignore[return-value]


def _to_lin(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def _to_srgb(c: float) -> float:
    c = min(max(c, 0.0), 1.0)
    return c * 12.92 if c <= 0.0031308 else 1.055 * c ** (1 / 2.4) - 0.055


def _lin_rgb(lch: LCH) -> tuple[float, float, float]:
    lightness, chroma, hue = lch
    rad = math.radians(hue)
    lms = _mul(_LMS_FROM_LAB, (lightness, chroma * math.cos(rad), chroma * math.sin(rad)))
    return _mul(_RGB_FROM_LMS, tuple(x**3 for x in lms))


def max_chroma(lightness: float, hue: float) -> float:
    if lightness <= 0.0 or lightness >= 1.0:
        return 0.0
    lo, hi = 0.0, 0.4
    for _ in range(26):
        mid = (lo + hi) / 2
        ok = all(-1e-4 <= c <= 1 + 1e-4 for c in _lin_rgb((lightness, mid, hue)))
        lo, hi = (mid, hi) if ok else (lo, mid)
    return lo


def hex_of(lch: LCH) -> str:
    return "#" + "".join(f"{round(_to_srgb(c) * 255):02x}" for c in _lin_rgb(lch))


def oklch_of(hexs: str) -> LCH:
    h = hexs.lstrip("#")
    lin = tuple(_to_lin(int(h[i:i + 2], 16) / 255) for i in (0, 2, 4))
    lms = _mul(_LMS_FROM_RGB, lin)
    lab = _mul(_LAB_FROM_LMS, tuple(math.copysign(abs(x) ** (1 / 3), x) for x in lms))
    return lab[0], math.hypot(lab[1], lab[2]), math.degrees(math.atan2(lab[2], lab[1])) % 360


def _rgb8(hexs: str) -> tuple[tuple[int, int, int], float]:
    h = hexs.lstrip("#")
    alpha = int(h[6:8], 16) / 255 if len(h) == 8 else 1.0
    return (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)), alpha


def composite(fg: str, bg: str) -> str:
    (f, a), (b, _) = _rgb8(fg), _rgb8(bg)
    return "#" + "".join(f"{round(x * a + y * (1 - a)):02x}" for x, y in zip(f, b))


def contrast(a: str, b: str) -> float:
    def lum(hexs: str) -> float:
        (r, g, bl), _ = _rgb8(hexs)
        return 0.2126 * _to_lin(r / 255) + 0.7152 * _to_lin(g / 255) + 0.0722 * _to_lin(bl / 255)

    hi, lo = sorted((lum(a), lum(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def grey(lightness: float) -> LCH:
    return (min(max(lightness, 0.0), 1.0), 0.0, 0.0)


# --------------------------------------------------------------------------------------------------
# Seeds
# --------------------------------------------------------------------------------------------------
def resolve_params(seed: dict[str, Any]) -> dict[str, tuple[Any, str]]:
    """Merge a seed over DEFAULTS. Each value is tagged 'stated' or 'default (<source>)'."""
    unknown = set(seed) - set(DEFAULTS)
    if unknown:
        raise SystemExit(f"unknown seed parameter(s): {sorted(unknown)}")
    if "brand.hue" not in seed:
        raise SystemExit("seed must state brand.hue")
    return {k: ((seed[k], "stated") if k in seed else (v, f"default ({src})")) for k, (v, src) in DEFAULTS.items()}


def exact_oklch(hexs: str) -> tuple[float, float, float]:
    """A hex as OKLCH at the fewest decimals that still round-trip to exactly that hex."""
    for places in range(3, 9):
        lch = tuple(round(x, places) for x in oklch_of(hexs))
        if hex_of(lch) == hexs:  # type: ignore[arg-type]
            return lch  # type: ignore[return-value]
    raise SystemExit(f"{hexs} does not round-trip through OKLCH")


def cmd_init_seeds(_: argparse.Namespace) -> None:
    for theme in SOURCE_THEMES:
        tokens = json.loads((RICHDOCS_THEMES / theme / "design-tokens.json").read_text(encoding="utf-8"))
        accents = {m: tokens["themes"][m]["accent"].lower() for m in MODES}
        seed: dict[str, float] = {}
        for m, prefix in (("light", "brand"), ("dark", "brand.dark")):
            if m == "dark" and accents["dark"] == accents["light"]:
                continue  # one accent for both modes: nothing more to state
            lightness, chroma, hue = exact_oklch(accents[m])
            seed |= {f"{prefix}.hue": hue, f"{prefix}.chroma": chroma, f"{prefix}.lightness": lightness}
        target = PROFILES / f"hue-{theme}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "seed.json").write_text(json.dumps(seed, indent=2) + "\n", encoding="utf-8")
        log.info("seed hue-%-12s exactly %s accents light %s, dark %s", theme, theme, accents["light"],
                 accents["dark"])


# --------------------------------------------------------------------------------------------------
# Curation: seed -> IR
# --------------------------------------------------------------------------------------------------
class Curator:
    def __init__(self, seed: dict[str, Any], stated: dict[str, dict[str, str]] | None = None) -> None:
        self.p = resolve_params(seed)
        # DT-PROV-1: values the IR states (hand edits), per role per mode. They are final: put()
        # keeps them in place of what the rule derives, and every later stage reads them.
        self.stated = stated or {}
        # What each keyword or implied default resolved to, for the showcase's controls.
        self.resolved: dict[str, Any] = {}
        self.ir: dict[str, dict[str, Any]] = {}

    def v(self, key: str) -> Any:
        return self.p[key][0]

    def cite(self, *keys: str) -> list[str]:
        return [f"{k}={self.p[k][0]} [{self.p[k][1]}]" for k in keys]

    def put(self, role: str, values: dict[str, str], rule: str, inputs: list[str],
            lch: dict[str, LCH] | None = None, alias: str | None = None, roles: list[str] | None = None) -> None:
        # DT-PROV-1: `derived` is what the rule produced. A value equal to it was not edited and is
        # rederived on the next run; a value that differs is stated, and kept.
        pinned = self.stated.get(role, {})
        ext: dict[str, Any] = {
            "origin": {m: "stated" if m in pinned else "imputed" for m in values},
            "derived": dict(values),
            "rule": rule,
            "inputs": inputs,
        }
        if roles or alias:
            ext["roles"] = roles or [alias]
        if lch:
            ext["oklch"] = {m: [round(x, 4) for x in lch[m]] for m in lch}
        for m, hexs in pinned.items():
            if "oklch" in ext and len(hexs) == 7:
                ext["oklch"][m] = [round(x, 4) for x in oklch_of(hexs)]
        if alias:
            ext["alias"] = alias
        self.ir[role] = {**values, **pinned, "$extensions": {EXT: ext}}

    def val(self, role: str, mode: str) -> str:
        return self.ir[role][mode]

    def grounds(self, mode: str) -> list[str]:
        return [self.val(r, mode) for r in ("color.surface.sunken", "color.surface", "color.surface.raised")]

    def sign(self, mode: str) -> float:
        return 1.0 if mode == "dark" else -1.0

    def bg(self, mode: str) -> float:
        return self.v("L-dark-bg") if mode == "dark" else self.v("L-light-bg")

    def solve(self, hue: float, cmax: float, anchor: float, test: Callable[[str], bool], what: str) -> LCH:
        for step in range(0, int(1 / STEP) + 1):
            for lightness in sorted({anchor + step * STEP, anchor - step * STEP}):
                if 0.0 <= lightness <= 1.0:
                    lch = (lightness, min(max_chroma(lightness, hue), cmax), hue)
                    if test(hex_of(lch)):
                        return lch
        raise SystemExit(f"unsolvable: {what} at hue {hue:.1f}")

    def on_all_grounds(self, mode: str, target: float) -> Callable[[str], bool]:
        return lambda colour: min(contrast(colour, g) for g in self.grounds(mode)) >= target

    # ---- stages ------------------------------------------------------------------------------------
    def neutrals(self) -> None:
        for role, key, absolute in (
            ("color.surface.sunken", "offset.surface.sunken", True),
            ("color.surface", None, True),
            ("color.surface.raised", "offset.surface.raised", True),
            ("color.text", "offset.text", False),
            ("color.text.subtle", "offset.text.subtle", False),
        ):
            lch = {}
            for m in MODES:
                off = self.v(key) if key else 0.0
                lch[m] = grey(self.bg(m) + (off if absolute else self.sign(m) * off))
            rule = "mode reference" if key is None else (
                "reference + absolute offset" if absolute else "reference + offset toward text")
            self.put(role, {m: hex_of(lch[m]) for m in MODES}, rule,
                     self.cite("L-light-bg", "L-dark-bg", *([key] if key else [])), lch)

        # DT-BORDER-1: an opaque grey solved to the lightness nearest the offset that reaches 3:1
        # against every ground. The offset is where the search starts, not the answer.
        lch = {}
        for m in MODES:
            anchor = self.bg(m) + self.sign(m) * self.v("offset.border.bold")
            passes = self.on_all_grounds(m, self.v("target.graphic"))
            lch[m] = next(grey(lt) for step in range(int(1 / STEP) + 1)
                          for lt in sorted({anchor + step * STEP, anchor - step * STEP})
                          if 0.0 <= lt <= 1.0 and passes(hex_of(grey(lt))))
        self.put("color.border.bold", {m: hex_of(lch[m]) for m in MODES},
                 "grey nearest reference + offset toward text reaching the target on every ground",
                 self.cite("L-light-bg", "L-dark-bg", "offset.border.bold", "target.graphic"), lch)

        lch = {}
        for m in MODES:
            for step in range(1, int(1 / STEP)):
                cand = grey(self.bg(m) + self.sign(m) * step * STEP)
                if self.on_all_grounds(m, self.v("target.text.subtlest"))(hex_of(cand)):
                    lch[m] = cand
                    break
        self.put("color.text.subtlest", {m: hex_of(lch[m]) for m in MODES},
                 "nearest the ground reaching the target on every ground", self.cite("target.text.subtlest"), lch)

        alpha = round(self.v("alpha.border") * 255)
        self.put("color.border", {m: f"{self.val('color.text', m)}{alpha:02x}" for m in MODES},
                 "color.text at alpha", self.cite("alpha.border"), roles=["color.text"])

    def brand(self) -> None:
        hue = float(self.v("brand.hue"))
        cusp_l = max((i * STEP for i in range(1, int(1 / STEP))), key=lambda lt: max_chroma(lt, hue))
        cusp_c = max_chroma(cusp_l, hue)
        chroma = cusp_c if self.v("brand.chroma") == "cusp" else float(self.v("brand.chroma"))
        brand_l = cusp_l if self.v("brand.lightness") == "cusp" else float(self.v("brand.lightness"))
        self.brand_hue, self.brand_c, self.brand_l = hue, chroma, brand_l
        # Each mode's accent: light is the brand.* accent; dark defaults to it, and any brand.dark.* key
        # overrides one coordinate. A stated lightness pins that mode's fill verbatim (DT-CONTRAST-1).
        dark = {k: self.v(f"brand.dark.{k}") for k in ("hue", "chroma", "lightness")}
        self.accent = {
            "light": (brand_l, chroma, hue),
            "dark": (brand_l if dark["lightness"] is None else float(dark["lightness"]),
                     chroma if dark["chroma"] is None else float(dark["chroma"]),
                     hue if dark["hue"] is None else float(dark["hue"])),
        }
        pinned = {"light": self.v("brand.lightness") != "cusp", "dark": dark["lightness"] is not None}
        self.resolved.update({"brand.lightness": brand_l, "brand.chroma": chroma,
                              **{f"brand.dark.{k}": v for k, v in zip(("lightness", "chroma", "hue"),
                                                                        self.accent["dark"])}})
        stated_dark = [f"brand.dark.{k}" for k, v in dark.items() if v is not None]
        base = self.cite("brand.hue", "brand.chroma", "brand.lightness", *stated_dark) + [
            f"cusp L={cusp_l:.3f} C={cusp_c:.4f} (derived)"]

        def best_text(colour: str) -> str:
            return "#000000" if contrast(colour, "#000000") >= contrast(colour, "#ffffff") else "#ffffff"

        lch = {}
        for m in MODES:
            anchor, c, h = self.accent[m]
            lch[m] = self.accent[m] if pinned[m] else self.solve(h, c, anchor, lambda col, m=m: (
                contrast(col, best_text(col)) >= self.v("target.text.inverse")
                and self.on_all_grounds(m, self.v("target.graphic"))(col)), "brand fill")
        solved = "lightness solved: inverse text reaches target, and 3:1 on every ground"
        rule = "; ".join(f"{m}: " + ("the stated accent, verbatim" if pinned[m] else solved) for m in MODES)
        self.put("color.background.brand.bold", {m: hex_of(lch[m]) for m in MODES},
                 rule, base + self.cite("target.text.inverse", "target.graphic"), lch)
        self.put("color.text.inverse", {m: best_text(self.val("color.background.brand.bold", m)) for m in MODES},
                 "black or white, whichever has more contrast on the brand fill", [],
                 roles=["color.background.brand.bold"])
        self.put("color.background.brand.subtlest",
                 {m: composite(self.val("color.background.brand.bold", m)
                               + f"{round(self.v('alpha.brand.subtlest') * 255):02x}", self.val("color.surface", m))
                  for m in MODES},
                 "brand fill at alpha over color.surface", self.cite("alpha.brand.subtlest"),
                 roles=["color.background.brand.bold", "color.surface"])
        for role, key in (("color.border.brand", "target.graphic"), ("color.link", "target.link")):
            lch = {m: self.solve(self.accent[m][2], self.accent[m][1], self.accent[m][0],
                                 self.on_all_grounds(m, self.v(key)), role) for m in MODES}
            self.put(role, {m: hex_of(lch[m]) for m in MODES},
                     "the mode's accent, lightness solved to reach the target on every ground",
                     base + self.cite(key), lch)

    def secondary(self) -> None:
        hue = float(self.v("secondary.hue") if self.v("secondary.hue") is not None else self.brand_hue)
        chroma = self.brand_c * float(self.v("secondary.chromaRatio"))
        inputs = self.cite("secondary.hue", "secondary.chromaRatio", "brand.hue", "brand.chroma")
        for role, extra in (("color.background.selected", 0.0), ("color.background.selected.hovered", STEP * 10)):
            lch = {}
            for m in MODES:
                lightness = self.bg(m) + self.sign(m) * (self.v("offset.background.selected") + extra)
                lch[m] = (lightness, min(max_chroma(lightness, hue), chroma), hue)
            self.put(role, {m: hex_of(lch[m]) for m in MODES},
                     "secondary at reduced chroma, offset from the ground toward text",
                     inputs + self.cite("offset.background.selected"), lch)
        lch = {m: self.solve(hue, self.brand_c, self.brand_l, self.on_all_grounds(m, self.v("target.graphic")),
                             "selected border") for m in MODES}
        self.put("color.border.selected", {m: hex_of(lch[m]) for m in MODES},
                 "secondary hue reaching 3:1 on every ground", inputs + self.cite("target.graphic"), lch)
        self.put("color.border.focused", {m: self.val("color.border.selected", m) for m in MODES},
                 "alias", [], alias="color.border.selected")
        self.put("color.text.selected", {m: self.val("color.text", m) for m in MODES}, "alias", [], alias="color.text")

    def status(self) -> None:
        for name in ("danger", "warning", "success"):
            key = f"status.hue.{name}"
            lch = {m: self.solve(float(self.v(key)), float(self.v("status.chromaCap")), 0.6,
                                 self.on_all_grounds(m, self.v("target.status")), name) for m in MODES}
            self.put(f"color.text.{name}", {m: hex_of(lch[m]) for m in MODES},
                     "conventional hue reaching the target on every ground",
                     self.cite(key, "status.chromaCap", "target.status"), lch)

    def walk(self) -> None:
        n, angle = int(self.v("walk.slots")), float(self.v("walk.angle"))
        hues = [(self.brand_hue + i * angle) % 360 for i in range(n)]
        ceiling = self.v("walk.chromaCeiling")
        follow = self.v("walk.lightness") == "brand"
        inputs = self.cite("brand.hue", "walk.slots", "walk.angle", "walk.lightness", "walk.chromaCeiling",
                           "target.graphic", *(["brand.chroma"] if ceiling == "seed" else []),
                           *(["brand.lightness"] if follow else []),
                           *(["brand.dark.lightness"] if follow and self.v("brand.dark.lightness") is not None
                             else []))
        per_mode: dict[str, list[LCH]] = {}
        for m in MODES:
            test = self.on_all_grounds(m, self.v("target.graphic"))
            # DT-WALK-2: solved nearest the seed's lightness, i.e. that mode's accent lightness.
            anchor = self.accent[m][0] if follow else float(self.v("walk.lightness"))
            self.resolved.setdefault("walk.lightness", {})[m] = anchor
            if ceiling == "floor":
                first = [self.solve(h, 1.0, anchor, test, "walk") for h in hues]
                floor = min(max_chroma(lt, h) for lt, _c, h in first)
                slots = [self.solve(h, floor, anchor, test, "walk") for h in hues]
                floor = min(max_chroma(lt, h) for lt, _c, h in slots)
                per_mode[m] = [(lt, floor, h) for lt, _c, h in slots]
            else:
                cap = self.brand_c if ceiling == "seed" else float(ceiling)
                per_mode[m] = [self.solve(h, cap, anchor, test, "walk") for h in hues]
        for i in range(n):
            lch = {m: per_mode[m][i] for m in MODES}
            self.put(f"color.chart.categorical.{i + 1}", {m: hex_of(lch[m]) for m in MODES},
                     f"golden walk slot {i + 1}: hue +{i}x{angle} deg, lightness solved to 3:1, chroma ceiling",
                     inputs, lch)

    def ramps(self) -> None:
        """Chart ramps the richdocs viewer needs. Prototype roles in the chart namespace."""
        spans = {"light": (0.88, 0.42), "dark": (0.30, 0.82)}
        danger = float(self.v("status.hue.danger"))
        success = float(self.v("status.hue.success"))
        cap = float(self.v("status.chromaCap"))
        brand_keys = ("brand.hue", "brand.chroma")
        for name, hue, chroma, count, keys in (
                ("sequential", self.brand_hue, self.brand_c, 5, brand_keys),
                ("diverging.positive", self.brand_hue, self.brand_c, 3, brand_keys),
                ("diverging.negative", danger, cap, 3, ("status.hue.danger", "status.chromaCap")),
                ("diverging.alt-positive", success, cap, 3, ("status.hue.success", "status.chromaCap"))):
            for i in range(count):
                lch = {}
                for m in MODES:
                    lo, hi = spans[m]
                    lightness = lo + (hi - lo) * (i / (count - 1))
                    lch[m] = (lightness, min(max_chroma(lightness, hue), chroma), hue)
                self.put(f"color.chart.{name}.{i + 1}", {m: hex_of(lch[m]) for m in MODES},
                         "evenly spaced lightness at a fixed hue, chroma capped",
                         ["prototype", *self.cite(*keys)], lch)
        for i in range(4):
            lch = {}
            for m in MODES:
                a = self.bg(m) + self.sign(m) * self.v("offset.border.bold")
                b = self.bg(m) + self.sign(m) * self.v("offset.text.subtle")
                lch[m] = grey(a + (b - a) * i / 3)
            self.put(f"color.chart.muted.{i + 1}", {m: hex_of(lch[m]) for m in MODES},
                     "greys from border.bold to text.subtle",
                     ["prototype", *self.cite("L-light-bg", "L-dark-bg", "offset.border.bold", "offset.text.subtle")], lch)

    def run(self) -> dict[str, Any]:
        self.neutrals()
        self.brand()
        self.secondary()
        self.status()
        self.walk()
        self.ramps()
        return {"$extensions": {EXT: {"params": {k: {"value": v, "source": s} for k, (v, s) in self.p.items()}}},
                **self.ir}


def profile_names(args: argparse.Namespace) -> list[str]:
    names = args.profile or sorted(p.name for p in PROFILES.iterdir() if (p / "seed.json").exists())
    if not names:
        raise SystemExit(f"no profiles with a seed.json under {PROFILES}; run init-seeds")
    return names


def stated_values(ir: dict[str, Any]) -> dict[str, dict[str, str]]:
    """DT-PROV-1: every value in an existing IR that is not what curation derived for it.

    A value already marked stated stays stated. A value with no `derived` record predates
    DT-PROV-1; the prototype wrote every such value itself, so it counts as derived.
    """
    stated: dict[str, dict[str, str]] = {}
    for role, node in ir.items():
        if role.startswith("$"):
            continue
        ext = node.get("$extensions", {}).get(EXT, {})
        origin, derived = ext.get("origin", {}), ext.get("derived", {})
        for m in MODES:
            if m not in node:
                continue
            was_stated = isinstance(origin, dict) and origin.get(m) == "stated"
            if was_stated or (m in derived and node[m] != derived[m]):
                stated.setdefault(role, {})[m] = node[m]
    return stated


AA_TEXT = 4.5  # WCAG 2.2 SC 1.4.3: the floor every text pairing is scored against


def score_contrast(ir: dict[str, Any]) -> list[dict[str, Any]]:
    """CURATION stage 7 / DT-CONTRAST-1: score every text-on-background pairing, per mode.

    A miss is a `defect` in the defaults only when both colours are imputed and neither was driven
    by a stated seed parameter (the brand hue aside, which every seed states). Any other miss is the
    user's `choice`: reported, never a failure.
    """
    def driven_by_statement(role: str, m: str) -> bool:
        ext = ir[role]["$extensions"][EXT]
        if ext["origin"].get(m) == "stated":
            return True
        return any(c.endswith("[stated]") and not c.startswith("brand.hue=") for c in ext["inputs"])

    scores = []
    for text, grounds in TEXT_CHECKS:
        for ground in grounds:
            for m in MODES:
                ratio = contrast(ir[text][m], ir[ground][m])
                verdict = "pass" if ratio >= AA_TEXT else (
                    "choice" if driven_by_statement(text, m) or driven_by_statement(ground, m) else "defect")
                scores.append({"text": text, "on": ground, "mode": m, "ratio": round(ratio, 2),
                               "target": AA_TEXT, "verdict": verdict})
    return scores


def curate_profile(folder: Path) -> list[str]:
    """Curate one profile in place: idempotent and additive (DT-BUILD-1, DT-PROV-1).

    Stated values are kept and feed every value derived after them; unedited values are rederived
    from the seed; absent roles are imputed. Returns the report lines.
    """
    seed = json.loads((folder / "seed.json").read_text(encoding="utf-8"))
    ir_path = folder / "ir.json"
    old = json.loads(ir_path.read_text(encoding="utf-8")) if ir_path.exists() else {}
    stated = stated_values(old)
    ir = Curator(seed, stated).run()
    report = []
    for role in (k for k in ir if not k.startswith("$")):
        for m in MODES:
            before, after = old.get(role, {}).get(m), ir[role][m]
            if role in stated and m in stated[role]:
                derived = ir[role]["$extensions"][EXT]["derived"][m]
                note = "" if derived == after else f" (rule would give {derived})"
                report.append(f"held    {role} {m} {after} stated{note}")
            elif before is None:
                report.append(f"new     {role} {m} {after}")
            elif before != after:
                report.append(f"updated {role} {m} {before} -> {after}")
    scores = score_contrast(ir)
    ir["$extensions"][EXT]["contrast"] = scores
    for sc in scores:
        if sc["verdict"] != "pass":
            report.append(f"{sc['verdict']:7} {sc['text']} on {sc['on']} {sc['mode']} {sc['ratio']}:1 "
                          f"(AA {sc['target']}:1)")
    ir_path.write_text(json.dumps(ir, indent=2) + "\n", encoding="utf-8")
    return report


def cmd_curate(args: argparse.Namespace) -> None:
    defects = 0
    for name in profile_names(args):
        report = curate_profile(PROFILES / name)
        count = {k: sum(r.startswith(k) for r in report) for k in ("held", "updated", "new", "defect", "choice")}
        log.info("curated %-16s held %d stated, updated %d, imputed %d new; contrast: %d defect, %d choice",
                 name, count["held"], count["updated"], count["new"], count["defect"], count["choice"])
        for line in report:
            if not line.startswith("new"):
                log.info("  %s", line)
        defects += count["defect"]
    if defects:
        # DT-CONTRAST-1: a miss the defaults caused is a failure of curation, never of the user.
        raise SystemExit(f"curation failed: {defects} text pairing(s) below AA from defaults alone")


# --------------------------------------------------------------------------------------------------
# Build: IR -> DTCG, and the richdocs projection
# --------------------------------------------------------------------------------------------------
def dtcg_colour(hexs: str, lch: list[float] | None) -> dict[str, Any]:
    (r, g, b), alpha = _rgb8(hexs)
    if lch is not None and alpha == 1.0:
        return {"colorSpace": "oklch", "components": lch, "hex": hexs[:7]}
    value: dict[str, Any] = {"colorSpace": "srgb", "components": [round(r / 255, 4), round(g / 255, 4),
                                                                   round(b / 255, 4)], "hex": hexs[:7]}
    if alpha != 1.0:
        value["alpha"] = round(alpha, 4)
    return value


def dtcg_path(role: str, roles: set[str]) -> list[str]:
    parts = role.split(".")
    return parts + ["default"] if any(r.startswith(role + ".") for r in roles) else parts


def cmd_build(args: argparse.Namespace) -> None:
    for name in profile_names(args):
        folder = PROFILES / name
        ir = json.loads((folder / "ir.json").read_text(encoding="utf-8"))
        roles = {k for k in ir if not k.startswith("$")}
        out = folder / "dtcg"
        out.mkdir(exist_ok=True)
        for m in MODES:
            tree: dict[str, Any] = {"color": {"$type": "color"}}
            for role in sorted(roles):
                ext = ir[role]["$extensions"][EXT]
                node = tree
                *groups, leaf = dtcg_path(role, roles)
                for part in groups:
                    node = node.setdefault(part, {})
                if "alias" in ext:
                    node[leaf] = {"$value": "{" + ".".join(dtcg_path(ext["alias"], roles)) + "}"}
                else:
                    node[leaf] = {"$value": dtcg_colour(ir[role][m], ext.get("oklch", {}).get(m))}
            (out / f"{m}.tokens.json").write_text(json.dumps(tree, indent=2) + "\n", encoding="utf-8")
        resolver = {
            "$schema": "https://www.designtokens.org/schemas/2025.10/resolver.json",
            "version": "2025.10",
            "modifiers": {"mode": {"contexts": {m: [{"$ref": f"{m}.tokens.json"}] for m in MODES},
                                   "default": "light"}},
            "resolutionOrder": [{"$ref": "#/modifiers/mode"}],
        }
        (out / "profile.resolver.json").write_text(json.dumps(resolver, indent=2) + "\n", encoding="utf-8")
        (folder / "design-tokens.json").write_text(json.dumps(project_richdocs(ir), indent=2) + "\n",
                                                   encoding="utf-8")
        seed = json.loads((folder / "seed.json").read_text(encoding="utf-8"))
        (folder / "lineage.json").write_text(json.dumps(build_lineage(ir, seed), indent=2) + "\n", encoding="utf-8")
        log.info("built    %-16s dtcg/{light,dark}.tokens.json + resolver + richdocs projection + lineage", name)


def project_richdocs(ir: dict[str, Any], ref: bool = False) -> dict[str, Any]:
    """Map IR roles onto richdocs' current design-tokens.json keys. A stand-in until migration.

    With `ref`, every colour leaf is `@role` (or `@a|@b` for a composite) instead of a hex, so the
    same mapping yields the IR -> projection lineage without a second copy of it.
    """
    def r(role: str, m: str) -> str:
        return f"@{role}" if ref else ir[role][m]

    def over(fg: str, bg: str, m: str) -> str:
        return f"@{fg}|@{bg}" if ref else composite(ir[fg][m], ir[bg][m])

    def seq(prefix: str, count: int, m: str) -> list[str]:
        return [r(f"{prefix}.{i}", m) for i in range(1, count + 1)]

    themes, cyto, plotly, status = {}, {}, {}, {}
    for m in MODES:
        border = over("color.border", "color.surface", m)
        themes[m] = {"bg": r("color.surface", m), "fg": r("color.text", m), "muted": r("color.text.subtle", m),
                     "accent": r("color.background.brand.bold", m), "surface": r("color.surface.raised", m),
                     "border": border, "onAccent": r("color.text.inverse", m), "link": r("color.link", m),
                     "radius": "12px", "pill": "999px"}
        cyto[m] = {"nodeFill": r("color.background.brand.subtlest", m), "nodeBorder": r("color.border.brand", m),
                   "nodeLabel": r("color.text", m), "nodeFillAlt": r("color.background.selected", m),
                   "edge": r("color.border.bold", m), "edgeLabel": r("color.text.subtle", m),
                   "edgeLabelBg": r("color.surface", m), "compoundBg": r("color.surface.sunken", m),
                   "compoundBorder": over("color.border", "color.surface.sunken", m),
                   "selected": r("color.border.selected", m), "shape": "round-rectangle", "roundness": 8}
        plotly[m] = {"paper": r("color.surface.raised", m), "plot": r("color.surface", m),
                     "font": r("color.text", m), "grid": border,
                     # Every walk slot: the categorical colours are one ordered list (DT-WALK-1, DT-CAT-1).
                     "series": seq("color.chart.categorical", 12, m),
                     "muted": seq("color.chart.muted", 4, m),
                     "sequential": seq("color.chart.sequential", 5, m),
                     "diverging": {"good": seq("color.chart.diverging.positive", 3, m),
                                   "zero": r("color.surface.sunken", m),
                                   "bad": seq("color.chart.diverging.negative", 3, m), "label": "brand ↔ danger"},
                     "divergingAlt": {"good": seq("color.chart.diverging.alt-positive", 3, m),
                                      "zero": r("color.surface.sunken", m),
                                      "bad": seq("color.chart.diverging.negative", 3, m),
                                      "label": "success ↔ danger"}}
        status[m] = {"colours": {"good": r("color.text.success", m), "warning": r("color.text.warning", m),
                                 "serious": r("color.text.danger", m), "critical": r("color.text.danger", m)},
                     "labels": {"good": "Good", "warning": "Warning", "serious": "Serious", "critical": "Critical"}}
    names = ("Compute", "Storage", "Database", "Networking", "Security", "Integration", "General")
    return {"defaultTheme": "light",
            "fonts": {"display": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
                      "body": "system-ui, -apple-system, 'Segoe UI', Roboto, sans-serif",
                      "mono": "ui-monospace, 'SF Mono', Menlo, Consolas, monospace"},
            "themes": themes, "canvas": {"cytoscape": cyto, "plotly": plotly},
            "categoryColours": {n: r(f"color.chart.categorical.{i + 1}", "light") for i, n in enumerate(names)},
            "status": status}


def _leaves(node: Any, path: tuple[str, ...] = ()) -> list[tuple[tuple[str, ...], Any]]:
    if isinstance(node, dict):
        return [x for k, v in node.items() for x in _leaves(v, (*path, k))]
    if isinstance(node, list):
        return [x for i, v in enumerate(node) for x in _leaves(v, (*path, str(i + 1)))]
    return [(path, node)]


def build_lineage(ir: dict[str, Any], seed: dict[str, Any]) -> dict[str, Any]:
    """Two Sankeys, in richdocs' lineage.json contract: seed -> IR, and IR -> the rendered projection.

    Each link is one recorded dependency (value 1), so a node's thickness is how many values it feeds
    or reads. Role nodes are painted in their own colour per mode, so the diagram doubles as a palette.
    """
    params = ir["$extensions"][EXT]["params"]
    roles = [k for k in ir if not k.startswith("$")]
    grey_node = {"light": "#8a8a8a", "dark": "#8a8a8a"}

    def role_colour(role: str) -> dict[str, str]:
        return {m: ir[role][m][:7] for m in MODES}

    # Seed -> IR: parameter -> role from each role's cited inputs, role -> role from recorded dependencies.
    links: list[dict[str, str]] = []
    used: set[str] = set()
    for role in roles:
        ext = ir[role]["$extensions"][EXT]
        for cite in ext["inputs"]:
            key = cite.split("=", 1)[0]
            if key in params:
                links.append({"source": f"param:{key}", "target": role})
                used.add(key)
        for dep in ext.get("roles", []):
            links.append({"source": dep, "target": role})
    nodes = []
    for key in (k for k in params if k in used):
        stated = params[key]["source"] == "stated"
        tier = "stated" if stated else "prototype default" if "prototype" in params[key]["source"] else "decided default"
        colour = role_colour("color.background.brand.bold") if stated else grey_node
        nodes.append({"id": f"param:{key}", "label": f"{key} = {params[key]['value']}", "group": tier,
                      "colour": colour})
    nodes += [{"id": r, "label": r, "group": "IR role", "colour": role_colour(r)} for r in roles]
    stated_keys = ", ".join(f"`{k}`" for k in seed) or "nothing"
    seed_to_ir = {
        "title": "Seed → IR",
        "caption": (f"Every parameter on the left is either stated in seed.json ({stated_keys}, in the brand "
                    "colour) or a default (grey). Each band is one recorded input of an IR role; roles that "
                    "read other roles chain to the right. Contrast solves also read the three surfaces, which "
                    "is not drawn."),
        "nodes": nodes, "links": links,
    }

    # IR -> projection: the same mapping as project_richdocs, run in reference mode.
    refs = dict(_leaves(project_richdocs(ir, ref=True)))
    real = dict(_leaves(project_richdocs(ir)))
    links, targets = [], {}
    for path, value in refs.items():
        if not (isinstance(value, str) and value.startswith("@")):
            continue
        mode_key = next((m for m in MODES if m in path), None)
        if mode_key == "dark":
            continue  # the mapping is identical per mode; each target carries both modes' colours
        label_path = tuple(p for p in path if p not in MODES and p not in ("canvas", "colours"))
        target = "out:" + ".".join(label_path)
        dark_path = tuple("dark" if p == "light" else p for p in path)
        targets[target] = {"id": target, "label": " · ".join(label_path), "group": label_path[0],
                           "colour": {"light": real[path][:7], "dark": real.get(dark_path, real[path])[:7]}}
        for src in value.split("|"):
            links.append({"source": src[1:], "target": target})
    sources = sorted({lk["source"] for lk in links}, key=roles.index)
    ir_to_final = {
        "title": "IR → rendered theme",
        "caption": ("Each IR role on the left feeds the keys of the design-tokens.json this showcase renders. "
                    "One role often feeds several surfaces; a composite (a translucent border over a ground) "
                    "reads two roles. IR roles with no band are carried in the DTCG build but not yet consumed "
                    "by richdocs."),
        "nodes": [{"id": r, "label": r, "group": "IR role", "colour": role_colour(r)} for r in sources]
                 + list(targets.values()),
        "links": links,
    }
    return {"sankeys": [seed_to_ir, ir_to_final]}


def generate(seed: dict[str, Any], context: dict[str, Any] | None = None) -> dict[str, Any]:
    """richdocs' live-generator entry point (ADR-022): one seed in, a brandpack and its lineage out.

    The showcase runs this very file in the browser under Pyodide, so the controls and the CLI share
    one curation, not a port of it. `context.stated` carries the profile's hand edits (DT-PROV-1), so
    tuning the seed live keeps them exactly as `curate` would.
    """
    curator = Curator(seed, (context or {}).get("stated"))
    ir = curator.run()
    return {"tokens": project_richdocs(ir), "lineage": build_lineage(ir, seed), "resolved": curator.resolved}


def generator_manifest(seed: dict[str, Any], ir: dict[str, Any]) -> dict[str, Any]:
    """The controls the showcase offers: every seed parameter with a range, its default and its source."""
    context = {"stated": stated_values(ir)}
    return {
        "entry": "generate",
        "seed": seed,
        "context": context,
        "resolved": generate(seed, context)["resolved"],
        "params": [{"key": k, "default": v, "source": src, **CONTROLS[k]}
                   for k, (v, src) in DEFAULTS.items() if k in CONTROLS],
    }


def cmd_install(args: argparse.Namespace) -> None:
    for name in profile_names(args):
        target = PROJECT_THEMES / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "design-tokens.json").write_text(
            (PROFILES / name / "design-tokens.json").read_text(encoding="utf-8"), encoding="utf-8")
        (target / "lineage.json").write_text(
            (PROFILES / name / "lineage.json").read_text(encoding="utf-8"), encoding="utf-8")
        seed = json.loads((PROFILES / name / "seed.json").read_text(encoding="utf-8"))
        ir = json.loads((PROFILES / name / "ir.json").read_text(encoding="utf-8"))
        (target / "generator.json").write_text(json.dumps(generator_manifest(seed, ir), indent=2) + "\n",
                                               encoding="utf-8")
        (target / "generator.py").write_text(Path(__file__).read_text(encoding="utf-8"), encoding="utf-8")
        # The showcase scopes each brand's CSS under :root[data-brand=...]; a brand with no
        # theme.css emits no scope, which richdocs' own gallery test treats as missing.
        (target / "theme.css").write_text(":root {\n  color-scheme: light dark;\n}\n", encoding="utf-8")
        log.info("installed %-15s -> %s", name, target)


# --------------------------------------------------------------------------------------------------
# Propagation document
# --------------------------------------------------------------------------------------------------
TEXT_CHECKS = [
    ("color.text", ("color.surface.sunken", "color.surface", "color.surface.raised")),
    ("color.text.subtle", ("color.surface.sunken", "color.surface", "color.surface.raised")),
    ("color.text.subtlest", ("color.surface.sunken", "color.surface", "color.surface.raised")),
    ("color.link", ("color.surface.sunken", "color.surface", "color.surface.raised")),
    ("color.text.danger", ("color.surface",)),
    ("color.text.warning", ("color.surface",)),
    ("color.text.success", ("color.surface",)),
    ("color.text.inverse", ("color.background.brand.bold",)),
    ("color.text", ("color.background.brand.subtlest",)),
    ("color.text.selected", ("color.background.selected", "color.background.selected.hovered")),
]


def chip(hexs: str) -> str:
    return (f'<span style="display:inline-block;width:38px;height:16px;border-radius:3px;vertical-align:middle;'
            f'border:1px solid #8886;background:{hexs}"></span> `{hexs}`')


def grade(ratio: float) -> str:
    return "AAA" if ratio >= 7 else "AA" if ratio >= 4.5 else "**below AA**"


def profile_section(name: str) -> str:
    folder = PROFILES / name
    seed = json.loads((folder / "seed.json").read_text(encoding="utf-8"))
    ir = json.loads((folder / "ir.json").read_text(encoding="utf-8"))
    params = ir["$extensions"][EXT]["params"]
    roles = [k for k in ir if not k.startswith("$")]
    light_dtcg = json.loads((folder / "dtcg" / "light.tokens.json").read_text(encoding="utf-8"))

    rows = ["| Role | Light | Dark | Rule |", "|---|---|---|---|"]
    for role in roles:
        if role.startswith("color.chart.") and not role.startswith("color.chart.categorical."):
            continue
        ext = ir[role]["$extensions"][EXT]
        rule = ext["rule"] if "alias" not in ext else f"alias of `{ext['alias']}`"
        rows.append(f"| `{role}` | {chip(ir[role]['light'])} | {chip(ir[role]['dark'])} | {rule} |")

    checks = ["| Text | On | Light | Dark |", "|---|---|---|---|"]
    for text, grounds in TEXT_CHECKS:
        for ground in grounds:
            cells = []
            for m in MODES:
                bg = ir[ground][m]
                ratio = contrast(ir[text][m], bg)
                cells.append(f"{ratio:.2f}:1 {grade(ratio)}")
            checks.append(f"| `{text}` | `{ground}` | {cells[0]} | {cells[1]} |")

    stated = [f"`{k}`" for k, v in params.items() if v["source"] == "stated"]
    imputed_prototype = [f"`{k}`" for k, v in params.items() if "prototype" in v["source"]]
    walk = [{"hex": ir[f"color.chart.categorical.{i}"][m], "label": f"{m} slot {i}"}
            for m in MODES for i in range(1, 13)]
    walk += [{"hex": ir["color.background.brand.bold"][m], "label": f"{m} brand fill"} for m in MODES]
    walk += [{"hex": ir["color.background.selected"][m], "label": f"{m} selected"} for m in MODES]
    deck = {"view": "orbit", "space": "oklch", "height": 440,
            "gamut": sorted({round(ir["color.chart.categorical.1"]["$extensions"][EXT]["oklch"][m][0], 2)
                             for m in MODES}),
            "layers": [{"type": "PointCloudLayer", "pointSize": 12, "data": walk}]}
    excerpt = {"color": {"background": light_dtcg["color"]["background"]["brand"],
                         "border": {"focused": light_dtcg["color"]["border"]["focused"]}}}
    return f"""
---

## `{name}`

### 1. The seed

```json
{json.dumps(seed, indent=2)}
```

Stated: {", ".join(stated)}. Every other parameter is a default; the ones marked prototype are not decided
yet: {", ".join(imputed_prototype)}.

### 2. The IR

{chr(10).join(rows)}

The 12 walk slots and the chart ramps are in `prototype/profiles/{name}/ir.json`, each with its rule and
inputs under `$extensions`.

### 3. The walk in OKLCH

```deckgl
{json.dumps(deck, indent=1)}
```

### 4. Text on a background colour (DT-CONTRAST-1)

{chr(10).join(checks)}

### 5. The DTCG build

`dtcg/light.tokens.json`, `dtcg/dark.tokens.json` and `dtcg/profile.resolver.json`. An excerpt from
light mode, showing colour objects and an alias:

```json
{json.dumps(excerpt, indent=2)}
```
"""


def cmd_doc(args: argparse.Namespace) -> None:
    names = profile_names(args)
    defaults = ["| Parameter | Default | Source |", "|---|---|---|"]
    defaults += [f"| `{k}` | `{v}` | {src} |" for k, (v, src) in DEFAULTS.items()]
    doc = f"""# From a hue to a theme: prototype propagation

Four seeds, each stating **only the brand accent**: the exact light accent of one existing richdocs theme,
as OKLCH lightness, chroma and hue.
Everything else is imputed by the prototype pipeline in `prototype/pipeline.py`, following the locked
decisions in `DECISIONS.md` wherever one exists.

This is a spike to make the defaults visible, not the curation tool. Where no decision exists yet, the
pipeline uses a **prototype default** so it can run, and says so.

## The pipeline

1. **Seed:** `profiles/<name>/seed.json`, what the user states.
2. **IR:** `profiles/<name>/ir.json`, every role in both modes, each carrying its rule and inputs.
3. **DTCG:** `profiles/<name>/dtcg/`, colour objects per mode plus a resolver. The only runtime artifact.
4. **Projection:** `profiles/<name>/design-tokens.json`, mapped onto richdocs' current schema so the
   existing showcase can render it. A stand-in until the skills are migrated.

## Every default

{chr(10).join(defaults)}

## Showcase

The gallery places each generated theme beside the theme its accent came from:
`tmp/richdocs/showcase.html`, generated by `showcase.py` after `pipeline.py install`.
{"".join(profile_section(n) for n in names)}
"""
    (HERE / "propagation.md").write_text(doc, encoding="utf-8")
    log.info("wrote %s", HERE / "propagation.md")


def cmd_all(args: argparse.Namespace) -> None:
    if not args.profile and not any(PROFILES.glob("*/seed.json")):
        cmd_init_seeds(args)
    for step in (cmd_curate, cmd_build, cmd_install, cmd_doc):
        step(args)


# --------------------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------------------
def build_parser() -> argparse.ArgumentParser:
    def _help(p: argparse.ArgumentParser) -> Callable[[argparse.Namespace], None]:
        def _print_help(_: argparse.Namespace) -> None:
            p.print_help()

        return _print_help

    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.set_defaults(func=_help(parser))
    sub = parser.add_subparsers(dest="cmd", required=False)
    for name, func, text in (
        ("init-seeds", cmd_init_seeds, "Write seeds stating the four richdocs themes' exact light accents"),
        ("curate", cmd_curate, "seed.json -> ir.json"),
        ("build", cmd_build, "ir.json -> DTCG + richdocs projection"),
        ("install", cmd_install, "Copy projections into tmp/richdocs/theme/ for showcase.py"),
        ("doc", cmd_doc, "Write propagation.md"),
        ("all", cmd_all, "curate, build, install, doc"),
    ):
        p = sub.add_parser(name, help=text)
        p.add_argument("--profile", action="append", help="Limit to a profile (repeatable)")
        p.set_defaults(func=func)
    return parser


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":
    main()
