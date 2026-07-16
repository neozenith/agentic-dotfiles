#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = ["pytest>=8.0", "pytest-cov>=4.0"]
# ///
"""Tests for md2html.py — real files, real template string ops."""

from __future__ import annotations

import json
import sys
from argparse import Namespace
from datetime import UTC, datetime
from pathlib import Path

import md2html
import pytest

DOC_MD = "# Title\n\nSome `</script>` text.\n\n```mermaid\ngraph LR; a-->b\n```\n"


@pytest.fixture
def doc(tmp_path: Path) -> Path:
    path = tmp_path / "mydoc.md"
    path.write_text(DOC_MD, encoding="utf-8")
    return path


def _args(doc: Path, out: Path, **overrides: object) -> Namespace:
    base: dict[str, object] = {
        "doc": str(doc),
        "out": str(out),
        "inline": False,
        "tokens": str(md2html.DEFAULT_TOKENS),
        "title": None,
        "serve_hint": False,
        "theme": None,
    }
    base.update(overrides)
    return Namespace(**base)


# ── Pure helpers ────────────────────────────────────────────────────────────
def test_make_build_id_format() -> None:
    fixed = datetime(2026, 7, 7, 3, 15, 0, tzinfo=UTC)
    assert md2html.make_build_id(fixed) == "20260707T031500Z"
    assert len(md2html.make_build_id()) == 16


def test_viewer_js_has_no_template_placeholders() -> None:
    """ADR-008: viewer.js must stay real, lintable JS. A `{{...}}` breaks parsing."""
    js = md2html.VIEWER_JS.read_text(encoding="utf-8")
    assert "{{" not in js
    assert 'document.getElementById("rd-config")' in js


def test_viewer_deckgl_js_has_no_template_placeholders() -> None:
    """ADR-008 applies to every hoisted renderer, not just viewer.js."""
    js = md2html.VIEWER_DECKGL_JS.read_text(encoding="utf-8")
    assert "{{" not in js
    assert "function rdRenderDeckGL(" in js


def test_build_config_carries_everything_the_viewer_needs() -> None:
    cfg = md2html.build_config(build_id="B1", source="doc.md")
    assert cfg["buildId"] == "B1"
    assert cfg["source"] == "doc.md"
    assert set(cfg["cdn"]) == {
        "cytoscape",
        "dagre",
        "cytoscapeDagre",
        "plotly",
        "deckgl",
        "maplibre",
        "maplibreCss",
        "duckdb",
    }
    assert cfg["fallbackTokens"] == md2html.FALLBACK_TOKENS


def test_deckgl_renderer_is_inlined_and_hoisted_before_viewer_js() -> None:
    """rdRenderDeckGL is called by viewer.js, so it must be DEFINED earlier in the page."""
    html = md2html.build_multi_html(build_id="B", title="T", source="doc.md")
    assert "function rdRenderDeckGL(" in html
    assert html.index("function rdRenderDeckGL(") < html.index(
        'JSON.parse(document.getElementById("rd-config")'
    )


def test_embed_json_escapes_script_close() -> None:
    embedded = md2html._embed_json("x</script><script>alert(1)")
    assert "</script" not in embedded
    assert "<\\/script" in embedded


def test_build_multi_html_has_no_unresolved_tokens() -> None:
    html = md2html.build_multi_html(build_id="B", title="T", source="doc.md")
    assert "{{" not in html
    assert '"source": "doc.md"' in html  # now arrives via the #rd-config block
    assert "__DOC_MD__ =" not in html
    for url in md2html.CDN.values():
        assert url in html


@pytest.mark.parametrize(
    ("tokens", "expected"),
    [
        ({"defaultTheme": "dark"}, "dark"),
        ({"defaultTheme": "light"}, "light"),
        ({"defaultTheme": "midnight"}, ""),  # invalid -> fall through
        ({}, ""),  # unset -> prefers-color-scheme
        (None, ""),
    ],
)
def test_resolve_default_theme(tokens: dict[str, object] | None, expected: str) -> None:
    assert md2html.resolve_default_theme(tokens) == expected


def test_default_theme_is_baked_into_the_pre_paint_script() -> None:
    """A brandpack may pin the initial theme; it must land before first paint."""
    html = md2html.build_multi_html(
        build_id="B", title="T", source="doc.md", default_theme="dark"
    )
    assert 't = "dark";' in html
    assert "{{DEFAULT_THEME}}" not in html

    # Unset leaves the placeholder empty, so the prefers-color-scheme branch runs.
    plain = md2html.build_multi_html(build_id="B", title="T", source="doc.md")
    assert 't = "";' in plain
    assert "prefers-color-scheme" in plain


