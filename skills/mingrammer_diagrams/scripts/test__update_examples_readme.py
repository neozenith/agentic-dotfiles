#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for _update_examples_readme.py (the examples-gallery generator)."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import _update_examples_readme as mod
import pytest


def _write_pair(examples_dir: Path, stem: str, source: str, *, png: bool = True) -> None:
    """Create a {stem}.py (+ optional {stem}.png) in examples_dir."""
    (examples_dir / f"{stem}.py").write_text(source, encoding="utf-8")
    if png:
        (examples_dir / f"{stem}.png").write_bytes(b"\x89PNG\r\n")


def test_build_section_shapes_python_fence_and_image() -> None:
    out = mod.build_section("aws_web_service", "print('hi')\n")
    assert out.startswith("## aws_web_service\n")
    assert "```python\nprint('hi')\n```" in out
    assert "![aws_web_service](aws_web_service.png)" in out


def test_build_section_appends_trailing_newline_when_missing() -> None:
    # Source without a trailing newline must still close the fence on its own line.
    out = mod.build_section("x", "no_newline")
    assert "```python\nno_newline\n```" in out


def test_build_readme_orders_sections_alphabetically(tmp_path: Path) -> None:
    _write_pair(tmp_path, "bravo", "b = 1\n")
    _write_pair(tmp_path, "alpha", "a = 1\n")
    readme = mod.build_readme(tmp_path)
    assert readme.index("## alpha") < readme.index("## bravo")
    assert "# Examples" in readme
    assert "## Re-rendering" in readme
    assert "<!--TOC-->" in readme


def test_build_readme_raises_when_no_examples(tmp_path: Path) -> None:
    with pytest.raises(RuntimeError, match="No .py example files"):
        mod.build_readme(tmp_path)


def test_build_readme_raises_when_png_missing(tmp_path: Path) -> None:
    _write_pair(tmp_path, "alpha", "a = 1\n", png=False)
    with pytest.raises(RuntimeError, match="Missing rendered PNG"):
        mod.build_readme(tmp_path)


def test_main_writes_readme(tmp_path: Path) -> None:
    _write_pair(tmp_path, "alpha", "a = 1\n")
    readme = tmp_path / "README.md"
    rc = mod.main(Namespace(dry_run=False), readme=readme, examples_dir=tmp_path)
    assert rc == 0
    assert "## alpha" in readme.read_text(encoding="utf-8")


def test_main_dry_run_writes_nothing(tmp_path: Path) -> None:
    _write_pair(tmp_path, "alpha", "a = 1\n")
    readme = tmp_path / "README.md"
    rc = mod.main(Namespace(dry_run=True), readme=readme, examples_dir=tmp_path)
    assert rc == 0
    assert not readme.exists()


def test_module_constants_point_at_examples_dir() -> None:
    assert mod.EXAMPLES_DIR.name == "examples"
    assert mod.README.name == "README.md"


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
