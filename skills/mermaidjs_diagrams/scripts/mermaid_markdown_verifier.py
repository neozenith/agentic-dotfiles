#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""
Mermaid Markdown Verifier

Scans Markdown files for ```mermaid code fences, renders each snippet via
mermaid-cli (mmdc), and outputs a JSON report of pass/fail status.

Each snippet is identified by a unique slug derived from the absolute file path
(SHA-1 hashed) and the line number range of the opening/closing fences.

Requires: Node.js + npx (mermaid-cli fetched automatically via npx).

Usage:
    python mermaid_markdown_verifier.py docs/plans/kg/00_gap_analysis.md
    python mermaid_markdown_verifier.py docs/                        # recursive
    python mermaid_markdown_verifier.py "docs/**/*.md" -v            # glob + verbose
    python mermaid_markdown_verifier.py README.md docs/plans/ -q     # multiple paths
"""

from __future__ import annotations

import argparse
import hashlib
import json
import logging
import re
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from textwrap import dedent

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

log = logging.getLogger(__name__)

# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class SnippetResult:
    """Render result for a single Mermaid code fence."""

    slug: str
    file_path: str
    line_start: int
    line_end: int
    content: str
    success: bool
    exit_code: int
    stdout: str
    stderr: str
    png_path: str | None


# ============================================================================
# Core Functions
# ============================================================================


def make_slug(file_path: Path, line_start: int, line_end: int) -> str:
    """Generate a unique slug from absolute file path and line number range.

    The slug encodes both a human-readable filename component and a 12-char
    SHA-1 hash of the absolute path, guaranteeing uniqueness even when two
    files share the same name in different directories.

    Example: ``00_gap_analysis_md__a3f7b2c1d2e3__L45_L68``
    """
    abs_path = str(file_path.resolve())
    path_hash = hashlib.sha1(abs_path.encode()).hexdigest()[:12]
    safe_name = re.sub(r"[^A-Za-z0-9]", "_", file_path.name)
    return f"{safe_name}__{path_hash}__L{line_start}_L{line_end}"


def extract_mermaid_snippets(file_path: Path) -> list[tuple[int, int, str]]:
    """Extract mermaid code fence snippets from a Markdown file.

    Handles fences using three or more backticks. The closing fence must use
    the same number of backticks (or more) as the opener, matching CommonMark
    spec semantics.

    Returns:
        List of ``(line_start, line_end, content)`` tuples where line numbers
        are 1-indexed and ``line_start`` / ``line_end`` are the lines of the
        opening and closing fence markers respectively.  ``content`` is the raw
        text between the fences (fences themselves excluded).
    """
    lines = file_path.read_text(encoding="utf-8").splitlines()
    snippets: list[tuple[int, int, str]] = []
    in_fence = False
    fence_start = 0
    fence_marker = ""
    fence_lines: list[str] = []

    for i, line in enumerate(lines, start=1):
        stripped = line.strip()
        if not in_fence:
            m = re.match(r"^(`{3,})mermaid\s*$", stripped)
            if m:
                in_fence = True
                fence_start = i
                fence_marker = m.group(1)
                fence_lines = []
        else:
            close_m = re.match(r"^(`{3,})\s*$", stripped)
            if close_m and len(close_m.group(1)) >= len(fence_marker):
                snippets.append((fence_start, i, "\n".join(fence_lines)))
                in_fence = False
                fence_marker = ""
                fence_lines = []
            else:
                fence_lines.append(line)

    return snippets


def collect_markdown_files(paths: list[str]) -> list[Path]:
    """Collect unique Markdown files from file paths, directories, or globs.

    Each element of ``paths`` is tried as:
    1. A literal file path (``Path.is_file()``)
    2. A directory to search recursively for ``*.md`` files
    3. A glob pattern evaluated from the current working directory

    Results are deduplicated by resolved absolute path, preserving order.
    """
    collected: list[Path] = []
    for path_str in paths:
        path = Path(path_str)
        if path.is_dir():
            collected.extend(sorted(path.rglob("*.md")))
        elif path.is_file():
            collected.append(path)
        else:
            # Treat as a glob pattern relative to cwd (only for relative patterns;
            # Path.glob() raises NotImplementedError on absolute patterns)
            if not path.is_absolute():
                matches = sorted(Path.cwd().glob(path_str))
                collected.extend(p for p in matches if p.suffix == ".md")

    # Deduplicate while preserving insertion order
    seen: set[Path] = set()
    unique: list[Path] = []
    for p in collected:
        resolved = p.resolve()
        if resolved not in seen:
            seen.add(resolved)
            unique.append(p)
    return unique


