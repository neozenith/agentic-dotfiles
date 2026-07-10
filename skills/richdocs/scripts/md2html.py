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
DEFAULT_TOKENS = SCRIPT_DIR.parent / "assets" / "design-tokens.json"
DEFAULT_OUT = Path("tmp/richdocs")

FALLBACK_TOKENS: dict[str, object] = {
    "fonts": {"body": "sans-serif", "mono": "monospace"},
    "themes": {
        "light": {
            "bg": "#f8fafc",
            "fg": "#0f172a",
            "muted": "#64748b",
            "accent": "#2563eb",
            "surface": "#ffffff",
            "border": "#e2e8f0",
        },
        "dark": {
            "bg": "#0f172a",
            "fg": "#e2e8f0",
            "muted": "#94a3b8",
            "accent": "#60a5fa",
            "surface": "#1e293b",
            "border": "#334155",
        },
    },
    "canvas": {
        "cytoscape": {
            "light": {
                "nodeFill": "#2563eb",
                "nodeLabel": "#0f172a",
                "edge": "#64748b",
                "compoundBg": "#f1f5f9",
                "compoundBorder": "#cbd5e1",
            },
            "dark": {
                "nodeFill": "#60a5fa",
                "nodeLabel": "#e2e8f0",
                "edge": "#94a3b8",
                "compoundBg": "#1e293b",
                "compoundBorder": "#475569",
            },
        },
        "plotly": {
            "light": {
                "paper": "#ffffff",
                "plot": "#f8fafc",
                "font": "#0f172a",
                "grid": "#e2e8f0",
                "series": ["#2563eb", "#0d9488", "#d97706", "#dc2626", "#7c3aed"],
            },
            "dark": {
                "paper": "#0f172a",
                "plot": "#1e293b",
                "font": "#e2e8f0",
                "grid": "#334155",
                "series": ["#60a5fa", "#2dd4bf", "#fbbf24", "#f87171", "#a78bfa"],
            },
        },
    },
}

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


