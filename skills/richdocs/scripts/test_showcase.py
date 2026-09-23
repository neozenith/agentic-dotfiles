#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for showcase.py — real assets, real stencils, real substitution."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from pathlib import Path

import pytest

import md2html
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
    imports, _rest = showcase.split_imports(css)
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


def test_every_architecture_groups_its_nodes_without_overlap() -> None:
    """Group layout is validated at build time: known members, one group each, no overlap."""
    for arch in showcase.ARCHITECTURES:
        assert arch.groups, arch.title
        boxes = showcase.group_boxes(arch)
        assert set(boxes) == {g.id for g in arch.groups}


def test_overlapping_groups_crash_the_build() -> None:
    arch = showcase.Arch(
        title="x",
        caption="",
        nodes=[showcase.Node("a", "a", "i", 0, 0), showcase.Node("b", "b", "i", 1, 1)],
        edges=[],
        groups=[
            showcase.Group("g1", "one", ["a", "b"]),
            showcase.Group("g2", "two", ["b"]),
        ],
    )
    with pytest.raises(SystemExit, match="is in groups"):
        showcase.group_boxes(arch)
    arch = showcase.Arch(
        title="x",
        caption="",
        nodes=[
            showcase.Node("a", "a", "i", 0, 0),
            showcase.Node("b", "b", "i", 2, 2),
            showcase.Node("c", "c", "i", 1, 1),
        ],
        edges=[],
        groups=[
            showcase.Group("g1", "one", ["a", "b"]),
            showcase.Group("g2", "two", ["c"]),
        ],
    )
    with pytest.raises(SystemExit, match="overlap"):
        showcase.group_boxes(arch)


def test_groups_are_drawio_containers_in_category_colours() -> None:
    """Members are children of a real container, and each group takes the next slot."""
    stencils = showcase.load_stencils(showcase.DEFAULT_ZIP)
    arch = showcase.ARCHITECTURES[0]
    svg = showcase.compose_architecture_svg(arch, stencils)
    xml = showcase._drawio_xml(arch)
    for k, g in enumerate(arch.groups, start=1):
        assert f'id="{g.id}"' in xml
        assert f"strokeColor=var(--sc-cat-{k});" in xml
        assert f'stroke="var(--sc-cat-{k})"' in svg
        for m in g.members:
            assert f'id="{m}"' in xml
            assert f'parent="{g.id}"' in xml
    assert "container=1" in xml


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


def test_gallery_carries_the_oklch_palette_scene(tmp_path: Path) -> None:
    """The brand palette is shown in OKLCH, and redrawn with the other deck.gl scenes."""
    showcase.main(_args(tmp_path))
    html = (tmp_path / "showcase.html").read_text(encoding="utf-8")
    assert 'id="sc-oklch"' in html
    assert 'id="sc-oklch-readout"' in html
    js = showcase.SHOWCASE_JS.read_text(encoding="utf-8")
    start = js.index("function drawDeck()")
    draw_deck = js[start : js.index("\n}\n", start)]
    assert "renderOklch();" in draw_deck
    assert "targetChroma" in js


def _theme_with_lineage(tmp_path: Path, lineage: dict | None) -> md2html.Theme:
    tokens = tmp_path / "design-tokens.json"
    tokens.write_text("{}", encoding="utf-8")
    if lineage is not None:
        (tmp_path / "lineage.json").write_text(json.dumps(lineage), encoding="utf-8")
    return md2html.Theme(name="t", tokens_path=tokens, css="")


def test_lineage_is_optional(tmp_path: Path) -> None:
    """A hand-authored theme has no lineage; the payload says so rather than inventing one."""
    assert showcase._load_lineage(_theme_with_lineage(tmp_path, None)) is None


def test_lineage_is_carried_when_present(tmp_path: Path) -> None:
    lineage = {
        "sankeys": [
            {
                "title": "Seed → IR",
                "nodes": [{"id": "a", "label": "a"}, {"id": "b", "label": "b"}],
                "links": [{"source": "a", "target": "b"}],
            }
        ]
    }
    assert showcase._load_lineage(_theme_with_lineage(tmp_path, lineage)) == lineage


