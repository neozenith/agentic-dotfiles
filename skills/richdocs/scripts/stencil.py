#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Browse and extract vendored draw.io stencils as standalone SVGs.

The stencil library lives in ../assets/stencils.json.zip: a single-entry
ZIP whose `stencils.json` maps draw.io stencil ids ("<pack>/<name>", e.g.
"mxgraph.aws4/lambda") to {"w", "h", "svg", "stencil_b64"}. The `svg` value
is the inner SVG fragment in 0..w / 0..h coordinates using `currentColor`.
"""

from __future__ import annotations

import argparse
import difflib
import functools
import io
import json
import sys
import zipfile
from collections import Counter
from pathlib import Path
from typing import Any
from xml.sax.saxutils import escape

# ── Configuration ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_ZIP = SCRIPT_DIR.parent / "assets" / "stencils.json.zip"
ZIP_ENTRY = "stencils.json"
GRID_COLS = 6
GRID_CELL = 120.0
GRID_ICON = 72.0
GRID_LABEL_PT = 9.0


# ── Core ───────────────────────────────────────────────────────────────────
@functools.cache
def load_stencils(zip_path: Path = DEFAULT_ZIP) -> dict[str, dict[str, Any]]:
    """Load the stencil library from the zip, fully in memory, cached."""
    raw = zip_path.read_bytes()
    with zipfile.ZipFile(io.BytesIO(raw)) as zf:
        data: dict[str, dict[str, Any]] = json.loads(zf.read(ZIP_ENTRY))
    return data


def pack_counts(stencils: dict[str, dict[str, Any]]) -> list[tuple[str, int]]:
    """Return (pack_prefix, entry_count) pairs sorted by count descending, then name."""
    counts = Counter(sid.split("/", 1)[0] for sid in stencils)
    return sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))


def filter_ids(
    stencils: dict[str, dict[str, Any]],
    *,
    pack: str | None = None,
    term: str | None = None,
    limit: int | None = None,
) -> list[str]:
    """Sorted stencil ids, optionally filtered by pack prefix and/or substring term."""
    ids = sorted(stencils)
    if pack is not None:
        ids = [sid for sid in ids if sid.split("/", 1)[0] == pack]
    if term is not None:
        needle = term.lower()
        ids = [sid for sid in ids if needle in sid.lower()]
    if limit is not None:
        ids = ids[:limit]
    return ids


def close_matches(
    stencils: dict[str, dict[str, Any]], missing_id: str, n: int = 5
) -> list[str]:
    """Up to n suggestions for an unknown id: substring hits first, then difflib."""
    substr = filter_ids(stencils, term=missing_id, limit=n)
    if len(substr) >= n:
        return substr[:n]
    fuzzy = difflib.get_close_matches(missing_id, list(stencils), n=n, cutoff=0.4)
    seen = list(substr)
    for sid in fuzzy:
        if sid not in seen:
            seen.append(sid)
    return seen[:n]


def build_svg(
    entry: dict[str, Any], *, color: str | None = None, size: float | None = None
) -> str:
    """Wrap a stored stencil fragment into a standalone SVG document."""
    w = float(entry["w"])
    h = float(entry["h"])
    frag = str(entry["svg"])
    if color is not None:
        frag = frag.replace("currentColor", color)
    width = size if size is not None else w
    height = width * h / w
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w:g} {h:g}" '
        f'width="{width:g}" height="{height:g}">{frag}</svg>'
    )


def build_grid_svg(
    stencils: dict[str, dict[str, Any]],
    ids: list[str],
    *,
    color: str | None = None,
    cols: int = GRID_COLS,
) -> str:
    """Composite the given stencil ids into one labelled contact-sheet SVG."""
    n = len(ids)
    rows = (n + cols - 1) // cols
    total_w = cols * GRID_CELL
    total_h = max(rows, 1) * GRID_CELL
    cells: list[str] = []
    for i, sid in enumerate(ids):
        entry = stencils[sid]
        w = float(entry["w"])
        h = float(entry["h"])
        frag = str(entry["svg"])
        if color is not None:
            frag = frag.replace("currentColor", color)
        scale = GRID_ICON / max(w, h)
        x = (i % cols) * GRID_CELL + (GRID_CELL - w * scale) / 2
        y = (
            (i // cols) * GRID_CELL
            + (GRID_CELL - GRID_ICON) / 2
            + (GRID_ICON - h * scale) / 2
        )
        label = escape(sid.split("/", 1)[-1])
        lx = (i % cols) * GRID_CELL + GRID_CELL / 2
        ly = (i // cols) * GRID_CELL + GRID_CELL - 12
        cells.append(
            f'<g transform="translate({x:g} {y:g}) scale({scale:g})">{frag}</g>'
            f'<text x="{lx:g}" y="{ly:g}" text-anchor="middle" '
            f'font-family="sans-serif" font-size="{GRID_LABEL_PT:g}">{label}</text>'
        )
    body = "".join(cells)
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {total_w:g} {total_h:g}" '
        f'width="{total_w:g}" height="{total_h:g}">{body}</svg>'
    )


# ── Command handlers ───────────────────────────────────────────────────────
def cmd_packs(args: argparse.Namespace) -> None:
    stencils = load_stencils(Path(args.zip))
    for pack, count in pack_counts(stencils):
        print(f"{pack:<28s} {count:>5d}")


def cmd_list(args: argparse.Namespace) -> None:
    stencils = load_stencils(Path(args.zip))
    for sid in filter_ids(stencils, pack=args.pack, limit=args.limit):
        print(sid)


def cmd_search(args: argparse.Namespace) -> None:
    stencils = load_stencils(Path(args.zip))
    hits = filter_ids(stencils, pack=args.pack, term=args.term, limit=args.limit)
    for sid in hits:
        print(sid)
    if not hits:
        print(f"no stencils match {args.term!r}", file=sys.stderr)
        raise SystemExit(1)


def _lookup(stencils: dict[str, dict[str, Any]], stencil_id: str) -> dict[str, Any]:
    entry = stencils.get(stencil_id)
    if entry is None:
        print(f"error: unknown stencil id {stencil_id!r}", file=sys.stderr)
        suggestions = close_matches(stencils, stencil_id)
        if suggestions:
            print("did you mean:", file=sys.stderr)
            for sid in suggestions:
                print(f"  {sid}", file=sys.stderr)
        raise SystemExit(1)
    return entry


def cmd_extract(args: argparse.Namespace) -> None:
    stencils = load_stencils(Path(args.zip))
    entry = _lookup(stencils, args.id)
    svg = build_svg(entry, color=args.color, size=args.size)
    if args.out:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(svg, encoding="utf-8")
        print(f"wrote {out}")
    else:
        print(svg)


def cmd_grid(args: argparse.Namespace) -> None:
    stencils = load_stencils(Path(args.zip))
    ids = filter_ids(stencils, term=args.term, limit=args.limit)
    if not ids:
        print(f"error: no stencils match {args.term!r}", file=sys.stderr)
        raise SystemExit(1)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(build_grid_svg(stencils, ids, color=args.color), encoding="utf-8")
    print(f"wrote {out} ({len(ids)} stencils)")


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    def _help(p: argparse.ArgumentParser) -> Any:
        """Return a handler that prints help for parser p (used as the default func)."""

        def _print_help(_: argparse.Namespace) -> None:
            p.print_help()

        return _print_help

    parser = argparse.ArgumentParser(
        prog="stencil.py", description="Browse/extract vendored draw.io stencil SVGs."
    )
    parser.add_argument(
        "--zip",
        default=str(DEFAULT_ZIP),
        help="Path to stencils.json.zip (default: bundled asset)",
    )
    parser.set_defaults(func=_help(parser))
    sub = parser.add_subparsers(dest="command", required=False)

    packs_p = sub.add_parser("packs", help="List pack prefixes with entry counts")
    packs_p.set_defaults(func=cmd_packs)

    list_p = sub.add_parser("list", help="List stencil ids (sorted)")
    list_p.add_argument("--pack", help="Filter to one pack prefix (e.g. mxgraph.aws4)")
    list_p.add_argument("--limit", type=int, help="Limit to first N ids")
    list_p.set_defaults(func=cmd_list)

    search_p = sub.add_parser(
        "search", help="Case-insensitive substring search on stencil ids"
    )
    search_p.add_argument("term", help="Substring to match")
    search_p.add_argument("--pack", help="Filter to one pack prefix")
    search_p.add_argument("--limit", type=int, help="Limit to first N hits")
    search_p.set_defaults(func=cmd_search)

    extract_p = sub.add_parser(
        "extract", help="Emit a standalone SVG for one stencil id"
    )
    extract_p.add_argument("id", help='Stencil id, e.g. "mxgraph.aws4/lambda"')
    extract_p.add_argument(
        "--color", help="Replace currentColor with this value (e.g. '#ED7100')"
    )
    extract_p.add_argument(
        "--size", type=float, help="Output width in px (height scales proportionally)"
    )
    extract_p.add_argument("--out", help="Write to this file instead of stdout")
    extract_p.set_defaults(func=cmd_extract)

    grid_p = sub.add_parser(
        "grid", help="Composite matching stencils into one contact-sheet SVG"
    )
    grid_p.add_argument("term", help="Substring (or pack prefix) to match")
    grid_p.add_argument("--out", required=True, help="Output SVG file")
    grid_p.add_argument("--color", help="Replace currentColor with this value")
    grid_p.add_argument(
        "--limit", type=int, default=24, help="Max stencils in the sheet (default: 24)"
    )
    grid_p.set_defaults(func=cmd_grid)

    return parser


def main() -> None:
    args = build_parser().parse_args()
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
