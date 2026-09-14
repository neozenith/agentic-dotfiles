#!/usr/bin/env -S uv run python
"""Test whether options C, E and D are one rule with one parameter.

Rule: chroma_i = min(max_chroma(L_i, h_i), ceiling), with L_i solved per slot per mode.
  ceiling = the walk's gamut floor (min over hues)  ->  should reproduce C (every slot equal)
  ceiling = the seed's chroma                        ->  should reproduce E
  ceiling = unbounded                                 ->  should reproduce D
Compares against the page generator's own C, D and E builds.
"""

from __future__ import annotations

import importlib.util
import logging
from pathlib import Path

log = logging.getLogger(__name__)

_spec = importlib.util.spec_from_file_location("q11", Path(__file__).with_name("build_q11_q3_doc.py"))
q = importlib.util.module_from_spec(_spec)  # type: ignore[arg-type]
_spec.loader.exec_module(q)  # type: ignore[union-attr]


def unified(mode: str, ceiling: float | str) -> list[tuple[float, float, float]]:
    if ceiling == "floor":
        # a floor is self-referential: solve at full chroma, take the floor, re-solve at it
        lights = [q.solve_lightness(h, mode, q.max_chroma) for h in q.HUES]
        floor = min(q.max_chroma(lt, h) for lt, h in zip(lights, q.HUES))
        lights = [q.solve_lightness(h, mode, lambda _l, _h: floor) for h in q.HUES]
        floor = min(q.max_chroma(lt, h) for lt, h in zip(lights, q.HUES))
        return [(lt, floor, h) for lt, h in zip(lights, q.HUES)]
    cap = float(ceiling)

    def rule(lightness: float, hue: float) -> float:
        return min(q.max_chroma(lightness, hue), cap)

    return [(lt, rule(lt, h), h) for h in q.HUES for lt in [q.solve_lightness(h, mode, rule)]]


def worst_diff(a: list, b: list) -> float:
    return max(abs(x - y) for sa, sb in zip(a, b) for x, y in zip(sa, sb))


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    for mode in ("dark", "light"):
        for label, ceiling, option in (("floor", "floor", "C"), ("seed", q.SEED_C, "E"), ("unbounded", 1.0, "D")):
            diff = worst_diff(unified(mode, ceiling), q.build(option, mode))
            log.info("%-5s ceiling=%-9s vs option %s: worst L/C/H difference %.5f  %s",
                     mode, label, option, diff, "MATCH" if diff < 1e-3 else "DIFFERS")


if __name__ == "__main__":
    main()
