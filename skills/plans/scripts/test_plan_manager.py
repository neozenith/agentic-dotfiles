#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "pytest>=8.0",
#   "pytest-cov>=4.0",
#   "marko>=2.2.2",
#   "python-frontmatter>=1.1.0",
#   "tiktoken>=0.9.0",
# ]
# ///
"""Tests for plan_manager.py — hierarchical planning document manager."""

from __future__ import annotations

import json
import sys
import tempfile
from argparse import Namespace
from pathlib import Path
from typing import Any

import frontmatter
import marko
import plan_manager as pm
import pytest

# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def temp_dir() -> Path:
    """Create a temporary directory for test files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def sample_md(temp_dir: Path) -> Path:
    """Create a sample markdown file without frontmatter."""
    content = """# My Plan

This is the introduction paragraph with enough words to be meaningful.

## Section One

Content for section one goes here. This has multiple sentences.
It describes the first part of the plan in detail.

### Subsection 1.1

Detailed subsection content with specific implementation notes.

## Section Two

Content for section two is here. Another set of details.

## Section Three

Third section with its own content.
"""
    path = temp_dir / "plan.md"
    path.write_text(content, encoding="utf-8")
    return path


@pytest.fixture
def sample_md_with_frontmatter(temp_dir: Path) -> Path:
    """Create a sample markdown file with existing frontmatter."""
    post = frontmatter.Post(
        "## Overview\n\nThis is a plan overview.\n\n## Details\n\nSome details here.",
        id="test-id-123",
        title="Test Plan",
        summary="A test plan for validation.",
        status="active",
        parent=None,
        children=[],
        token_estimate=100,
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        tags=["test"],
    )
    path = temp_dir / "with_meta.md"
    path.write_text(frontmatter.dumps(post), encoding="utf-8")
    return path


@pytest.fixture
def plan_hierarchy(temp_dir: Path) -> Path:
    """Create a hierarchy of plan documents with parent/child relationships."""
    # Root plan
    root_post = frontmatter.Post(
        "# Root Plan\n\nThe top-level plan.\n\n## Overview\n\nHigh level overview.",
        id="root-id",
        title="Root Plan",
        summary="The root planning document.",
        status="active",
        parent=None,
        children=["children/child-a.md", "children/child-b.md"],
        token_estimate=50,
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        tags=[],
    )
    root_path = temp_dir / "root.md"
    root_path.write_text(frontmatter.dumps(root_post), encoding="utf-8")

    # Child directory
    children_dir = temp_dir / "children"
    children_dir.mkdir()

    # Child A
    child_a_post = frontmatter.Post(
        "## Child A Content\n\nDetailed content for child A.",
        id="child-a-id",
        title="Child A",
        summary="First child document with detailed content.",
        status="active",
        parent="../root.md",
        children=[],
        token_estimate=30,
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        tags=[],
    )
    (children_dir / "child-a.md").write_text(frontmatter.dumps(child_a_post), encoding="utf-8")

    # Child B
    child_b_post = frontmatter.Post(
        "## Child B Content\n\nDetailed content for child B.",
        id="child-b-id",
        title="Child B",
        summary="Second child document.",
        status="draft",
        parent="../root.md",
        children=[],
        token_estimate=25,
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        tags=[],
    )
    (children_dir / "child-b.md").write_text(frontmatter.dumps(child_b_post), encoding="utf-8")

    return root_path


@pytest.fixture
def three_level_hierarchy(temp_dir: Path) -> Path:
    """Create a 3-level hierarchy: root → child → grandchild."""
    # Root
    root_post = frontmatter.Post(
        "# Root\n\nRoot content.",
        id="root-id",
        title="Root",
        summary="Root summary.",
        status="active",
        parent=None,
        children=["root/child.md"],
        token_estimate=10,
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        tags=[],
    )
    root_path = temp_dir / "root.md"
    root_path.write_text(frontmatter.dumps(root_post), encoding="utf-8")

    # Child dir
    child_dir = temp_dir / "root"
    child_dir.mkdir()

    child_post = frontmatter.Post(
        "## Child\n\nChild content.",
        id="child-id",
        title="Child",
        summary="Child summary.",
        status="active",
        parent="../root.md",
        children=["child/grandchild.md"],
        token_estimate=10,
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        tags=[],
    )
    (child_dir / "child.md").write_text(frontmatter.dumps(child_post), encoding="utf-8")

    # Grandchild dir
    grandchild_dir = child_dir / "child"
    grandchild_dir.mkdir()

    grandchild_post = frontmatter.Post(
        "### Grandchild\n\nGrandchild content.",
        id="grandchild-id",
        title="Grandchild",
        summary="Grandchild summary.",
        status="draft",
        parent="../child.md",
        children=[],
        token_estimate=10,
        created="2026-01-01T00:00:00+00:00",
        updated="2026-01-01T00:00:00+00:00",
        tags=[],
    )
    (grandchild_dir / "grandchild.md").write_text(
        frontmatter.dumps(grandchild_post), encoding="utf-8"
    )

    return root_path


def _parse(body: str) -> marko.block.Document:
    """Parse markdown body into marko AST."""
    md = pm.get_md_parser()
    return md.parse(body)


def _make_args(**kwargs: Any) -> Namespace:
    """Create an argparse.Namespace with defaults."""
    defaults: dict[str, Any] = {
        "verbose": False,
        "command": None,
        "format": "json",
        "summaries_only": False,
    }
    defaults.update(kwargs)
    return Namespace(**defaults)


# ============================================================================
# Token Counting
# ============================================================================


class TestCountTokens:
    def test_empty_string(self) -> None:
        assert pm.count_tokens("") == 0

    def test_whitespace_only(self) -> None:
        assert pm.count_tokens("   \n\n  ") == 0

    def test_simple_text(self) -> None:
        count = pm.count_tokens("Hello, world!")
        assert count > 0
        assert count < 10  # Should be just a few tokens

    def test_longer_text(self) -> None:
        text = "This is a longer piece of text with multiple words and sentences. " * 10
        count = pm.count_tokens(text)
        assert count > 50

    def test_get_encoder_cached(self) -> None:
        enc1 = pm.get_encoder()
        enc2 = pm.get_encoder()
        assert enc1 is enc2  # Same instance (cached)


# ============================================================================
# Slugify
# ============================================================================


class TestSlugify:
    def test_basic(self) -> None:
        assert pm.slugify("Hello World") == "hello-world"

    def test_special_chars(self) -> None:
        assert pm.slugify("Section (1): Setup!") == "section-1-setup"

    def test_multiple_spaces(self) -> None:
        assert pm.slugify("Multiple   Spaces   Here") == "multiple-spaces-here"

    def test_hyphens(self) -> None:
        assert pm.slugify("already-kebab-case") == "already-kebab-case"


# ============================================================================
# Section Extraction (AST-based)
# ============================================================================


class TestExtractSectionsAst:
    def test_no_headings(self) -> None:
        body = "Just plain text without any headings."
        parsed = _parse(body)
        preamble, sections = pm.extract_sections_ast(parsed)
        assert "Just plain text" in preamble
        assert sections == []

    def test_single_heading(self) -> None:
        body = "## Section One\n\nContent here."
        parsed = _parse(body)
        preamble, sections = pm.extract_sections_ast(parsed)
        assert preamble == ""
        assert len(sections) == 1
        assert sections[0][0] == 2  # level
        assert sections[0][1] == "Section One"  # heading

    def test_multiple_headings(self) -> None:
        body = "# Title\n\nIntro.\n\n## Part A\n\nContent A.\n\n## Part B\n\nContent B."
        parsed = _parse(body)
        preamble, sections = pm.extract_sections_ast(parsed)
        assert preamble == ""
        assert len(sections) == 3
        assert sections[0][1] == "Title"
        assert sections[1][1] == "Part A"
        assert sections[2][1] == "Part B"

    def test_preamble_before_heading(self) -> None:
        body = "Some intro text.\n\n## First Section\n\nContent."
        parsed = _parse(body)
        preamble, sections = pm.extract_sections_ast(parsed)
        assert "Some intro text." in preamble
        assert len(sections) == 1

    def test_nested_headings(self) -> None:
        body = "## Parent\n\nContent.\n\n### Child\n\nChild content.\n\n## Sibling\n\nMore."
        parsed = _parse(body)
        _, sections = pm.extract_sections_ast(parsed)
        assert len(sections) == 3
        assert sections[0][0] == 2  # ## Parent
        assert sections[1][0] == 3  # ### Child
        assert sections[2][0] == 2  # ## Sibling

    def test_node_indices_are_contiguous(self) -> None:
        body = "# A\n\nContent A.\n\n## B\n\nContent B.\n\n## C\n\nContent C."
        parsed = _parse(body)
        _, sections = pm.extract_sections_ast(parsed)
        # First section starts at node index 0
        assert sections[0][2] == 0
        # Each section's end matches the next section's start
        for i in range(len(sections) - 1):
            assert sections[i][3] == sections[i + 1][2]
        # Last section's end is the total number of children
        assert sections[-1][3] == len(parsed.children)

    def test_code_fence_comments_not_treated_as_headings(self) -> None:
        """Critical: # comments inside code fences must NOT be treated as headings."""
        body = (
            "# Real Heading\n\n"
            "Some content.\n\n"
            "```python\n"
            "# This is a code comment, not a heading\n"
            "x = 42\n"
            "```\n\n"
            "## Another Real Heading\n\n"
            "More content."
        )
        parsed = _parse(body)
        _, sections = pm.extract_sections_ast(parsed)
        # Should only find 2 headings, not 3
        assert len(sections) == 2
        assert sections[0][1] == "Real Heading"
        assert sections[1][1] == "Another Real Heading"

    def test_multiple_code_fence_comments(self) -> None:
        """Multiple # lines inside different code fences."""
        body = (
            "## Setup\n\n"
            "```python\n"
            "# Setup the pipeline\n"
            "pipeline = Pipeline([])\n"
            "```\n\n"
            "```python\n"
            "# Publisher (on write operations)\n"
            "async def publish(): pass\n"
            "```\n\n"
            "## Monitoring\n\n"
            "Metrics here."
        )
        parsed = _parse(body)
        _, sections = pm.extract_sections_ast(parsed)
        assert len(sections) == 2
        headings = [s[1] for s in sections]
        assert "Setup" in headings
        assert "Monitoring" in headings
        # Code comments should NOT appear as headings
        assert "Setup the pipeline" not in headings
        assert "Publisher (on write operations)" not in headings


