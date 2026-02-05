# dbt Explorer Script Specification

## Overview

A Python script to load, parse, and explore dbt artifacts (`manifest.json`, `catalog.json`) with graph-based traversal capabilities.

## User Requirements

> I want a python script that can load in the targets/ artifacts and follows common Python script best practices (PEP-723 inline script metadata, argparse CLI, structured logging, dataclasses for schema)
>
> The script can:
> - read targets/manifest.json
> - read targets/catalog.json
> - Define dataclasses for each Recursive level of these artifacts.
>   - For example catalog.json appears to have 4 root keys metadata, nodes, sources, errors. So we should create CatalogMetadata, CatalogNode, CatalogSource, CatalogError (The respective collections being `CatalogNodes = dict[str, CatalogNode]` etc)
> - build your own internal NetworkX graph data structure
> - The script has a self documented syntax that we can call to perform graph search operations to pull up this extra data which is not always accessible through the existing dbt CLI commands.

## Artifact Schemas

### manifest.json

Root keys:
- `metadata` - dbt version info, project info
- `nodes` - models, tests, seeds, snapshots (keyed by unique_id like `model.my_project.my_model`)
- `sources` - source definitions (keyed by unique_id like `source.my_project.raw.my_table`)
- `macros` - macro definitions
- `docs` - doc blocks
- `exposures` - exposure definitions
- `metrics` - metric definitions
- `groups` - group definitions
- `selectors` - selector definitions
- `disabled` - disabled nodes
- `parent_map` - node -> list of parent unique_ids
- `child_map` - node -> list of child unique_ids
- `group_map` - group memberships
- `saved_queries` - saved queries
- `semantic_models` - semantic layer models
- `unit_tests` - unit test definitions

Node keys (model example):
- `database`, `schema`, `name`, `alias`
- `resource_type` - model, test, seed, snapshot, source, etc.
- `unique_id` - canonical identifier
- `fqn` - fully qualified name array
- `path`, `original_file_path`
- `config` - materialization, tags, etc.
- `tags`, `description`, `columns`, `meta`
- `depends_on` - `{macros: [], nodes: []}`
- `refs`, `sources`
- `compiled_code`, `raw_code`

### catalog.json

Root keys:
- `metadata` - dbt version info
- `nodes` - materialized objects with column info (keyed by unique_id)
- `sources` - source tables with column info
- `errors` - any errors during catalog generation

Node keys:
- `metadata` - owner, type, schema, name, database
- `columns` - dict of column name -> {type, index, name, comment}
- `stats` - table statistics
- `unique_id`

## Dataclass Design

```python
# Catalog types
@dataclass
class CatalogColumn:
    name: str
    type: str
    index: int
    comment: str | None = None

@dataclass
class CatalogMetadata:
    dbt_schema_version: str
    dbt_version: str
    generated_at: str
    invocation_id: str
    env: dict[str, str]

@dataclass
class CatalogNodeMetadata:
    type: str
    schema_: str  # 'schema' is reserved
    name: str
    database: str
    owner: str | None = None

@dataclass
class CatalogNode:
    unique_id: str
    metadata: CatalogNodeMetadata
    columns: dict[str, CatalogColumn]
    stats: dict[str, Any]

@dataclass
class CatalogSource:
    unique_id: str
    metadata: CatalogNodeMetadata
    columns: dict[str, CatalogColumn]
    stats: dict[str, Any]

@dataclass
class Catalog:
    metadata: CatalogMetadata
    nodes: dict[str, CatalogNode]
    sources: dict[str, CatalogSource]
    errors: list[str] | None

# Manifest types (similar pattern)
@dataclass
class ManifestMetadata:
    dbt_schema_version: str
    dbt_version: str
    generated_at: str
    invocation_id: str
    project_name: str
    project_id: str | None
    adapter_type: str
    env: dict[str, str]

@dataclass
class ManifestNode:
    unique_id: str
    resource_type: str
    database: str
    schema_: str
    name: str
    alias: str | None
    fqn: list[str]
    path: str
    original_file_path: str
    config: dict[str, Any]
    tags: list[str]
    description: str
    columns: dict[str, Any]
    depends_on: dict[str, list[str]]
    refs: list[list[str]]
    sources: list[list[str]]
    raw_code: str | None = None
    compiled_code: str | None = None

@dataclass
class ManifestSource:
    unique_id: str
    database: str
    schema_: str
    name: str
    identifier: str
    description: str
    loader: str
    tables: list[str] | None = None

@dataclass
class Manifest:
    metadata: ManifestMetadata
    nodes: dict[str, ManifestNode]
    sources: dict[str, ManifestSource]
    macros: dict[str, Any]
    parent_map: dict[str, list[str]]
    child_map: dict[str, list[str]]
    # ... other fields as needed
```

