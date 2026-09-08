#!/usr/bin/env -S uv run python
"""Verify the chosen neutral reference: dark bg 0.15, light bg 0.90.

Confirms the triples separate, records what each role resolves to, and reports the
headroom the maintainer wanted above light `bg-light` for a bright-white top border.
"""

from __future__ import annotations

DARK_BG, LIGHT_BG = 0.15, 0.90
OFF_TOWARD_TEXT = {"text-muted": 0.65, "text": 0.90}
OFF_ABSOLUTE = {"bg-dark": -0.05, "bg-light": +0.05}
ORDER = ("bg-dark", "bg", "bg-light", "text-muted", "text")


def y_of(l: float) -> float:
    return max(min(l, 1.0), 0.0) ** 3


def linear_to_srgb(v: float) -> float:
    v = min(max(v, 0.0), 1.0)
    return v * 12.92 if v <= 0.0031308 else 1.055 * (v ** (1 / 2.4)) - 0.055


def hexof(l: float) -> str:
    v = round(linear_to_srgb(y_of(l)) * 255)
    return f"#{v:02x}{v:02x}{v:02x}"


def contrast(a: float, b: float) -> float:
    ya, yb = y_of(a), y_of(b)
    hi, lo = max(ya, yb), min(ya, yb)
    return (hi + 0.05) / (lo + 0.05)


def build(bg: float, *, dark: bool) -> dict[str, float]:
    sign = 1.0 if dark else -1.0
    roles = {"bg": bg}
    for role, off in OFF_TOWARD_TEXT.items():
        roles[role] = min(max(bg + sign * off, 0.0), 1.0)
    for role, off in OFF_ABSOLUTE.items():
        roles[role] = min(max(bg + off, 0.0), 1.0)
    return roles


def solve(bg: float, ratio: float, *, lighter: bool) -> float | None:
    rng = range(int(bg * 100) + 1, 101) if lighter else range(int(bg * 100) - 1, -1, -1)
    for i in rng:
        if contrast(bg, i / 100) >= ratio:
            return i / 100
    return None


def main() -> None:
    d, lt = build(DARK_BG, dark=True), build(LIGHT_BG, dark=False)

    print(f"CHOSEN: dark bg {DARK_BG:.2f}, light bg {LIGHT_BG:.2f}\n")
    print(f"{'role':<12} {'dark L':>7} {'hex':>9}   |{'light L':>8} {'hex':>9}")
    for role in ORDER:
        print(f"{role:<12} {d[role]:>7.2f} {hexof(d[role]):>9}   |{lt[role]:>8.2f} {hexof(lt[role]):>9}")

    print("\n8-bit separation of the bg triples")
    for name, roles in (("dark ", d), ("light", lt)):
        vals = [int(hexof(roles[r])[1:3], 16) for r in ("bg-dark", "bg", "bg-light")]
        gaps = [vals[1] - vals[0], vals[2] - vals[1]]
        note = "INVISIBLE" if min(gaps) < 3 else ("faint" if min(gaps) < 8 else "clear")
        print(f"  {name} {vals}  gaps {gaps}  {note}")

    print("\nAchieved contrast")
    worst = 0.0
    for bg in ("bg-dark", "bg", "bg-light"):
        for fg in ("text-muted", "text"):
            cd, cl = contrast(d[bg], d[fg]), contrast(lt[bg], lt[fg])
            worst = max(worst, abs(cd - cl))
            tag = "AAA" if min(cd, cl) >= 7 else ("AA " if min(cd, cl) >= 4.5 else "FAIL")
            print(f"  {bg:<9} x {fg:<11} dark {cd:6.2f}:1  light {cl:6.2f}:1"
                  f"  delta {abs(cd - cl):5.2f}  [{tag}]")
    print(f"  worst dark/light divergence: {worst:.2f}")

    print("\nHeadroom above light bg-light (the bright-white border the maintainer wanted)")
    top = lt["bg-light"]
    print(f"  light bg-light  L {top:.2f}  {hexof(top)}")
    print(f"  pure white      L 1.00  {hexof(1.0)}   contrast vs bg-light: {contrast(top, 1.0):.2f}:1")
    print(f"  room remaining  {1.0 - top:.2f} L  ({int((1.0 - top) / 0.05)} steps of 0.05)")

    print("\nWhere a 3:1 border lands (the unnamed mid-ramp role)")
    for name, roles, lighter in (("dark ", d, True), ("light", lt, False)):
        for bg in ("bg-dark", "bg", "bg-light"):
            got = solve(roles[bg], 3.0, lighter=lighter)
            print(f"  {name} on {bg:<9} L {got:.2f}  {hexof(got)}  ({contrast(roles[bg], got):.2f}:1)")


if __name__ == "__main__":
    main()
