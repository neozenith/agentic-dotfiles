#!/usr/bin/env -S uv run --no-project python
"""Prototype seed -> IR -> DTCG pipeline for the design-token refactor.

A throwaway spike that walks the locked decisions end to end from a seed carrying ONLY a hue, so the
defaults can be seen propagating before the real curation tool is designed. Stdlib only.

    seed.json              {"brand.hue": 295.04}                 what the user states
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
    "brand.chroma": ("cusp", "prototype"),
    "L-dark-bg": (0.15, "DT-REF-1"),
    "L-light-bg": (0.90, "DT-REF-1"),
    "offset.surface.sunken": (-0.05, "DT-REF-1"),
    "offset.surface.raised": (0.05, "DT-REF-1"),
    "offset.text": (0.90, "DT-REF-1"),
    "offset.text.subtle": (0.65, "DT-REF-1"),
    "target.text.subtlest": (4.5, "prototype"),
    "alpha.border": (0.14, "DT-BORDER-1"),
    "offset.border.bold": (0.35, "DT-BORDER-1"),
    "target.graphic": (3.0, "WCAG 2.2 SC 1.4.11"),
    "target.text.inverse": (7.0, "prototype (DT-CONTRAST-1: maximise)"),
    "target.link": (4.5, "prototype"),
    "alpha.brand.subtlest": (0.16, "prototype (richdocs rdMix 0.84)"),
    "secondary.hue": (None, "DT-ACCENT-1 (defaults to brand.hue)"),
    "secondary.chromaRatio": (0.444, "DT-ACCENT-1 (M3 chroma 16/36)"),
    "offset.background.selected": (0.10, "prototype"),
    "walk.slots": (12, "DT-WALK-1"),
    "walk.angle": (137.5, "DT-WALK-1"),
    "walk.lightness": (0.60, "prototype (richdocs measured bands 0.58-0.65)"),
    "walk.chromaCeiling": ("floor", "DT-WALK-2"),
    "status.hue.danger": (25.0, "prototype"),
    "status.hue.warning": (80.0, "prototype"),
    "status.hue.success": (145.0, "prototype"),
    "status.chromaCap": (0.18, "prototype"),
    "target.status": (4.5, "prototype"),
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


def cmd_init_seeds(_: argparse.Namespace) -> None:
    for theme in SOURCE_THEMES:
        tokens = json.loads((RICHDOCS_THEMES / theme / "design-tokens.json").read_text(encoding="utf-8"))
        accent = tokens["themes"]["light"]["accent"]
        hue = round(oklch_of(accent)[2], 2)
        target = PROFILES / f"hue-{theme}"
        target.mkdir(parents=True, exist_ok=True)
        (target / "seed.json").write_text(json.dumps({"brand.hue": hue}, indent=2) + "\n", encoding="utf-8")
        log.info("seed hue-%-12s brand.hue %6.2f  (from %s light accent %s)", theme, hue, theme, accent)


# --------------------------------------------------------------------------------------------------
# Curation: seed -> IR
# --------------------------------------------------------------------------------------------------
class Curator:
    def __init__(self, seed: dict[str, Any]) -> None:
        self.p = resolve_params(seed)
        self.ir: dict[str, dict[str, Any]] = {}

    def v(self, key: str) -> Any:
        return self.p[key][0]

    def cite(self, *keys: str) -> list[str]:
        return [f"{k}={self.p[k][0]} [{self.p[k][1]}]" for k in keys]

    def put(self, role: str, values: dict[str, str], rule: str, inputs: list[str],
            lch: dict[str, LCH] | None = None, alias: str | None = None) -> None:
        ext: dict[str, Any] = {"origin": "imputed", "rule": rule, "inputs": inputs}
        if lch:
            ext["oklch"] = {m: [round(x, 4) for x in lch[m]] for m in lch}
        if alias:
            ext["alias"] = alias
        self.ir[role] = {**values, "$extensions": {EXT: ext}}

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
            ("color.border.bold", "offset.border.bold", False),
        ):
            lch = {}
            for m in MODES:
                off = self.v(key) if key else 0.0
                lch[m] = grey(self.bg(m) + (off if absolute else self.sign(m) * off))
            rule = "mode reference" if key is None else (
                "reference + absolute offset" if absolute else "reference + offset toward text")
            self.put(role, {m: hex_of(lch[m]) for m in MODES}, rule,
                     self.cite("L-light-bg", "L-dark-bg", *([key] if key else [])), lch)

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
                 "color.text at alpha", self.cite("alpha.border"))

    def brand(self) -> None:
        hue = float(self.v("brand.hue"))
        cusp_l = max((i * STEP for i in range(1, int(1 / STEP))), key=lambda lt: max_chroma(lt, hue))
        cusp_c = max_chroma(cusp_l, hue)
        chroma = cusp_c if self.v("brand.chroma") == "cusp" else float(self.v("brand.chroma"))
        self.brand_hue, self.brand_c, self.cusp_l = hue, chroma, cusp_l
        base = self.cite("brand.hue", "brand.chroma") + [f"cusp L={cusp_l:.3f} C={cusp_c:.4f} (derived)"]

        def best_text(colour: str) -> str:
            return "#000000" if contrast(colour, "#000000") >= contrast(colour, "#ffffff") else "#ffffff"

        lch = {m: self.solve(hue, chroma, cusp_l, lambda c, m=m: (
            contrast(c, best_text(c)) >= self.v("target.text.inverse")
            and self.on_all_grounds(m, self.v("target.graphic"))(c)), "brand fill") for m in MODES}
        self.put("color.background.brand.bold", {m: hex_of(lch[m]) for m in MODES},
                 "brand hue nearest its cusp: inverse text reaches target, and 3:1 on every ground",
                 base + self.cite("target.text.inverse", "target.graphic"), lch)
        self.put("color.text.inverse", {m: best_text(self.val("color.background.brand.bold", m)) for m in MODES},
                 "black or white, whichever has more contrast on the brand fill", ["color.background.brand.bold"])
        self.put("color.background.brand.subtlest",
                 {m: composite(self.val("color.background.brand.bold", m)
                               + f"{round(self.v('alpha.brand.subtlest') * 255):02x}", self.val("color.surface", m))
                  for m in MODES},
                 "brand fill at alpha over color.surface", self.cite("alpha.brand.subtlest"))
        for role, key in (("color.border.brand", "target.graphic"), ("color.link", "target.link")):
            lch = {m: self.solve(hue, chroma, cusp_l, self.on_all_grounds(m, self.v(key)), role) for m in MODES}
            self.put(role, {m: hex_of(lch[m]) for m in MODES},
                     "brand hue nearest its cusp reaching the target on every ground", base + self.cite(key), lch)

    def secondary(self) -> None:
        hue = float(self.v("secondary.hue") if self.v("secondary.hue") is not None else self.brand_hue)
        chroma = self.brand_c * float(self.v("secondary.chromaRatio"))
        inputs = self.cite("secondary.hue", "secondary.chromaRatio")
        for role, extra in (("color.background.selected", 0.0), ("color.background.selected.hovered", STEP * 10)):
            lch = {}
            for m in MODES:
                lightness = self.bg(m) + self.sign(m) * (self.v("offset.background.selected") + extra)
                lch[m] = (lightness, min(max_chroma(lightness, hue), chroma), hue)
            self.put(role, {m: hex_of(lch[m]) for m in MODES},
                     "secondary at reduced chroma, offset from the ground toward text",
                     inputs + self.cite("offset.background.selected"), lch)
        lch = {m: self.solve(hue, self.brand_c, self.cusp_l, self.on_all_grounds(m, self.v("target.graphic")),
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
        inputs = self.cite("brand.hue", "walk.slots", "walk.angle", "walk.lightness", "walk.chromaCeiling",
                           "target.graphic")
        per_mode: dict[str, list[LCH]] = {}
        for m in MODES:
            test = self.on_all_grounds(m, self.v("target.graphic"))
            anchor = float(self.v("walk.lightness"))
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
        for name, hue, chroma, count in (("sequential", self.brand_hue, self.brand_c, 5),
                                         ("diverging.positive", self.brand_hue, self.brand_c, 3),
                                         ("diverging.negative", danger, cap, 3),
                                         ("diverging.alt-positive", success, cap, 3)):
            for i in range(count):
                lch = {}
                for m in MODES:
                    lo, hi = spans[m]
                    lightness = lo + (hi - lo) * (i / (count - 1))
                    lch[m] = (lightness, min(max_chroma(lightness, hue), chroma), hue)
                self.put(f"color.chart.{name}.{i + 1}", {m: hex_of(lch[m]) for m in MODES},
                         "evenly spaced lightness at a fixed hue, chroma capped", ["prototype"], lch)
        for i in range(4):
            lch = {}
            for m in MODES:
                a = self.bg(m) + self.sign(m) * self.v("offset.border.bold")
                b = self.bg(m) + self.sign(m) * self.v("offset.text.subtle")
                lch[m] = grey(a + (b - a) * i / 3)
            self.put(f"color.chart.muted.{i + 1}", {m: hex_of(lch[m]) for m in MODES},
                     "greys from border.bold to text.subtle", ["prototype"], lch)

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


def cmd_curate(args: argparse.Namespace) -> None:
    for name in profile_names(args):
        seed = json.loads((PROFILES / name / "seed.json").read_text(encoding="utf-8"))
        ir = Curator(seed).run()
        (PROFILES / name / "ir.json").write_text(json.dumps(ir, indent=2) + "\n", encoding="utf-8")
        log.info("curated %-16s %d roles", name, len(ir) - 1)


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
        log.info("built    %-16s dtcg/{light,dark}.tokens.json + resolver + richdocs projection", name)


def project_richdocs(ir: dict[str, Any]) -> dict[str, Any]:
    """Map IR roles onto richdocs' current design-tokens.json keys. A stand-in until migration."""
    def r(role: str, m: str) -> str:
        return ir[role][m]

    def seq(prefix: str, count: int, m: str) -> list[str]:
        return [r(f"{prefix}.{i}", m) for i in range(1, count + 1)]

    themes, cyto, plotly, status = {}, {}, {}, {}
    for m in MODES:
        border = composite(r("color.border", m), r("color.surface", m))
        themes[m] = {"bg": r("color.surface", m), "fg": r("color.text", m), "muted": r("color.text.subtle", m),
                     "accent": r("color.background.brand.bold", m), "surface": r("color.surface.raised", m),
                     "border": border, "onAccent": r("color.text.inverse", m), "link": r("color.link", m),
                     "radius": "12px", "pill": "999px"}
        cyto[m] = {"nodeFill": r("color.background.brand.subtlest", m), "nodeBorder": r("color.border.brand", m),
                   "nodeLabel": r("color.text", m), "nodeFillAlt": r("color.background.selected", m),
                   "edge": r("color.border.bold", m), "edgeLabel": r("color.text.subtle", m),
                   "edgeLabelBg": r("color.surface", m), "compoundBg": r("color.surface.sunken", m),
                   "compoundBorder": composite(r("color.border", m), r("color.surface.sunken", m)),
                   "selected": r("color.border.selected", m), "shape": "round-rectangle", "roundness": 8}
        plotly[m] = {"paper": r("color.surface.raised", m), "plot": r("color.surface", m),
                     "font": r("color.text", m), "grid": border,
                     "series": seq("color.chart.categorical", 8, m),
                     "seriesAlt": [r(f"color.chart.categorical.{i}", m) for i in range(5, 13)],
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


def cmd_install(args: argparse.Namespace) -> None:
    for name in profile_names(args):
        target = PROJECT_THEMES / name
        target.mkdir(parents=True, exist_ok=True)
        (target / "design-tokens.json").write_text(
            (PROFILES / name / "design-tokens.json").read_text(encoding="utf-8"), encoding="utf-8")
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

Four seeds, each stating **only a hue**, taken from the light accent of one existing richdocs theme.
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

The gallery places each hue-only theme beside the theme its hue came from:
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
        ("init-seeds", cmd_init_seeds, "Write hue-only seeds from the four richdocs themes' light accents"),
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
