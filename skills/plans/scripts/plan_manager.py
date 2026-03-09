#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["marko>=2.2.2", "python-frontmatter>=1.1.0", "tiktoken>=0.9.0"]
# ///
"""
plan_manager - Hierarchical planning document manager for Claude Code.

Manages markdown planning documents with YAML frontmatter, token-budgeted
lazy loading, and automatic rebalancing when documents grow too large.

Subcommands:
    init            Add frontmatter metadata to an existing markdown document
    analyze         Parse a plan document and show section tree with token estimates
    context         Emit cascading context for a planning doc hierarchy
    rebalance       Split oversized documents into child files
    update-summary  Update frontmatter summary and token estimate

Usage:
    uv run plan_manager.py init plan.md
    uv run plan_manager.py analyze plan.md
    uv run plan_manager.py context plan.md --depth 2 --max-tokens 8000
    uv run plan_manager.py rebalance plan.md --threshold 4000
    uv run plan_manager.py update-summary plan.md --propagate
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import subprocess
import sys
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

import frontmatter
import marko
import tiktoken
from marko.md_renderer import MarkdownRenderer

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

log = logging.getLogger(__name__)

DEFAULT_TOKEN_THRESHOLD = 4_000
MIN_SECTION_TOKENS = 500

# Type alias for summary generation functions
SummaryFn = Callable[[str], str]

# Lazy-initialized tiktoken encoder
_encoder: tiktoken.Encoding | None = None


# ============================================================================
# Token Counting
# ============================================================================


def get_encoder() -> tiktoken.Encoding:
    """Return the shared tiktoken encoder (cl100k_base), initializing on first call."""
    global _encoder  # noqa: PLW0603
    if _encoder is None:
        _encoder = tiktoken.get_encoding("cl100k_base")
    return _encoder


def count_tokens(text: str) -> int:
    """Count tokens in text using tiktoken cl100k_base encoding."""
    if not text.strip():
        return 0
    return len(get_encoder().encode(text))


# ============================================================================
# Data Structures
# ============================================================================


@dataclass
class Section:
    """A heading-delimited section of a markdown document.

    Uses marko AST node indices rather than raw character offsets.
    This ensures headings inside code fences are never treated as sections.
    """

    heading: str
    level: int
    raw_text: str  # Own rendered content (heading + body until next heading)
    token_estimate: int
    node_start: int  # Index into parsed Document.children
    node_end: int  # Exclusive end index into Document.children (own content only)
    children: list[Section] = field(default_factory=list)
    parent: Section | None = field(default=None, repr=False)

    @property
    def total_tokens(self) -> int:
        """Total tokens including all descendant sections."""
        return self.token_estimate + sum(c.total_tokens for c in self.children)

    @property
    def full_node_end(self) -> int:
        """End node index including all descendant sections."""
        if self.children:
            return self.children[-1].full_node_end
        return self.node_end

    def full_text(self, parsed: marko.block.Document) -> str:
        """Render the full text of this section including all children from the AST."""
        return render_node_range(parsed, self.node_start, self.full_node_end)

    def walk(self) -> list[Section]:
        """Depth-first traversal of this section and all descendants."""
        result = [self]
        for child in self.children:
            result.extend(child.walk())
        return result


@dataclass
class PlanDocument:
    """A parsed planning document with frontmatter and section tree."""

    path: Path
    metadata: dict[str, Any]
    sections: list[Section]
    preamble: str  # Content before first heading
    body_raw: str  # Full body (no frontmatter)
    parsed: marko.block.Document = field(repr=False)  # Marko AST

    @property
    def total_token_estimate(self) -> int:
        """Total tokens across preamble and all sections."""
        preamble_tokens = count_tokens(self.preamble) if self.preamble else 0
        return preamble_tokens + sum(s.total_tokens for s in self.sections)

    def all_sections(self) -> list[Section]:
        """Flat list of all sections via depth-first traversal."""
        result: list[Section] = []
        for s in self.sections:
            result.extend(s.walk())
        return result


# ============================================================================
# Section Extraction (AST-based via marko)
# ============================================================================

_md_parser: marko.Markdown | None = None
_md_renderer: MarkdownRenderer | None = None


def get_md_parser() -> marko.Markdown:
    """Return the shared marko Markdown parser, initializing on first call."""
    global _md_parser  # noqa: PLW0603
    if _md_parser is None:
        _md_parser = marko.Markdown(renderer=MarkdownRenderer)
    return _md_parser


def get_md_renderer() -> MarkdownRenderer:
    """Return the shared MarkdownRenderer, initializing on first call."""
    global _md_renderer  # noqa: PLW0603
    if _md_renderer is None:
        _md_renderer = MarkdownRenderer()
    return _md_renderer


def render_node_range(parsed: marko.block.Document, start: int, end: int) -> str:
    """Render a contiguous range of AST children back to markdown."""
    renderer = get_md_renderer()
    temp = marko.block.Document()
    temp.children = list(parsed.children[start:end])
    result: str = renderer.render(temp)
    return result.rstrip("\n")


def extract_sections_ast(
    parsed: marko.block.Document,
) -> tuple[str, list[tuple[int, str, int, int]]]:
    """Extract heading-delimited sections from a marko AST.

    Uses the AST to identify headings, which correctly ignores headings
    inside fenced code blocks, blockquotes, and other container elements.

    Returns (preamble_text, [(level, heading_text, node_start, node_end), ...])
    where node_start/end are indices into parsed.children.
    """
    renderer = get_md_renderer()
    heading_indices: list[tuple[int, int, str]] = []

    for i, child in enumerate(parsed.children):
        if isinstance(child, marko.block.Heading):
            text = renderer.render_children(child).strip()
            heading_indices.append((i, child.level, text))

    if not heading_indices:
        preamble = render_node_range(parsed, 0, len(parsed.children))
        return preamble, []

    # Preamble is everything before the first heading
    first_heading_idx = heading_indices[0][0]
    preamble = render_node_range(parsed, 0, first_heading_idx) if first_heading_idx > 0 else ""

    sections: list[tuple[int, str, int, int]] = []
    for j, (node_idx, level, heading_text) in enumerate(heading_indices):
        # Section ends at the next heading's node index, or at the end of document
        if j + 1 < len(heading_indices):
            end_idx = heading_indices[j + 1][0]
        else:
            end_idx = len(parsed.children)
        sections.append((level, heading_text, node_idx, end_idx))

    return preamble, sections


def build_section_tree(
    parsed: marko.block.Document, flat_sections: list[tuple[int, str, int, int]]
) -> list[Section]:
    """Build hierarchical section tree from flat AST-based sections.

    Uses a stack-based algorithm: each heading pops the stack until finding
    a parent with a lower level number (higher in hierarchy), then becomes
    that parent's child.
    """
    stack: list[Section] = []
    root_sections: list[Section] = []

    for level, heading, node_start, node_end in flat_sections:
        raw_text = render_node_range(parsed, node_start, node_end)
        section = Section(
            heading=heading,
            level=level,
            raw_text=raw_text,
            token_estimate=count_tokens(raw_text),
            node_start=node_start,
            node_end=node_end,
        )

        # Pop stack until we find a parent with a strictly lower level number
        while stack and stack[-1].level >= level:
            stack.pop()

        if stack:
            stack[-1].children.append(section)
            section.parent = stack[-1]
        else:
            root_sections.append(section)

        stack.append(section)

    return root_sections


# ============================================================================
# Parsing
# ============================================================================


def parse_plan(filepath: Path) -> PlanDocument:
    """Parse a planning document into structured form with section tree.

    Uses the marko AST to identify sections, ensuring headings inside
    code fences are correctly ignored.
    """
    post = frontmatter.load(str(filepath))
    body = str(post.content)
    md = get_md_parser()
    parsed = md.parse(body)
    preamble, flat_sections = extract_sections_ast(parsed)
    sections = build_section_tree(parsed, flat_sections)

    return PlanDocument(
        path=filepath,
        metadata=dict(post.metadata),
        sections=sections,
        preamble=preamble,
        body_raw=body,
        parsed=parsed,
    )


def validate_markdown(body: str) -> bool:
    """Validate body as CommonMark using marko parser."""
    md = marko.Markdown(renderer=MarkdownRenderer)
    md.parse(body)
    return True


# ============================================================================
# Frontmatter Helpers
# ============================================================================


def make_frontmatter(
    title: str,
    summary: str = "",
    status: str = "draft",
    parent: str | None = None,
    children: list[str] | None = None,
    token_estimate: int = 0,
    tags: list[str] | None = None,
) -> dict[str, Any]:
    """Create a new frontmatter metadata dict with all required fields."""
    now = datetime.now(UTC).isoformat()
    meta: dict[str, Any] = {
        "id": str(uuid.uuid4()),
        "title": title,
        "summary": summary,
        "status": status,
        "parent": parent,
        "children": children or [],
        "token_estimate": token_estimate,
        "created": now,
        "updated": now,
        "tags": tags or [],
    }
    return meta


def update_frontmatter_fields(filepath: Path, updates: dict[str, Any]) -> None:
    """Update specific frontmatter fields on a file, preserving the body."""
    post = frontmatter.load(str(filepath))
    for key, value in updates.items():
        post[key] = value
    post["updated"] = datetime.now(UTC).isoformat()
    filepath.write_text(frontmatter.dumps(post), encoding="utf-8")


# ============================================================================
# Slugify
# ============================================================================


def slugify(text: str) -> str:
    """Convert text to a URL/filename-safe slug."""
    text = text.lower()
    text = re.sub(r"[^\w\s-]", "", text)
    text = re.sub(r"[-\s]+", "-", text).strip("-")
    return text


# ============================================================================
# Summary Generation
# ============================================================================


def generate_summary_heuristic(body: str, max_sentences: int = 3) -> str:
    """Extract first N meaningful sentences from body as a summary.

    Strips headings, code blocks, and blockquotes to find prose content,
    then takes the first max_sentences sentences.
    """
    # Remove headings
    text = re.sub(r"^#{1,6}\s+.+$", "", body, flags=re.MULTILINE)
    # Remove fenced code blocks
    text = re.sub(r"```[\s\S]*?```", "", text)
    # Remove blockquotes
    text = re.sub(r"^>\s+.*$", "", text, flags=re.MULTILINE)
    # Remove markdown links, keep display text
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)
    # Remove list markers
    text = re.sub(r"^[\s]*[-*+]\s+", "", text, flags=re.MULTILINE)
    # Collapse whitespace
    text = re.sub(r"\n{2,}", " ", text).strip()
    text = re.sub(r"\s+", " ", text)

    # Split into sentences
    sentences = re.split(r"(?<=[.!?])\s+", text)
    result: list[str] = []
    for s in sentences:
        s = s.strip()
        if s and len(s) > 15:
            result.append(s)
            if len(result) >= max_sentences:
                break
    return " ".join(result) if result else text[:200].strip()


def generate_summary_api(body: str) -> str:  # pragma: no cover
    """Generate summary using claude -p subprocess.

    Requires the Claude Code CLI to be installed and configured.
    """
    prompt = (
        "You are updating the summary metadata for a planning document section.\n"
        "Write a 2-4 sentence summary suitable for:\n"
        "- A developer scanning to decide if this section is relevant\n"
        "- An LLM agent deciding whether to load the full document into context\n\n"
        "Focus on: what this covers, its current status, and any blockers.\n"
        "Be dense and specific. No generic phrases.\n\n"
        f"Document body:\n{body}\n\n"
        "Return only the summary text, no preamble."
    )
    result = subprocess.run(
        ["claude", "-p", prompt],
        capture_output=True,
        text=True,
        timeout=60,
    )
    if result.returncode != 0:
        raise RuntimeError(f"claude -p failed (exit {result.returncode}): {result.stderr}")
    return result.stdout.strip()


# ============================================================================
# Command: init
# ============================================================================


def cmd_init(args: argparse.Namespace, summary_fn: SummaryFn | None = None) -> None:
    """Add or update frontmatter on a markdown file."""
    filepath = Path(args.file).resolve()
    if not filepath.exists():
        log.error("File not found: %s", filepath)
        sys.exit(1)

    post = frontmatter.load(str(filepath))
    body = str(post.content)
    existing_meta = dict(post.metadata)

    # Determine title using marko AST (safe from code fence false positives)
    title = getattr(args, "title", None)
    if not title:
        md = get_md_parser()
        parsed = md.parse(body)
        renderer = get_md_renderer()
        for child in parsed.children:
            if isinstance(child, marko.block.Heading):
                title = renderer.render_children(child).strip()
                break
        if not title:
            title = filepath.stem.replace("-", " ").replace("_", " ").title()

    # Generate summary if none exists (via claude -p API by default)
    if summary_fn is None:
        summary_fn = generate_summary_api
    summary = existing_meta.get("summary", "")
    if not summary:
        summary = summary_fn(body)

    # Calculate token estimate
    token_est = count_tokens(body)

    # Build metadata, preserving existing values
    meta = make_frontmatter(
        title=existing_meta.get("title", title),
        summary=str(existing_meta.get("summary", summary)),
        status=existing_meta.get("status", "draft"),
        parent=existing_meta.get("parent"),
        children=existing_meta.get("children", []),
        token_estimate=token_est,
        tags=existing_meta.get("tags", []),
    )
    # Preserve existing id and created timestamp
    if "id" in existing_meta:
        meta["id"] = existing_meta["id"]
    if "created" in existing_meta:
        meta["created"] = existing_meta["created"]

    # Write back
    new_post = frontmatter.Post(body, **meta)
    filepath.write_text(frontmatter.dumps(new_post), encoding="utf-8")

    log.info("Initialized frontmatter on %s (~%d tokens)", filepath.name, token_est)
    print(
        json.dumps(
            {
                "file": str(filepath),
                "token_estimate": token_est,
                "title": meta["title"],
            },
            indent=2,
        )
    )


# ============================================================================
# Command: analyze
# ============================================================================


def format_tree(sections: list[Section], indent: str = "") -> list[str]:
    """Format sections as a visual tree with box-drawing characters."""
    lines: list[str] = []
    for i, section in enumerate(sections):
        is_last = i == len(sections) - 1
        connector = "\u2514\u2500\u2500 " if is_last else "\u251c\u2500\u2500 "
        child_indent = indent + ("    " if is_last else "\u2502   ")

        hashes = "#" * section.level
        if section.children:
            tokens_str = f"~{section.total_tokens}"
        else:
            tokens_str = f"~{section.token_estimate}"
        lines.append(f"{indent}{connector}{hashes} {section.heading} ({tokens_str} tokens)")

        if section.children:
            lines.extend(format_tree(section.children, child_indent))

    return lines


def section_to_dict(section: Section) -> dict[str, Any]:
    """Convert a Section to a JSON-serializable dict."""
    d: dict[str, Any] = {
        "heading": section.heading,
        "level": section.level,
        "token_estimate": section.token_estimate,
        "total_tokens": section.total_tokens,
    }
    if section.children:
        d["children"] = [section_to_dict(c) for c in section.children]
    return d


def cmd_analyze(args: argparse.Namespace) -> None:
    """Parse and display section tree with token estimates."""
    filepath = Path(args.file).resolve()
    if not filepath.exists():
        log.error("File not found: %s", filepath)
        sys.exit(1)

    doc = parse_plan(filepath)

    if args.format == "json":
        result = {
            "file": str(doc.path),
            "total_token_estimate": doc.total_token_estimate,
            "metadata": doc.metadata,
            "preamble_tokens": count_tokens(doc.preamble) if doc.preamble else 0,
            "sections": [section_to_dict(s) for s in doc.sections],
        }
        print(json.dumps(result, indent=2, default=str))
    else:
        # Tree display
        title = doc.metadata.get("title", doc.path.name)
        status = doc.metadata.get("status", "unknown")
        print(f"Plan: {doc.path.name} (~{doc.total_token_estimate} tokens)")
        print(f"Title: {title} | Status: {status}")
        if doc.metadata.get("summary"):
            summary = str(doc.metadata["summary"])
            if len(summary) > 120:
                summary = summary[:117] + "..."
            print(f"Summary: {summary}")
        print()

        if doc.preamble:
            preamble_tokens = count_tokens(doc.preamble)
            print(f"  (preamble: ~{preamble_tokens} tokens)")

        tree_lines = format_tree(doc.sections)
        for line in tree_lines:
            print(f"  {line}")

        # Validation with marko
        valid = validate_markdown(doc.body_raw)
        print(f"\nCommonMark valid: {'yes' if valid else 'NO'}")


# ============================================================================
# Command: context
# ============================================================================


def load_frontmatter_only(filepath: Path) -> dict[str, Any]:
    """Load only the frontmatter metadata from a file."""
    post = frontmatter.load(str(filepath))
    return dict(post.metadata)


def load_body_only(filepath: Path) -> str:
    """Load only the body (no frontmatter) from a file."""
    post = frontmatter.load(str(filepath))
    return str(post.content)


def format_metadata_header(meta: dict[str, Any], filepath: Path) -> str:
    """Format a metadata block as the header of context output."""
    title = meta.get("title", filepath.stem)
    status = meta.get("status", "unknown")
    tokens = meta.get("token_estimate", "?")
    updated = meta.get("updated", "?")
    summary = meta.get("summary", "")

    lines = [
        f"# Plan: {title}",
        f"Status: {status} | Tokens: ~{tokens} | Updated: {updated}",
    ]
    if summary:
        lines.append("")
        lines.append(f"> {summary}")
    return "\n".join(lines)


def format_child_summary(meta: dict[str, Any], child_path: str) -> str:
    """Format a child's summary block for compact context injection."""
    title = meta.get("title", Path(child_path).stem)
    status = meta.get("status", "?")
    tokens = meta.get("token_estimate", "?")
    summary = meta.get("summary", "No summary available.")

    lines = [
        f"### [{title}]({child_path}) \u00b7 ~{tokens} tokens \u00b7 {status}",
        "",
        f"> {summary}",
    ]
    return "\n".join(lines)


