#!/usr/bin/env -S uv run python
"""Compare richdocs' colour roles against diagram-design's, with real values.

Answers: what are the 8 and the 10, and where do they actually line up?
Purposes for diagram-design come from its style-guide.md role table; purposes for
richdocs are inferred from where the value is consumed and are marked as such.
"""

from __future__ import annotations

import json
from pathlib import Path

PACK = Path("skills/richdocs/resources/themes/osakanights/design-tokens.json")

# From ~/foss/diagram-design/skills/diagram-design/references/style-guide.md:17-28
DIAGRAM_DESIGN = {
    "paper": ("Page background, default node fill", "#f5f5f5", "#2d3142"),
    "paper-2": ("Diagram container bg, secondary fill", "#ececec", "#393e53"),
    "ink": ("Primary text, primary stroke", "#2d3142", "#f5f5f5"),
    "muted": ("Secondary text, default arrow stroke", "#4f5d75", "#bfc0c0"),
    "soft": ("Sublabels, boundary labels", "#7a8399", "#8e98ac"),
    "rule": ("Hairline borders", "rgba(45,49,66,0.12)", "rgba(245,245,245,0.12)"),
    "rule-solid": ("Stronger borders, baselines", "#bfc0c0", "rgba(191,192,192,0.25)"),
    "accent": ("Focal / 1-2 max per diagram", "#eb6c36", "#f08a59"),
    "accent-tint": ("Fill for accent-bordered boxes", "rgba(235,108,54,0.08)", "rgba(240,138,89,0.10)"),
    "link": ("HTTP/API calls, external arrows", "#2e5aa8", "#6a95d8"),
}

# Prospective mapping. None = no counterpart on that side.
MAPPING: list[tuple[str | None, str | None, str]] = [
    ("bg", "paper", "exact - the page ground"),
    ("surface", "paper-2", "exact - the raised/secondary fill"),
    ("fg", "ink", "exact - primary text"),
    ("muted", "muted", "exact - secondary text"),
    (None, "soft", "GAP in richdocs - a third text tier below muted"),
    ("border", "rule", "partial - richdocs has ONE border; dd splits hairline vs solid"),
    (None, "rule-solid", "GAP in richdocs - the stronger border tier"),
    ("accent", "accent", "exact - the focal colour"),
    (None, "accent-tint", "GAP as a TOKEN - richdocs computes it at render via rdMix()"),
    ("onAccent", None, "GAP in dd - richdocs names the text colour that sits ON accent"),
    ("link", "link", "exact - external/API links"),
]


def main() -> None:
    data = json.loads(PACK.read_text(encoding="utf-8"))
    light, dark = data["themes"]["light"], data["themes"]["dark"]
    colour_roles = [k for k, v in light.items() if isinstance(v, str) and v.startswith("#")]

    print(f"richdocs colour roles ({len(colour_roles)}): {colour_roles}")
    print(f"non-colour keys in the same group: "
          f"{[k for k in light if k not in colour_roles]}")
    print(f"\ndiagram-design semantic roles ({len(DIAGRAM_DESIGN)}): {list(DIAGRAM_DESIGN)}")

    print("\n" + "=" * 108)
    print(f"{'richdocs':<10} {'light':>9} {'dark':>9}  | {'diagram-design':<12} | {'verdict'}")
    print("=" * 108)
    for rd, dd, note in MAPPING:
        rl = light.get(rd, "") if rd else ""
        rdk = dark.get(rd, "") if rd else ""
        print(f"{rd or '--':<10} {rl:>9} {rdk:>9}  | {dd or '--':<12} | {note}")

    print("\nUnmapped on either side:")
    mapped_rd = {m[0] for m in MAPPING if m[0]}
    mapped_dd = {m[1] for m in MAPPING if m[1]}
    print(f"  richdocs roles not in the mapping:       {sorted(set(colour_roles) - mapped_rd) or 'none'}")
    print(f"  diagram-design roles not in the mapping: {sorted(set(DIAGRAM_DESIGN) - mapped_dd) or 'none'}")

    print("\nCounts")
    exact = sum(1 for m in MAPPING if m[2].startswith("exact"))
    print(f"  exact matches            {exact}")
    print(f"  gaps in richdocs         {sum(1 for m in MAPPING if m[0] is None)}")
    print(f"  gaps in diagram-design   {sum(1 for m in MAPPING if m[1] is None)}")
    print(f"  partial                  {sum(1 for m in MAPPING if m[2].startswith('partial'))}")
    print(f"  union role count         {len(mapped_rd | mapped_dd)}")


if __name__ == "__main__":
    main()
