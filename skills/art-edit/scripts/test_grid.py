#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0",
#   "pytest-cov>=4.0",
#   "Pillow>=10.1.0",
#   "numpy>=1.26.0",
# ]
# ///
"""Tests for grid — the labelled coordinate grid + cell resolver."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import grid
import pytest
from PIL import Image


# ── column labels ────────────────────────────────────────────────────────────
@pytest.mark.parametrize("idx,label", [(0, "A"), (1, "B"), (25, "Z"), (26, "AA"), (27, "AB"), (51, "AZ"), (52, "BA")])
def test_column_label_roundtrips(idx: int, label: str) -> None:
    assert grid.column_label(idx) == label
    assert grid.column_index(label) == idx


def test_column_label_rejects_negative() -> None:
    with pytest.raises(ValueError, match="non-negative"):
        grid.column_label(-1)


@pytest.mark.parametrize("bad", ["", "4", "A4"])
def test_column_index_rejects_non_alpha(bad: str) -> None:
    with pytest.raises(ValueError, match="bad column"):
        grid.column_index(bad)


# ── cell parsing ─────────────────────────────────────────────────────────────
@pytest.mark.parametrize("ref,expected", [("A1", (0, 0)), ("C4", (2, 3)), ("z9", (25, 8)), ("AA10", (26, 9))])
def test_parse_cell(ref: str, expected: tuple[int, int]) -> None:
    assert grid.parse_cell(ref) == expected


@pytest.mark.parametrize("bad", ["", "44", "AB", ":", "C"])
def test_parse_cell_rejects_malformed(bad: str) -> None:
    with pytest.raises(ValueError, match="bad cell"):
        grid.parse_cell(bad)


# ── range → box ──────────────────────────────────────────────────────────────
def test_cells_to_box_range() -> None:
    # C4:F5 → cols C..F (2..5), rows 4..5 (3..4), at 200px.
    assert grid.cells_to_box("C4:F5", 200) == (2 * 200, 3 * 200, 6 * 200, 5 * 200)


def test_cells_to_box_single_cell_is_one_by_one() -> None:
    assert grid.cells_to_box("A1", 100) == (0, 0, 100, 100)


def test_cells_to_box_normalises_reversed_range() -> None:
    # A range given bottom-right first still yields the same box.
    assert grid.cells_to_box("F5:C4", 200) == grid.cells_to_box("C4:F5", 200)


def test_box_to_quad_orders_corners_tl_tr_br_bl() -> None:
    assert grid.box_to_quad((10, 20, 30, 40)) == [[10, 20], [30, 20], [30, 40], [10, 40]]


# ── overlay ──────────────────────────────────────────────────────────────────
def test_overlay_grid_preserves_size_and_draws() -> None:
    base = Image.new("RGB", (400, 300), (10, 10, 10))
    out = grid.overlay_grid(base, cell=100)
    assert out.size == (400, 300)
    # Some green grid pixels must now exist where the flat base had none.
    assert any(px[1] > 200 and px[0] < 100 for px in out.getdata())


# ── highlight parsing ────────────────────────────────────────────────────────
def test_parse_highlight_spec_basic_and_colour() -> None:
    specs = grid.parse_highlight_spec("C5:F6=AURIZON, H2:H3=Roy#22d3ee")
    assert specs[0] == ("C5:F6", "AURIZON", None)
    assert specs[1] == ("H2:H3", "Roy", (0x22, 0xD3, 0xEE))


def test_parse_highlight_spec_skips_blanks() -> None:
    assert grid.parse_highlight_spec("A1=x,, ,B2=y") == [("A1", "x", None), ("B2", "y", None)]


def test_parse_highlight_spec_rejects_bad_colour() -> None:
    with pytest.raises(ValueError, match="bad colour"):
        grid.parse_highlight_spec("A1=x#ZZZ")


def test_parse_highlight_spec_rejects_bad_range() -> None:
    with pytest.raises(ValueError, match="bad cell"):
        grid.parse_highlight_spec("nonsense=x")


def test_overlay_grid_with_highlight_fills_region() -> None:
    base = Image.new("RGB", (600, 400), (10, 10, 10))
    out = grid.overlay_grid(base, cell=200, highlights=[("B2:B2", "X", (240, 150, 40))])
    # Centre of cell B2 (col1,row1 → x200-400,y200-400) should now carry the amber tint.
    px = out.getpixel((300, 300))
    assert px[0] > 40 and px[0] > px[2]  # reddish/amber, not the flat dark base


# ── CLI ──────────────────────────────────────────────────────────────────────
def test_main_overlay_writes_file(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    src = tmp_path / "in.png"
    Image.new("RGB", (200, 200), (0, 0, 0)).save(src)
    ns = argparse.Namespace(
        command="overlay",
        image=src,
        out=tmp_path / "out.png",
        cell=100,
        highlight="A1=x",
        verbose=False,
        quiet=False,
    )
    assert grid.main(ns) == 0
    assert (tmp_path / "out.png").exists()
    assert "saved" in capsys.readouterr().out


def test_main_resolve_prints_box_and_quad(capsys: pytest.CaptureFixture[str]) -> None:
    ns = argparse.Namespace(command="resolve", cells="C4:F5", cell=200, verbose=False, quiet=False)
    assert grid.main(ns) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["box"] == [400, 600, 1200, 1000]
    assert payload["quad"][0] == [400, 600] and payload["quad"][2] == [1200, 1000]


def test_build_parser_resolve() -> None:
    ns = grid.build_parser().parse_args(["resolve", "C4:F5"])
    assert ns.command == "resolve" and ns.cells == "C4:F5" and ns.cell == grid.DEFAULT_CELL


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