def load_context_recursive(filepath: Path, depth: int, budget: int, output: list[str]) -> int:
    """Recursively load context from child documents. Returns remaining budget."""
    if (depth < 1 and depth != -1) or budget <= 0:
        return budget

    meta = load_frontmatter_only(filepath)
    body = load_body_only(filepath)
    body_tokens = count_tokens(body)

    if body_tokens <= budget:
        output.append(f"#### Full content: {meta.get('title', filepath.stem)}")
        output.append("")
        output.append(body)
        output.append("")
        budget -= body_tokens

    for child_rel in meta.get("children", []):
        child_path = (filepath.parent / child_rel).resolve()
        if child_path.exists() and budget > 0:
            child_meta = load_frontmatter_only(child_path)
            summary_block = format_child_summary(child_meta, child_rel)
            summary_tokens = count_tokens(summary_block)
            if summary_tokens <= budget:
                output.append(summary_block)
                budget -= summary_tokens

    return budget


def _load_summaries_recursive(
    filepath: Path, depth: int, budget: int, output: list[str], level: int = 0
) -> int:
    """Recursively load only frontmatter summaries. Returns remaining budget."""
    meta = load_frontmatter_only(filepath)
    summary_block = format_child_summary(meta, str(filepath.name))
    summary_tokens = count_tokens(summary_block)

    if summary_tokens <= budget:
        indent = "  " * level
        # Re-format with indent for tree-like display
        output.append(f"{indent}{summary_block}")
        output.append("")
        budget -= summary_tokens

    if depth != 0 and budget > 0:
        next_depth = depth - 1 if depth > 0 else -1  # -1 stays -1 (unlimited)
        for child_rel in meta.get("children", []):
            child_path = (filepath.parent / child_rel).resolve()
            if child_path.exists() and budget > 0:
                budget = _load_summaries_recursive(
                    child_path, next_depth, budget, output, level + 1
                )

    return budget


