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

# ── Configuration ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"

DEFAULT_TOKENS = ASSETS_DIR / "design-tokens.json"
VIEWER_HTML = ASSETS_DIR / "viewer.html"
VIEWER_CSS = ASSETS_DIR / "viewer.css"
VIEWER_JS = ASSETS_DIR / "viewer.js"

DEFAULT_OUT = Path("tmp/richdocs")

# The baked fallback palette IS the default brandpack — read, never re-declared.
# A second hand-maintained copy would drift (this retires the ADR-004 hazard).
FALLBACK_TOKENS: dict[str, object] = json.loads(
    DEFAULT_TOKENS.read_text(encoding="utf-8")
)

# Pinned CDN versions (jsdelivr). marked + mermaid load eagerly; cytoscape /
# dagre / plotly are injected lazily on first use so plain docs stay light.
CDN = {
    "marked": "https://cdn.jsdelivr.net/npm/marked@12.0.2/marked.min.js",
    "mermaid": "https://cdn.jsdelivr.net/npm/mermaid@11.4.1/dist/mermaid.min.js",
    "cytoscape": "https://cdn.jsdelivr.net/npm/cytoscape@3.30.2/dist/cytoscape.min.js",
    "dagre": "https://cdn.jsdelivr.net/npm/dagre@0.8.5/dist/dagre.min.js",
    "cytoscape-dagre": "https://cdn.jsdelivr.net/npm/cytoscape-dagre@2.5.0/cytoscape-dagre.min.js",
    "plotly": "https://cdn.jsdelivr.net/npm/plotly.js-dist-min@2.35.2/plotly.min.js",
}


# ── Core (pure) ────────────────────────────────────────────────────────────
def make_build_id(now: datetime | None = None) -> str:
    """UTC build id, e.g. 20260707T031500Z."""
    dt = now if now is not None else datetime.now(UTC)
    return dt.strftime("%Y%m%dT%H%M%SZ")


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


def build_config(*, build_id: str, source: str) -> dict[str, object]:
    """Everything viewer.js needs from generation time.

    Delivered as one JSON block (#rd-config) rather than as template placeholders
    inside the JS, so viewer.js stays placeholder-free and lintable (ADR-008).
    """
    return {
        "buildId": build_id,
        "source": source,
        "cdn": {
            "cytoscape": CDN["cytoscape"],
            "dagre": CDN["dagre"],
            "cytoscapeDagre": CDN["cytoscape-dagre"],
            "plotly": CDN["plotly"],
        },
        "fallbackTokens": FALLBACK_TOKENS,
    }


def _base_html(
    *, build_id: str, title: str, source: str, bootstrap: str, default_theme: str = ""
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
        "{{VIEWER_JS}}": VIEWER_JS.read_text(encoding="utf-8"),
        "{{RD_CONFIG}}": _embed_json(build_config(build_id=build_id, source=source)),
        "{{CDN_MARKED}}": CDN["marked"],
        "{{CDN_MERMAID}}": CDN["mermaid"],
    }
    html = VIEWER_HTML.read_text(encoding="utf-8")
    for placeholder, value in substitutions.items():
        html = html.replace(placeholder, value)
    return html


def build_multi_html(
    *, build_id: str, title: str, source: str, default_theme: str = ""
) -> str:
    """HTML for multi-file mode: markdown + tokens fetched at runtime."""
    return _base_html(
        build_id=build_id,
        title=title,
        source=source,
        bootstrap="",
        default_theme=default_theme,
    )


def build_inline_html(
    md_text: str, tokens: object, *, build_id: str, title: str, source: str
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
    )


# ── Output writers ─────────────────────────────────────────────────────────
def write_multi(
    doc: Path, out_dir: Path, tokens_path: Path, *, title: str, build_id: str
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
        ),
        encoding="utf-8",
    )
    md_copy = out_dir / f"{stem}.md"
    if doc.resolve() != md_copy.resolve():
        shutil.copyfile(doc, md_copy)
    shutil.copyfile(tokens_path, out_dir / "design-tokens.json")
    return html_path


def write_inline(
    doc: Path, out_dir: Path, tokens_path: Path, *, title: str, build_id: str
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
        "--tokens", default=str(DEFAULT_TOKENS), help="design-tokens.json to use"
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
    tokens_path = Path(args.tokens)
    if not tokens_path.is_file():
        print(f"error: design tokens file not found: {tokens_path}", file=sys.stderr)
        raise SystemExit(1)

    out_dir = Path(args.out)
    title = args.title or doc.stem
    build_id = make_build_id()

    if args.inline:
        html_path = write_inline(
            doc, out_dir, tokens_path, title=title, build_id=build_id
        )
        print(
            f"wrote {html_path} (self-contained; opens over file://, CDN network still required)"
        )
    else:
        html_path = write_multi(
            doc, out_dir, tokens_path, title=title, build_id=build_id
        )
        print(f"wrote {html_path} (+ {doc.stem}.md, design-tokens.json)")
        print(
            "note: multi-file mode fetches at runtime — file:// blocks fetch, serve it over HTTP."
        )

    if args.serve_hint:
        print(
            f"serve with: uv run --no-project {SCRIPT_DIR / 'serve.py'} {out_dir} --open"
        )


if __name__ == "__main__":  # pragma: no cover
    main(build_parser().parse_args())
