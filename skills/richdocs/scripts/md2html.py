#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate a rich HTML viewer for a markdown document (paired-markdown pattern).

Two output modes:

- Multi-file (default): writes <out>/<stem>.html + a copy of the markdown +
  design-tokens.json. The HTML fetches both at runtime (cache: no-store), so
  it needs an HTTP server — use serve.py; file:// blocks fetch.
- --inline: one self-contained <stem>.html with the markdown and tokens
  embedded as window globals. Opens over file:// (CDN network still required).

The viewer renders markdown client-side (marked), with fenced-block upgrades:
```mermaid (mermaid.run), ```cytoscape (cytoscape+dagre, lazy-loaded), and
```plotly (plotly.js, lazy-loaded) — all themed from design-tokens.json with
a light/dark toggle.

This module is the *generator*. The page it generates lives in `assets/` as three
editable files (viewer.html / viewer.css / viewer.js) — see ADR-008. Nothing here
should contain HTML, CSS, or JS source.
"""

from __future__ import annotations

import argparse
import json
import shutil
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import NamedTuple

# ── Configuration ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
SKILL_DIR = SCRIPT_DIR.parent
ASSETS_DIR = SKILL_DIR / "assets"
THEMES_DIR = SKILL_DIR / "resources" / "themes"

DEFAULT_TOKENS = ASSETS_DIR / "design-tokens.json"
VIEWER_HTML = ASSETS_DIR / "viewer.html"
VIEWER_CSS = ASSETS_DIR / "viewer.css"
VIEWER_JS = ASSETS_DIR / "viewer.js"
VIEWER_CYTOSCAPE_JS = ASSETS_DIR / "viewer-cytoscape.js"
VIEWER_DECKGL_JS = ASSETS_DIR / "viewer-deckgl.js"

DEFAULT_OUT = Path("tmp/richdocs")

# The baked fallback palette IS the default brandpack — read, never re-declared.
# A second hand-maintained copy would drift (this retires the ADR-004 hazard).
FALLBACK_TOKENS: dict[str, object] = json.loads(
    DEFAULT_TOKENS.read_text(encoding="utf-8")
)

# Pinned CDN versions (jsdelivr). marked + mermaid load eagerly; cytoscape /
# dagre / plotly / deck.gl are injected lazily on first use so plain docs stay
# light. deck.gl is the heaviest of the four (~1 MB) — hence never eager.
CDN = {
    "marked": "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js",
    "mermaid": "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js",
    "cytoscape": "https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js",
    "dagre": "https://cdn.jsdelivr.net/npm/dagre@0.8.5/dist/dagre.min.js",
    "cytoscape-dagre": "https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js",
    "plotly": "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js",
    "deckgl": "https://cdn.jsdelivr.net/npm/deck.gl@9.0.36/dist.min.js",
    # MapLibre GL powers the optional vector basemap under a `map`-view deckgl block
    # (deck rides as a MapboxOverlay). CSS is a separate file MapLibre needs to size
    # its canvas + controls. Both free, keyless.
    "maplibre": "https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.js",
    "maplibreCss": "https://cdn.jsdelivr.net/npm/maplibre-gl@4.7.1/dist/maplibre-gl.css",
    # duckdb-wasm: an in-browser OLAP SQL engine, loaded as an ES module. Pinned to a
    # STABLE release (npm `latest` serves a -dev build). The mvp/eh bundles it selects
    # need no COOP/COEP headers, so a plain no-store static server can host the demo.
    "duckdb": "https://cdn.jsdelivr.net/npm/@duckdb/duckdb-wasm@1.32.0/+esm",
}


# ── Core (pure) ────────────────────────────────────────────────────────────
def make_build_id(now: datetime | None = None) -> str:
    """UTC build id, e.g. 20260707T031500Z."""
    dt = now if now is not None else datetime.now(UTC)
    return dt.strftime("%Y%m%dT%H%M%SZ")


class Theme(NamedTuple):
    """A named brand theme: its brandpack, plus optional CSS the pack can't express.

    The brandpack *chooses* the faces (`fonts.display` / `body` / `mono`) — a typeface
    is a brand value. But a JSON file cannot `@import` a webfile, and cannot express
    layout (sizes, tracking, borders). `theme.css` does those. It is optional.
    """

    name: str
    tokens_path: Path
    css: str


def available_themes() -> list[str]:
    """Theme names: directories under resources/themes/ holding a brandpack.

    Themes are **real files inside the skill** — never symlinks out to a project.
    The skill must stay self-contained and portable: copy `.claude/` anywhere and
    every theme still resolves (ADR-009).
    """
    if not THEMES_DIR.is_dir():
        return []
    return sorted(
        d.name
        for d in THEMES_DIR.iterdir()
        if d.is_dir() and (d / "design-tokens.json").is_file()
    )


def load_theme(name: str) -> Theme:
    """Resolve a named theme. Crashes loudly on an unknown name (escalators-not-stairs)."""
    theme_dir = THEMES_DIR / name
    tokens_path = theme_dir / "design-tokens.json"
    if not tokens_path.is_file():
        known = ", ".join(available_themes()) or "(none installed)"
        raise SystemExit(
            f"error: unknown theme {name!r}. Available: {known}\n"
            f"       (a theme is a directory under {THEMES_DIR} containing design-tokens.json)"
        )
    css_path = theme_dir / "theme.css"
    css = css_path.read_text(encoding="utf-8") if css_path.is_file() else ""
    return Theme(name=name, tokens_path=tokens_path, css=css)


def resolve_default_theme(tokens: dict[str, object] | None) -> str:
    """A brandpack may pin the initial theme via `defaultTheme: "dark" | "light"`.

    Returns "" when unset or invalid, which leaves the page on the
    prefers-color-scheme fallback. An explicit user toggle always wins over this.
    """
    value = (tokens or {}).get("defaultTheme")
    return value if value in ("light", "dark") else ""


def _embed_json(value: object) -> str:
    """json.dumps with `</` escaped as `<\\/` so embedded payloads can't close the script tag."""
    return json.dumps(value).replace("</", "<\\/")


def tokens_source_for(stem: str) -> str:
    """The brandpack is PAIRED with the doc, like the markdown is.

    A fixed `design-tokens.json` meant one output directory could only ever hold
    one theme — rendering a second doc with a different --theme silently clobbered
    the first doc's palette, and both pages then loaded the survivor's brand.
    """
    return f"{stem}.tokens.json"


def build_config(
    *, build_id: str, source: str, tokens_source: str = "design-tokens.json"
) -> dict[str, object]:
    """Everything viewer.js needs from generation time.

    Delivered as one JSON block (#rd-config) rather than as template placeholders
    inside the JS, so viewer.js stays placeholder-free and lintable (ADR-008).
    """
    return {
        "buildId": build_id,
        "source": source,
        "tokensSource": tokens_source,
        "cdn": {
            "cytoscape": CDN["cytoscape"],
            "dagre": CDN["dagre"],
            "cytoscapeDagre": CDN["cytoscape-dagre"],
            "plotly": CDN["plotly"],
            "deckgl": CDN["deckgl"],
            "maplibre": CDN["maplibre"],
            "maplibreCss": CDN["maplibreCss"],
            "duckdb": CDN["duckdb"],
        },
        "fallbackTokens": FALLBACK_TOKENS,
    }


def _base_html(
    *,
    build_id: str,
    title: str,
    source: str,
    bootstrap: str,
    default_theme: str = "",
    theme_css: str = "",
    tokens_source: str = "design-tokens.json",
) -> str:
    """Assemble viewer.html + viewer.css + viewer.js into one page.

    viewer.css and viewer.js are inlined verbatim; only viewer.html carries
    placeholders. Substitution is a single pass over one shell.
    """
    substitutions = {
        "{{TITLE}}": title,
        "{{SOURCE}}": source,
        "{{BUILD_ID}}": build_id,
        "{{DEFAULT_THEME}}": default_theme,
        "{{BOOTSTRAP}}": bootstrap,
        "{{VIEWER_CSS}}": VIEWER_CSS.read_text(encoding="utf-8"),
        "{{THEME_CSS}}": theme_css,
        "{{VIEWER_JS}}": VIEWER_JS.read_text(encoding="utf-8"),
        "{{VIEWER_CYTOSCAPE_JS}}": VIEWER_CYTOSCAPE_JS.read_text(encoding="utf-8"),
        "{{VIEWER_DECKGL_JS}}": VIEWER_DECKGL_JS.read_text(encoding="utf-8"),
        "{{RD_CONFIG}}": _embed_json(
            build_config(build_id=build_id, source=source, tokens_source=tokens_source)
        ),
        "{{CDN_MARKED}}": CDN["marked"],
        "{{CDN_MERMAID}}": CDN["mermaid"],
    }
    html = VIEWER_HTML.read_text(encoding="utf-8")
    for placeholder, value in substitutions.items():
        html = html.replace(placeholder, value)
    return html


def build_multi_html(
    *,
    build_id: str,
    title: str,
    source: str,
    default_theme: str = "",
    theme_css: str = "",
    tokens_source: str = "design-tokens.json",
) -> str:
    """HTML for multi-file mode: markdown + tokens fetched at runtime."""
    return _base_html(
        build_id=build_id,
        title=title,
        source=source,
        bootstrap="",
        default_theme=default_theme,
        theme_css=theme_css,
        tokens_source=tokens_source,
    )


def build_inline_html(
    md_text: str,
    tokens: object,
    *,
    build_id: str,
    title: str,
    source: str,
    theme_css: str = "",
) -> str:
    """HTML for --inline mode: markdown + tokens embedded as window globals."""
    bootstrap = (
        "<script>\n"
        f"window.__DOC_MD__ = {_embed_json(md_text)};\n"
        f"window.__DOC_TOKENS__ = {_embed_json(tokens)};\n"
        "</script>"
    )
    return _base_html(
        build_id=build_id,
        title=title,
        source=source,
        bootstrap=bootstrap,
        default_theme=resolve_default_theme(
            tokens if isinstance(tokens, dict) else None
        ),
        theme_css=theme_css,
    )


# ── Output writers ─────────────────────────────────────────────────────────
def write_multi(
    doc: Path,
    out_dir: Path,
    tokens_path: Path,
    *,
    title: str,
    build_id: str,
    theme_css: str = "",
) -> Path:
    """Write <out>/<stem>.html + <stem>.md copy + design-tokens.json copy."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = doc.stem
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(
        build_multi_html(
            build_id=build_id,
            title=title,
            source=f"{stem}.md",
            default_theme=resolve_default_theme(tokens),
            theme_css=theme_css,
            tokens_source=tokens_source_for(stem),
        ),
        encoding="utf-8",
    )
    md_copy = out_dir / f"{stem}.md"
    if doc.resolve() != md_copy.resolve():
        shutil.copyfile(doc, md_copy)
    # Paired with the doc: two docs in one dir may carry two different brands.
    shutil.copyfile(tokens_path, out_dir / tokens_source_for(stem))
    return html_path


def write_inline(
    doc: Path,
    out_dir: Path,
    tokens_path: Path,
    *,
    title: str,
    build_id: str,
    theme_css: str = "",
) -> Path:
    """Write a single self-contained <out>/<stem>.html."""
    out_dir.mkdir(parents=True, exist_ok=True)
    tokens = json.loads(tokens_path.read_text(encoding="utf-8"))
    html_path = out_dir / f"{doc.stem}.html"
    html = build_inline_html(
        doc.read_text(encoding="utf-8"),
        tokens,
        build_id=build_id,
        title=title,
        source=doc.name,
        theme_css=theme_css,
    )
    html_path.write_text(html, encoding="utf-8")
    return html_path


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="md2html.py",
        description="Generate a rich, token-themed HTML viewer for a markdown document.",
    )
    parser.add_argument("doc", help="Markdown file to render")
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    parser.add_argument(
        "--inline",
        action="store_true",
        help="Emit one self-contained HTML file (file:// friendly)",
    )
    parser.add_argument(
        "--theme",
        help=(
            "Named brand theme from resources/themes/ "
            f"(available: {', '.join(available_themes()) or 'none installed'}). "
            "Supplies the brandpack AND its theme.css. Overrides --tokens."
        ),
    )
    parser.add_argument(
        "--tokens",
        default=str(DEFAULT_TOKENS),
        help="design-tokens.json to use (ignored when --theme is given)",
    )
    parser.add_argument("--title", help="Page title (default: doc stem)")
    parser.add_argument(
        "--serve-hint",
        action="store_true",
        help="Print the serve.py invocation for the output dir",
    )
    return parser


def main(args: argparse.Namespace) -> None:
    doc = Path(args.doc)
    if not doc.is_file():
        print(f"error: markdown file not found: {doc}", file=sys.stderr)
        raise SystemExit(1)

    # A named theme brings its own brandpack + CSS, so it supersedes --tokens.
    theme = load_theme(args.theme) if args.theme else None
    tokens_path = theme.tokens_path if theme else Path(args.tokens)
    theme_css = theme.css if theme else ""
    if not tokens_path.is_file():
        print(f"error: design tokens file not found: {tokens_path}", file=sys.stderr)
        raise SystemExit(1)

    out_dir = Path(args.out)
    title = args.title or doc.stem
    build_id = make_build_id()

    if args.inline:
        html_path = write_inline(
            doc,
            out_dir,
            tokens_path,
            title=title,
            build_id=build_id,
            theme_css=theme_css,
        )
        print(
            f"wrote {html_path} (self-contained; opens over file://, CDN network still required)"
        )
    else:
        html_path = write_multi(
            doc,
            out_dir,
            tokens_path,
            title=title,
            build_id=build_id,
            theme_css=theme_css,
        )
        print(f"wrote {html_path} (+ {doc.stem}.md, {tokens_source_for(doc.stem)})")
        print(
            "note: multi-file mode fetches at runtime — file:// blocks fetch, serve it over HTTP."
        )

    if theme:
        print(f"theme: {theme.name}")

    if args.serve_hint:
        print(
            f"serve with: uv run --no-project {SCRIPT_DIR / 'serve.py'} {out_dir} --open"
        )


if __name__ == "__main__":  # pragma: no cover
    main(build_parser().parse_args())