def cmd_context(args: argparse.Namespace) -> None:
    """Emit cascading context for a planning doc hierarchy."""
    root_path = Path(args.file).resolve()
    if not root_path.exists():
        log.error("File not found: %s", root_path)
        sys.exit(1)

    depth = args.depth
    max_tokens = args.max_tokens
    budget = max_tokens
    summaries_only = args.summaries_only
    output: list[str] = []

    # Always load root frontmatter
    root_meta = load_frontmatter_only(root_path)
    header = format_metadata_header(root_meta, root_path)
    header_tokens = count_tokens(header)
    output.append(header)
    budget -= header_tokens

    if summaries_only:
        # Summaries-only mode: just frontmatter summaries at each level
        children = root_meta.get("children", [])
        if children:
            output.append("")
            output.append("## Children")
            output.append("")
        effective_depth = depth - 1 if depth > 0 else depth  # -1 stays unlimited
        for child_rel in children:
            child_path = (root_path.parent / child_rel).resolve()
            if child_path.exists() and budget > 0:
                budget = _load_summaries_recursive(child_path, effective_depth, budget, output)
            elif not child_path.exists():
                output.append(f"- [{child_rel}]({child_rel}) \u2014 **FILE NOT FOUND**")
    elif (depth >= 1 or depth == -1) and budget > 0:
        # Full context loading mode
        root_body = load_body_only(root_path)
        body_tokens = count_tokens(root_body)
        if body_tokens <= budget:
            output.append("")
            output.append("---")
            output.append("")
            output.append(root_body)
            budget -= body_tokens
        else:
            output.append("")
            output.append(f"(body too large: ~{body_tokens} tokens, budget remaining: ~{budget})")

        # Load child summaries
        children = root_meta.get("children", [])
        if children:
            output.append("")
            output.append("---")
            output.append("## Children")
            output.append("")

        for child_rel in children:
            child_path = (root_path.parent / child_rel).resolve()
            if not child_path.exists():
                output.append(f"- [{child_rel}]({child_rel}) \u2014 **FILE NOT FOUND**")
                continue

            child_meta = load_frontmatter_only(child_path)
            summary_block = format_child_summary(child_meta, child_rel)
            summary_tokens = count_tokens(summary_block)

            if summary_tokens <= budget:
                output.append(summary_block)
                output.append("")
                budget -= summary_tokens

            # Recurse if depth >= 2 or unlimited (-1)
            if (depth >= 2 or depth == -1) and budget > 0:
                next_depth = depth - 1 if depth > 0 else -1
                budget = load_context_recursive(child_path, next_depth, budget, output)

    print("\n".join(output))