def test_lineage_link_to_an_unknown_node_crashes(tmp_path: Path) -> None:
    """A dangling link would silently drop a band in Plotly; fail the build instead."""
    lineage = {
        "sankeys": [
            {
                "title": "x",
                "nodes": [{"id": "a"}],
                "links": [{"source": "a", "target": "zz"}],
            }
        ]
    }
    with pytest.raises(SystemExit, match="unknown node"):
        showcase._load_lineage(_theme_with_lineage(tmp_path, lineage))


def test_gallery_carries_lineage_section_and_section_nav(tmp_path: Path) -> None:
    showcase.main(_args(tmp_path))
    html = (tmp_path / "showcase.html").read_text(encoding="utf-8")
    assert 'id="sc-lineage"' in html
    assert 'id="sc-nav"' in html
    assert 'aria-controls="sc-nav"' in html
    js = showcase.SHOWCASE_JS.read_text(encoding="utf-8")
    start = js.index("function render()")
    render = js[start : js.index("\n}\n", start)]
    assert "drawLineage();" in render
    # every storage access is guarded: a private window must not break the page
    storage = [ln for ln in js.splitlines() if "localStorage." in ln]
    assert storage
    assert all("try {" in ln for ln in storage), storage


def _theme_with_generator(
    tmp_path: Path, manifest: dict | None, source: str | None
) -> md2html.Theme:
    theme = _theme_with_lineage(tmp_path, None)
    if manifest is not None:
        (tmp_path / "generator.json").write_text(json.dumps(manifest), encoding="utf-8")
    if source is not None:
        (tmp_path / "generator.py").write_text(source, encoding="utf-8")
    return theme


GEN_MANIFEST = {
    "entry": "generate",
    "seed": {"hue": 1},
    "params": [{"key": "hue", "default": None}],
}


def test_generator_is_optional(tmp_path: Path) -> None:
    assert showcase._load_generator(_theme_with_generator(tmp_path, None, None)) is None


def test_generator_carries_manifest_and_source(tmp_path: Path) -> None:
    source = "def generate(seed):\n    return {'tokens': {}}\n"
    gen = showcase._load_generator(
        _theme_with_generator(tmp_path, GEN_MANIFEST, source)
    )
    assert gen == {"manifest": GEN_MANIFEST, "source": source}


def test_generator_manifest_without_its_module_crashes(tmp_path: Path) -> None:
    """A manifest promising live tuning with nothing to run must fail the build, not the page."""
    with pytest.raises(SystemExit, match="no generator.py"):
        showcase._load_generator(_theme_with_generator(tmp_path, GEN_MANIFEST, None))


def test_generator_manifest_missing_a_key_crashes(tmp_path: Path) -> None:
    with pytest.raises(SystemExit, match="missing 'params'"):
        showcase._load_generator(
            _theme_with_generator(
                tmp_path, {"entry": "generate", "seed": {}}, "x = 1\n"
            )
        )


def test_live_tuning_is_wired_and_lazy(tmp_path: Path) -> None:
    """Pyodide is pinned, loaded only on demand, and the panel follows the brand switch."""
    showcase.main(_args(tmp_path))
    html = (tmp_path / "showcase.html").read_text(encoding="utf-8")
    assert 'id="sc-tune"' in html
    assert "pyodide@" in html
    js = showcase.SHOWCASE_JS.read_text(encoding="utf-8")
    start = js.index("function setBrand(")
    set_brand = js[start : js.index("\n}\n", start)]
    assert "syncTune();" in set_brand
    assert 'loadScript("pyodide"' in js
    boot = js[js.index("// ── boot / re-render") :]
    assert "initPy(" not in boot  # never eager: ~10 MB only when a control changes


def test_build_parser_defaults() -> None:
    args = showcase.build_parser().parse_args([])
    assert args.theme is None
    assert args.out == str(showcase.DEFAULT_OUT)


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
