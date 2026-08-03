#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "Pillow>=10.1.0",
#   "numpy>=1.26.0",
# ]
# ///
"""grid — a labelled coordinate grid for pinpointing regions by cell reference.

A shared vocabulary for "which part of the image": overlay a grid whose columns are
letters (A, B, C, … Z, AA, …) and rows are numbers (1, 2, 3, …), then refer to any
rectangle as a spreadsheet-style range like ``C4:F5``. The overlay is a visual aid; the
resolver turns a range back into a pixel box you can feed straight into an ``art_pipe``
spec (e.g. a ``perspective-overlay`` ``dst`` quad), so a human and the agent point at the
same place without exchanging raw pixel coordinates.

  overlay  draw the labelled grid onto an image
  resolve  print the pixel box (and quad) for a cell range, for use in a pipeline spec
"""

from __future__ import annotations

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw, ImageFont

# ── Configuration ──────────────────────────────────────────────────────────
log = logging.getLogger(__name__)

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

DEFAULT_CELL = 200
GRID_RGB = (0, 255, 0)


# ── Pure cell/label maths (fully unit-tested, no IO) ───────────────────────
def column_label(index: int) -> str:
    """0-based column index → spreadsheet letters (0→A, 25→Z, 26→AA)."""
    if index < 0:
        raise ValueError(f"column index must be non-negative, got {index}")
    label = ""
    index += 1
    while index > 0:
        index, rem = divmod(index - 1, 26)
        label = chr(ord("A") + rem) + label
    return label


def column_index(label: str) -> int:
    """Spreadsheet letters → 0-based column index (A→0, Z→25, AA→26)."""
    label = label.strip().upper()
    if not label or not label.isalpha():
        raise ValueError(f"bad column label {label!r}")
    index = 0
    for ch in label:
        index = index * 26 + (ord(ch) - ord("A") + 1)
    return index - 1


def parse_cell(ref: str) -> tuple[int, int]:
    """A cell like ``C4`` → 0-based (col, row). Rows are 1-based in the reference."""
    ref = ref.strip().upper()
    letters = "".join(c for c in ref if c.isalpha())
    digits = "".join(c for c in ref if c.isdigit())
    if not letters or not digits:
        raise ValueError(f"bad cell reference {ref!r} (expected e.g. C4)")
    return column_index(letters), int(digits) - 1


def cells_to_box(ref: str, cell: int = DEFAULT_CELL) -> tuple[int, int, int, int]:
    """A range like ``C4:F5`` → pixel box ``(x0, y0, x1, y1)`` at the given cell size.

    A single cell (``C4``) is treated as the 1×1 range ``C4:C4``. The box spans the OUTER
    edges of the named cells, so ``C4:F5`` covers columns C–F and rows 4–5 inclusive — the
    same rectangle a reader would trace on the overlay.
    """
    lo, _, hi = ref.partition(":")
    c0, r0 = parse_cell(lo)
    c1, r1 = parse_cell(hi if hi else lo)
    # Normalise the corners *before* growing by one cell, so a range given in either
    # order (C4:F5 or F5:C4) spans the same outer edges.
    col_lo, col_hi = min(c0, c1), max(c0, c1)
    row_lo, row_hi = min(r0, r1), max(r0, r1)
    return col_lo * cell, row_lo * cell, (col_hi + 1) * cell, (row_hi + 1) * cell


def box_to_quad(box: tuple[int, int, int, int]) -> list[list[int]]:
    """Axis-aligned box → TL, TR, BR, BL quad (the order ``perspective-overlay`` wants)."""
    x0, y0, x1, y1 = box
    return [[x0, y0], [x1, y0], [x1, y1], [x0, y1]]


# A distinct, high-contrast palette for proposed regions (RGB).
HIGHLIGHT_PALETTE = [
    (240, 150, 40),  # amber
    (250, 205, 60),  # gold
    (56, 189, 248),  # sky
    (74, 222, 128),  # green
    (244, 114, 182),  # pink
    (167, 139, 250),  # violet
]


def parse_highlight_spec(spec: str) -> list[tuple[str, str, tuple[int, int, int] | None]]:
    """Parse ``"C5:F6=AURIZON,H2:H3=Roy#22d3ee"`` → [(range, label, colour|None)].

    A per-entry ``#RRGGBB`` suffix pins a colour; otherwise the caller cycles the palette.
    This is the format the agent uses to *propose* regions the human then corrects.
    """
    out: list[tuple[str, str, tuple[int, int, int] | None]] = []
    for chunk in spec.split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        rng, _, rest = chunk.partition("=")
        label, _, hexcol = rest.partition("#")
        colour: tuple[int, int, int] | None = None
        if hexcol:
            h = hexcol.strip().lstrip("#")
            if len(h) != 6:
                raise ValueError(f"bad colour {hexcol!r} in highlight (expected RRGGBB)")
            colour = (int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16))
        # Validate the range eagerly so a typo fails at parse time, not mid-draw.
        cells_to_box(rng.strip())
        out.append((rng.strip(), label.strip(), colour))
    return out