def verify_snippet(
    slug: str,
    file_path: Path,
    line_start: int,
    line_end: int,
    content: str,
    tmp_dir: Path,
    _cmd: list[str] | None = None,
) -> SnippetResult:
    """Write a snippet to a ``.mmd`` file and render it via ``mmdc``.

    Args:
        slug: Unique identifier used for temp file names.
        file_path: Source Markdown file (used for reporting only).
        line_start: 1-indexed line of the opening fence.
        line_end: 1-indexed line of the closing fence.
        content: Raw Mermaid diagram text (fences excluded).
        tmp_dir: Directory for ``.mmd`` and ``.png`` temp files.
        _cmd: Override the render command (for testing error paths).
    """
    mmd_path = tmp_dir / f"{slug}.mmd"
    png_path = tmp_dir / f"{slug}.png"

    mmd_path.write_text(content, encoding="utf-8")

    cmd: list[str]
    if _cmd is not None:
        cmd = _cmd
    else:
        cmd = [
            "npx",
            "-p",
            "@mermaid-js/mermaid-cli",
            "mmdc",
            "--input",
            str(mmd_path),
            "--output",
            str(png_path),
            "--theme",
            "default",
            "--backgroundColor",
            "white",
            "--scale",
            "4",
        ]

    log.debug("Running mmdc for slug %s", slug)

    try:
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=60,
        )
        success = proc.returncode == 0
        return SnippetResult(
            slug=slug,
            file_path=str(file_path),
            line_start=line_start,
            line_end=line_end,
            content=content,
            success=success,
            exit_code=proc.returncode,
            stdout=proc.stdout.strip(),
            stderr=proc.stderr.strip(),
            png_path=str(png_path) if success and png_path.exists() else None,
        )
    except subprocess.TimeoutExpired:  # pragma: no cover
        return SnippetResult(
            slug=slug,
            file_path=str(file_path),
            line_start=line_start,
            line_end=line_end,
            content=content,
            success=False,
            exit_code=-1,
            stdout="",
            stderr="mmdc timed out after 60 seconds",
            png_path=None,
        )
    except FileNotFoundError:
        return SnippetResult(
            slug=slug,
            file_path=str(file_path),
            line_start=line_start,
            line_end=line_end,
            content=content,
            success=False,
            exit_code=-2,
            stdout="",
            stderr="npx not found — ensure Node.js and npm are installed",
            png_path=None,
        )


def build_report(results: list[SnippetResult]) -> dict:  # type: ignore[type-arg]
    """Consolidate snippet results into a structured report dict."""
    files_scanned = len({r.file_path for r in results})
    passed = sum(1 for r in results if r.success)
    failed = len(results) - passed

    return {
        "summary": {
            "total_snippets": len(results),
            "passed": passed,
            "failed": failed,
            "files_scanned": files_scanned,
        },
        "results": [asdict(r) for r in results],
    }


# ============================================================================
# Internal Processing
# ============================================================================


def _process_files(files: list[Path], tmp_dir: Path) -> dict:  # type: ignore[type-arg]
    """Process all files, render each snippet, return consolidated report."""
    all_results: list[SnippetResult] = []

    for file_path in files:
        log.info("Processing %s", file_path)
        snippets = extract_mermaid_snippets(file_path)
        log.info("  Found %d mermaid snippet(s)", len(snippets))

        for line_start, line_end, content in snippets:
            slug = make_slug(file_path, line_start, line_end)
            log.debug("  Verifying %s (lines %d-%d)", slug, line_start, line_end)
            result = verify_snippet(slug, file_path, line_start, line_end, content, tmp_dir)
            all_results.append(result)

            if result.success:
                log.info("  ✓ lines %d-%d passed", line_start, line_end)
            else:
                log.warning(
                    "  ✗ lines %d-%d failed (exit=%d): %s",
                    line_start,
                    line_end,
                    result.exit_code,
                    result.stderr[:120],
                )

    return build_report(all_results)


# ============================================================================
# CLI Interface
# ============================================================================


def main(args: argparse.Namespace, tmp_dir: Path | None = None) -> dict:  # type: ignore[type-arg]
    """Main entry point. Returns the report dict.

    Args:
        args: Parsed CLI arguments.
        tmp_dir: Injected temp directory (for testing). When ``None``, a
                 ``TemporaryDirectory`` is created and cleaned up automatically.
    """
    if not args.paths:
        log.error("No paths specified")
        return build_report([])

    files = collect_markdown_files(args.paths)
    if not files:
        log.warning("No Markdown files found for paths: %s", args.paths)
        return build_report([])

    log.info("Scanning %d Markdown file(s) for mermaid snippets...", len(files))

    if tmp_dir is not None:
        return _process_files(files, tmp_dir)

    with tempfile.TemporaryDirectory() as tmp:
        return _process_files(files, Path(tmp))


if __name__ == "__main__":  # pragma: no cover
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(
            """\
            mermaid_markdown_verifier — Extract and verify Mermaid diagrams in Markdown files.

            Scans each file for ```mermaid code fences, renders every snippet via
            mermaid-cli (mmdc), and outputs a JSON report with pass/fail status and
            captured error output for any failing diagrams.

            Requires: Node.js + npx (mermaid-cli fetched automatically).
            """
        ),
        epilog=dedent(
            """\
            Examples:
              %(prog)s docs/plans/kg/00_gap_analysis.md       # single file
              %(prog)s docs/                                   # recursive directory scan
              %(prog)s "docs/**/*.md"                          # glob (quote to prevent shell expansion)
              %(prog)s README.md docs/plans/ -v               # multiple paths, verbose
              %(prog)s docs/ -q                               # quiet (errors only)

            Exit codes:
              0  All diagrams rendered successfully (or no diagrams found)
              1  One or more diagrams failed to render
            """
        ),
    )
    parser.add_argument("paths", nargs="*", help="Markdown files, directories, or glob patterns")
    parser.add_argument("-v", "--verbose", action="store_true", help="Debug logging")
    parser.add_argument("-q", "--quiet", action="store_true", help="Errors only")

    parsed = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if parsed.verbose else logging.ERROR if parsed.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    report = main(parsed)
    print(json.dumps(report, indent=2))

    sys.exit(0 if report["summary"]["failed"] == 0 else 1)
