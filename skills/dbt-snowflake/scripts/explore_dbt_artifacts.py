#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "networkx>=3.0",
# ]
# ///
"""
explore_dbt_artifacts - Load and explore dbt artifacts with graph-based traversal.

Parses manifest.json and catalog.json from target/ directory, builds a NetworkX
directed graph, and provides CLI commands for exploring model lineage, dependencies,
and metadata.

Usage:
    uv run explore_dbt_artifacts.py nodes                    # List all nodes
    uv run explore_dbt_artifacts.py node <unique_id>         # Show node details
    uv run explore_dbt_artifacts.py upstream <unique_id>     # Find ancestors
    uv run explore_dbt_artifacts.py downstream <unique_id>   # Find descendants
    uv run explore_dbt_artifacts.py path <from> <to>         # Find path between nodes
    uv run explore_dbt_artifacts.py stats                    # Show graph statistics
"""
import argparse
import json
import logging
from dataclasses import dataclass, field
from pathlib import Path
from textwrap import dedent
from typing import Any

import networkx as nx

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

# Use current working directory as the dbt project root
# (skill should be invoked from within the dbt project)
PROJECT_ROOT = Path.cwd()

TARGET_DIR = PROJECT_ROOT / "target"
MANIFEST_PATH = TARGET_DIR / "manifest.json"
CATALOG_PATH = TARGET_DIR / "catalog.json"

ALL_INPUTS = [MANIFEST_PATH, CATALOG_PATH]

log = logging.getLogger(__name__)

# ============================================================================
# Dataclasses - Catalog
# ============================================================================


@dataclass
class CatalogColumn:
    """Column metadata from catalog.json."""

    name: str
    type: str
    index: int
    comment: str | None = None

    @classmethod
    def from_dict(cls, name: str, data: dict[str, Any]) -> "CatalogColumn":
        return cls(
            name=name,
            type=data.get("type", ""),
            index=data.get("index", 0),
            comment=data.get("comment"),
        )


@dataclass
class CatalogNodeMetadata:
    """Metadata for a catalog node."""

    type: str
    schema_name: str
    name: str
    database: str
    owner: str | None = None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatalogNodeMetadata":
        return cls(
            type=data.get("type", ""),
            schema_name=data.get("schema", ""),
            name=data.get("name", ""),
            database=data.get("database", ""),
            owner=data.get("owner"),
        )


@dataclass
class CatalogNode:
    """A node (table/view) from catalog.json."""

    unique_id: str
    metadata: CatalogNodeMetadata
    columns: dict[str, CatalogColumn]
    stats: dict[str, Any]

    @classmethod
    def from_dict(cls, unique_id: str, data: dict[str, Any]) -> "CatalogNode":
        columns = {}
        for col_name, col_data in data.get("columns", {}).items():
            columns[col_name] = CatalogColumn.from_dict(col_name, col_data)

        return cls(
            unique_id=unique_id,
            metadata=CatalogNodeMetadata.from_dict(data.get("metadata", {})),
            columns=columns,
            stats=data.get("stats", {}),
        )


@dataclass
class CatalogMetadata:
    """Top-level metadata from catalog.json."""

    dbt_schema_version: str
    dbt_version: str
    generated_at: str
    invocation_id: str
    env: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "CatalogMetadata":
        return cls(
            dbt_schema_version=data.get("dbt_schema_version", ""),
            dbt_version=data.get("dbt_version", ""),
            generated_at=data.get("generated_at", ""),
            invocation_id=data.get("invocation_id", ""),
            env=data.get("env", {}),
        )


@dataclass
class Catalog:
    """Parsed catalog.json."""

    metadata: CatalogMetadata
    nodes: dict[str, CatalogNode]
    sources: dict[str, CatalogNode]
    errors: list[Any] | None

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Catalog":
        nodes = {}
        for uid, node_data in data.get("nodes", {}).items():
            nodes[uid] = CatalogNode.from_dict(uid, node_data)

        sources = {}
        for uid, source_data in data.get("sources", {}).items():
            sources[uid] = CatalogNode.from_dict(uid, source_data)

        return cls(
            metadata=CatalogMetadata.from_dict(data.get("metadata", {})),
            nodes=nodes,
            sources=sources,
            errors=data.get("errors"),
        )


# ============================================================================
# Dataclasses - Manifest
# ============================================================================