## CLI Commands

### Graph Operations

```bash
# List all nodes with optional filters
./explore_dbt_artifacts.sh nodes [--type model|test|seed|source] [--tag TAG] [--schema SCHEMA]

# Show node details
./explore_dbt_artifacts.sh node <unique_id>

# Find upstream dependencies (parents)
./explore_dbt_artifacts.sh upstream <unique_id> [--depth N]

# Find downstream dependents (children)
./explore_dbt_artifacts.sh downstream <unique_id> [--depth N]

# Find path between two nodes
./explore_dbt_artifacts.sh path <from_id> <to_id>

# Find all roots (nodes with no parents)
./explore_dbt_artifacts.sh roots [--type model]

# Find all leaves (nodes with no children)
./explore_dbt_artifacts.sh leaves [--type model]

# Find orphan models (no refs, no downstream)
./explore_dbt_artifacts.sh orphans

# Show graph statistics
./explore_dbt_artifacts.sh stats
```

### Catalog Operations

```bash
# List columns for a node
./explore_dbt_artifacts.sh columns <unique_id>

# Search for column by name pattern
./explore_dbt_artifacts.sh find-column <pattern>

# Compare manifest vs catalog (find unmaterialized models)
./explore_dbt_artifacts.sh compare
```

### Search Operations

```bash
# Search nodes by name pattern
./explore_dbt_artifacts.sh search <pattern> [--field name|description|path]

# Find models by materialization
./explore_dbt_artifacts.sh materialized <incremental|table|view|ephemeral>
```

## Output Formats

Support multiple output formats via `-f/--format`:
- `table` (default) - human-readable table
- `json` - JSON object
- `jsonl` - newline-delimited JSON
- `dot` - GraphViz DOT format (for graph commands)

## Implementation Notes

### NetworkX Graph Construction

```python
import networkx as nx

def build_graph(manifest: Manifest) -> nx.DiGraph:
    G = nx.DiGraph()

    # Add all nodes with attributes
    for unique_id, node in manifest.nodes.items():
        G.add_node(unique_id, **{
            'resource_type': node.resource_type,
            'schema': node.schema_,
            'name': node.name,
            'materialized': node.config.get('materialized'),
            'tags': node.tags,
        })

    # Add edges from parent_map
    for child_id, parent_ids in manifest.parent_map.items():
        for parent_id in parent_ids:
            G.add_edge(parent_id, child_id)

    return G
```

### Graph Queries

```python
# Upstream (all ancestors)
ancestors = nx.ancestors(G, node_id)

# Downstream (all descendants)
descendants = nx.descendants(G, node_id)

# Shortest path
path = nx.shortest_path(G, source_id, target_id)

# Depth-limited BFS
subgraph = nx.bfs_tree(G, node_id, depth_limit=N)

# Topological sort (execution order)
order = list(nx.topological_sort(G))

# Find cycles (should be none in valid DAG)
cycles = list(nx.simple_cycles(G))
```

## File Locations

- Script: `.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.py`
- Wrapper: `.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh`
- Spec: `.claude/skills/dbt-snowflake/specs/dbt-explorer-script.md` (this file)

## Dependencies (PEP-723)

```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "networkx>=3.0",
# ]
# ///
```

## dbt Graph Selector Syntax Support

Support dbt's native graph selector syntax for complex node selection. This enables the same selection patterns used in `dbt run --select` and `dbt ls --select`.

Reference: https://docs.getdbt.com/reference/node-selection/syntax

### Graph Operators