# ============================================================================
# Command: rebalance
# ============================================================================


def derive_child_path(parent_path: Path, heading: str, create_dir: bool = True) -> Path:
    """Derive child file path from parent path and heading text.

    Creates a subdirectory named after the parent file stem,
    with the child named after the slugified heading.
    Set create_dir=False for dry-run / preview operations.
    """
    stem = slugify(heading)
    child_dir = parent_path.parent / parent_path.stem
    if create_dir:
        child_dir.mkdir(parents=True, exist_ok=True)
    return child_dir / f"{stem}.md"


def cmd_rebalance(args: argparse.Namespace, summary_fn: SummaryFn | None = None) -> None:
    """Split oversized documents into child files."""
    if summary_fn is None:
        summary_fn = generate_summary_api
    filepath = Path(args.file).resolve()
    if not filepath.exists():
        log.error("File not found: %s", filepath)
        sys.exit(1)

    threshold = args.threshold
    min_section = args.min_section
    dry_run = args.dry_run

    doc = parse_plan(filepath)

    if doc.total_token_estimate <= threshold:
        log.info(
            "Document within budget (~%d <= %d tokens)",
            doc.total_token_estimate,
            threshold,
        )
        print(
            json.dumps(
                {
                    "status": "within_budget",
                    "total_tokens": doc.total_token_estimate,
                    "extracted": [],
                }
            )
        )
        return

    # Find candidate sections (top-level only for simplicity)
    candidates = [s for s in doc.sections if s.total_tokens >= min_section]
    candidates.sort(key=lambda s: s.total_tokens, reverse=True)

    if not candidates:
        log.warning("No sections large enough to extract (min: %d tokens)", min_section)
        print(
            json.dumps(
                {
                    "status": "no_candidates",
                    "total_tokens": doc.total_token_estimate,
                }
            )
        )
        return

    # Phase 1: Determine which sections to extract
    remaining_tokens = doc.total_token_estimate
    to_extract: list[Section] = []
    for section in candidates:
        if remaining_tokens <= threshold:
            break
        to_extract.append(section)
        remaining_tokens -= section.total_tokens

    extracted: list[dict[str, Any]] = []
    children_paths: list[str] = list(doc.metadata.get("children", []))

    if dry_run:
        for section in to_extract:
            extracted.append(
                {
                    "heading": section.heading,
                    "tokens": section.total_tokens,
                    "would_create": str(
                        derive_child_path(filepath, section.heading, create_dir=False)
                    ),
                }
            )
        print(
            json.dumps(
                {
                    "status": "dry_run",
                    "original_tokens": doc.total_token_estimate,
                    "remaining_tokens": remaining_tokens,
                    "extracted": extracted,
                },
                indent=2,
            )
        )
        return

    # Phase 2: Extract sections using AST node ranges.
    # Sort by node_start descending so back-to-front removal preserves indices.
    to_extract.sort(key=lambda s: s.node_start, reverse=True)

    for section in to_extract:
        child_path = derive_child_path(filepath, section.heading)
        child_rel = str(child_path.relative_to(filepath.parent))

        # Render full section subtree via AST (preserves code fences correctly)
        full_section_text = section.full_text(doc.parsed)

        # Generate summary
        summary = summary_fn(full_section_text)

        # Calculate tokens
        section_tokens = count_tokens(full_section_text)

        # Create child file with frontmatter
        child_meta = make_frontmatter(
            title=section.heading,
            summary=summary,
            parent=str(filepath.name),
            token_estimate=section_tokens,
        )
        child_post = frontmatter.Post(full_section_text, **child_meta)
        child_path.write_text(frontmatter.dumps(child_post), encoding="utf-8")

        # Validate the child file is valid CommonMark
        validate_markdown(full_section_text)

        # Replace the section's AST nodes with a summary+link placeholder.
        # Build replacement markdown and parse it into AST nodes.
        replacement_md = (
            f"## {section.heading}\n\n> **Summary:** {summary}\n> See: [{child_rel}]({child_rel})\n"
        )
        md = get_md_parser()
        replacement_parsed = md.parse(replacement_md)
        replacement_nodes = list(replacement_parsed.children)

        # Splice: remove section nodes, insert replacement nodes
        start = section.node_start
        end = section.full_node_end
        doc.parsed.children[start:end] = replacement_nodes

        children_paths.append(child_rel)
        extracted.append(
            {
                "heading": section.heading,
                "tokens": section_tokens,
                "created": str(child_path),
            }
        )
        log.info(
            "Extracted '%s' (~%d tokens) -> %s",
            section.heading,
            section_tokens,
            child_path,
        )

    # Render the modified AST back to markdown for the parent file
    renderer = get_md_renderer()
    new_body = renderer.render(doc.parsed).rstrip("\n")

    # Validate the parent file is valid CommonMark
    validate_markdown(new_body)

    # Update parent file
    parent_post = frontmatter.Post(new_body, **doc.metadata)
    parent_post["children"] = children_paths
    parent_post["token_estimate"] = count_tokens(new_body)
    parent_post["updated"] = datetime.now(UTC).isoformat()
    filepath.write_text(frontmatter.dumps(parent_post), encoding="utf-8")

    print(
        json.dumps(
            {
                "status": "rebalanced",
                "original_tokens": doc.total_token_estimate,
                "remaining_tokens": count_tokens(new_body),
                "extracted": extracted,
            },
            indent=2,
        )
    )


