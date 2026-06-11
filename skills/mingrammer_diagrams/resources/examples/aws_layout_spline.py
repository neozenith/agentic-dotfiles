#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["diagrams>=0.24"]
# ///
"""Layout variant — same AWS architecture, `splines=spline` (soft curves).

Use spline edges when `ortho` produces too many overlapping right-angle bends
in an edge-dense graph. Self-rendering: `uv run <this file>` writes the PNG.
"""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS, EC2
from diagrams.aws.database import RDS, Elasticache
from diagrams.aws.network import ELB, CloudFront, Route53

OUT = str(Path(__file__).with_suffix(""))  # -> resources/examples/aws_layout_spline(.png)

with Diagram(
    "AWS — splines=spline",
    filename=OUT,
    show=False,
    outformat="png",
    graph_attr={"rankdir": "LR", "splines": "spline", "nodesep": "0.70", "ranksep": "0.90"},
):
    dns = Route53("Route 53")
    cdn = CloudFront("CloudFront")

    with Cluster("Web Tier"):
        lb = ELB("ALB")
        web = [EC2("Web 1"), EC2("Web 2"), EC2("Web 3")]

    with Cluster("Data Tier"):
        app = ECS("App")
        primary = RDS("Primary")
        cache = Elasticache("Redis")

    dns >> cdn >> lb >> web
    web[0] >> app
    web[1] >> app
    web[2] >> app
    app >> Edge(label="read/write") >> primary
    app >> cache