# ── Template ───────────────────────────────────────────────────────────────
TEMPLATE = """<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{{TITLE}}</title>
<script>
  // Pre-paint theme resolution: localStorage -> prefers-color-scheme -> light.
  (function () {
    var t = null;
    try { t = localStorage.getItem("richdocs-theme"); } catch (e) {}
    if (t !== "light" && t !== "dark") {
      t = window.matchMedia && window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
    }
    document.documentElement.setAttribute("data-theme", t);
  })();
</script>
<style>
  * { box-sizing: border-box; }
  html { -webkit-text-size-adjust: 100%; }
  body {
    margin: 0;
    background: var(--rd-bg);
    color: var(--rd-fg);
    font-family: var(--rd-font-body);
    line-height: 1.65;
  }
  header.rd-header {
    position: sticky; top: 0; z-index: 10;
    display: flex; align-items: baseline; gap: 0.75rem;
    padding: 0.6rem 1rem;
    background: var(--rd-surface);
    border-bottom: 1px solid var(--rd-border);
  }
  header.rd-header h1 { font-size: 1rem; margin: 0; }
  header.rd-header .rd-meta { color: var(--rd-muted); font-size: 0.75rem; font-family: var(--rd-font-mono); }
  header.rd-header button {
    margin-left: auto;
    background: var(--rd-bg); color: var(--rd-fg);
    border: 1px solid var(--rd-border); border-radius: 6px;
    padding: 0.25rem 0.7rem; cursor: pointer; font-size: 0.85rem;
  }
  main { max-width: 52rem; margin: 0 auto; padding: 1.5rem 1rem 5rem; }
  main h1, main h2, main h3 { line-height: 1.25; }
  main h2 { border-bottom: 1px solid var(--rd-border); padding-bottom: 0.3rem; }
  main a { color: var(--rd-accent); }
  main code {
    font-family: var(--rd-font-mono); font-size: 0.875em;
    background: var(--rd-surface); border: 1px solid var(--rd-border);
    border-radius: 4px; padding: 0.1em 0.35em;
  }
  main pre {
    background: var(--rd-surface); border: 1px solid var(--rd-border);
    border-radius: 8px; padding: 0.9rem 1rem; overflow-x: auto;
  }
  main pre code { background: none; border: none; padding: 0; }
  main blockquote {
    margin: 1rem 0; padding: 0.25rem 1rem;
    border-left: 3px solid var(--rd-accent);
    color: var(--rd-muted); background: var(--rd-surface);
  }
  .rd-table-wrap { overflow-x: auto; }
  main table { border-collapse: collapse; margin: 1rem 0; width: 100%; }
  main th, main td { border: 1px solid var(--rd-border); padding: 0.4rem 0.7rem; text-align: left; }
  main th { background: var(--rd-surface); }
  main img { max-width: 100%; }
  .rd-canvas {
    background: var(--rd-surface); border: 1px solid var(--rd-border);
    border-radius: 8px; margin: 1rem 0;
  }
  .rd-mermaid { display: flex; justify-content: center; padding: 0.75rem; }
  .rd-error {
    border: 1px solid #dc2626; color: #dc2626;
    border-radius: 8px; padding: 0.75rem 1rem; margin: 1rem 0;
    font-family: var(--rd-font-mono); font-size: 0.85rem; white-space: pre-wrap;
  }
</style>
<script src="{{CDN_MARKED}}"></script>
<script src="{{CDN_MERMAID}}"></script>
</head>
<body>
<header class="rd-header">
  <h1 id="rd-title">{{TITLE}}</h1>
  <span class="rd-meta">{{SOURCE}}</span>
  <span class="rd-meta">build {{BUILD_ID}}</span>
  <button id="rd-theme-toggle" type="button" aria-label="Toggle theme">theme</button>
</header>
<main><article id="rd-article">Loading…</article></main>
{{BOOTSTRAP}}
<script>
"use strict";
var BUILD_ID = "{{BUILD_ID}}";
var SOURCE = "{{SOURCE}}";
var CDN = { cytoscape: "{{CDN_CYTOSCAPE}}", dagre: "{{CDN_DAGRE}}", cytoscapeDagre: "{{CDN_CYTOSCAPE_DAGRE}}", plotly: "{{CDN_PLOTLY}}" };
var FALLBACK_TOKENS = {{FALLBACK_TOKENS}};
var TOKENS = FALLBACK_TOKENS;
var cyBlocks = [];      // { el, payload } for re-theming
var plotlyBlocks = [];  // { el, payload }
var mermaidSources = []; // { el, src }
var lazyLoaded = {};

function currentTheme() {
  return document.documentElement.getAttribute("data-theme") === "dark" ? "dark" : "light";
}

function applyTokenCss(tokens) {
  var css = "";
  ["light", "dark"].forEach(function (theme) {
    var t = tokens.themes[theme];
    css += ":root[data-theme=" + theme + "]{"
      + "--rd-bg:" + t.bg + ";--rd-fg:" + t.fg + ";--rd-muted:" + t.muted + ";"
      + "--rd-accent:" + t.accent + ";--rd-surface:" + t.surface + ";--rd-border:" + t.border + ";"
      + "--rd-font-body:" + tokens.fonts.body + ";--rd-font-mono:" + tokens.fonts.mono + ";}";
  });
  var style = document.getElementById("rd-token-css");
  if (!style) {
    style = document.createElement("style");
    style.id = "rd-token-css";
    document.head.appendChild(style);
  }
  style.textContent = css;
}

function loadScript(name, url) {
  if (lazyLoaded[name]) return lazyLoaded[name];
  lazyLoaded[name] = new Promise(function (resolve, reject) {
    var s = document.createElement("script");
    s.src = url;
    s.onload = resolve;
    s.onerror = function () { reject(new Error("failed to load " + url)); };
    document.head.appendChild(s);
  });
  return lazyLoaded[name];
}

function fetchNoStore(url) {
  return fetch(url + "?v=" + BUILD_ID, { cache: "no-store" }).then(function (r) {
    if (!r.ok) throw new Error("HTTP " + r.status + " fetching " + url);
    return r;
  });
}

function showError(el, err) {
  var div = document.createElement("div");
  div.className = "rd-error";
  div.textContent = String(err && err.message ? err.message : err);
  el.replaceChildren(div);
  console.error(err);
}

// ── Mermaid ────────────────────────────────────────────────────────────
function renderAllMermaid() {
  if (mermaidSources.length === 0) return Promise.resolve();
  window.mermaid.initialize({
    startOnLoad: false,
    theme: currentTheme() === "dark" ? "dark" : "default",
    securityLevel: "loose"
  });
  var seq = Promise.resolve();
  mermaidSources.forEach(function (m, i) {
    seq = seq.then(function () {
      return window.mermaid.render("rd-mmd-" + BUILD_ID + "-" + i + "-" + currentTheme(), m.src)
        .then(function (out) { m.el.innerHTML = out.svg; })
        .catch(function (err) { showError(m.el, err); });
    });
  });
  return seq;
}

// ── Cytoscape ──────────────────────────────────────────────────────────
function cyStyle(theme) {
  var c = TOKENS.canvas.cytoscape[theme];
  return [
    { selector: "node", style: {
        "background-color": c.nodeFill, "label": "data(label)",
        "color": c.nodeLabel, "font-size": "11px",
        "text-valign": "bottom", "text-margin-y": 4,
        "font-family": TOKENS.fonts.body } },
    { selector: ":parent", style: {
        "background-color": c.compoundBg, "border-color": c.compoundBorder,
        "border-width": 1, "text-valign": "top", "color": c.nodeLabel } },
    { selector: "edge", style: {
        "line-color": c.edge, "target-arrow-color": c.edge,
        "target-arrow-shape": "triangle", "curve-style": "bezier", "width": 1.5 } }
  ];
}

function renderCytoscape(block) {
  var payload = block.payload;
  var el = block.el;
  el.style.height = (payload.height || 420) + "px";
  var layout = payload.layout || { name: "dagre", rankDir: "LR" };
  if (layout.name === "dagre" && !layout.rankDir) layout.rankDir = "LR";
  if (block.cy) { block.cy.destroy(); }
  block.cy = window.cytoscape({
    container: el,
    elements: payload.elements,
    layout: layout,
    style: cyStyle(currentTheme())
  });
}

function loadCytoscapeLibs() {
  return loadScript("cytoscape", CDN.cytoscape)
    .then(function () { return loadScript("dagre", CDN.dagre); })
    .then(function () { return loadScript("cytoscapeDagre", CDN.cytoscapeDagre); })
    .then(function () { window.cytoscape.use(window.cytoscapeDagre); });
}

// ── Plotly ─────────────────────────────────────────────────────────────
function plotlyLayout(payload) {
  var p = TOKENS.canvas.plotly[currentTheme()];
  var layout = Object.assign({}, payload.layout || {});
  layout.paper_bgcolor = p.paper;
  layout.plot_bgcolor = p.plot;
  layout.font = Object.assign({}, layout.font || {}, { color: p.font, family: TOKENS.fonts.body });
  layout.colorway = p.series;
  layout.xaxis = Object.assign({}, layout.xaxis || {}, { gridcolor: p.grid });
  layout.yaxis = Object.assign({}, layout.yaxis || {}, { gridcolor: p.grid });
  return layout;
}

function renderPlotly(block) {
  return window.Plotly.react(block.el, block.payload.data, plotlyLayout(block.payload), { responsive: true });
}

// ── Fenced-block upgrade ───────────────────────────────────────────────
function resolvePayload(raw) {
  var payload = JSON.parse(raw);
  if (typeof payload.data === "string") {
    return fetchNoStore(payload.data).then(function (r) { return r.json(); }).then(function (remote) {
      if (Array.isArray(remote)) {
        payload.data = remote;
      } else {
        delete payload.data;
        payload = Object.assign({}, remote, payload);
      }
      return payload;
    });
  }
  return Promise.resolve(payload);
}

function upgradeFences(article) {
  var jobs = [];
  var needsCy = false, needsPlotly = false;
  article.querySelectorAll("pre > code").forEach(function (code) {
    var lang = (code.className.match(/language-([\\w-]+)/) || [])[1];
    if (lang !== "mermaid" && lang !== "cytoscape" && lang !== "plotly") return;
    var pre = code.parentElement;
    var div = document.createElement("div");
    div.className = "rd-canvas rd-" + lang;
    pre.replaceWith(div);
    var raw = code.textContent;
    if (lang === "mermaid") {
      mermaidSources.push({ el: div, src: raw });
    } else {
      jobs.push(resolvePayload(raw).then(function (payload) {
        var block = { el: div, payload: payload };
        if (lang === "cytoscape") { cyBlocks.push(block); needsCy = true; }
        else { plotlyBlocks.push(block); needsPlotly = true; }
      }).catch(function (err) { showError(div, err); }));
    }
  });
  return Promise.all(jobs).then(function () {
    var loads = [];
    if (cyBlocks.length) loads.push(loadCytoscapeLibs());
    if (plotlyBlocks.length) loads.push(loadScript("plotly", CDN.plotly));
    return Promise.all(loads);
  }).then(function () {
    cyBlocks.forEach(function (b) { try { renderCytoscape(b); } catch (e) { showError(b.el, e); } });
    plotlyBlocks.forEach(function (b) { renderPlotly(b).catch(function (e) { showError(b.el, e); }); });
    return renderAllMermaid();
  });
}

function wrapTables(article) {
  article.querySelectorAll("table").forEach(function (table) {
    var wrap = document.createElement("div");
    wrap.className = "rd-table-wrap";
    table.replaceWith(wrap);
    wrap.appendChild(table);
  });
}

// ── Theme toggle ───────────────────────────────────────────────────────
function retheme() {
  cyBlocks.forEach(function (b) { try { renderCytoscape(b); } catch (e) { showError(b.el, e); } });
  plotlyBlocks.forEach(function (b) { renderPlotly(b).catch(function (e) { showError(b.el, e); }); });
  renderAllMermaid();
}

document.getElementById("rd-theme-toggle").addEventListener("click", function () {
  var next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  try { localStorage.setItem("richdocs-theme", next); } catch (e) {}
  retheme();
});

// ── Boot ───────────────────────────────────────────────────────────────
function loadTokens() {
  if (window.__DOC_TOKENS__ !== undefined) return Promise.resolve(window.__DOC_TOKENS__);
  return fetchNoStore("design-tokens.json").then(function (r) { return r.json(); })
    .catch(function (err) {
      console.error("design-tokens.json fetch failed; using baked fallback tokens", err);
      return FALLBACK_TOKENS;
    });
}

function loadDoc() {
  if (window.__DOC_MD__ !== undefined) return Promise.resolve(window.__DOC_MD__);
  return fetchNoStore(SOURCE).then(function (r) { return r.text(); });
}

loadTokens().then(function (tokens) {
  TOKENS = tokens;
  applyTokenCss(tokens);
  return loadDoc();
}).then(function (md) {
  var article = document.getElementById("rd-article");
  article.innerHTML = window.marked.parse(md);
  wrapTables(article);
  return upgradeFences(article);
}).catch(function (err) {
  showError(document.getElementById("rd-article"), err);
});
</script>
</body>
</html>
"""


