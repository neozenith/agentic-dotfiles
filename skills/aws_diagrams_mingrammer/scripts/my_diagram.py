#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["diagrams>=0.24"]
# ///
"""Generate example AWS architecture diagrams showcasing recommended layout configurations.

Produces PNG images for each recommended layout variant into the resources/ directory.
These images are referenced by the SKILL.md as visual examples.

Self-describing output targets:
    Pass --output-targets to print the list of output files (one per line) and exit.
    This enables Makefile integration where Make can query this script for its targets
    and only rebuild when the source .py file is newer than its outputs.

Output structure:
    .claude/skills/aws_diagrams_mingrammer/resources/{variant}.png

Usage:
    uv run .claude/skills/aws_diagrams_mingrammer/scripts/my_diagram.py
    uv run .claude/skills/aws_diagrams_mingrammer/scripts/my_diagram.py --output-targets
"""
import logging
import sys
from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import EC2, ECS, Lambda
from diagrams.aws.database import RDS, Elasticache
from diagrams.aws.network import ELB, CloudFront, Route53

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
log = logging.getLogger(__name__)

SCRIPT = Path(__file__)
SCRIPT_DIR = SCRIPT.parent.resolve()
RESOURCES_DIR = (SCRIPT_DIR / ".." / "resources").resolve()

# ============================================================================
# Layout Configurations — the recommended variants
# ============================================================================

LAYOUT_CONFIGS = [
    {
        "name": "dot_lr_ortho",
        "title": "dot LR + ortho (Recommended)",
        "graph_attr": {
            "rankdir": "LR",
            "splines": "ortho",
            "nodesep": "0.70",
            "ranksep": "0.90",
        },
    },
    {
        "name": "dot_lr_spline",
        "title": "dot LR + spline (Soft Curves)",
        "graph_attr": {
            "rankdir": "LR",
            "splines": "spline",
            "nodesep": "0.70",
            "ranksep": "0.90",
        },
    },
    {
        "name": "dot_tb_ortho",
        "title": "dot TB + ortho (Vertical Flow)",
        "graph_attr": {
            "rankdir": "TB",
            "splines": "ortho",
            "nodesep": "0.70",
            "ranksep": "0.75",
        },
    },
]

# ============================================================================
# Self-describing output targets
#
# The DIAGRAMS registry is the single source of truth for what this script
# produces. OUTPUT_TARGETS derives the list of output file paths from it.
# Pass --output-targets to print this list and exit (used by Make).
# ============================================================================

DIAGRAMS = [(f"resources/{cfg['name']}", cfg) for cfg in LAYOUT_CONFIGS]
OUTPUT_TARGETS = [f"{name}.png" for name, _ in DIAGRAMS]


# ============================================================================
# Diagram Builder
# ============================================================================


def build_diagram(config: dict[str, object]) -> None:
    """Build and render the example 3-tier AWS architecture diagram.

    The diagram models a typical web service:
      DNS -> CDN -> LB -> [Web Servers] -> [App Containers] -> DB + Cache
    """
    name = str(config["name"])
    title = str(config["title"])
    graph_attr = config.get("graph_attr", {})
    assert isinstance(graph_attr, dict)

    filepath = str(RESOURCES_DIR / name)

    log.info("  %-30s -> resources/%s.png", name, name)

    with Diagram(
        title,
        filename=filepath,
        show=False,
        outformat="png",
        graph_attr=graph_attr,
    ):
        # ── Ingress ─────────────────────────────────────────
        dns = Route53("Route53\nDNS")
        cdn = CloudFront("CloudFront\nCDN")

        # ── Web Tier ────────────────────────────────────────
        with Cluster("Web Tier"):
            lb = ELB("ALB")
            web1 = EC2("Web 1")
            web2 = EC2("Web 2")
            web3 = EC2("Web 3")

        # ── App Tier ────────────────────────────────────────
        with Cluster("App Tier"):
            app1 = ECS("App 1")
            app2 = ECS("App 2")
            worker = Lambda("Worker")

        # ── Data Tier ───────────────────────────────────────
        with Cluster("Data Tier"):
            db_primary = RDS("Primary DB")
            db_replica = RDS("Read Replica")
            cache = Elasticache("Redis Cache")

        # ── Connections ─────────────────────────────────────
        dns >> cdn >> lb
        lb >> [web1, web2, web3]
        web1 >> app1
        web2 >> app2
        web3 >> app1
        app1 >> db_primary
        app2 >> db_primary
        app1 >> cache
        app2 >> cache
        db_primary >> Edge(label="replication", style="dashed") >> db_replica
        worker >> db_primary


# ============================================================================
# Main
# ============================================================================


def main() -> None:
    RESOURCES_DIR.mkdir(parents=True, exist_ok=True)

    log.info("Output directory: %s", RESOURCES_DIR)
    log.info("Generating %d layout variants...\n", len(LAYOUT_CONFIGS))

    for config in LAYOUT_CONFIGS:
        build_diagram(config)

    log.info("\nDone. Generated images:")
    for png in sorted(RESOURCES_DIR.glob("*.png")):
        size_kb = png.stat().st_size / 1024
        log.info("  %-35s %6.0f KB", png.name, size_kb)


if __name__ == "__main__":  # pragma: no cover
    if "--output-targets" in sys.argv:
        for target in OUTPUT_TARGETS:
            print(target)
        sys.exit(0)

    main()