# ── Overlay (IO; the font-fallback line is the only uncovered branch) ──────
def _font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    for path in (
        "/System/Library/Fonts/Supplemental/Arial Bold.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:  # pragma: no cover - depends on host fonts
            continue
    return ImageFont.load_default(size)  # pragma: no cover - only on a font-less host


def _label(d: ImageDraw.ImageDraw, xy: tuple[int, int], text: str, font: Any, fill: tuple[int, int, int]) -> None:
    """Draw a label with a black outline so it stays legible on any background.

    Bright green on a bright sky is invisible; a stroked glyph reads on both light and dark
    without having to sample the local background colour.
    """
    d.text(xy, text, fill=fill, font=font, stroke_width=3, stroke_fill=(0, 0, 0))


def overlay_grid(
    img: Image.Image,
    cell: int = DEFAULT_CELL,
    highlights: list[tuple[str, str, tuple[int, int, int] | None]] | None = None,
) -> Image.Image:
    """Return a copy of ``img`` with a labelled letter×number grid, plus optional highlights.

    ``highlights`` fills named cell ranges with a translucent colour and a label — used to
    *propose* regions (e.g. where the agent thinks the doors are) for the human to correct.
    """
    out = img.convert("RGBA").copy()
    w, h = out.size
    font = _font(max(14, cell // 9))

    if highlights:
        fill_layer = Image.new("RGBA", (w, h), (0, 0, 0, 0))
        fd = ImageDraw.Draw(fill_layer)
        for i, (rng, label, colour) in enumerate(highlights):
            col = colour if colour is not None else HIGHLIGHT_PALETTE[i % len(HIGHLIGHT_PALETTE)]
            x0, y0, x1, y1 = cells_to_box(rng, cell)
            fd.rectangle([x0, y0, x1, y1], fill=(*col, 80), outline=(*col, 255), width=5)
            if label:
                _label(fd, (x0 + 8, y0 + 6), f"{label} [{rng}]", font, col)
        out = Image.alpha_composite(out, fill_layer)

    d = ImageDraw.Draw(out)
    for i, x in enumerate(range(0, w, cell)):
        d.line([(x, 0), (x, h)], fill=GRID_RGB, width=2)
        _label(d, (x + 4, 4), column_label(i), font, GRID_RGB)
    for j, y in enumerate(range(0, h, cell)):
        d.line([(0, y), (w, y)], fill=GRID_RGB, width=2)
        _label(d, (4, y + 4), str(j + 1), font, GRID_RGB)
    return out.convert("RGB")


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="grid.py", description="Labelled coordinate grid + cell-range resolver.")
    sub = p.add_subparsers(dest="command", required=True)

    ov = sub.add_parser("overlay", help="Draw a labelled grid onto an image")
    ov.add_argument("image", type=Path)
    ov.add_argument("-o", "--out", type=Path, required=True)
    ov.add_argument("--cell", type=int, default=DEFAULT_CELL, help=f"Cell size px (default {DEFAULT_CELL})")
    ov.add_argument(
        "--highlight",
        default=None,
        help='Propose regions: "C5:F6=AURIZON,H2:H3=Roy#22d3ee" (range=label[#RRGGBB], comma-separated)',
    )

    rs = sub.add_parser("resolve", help="Print the pixel box + quad for a cell range like C4:F5")
    rs.add_argument("cells", help="Cell range, e.g. C4:F5 (or a single cell C4)")
    rs.add_argument("--cell", type=int, default=DEFAULT_CELL, help=f"Cell size px (default {DEFAULT_CELL})")

    for q in (ov, rs):
        q.add_argument("-v", "--verbose", action="store_true")
        q.add_argument("-q", "--quiet", action="store_true")
    return p


def main(args: argparse.Namespace) -> int:
    if args.command == "overlay":
        highlights = parse_highlight_spec(args.highlight) if getattr(args, "highlight", None) else None
        with Image.open(args.image) as im:
            out = overlay_grid(im, args.cell, highlights)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        out.save(args.out)
        sys.stdout.write(f"  saved: {args.out}\n")
        return 0

    box = cells_to_box(args.cells, args.cell)
    payload: dict[str, Any] = {"cells": args.cells, "cell": args.cell, "box": list(box), "quad": box_to_quad(box)}
    sys.stdout.write(json.dumps(payload) + "\n")
    return 0


if __name__ == "__main__":  # pragma: no cover
    parser = build_parser()
    ns = parser.parse_args()
    logging.basicConfig(
        level=logging.DEBUG if ns.verbose else logging.ERROR if ns.quiet else logging.INFO,
        format="%(levelname)s: %(message)s",
    )
    try:
        raise SystemExit(main(ns))
    except (ValueError, OSError) as exc:
        log.error("%s", exc)
        raise SystemExit(1) from exc