# ============================================================================
# Section Tree Building
# ============================================================================


class TestBuildSectionTree:
    def test_flat_sections(self) -> None:
        body = "## A\n\nContent A.\n\n## B\n\nContent B."
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        assert len(tree) == 2
        assert tree[0].heading == "A"
        assert tree[1].heading == "B"
        assert tree[0].children == []
        assert tree[1].children == []

    def test_nested_sections(self) -> None:
        body = "## Parent\n\nContent.\n\n### Child 1\n\nC1.\n\n### Child 2\n\nC2."
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        assert len(tree) == 1
        parent = tree[0]
        assert parent.heading == "Parent"
        assert len(parent.children) == 2
        assert parent.children[0].heading == "Child 1"
        assert parent.children[1].heading == "Child 2"
        assert parent.children[0].parent is parent

    def test_deep_nesting(self) -> None:
        body = "# L1\n\n## L2\n\n### L3\n\n#### L4\n\nDeep content."
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        assert len(tree) == 1
        assert tree[0].children[0].children[0].children[0].heading == "L4"

    def test_sibling_after_nested(self) -> None:
        body = "## A\n\n### A.1\n\nNested.\n\n## B\n\nSibling."
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        assert len(tree) == 2
        assert tree[0].heading == "A"
        assert len(tree[0].children) == 1
        assert tree[1].heading == "B"
        assert tree[1].children == []

    def test_total_tokens(self) -> None:
        body = "## Parent\n\nContent.\n\n### Child\n\nMore content."
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        parent = tree[0]
        assert parent.total_tokens == parent.token_estimate + parent.children[0].token_estimate

    def test_full_node_end_with_children(self) -> None:
        body = "## A\n\nContent A.\n\n### A.1\n\nSub content.\n\n## B\n\nContent B."
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        # A's full_node_end should include A.1
        section_a = tree[0]
        assert section_a.full_node_end == section_a.children[0].node_end
        # B's full_node_end is its own node_end
        section_b = tree[1]
        assert section_b.full_node_end == section_b.node_end

    def test_walk(self) -> None:
        body = "## A\n\n### A.1\n\n### A.2\n\n## B\n\n"
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        walked = tree[0].walk()
        assert len(walked) == 3  # A, A.1, A.2
        assert walked[0].heading == "A"
        assert walked[1].heading == "A.1"
        assert walked[2].heading == "A.2"


