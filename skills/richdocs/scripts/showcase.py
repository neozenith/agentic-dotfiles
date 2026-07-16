#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = []
# ///
"""Generate a theme showcase: every brand, every mode, in one page.

Two shapes of output:

- **Gallery (default)** — every installed theme embedded, with a brand switcher
  and a light/dark toggle. Use it to compare brands side by side, or to prove a
  new brand holds up across the whole surface.
- **`--theme NAME`** — that brand ALONE. No switcher, nothing from any other
  brand in the artifact. Use it to hand someone a single-brand reference.

The page exercises the full surface a brand has to survive: colour ramps,
typography (including the glyph-disambiguation gate), components, Plotly charts,
a Cytoscape graph, Mermaid, and architecture diagrams composed from the vendored
draw.io stencils — emitted as **editable SVG** (drawio round-trips them via the
`content` attribute, so a reader can open one and keep editing).

This module is a *generator*. The page lives in `assets/showcase.*` (ADR-008).
"""

from __future__ import annotations

import argparse
import html
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from xml.sax.saxutils import quoteattr

from md2html import (
    CDN,
    THEMES_DIR,
    Theme,
    available_themes,
    load_theme,
    make_build_id,
)
from stencil import DEFAULT_ZIP, load_stencils
from typing import Any

# ── Configuration ──────────────────────────────────────────────────────────
SCRIPT_DIR = Path(__file__).resolve().parent
ASSETS_DIR = SCRIPT_DIR.parent / "assets"

SHOWCASE_HTML = ASSETS_DIR / "showcase.html"
SHOWCASE_CSS = ASSETS_DIR / "showcase.css"
SHOWCASE_JS = ASSETS_DIR / "showcase.js"
VIEWER_CYTOSCAPE_JS = ASSETS_DIR / "viewer-cytoscape.js"
VIEWER_DECKGL_JS = ASSETS_DIR / "viewer-deckgl.js"
# Committed, precomputed 3D embeddings so the showcase is self-contained and its build
# stays OFFLINE. These are regenerated out-of-band by a Tier-A helper (model2vec +
# umap-learn; needs network + a model download), never during `make ci`.
EMB_LOCAL = ASSETS_DIR / "embeddings_umap_local.json"
EMB_GLOBAL = ASSETS_DIR / "embeddings_umap_global.json"

DEFAULT_OUT = Path("tmp/richdocs")


@dataclass(frozen=True)
class Node:
    """One box. `icon` is a vendored stencil id; `x`/`y` are grid cells, not pixels."""

    id: str
    label: str
    icon: str
    x: int
    y: int


@dataclass(frozen=True)
class Arch:
    title: str
    caption: str
    nodes: list[Node]
    edges: list[tuple[str, str, str]]  # (source, target, label)


