#!/usr/bin/env python3
# /// script
# requires-python = ">=3.9"
# dependencies = ["diagrams>=0.24"]
# ///
"""Azure 3-tier web service — same shape as the AWS example, Azure node set.

Self-rendering example: `uv run <this file>` writes `azure_web_service.png`
beside it. Requires Graphviz (`dot`) on PATH.
"""

from pathlib import Path

from diagrams import Cluster, Diagram, Edge
from diagrams.azure.compute import AKS, FunctionApps
from diagrams.azure.database import CacheForRedis, SQLDatabases
from diagrams.azure.network import CDNProfiles, DNSZones, LoadBalancers

OUT = str(Path(__file__).with_suffix(""))  # -> resources/examples/azure_web_service(.png)

with Diagram(
    "Azure Web Service",
    filename=OUT,
    show=False,
    outformat="png",
    graph_attr={"rankdir": "LR", "splines": "ortho", "nodesep": "0.70", "ranksep": "0.90"},
):
    dns = DNSZones("DNS Zone")
    cdn = CDNProfiles("CDN")

    with Cluster("Web Tier"):
        lb = LoadBalancers("Load Balancer")
        web = [AKS("AKS 1"), AKS("AKS 2"), AKS("AKS 3")]

    with Cluster("App Tier"):
        fn = [FunctionApps("Func 1"), FunctionApps("Func 2")]

    with Cluster("Data Tier"):
        primary = SQLDatabases("SQL DB")
        replica = SQLDatabases("Geo Replica")
        cache = CacheForRedis("Redis")

    dns >> cdn >> lb >> web
    web[0] >> fn[0]
    web[1] >> fn[1]
    web[2] >> fn[0]
    fn[0] >> [primary, cache]
    fn[1] >> [primary, cache]
    primary >> Edge(label="geo-replication", style="dashed") >> replica