def test_build_inline_html_embeds_doc_and_tokens() -> None:
    tokens = {"themes": {"light": {}}, "note": "</script>"}
    html = md2html.build_inline_html(
        "hello </script> world", tokens, build_id="B", title="T", source="s.md"
    )
    assert "window.__DOC_MD__ = " in html
    assert "window.__DOC_TOKENS__ = " in html
    assert "hello <\\/script> world" in html
    # No raw </script> from embedded payloads may appear before the real closer.
    assert html.count("</script>") == html.count("<script")


def test_fallback_tokens_are_the_default_brandpack() -> None:
    """ADR-008 retires the ADR-004 hand-sync hazard: one source, not two copies."""
    asset = json.loads(md2html.DEFAULT_TOKENS.read_text(encoding="utf-8"))
    assert md2html.FALLBACK_TOKENS == asset
    assert {"fonts", "themes", "canvas"} <= set(md2html.FALLBACK_TOKENS)


def test_assembled_html_inlines_every_asset() -> None:
    html = md2html.build_multi_html(build_id="B", title="T", source="doc.md")
    assert md2html.VIEWER_CSS.read_text(encoding="utf-8") in html
    assert md2html.VIEWER_JS.read_text(encoding="utf-8") in html
    assert md2html.VIEWER_CYTOSCAPE_JS.read_text(encoding="utf-8") in html
    assert '<script type="application/json" id="rd-config">' in html


def test_viewer_cytoscape_js_has_no_template_placeholders() -> None:
    """ADR-008 applies to every asset, not just viewer.js."""
    js = md2html.VIEWER_CYTOSCAPE_JS.read_text(encoding="utf-8")
    assert "{{" not in js
    assert "function rdRenderCytoscape(" in js


# ── Named themes ────────────────────────────────────────────────────────────
def test_available_themes_finds_the_installed_brandpacks() -> None:
    themes = md2html.available_themes()
    assert "osakanights" in themes
    for name in themes:
        assert (md2html.THEMES_DIR / name / "design-tokens.json").is_file()


def test_load_theme_returns_tokens_and_css() -> None:
    theme = md2html.load_theme("osakanights")
    assert theme.name == "osakanights"
    assert theme.tokens_path.is_file()
    assert "Fraunces" in theme.css  # theme.css is what actually loads the webfont


def test_installed_brandpacks_declare_a_display_face() -> None:
    """A typeface is a brand value; it belongs in the pack, not only in CSS."""
    for name in md2html.available_themes():
        tokens = json.loads(
            md2html.load_theme(name).tokens_path.read_text(encoding="utf-8")
        )
        assert "display" in tokens["fonts"], f"{name} has no fonts.display"


def test_themes_are_real_files_not_symlinks() -> None:
    """The skill must be portable: copy .claude/ anywhere and themes still resolve.

    A symlink out to a project directory is a co-dependency, not a theme.
    """
    for name in md2html.available_themes():
        pack = md2html.THEMES_DIR / name / "design-tokens.json"
        assert not pack.is_symlink(), f"{name} brandpack is a symlink"
        css = md2html.THEMES_DIR / name / "theme.css"
        assert not css.is_symlink(), f"{name} theme.css is a symlink"


def test_two_themed_docs_in_one_dir_keep_their_own_brand(tmp_path: Path) -> None:
    """REGRESSION: a shared design-tokens.json let one doc clobber another's brand.

    Rendering doc B with --theme v2ai overwrote the pack that doc A (--theme
    osakanights) fetches at runtime, so BOTH pages loaded V2's palette and fonts.
    The brandpack is now paired with the doc, like the markdown already was.
    """
    out = tmp_path / "out"
    for stem, theme in [("alpha", "osakanights"), ("beta", "v2ai")]:
        src = tmp_path / f"{stem}.md"
        src.write_text(f"# {stem}\n", encoding="utf-8")
        md2html.main(_args(src, out, theme=theme))

    alpha = json.loads((out / "alpha.tokens.json").read_text(encoding="utf-8"))
    beta = json.loads((out / "beta.tokens.json").read_text(encoding="utf-8"))
    assert "Fraunces" in alpha["fonts"]["display"]
    assert "Outfit" in beta["fonts"]["display"]

    # and each page must fetch ITS OWN pack, not a shared filename
    assert '"tokensSource": "alpha.tokens.json"' in (out / "alpha.html").read_text(
        encoding="utf-8"
    )
    assert '"tokensSource": "beta.tokens.json"' in (out / "beta.html").read_text(
        encoding="utf-8"
    )


