#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for mermaid_markdown_verifier."""

from __future__ import annotations

import json
import shutil
import sys
import tempfile
from argparse import Namespace
from pathlib import Path

import pytest

from mermaid_markdown_verifier import (
    SnippetResult,
    build_report,
    collect_markdown_files,
    extract_mermaid_snippets,
    main,
    make_slug,
    verify_snippet,
)

# ============================================================================
# Fixtures
# ============================================================================

VALID_MERMAID = "graph TD\n    A[Start] --> B[Process]\n    B --> C[End]"
VALID_MERMAID_LR = "graph LR\n    X --> Y --> Z"
INVALID_MERMAID = "THIS IS NOT VALID MERMAID SYNTAX @@@@"


@pytest.fixture
def temp_dir() -> Path:
    """Isolated temporary directory for each test."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_md(temp_dir: Path) -> Path:
    """Markdown file with two valid mermaid snippets."""
    content = f"# Test Document\n\nSome text.\n\n```mermaid\n{VALID_MERMAID}\n```\n\nMiddle text.\n\n```mermaid\n{VALID_MERMAID_LR}\n```\n\nFinal text.\n"
    md_file = temp_dir / "test_doc.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def invalid_md(temp_dir: Path) -> Path:
    """Markdown file with one invalid mermaid snippet."""
    content = f"# Bad Diagrams\n\n```mermaid\n{INVALID_MERMAID}\n```\n"
    md_file = temp_dir / "invalid_doc.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


@pytest.fixture
def no_mermaid_md(temp_dir: Path) -> Path:
    """Markdown file with no mermaid snippets."""
    content = "# Plain Document\n\nJust text with a Python block:\n\n```python\nprint('hello')\n```\n"
    md_file = temp_dir / "no_mermaid.md"
    md_file.write_text(content, encoding="utf-8")
    return md_file


def _make_result(success: bool, file_path: str = "test.md") -> SnippetResult:
    """Helper to build a SnippetResult for report tests."""
    return SnippetResult(
        slug="test_slug",
        file_path=file_path,
        line_start=1,
        line_end=10,
        content=VALID_MERMAID,
        success=success,
        exit_code=0 if success else 1,
        stdout="",
        stderr="" if success else "Error: syntax",
        png_path="/tmp/test.png" if success else None,
    )


# ============================================================================
# Tests: make_slug
# ============================================================================


class TestMakeSlug:
    def test_generates_deterministic_slug(self, temp_dir: Path) -> None:
        file_path = temp_dir / "test.md"
        assert make_slug(file_path, 10, 20) == make_slug(file_path, 10, 20)

    def test_different_line_ranges_give_different_slugs(self, temp_dir: Path) -> None:
        file_path = temp_dir / "test.md"
        assert make_slug(file_path, 10, 20) != make_slug(file_path, 30, 40)

    def test_different_files_give_different_slugs(self, temp_dir: Path) -> None:
        assert make_slug(temp_dir / "a.md", 10, 20) != make_slug(temp_dir / "b.md", 10, 20)

    def test_slug_contains_line_numbers(self, temp_dir: Path) -> None:
        slug = make_slug(temp_dir / "test.md", 45, 68)
        assert "L45" in slug
        assert "L68" in slug

    def test_slug_contains_filename_stem(self, temp_dir: Path) -> None:
        slug = make_slug(temp_dir / "my_document.md", 1, 10)
        assert "my_document" in slug

    def test_slug_is_filesystem_safe(self, temp_dir: Path) -> None:
        slug = make_slug(temp_dir / "test-doc.md", 1, 10)
        # Characters that are problematic on common filesystems
        for char in "/\\:*?\"<>|":
            assert char not in slug, f"slug contains unsafe char '{char}': {slug}"

    def test_same_filename_different_dirs_gives_different_slug(self, temp_dir: Path) -> None:
        dir_a = temp_dir / "subdir_a"
        dir_b = temp_dir / "subdir_b"
        dir_a.mkdir()
        dir_b.mkdir()
        slug_a = make_slug(dir_a / "doc.md", 1, 5)
        slug_b = make_slug(dir_b / "doc.md", 1, 5)
        # Hash component must differ even though filename is the same
        assert slug_a != slug_b


# ============================================================================
# Tests: extract_mermaid_snippets
# ============================================================================


class TestExtractMermaidSnippets:
    def test_extracts_single_snippet(self, temp_dir: Path) -> None:
        md = temp_dir / "test.md"
        md.write_text("# Doc\n\n```mermaid\ngraph TD\n    A --> B\n```\n", encoding="utf-8")
        assert len(extract_mermaid_snippets(md)) == 1

    def test_extracts_multiple_snippets(self, sample_md: Path) -> None:
        assert len(extract_mermaid_snippets(sample_md)) == 2

    def test_returns_correct_line_numbers(self, temp_dir: Path) -> None:
        md = temp_dir / "test.md"
        md.write_text("line1\nline2\n```mermaid\ngraph TD\n    A --> B\n```\n", encoding="utf-8")
        snippets = extract_mermaid_snippets(md)
        assert len(snippets) == 1
        line_start, line_end, _ = snippets[0]
        assert line_start == 3  # Opening ``` is on line 3
        assert line_end == 6  # Closing ``` is on line 6

    def test_extracts_correct_content(self, temp_dir: Path) -> None:
        expected = "graph TD\n    A --> B"
        md = temp_dir / "test.md"
        md.write_text(f"```mermaid\n{expected}\n```\n", encoding="utf-8")
        _, _, content = extract_mermaid_snippets(md)[0]
        assert content == expected

    def test_no_snippets_in_plain_markdown(self, no_mermaid_md: Path) -> None:
        assert extract_mermaid_snippets(no_mermaid_md) == []

    def test_ignores_non_mermaid_fences(self, temp_dir: Path) -> None:
        md = temp_dir / "test.md"
        md.write_text(
            "```python\nprint('hello')\n```\n\n```mermaid\ngraph TD\n    A --> B\n```\n",
            encoding="utf-8",
        )
        snippets = extract_mermaid_snippets(md)
        assert len(snippets) == 1  # Only the mermaid fence

    def test_handles_four_backtick_fence(self, temp_dir: Path) -> None:
        md = temp_dir / "test.md"
        md.write_text("````mermaid\ngraph TD\n    A --> B\n````\n", encoding="utf-8")
        assert len(extract_mermaid_snippets(md)) == 1

    def test_unclosed_fence_is_ignored(self, temp_dir: Path) -> None:
        md = temp_dir / "test.md"
        md.write_text("```mermaid\ngraph TD\n    A --> B\n", encoding="utf-8")
        # No closing fence → should not produce a snippet
        assert extract_mermaid_snippets(md) == []

    def test_empty_file_returns_no_snippets(self, temp_dir: Path) -> None:
        md = temp_dir / "empty.md"
        md.write_text("", encoding="utf-8")
        assert extract_mermaid_snippets(md) == []


# ============================================================================
# Tests: collect_markdown_files
# ============================================================================


class TestCollectMarkdownFiles:
    def test_collects_single_file(self, sample_md: Path) -> None:
        files = collect_markdown_files([str(sample_md)])
        assert sample_md.resolve() in [f.resolve() for f in files]

    def test_collects_from_directory(self, temp_dir: Path, sample_md: Path) -> None:
        files = collect_markdown_files([str(temp_dir)])
        assert sample_md.resolve() in [f.resolve() for f in files]

    def test_deduplicates_files_specified_twice(self, sample_md: Path) -> None:
        files = collect_markdown_files([str(sample_md), str(sample_md)])
        assert [f.resolve() for f in files].count(sample_md.resolve()) == 1

    def test_returns_empty_for_nonexistent_path(self, temp_dir: Path) -> None:
        files = collect_markdown_files([str(temp_dir / "does_not_exist.md")])
        assert files == []

    def test_recursive_directory_scan(self, temp_dir: Path) -> None:
        subdir = temp_dir / "sub"
        subdir.mkdir()
        (subdir / "nested.md").write_text("# Nested\n", encoding="utf-8")
        (temp_dir / "root.md").write_text("# Root\n", encoding="utf-8")

        files = collect_markdown_files([str(temp_dir)])
        names = {f.name for f in files}
        assert "nested.md" in names
        assert "root.md" in names

    def test_ignores_non_markdown_files(self, temp_dir: Path) -> None:
        (temp_dir / "script.py").write_text("print('hi')", encoding="utf-8")
        (temp_dir / "doc.md").write_text("# Doc\n", encoding="utf-8")

        files = collect_markdown_files([str(temp_dir)])
        assert all(f.suffix == ".md" for f in files)

    def test_empty_paths_returns_empty(self) -> None:
        assert collect_markdown_files([]) == []


# ============================================================================
# Tests: build_report
# ============================================================================


class TestBuildReport:
    def test_empty_results(self) -> None:
        report = build_report([])
        assert report["summary"] == {
            "total_snippets": 0,
            "passed": 0,
            "failed": 0,
            "files_scanned": 0,
        }

    def test_all_passed(self) -> None:
        report = build_report([_make_result(True), _make_result(True)])
        assert report["summary"]["passed"] == 2
        assert report["summary"]["failed"] == 0

    def test_all_failed(self) -> None:
        report = build_report([_make_result(False), _make_result(False)])
        assert report["summary"]["passed"] == 0
        assert report["summary"]["failed"] == 2

    def test_mixed_results(self) -> None:
        report = build_report([_make_result(True, "a.md"), _make_result(False, "b.md")])
        assert report["summary"]["passed"] == 1
        assert report["summary"]["failed"] == 1

    def test_counts_unique_source_files(self) -> None:
        results = [
            _make_result(True, "a.md"),
            _make_result(True, "a.md"),  # same file, second snippet
            _make_result(True, "b.md"),
        ]
        report = build_report(results)
        assert report["summary"]["files_scanned"] == 2

    def test_results_list_is_json_serializable(self) -> None:
        report = build_report([_make_result(True), _make_result(False)])
        parsed = json.loads(json.dumps(report))
        assert len(parsed["results"]) == 2

    def test_results_preserve_all_fields(self) -> None:
        result = _make_result(True, "doc.md")
        report = build_report([result])
        r = report["results"][0]
        assert r["slug"] == result.slug
        assert r["file_path"] == result.file_path
        assert r["line_start"] == result.line_start
        assert r["line_end"] == result.line_end
        assert r["success"] == result.success
        assert r["exit_code"] == result.exit_code


# ============================================================================
# Tests: verify_snippet — error paths (no npx required)
# ============================================================================


class TestVerifySnippetErrors:
    """Error-path tests that do not require npx/mmdc."""

    def test_missing_command_returns_failure_result(self, temp_dir: Path) -> None:
        result = verify_snippet(
            slug="test_missing_L1_L3",
            file_path=temp_dir / "test.md",
            line_start=1,
            line_end=3,
            content=VALID_MERMAID,
            tmp_dir=temp_dir,
            _cmd=["command_that_does_not_exist_xyz_123_abc"],
        )
        assert result.success is False
        assert result.exit_code == -2
        assert "not found" in result.stderr.lower()

    def test_command_failure_returns_non_zero_exit(self, temp_dir: Path) -> None:
        # `false` always exits with code 1
        false_cmd = shutil.which("false") or "/usr/bin/false"
        result = verify_snippet(
            slug="test_false_L1_L3",
            file_path=temp_dir / "test.md",
            line_start=1,
            line_end=3,
            content=VALID_MERMAID,
            tmp_dir=temp_dir,
            _cmd=[false_cmd],
        )
        assert result.success is False
        assert result.exit_code != 0

    def test_result_carries_correct_metadata(self, temp_dir: Path) -> None:
        file_path = temp_dir / "source.md"
        false_cmd = shutil.which("false") or "/usr/bin/false"
        result = verify_snippet(
            slug="meta_slug_L5_L12",
            file_path=file_path,
            line_start=5,
            line_end=12,
            content="graph TD\n    A --> B",
            tmp_dir=temp_dir,
            _cmd=[false_cmd],
        )
        assert result.slug == "meta_slug_L5_L12"
        assert result.file_path == str(file_path)
        assert result.line_start == 5
        assert result.line_end == 12
        assert result.content == "graph TD\n    A --> B"
        assert result.png_path is None

    def test_writes_mmd_file_to_tmp_dir(self, temp_dir: Path) -> None:
        false_cmd = shutil.which("false") or "/usr/bin/false"
        verify_snippet(
            slug="write_check_L1_L3",
            file_path=temp_dir / "test.md",
            line_start=1,
            line_end=3,
            content=VALID_MERMAID,
            tmp_dir=temp_dir,
            _cmd=[false_cmd],
        )
        mmd_file = temp_dir / "write_check_L1_L3.mmd"
        assert mmd_file.exists()
        assert mmd_file.read_text(encoding="utf-8") == VALID_MERMAID


# ============================================================================
# Tests: verify_snippet — real mmdc (requires npx)
# ============================================================================

_npx_available = shutil.which("npx") is not None


@pytest.mark.skipif(not _npx_available, reason="npx not available in this environment")
class TestVerifySnippetWithNpx:
    def test_valid_diagram_succeeds(self, temp_dir: Path) -> None:
        result = verify_snippet(
            slug="valid_L1_L4",
            file_path=temp_dir / "test.md",
            line_start=1,
            line_end=4,
            content=VALID_MERMAID,
            tmp_dir=temp_dir,
        )
        assert result.success is True
        assert result.exit_code == 0

    def test_valid_diagram_creates_png(self, temp_dir: Path) -> None:
        result = verify_snippet(
            slug="png_check_L1_L4",
            file_path=temp_dir / "test.md",
            line_start=1,
            line_end=4,
            content=VALID_MERMAID,
            tmp_dir=temp_dir,
        )
        if result.success:
            assert result.png_path is not None
            assert Path(result.png_path).exists()

    def test_invalid_diagram_fails(self, temp_dir: Path) -> None:
        result = verify_snippet(
            slug="invalid_L1_L3",
            file_path=temp_dir / "test.md",
            line_start=1,
            line_end=3,
            content=INVALID_MERMAID,
            tmp_dir=temp_dir,
        )
        assert result.success is False
        assert result.exit_code != 0
        assert result.png_path is None

    def test_invalid_diagram_captures_stderr(self, temp_dir: Path) -> None:
        result = verify_snippet(
            slug="stderr_L1_L3",
            file_path=temp_dir / "test.md",
            line_start=1,
            line_end=3,
            content=INVALID_MERMAID,
            tmp_dir=temp_dir,
        )
        # mmdc should emit something to stderr/stdout on failure
        assert not result.success
        assert len(result.stderr) > 0 or len(result.stdout) > 0


# ============================================================================
# Tests: main — no npx required paths
# ============================================================================


class TestMainNoNpx:
    def test_empty_paths_returns_empty_report(self, temp_dir: Path) -> None:
        args = Namespace(paths=[], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        assert report["summary"]["total_snippets"] == 0

    def test_nonexistent_path_returns_empty_report(self, temp_dir: Path) -> None:
        args = Namespace(paths=[str(temp_dir / "ghost.md")], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        assert report["summary"]["total_snippets"] == 0

    def test_file_with_no_mermaid_produces_zero_snippets(self, no_mermaid_md: Path, temp_dir: Path) -> None:
        args = Namespace(paths=[str(no_mermaid_md)], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        assert report["summary"]["total_snippets"] == 0
        assert report["summary"]["files_scanned"] == 0

    def test_main_creates_own_tmp_dir_when_not_injected(self, no_mermaid_md: Path) -> None:
        # Exercises the `with tempfile.TemporaryDirectory()` branch in main()
        args = Namespace(paths=[str(no_mermaid_md)], verbose=False, quiet=False)
        report = main(args)  # no tmp_dir injection
        assert report["summary"]["total_snippets"] == 0

    def test_report_has_required_keys(self, no_mermaid_md: Path, temp_dir: Path) -> None:
        args = Namespace(paths=[str(no_mermaid_md)], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        assert "summary" in report
        assert "results" in report
        for key in ("total_snippets", "passed", "failed", "files_scanned"):
            assert key in report["summary"]


# ============================================================================
# Tests: main — requires npx
# ============================================================================


@pytest.mark.skipif(not _npx_available, reason="npx not available in this environment")
class TestMainWithNpx:
    def test_processes_valid_markdown_file(self, sample_md: Path, temp_dir: Path) -> None:
        args = Namespace(paths=[str(sample_md)], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        assert report["summary"]["total_snippets"] == 2
        assert report["summary"]["files_scanned"] == 1

    def test_report_is_json_serializable(self, sample_md: Path, temp_dir: Path) -> None:
        args = Namespace(paths=[str(sample_md)], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        # Must not raise
        json_str = json.dumps(report)
        parsed = json.loads(json_str)
        assert parsed["summary"]["total_snippets"] == 2

    def test_directory_scan_finds_snippets(self, sample_md: Path, temp_dir: Path) -> None:
        args = Namespace(paths=[str(temp_dir)], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        assert report["summary"]["total_snippets"] >= 2

    def test_invalid_mermaid_produces_failure_in_report(self, invalid_md: Path, temp_dir: Path) -> None:
        # Exercises the log.warning branch in _process_files
        args = Namespace(paths=[str(invalid_md)], verbose=False, quiet=False)
        report = main(args, tmp_dir=temp_dir)
        assert report["summary"]["total_snippets"] == 1
        assert report["summary"]["failed"] == 1


# ============================================================================
# PEP-723 entry point
# ============================================================================

if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    extra_args = sys.argv[1:]
    sys.exit(pytest.main(base_args + extra_args))