# ============================================================================
# Parsing
# ============================================================================


class TestParsePlan:
    def test_parse_without_frontmatter(self, sample_md: Path) -> None:
        doc = pm.parse_plan(sample_md)
        assert doc.path == sample_md
        assert doc.metadata == {}
        assert len(doc.sections) > 0
        assert doc.total_token_estimate > 0

    def test_parse_with_frontmatter(self, sample_md_with_frontmatter: Path) -> None:
        doc = pm.parse_plan(sample_md_with_frontmatter)
        assert doc.metadata["title"] == "Test Plan"
        assert doc.metadata["status"] == "active"
        assert len(doc.sections) == 2

    def test_all_sections_flat(self, sample_md: Path) -> None:
        doc = pm.parse_plan(sample_md)
        all_sections = doc.all_sections()
        # Should include nested sections
        assert len(all_sections) >= len(doc.sections)

    def test_preamble_extraction(self, temp_dir: Path) -> None:
        content = "Some preamble text.\n\n## First Section\n\nContent."
        path = temp_dir / "preamble.md"
        path.write_text(content, encoding="utf-8")
        doc = pm.parse_plan(path)
        assert "Some preamble text." in doc.preamble

    def test_parsed_ast_stored(self, sample_md: Path) -> None:
        """PlanDocument should store the marko AST."""
        doc = pm.parse_plan(sample_md)
        assert isinstance(doc.parsed, marko.block.Document)


# ============================================================================
# Validate Markdown
# ============================================================================


class TestValidateMarkdown:
    def test_valid_markdown(self) -> None:
        assert pm.validate_markdown("# Hello\n\nWorld.") is True

    def test_empty_string(self) -> None:
        assert pm.validate_markdown("") is True


# ============================================================================
# Frontmatter Helpers
# ============================================================================


class TestMakeFrontmatter:
    def test_defaults(self) -> None:
        meta = pm.make_frontmatter(title="Test")
        assert meta["title"] == "Test"
        assert meta["status"] == "draft"
        assert meta["summary"] == ""
        assert meta["children"] == []
        assert meta["tags"] == []
        assert "id" in meta
        assert "created" in meta
        assert "updated" in meta

    def test_custom_values(self) -> None:
        meta = pm.make_frontmatter(
            title="Custom",
            summary="A summary.",
            status="active",
            parent="parent.md",
            children=["child.md"],
            token_estimate=500,
            tags=["test"],
        )
        assert meta["summary"] == "A summary."
        assert meta["status"] == "active"
        assert meta["parent"] == "parent.md"
        assert meta["children"] == ["child.md"]
        assert meta["token_estimate"] == 500


class TestUpdateFrontmatterFields:
    def test_update_fields(self, sample_md_with_frontmatter: Path) -> None:
        pm.update_frontmatter_fields(
            sample_md_with_frontmatter,
            {"status": "complete", "token_estimate": 999},
        )
        post = frontmatter.load(str(sample_md_with_frontmatter))
        assert post["status"] == "complete"
        assert post["token_estimate"] == 999
        # Updated timestamp should have changed
        assert post["updated"] != "2026-01-01T00:00:00+00:00"


# ============================================================================
# Summary Generation
# ============================================================================