# Architecture diagrams composed from real draw.io stencils. The icon id doubles as
# the drawio `resIcon`, so the emitted XML re-opens as a first-class AWS shape
# rather than a flat image.
ARCHITECTURES: list[Arch] = [
    Arch(
        title="Agentic web app · GCP request & data plane",
        caption=(
            "A multi-container Cloud Run service: FastAPI ingress, an ADK agent on "
            "Vertex AI Gemini, and a dbt sidecar, fronted by IAP, over Firestore / "
            "BigQuery / GCS — provisioned keylessly through Workload Identity."
        ),
        nodes=[
            Node("sa", "Runtime SA", "mxgraph.gcp2/Cloud IAM", 1, 0),
            Node("browser", "React SPA", "mxgraph.gcp2/Users", 0, 2),
            Node(
                "iap", "Identity-Aware Proxy", "mxgraph.gcp2/Identity Aware Proxy", 1, 2
            ),
            Node("backend", "FastAPI backend", "mxgraph.gcp2/Cloud Run", 2, 1),
            Node("agent", "ADK agent", "mxgraph.gcp2/Cloud Run", 2, 2),
            Node("dbt", "dbt sidecar", "mxgraph.gcp2/Container Engine", 2, 3),
            Node(
                "vertex",
                "Vertex AI Gemini",
                "mxgraph.gcp2/Cloud Machine Learning",
                3,
                0,
            ),
            Node("fs", "Firestore", "mxgraph.gcp2/cloud firestore", 3, 1),
            Node("bq", "BigQuery", "mxgraph.gcp2/BigQuery", 3, 2),
            Node("gcs", "Cloud Storage", "mxgraph.gcp2/Cloud Storage", 3, 3),
            Node("build", "Cloud Build", "mxgraph.gcp2/Container Builder", 4, 1),
            Node("ar", "Artifact Registry", "mxgraph.gcp2/Container Registry", 4, 2),
            Node("wif", "Workload Identity", "mxgraph.gcp2/Cloud IAM", 4, 3),
        ],
        edges=[
            ("browser", "iap", "https"),
            ("iap", "backend", "invoke"),
            ("sa", "backend", "runs as"),
            ("backend", "agent", "/run"),
            ("backend", "dbt", "/api/dbt"),
            ("agent", "vertex", "infer"),
            ("agent", "fs", "sessions"),
            ("backend", "bq", "semantic"),
            ("backend", "gcs", "assets"),
            ("dbt", "bq", "materialise"),
            ("wif", "build", "deploy"),
            ("build", "ar", "push"),
            ("ar", "backend", "image"),
        ],
    ),
    Arch(
        title="Scale-to-zero web app · AWS edge to compute",
        caption=(
            "CloudFront is the only door: Lambda@Edge does the auth, S3 serves the "
            "SPA, and a Fargate task that idles at zero is woken by EventBridge, an "
            "SQS-depth alarm, or a Scheduler tick via the lifecycle Lambda."
        ),
        nodes=[
            Node("browser", "User Browser", "mxgraph.aws4/user", 0, 2),
            Node("r53", "Route 53", "mxgraph.aws4/route 53", 1, 0),
            Node("acm", "ACM cert", "mxgraph.aws4/certificate manager", 1, 1),
            Node("cf", "CloudFront", "mxgraph.aws4/cloudfront", 1, 2),
            Node("edge", "Lambda@Edge auth", "mxgraph.aws4/lambda", 1, 3),
            Node("s3", "S3 SPA assets", "mxgraph.aws4/s3", 2, 0),
            Node("vpc", "VPC", "mxgraph.aws4/vpc", 2, 1),
            Node("ecs", "Fargate task", "mxgraph.aws4/fargate", 2, 2),
            Node("sqs", "SQS queue", "mxgraph.aws4/sqs", 2, 3),
            Node("ecr", "ECR", "mxgraph.aws4/ecr", 3, 0),
            Node("ssm", "SSM Params", "mxgraph.aws4/systems manager", 3, 1),
            Node("logs", "CloudWatch", "mxgraph.aws4/cloudwatch", 3, 2),
            Node("eb", "EventBridge", "mxgraph.aws4/eventbridge", 3, 3),
            Node(
                "iam", "IAM roles", "mxgraph.aws4/identity and access management", 4, 1
            ),
            Node("ctl", "Lifecycle Lambda", "mxgraph.aws4/lambda", 4, 2),
            Node("sch", "Scheduler", "mxgraph.aws4/cloudwatch", 4, 3),
        ],
        edges=[
            ("browser", "cf", "https"),
            ("r53", "cf", "alias"),
            ("acm", "cf", "TLS"),
            ("cf", "edge", "viewer-req"),
            ("cf", "s3", "/*"),
            ("cf", "ecs", "/api/*"),
            ("ecr", "ecs", "pull"),
            ("ecs", "ssm", "secrets"),
            ("ecs", "logs", "awslogs"),
            ("ecs", "eb", "task-state"),
            ("sqs", "eb", "depth"),
            ("eb", "ctl", "wake"),
            ("sch", "ctl", "tick"),
            ("ctl", "ecs", "desiredCount"),
            ("iam", "ecs", "task role"),
            ("vpc", "ecs", "runs in"),
        ],
    ),
]

CELL_W, CELL_H = 210, 158
ICON = 52


# ── CSS scoping ────────────────────────────────────────────────────────────
_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)

# `@import[^;]+;` is WRONG, and failed silently in two ways:
#
#   1. A Google Fonts URL contains semicolons in its weight list
#      (`wght@400;500;600`), so it truncated mid-URL and emitted a broken rule.
#      The page then fell back to the generic serif — which LOOKS like the real
#      face at a glance, so it survived review.
#   2. It matched the literal word "@import" inside a comment and swallowed prose.
#
# So: strip comments first, then match the url()/string token as a unit, which
# lets semicolons live inside it.
_IMPORT_RE = re.compile(
    r"""@import\s+
        (?: url\( [^)]* \)      # url(...) — semicolons are legal inside
          | "[^"]*"             # "..."
          | '[^']*'             # '...'
        )
        [^;]*                   # media query / layer / supports
        ;""",
    re.I | re.X,
)