# ── Core (pure) ────────────────────────────────────────────────────────────
def make_build_id(now: datetime | None = None) -> str:
    """UTC build id, e.g. 20260707T031500Z."""
    dt = now if now is not None else datetime.now(UTC)
    return dt.strftime("%Y%m%dT%H%M%SZ")


def _apply_tokens(template: str, *, build_id: str, title: str, source: str) -> str:
    """Substitute the {{BUILD_ID}} / {{TITLE}} / {{SOURCE}} template tokens."""
    return (
        template.replace("{{BUILD_ID}}", build_id)
        .replace("{{TITLE}}", title)
        .replace("{{SOURCE}}", source)
    )


def _embed_json(value: object) -> str:
    """json.dumps with `</` escaped as `<\\/` so embedded payloads can't close the script tag."""
    return json.dumps(value).replace("</", "<\\/")


def _base_html(*, build_id: str, title: str, source: str, bootstrap: str) -> str:
    html = _apply_tokens(TEMPLATE, build_id=build_id, title=title, source=source)
    html = html.replace("{{FALLBACK_TOKENS}}", _embed_json(FALLBACK_TOKENS))
    html = html.replace("{{BOOTSTRAP}}", bootstrap)
    for name, url in CDN.items():
        html = html.replace("{{CDN_" + name.upper().replace("-", "_") + "}}", url)
    return html


def build_multi_html(*, build_id: str, title: str, source: str) -> str:
    """HTML for multi-file mode: markdown + tokens fetched at runtime."""
    return _base_html(build_id=build_id, title=title, source=source, bootstrap="")


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
        build_id=build_id, title=title, source=source, bootstrap=bootstrap
    )


# ── Output writers ─────────────────────────────────────────────────────────
def write_multi(
    doc: Path, out_dir: Path, tokens_path: Path, *, title: str, build_id: str
) -> Path:
    """Write <out>/<stem>.html + <stem>.md copy + design-tokens.json copy."""
    out_dir.mkdir(parents=True, exist_ok=True)
    stem = doc.stem
    html_path = out_dir / f"{stem}.html"
    html_path.write_text(
        build_multi_html(build_id=build_id, title=title, source=f"{stem}.md"),
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
