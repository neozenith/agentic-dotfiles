#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["diagrams>=0.24"]
# ///
"""AWS 3-tier web service — the recommended layout (dot, LR, ortho edges).

Self-rendering example: `uv run <this file>` writes `aws_web_service.png`
beside it. Requires Graphviz (`dot`) on PATH.
"""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.aws.compute import ECS, EC2, Lambda
from diagrams.aws.database import RDS, Elasticache
from diagrams.aws.network import ELB, CloudFront, Route53

OUT = str(Path(__file__).with_suffix(""))  # -> resources/examples/aws_web_service(.png)

with Diagram(
    "AWS Web Service",
    filename=OUT,
    show=False,
    outformat="png",
    graph_attr={"rankdir": "LR", "splines": "ortho", "nodesep": "0.70", "ranksep": "0.90"},
):
    dns = Route53("Route 53\nDNS")
    cdn = CloudFront("CloudFront\nCDN")

    with Cluster("Web Tier"):
        lb = ELB("ALB")
        web = [EC2("Web 1"), EC2("Web 2"), EC2("Web 3")]

    with Cluster("App Tier"):
        apps = [ECS("App 1"), ECS("App 2")]
        worker = Lambda("Worker")

    with Cluster("Data Tier"):
        primary = RDS("Primary")
        replica = RDS("Read Replica")
        cache = Elasticache("Redis")

    dns >> cdn >> lb >> web
    web[0] >> apps[0]
    web[1] >> apps[1]
    web[2] >> apps[0]
    apps[0] >> [primary, cache]
    apps[1] >> [primary, cache]
    worker >> primary
    primary >> Edge(label="replication", style="dashed") >> replica