| Operator | Syntax | Description |
|----------|--------|-------------|
| Plus (upstream) | `+model_name` | Select model and all ancestors |
| Plus (downstream) | `model_name+` | Select model and all descendants |
| Plus (both) | `+model_name+` | Select model, ancestors, and descendants |
| N-plus (upstream) | `2+model_name` | Select model and ancestors up to N levels |
| N-plus (downstream) | `model_name+2` | Select model and descendants up to N levels |
| At | `@model_name` | Select model, ancestors, AND descendants of ancestors |

### Method Selectors

| Method | Syntax | Description |
|--------|--------|-------------|
| Tag | `tag:my_tag` | Nodes with specific tag |
| Config | `config.materialized:incremental` | Nodes with config value |
| Path | `path:models/staging` | Nodes in path (supports wildcards) |
| Package | `package:my_package` | Nodes from package |
| Resource type | `resource_type:model` | Filter by type |
| Source | `source:raw.users` | Source nodes |
| Exposure | `exposure:my_dashboard` | Exposure nodes |
| Metric | `metric:revenue` | Metric nodes |
| FQN | `fqn:staging.users` | Match fully qualified name |
| File | `file:models/staging/stg_users.sql` | Match by file path |
| State | `state:modified` | Compare to previous state |
| Test type | `test_type:singular` | Filter tests |
| Test name | `test_name:not_null` | Filter by test name |

### Set Operations

| Operation | Syntax | Description |
|-----------|--------|-------------|
| Union | `model_a model_b` | Select both (space-separated) |
| Union | `model_a,model_b` | Select both (comma-separated) |
| Intersection | `model_a,+model_b` | Must match both conditions |
| Exclusion | `--exclude model_name` | Remove from selection |

### Wildcards

| Pattern | Description |
|---------|-------------|
| `*` | Match any characters |
| `stg_*` | All nodes starting with `stg_` |
| `*_daily` | All nodes ending with `_daily` |

### CLI Integration

```bash
# New 'select' command using dbt selector syntax
./explore_dbt_artifacts.sh select "+dim_date"                    # dim_date and all ancestors
./explore_dbt_artifacts.sh select "dim_date+"                    # dim_date and all descendants
./explore_dbt_artifacts.sh select "+dim_date+"                   # dim_date and full lineage
./explore_dbt_artifacts.sh select "2+dim_date"                   # dim_date and 2 levels of ancestors
./explore_dbt_artifacts.sh select "@dim_date"                    # dim_date, ancestors, and their descendants

# Method selectors
./explore_dbt_artifacts.sh select "tag:finance"                  # All nodes tagged 'finance'
./explore_dbt_artifacts.sh select "config.materialized:incremental"  # All incremental models
./explore_dbt_artifacts.sh select "path:models/staging/*"        # All staging models
./explore_dbt_artifacts.sh select "resource_type:source"         # All sources

# Combining selectors
./explore_dbt_artifacts.sh select "tag:finance config.materialized:table"  # Union
./explore_dbt_artifacts.sh select "+stg_users+" --exclude "test_*"         # With exclusion

# Complex selections
./explore_dbt_artifacts.sh select "+dim_date+ tag:core"          # Full lineage of dim_date OR tagged core
./explore_dbt_artifacts.sh select "path:models/marts/*" --exclude "tag:deprecated"
```

### Implementation Notes

#### Selector Parser