@dataclass
class ManifestMetadata:
    """Top-level metadata from manifest.json."""

    dbt_schema_version: str
    dbt_version: str
    generated_at: str
    invocation_id: str
    project_name: str
    project_id: str | None
    adapter_type: str
    env: dict[str, str]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestMetadata":
        return cls(
            dbt_schema_version=data.get("dbt_schema_version", ""),
            dbt_version=data.get("dbt_version", ""),
            generated_at=data.get("generated_at", ""),
            invocation_id=data.get("invocation_id", ""),
            project_name=data.get("project_name", ""),
            project_id=data.get("project_id"),
            adapter_type=data.get("adapter_type", ""),
            env=data.get("env", {}),
        )


@dataclass
class ManifestNodeConfig:
    """Configuration for a manifest node."""

    materialized: str | None = None
    schema_name: str | None = None
    database: str | None = None
    tags: list[str] = field(default_factory=list)
    meta: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ManifestNodeConfig":
        return cls(
            materialized=data.get("materialized"),
            schema_name=data.get("schema"),
            database=data.get("database"),
            tags=data.get("tags", []),
            meta=data.get("meta", {}),
        )


@dataclass
class ManifestNode:
    """A node from manifest.json (model, test, seed, snapshot, etc.)."""

    unique_id: str
    resource_type: str
    database: str
    schema_name: str
    name: str
    alias: str | None
    fqn: list[str]
    path: str
    original_file_path: str
    config: ManifestNodeConfig
    tags: list[str]
    description: str
    columns: dict[str, Any]
    depends_on_nodes: list[str]
    depends_on_macros: list[str]
    refs: list[list[str]]
    sources: list[list[str]]
    raw_code: str | None = None
    compiled_code: str | None = None

    @classmethod
    def from_dict(cls, unique_id: str, data: dict[str, Any]) -> "ManifestNode":
        depends_on = data.get("depends_on", {})
        return cls(
            unique_id=unique_id,
            resource_type=data.get("resource_type", ""),
            database=data.get("database", ""),
            schema_name=data.get("schema", ""),
            name=data.get("name", ""),
            alias=data.get("alias"),
            fqn=data.get("fqn", []),
            path=data.get("path", ""),
            original_file_path=data.get("original_file_path", ""),
            config=ManifestNodeConfig.from_dict(data.get("config", {})),
            tags=data.get("tags", []),
            description=data.get("description", ""),
            columns=data.get("columns", {}),
            depends_on_nodes=depends_on.get("nodes", []),
            depends_on_macros=depends_on.get("macros", []),
            refs=data.get("refs", []),
            sources=data.get("sources", []),
            raw_code=data.get("raw_code"),
            compiled_code=data.get("compiled_code"),
        )


@dataclass
class ManifestSource:
    """A source from manifest.json."""

    unique_id: str
    database: str
    schema_name: str
    name: str
    identifier: str
    description: str
    loader: str
    source_name: str

    @classmethod
    def from_dict(cls, unique_id: str, data: dict[str, Any]) -> "ManifestSource":
        return cls(
            unique_id=unique_id,
            database=data.get("database", ""),
            schema_name=data.get("schema", ""),
            name=data.get("name", ""),
            identifier=data.get("identifier", ""),
            description=data.get("description", ""),
            loader=data.get("loader", ""),
            source_name=data.get("source_name", ""),
        )


@dataclass
class ManifestDocBlock:
    """A docs block from manifest.json."""

    unique_id: str
    name: str
    block_contents: str
    original_file_path: str

    @classmethod
    def from_dict(cls, unique_id: str, data: dict[str, Any]) -> "ManifestDocBlock":
        return cls(
            unique_id=unique_id,
            name=data.get("name", ""),
            block_contents=data.get("block_contents", ""),
            original_file_path=data.get("original_file_path", ""),
        )


@dataclass
class Manifest:
    """Parsed manifest.json."""

    metadata: ManifestMetadata
    nodes: dict[str, ManifestNode]
    sources: dict[str, ManifestSource]
    macros: dict[str, Any]
    docs: dict[str, ManifestDocBlock]
    parent_map: dict[str, list[str]]
    child_map: dict[str, list[str]]
    exposures: dict[str, Any]
    metrics: dict[str, Any]
    groups: dict[str, Any]
    selectors: dict[str, Any]
    disabled: dict[str, Any]

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "Manifest":
        nodes = {}
        for uid, node_data in data.get("nodes", {}).items():
            nodes[uid] = ManifestNode.from_dict(uid, node_data)

        sources = {}
        for uid, source_data in data.get("sources", {}).items():
            sources[uid] = ManifestSource.from_dict(uid, source_data)

        docs = {}
        for uid, doc_data in data.get("docs", {}).items():
            docs[uid] = ManifestDocBlock.from_dict(uid, doc_data)

        return cls(
            metadata=ManifestMetadata.from_dict(data.get("metadata", {})),
            nodes=nodes,
            sources=sources,
            macros=data.get("macros", {}),
            docs=docs,
            parent_map=data.get("parent_map", {}),
            child_map=data.get("child_map", {}),
            exposures=data.get("exposures", {}),
            metrics=data.get("metrics", {}),
            groups=data.get("groups", {}),
            selectors=data.get("selectors", {}),
            disabled=data.get("disabled", {}),
        )


