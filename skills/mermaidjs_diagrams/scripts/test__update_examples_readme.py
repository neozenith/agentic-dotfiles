#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for _update_examples_readme.py"""

from __future__ import annotations

import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import pytest

import _update_examples_readme as mod


@pytest.fixture
def temp_dir() -> Path:
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def examples_dir(temp_dir: Path) -> Path:
    """Temp dir pre-populated with two .mmd files (alphabetical order: a, b)."""
    (temp_dir / "alpha.mmd").write_text("flowchart LR\n  A --> B\n", encoding="utf-8")
    (temp_dir / "beta.mmd").write_text("flowchart LR\n  C --> D\n", encoding="utf-8")
    return temp_dir


def _args(**kwargs: object) -> Namespace:
    defaults: dict[str, object] = {"dry_run": False, "verbose": False, "quiet": False}
    defaults.update(kwargs)
    return Namespace(**defaults)


class TestBuildSection:
    def test_heading(self) -> None:
        result = mod.build_section("my_diagram", "flowchart LR\n  A --> B\n")
        assert result.startswith("## my_diagram\n")

    def test_code_subsection(self) -> None:
        result = mod.build_section("x", "flowchart LR\n  A --> B\n")
        assert "### Code\n" in result

    def test_mermaid_subsection(self) -> None:
        result = mod.build_section("x", "flowchart LR\n  A --> B\n")
        assert "### Mermaid\n" in result

    def test_image_subsection(self) -> None:
        result = mod.build_section("x", "flowchart LR\n  A --> B\n")
        assert "### Image (PNG)\n" in result

    def test_text_fence_contains_content(self) -> None:
        content = "flowchart LR\n  A --> B\n"
        result = mod.build_section("x", content)
        assert f"```text\n{content}```" in result

    def test_mermaid_fence_contains_content(self) -> None:
        content = "flowchart LR\n  A --> B\n"
        result = mod.build_section("x", content)
        assert f"```mermaid\n{content}```" in result

    def test_image_link_uses_stem(self) -> None:
        result = mod.build_section("my_diagram", "flowchart LR\n")
        assert "![my_diagram](my_diagram.png)" in result


class TestBuildReadme:
    def test_starts_with_header(self, examples_dir: Path) -> None:
        result = mod.build_readme(examples_dir)
        assert result.startswith("# Examples\n")

    def test_contains_toc_markers(self, examples_dir: Path) -> None:
        result = mod.build_readme(examples_dir)
        assert "<!--TOC-->\n<!--TOC-->" in result

    def test_contains_all_stems(self, examples_dir: Path) -> None:
        result = mod.build_readme(examples_dir)
        assert "## alpha\n" in result
        assert "## beta\n" in result

    def test_sections_separated_by_hr(self, examples_dir: Path) -> None:
        result = mod.build_readme(examples_dir)
        # Between examples: blank line, ---, blank line
        assert "\n---\n\n## beta" in result

    def test_footer_appended(self, examples_dir: Path) -> None:
        result = mod.build_readme(examples_dir)
        assert "## Mermaid Version Information Debugging" in result

    def test_footer_preceded_by_hr_no_blank(self, examples_dir: Path) -> None:
        result = mod.build_readme(examples_dir)
        # Last --- before footer has no trailing blank line
        assert "\n---\n## Mermaid Version Information Debugging" in result

    def test_alphabetical_ordering(self, temp_dir: Path) -> None:
        (temp_dir / "z_last.mmd").write_text("flowchart LR\n  Z\n", encoding="utf-8")
        (temp_dir / "a_first.mmd").write_text("flowchart LR\n  A\n", encoding="utf-8")
        result = mod.build_readme(temp_dir)
        assert result.index("## a_first") < result.index("## z_last")

    def test_raises_on_empty_dir(self, temp_dir: Path) -> None:
        with pytest.raises(RuntimeError, match="No .mmd files found"):
            mod.build_readme(temp_dir)

    def test_idempotent(self, examples_dir: Path) -> None:
        assert mod.build_readme(examples_dir) == mod.build_readme(examples_dir)


class TestMain:
    def test_writes_readme(self, examples_dir: Path, temp_dir: Path) -> None:
        readme = temp_dir / "README.md"
        result = mod.main(_args(), readme=readme, examples_dir=examples_dir)
        assert result == 0
        assert readme.exists()

    def test_readme_content_correct(self, examples_dir: Path, temp_dir: Path) -> None:
        readme = temp_dir / "README.md"
        mod.main(_args(), readme=readme, examples_dir=examples_dir)
        content = readme.read_text(encoding="utf-8")
        assert "# Examples" in content
        assert "## alpha" in content

    def test_dry_run_does_not_write(self, examples_dir: Path, temp_dir: Path) -> None:
        readme = temp_dir / "README.md"
        result = mod.main(_args(dry_run=True), readme=readme, examples_dir=examples_dir)
        assert result == 0
        assert not readme.exists()

    def test_returns_zero_on_success(self, examples_dir: Path, temp_dir: Path) -> None:
        readme = temp_dir / "README.md"
        assert mod.main(_args(), readme=readme, examples_dir=examples_dir) == 0

    def test_idempotent(self, examples_dir: Path, temp_dir: Path) -> None:
        readme = temp_dir / "README.md"
        mod.main(_args(), readme=readme, examples_dir=examples_dir)
        first = readme.read_text(encoding="utf-8")
        mod.main(_args(), readme=readme, examples_dir=examples_dir)
        second = readme.read_text(encoding="utf-8")
        assert first == second


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