```python
import re
from dataclasses import dataclass
from enum import Enum

class SelectorMethod(Enum):
    TAG = "tag"
    CONFIG = "config"
    PATH = "path"
    PACKAGE = "package"
    RESOURCE_TYPE = "resource_type"
    SOURCE = "source"
    FQN = "fqn"
    FILE = "file"
    # ... etc

@dataclass
class GraphSelector:
    """Parsed graph selector."""
    node_pattern: str
    upstream_depth: int | None = None      # None = unlimited, 0 = none
    downstream_depth: int | None = None    # None = unlimited, 0 = none
    at_operator: bool = False              # @ operator
    method: SelectorMethod | None = None
    method_value: str | None = None

def parse_selector(selector: str) -> GraphSelector:
    """Parse a dbt selector string into a GraphSelector object.

    Examples:
        "+model_name"     -> upstream_depth=None (all), downstream_depth=0
        "model_name+"     -> upstream_depth=0, downstream_depth=None (all)
        "2+model_name"    -> upstream_depth=2, downstream_depth=0
        "model_name+3"    -> upstream_depth=0, downstream_depth=3
        "+model_name+"    -> upstream_depth=None, downstream_depth=None
        "@model_name"     -> at_operator=True
        "tag:finance"     -> method=TAG, method_value="finance"
    """
    # Implementation here
    pass

def apply_selector(graph: nx.DiGraph, selector: GraphSelector) -> set[str]:
    """Apply a parsed selector to the graph, returning matching node IDs."""
    pass

def apply_selectors(
    graph: nx.DiGraph,
    selectors: list[str],
    exclude: list[str] | None = None
) -> set[str]:
    """Apply multiple selectors (union) with optional exclusions."""
    included = set()
    for sel_str in selectors:
        selector = parse_selector(sel_str)
        included |= apply_selector(graph, selector)

    if exclude:
        for excl_str in exclude:
            excl_selector = parse_selector(excl_str)
            included -= apply_selector(graph, excl_selector)

    return included
```

#### Method Selector Matching

```python
def matches_method_selector(
    graph: nx.DiGraph,
    node_id: str,
    method: SelectorMethod,
    value: str
) -> bool:
    """Check if a node matches a method selector."""
    attrs = graph.nodes[node_id]

    if method == SelectorMethod.TAG:
        return value in attrs.get("tags", [])

    elif method == SelectorMethod.CONFIG:
        # Handle dotted config paths like "config.materialized:incremental"
        config_path, config_value = value.split(":", 1) if ":" in value else (value, None)
        # Navigate config dict...
        pass

    elif method == SelectorMethod.PATH:
        import fnmatch
        return fnmatch.fnmatch(attrs.get("path", ""), value)

    elif method == SelectorMethod.RESOURCE_TYPE:
        return attrs.get("resource_type") == value

    # ... other methods
```

#### @ Operator Implementation

The `@` operator selects a node, all its ancestors, AND all descendants of those ancestors:

```python
def apply_at_operator(graph: nx.DiGraph, node_id: str) -> set[str]:
    """Apply @ operator: node + ancestors + descendants of ancestors."""
    result = {node_id}

    # Get all ancestors
    ancestors = nx.ancestors(graph, node_id)
    result |= ancestors

    # Get descendants of all ancestors (including the node itself)
    for ancestor in ancestors | {node_id}:
        result |= nx.descendants(graph, ancestor)

    return result
```

### Testing the Selector Parser

```python
def test_parse_selector():
    # Graph operators
    assert parse_selector("+model").upstream_depth is None
    assert parse_selector("+model").downstream_depth == 0
    assert parse_selector("model+").downstream_depth is None
    assert parse_selector("2+model").upstream_depth == 2
    assert parse_selector("model+3").downstream_depth == 3
    assert parse_selector("+model+").upstream_depth is None
    assert parse_selector("+model+").downstream_depth is None
    assert parse_selector("@model").at_operator is True

    # Method selectors
    assert parse_selector("tag:finance").method == SelectorMethod.TAG
    assert parse_selector("tag:finance").method_value == "finance"
    assert parse_selector("config.materialized:incremental").method == SelectorMethod.CONFIG
```

## Success Criteria

1. Script loads manifest.json and catalog.json from target/
2. Dataclasses defined for all major artifact types
3. NetworkX DiGraph built from parent_map/child_map
4. CLI provides graph traversal commands (upstream, downstream, path, roots, leaves)
5. Output formats: table, json, jsonl
6. Self-documenting --help with examples
7. Bash wrapper enables `uv run` invocation
8. **dbt graph selector syntax support:**
   - Graph operators: `+`, `N+`, `+N`, `@`
   - Method selectors: `tag:`, `config.X:`, `path:`, `resource_type:`, etc.
   - Set operations: union (space/comma), exclusion (`--exclude`)
   - Wildcard patterns: `*`, `stg_*`, `*_daily`
   - `select` command that accepts selector strings