def split_imports(css: str) -> tuple[str, str]:
    """Separate `@import` rules from the rest.

    `@import` is only legal at the top of a stylesheet, so it cannot survive being
    nested under a brand scope. Hoist it; scope everything else.

    Comments are stripped first — the word "@import" appears in this project's own
    theme.css prose, and matching it there produced a stylesheet of English.
    """
    css = _COMMENT_RE.sub("", css)
    imports = "\n".join(m.group(0) for m in _IMPORT_RE.finditer(css))
    return imports, _IMPORT_RE.sub("", css)


def scope_css(css: str, brand: str) -> str:
    """Confine a theme's CSS to `[data-brand="<brand>"]`.

    The gallery holds every brand at once, so one brand's rules must not leak into
    another's. Selectors are prefixed rather than wrapped, because `@scope` and
    nesting are not safe to assume in every browser this may be opened in.
    """
    css = _COMMENT_RE.sub("", css)
    prefix = f':root[data-brand="{brand}"]'
    out: list[str] = []
    for block in re.finditer(r"([^{}]+)\{([^{}]*)\}", css):
        selectors, body = block.group(1).strip(), block.group(2).strip()
        if not selectors or not body:
            continue
        scoped = ", ".join(
            # `*` and `:root`/`html`/`body` anchor to the scope itself, not below it.
            f"{prefix} {s.strip()}"
            if s.strip() not in ("*", ":root", "html", "body")
            else f"{prefix} {s.strip()}".replace(f"{prefix} :root", prefix)
            for s in selectors.split(",")
        )
        out.append(f"{scoped} {{ {body} }}")
    return "\n".join(out)


# ── Stencil architecture → editable SVG ────────────────────────────────────
def _drawio_xml(arch: Arch) -> str:
    """The mxfile source drawio needs to re-open the diagram as editable shapes."""
    cells: list[str] = []
    for n in arch.nodes:
        dotted = n.icon.replace("/", ".")
        # Provider-aware round-trip: AWS stencils are the `resourceIcon` shape with a
        # `resIcon`; GCP (and any non-AWS) stencils are referenced as their own shape,
        # so each re-opens in diagrams.net as a first-class shape of its own provider.
        if n.icon.startswith("mxgraph.aws4/"):
            style = (
                "sketch=0;outlineConnect=0;fontColor=#232F3E;gradientColor=none;"
                "fillColor=#232F3E;strokeColor=none;dashed=0;verticalLabelPosition=bottom;"
                "verticalAlign=top;align=center;html=1;fontSize=12;fontStyle=0;"
                f"aspect=fixed;shape=mxgraph.aws4.resourceIcon;resIcon={dotted};"
            )
        else:
            style = (
                "sketch=0;outlineConnect=0;html=1;fontSize=12;verticalLabelPosition=bottom;"
                f"verticalAlign=top;align=center;aspect=fixed;strokeColor=none;shape={dotted};"
            )
        cells.append(
            f'<mxCell id="{n.id}" value={quoteattr(n.label)} style="{style}" '
            'vertex="1" parent="1">'
            f'<mxGeometry x="{n.x * CELL_W + 40}" y="{n.y * CELL_H + 40}" '
            f'width="{ICON}" height="{ICON}" as="geometry"/></mxCell>'
        )
    for i, (src, dst, label) in enumerate(arch.edges):
        cells.append(
            f'<mxCell id="e{i}" value={quoteattr(label)} '
            'style="edgeStyle=orthogonalEdgeStyle;rounded=0;html=1;fontSize=10;" '
            f'edge="1" parent="1" source="{src}" target="{dst}">'
            '<mxGeometry relative="1" as="geometry"/></mxCell>'
        )
    return (
        '<mxfile host="app.diagrams.net">'
        f'<diagram name={quoteattr(arch.title)} id="d1">'
        '<mxGraphModel dx="800" dy="600" grid="1" gridSize="10" page="1" '
        'pageWidth="850" pageHeight="1100" math="0" shadow="0">'
        f'<root><mxCell id="0"/><mxCell id="1" parent="0"/>{"".join(cells)}</root>'
        "</mxGraphModel></diagram></mxfile>"
    )