# ============================================================================
# Command: update-summary
# ============================================================================


def _update_single_summary(filepath: Path, summary_fn: SummaryFn | None = None) -> dict[str, Any]:
    """Update the summary and token_estimate on a single file. Returns result dict."""
    if summary_fn is None:
        summary_fn = generate_summary_api
    post = frontmatter.load(str(filepath))
    body = str(post.content)

    new_summary = summary_fn(body)

    old_summary = post.metadata.get("summary", "")
    new_token_estimate = count_tokens(body)

    # Update frontmatter
    post["summary"] = new_summary
    post["token_estimate"] = new_token_estimate
    post["updated"] = datetime.now(UTC).isoformat()
    filepath.write_text(frontmatter.dumps(post), encoding="utf-8")

    summary_changed = old_summary != new_summary

    log.info(
        "Updated %s: summary %s, ~%d tokens",
        filepath.name,
        "changed" if summary_changed else "unchanged",
        new_token_estimate,
    )

    return {
        "file": str(filepath),
        "summary": new_summary,
        "token_estimate": new_token_estimate,
        "summary_changed": summary_changed,
    }


def _propagate_tree(
    filepath: Path, results: list[dict[str, Any]], summary_fn: SummaryFn | None = None
) -> None:
    """Bidirectional propagation: depth-first DOWN to leaves, then update self.

    Phase 1: Recurse into each child (depth-first) so leaf summaries are fresh.
    Phase 2: Update own summary (which now incorporates updated child summaries).
    """
    post = frontmatter.load(str(filepath))
    children = post.metadata.get("children", [])

    # Phase 1: recurse DOWN into children first
    for child_rel in children:
        child_path = (filepath.parent / child_rel).resolve()
        if child_path.exists():
            log.info("Propagating down to child: %s", child_path)
            _propagate_tree(child_path, results, summary_fn)
        else:
            log.warning("Child file not found: %s", child_path)

    # Phase 2: update own summary (children are now fresh)
    result = _update_single_summary(filepath, summary_fn)
    results.append(result)