# ============================================================================
# Artifact Loading
# ============================================================================


@dataclass
class DbtArtifacts:
    """Container for loaded dbt artifacts."""

    manifest: Manifest
    catalog: Catalog | None
    graph: nx.DiGraph


def load_artifacts(target_dir: Path = TARGET_DIR) -> DbtArtifacts:
    """Load manifest and catalog from target directory."""
    manifest_path = target_dir / "manifest.json"
    catalog_path = target_dir / "catalog.json"

    if not manifest_path.exists():
        raise FileNotFoundError(f"manifest.json not found at {manifest_path}. Run 'dbt compile' first.")

    log.info(f"Loading manifest from {manifest_path}")
    manifest_data = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest = Manifest.from_dict(manifest_data)

    catalog = None
    if catalog_path.exists():
        log.info(f"Loading catalog from {catalog_path}")
        catalog_data = json.loads(catalog_path.read_text(encoding="utf-8"))
        catalog = Catalog.from_dict(catalog_data)
    else:
        log.warning(f"catalog.json not found at {catalog_path}. Run 'dbt docs generate' for column info.")

    graph = build_graph(manifest)

    return DbtArtifacts(manifest=manifest, catalog=catalog, graph=graph)


# ============================================================================
# Graph Construction
# ============================================================================


def build_graph(manifest: Manifest) -> nx.DiGraph:
    """Build a NetworkX directed graph from manifest parent/child maps."""
    G = nx.DiGraph()

    # Add nodes from manifest.nodes
    for unique_id, node in manifest.nodes.items():
        G.add_node(
            unique_id,
            resource_type=node.resource_type,
            schema=node.schema_name,
            name=node.name,
            alias=node.alias,
            materialized=node.config.materialized,
            tags=node.tags,
            path=node.original_file_path,
            database=node.database,
        )

    # Add source nodes
    for unique_id, source in manifest.sources.items():
        G.add_node(
            unique_id,
            resource_type="source",
            schema=source.schema_name,
            name=source.name,
            database=source.database,
            source_name=source.source_name,
        )

    # Add edges from parent_map (parent -> child)
    for child_id, parent_ids in manifest.parent_map.items():
        for parent_id in parent_ids:
            if parent_id in G and child_id in G:
                G.add_edge(parent_id, child_id)

    log.info(f"Built graph with {G.number_of_nodes()} nodes and {G.number_of_edges()} edges")
    return G


# ============================================================================
# Graph Query Functions
# ============================================================================


def get_upstream(graph: nx.DiGraph, node_id: str, depth: int | None = None) -> list[str]:
    """Get all upstream nodes (ancestors) of a node."""
    if node_id not in graph:
        return []
    if depth is not None:
        # Use BFS with depth limit on reversed graph
        ancestors = set()
        current_level = {node_id}
        for _ in range(depth):
            next_level = set()
            for n in current_level:
                next_level.update(graph.predecessors(n))
            ancestors.update(next_level)
            current_level = next_level
        return list(ancestors)
    return list(nx.ancestors(graph, node_id))


def get_downstream(graph: nx.DiGraph, node_id: str, depth: int | None = None) -> list[str]:
    """Get all downstream nodes (descendants) of a node."""
    if node_id not in graph:
        return []
    if depth is not None:
        descendants = set()
        current_level = {node_id}
        for _ in range(depth):
            next_level = set()
            for n in current_level:
                next_level.update(graph.successors(n))
            descendants.update(next_level)
            current_level = next_level
        return list(descendants)
    return list(nx.descendants(graph, node_id))


def get_path(graph: nx.DiGraph, source: str, target: str) -> list[str] | None:
    """Find shortest path between two nodes."""
    try:
        return nx.shortest_path(graph, source, target)
    except nx.NetworkXNoPath:
        return None
    except nx.NodeNotFound:
        return None