def test_load_theme_unknown_name_crashes_loudly() -> None:
    """escalators-not-stairs: a typo'd theme must fail, never silently fall back."""
    with pytest.raises(SystemExit) as excinfo:
        md2html.load_theme("nope")
    assert "unknown theme" in str(excinfo.value)
    assert "osakanights" in str(excinfo.value)  # lists what IS available


def test_theme_css_is_injected_after_viewer_css() -> None:
    theme = md2html.load_theme("osakanights")
    html = md2html.build_multi_html(
        build_id="B", title="T", source="d.md", theme_css=theme.css
    )
    assert theme.css in html
    assert html.index(md2html.VIEWER_CSS.read_text(encoding="utf-8")) < html.index(
        theme.css
    )


def test_main_theme_supersedes_tokens(
    doc: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    md2html.main(_args(doc, tmp_path, theme="osakanights"))
    out = capsys.readouterr().out
    assert "theme: osakanights" in out
    html = (tmp_path / "mydoc.html").read_text(encoding="utf-8")
    assert "Fraunces" in html


# ── Output writers ──────────────────────────────────────────────────────────
def test_write_multi_outputs(doc: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    html_path = md2html.write_multi(
        doc, out_dir, md2html.DEFAULT_TOKENS, title="My Doc", build_id="B123"
    )
    assert html_path == out_dir / "mydoc.html"
    assert (out_dir / "mydoc.md").read_text(encoding="utf-8") == DOC_MD
    copied = json.loads((out_dir / "mydoc.tokens.json").read_text(encoding="utf-8"))
    assert {"fonts", "themes", "canvas"} <= set(copied)
    html = html_path.read_text(encoding="utf-8")
    assert "build B123" in html
    assert "<title>My Doc</title>" in html


def test_write_inline_output(doc: Path, tmp_path: Path) -> None:
    out_dir = tmp_path / "out"
    html_path = md2html.write_inline(
        doc, out_dir, md2html.DEFAULT_TOKENS, title="T", build_id="B"
    )
    html = html_path.read_text(encoding="utf-8")
    assert "window.__DOC_MD__ = " in html
    assert "graph LR" in html
    assert "categoryColours" in html
    assert not (out_dir / "mydoc.tokens.json").exists()


# ── main() ──────────────────────────────────────────────────────────────────
def test_main_multi_prints_serve_reminder(
    doc: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    md2html.main(_args(doc, out_dir, serve_hint=True))
    out = capsys.readouterr().out
    assert "wrote" in out
    assert "file:// blocks fetch" in out
    assert "serve.py" in out
    assert (out_dir / "mydoc.html").is_file()


def test_main_inline(
    doc: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    out_dir = tmp_path / "out"
    md2html.main(_args(doc, out_dir, inline=True, title="Custom"))
    assert "self-contained" in capsys.readouterr().out
    assert "<title>Custom</title>" in (out_dir / "mydoc.html").read_text(
        encoding="utf-8"
    )


def test_main_missing_doc_exits_1(
    tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        md2html.main(_args(tmp_path / "nope.md", tmp_path))
    assert excinfo.value.code == 1
    assert "markdown file not found" in capsys.readouterr().err


def test_main_missing_tokens_exits_1(
    doc: Path, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    with pytest.raises(SystemExit) as excinfo:
        md2html.main(_args(doc, tmp_path, tokens=str(tmp_path / "nope.json")))
    assert excinfo.value.code == 1
    assert "design tokens file not found" in capsys.readouterr().err


def test_build_parser_defaults() -> None:
    args = md2html.build_parser().parse_args(["doc.md"])
    assert args.doc == "doc.md"
    assert args.out == str(md2html.DEFAULT_OUT)
    assert args.inline is False
    assert args.tokens == str(md2html.DEFAULT_TOKENS)
    assert args.title is None
    assert args.serve_hint is False


def test_write_multi_same_dir_source(tmp_path: Path) -> None:
    """Doc already living in the out dir must not be copied onto itself."""
    doc = tmp_path / "inplace.md"
    doc.write_text("# hi\n", encoding="utf-8")
    html_path = md2html.write_multi(
        doc, tmp_path, md2html.DEFAULT_TOKENS, title="T", build_id="B"
    )
    assert html_path.is_file()
    assert doc.read_text(encoding="utf-8") == "# hi\n"


if __name__ == "__main__":  # pragma: no cover
    script_dir = str(Path(__file__).parent.resolve())
    base_args = [__file__, "-v", "--rootdir", script_dir, "-o", "addopts="]
    sys.exit(pytest.main(base_args + sys.argv[1:]))
