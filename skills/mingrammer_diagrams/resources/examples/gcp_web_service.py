#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["diagrams>=0.24"]
# ///
"""GCP 3-tier web service — same shape as the AWS example, GCP node set.

Self-rendering example: `uv run <this file>` writes `gcp_web_service.png`
beside it. Requires Graphviz (`dot`) on PATH.
"""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.gcp.compute import Functions, GKE
from diagrams.gcp.database import SQL, Memorystore
from diagrams.gcp.network import CDN, DNS, LoadBalancing

OUT = str(Path(__file__).with_suffix(""))  # -> resources/examples/gcp_web_service(.png)

with Diagram(
    "GCP Web Service",
    filename=OUT,
    show=False,
    outformat="png",
    graph_attr={"rankdir": "LR", "splines": "ortho", "nodesep": "0.70", "ranksep": "0.90"},
):
    dns = DNS("Cloud DNS")
    cdn = CDN("Cloud CDN")

    with Cluster("Web Tier"):
        lb = LoadBalancing("HTTPS LB")
        web = [GKE("GKE 1"), GKE("GKE 2"), GKE("GKE 3")]

    with Cluster("App Tier"):
        fn = [Functions("Fn 1"), Functions("Fn 2")]

    with Cluster("Data Tier"):
        primary = SQL("Cloud SQL")
        replica = SQL("Read Replica")
        cache = Memorystore("Memorystore")

    dns >> cdn >> lb >> web
    web[0] >> fn[0]
    web[1] >> fn[1]
    web[2] >> fn[0]
    fn[0] >> [primary, cache]
    fn[1] >> [primary, cache]
    primary >> Edge(label="replication", style="dashed") >> replica