def get_roots(graph: nx.DiGraph, resource_type: str | None = None) -> list[str]:
    """Get nodes with no incoming edges (sources/roots)."""
    roots = [n for n in graph.nodes() if graph.in_degree(n) == 0]
    if resource_type:
        roots = [n for n in roots if graph.nodes[n].get("resource_type") == resource_type]
    return roots


def get_leaves(graph: nx.DiGraph, resource_type: str | None = None) -> list[str]:
    """Get nodes with no outgoing edges (terminal nodes)."""
    leaves = [n for n in graph.nodes() if graph.out_degree(n) == 0]
    if resource_type:
        leaves = [n for n in leaves if graph.nodes[n].get("resource_type") == resource_type]
    return leaves


def get_orphans(graph: nx.DiGraph) -> list[str]:
    """Get models with no refs and no downstream dependents (isolated)."""
    orphans = []
    for node_id in graph.nodes():
        attrs = graph.nodes[node_id]
        if attrs.get("resource_type") == "model":
            if graph.in_degree(node_id) == 0 and graph.out_degree(node_id) == 0:
                orphans.append(node_id)
    return orphans


def find_nodes(
    graph: nx.DiGraph,
    pattern: str | None = None,
    resource_type: str | None = None,
    tag: str | None = None,
    schema: str | None = None,
    materialized: str | None = None,
) -> list[str]:
    """Find nodes matching criteria."""
    results = []
    for node_id in graph.nodes():
        attrs = graph.nodes[node_id]

        if resource_type and attrs.get("resource_type") != resource_type:
            continue
        if tag and tag not in attrs.get("tags", []):
            continue
        if schema and attrs.get("schema", "").upper() != schema.upper():
            continue
        if materialized and attrs.get("materialized") != materialized:
            continue
        if pattern:
            name = attrs.get("name", "")
            if pattern.lower() not in name.lower() and pattern.lower() not in node_id.lower():
                continue

        results.append(node_id)

    return results


# ============================================================================
# Output Formatting
# ============================================================================


def format_output(data: Any, output_format: str = "table", graph: nx.DiGraph | None = None) -> str:
    """Format output data for display."""
    if output_format == "json":
        return json.dumps(data, indent=2, default=str)

    if output_format == "jsonl":
        if isinstance(data, list):
            return "\n".join(json.dumps(item, default=str) for item in data)
        return json.dumps(data, default=str)

    if output_format == "dot" and graph is not None:
        # Simple DOT format for visualization
        lines = ["digraph dbt {", "  rankdir=LR;"]
        for node in graph.nodes():
            attrs = graph.nodes[node]
            label = attrs.get("name", node.split(".")[-1])
            rtype = attrs.get("resource_type", "")
            color = {"model": "lightblue", "source": "lightgreen", "test": "lightyellow"}.get(rtype, "white")
            lines.append(f'  "{node}" [label="{label}" fillcolor="{color}" style="filled"];')
        for u, v in graph.edges():
            lines.append(f'  "{u}" -> "{v}";')
        lines.append("}")
        return "\n".join(lines)

    # Table format
    if not data:
        return "No results found."

    if isinstance(data, dict):
        # Single item - show as key-value pairs
        lines = []
        max_key_len = max(len(str(k)) for k in data.keys())
        for k, v in data.items():
            lines.append(f"{str(k).ljust(max_key_len)} : {v}")
        return "\n".join(lines)

    if isinstance(data, list):
        if not data:
            return "No results found."

        if isinstance(data[0], str):
            # List of strings (node IDs)
            return "\n".join(data)

        if isinstance(data[0], dict):
            # List of dicts - format as table
            columns = list(data[0].keys())
            widths = {}
            for col in columns:
                widths[col] = max(len(str(col)), max(len(str(row.get(col, ""))[:60]) for row in data))

            lines = []
            header = " | ".join(str(col).ljust(widths[col])[:60] for col in columns)
            lines.append(header)
            lines.append("-" * len(header))

            for row in data:
                line = " | ".join(str(row.get(col, ""))[:60].ljust(widths[col]) for col in columns)
                lines.append(line)

            return "\n".join(lines)

    return str(data)


# ============================================================================
# CLI Command Handlers
# ============================================================================