class TestGenerateSummaryHeuristic:
    def test_prose_extraction(self) -> None:
        body = "## Heading\n\nFirst sentence here. Second sentence follows. Third one too."
        summary = pm.generate_summary_heuristic(body)
        assert "First sentence here." in summary
        assert "Second sentence follows." in summary

    def test_strips_code_blocks(self) -> None:
        body = "Intro sentence here.\n\n```python\ncode = True\n```\n\nFollowing sentence."
        summary = pm.generate_summary_heuristic(body)
        assert "code = True" not in summary

    def test_strips_blockquotes(self) -> None:
        body = "> Quote line.\n\nActual content sentence here."
        summary = pm.generate_summary_heuristic(body)
        assert "Quote line" not in summary

    def test_handles_empty_body(self) -> None:
        summary = pm.generate_summary_heuristic("")
        assert isinstance(summary, str)

    def test_max_sentences(self) -> None:
        body = (
            "This is the first complete sentence of the document. "
            "Here comes the second sentence with details. "
            "A third sentence provides more context. "
            "Fourth sentence adds extra information. "
            "Fifth sentence wraps things up nicely."
        )
        summary = pm.generate_summary_heuristic(body, max_sentences=2)
        # Should contain at most 2 sentences
        assert "first complete sentence" in summary
        assert "second sentence" in summary
        assert "third sentence" not in summary.lower()


# ============================================================================
# Render Node Range
# ============================================================================


class TestRenderNodeRange:
    def test_renders_subset(self) -> None:
        body = "# A\n\nContent A.\n\n## B\n\nContent B."
        parsed = _parse(body)
        # Render just the first child (heading)
        rendered = pm.render_node_range(parsed, 0, 1)
        assert "A" in rendered

    def test_renders_full_document(self) -> None:
        body = "# A\n\nContent A."
        parsed = _parse(body)
        rendered = pm.render_node_range(parsed, 0, len(parsed.children))
        assert "A" in rendered
        assert "Content A." in rendered


# ============================================================================
# Command: init
# ============================================================================