def compose_architecture_svg(arch: Arch, stencils: dict[str, dict[str, Any]]) -> str:
    """Render one architecture as an SVG that drawio can re-open and edit.

    Icons are the real vendored stencils. Everything else (labels, connectors,
    arrowheads) is painted with CSS custom properties, so ONE SVG serves every
    brand and both modes — no re-generation on theme switch.
    """
    nodes = {n.id: n for n in arch.nodes}
    cols = max(n.x for n in arch.nodes) + 1
    rows = max(n.y for n in arch.nodes) + 1
    pad = 34
    w, h = cols * CELL_W + 2 * pad, rows * CELL_H + 2 * pad
    r = ICON / 2

    def centre(n: Node) -> tuple[float, float]:
        return (n.x * CELL_W + CELL_W / 2 + pad, n.y * CELL_H + CELL_H / 2 + pad)

    def port(
        a: tuple[float, float], b: tuple[float, float]
    ) -> tuple[float, float, float, float]:
        """Point on a's boundary facing b, plus the outward unit direction. Edges
        leave and arrive on the side that points at the other node, so they never
        stab through the icon's face."""
        ax, ay = a
        dx, dy = b[0] - ax, b[1] - ay
        if abs(dx) >= abs(dy):
            s = 1.0 if dx > 0 else -1.0
            return ax + (r + 7) * s, ay, s, 0.0
        s = 1.0 if dy > 0 else -1.0
        return ax, ay + (r + 7) * s, 0.0, s

    parts: list[str] = []
    labels: list[tuple[float, float, str]] = []

    # Edges first (they sit UNDER the halos + icons), as smooth curves that depart
    # and arrive along the correct side. A halo behind every icon means the rare
    # edge that passes behind one reads cleanly instead of tangling with it.
    for src, dst, label in arch.edges:
        c1, c2 = centre(nodes[src]), centre(nodes[dst])
        sx, sy, sdx, sdy = port(c1, c2)
        tx, ty, tdx, tdy = port(c2, c1)
        k = 52.0
        d = (
            f"M {sx:.1f} {sy:.1f} C {sx + sdx * k:.1f} {sy + sdy * k:.1f}, "
            f"{tx + tdx * k:.1f} {ty + tdy * k:.1f}, {tx:.1f} {ty:.1f}"
        )
        parts.append(
            f'<path d="{d}" fill="none" stroke="var(--sc-edge)" stroke-width="1.4" '
            'opacity="0.85" marker-end="url(#sc-arrow)"/>'
        )
        # Label near the curve's midpoint (average of endpoints and control handles).
        lx = (sx + tx) / 4 + (sx + sdx * k + tx + tdx * k) / 4
        ly = (sy + ty) / 4 + (sy + sdy * k + ty + tdy * k) / 4
        labels.append((lx, ly, label))

    # Label plates on top of the lines, so overlapping labels stay individually legible.
    for lx, ly, label in labels:
        plate_w = len(label) * 5.6 + 10
        parts.append(
            f'<rect x="{lx - plate_w / 2:.1f}" y="{ly - 8:.1f}" width="{plate_w:.1f}" '
            'height="14" rx="3" fill="var(--rd-surface)" opacity="0.9"/>'
        )
        parts.append(
            f'<text x="{lx:.1f}" y="{ly + 2.5:.1f}" text-anchor="middle" font-size="9.5" '
            'fill="var(--sc-muted)" font-family="var(--rd-font-mono)">'
            f"{html.escape(label)}</text>"
        )

    for n in arch.nodes:
        cx, cy = centre(n)
        entry = stencils.get(n.icon)
        if entry is None:  # a typo must fail the BUILD, not render an empty box
            raise SystemExit(f"error: stencil not found: {n.icon!r}")
        ew, eh = float(entry["w"]), float(entry["h"])
        scale = ICON / max(ew, eh)
        parts.append(
            f'<circle cx="{cx:.1f}" cy="{cy:.1f}" r="{r + 8:.1f}" fill="var(--rd-surface)"/>'
        )
        parts.append(
            f'<g transform="translate({cx - ew * scale / 2:.1f},{cy - eh * scale / 2:.1f}) '
            f'scale({scale:.4f})" color="var(--sc-icon)">{entry["svg"]}</g>'
        )
        parts.append(
            f'<text x="{cx}" y="{cy + ICON / 2 + 16}" text-anchor="middle" font-size="11.5" '
            'font-weight="600" fill="var(--sc-fg)" font-family="var(--rd-font-body)">'
            f"{html.escape(n.label)}</text>"
        )

    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" '
        f'width="100%" class="sc-arch" content={quoteattr(_drawio_xml(arch))}>'
        '<defs><marker id="sc-arrow" viewBox="0 0 10 10" refX="8" refY="5" '
        'markerWidth="6" markerHeight="6" orient="auto-start-reverse">'
        '<path d="M 0 0 L 10 5 L 0 10 z" fill="var(--sc-edge)"/></marker></defs>'
        f"{''.join(parts)}</svg>"
    )