def cmd_nodes(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """List nodes matching criteria."""
    node_ids = find_nodes(
        artifacts.graph,
        pattern=args.pattern if hasattr(args, "pattern") else None,
        resource_type=args.type,
        tag=args.tag,
        schema=args.schema,
        materialized=args.materialized,
    )

    results = []
    for nid in sorted(node_ids):
        attrs = artifacts.graph.nodes[nid]
        results.append(
            {
                "unique_id": nid,
                "name": attrs.get("name", ""),
                "type": attrs.get("resource_type", ""),
                "schema": attrs.get("schema", ""),
                "materialized": attrs.get("materialized", ""),
            }
        )

    return results


def cmd_node(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Show details for a specific node."""
    node_id = resolve_node_id(args.unique_id, artifacts)
    if not node_id:
        return {"error": f"Node not found: {args.unique_id}"}

    # Get graph attributes
    attrs = dict(artifacts.graph.nodes[node_id])

    # Get manifest node details if available
    if node_id in artifacts.manifest.nodes:
        node = artifacts.manifest.nodes[node_id]
        attrs["description"] = node.description
        attrs["path"] = node.original_file_path
        attrs["depends_on"] = node.depends_on_nodes

    # Get catalog info if available
    if artifacts.catalog and node_id in artifacts.catalog.nodes:
        cat_node = artifacts.catalog.nodes[node_id]
        attrs["column_count"] = len(cat_node.columns)

    attrs["upstream_count"] = len(get_upstream(artifacts.graph, node_id))
    attrs["downstream_count"] = len(get_downstream(artifacts.graph, node_id))

    return attrs


def cmd_upstream(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Get upstream dependencies."""
    node_id = resolve_node_id(args.unique_id, artifacts)
    if not node_id:
        return {"error": f"Node not found: {args.unique_id}"}

    depth = args.depth if hasattr(args, "depth") else None
    upstream = get_upstream(artifacts.graph, node_id, depth=depth)

    results = []
    for nid in sorted(upstream):
        attrs = artifacts.graph.nodes[nid]
        results.append(
            {
                "unique_id": nid,
                "name": attrs.get("name", ""),
                "type": attrs.get("resource_type", ""),
            }
        )

    return results


def cmd_downstream(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Get downstream dependents."""
    node_id = resolve_node_id(args.unique_id, artifacts)
    if not node_id:
        return {"error": f"Node not found: {args.unique_id}"}

    depth = args.depth if hasattr(args, "depth") else None
    downstream = get_downstream(artifacts.graph, node_id, depth=depth)

    results = []
    for nid in sorted(downstream):
        attrs = artifacts.graph.nodes[nid]
        results.append(
            {
                "unique_id": nid,
                "name": attrs.get("name", ""),
                "type": attrs.get("resource_type", ""),
            }
        )

    return results


def cmd_path(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Find path between two nodes."""
    source = resolve_node_id(args.source, artifacts)
    target = resolve_node_id(args.target, artifacts)

    if not source:
        return {"error": f"Source node not found: {args.source}"}
    if not target:
        return {"error": f"Target node not found: {args.target}"}

    path = get_path(artifacts.graph, source, target)
    if path is None:
        return {"error": f"No path found from {source} to {target}"}

    results = []
    for i, nid in enumerate(path):
        attrs = artifacts.graph.nodes[nid]
        results.append(
            {
                "step": i,
                "unique_id": nid,
                "name": attrs.get("name", ""),
                "type": attrs.get("resource_type", ""),
            }
        )

    return results


def cmd_roots(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Find root nodes (no upstream)."""
    roots = get_roots(artifacts.graph, resource_type=args.type)
    return sorted(roots)


def cmd_leaves(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Find leaf nodes (no downstream)."""
    leaves = get_leaves(artifacts.graph, resource_type=args.type)
    return sorted(leaves)


def cmd_orphans(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Find orphan models (isolated, no connections)."""
    orphans = get_orphans(artifacts.graph)
    return sorted(orphans)


def cmd_stats(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Show graph statistics."""
    G = artifacts.graph

    # Count by resource type
    type_counts: dict[str, int] = {}
    mat_counts: dict[str, int] = {}
    for node in G.nodes():
        attrs = G.nodes[node]
        rtype = attrs.get("resource_type", "unknown")
        type_counts[rtype] = type_counts.get(rtype, 0) + 1

        mat = attrs.get("materialized")
        if mat:
            mat_counts[mat] = mat_counts.get(mat, 0) + 1

    return {
        "total_nodes": G.number_of_nodes(),
        "total_edges": G.number_of_edges(),
        "nodes_by_type": type_counts,
        "models_by_materialization": mat_counts,
        "root_count": len(get_roots(G)),
        "leaf_count": len(get_leaves(G)),
        "orphan_count": len(get_orphans(G)),
        "is_dag": nx.is_directed_acyclic_graph(G),
        "manifest_generated_at": artifacts.manifest.metadata.generated_at,
        "dbt_version": artifacts.manifest.metadata.dbt_version,
    }


def cmd_columns(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """List columns for a node from catalog."""
    if artifacts.catalog is None:
        return {"error": "No catalog.json found. Run 'dbt docs generate' first."}

    node_id = resolve_node_id(args.unique_id, artifacts)
    if not node_id:
        return {"error": f"Node not found: {args.unique_id}"}

    cat_node = artifacts.catalog.nodes.get(node_id) or artifacts.catalog.sources.get(node_id)
    if not cat_node:
        return {"error": f"Node not in catalog: {node_id}. It may not be materialized."}

    results = []
    for col_name, col in sorted(cat_node.columns.items(), key=lambda x: x[1].index):
        results.append(
            {
                "index": col.index,
                "name": col.name,
                "type": col.type,
                "comment": col.comment or "",
            }
        )

    return results


def cmd_search(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Search nodes by pattern."""
    node_ids = find_nodes(artifacts.graph, pattern=args.pattern, resource_type=args.type)

    results = []
    for nid in sorted(node_ids):
        attrs = artifacts.graph.nodes[nid]
        results.append(
            {
                "unique_id": nid,
                "name": attrs.get("name", ""),
                "type": attrs.get("resource_type", ""),
                "path": attrs.get("path", ""),
            }
        )

    return results


def cmd_compare(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Compare manifest models vs catalog (find unmaterialized)."""
    if artifacts.catalog is None:
        return {"error": "No catalog.json found. Run 'dbt docs generate' first."}

    manifest_models = {
        uid for uid, node in artifacts.manifest.nodes.items() if node.resource_type == "model"
    }
    catalog_nodes = set(artifacts.catalog.nodes.keys())

    in_manifest_only = manifest_models - catalog_nodes
    in_catalog_only = catalog_nodes - manifest_models

    return {
        "manifest_model_count": len(manifest_models),
        "catalog_node_count": len(catalog_nodes),
        "in_manifest_only": sorted(in_manifest_only)[:20],  # Limit output
        "in_manifest_only_count": len(in_manifest_only),
        "in_catalog_only": sorted(in_catalog_only)[:20],
        "in_catalog_only_count": len(in_catalog_only),
    }


def cmd_docs(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """List all docs blocks."""
    results = []
    for uid, doc in sorted(artifacts.manifest.docs.items()):
        # Skip dbt's default overview
        if uid == "doc.dbt.__overview__":
            continue
        results.append(
            {
                "unique_id": uid,
                "name": doc.name,
                "path": doc.original_file_path,
                "content_length": len(doc.block_contents),
            }
        )
    return results


def cmd_doc(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Show a specific docs block content."""
    # Try exact match first
    doc = artifacts.manifest.docs.get(args.doc_id)

    # Try partial match by name
    if not doc:
        for uid, d in artifacts.manifest.docs.items():
            if d.name == args.doc_id or args.doc_id in uid:
                doc = d
                break

    if not doc:
        return {"error": f"Doc block not found: {args.doc_id}"}

    return {
        "unique_id": doc.unique_id,
        "name": doc.name,
        "path": doc.original_file_path,
        "content": doc.block_contents,
    }


def cmd_undocumented(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Find models and sources without descriptions."""
    results = []

    # Check models
    for uid, node in artifacts.manifest.nodes.items():
        if node.resource_type != "model":
            continue
        if args.type and args.type != "model":
            continue

        if not node.description or not node.description.strip():
            results.append(
                {
                    "unique_id": uid,
                    "name": node.name,
                    "type": "model",
                    "path": node.original_file_path,
                    "issue": "no_description",
                }
            )
        elif args.columns:
            # Check for undocumented columns
            for col_name, col_data in node.columns.items():
                col_desc = col_data.get("description", "")
                if not col_desc or not col_desc.strip():
                    results.append(
                        {
                            "unique_id": uid,
                            "name": node.name,
                            "type": "model",
                            "path": node.original_file_path,
                            "issue": f"undocumented_column:{col_name}",
                        }
                    )

    # Check sources
    if not args.type or args.type == "source":
        for uid, source in artifacts.manifest.sources.items():
            if not source.description or not source.description.strip():
                results.append(
                    {
                        "unique_id": uid,
                        "name": source.name,
                        "type": "source",
                        "path": "",
                        "issue": "no_description",
                    }
                )

    return results


def cmd_search_docs(args: argparse.Namespace, artifacts: DbtArtifacts) -> Any:
    """Search across descriptions and doc block content."""
    pattern = args.pattern.lower()
    results = []

    # Search model descriptions
    for uid, node in artifacts.manifest.nodes.items():
        if node.resource_type != "model":
            continue

        # Check model description
        if node.description and pattern in node.description.lower():
            results.append(
                {
                    "unique_id": uid,
                    "name": node.name,
                    "type": "model_description",
                    "match_context": node.description[:100] + ("..." if len(node.description) > 100 else ""),
                }
            )

        # Check column descriptions
        for col_name, col_data in node.columns.items():
            col_desc = col_data.get("description", "")
            if col_desc and pattern in col_desc.lower():
                results.append(
                    {
                        "unique_id": uid,
                        "name": f"{node.name}.{col_name}",
                        "type": "column_description",
                        "match_context": col_desc[:100] + ("..." if len(col_desc) > 100 else ""),
                    }
                )

    # Search source descriptions
    for uid, source in artifacts.manifest.sources.items():
        if source.description and pattern in source.description.lower():
            results.append(
                {
                    "unique_id": uid,
                    "name": source.name,
                    "type": "source_description",
                    "match_context": source.description[:100] + ("..." if len(source.description) > 100 else ""),
                }
            )

    # Search docs blocks
    for uid, doc in artifacts.manifest.docs.items():
        if uid == "doc.dbt.__overview__":
            continue
        if pattern in doc.block_contents.lower():
            # Find the matching line for context
            lines = doc.block_contents.split("\n")
            context = ""
            for line in lines:
                if pattern in line.lower():
                    context = line.strip()[:100]
                    break
            results.append(
                {
                    "unique_id": uid,
                    "name": doc.name,
                    "type": "doc_block",
                    "match_context": context + ("..." if len(context) >= 100 else ""),
                }
            )

    return results


# ============================================================================
# Helpers
# ============================================================================


def resolve_node_id(partial_id: str, artifacts: DbtArtifacts) -> str | None:
    """Resolve a partial node ID to a full unique_id."""
    # Exact match
    if partial_id in artifacts.graph:
        return partial_id

    # Try common prefixes
    for prefix in ["model.", "source.", "test.", "seed.", "snapshot."]:
        full_id = f"{prefix}{artifacts.manifest.metadata.project_name}.{partial_id}"
        if full_id in artifacts.graph:
            return full_id

    # Fuzzy match by name
    for node_id in artifacts.graph.nodes():
        attrs = artifacts.graph.nodes[node_id]
        if attrs.get("name") == partial_id:
            return node_id

    return None


def _format_file_list(files: list[Path], max_show: int = 5) -> str:
    """Format paths relative to project root."""
    formatted = "\n        ".join(f"- {p.relative_to(PROJECT_ROOT)}" for p in files[:max_show] if p.exists())
    if len(files) > max_show:
        formatted += f"\n        ... and {len(files) - max_show} more files"
    return formatted if formatted else "- (none found)"


# ============================================================================
# Main
# ============================================================================


def main(args: argparse.Namespace) -> None:
    """Main entry point."""
    try:
        artifacts = load_artifacts(Path(args.target_dir))
    except FileNotFoundError as e:
        log.error(str(e))
        raise SystemExit(1) from e

    handlers = {
        "nodes": cmd_nodes,
        "node": cmd_node,
        "upstream": cmd_upstream,
        "downstream": cmd_downstream,
        "path": cmd_path,
        "roots": cmd_roots,
        "leaves": cmd_leaves,
        "orphans": cmd_orphans,
        "stats": cmd_stats,
        "columns": cmd_columns,
        "search": cmd_search,
        "compare": cmd_compare,
        "docs": cmd_docs,
        "doc": cmd_doc,
        "undocumented": cmd_undocumented,
        "search-docs": cmd_search_docs,
    }

    handler = handlers.get(args.command)
    if not handler:
        log.error(f"Unknown command: {args.command}")
        raise SystemExit(1)

    result = handler(args, artifacts)

    # Format and output - use print for actual results (not logging)
    output = format_output(result, args.format, artifacts.graph if args.format == "dot" else None)
    print(output)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} - Explore dbt artifacts with graph-based traversal.

        Parses manifest.json and catalog.json from target/, builds a NetworkX
        DAG, and provides commands for exploring model lineage and dependencies.

        INPUTS:
        {_format_file_list(ALL_INPUTS)}

        OUTPUTS:
            (none - read-only exploration)

        Examples:
            uv run {SCRIPT_NAME}.py stats
            uv run {SCRIPT_NAME}.py nodes --type model --materialized incremental
            uv run {SCRIPT_NAME}.py upstream my_model --depth 2
            uv run {SCRIPT_NAME}.py path source.proj.raw.users model.proj.dim_users
        """),
    )

    # Global options
    parser.add_argument("-q", "--quiet", action="store_true", help="Show only errors")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "-f",
        "--format",
        choices=["table", "json", "jsonl", "dot"],
        default="table",
        help="Output format (default: table)",
    )
    parser.add_argument(
        "--target-dir",
        default=str(TARGET_DIR),
        help=f"dbt target directory (default: {TARGET_DIR})",
    )

    subparsers = parser.add_subparsers(dest="command", metavar="COMMAND", help="Available commands")

    # nodes command
    nodes_parser = subparsers.add_parser("nodes", help="List all nodes with optional filters")
    nodes_parser.add_argument("--type", help="Filter by resource type (model, test, source, seed, snapshot)")
    nodes_parser.add_argument("--tag", help="Filter by tag")
    nodes_parser.add_argument("--schema", help="Filter by schema name")
    nodes_parser.add_argument("--materialized", help="Filter by materialization (table, view, incremental, ephemeral)")

    # node command
    node_parser = subparsers.add_parser("node", help="Show details for a specific node")
    node_parser.add_argument("unique_id", help="Node unique_id or name")

    # upstream command
    upstream_parser = subparsers.add_parser("upstream", help="Find upstream dependencies (ancestors)")
    upstream_parser.add_argument("unique_id", help="Node unique_id or name")
    upstream_parser.add_argument("--depth", type=int, help="Limit depth of traversal")

    # downstream command
    downstream_parser = subparsers.add_parser("downstream", help="Find downstream dependents (descendants)")
    downstream_parser.add_argument("unique_id", help="Node unique_id or name")
    downstream_parser.add_argument("--depth", type=int, help="Limit depth of traversal")

    # path command
    path_parser = subparsers.add_parser("path", help="Find shortest path between two nodes")
    path_parser.add_argument("source", help="Source node unique_id or name")
    path_parser.add_argument("target", help="Target node unique_id or name")

    # roots command
    roots_parser = subparsers.add_parser("roots", help="Find root nodes (no upstream dependencies)")
    roots_parser.add_argument("--type", help="Filter by resource type")

    # leaves command
    leaves_parser = subparsers.add_parser("leaves", help="Find leaf nodes (no downstream dependents)")
    leaves_parser.add_argument("--type", help="Filter by resource type")

    # orphans command
    subparsers.add_parser("orphans", help="Find orphan models (no connections)")

    # stats command
    subparsers.add_parser("stats", help="Show graph statistics")

    # columns command
    columns_parser = subparsers.add_parser("columns", help="List columns for a node (requires catalog)")
    columns_parser.add_argument("unique_id", help="Node unique_id or name")

    # search command
    search_parser = subparsers.add_parser("search", help="Search nodes by name pattern")
    search_parser.add_argument("pattern", help="Search pattern (case-insensitive)")
    search_parser.add_argument("--type", help="Filter by resource type")

    # compare command
    subparsers.add_parser("compare", help="Compare manifest vs catalog (find unmaterialized models)")

    # docs command
    subparsers.add_parser("docs", help="List all docs blocks")

    # doc command
    doc_parser = subparsers.add_parser("doc", help="Show a specific docs block content")
    doc_parser.add_argument("doc_id", help="Doc block unique_id or name")

    # undocumented command
    undoc_parser = subparsers.add_parser("undocumented", help="Find models/sources without descriptions")
    undoc_parser.add_argument("--type", choices=["model", "source"], help="Filter by resource type")
    undoc_parser.add_argument("--columns", action="store_true", help="Also check for undocumented columns")

    # search-docs command
    search_docs_parser = subparsers.add_parser("search-docs", help="Search across descriptions and doc blocks")
    search_docs_parser.add_argument("pattern", help="Search pattern (case-insensitive)")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not args.command:
        parser.print_help()
    else:
        main(args)