class TestCmdInit:
    def test_init_new_frontmatter(
        self, sample_md: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="init", file=str(sample_md), title=None)
        pm.cmd_init(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["token_estimate"] > 0
        assert result["title"] == "My Plan"

        # Verify file was updated
        post = frontmatter.load(str(sample_md))
        assert "id" in post.metadata
        assert post["title"] == "My Plan"
        assert post["status"] == "draft"
        assert post["token_estimate"] > 0

    def test_init_preserves_existing(
        self, sample_md_with_frontmatter: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="init", file=str(sample_md_with_frontmatter), title=None)
        pm.cmd_init(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["title"] == "Test Plan"  # Preserved

        post = frontmatter.load(str(sample_md_with_frontmatter))
        assert post["id"] == "test-id-123"  # Preserved
        assert post["status"] == "active"  # Preserved

    def test_init_with_explicit_title(
        self, sample_md: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="init", file=str(sample_md), title="Custom Title")
        pm.cmd_init(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["title"] == "Custom Title"


# ============================================================================
# Command: analyze
# ============================================================================


class TestCmdAnalyze:
    def test_analyze_json(self, sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = _make_args(command="analyze", file=str(sample_md), format="json")
        pm.cmd_analyze(args)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "total_token_estimate" in result
        assert "sections" in result
        assert result["total_token_estimate"] > 0

    def test_analyze_tree(self, sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = _make_args(command="analyze", file=str(sample_md), format="tree")
        pm.cmd_analyze(args)
        captured = capsys.readouterr()
        assert "Plan:" in captured.out
        assert "tokens" in captured.out
        assert "CommonMark valid:" in captured.out

    def test_analyze_with_frontmatter(
        self, sample_md_with_frontmatter: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="analyze", file=str(sample_md_with_frontmatter), format="json")
        pm.cmd_analyze(args)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["metadata"]["title"] == "Test Plan"


# ============================================================================
# Command: context
# ============================================================================


class TestCmdContext:
    def test_context_depth_0(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="context", file=str(plan_hierarchy), depth=0, max_tokens=8000)
        pm.cmd_context(args)
        captured = capsys.readouterr()
        assert "# Plan: Root Plan" in captured.out
        assert "The root planning document." in captured.out
        # Should NOT include body at depth 0
        assert "High level overview" not in captured.out

    def test_context_depth_1(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="context", file=str(plan_hierarchy), depth=1, max_tokens=8000)
        pm.cmd_context(args)
        captured = capsys.readouterr()
        assert "# Plan: Root Plan" in captured.out
        # Body should be included
        assert "High level overview" in captured.out
        # Child summaries should be included
        assert "Child A" in captured.out
        assert "Child B" in captured.out

    def test_context_budget_limit(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        # Very small budget — should still get the header
        args = _make_args(command="context", file=str(plan_hierarchy), depth=1, max_tokens=50)
        pm.cmd_context(args)
        captured = capsys.readouterr()
        assert "# Plan: Root Plan" in captured.out

    def test_context_missing_child(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        root_post = frontmatter.Post(
            "## Content\n\nBody.",
            title="Test",
            summary="Test summary.",
            children=["nonexistent.md"],
            status="draft",
            token_estimate=10,
        )
        root = temp_dir / "root.md"
        root.write_text(frontmatter.dumps(root_post), encoding="utf-8")

        args = _make_args(command="context", file=str(root), depth=1, max_tokens=8000)
        pm.cmd_context(args)
        captured = capsys.readouterr()
        assert "FILE NOT FOUND" in captured.out

    def test_context_summaries_only(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--summaries-only should emit only frontmatter summaries, no bodies."""
        args = _make_args(
            command="context",
            file=str(plan_hierarchy),
            depth=1,
            max_tokens=8000,
            summaries_only=True,
        )
        pm.cmd_context(args)
        captured = capsys.readouterr()
        assert "# Plan: Root Plan" in captured.out
        # Child summaries should appear
        assert "Child A" in captured.out
        assert "Child B" in captured.out
        # Body content should NOT appear (summaries-only mode)
        assert "High level overview" not in captured.out

    def test_context_depth_unlimited(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """--depth -1 should load the entire tree."""
        args = _make_args(command="context", file=str(plan_hierarchy), depth=-1, max_tokens=50000)
        pm.cmd_context(args)
        captured = capsys.readouterr()
        assert "# Plan: Root Plan" in captured.out
        assert "Child A" in captured.out
        assert "Child B" in captured.out


# ============================================================================
# Command: rebalance
# ============================================================================


class TestCmdRebalance:
    def _make_large_doc(self, temp_dir: Path, num_sections: int = 5) -> Path:
        """Create a large document that exceeds the default threshold."""
        sections = []
        for i in range(num_sections):
            # Each section has ~200 tokens of content
            content = f"This is detailed content for section {i}. " * 50
            sections.append(f"## Section {i}\n\n{content}")
        body = "# Large Plan\n\nIntroduction.\n\n" + "\n\n".join(sections)

        post = frontmatter.Post(
            body,
            id="large-doc-id",
            title="Large Plan",
            summary="A large plan.",
            status="draft",
            children=[],
            token_estimate=0,
        )
        path = temp_dir / "large.md"
        path.write_text(frontmatter.dumps(post), encoding="utf-8")
        return path

    def test_within_budget(
        self, sample_md_with_frontmatter: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(
            command="rebalance",
            file=str(sample_md_with_frontmatter),
            threshold=100_000,
            min_section=500,
            dry_run=False,
        )
        pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["status"] == "within_budget"

    def test_dry_run(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = self._make_large_doc(temp_dir)
        args = _make_args(
            command="rebalance",
            file=str(path),
            threshold=500,
            min_section=100,
            dry_run=True,
        )
        pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["status"] == "dry_run"
        assert len(result["extracted"]) > 0
        # No child files should have been created
        child_dir = path.parent / path.stem
        assert not child_dir.exists()

    def test_actual_rebalance(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        path = self._make_large_doc(temp_dir)
        args = _make_args(
            command="rebalance",
            file=str(path),
            threshold=500,
            min_section=100,
            dry_run=False,
        )
        pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["status"] == "rebalanced"
        assert len(result["extracted"]) > 0

        # Child files should exist
        for entry in result["extracted"]:
            child_path = Path(entry["created"])
            assert child_path.exists()
            # Each child should have frontmatter
            child_post = frontmatter.load(str(child_path))
            assert "id" in child_post.metadata
            assert "title" in child_post.metadata
            assert "summary" in child_post.metadata

        # Parent should reference children
        parent_post = frontmatter.load(str(path))
        assert len(parent_post["children"]) > 0

    def test_rebalance_produces_valid_markdown(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Post-rebalance: both parent and child files must be valid CommonMark."""
        path = self._make_large_doc(temp_dir)
        args = _make_args(
            command="rebalance",
            file=str(path),
            threshold=500,
            min_section=100,
            dry_run=False,
        )
        pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)

        # Validate parent
        parent_post = frontmatter.load(str(path))
        assert pm.validate_markdown(str(parent_post.content))

        # Validate each child
        for entry in result["extracted"]:
            child_path = Path(entry["created"])
            child_post = frontmatter.load(str(child_path))
            assert pm.validate_markdown(str(child_post.content))

    def test_rebalance_with_code_fences(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Rebalance on a doc with code fences should produce valid output."""
        body = (
            "# Plan\n\n"
            "Introduction.\n\n"
            "## Architecture\n\n"
            "Design notes.\n\n"
            "```python\n"
            "# Setup the pipeline\n"
            "pipeline = Pipeline([])\n"
            "```\n\n" + ("More architecture content. " * 100) + "\n\n"
            "## Monitoring\n\n" + ("Monitoring details here. " * 100)
        )
        post = frontmatter.Post(body, title="Plan", status="draft", children=[], token_estimate=0)
        path = temp_dir / "code_fence.md"
        path.write_text(frontmatter.dumps(post), encoding="utf-8")

        args = _make_args(
            command="rebalance",
            file=str(path),
            threshold=200,
            min_section=50,
            dry_run=False,
        )
        pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["status"] == "rebalanced"

        # Both parent and children should be valid markdown
        parent_post = frontmatter.load(str(path))
        assert pm.validate_markdown(str(parent_post.content))
        for entry in result["extracted"]:
            child_post = frontmatter.load(str(Path(entry["created"])))
            assert pm.validate_markdown(str(child_post.content))

    def test_no_candidates(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        # Create a doc with many tiny sections
        sections = [f"## S{i}\n\nTiny." for i in range(10)]
        body = "\n\n".join(sections)
        post = frontmatter.Post(body, title="Tiny", status="draft", children=[])
        path = temp_dir / "tiny.md"
        path.write_text(frontmatter.dumps(post), encoding="utf-8")

        args = _make_args(
            command="rebalance",
            file=str(path),
            threshold=10,  # Very low threshold
            min_section=50_000,  # But very high min section
            dry_run=False,
        )
        pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["status"] == "no_candidates"


# ============================================================================
# Command: update-summary
# ============================================================================


class TestCmdUpdateSummary:
    def test_single_update(
        self, sample_md_with_frontmatter: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(
            command="update-summary",
            file=str(sample_md_with_frontmatter),
            propagate=False,
        )
        pm.cmd_update_summary(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "summary" in result
        assert "token_estimate" in result
        assert result["token_estimate"] > 0

    def test_updates_token_estimate(
        self, sample_md_with_frontmatter: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(
            command="update-summary",
            file=str(sample_md_with_frontmatter),
            propagate=False,
        )
        pm.cmd_update_summary(args, summary_fn=pm.generate_summary_heuristic)

        post = frontmatter.load(str(sample_md_with_frontmatter))
        # Token estimate should reflect actual content
        actual = pm.count_tokens(post.content)
        assert post["token_estimate"] == actual


# ============================================================================
# Format Tree
# ============================================================================


class TestFormatTree:
    def test_flat_sections(self) -> None:
        sections = [
            pm.Section("A", 2, "## A\n\nContent.", 10, 0, 2),
            pm.Section("B", 2, "## B\n\nMore.", 8, 2, 4),
        ]
        lines = pm.format_tree(sections)
        assert len(lines) == 2
        assert "A" in lines[0]
        assert "B" in lines[1]
        # First should use ├, last should use └
        assert "\u251c" in lines[0]
        assert "\u2514" in lines[1]

    def test_nested_sections(self) -> None:
        child = pm.Section("Child", 3, "### Child\n\nC.", 5, 2, 4)
        parent = pm.Section("Parent", 2, "## Parent\n\nP.", 8, 0, 2, children=[child])
        child.parent = parent

        lines = pm.format_tree([parent])
        assert len(lines) == 2
        assert "Parent" in lines[0]
        assert "Child" in lines[1]


# ============================================================================
# Derive Child Path
# ============================================================================


class TestDeriveChildPath:
    def test_basic(self, temp_dir: Path) -> None:
        parent = temp_dir / "plan.md"
        parent.touch()
        child = pm.derive_child_path(parent, "My Section Title")
        assert child.name == "my-section-title.md"
        assert child.parent.name == "plan"
        assert child.parent.exists()

    def test_special_characters(self, temp_dir: Path) -> None:
        parent = temp_dir / "plan.md"
        parent.touch()
        child = pm.derive_child_path(parent, "Section: Setup & Config!")
        assert child.name == "section-setup-config.md"


# ============================================================================
# Section to Dict
# ============================================================================


class TestSectionToDict:
    def test_leaf_section(self) -> None:
        section = pm.Section("Leaf", 2, "## Leaf\n\nContent.", 10, 0, 2)
        d = pm.section_to_dict(section)
        assert d["heading"] == "Leaf"
        assert d["level"] == 2
        assert d["token_estimate"] == 10
        assert "children" not in d

    def test_section_with_children(self) -> None:
        child = pm.Section("Child", 3, "### Child\n\nC.", 5, 2, 4)
        parent = pm.Section("Parent", 2, "## Parent\n\nP.", 8, 0, 2, children=[child])
        d = pm.section_to_dict(parent)
        assert "children" in d
        assert len(d["children"]) == 1
        assert d["children"][0]["heading"] == "Child"


# ============================================================================
# Context Formatting
# ============================================================================


class TestFormatMetadataHeader:
    def test_basic(self, temp_dir: Path) -> None:
        meta = {
            "title": "My Plan",
            "status": "active",
            "token_estimate": 500,
            "updated": "2026-01-01",
        }
        header = pm.format_metadata_header(meta, temp_dir / "plan.md")
        assert "# Plan: My Plan" in header
        assert "active" in header
        assert "500" in header


class TestFormatChildSummary:
    def test_basic(self) -> None:
        meta = {
            "title": "Child",
            "status": "draft",
            "token_estimate": 200,
            "summary": "Child summary.",
        }
        block = pm.format_child_summary(meta, "./child.md")
        assert "[Child](./child.md)" in block
        assert "200" in block
        assert "draft" in block
        assert "Child summary." in block


# ============================================================================
# Section.full_text (AST-based)
# ============================================================================


class TestSectionFullText:
    def test_full_text_extraction(self) -> None:
        body = "## A\n\nContent A.\n\n### A.1\n\nSub content.\n\n## B\n\nContent B."
        parsed = _parse(body)
        _, flat = pm.extract_sections_ast(parsed)
        tree = pm.build_section_tree(parsed, flat)
        section_a = tree[0]
        full = section_a.full_text(parsed)
        assert "A" in full
        assert "A.1" in full
        assert "Sub content." in full


# ============================================================================
# Error Paths (file not found)
# ============================================================================


class TestErrorPaths:
    def test_init_file_not_found(self) -> None:
        args = _make_args(command="init", file="/nonexistent/path.md", title=None)
        with pytest.raises(SystemExit):
            pm.cmd_init(args, summary_fn=pm.generate_summary_heuristic)

    def test_analyze_file_not_found(self) -> None:
        args = _make_args(command="analyze", file="/nonexistent/path.md", format="json")
        with pytest.raises(SystemExit):
            pm.cmd_analyze(args)

    def test_context_file_not_found(self) -> None:
        args = _make_args(command="context", file="/nonexistent/path.md", depth=1, max_tokens=8000)
        with pytest.raises(SystemExit):
            pm.cmd_context(args)

    def test_rebalance_file_not_found(self) -> None:
        args = _make_args(
            command="rebalance",
            file="/nonexistent/path.md",
            threshold=4000,
            min_section=500,
            dry_run=False,
        )
        with pytest.raises(SystemExit):
            pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)

    def test_update_summary_file_not_found(self) -> None:
        args = _make_args(
            command="update-summary",
            file="/nonexistent/path.md",
            propagate=False,
        )
        with pytest.raises(SystemExit):
            pm.cmd_update_summary(args, summary_fn=pm.generate_summary_heuristic)


# ============================================================================
# Init: title from filename stem (no heading)
# ============================================================================


class TestCmdInitEdgeCases:
    def test_init_title_from_stem(self, temp_dir: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """When the doc has no heading, title is derived from the filename."""
        path = temp_dir / "my-cool-plan.md"
        path.write_text("Just some plain text without any headings.", encoding="utf-8")
        args = _make_args(command="init", file=str(path), title=None)
        pm.cmd_init(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["title"] == "My Cool Plan"


# ============================================================================
# Analyze: tree with summary and preamble
# ============================================================================


class TestCmdAnalyzeEdgeCases:
    def test_analyze_tree_with_summary(
        self, sample_md_with_frontmatter: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="analyze", file=str(sample_md_with_frontmatter), format="tree")
        pm.cmd_analyze(args)
        captured = capsys.readouterr()
        assert "Summary:" in captured.out

    def test_analyze_tree_long_summary_truncation(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        long_summary = "A" * 200
        post = frontmatter.Post(
            "## Content\n\nBody.",
            title="Test",
            summary=long_summary,
            status="draft",
        )
        path = temp_dir / "long.md"
        path.write_text(frontmatter.dumps(post), encoding="utf-8")

        args = _make_args(command="analyze", file=str(path), format="tree")
        pm.cmd_analyze(args)
        captured = capsys.readouterr()
        assert "..." in captured.out

    def test_analyze_tree_with_preamble(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        content = "Some preamble text.\n\n## Section\n\nContent."
        path = temp_dir / "preamble.md"
        path.write_text(content, encoding="utf-8")

        args = _make_args(command="analyze", file=str(path), format="tree")
        pm.cmd_analyze(args)
        captured = capsys.readouterr()
        assert "preamble:" in captured.out


# ============================================================================
# Context: depth 2 (recursive)
# ============================================================================


class TestCmdContextDepth2:
    def test_context_depth_2(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        args = _make_args(command="context", file=str(plan_hierarchy), depth=2, max_tokens=50000)
        pm.cmd_context(args)
        captured = capsys.readouterr()
        assert "# Plan: Root Plan" in captured.out
        # At depth 2, child bodies should also be loaded
        assert "Child A Content" in captured.out


# ============================================================================
# Load Context Recursive (direct)
# ============================================================================


class TestLoadContextRecursive:
    def test_recursive_loading(self, plan_hierarchy: Path) -> None:
        output: list[str] = []
        child_path = plan_hierarchy.parent / "children" / "child-a.md"
        remaining = pm.load_context_recursive(child_path, depth=1, budget=5000, output=output)
        assert remaining < 5000
        combined = "\n".join(output)
        assert "Child A Content" in combined

    def test_budget_exhausted(self, plan_hierarchy: Path) -> None:
        output: list[str] = []
        child_path = plan_hierarchy.parent / "children" / "child-a.md"
        remaining = pm.load_context_recursive(child_path, depth=1, budget=0, output=output)
        assert remaining == 0
        assert output == []

    def test_depth_zero(self, plan_hierarchy: Path) -> None:
        output: list[str] = []
        child_path = plan_hierarchy.parent / "children" / "child-a.md"
        remaining = pm.load_context_recursive(child_path, depth=0, budget=5000, output=output)
        assert remaining == 5000
        assert output == []


# ============================================================================
# Rebalance: early threshold break
# ============================================================================


class TestCmdRebalanceEdgeCases:
    def test_rebalance_stops_at_threshold(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Rebalance should stop extracting once below threshold."""
        # Create a doc with several sections, set threshold so only 1 needs extraction
        sections = []
        for i in range(3):
            content = f"Content for section {i}. " * 50
            sections.append(f"## Section {i}\n\n{content}")
        body = "\n\n".join(sections)
        post = frontmatter.Post(
            body,
            title="Multi",
            status="draft",
            children=[],
            token_estimate=0,
        )
        path = temp_dir / "multi.md"
        path.write_text(frontmatter.dumps(post), encoding="utf-8")

        # Set threshold very high so only one section needs extraction
        doc = pm.parse_plan(path)
        # Extract just enough to get under a threshold slightly below total
        threshold = doc.total_token_estimate - doc.sections[0].total_tokens + 10
        args = _make_args(
            command="rebalance",
            file=str(path),
            threshold=threshold,
            min_section=10,
            dry_run=False,
        )
        pm.cmd_rebalance(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["status"] == "rebalanced"
        # Should have extracted exactly 1 section
        assert len(result["extracted"]) == 1


# ============================================================================
# Update Summary: bidirectional propagation
# ============================================================================


class TestCmdUpdateSummaryPropagation:
    def test_propagate_from_root(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Bidirectional propagation from root: down to children, then update root."""
        args = _make_args(
            command="update-summary",
            file=str(plan_hierarchy),
            propagate=True,
        )
        pm.cmd_update_summary(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        # Propagation emits one JSON object per file updated (children first, root last).
        decoder = json.JSONDecoder()
        text = captured.out.strip()
        json_objects: list[dict[str, Any]] = []
        pos = 0
        while pos < len(text):
            obj, end = decoder.raw_decode(text, pos)
            json_objects.append(obj)
            pos = end
            while pos < len(text) and text[pos] in " \t\n\r":
                pos += 1
        # Should update children first (2), then root (1) = 3 total
        assert len(json_objects) == 3
        # All should have summaries
        for obj in json_objects:
            assert "summary" in obj
            assert "token_estimate" in obj

    def test_propagate_from_leaf(
        self, plan_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Propagation from a leaf (no children): just updates itself."""
        child_path = plan_hierarchy.parent / "children" / "child-a.md"
        args = _make_args(
            command="update-summary",
            file=str(child_path),
            propagate=True,
        )
        pm.cmd_update_summary(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        # Only one JSON object (the leaf itself)
        result = json.loads(captured.out)
        assert "summary" in result
        assert result["summary_changed"] is True

    def test_propagate_three_levels(
        self, three_level_hierarchy: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Bidirectional propagation across 3 levels: grandchild → child → root."""
        args = _make_args(
            command="update-summary",
            file=str(three_level_hierarchy),
            propagate=True,
        )
        pm.cmd_update_summary(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        decoder = json.JSONDecoder()
        text = captured.out.strip()
        json_objects: list[dict[str, Any]] = []
        pos = 0
        while pos < len(text):
            obj, end = decoder.raw_decode(text, pos)
            json_objects.append(obj)
            pos = end
            while pos < len(text) and text[pos] in " \t\n\r":
                pos += 1
        # Should update grandchild, child, root = 3 files
        assert len(json_objects) == 3
        # Timestamps should all be updated
        for obj in json_objects:
            assert "token_estimate" in obj

    def test_propagate_no_propagation(
        self, temp_dir: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Without --propagate, only the specified file is updated."""
        post = frontmatter.Post(
            "## Content\n\nBody text here.",
            title="Solo",
            summary="Old summary.",
            status="draft",
            parent=None,
            children=[],
        )
        path = temp_dir / "solo.md"
        path.write_text(frontmatter.dumps(post), encoding="utf-8")

        args = _make_args(
            command="update-summary",
            file=str(path),
            propagate=False,
        )
        pm.cmd_update_summary(args, summary_fn=pm.generate_summary_heuristic)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "summary" in result
        assert result["token_estimate"] > 0


# ============================================================================
# Summaries-Only Recursive Loading
# ============================================================================


class TestLoadSummariesRecursive:
    def test_loads_summaries(self, plan_hierarchy: Path) -> None:
        output: list[str] = []
        child_path = plan_hierarchy.parent / "children" / "child-a.md"
        remaining = pm._load_summaries_recursive(child_path, depth=0, budget=5000, output=output)
        assert remaining < 5000
        combined = "\n".join(output)
        assert "Child A" in combined

    def test_budget_respected(self, plan_hierarchy: Path) -> None:
        output: list[str] = []
        child_path = plan_hierarchy.parent / "children" / "child-a.md"
        pm._load_summaries_recursive(child_path, depth=0, budget=1, output=output)
        # Budget too small for summary, nothing added
        assert output == []


# ============================================================================
# Marko Parser Caching
# ============================================================================


class TestMarkoParserCaching:
    def test_parser_cached(self) -> None:
        p1 = pm.get_md_parser()
        p2 = pm.get_md_parser()
        assert p1 is p2

    def test_renderer_cached(self) -> None:
        r1 = pm.get_md_renderer()
        r2 = pm.get_md_renderer()
        assert r1 is r2


# ============================================================================
# CLI: build_parser and main
# ============================================================================


class TestCLI:
    def test_build_parser(self) -> None:
        parser = pm.build_parser()
        args = parser.parse_args(["analyze", "test.md", "-f", "json"])
        assert args.command == "analyze"
        assert args.file == "test.md"
        assert args.format == "json"

    def test_build_parser_all_commands(self) -> None:
        parser = pm.build_parser()
        # init
        args = parser.parse_args(["init", "f.md", "--title", "T"])
        assert args.command == "init"
        assert args.title == "T"
        # context
        args = parser.parse_args(["context", "f.md", "-d", "2", "--max-tokens", "1000"])
        assert args.command == "context"
        assert args.depth == 2
        assert args.max_tokens == 1000
        # context with --summaries-only
        args = parser.parse_args(["context", "f.md", "--summaries-only"])
        assert args.summaries_only is True
        # context with unlimited depth
        args = parser.parse_args(["context", "f.md", "-d", "-1"])
        assert args.depth == -1
        # rebalance
        args = parser.parse_args(["rebalance", "f.md", "--threshold", "500", "--dry-run"])
        assert args.command == "rebalance"
        assert args.threshold == 500
        assert args.dry_run is True
        # update-summary
        args = parser.parse_args(["update-summary", "f.md", "--propagate"])
        assert args.command == "update-summary"
        assert args.propagate is True

    def test_main_dispatches(self, sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = _make_args(command="analyze", file=str(sample_md), format="json")
        pm.main(args)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert "total_token_estimate" in result

    def test_main_verbose(self, sample_md: Path, capsys: pytest.CaptureFixture[str]) -> None:
        args = _make_args(command="analyze", file=str(sample_md), format="json", verbose=True)
        pm.main(args)
        captured = capsys.readouterr()
        result = json.loads(captured.out)
        assert result["total_token_estimate"] > 0


# ============================================================================
# Entry Point
# ============================================================================

if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    extra_args = sys.argv[1:]
    sys.exit(pytest.main(base_args + extra_args))