def cmd_update_summary(args: argparse.Namespace, summary_fn: SummaryFn | None = None) -> None:
    """Update frontmatter summary and token estimate on a plan file."""
    filepath = Path(args.file).resolve()
    if not filepath.exists():
        log.error("File not found: %s", filepath)
        sys.exit(1)

    if args.propagate:
        # Bidirectional propagation: down to leaves, then back up
        results: list[dict[str, Any]] = []
        _propagate_tree(filepath, results, summary_fn)
        for r in results:
            print(json.dumps(r, indent=2))
    else:
        # Single file update
        result = _update_single_summary(filepath, summary_fn)
        print(json.dumps(result, indent=2))


# ============================================================================
# CLI Interface
# ============================================================================


def build_parser() -> argparse.ArgumentParser:
    """Build the argument parser with all subcommands."""
    parser = argparse.ArgumentParser(
        prog="plan_manager",
        description="Hierarchical planning document manager for Claude Code.",
    )
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    subparsers = parser.add_subparsers(dest="command", required=True)

    # init
    p_init = subparsers.add_parser("init", help="Add frontmatter to a markdown file")
    p_init.add_argument("file", help="Path to markdown file")
    p_init.add_argument(
        "--title",
        help="Document title (auto-detected from first heading if omitted)",
    )

    # analyze
    p_analyze = subparsers.add_parser("analyze", help="Show section tree with token estimates")
    p_analyze.add_argument("file", help="Path to markdown file")
    p_analyze.add_argument(
        "-f",
        "--format",
        choices=["tree", "json"],
        default="tree",
        help="Output format (default: tree)",
    )

    # context
    p_context = subparsers.add_parser(
        "context",
        help="Emit cascading context for a plan hierarchy",
        epilog=(
            "Depth controls how much of the hierarchy to load:\n"
            "  0  = Root metadata only (~100-200 tokens)\n"
            "  1  = Root body + child summaries (default)\n"
            "  2+ = Recursively load child bodies + grandchild summaries\n"
            "  -1 = Unlimited depth (load entire tree)\n\n"
            "The --max-tokens budget caps total output. The loader stops\n"
            "adding content when the budget would be exceeded.\n\n"
            "Use --summaries-only to emit only frontmatter summaries\n"
            "(no document bodies) — useful for quick tree inspection."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_context.add_argument("file", help="Path to root plan file")
    p_context.add_argument(
        "-d",
        "--depth",
        type=int,
        default=1,
        help="Loading depth (0=metadata, 1=body+children, -1=all)",
    )
    p_context.add_argument(
        "--max-tokens", type=int, default=8000, help="Token budget (default: 8000)"
    )
    p_context.add_argument(
        "--summaries-only",
        action="store_true",
        help="Emit only frontmatter summaries, no document bodies",
    )

    # rebalance
    p_rebalance = subparsers.add_parser("rebalance", help="Split oversized documents into children")
    p_rebalance.add_argument("file", help="Path to markdown file")
    p_rebalance.add_argument(
        "--threshold",
        type=int,
        default=DEFAULT_TOKEN_THRESHOLD,
        help=f"Token threshold (default: {DEFAULT_TOKEN_THRESHOLD})",
    )
    p_rebalance.add_argument(
        "--min-section",
        type=int,
        default=MIN_SECTION_TOKENS,
        help=f"Min section size to extract (default: {MIN_SECTION_TOKENS})",
    )
    p_rebalance.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be extracted without doing it",
    )

    # update-summary
    p_summary = subparsers.add_parser(
        "update-summary",
        help="Update frontmatter summary and token estimate",
        epilog=(
            "Generates summaries via `claude -p` (requires Claude Code CLI).\n\n"
            "With --propagate, performs bidirectional tree traversal:\n"
            "  1. Recurse DOWN to all leaf children first\n"
            "  2. Update each file's summary (leaves first)\n"
            "  3. Bubble UP so parent summaries reflect updated children\n\n"
            "Without --propagate, updates only the specified file."
        ),
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    p_summary.add_argument("file", help="Path to markdown file")
    p_summary.add_argument(
        "--propagate",
        action="store_true",
        help="Bidirectional propagation: update all children, then bubble up",
    )

    return parser


def main(args: argparse.Namespace) -> None:
    """Main entry point — dispatches to subcommand handlers."""
    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(levelname)s: %(message)s",
        stream=sys.stderr,
    )

    commands: dict[str, Any] = {
        "init": cmd_init,
        "analyze": cmd_analyze,
        "context": cmd_context,
        "rebalance": cmd_rebalance,
        "update-summary": cmd_update_summary,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args)
    else:
        log.error("Unknown command: %s", args.command)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    parser = build_parser()
    main(parser.parse_args())
