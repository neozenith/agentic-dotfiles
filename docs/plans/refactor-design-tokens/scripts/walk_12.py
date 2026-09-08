#!/usr/bin/env -S uv run python
"""Compute the 12-slot golden-angle walk in OKLCH and report its gamut cost.

Research flagged that constant-L, constant-C hue rotation is the operation most likely
to leave sRGB, and that the effective chroma for a whole walk is the MINIMUM over its
hues. With 12 slots instead of 7 that constraint binds harder, so this measures it.

Seeded on osakanights' light accent #5c4295. Gamut mapping reduces chroma and holds
L and H, per CSS Color 4.
"""

from __future__ import annotations

import math

SLOTS = 12
GOLDEN_ANGLE = 137.5
SEED_HEX = "#5c4295"  # osakanights light accent

# OKLab <-> linear sRGB matrices (Bjorn Ottosson)
_LMS_FROM_RGB = (
    (0.4122214708, 0.5363325363, 0.0514459929),
    (0.2119034982, 0.6806995451, 0.1073969566),
    (0.0883024619, 0.2817188376, 0.6299787005),
)
_LAB_FROM_LMS = (
    (0.2104542553, 0.7936177850, -0.0040720468),
    (1.9779984951, -2.4285922050, 0.4505937099),
    (0.0259040371, 0.7827717662, -0.8086757660),
)
_LMS_FROM_LAB = (
    (1.0, 0.3963377774, 0.2158037573),
    (1.0, -0.1055613458, -0.0638541728),
    (1.0, -0.0894841775, -1.2914855480),
)
_RGB_FROM_LMS = (
    (4.0767416621, -3.3077115913, 0.2309699292),
    (-1.2684380046, 2.6097574011, -0.3413193965),
    (-0.0041960863, -0.7034186147, 1.7076147010),
)


def _mul(m: tuple, v: tuple[float, float, float]) -> tuple[float, float, float]:
    return tuple(sum(row[i] * v[i] for i in range(3)) for row in m)  # type: ignore[return-value]


def srgb_to_linear(c: float) -> float:
    return c / 12.92 if c <= 0.04045 else ((c + 0.055) / 1.055) ** 2.4


def linear_to_srgb(c: float) -> float:
    return c * 12.92 if c <= 0.0031308 else 1.055 * (c ** (1 / 2.4)) - 0.055


def hex_to_oklch(hexs: str) -> tuple[float, float, float]:
    r, g, b = (int(hexs[i : i + 2], 16) / 255 for i in (1, 3, 5))
    lms = _mul(_LMS_FROM_RGB, (srgb_to_linear(r), srgb_to_linear(g), srgb_to_linear(b)))
    lab = _mul(_LAB_FROM_LMS, tuple(math.copysign(abs(x) ** (1 / 3), x) for x in lms))
    lightness, a, bb = lab
    return lightness, math.hypot(a, bb), math.degrees(math.atan2(bb, a)) % 360


def oklch_to_linear_rgb(lightness: float, chroma: float, hue: float) -> tuple[float, float, float]:
    rad = math.radians(hue)
    lab = (lightness, chroma * math.cos(rad), chroma * math.sin(rad))
    lms = _mul(_LMS_FROM_LAB, lab)
    return _mul(_RGB_FROM_LMS, tuple(x**3 for x in lms))


def in_gamut(lightness: float, chroma: float, hue: float, *, eps: float = 1e-4) -> bool:
    return all(-eps <= c <= 1 + eps for c in oklch_to_linear_rgb(lightness, chroma, hue))


def to_hex(lightness: float, chroma: float, hue: float) -> str:
    rgb = oklch_to_linear_rgb(lightness, chroma, hue)
    vals = [max(0, min(255, round(linear_to_srgb(max(0.0, min(1.0, c))) * 255))) for c in rgb]
    return "#{:02x}{:02x}{:02x}".format(*vals)


def max_chroma(lightness: float, hue: float, *, hi: float = 0.5) -> float:
    """Binary search the largest in-gamut chroma at this L and H."""
    lo = 0.0
    for _ in range(28):
        mid = (lo + hi) / 2
        if in_gamut(lightness, mid, hue):
            lo = mid
        else:
            hi = mid
    return lo


def main() -> None:
    seed_l, seed_c, seed_h = hex_to_oklch(SEED_HEX)
    print(f"seed {SEED_HEX}  ->  L {seed_l:.4f}  C {seed_c:.4f}  H {seed_h:.2f}deg")

    hues = [(seed_h + i * GOLDEN_ANGLE) % 360 for i in range(SLOTS)]

    print(f"\nPer-slot max in-gamut chroma at the seed's L ({seed_l:.3f})")
    print(f"  {'slot':>4} {'hue':>7} {'maxC':>7}  {'at seed C':>10}")
    caps = []
    for i, h in enumerate(hues):
        cap = max_chroma(seed_l, h)
        caps.append(cap)
        flag = "ok" if cap >= seed_c else f"CLIPS ({cap / seed_c:.0%} of seed C)"
        print(f"  {i:>4} {h:>7.2f} {cap:>7.4f}  {flag:>10}")

    effective = min(caps)
    print(f"\neffective chroma for the whole walk = min over hues = {effective:.4f}")
    print(f"  seed chroma {seed_c:.4f}  ->  retained {effective / seed_c:.1%}")
    worst = hues[caps.index(effective)]
    print(f"  binding hue: {worst:.2f}deg (slot {caps.index(effective)})")

    print(f"\nThe walk at the effective chroma (L {seed_l:.3f}, C {effective:.4f})")
    print(f"  {'slot':>4} {'hue':>7}  {'hex':>9}")
    for i, h in enumerate(hues):
        print(f"  {i:>4} {h:>7.2f}  {to_hex(seed_l, effective, h):>9}")

    print("\nAdjacency: minimum hue separation between any two slots")
    sorted_h = sorted(hues)
    gaps = [
        (sorted_h[(i + 1) % SLOTS] - sorted_h[i]) % 360 for i in range(SLOTS)
    ]
    print(f"  smallest gap {min(gaps):.2f}deg   largest {max(gaps):.2f}deg")
    print(f"  ideal even spacing at {SLOTS} slots would be {360 / SLOTS:.2f}deg")

    print(f"\nFor comparison, effective chroma if the walk stopped at 7 slots:")
    print(f"  {min(caps[:7]):.4f}  (retained {min(caps[:7]) / seed_c:.1%})")


if __name__ == "__main__":
    main()
