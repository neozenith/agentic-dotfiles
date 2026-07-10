#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for stencil.py — real bundled stencil zip, real CLI dispatch."""

from __future__ import annotations

import json
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import pytest
import stencil


# ── Real-data smoke checks against the bundled zip ─────────────────────────
def test_loader_finds_over_1000_entries() -> None:
    stencils = stencil.load_stencils()
    assert len(stencils) > 1000


def test_loader_is_cached() -> None:
    assert stencil.load_stencils() is stencil.load_stencils()


def test_lambda_exists_and_extract_is_valid_xml() -> None:
    stencils = stencil.load_stencils()
    assert "mxgraph.aws4/lambda" in stencils
    svg = stencil.build_svg(stencils["mxgraph.aws4/lambda"], color="#ED7100", size=64)
    root = ET.fromstring(svg)
    assert root.tag == "{http://www.w3.org/2000/svg}svg"
    assert root.attrib["width"] == "64"
    assert "#ED7100" in svg
    assert "currentColor" not in svg


def test_extract_without_color_keeps_current_color() -> None:
    stencils = stencil.load_stencils()
    entry = stencils["mxgraph.aws4/lambda"]
    svg = stencil.build_svg(entry)
    assert 'viewBox="0 0 54.05 56"' in svg
    assert svg.count("currentColor") == entry["svg"].count("currentColor")


def test_search_s3_returns_hits() -> None:
    stencils = stencil.load_stencils()
    hits = stencil.filter_ids(stencils, term="s3")
    assert hits
    assert all("s3" in sid.lower() for sid in hits)


# ── Pure-function behavior on a small synthetic zip ────────────────────────
@pytest.fixture
def tiny_zip(tmp_path: Path) -> Path:
    data = {
        "packa/alpha": {
            "w": 10.0,
            "h": 20.0,
            "svg": '<rect fill="currentColor"/>',
            "stencil_b64": "x",
        },
        "packa/beta": {"w": 10.0, "h": 10.0, "svg": "<circle/>", "stencil_b64": "x"},
        "packb/gamma": {"w": 4.0, "h": 2.0, "svg": "<path/>", "stencil_b64": "x"},
    }
    path = tmp_path / "stencils.json.zip"
    with zipfile.ZipFile(path, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("stencils.json", json.dumps(data))
    return path


def test_pack_counts(tiny_zip: Path) -> None:
    stencils = stencil.load_stencils(tiny_zip)
    assert stencil.pack_counts(stencils) == [("packa", 2), ("packb", 1)]


def test_filter_ids_pack_term_limit(tiny_zip: Path) -> None:
    stencils = stencil.load_stencils(tiny_zip)
    assert stencil.filter_ids(stencils, pack="packa") == ["packa/alpha", "packa/beta"]
    assert stencil.filter_ids(stencils, term="GAM") == ["packb/gamma"]
    assert stencil.filter_ids(stencils, limit=1) == ["packa/alpha"]


def test_close_matches_substring_then_fuzzy(tiny_zip: Path) -> None:
    stencils = stencil.load_stencils(tiny_zip)
    assert stencil.close_matches(stencils, "alpha") == ["packa/alpha"]
    assert "packb/gamma" in stencil.close_matches(stencils, "packb/gama")


def test_build_svg_proportional_height(tiny_zip: Path) -> None:
    stencils = stencil.load_stencils(tiny_zip)
    svg = stencil.build_svg(stencils["packa/alpha"], size=50)
    assert 'width="50"' in svg
    assert 'height="100"' in svg


def test_build_grid_svg(tiny_zip: Path) -> None:
    stencils = stencil.load_stencils(tiny_zip)
    ids = stencil.filter_ids(stencils)
    svg = stencil.build_grid_svg(stencils, ids, color="#123456")
    root = ET.fromstring(svg)
    assert root.tag.endswith("svg")
    assert svg.count("<text") == 3
    assert "#123456" in svg


# ── CLI dispatch ────────────────────────────────────────────────────────────
def _run(argv: list[str]) -> None:
    parser = stencil.build_parser()
    args = parser.parse_args(argv)
    args.func(args)


def test_cli_no_subcommand_prints_help(capsys: pytest.CaptureFixture[str]) -> None:
    _run([])
    assert "usage: stencil.py" in capsys.readouterr().out


def test_cli_packs(capsys: pytest.CaptureFixture[str]) -> None:
    _run(["packs"])
    out = capsys.readouterr().out
    assert "mxgraph.aws4" in out


def test_cli_list_with_pack_and_limit(capsys: pytest.CaptureFixture[str]) -> None:
    _run(["list", "--pack", "mxgraph.aws4", "--limit", "3"])
    lines = capsys.readouterr().out.strip().splitlines()
    assert len(lines) == 3
    assert all(line.startswith("mxgraph.aws4/") for line in lines)


def test_cli_search_hit_and_miss(capsys: pytest.CaptureFixture[str]) -> None:
    _run(["search", "lambda", "--limit", "5"])
    assert "mxgraph.aws4/lambda" in capsys.readouterr().out
    with pytest.raises(SystemExit) as excinfo:
        _run(["search", "zzz-no-such-stencil-zzz"])
    assert excinfo.value.code == 1
    assert "no stencils match" in capsys.readouterr().err


def test_cli_extract_stdout_and_file(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    _run(["extract", "mxgraph.aws4/lambda", "--color", "#ED7100"])
    assert "<svg" in capsys.readouterr().out
    out_file = tmp_path / "sub" / "lambda.svg"
    _run(["extract", "mxgraph.aws4/lambda", "--out", str(out_file)])
    assert out_file.is_file()
    ET.parse(out_file)


def test_cli_extract_unknown_id_suggests(capsys: pytest.CaptureFixture[str]) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run(["extract", "mxgraph.aws4/lambada"])
    assert excinfo.value.code == 1
    err = capsys.readouterr().err
    assert "unknown stencil id" in err
    assert "did you mean" in err
    assert "lambda" in err


def test_cli_grid(tmp_path: Path, capsys: pytest.CaptureFixture[str]) -> None:
    out_file = tmp_path / "grid.svg"
    _run(["grid", "s3", "--out", str(out_file), "--limit", "6", "--color", "#7AA116"])
    assert out_file.is_file()
    ET.parse(out_file)
    assert "6 stencils" in capsys.readouterr().out


def test_cli_grid_no_match_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        _run(["grid", "zzz-nope-zzz", "--out", str(tmp_path / "g.svg")])
    assert excinfo.value.code == 1
    assert "no stencils match" in capsys.readouterr().err


def test_main_dispatches(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    monkeypatch.setattr(sys, "argv", ["stencil.py", "packs"])
    stencil.main()
    assert "mxgraph.aws4" in capsys.readouterr().out


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