# ── Assembly ───────────────────────────────────────────────────────────────
def _load_embeddings(path: Path) -> dict[str, Any]:
    """Load a precomputed 3D embedding and attach a tooltip label per point."""
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    for p in data.get("points", []):
        text = p.get("text", "")
        p["label"] = (
            p.get("topic", "") + " · " + (text[:64] + ("…" if len(text) > 64 else ""))
        )
    return data


def build_payload(themes: list[Theme], *, build_id: str) -> dict[str, object]:
    """Everything showcase.js needs, as one JSON block (ADR-008)."""
    stencils = load_stencils(DEFAULT_ZIP)
    return {
        "buildId": build_id,
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
        "embeddings": {
            "local": _load_embeddings(EMB_LOCAL),
            "global": _load_embeddings(EMB_GLOBAL),
        },
        "brands": [
            {
                "name": t.name,
                "tokens": json.loads(t.tokens_path.read_text(encoding="utf-8")),
            }
            for t in themes
        ],
        "architectures": [
            {
                "title": a.title,
                "caption": a.caption,
                "svg": compose_architecture_svg(a, stencils),
            }
            for a in ARCHITECTURES
        ],
    }


def _embed_json(value: object) -> str:
    return json.dumps(value).replace("</", "<\\/")


def build_html(themes: list[Theme], *, build_id: str, single: bool) -> str:
    imports: list[str] = []
    scoped: list[str] = []
    for t in themes:
        imp, rest = split_imports(t.css)
        if imp:
            imports.append(imp)
        # A single-brand artifact still gets scoped CSS: the scope simply always
        # matches. That keeps one code path, and keeps the two outputs identical
        # in everything but which brands are present.
        scoped.append(scope_css(rest, t.name))

    subs = {
        "{{BUILD_ID}}": build_id,
        "{{TITLE}}": (
            f"{themes[0].name} — theme showcase"
            if single
            else "Theme showcase — all brands"
        ),
        "{{THEME_IMPORTS}}": "\n".join(imports),
        "{{THEME_CSS}}": "\n".join(scoped),
        "{{SHOWCASE_CSS}}": SHOWCASE_CSS.read_text(encoding="utf-8"),
        "{{SHOWCASE_JS}}": SHOWCASE_JS.read_text(encoding="utf-8"),
        "{{VIEWER_CYTOSCAPE_JS}}": VIEWER_CYTOSCAPE_JS.read_text(encoding="utf-8"),
        "{{VIEWER_DECKGL_JS}}": VIEWER_DECKGL_JS.read_text(encoding="utf-8"),
        "{{SINGLE}}": "true" if single else "false",
        "{{PAYLOAD}}": _embed_json(build_payload(themes, build_id=build_id)),
        "{{CDN_MERMAID}}": CDN["mermaid"],
    }
    out = SHOWCASE_HTML.read_text(encoding="utf-8")
    for k, v in subs.items():
        out = out.replace(k, v)
    return out


# ── CLI ────────────────────────────────────────────────────────────────────
def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="showcase.py",
        description="Generate a theme showcase — every brand, or one brand alone.",
    )
    parser.add_argument(
        "--theme",
        help=(
            "Show ONE brand, alone — no switcher, nothing from any other brand in "
            f"the artifact. Omit for a gallery of all installed brands "
            f"(available: {', '.join(available_themes()) or 'none installed'})."
        ),
    )
    parser.add_argument(
        "--out",
        default=str(DEFAULT_OUT),
        help=f"Output directory (default: {DEFAULT_OUT})",
    )
    return parser


def main(args: argparse.Namespace) -> None:
    if args.theme:
        themes = [load_theme(args.theme)]
        stem = f"showcase-{args.theme}"
    else:
        names = available_themes()
        if not names:
            print(f"error: no themes installed under {THEMES_DIR}", file=sys.stderr)
            raise SystemExit(1)
        themes = [load_theme(n) for n in names]
        stem = "showcase"

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{stem}.html"
    path.write_text(
        build_html(themes, build_id=make_build_id(), single=bool(args.theme)),
        encoding="utf-8",
    )
    which = (
        themes[0].name
        if args.theme
        else f"{len(themes)} brands: " + ", ".join(t.name for t in themes)
    )
    print(f"wrote {path} ({which})")
    print("note: self-contained apart from pinned CDN libs — serve it or open it.")


if __name__ == "__main__":  # pragma: no cover
    main(build_parser().parse_args())
