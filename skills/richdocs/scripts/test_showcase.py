#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for showcase.py — real assets, real stencils, real substitution."""

from __future__ import annotations

import sys
from argparse import Namespace
from pathlib import Path

import md2html
import pytest
import showcase


def _args(out: Path, theme: str | None = None) -> Namespace:
    return Namespace(out=str(out), theme=theme)


# ── CSS scoping ─────────────────────────────────────────────────────────────
def test_split_imports_hoists_only_imports() -> None:
    css = "@import url('a.css');\nmain h1 { color: red; }\n@import url('b.css');"
    imports, rest = showcase.split_imports(css)
    assert imports.count("@import") == 2
    assert "@import" not in rest
    assert "main h1" in rest


def test_split_imports_survives_semicolons_inside_the_url() -> None:
    """REGRESSION: a Google Fonts URL carries semicolons in its weight list.

    `@import[^;]+;` truncated at the FIRST semicolon inside the URL, emitting a
    broken rule. No webfont loaded; the page fell back to a generic serif — which
    looks like the real face at a glance, so it survived review.
    """
    url = (
        "https://fonts.googleapis.com/css2"
        "?family=Fraunces:opsz,wght@9..144,400;9..144,700"
        "&family=Fira+Sans:wght@400;700&display=swap"
    )
    imports, rest = showcase.split_imports(f"@import url('{url}');\np {{ margin: 0; }}")
    assert url in imports  # the WHOLE url, not a prefix
    assert imports.rstrip().endswith(");")
    assert "@import" not in rest


def test_split_imports_ignores_the_word_import_inside_a_comment() -> None:
    """REGRESSION: the word "@import" in theme.css prose was matched and hoisted,
    producing a stylesheet made of English."""
    css = "/* This file must @import the webfiles. */\n@import url('real.css');\np { margin: 0; }"
    imports, rest = showcase.split_imports(css)
    assert imports.count("@import") == 1
    assert "webfiles" not in imports
    assert "real.css" in imports


def test_every_theme_import_is_a_complete_rule() -> None:
    """The gate: a truncated @import silently kills every webfont in the brand."""
    for name in md2html.available_themes():
        theme = md2html.load_theme(name)
        imports, _ = showcase.split_imports(theme.css)
        if not imports:
            continue
        for line in imports.splitlines():
            assert line.startswith("@import url("), line
            assert line.rstrip().endswith(");"), f"{name}: truncated @import -> {line}"


def test_scope_css_confines_a_brand_to_its_own_scope() -> None:
    scoped = showcase.scope_css("main h1 { color: red; }\np, li { margin: 0; }", "acme")
    assert ':root[data-brand="acme"] main h1' in scoped
    # every selector in a comma list gets scoped, not just the first
    assert ':root[data-brand="acme"] p' in scoped
    assert ':root[data-brand="acme"] li' in scoped


def test_scope_css_anchors_root_to_the_scope_itself() -> None:
    """`:root { --x: 1 }` must land ON the scope, not on a descendant of it."""
    scoped = showcase.scope_css(":root { --x: 1px; }", "acme")
    assert ':root[data-brand="acme"] { --x: 1px; }' in scoped
    assert ':root[data-brand="acme"] :root' not in scoped


def test_scope_css_drops_comments() -> None:
    assert "secret" not in showcase.scope_css("/* secret */ p { margin: 0; }", "a")


# ── Stencil architecture ────────────────────────────────────────────────────
def test_every_referenced_stencil_exists() -> None:
    """A typo'd stencil id must fail the BUILD, not render an empty box."""
    stencils = showcase.load_stencils(showcase.DEFAULT_ZIP)
    for arch in showcase.ARCHITECTURES:
        for node in arch.nodes:
            assert node.icon in stencils, node.icon


def test_unknown_stencil_crashes_the_build() -> None:
    stencils = showcase.load_stencils(showcase.DEFAULT_ZIP)
    bad = showcase.Arch(
        title="x",
        caption="",
        nodes=[showcase.Node("n", "n", "nope/nope", 0, 0)],
        edges=[],
    )
    with pytest.raises(SystemExit, match="stencil not found"):
        showcase.compose_architecture_svg(bad, stencils)


def test_architecture_svg_is_drawio_editable() -> None:
    stencils = showcase.load_stencils(showcase.DEFAULT_ZIP)
    by_title = {a.title: a for a in showcase.ARCHITECTURES}
    aws = next(
        a for a in showcase.ARCHITECTURES if a.nodes[0].icon.startswith("mxgraph.aws4/")
    )
    gcp = next(
        a for a in showcase.ARCHITECTURES if a.nodes[0].icon.startswith("mxgraph.gcp2/")
    )

    aws_svg = showcase.compose_architecture_svg(aws, stencils)
    assert aws_svg.startswith("<svg")
    # drawio re-opens a diagram from the `content` attribute; without it the SVG
    # is a flat picture and the "editable" claim is a lie.
    assert "content=" in aws_svg
    assert "&lt;mxfile" in aws_svg or "<mxfile" in aws_svg
    assert "mxgraph.aws4.resourceIcon" in aws_svg  # real AWS shapes, not images
    assert "resIcon=mxgraph.aws4." in aws_svg

    # GCP stencils round-trip as their OWN provider shape, not an AWS resourceIcon.
    gcp_svg = showcase.compose_architecture_svg(gcp, stencils)
    assert "shape=mxgraph.gcp2." in gcp_svg
    assert "resIcon=mxgraph.gcp2" not in gcp_svg  # never an AWS wrapper on a GCP icon
    assert by_title  # both diagrams present and titled


# ── Assembly ────────────────────────────────────────────────────────────────
def test_gallery_embeds_every_installed_brand(tmp_path: Path) -> None:
    showcase.main(_args(tmp_path))
    html = (tmp_path / "showcase.html").read_text(encoding="utf-8")
    assert "{{" not in html
    assert "var SC_SINGLE = false;" in html
    for name in md2html.available_themes():
        assert f'"name": "{name}"' in html
        assert f':root[data-brand="{name}"]' in html


def test_single_theme_artifact_contains_no_other_brand(tmp_path: Path) -> None:
    """--theme means that brand ALONE: no switcher, no other brand's tokens or CSS."""
    names = md2html.available_themes()
    assert len(names) >= 2, "need >=2 themes to prove isolation"
    mine, other = names[0], names[1]

    showcase.main(_args(tmp_path, theme=mine))
    html = (tmp_path / f"showcase-{mine}.html").read_text(encoding="utf-8")
    assert "var SC_SINGLE = true;" in html
    assert f'"name": "{mine}"' in html
    assert other not in html


def test_unknown_theme_crashes_loudly(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="unknown theme"):
        showcase.main(_args(tmp_path, theme="nope"))


def test_showcase_js_has_no_template_placeholders() -> None:
    """ADR-008 applies to the showcase assets too."""
    assert "{{" not in showcase.SHOWCASE_JS.read_text(encoding="utf-8")
    assert "{{" not in showcase.SHOWCASE_CSS.read_text(encoding="utf-8")


def test_build_parser_defaults() -> None:
    args = showcase.build_parser().parse_args([])
    assert args.theme is None
    assert args.out == str(showcase.DEFAULT_OUT)


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
