---
name: dbt-snowflake
description: Expert assistance with Snowflake connectivity and dbt Cloud. Use when working with Snowflake databases, testing connections, running dbt commands, or debugging environment setup issues.
allowed-tools:
  - Read
  - Grep
  - Glob
  - Bash(.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh *)
  - Bash(.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh *)
user-invocable: true
---

# dbt-Snowflake Skill

This skill provides guidance for working with Snowflake and dbt projects.

## Hypothesis-Driven Data Exploration

When exploring data, follow an iterative question-answer-refine cycle:

### 1. Maintain a Question Queue

Before querying, explicitly track:
- **Open questions** - What are we trying to answer?
- **Hypotheses** - What do we expect to find?
- **Query strategies** - How will we get the data?

Use the TaskCreate/TaskList tools to track questions as tasks when exploration is complex.

### 2. Query and Reveal

Each query reveals new information. After each result:
- **What did we learn?** - Document the finding
- **Does this answer the question?** - Mark complete if yes
- **What new questions emerged?** - Add to the queue

### 3. Critical Analysis Loop

After each query, ask:
- Do the numbers make sense? Cross-reference with other tables.
- Are there discrepancies? (e.g., counts differ between dimension and fact tables)
- What does this mean in business context?
- Should we qualify/caveat this finding?

### 4. Reconciliation Patterns

When exploring multiple related tables:

| Pattern | Example |
|---------|---------|
| **Dimension vs Fact** | Dimension table shows what *could* exist; fact table shows what *happened* |
| **Count discrepancies** | "100 entities defined, 20 with activity" is a finding about data completeness |
| **Source attribution** | Always note which table a metric comes from |

### Example Question Queue

```
Q1: How many customers have multiple orders? [OPEN]
  → Strategy: Count distinct orders per customer in fact_orders

Q2: Which regions have multiple stores? [OPEN]
  → Strategy: Group by region, count distinct stores
  → Caveat: Check both dim_store (defined) and fact_sales (active)

Q3: [SPAWNED from Q2] Why does Region X show 10 stores but only 2 with sales?
  → Strategy: Compare dim_store vs fact_sales for Region X
  → Finding: Data completeness issue - 8 stores have no sales data
```

## Persisting Learnings in dbt

Insights discovered during exploration should be documented for future retrieval. Use dbt's built-in documentation conventions:

### Documentation Options

| Location | Best For | Retrieval |
|----------|----------|-----------|
| **schema.yml `description`** | Model/column purpose, business context | `search-docs` command |
| **docs blocks** (`.md` files) | Reusable reference tables, domain glossaries | `doc <name>` command |
| **`meta`** field | Structured metadata (owner, sla, domain) | Direct manifest query |
| **analyses/** folder | Exploratory SQL with embedded findings | `search <pattern>` command |

### Best Practices

1. **Model descriptions**: Explain the "why" not the "what"
   - Good: "Unified customer activity combining online and in-store transactions for cross-channel analysis"
   - Bad: "Joins transactions from two sources"

2. **Column descriptions**: Focus on business meaning and caveats
   - Good: "Parent organization (e.g., 'Acme Corp'). Note: org_name != physical location - use location_name for individual sites"
   - Bad: "The organization name field"

3. **Docs blocks**: Create for reusable reference information
   ```markdown
   {% docs entity_terminology %}
   | Term | Definition |
   |------|------------|
   | org_name | Parent organization/group |
   | location_name | Individual physical location |
   | dim_location | All defined locations |
   | fact_activity | Locations with recorded activity |
   {% enddocs %}
   ```

4. **Analysis files**: Preserve exploratory SQL with findings as comments
   ```sql
   -- Finding: 10 locations in dim_location for Region X, but only 2 with activity
   -- Implication: 8 locations have no recorded activity in fact_activity
   SELECT region, COUNT(DISTINCT location_id) FROM dim_location GROUP BY 1
   ```

### Querying Documentation

```bash
# Find all documentation mentioning a term
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh search-docs "<term>"

# View a domain glossary
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh doc <doc_name>

# Find models needing documentation
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh undocumented --type model
```

## Environment Setup

### CRITICAL: Credential Loading is USER-ONLY

**The agent must NEVER run any of the following:**

- `eval "$(uv run python .../exportenv.py)"` or any `eval` that loads env vars
- `export SNOWFLAKE_*=...` or any `export` of credentials
- `env | grep SNOW` or any command that prints credentials/env vars
- `source .env` or any command that reads dotenv files
- Any command that loads, exports, prints, or manipulates credentials

Running these commands can load the wrong credentials, overwrite the user's
authenticated session, or leak secrets into the conversation context.

**The user must set up their environment BEFORE starting Claude Code:**

```bash
# User runs these in their terminal BEFORE launching claude:
eval "$(uv run python $(git rev-parse --show-toplevel)/scripts/exportenv.py)"
export DBT_GIT_BRANCH="$(git rev-parse --abbrev-ref HEAD)"
env | grep SNOW  # user verifies their own setup
```

If credentials are not working, tell the user to exit the session, fix their
environment, and restart Claude Code.

### Agent-Safe Connection Verification

These are the ONLY commands the agent may run to check connectivity:

```bash
# Preferred: uses the explore_snowflake.sh script's built-in connection test
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh connection-test

# Alternative: snowflake-cli (reads existing env vars, does not load them)
uvx --from snowflake-cli snow connection test --temporary-connection

# dbt connection check
uv run dbt debug
```

If any of these fail, do NOT attempt to fix or reload credentials. Tell the user:
> Snowflake connection failed. Please check your environment variables are
> loaded correctly and restart the Claude Code session.

### Required Environment Variables

The user's shell session must have these set (per snowflake-cli conventions):
- `SNOWFLAKE_ACCOUNT` (not `SNOWFLAKE_ACCOUNTNAME`)
- `SNOWFLAKE_USER` (not `SNOWFLAKE_USERNAME`)
- `SNOWFLAKE_PRIVATE_KEY_PATH`
- `SNOWFLAKE_ROLE`

## Using Snowflake CLI for Ad-Hoc Queries

The Snowflake CLI can be used for quick one-off queries:

1. **Exploring schemas and tables**:
   ```bash
   uvx --from snowflake-cli snow sql --temporary-connection -q "SHOW SCHEMAS IN DATABASE <db>"
   uvx --from snowflake-cli snow sql --temporary-connection -q "SHOW TABLES IN SCHEMA <db>.<schema>"
   uvx --from snowflake-cli snow sql --temporary-connection -q "DESCRIBE TABLE <db>.<schema>.<table>"
   ```

2. **Sampling data**:
   ```bash
   uvx --from snowflake-cli snow sql --temporary-connection -q "SELECT * FROM <table> LIMIT 10"
   ```

3. **Getting DDL**:
   ```bash
   uvx --from snowflake-cli snow sql --temporary-connection -q "SELECT GET_DDL('TABLE', '<db>.<schema>.<table>')"
   ```

### Self-Discovery via --help

When in doubt about Snowflake CLI capabilities:

```bash
uvx --from snowflake-cli snow --help
uvx --from snowflake-cli snow sql --help
```

## dbt Commands

### Verify dbt Configuration

```bash
uv run dbt debug
```

Validates profiles.yml, Snowflake connection, and project configuration.

### Compile dbt Models

```bash
uv run dbt compile
```

Parses all models, resolves refs and sources, generates compiled SQL without executing.

### Common dbt Commands

```bash
uv run dbt ls                          # List all models
uv run dbt run --select <model_name>   # Run specific model
uv run dbt test                        # Test models
uv run dbt docs generate               # Generate documentation
```

## Troubleshooting Workflow

If commands fail, follow this diagnostic sequence:

1. **Test Snowflake connectivity**: `.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh connection-test`
2. **Verify dbt can connect**: `uv run dbt debug`
3. **If either fails**: Tell the user their credentials are not working and ask them to reload their environment outside of Claude Code and restart the session. Do NOT attempt to reload credentials yourself.

## dbt Artifact Explorer

A graph-based exploration tool for dbt artifacts. Parses `manifest.json` and `catalog.json` from `target/`, builds a NetworkX DAG, and provides commands for exploring model lineage and dependencies.

### Prerequisites

```bash
uv run dbt compile           # Generate manifest.json (required)
uv run dbt docs generate     # Generate catalog.json (optional, for column info)
```

### Quick Start

```bash
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh stats
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh --help
```

### Available Commands

#### Graph Statistics

```bash
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh stats
```

Returns: node counts by type, materialization breakdown, root/leaf/orphan counts, DAG validation.

#### List Nodes

```bash
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh nodes --type model
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh nodes --type model --materialized incremental
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh nodes --schema staging
```

#### Node Details

```bash
# Supports partial name match
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh node <model_name>

# Full unique_id also works
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh node model.<project>.<model_name>
```

#### Lineage Traversal

```bash
# Find upstream dependencies (ancestors)
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh upstream <model_name>
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh upstream <model_name> --depth 2

# Find downstream dependents (descendants)
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh downstream <model_name>

# Find path between two nodes
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh path <source_node> <target_node>
```

#### Discovery Commands

```bash
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh roots              # Root nodes (no upstream)
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh leaves --type model # Leaf nodes (no downstream)
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh orphans            # Isolated models
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh search <pattern>   # Search by name pattern
```

#### Catalog Operations

```bash
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh columns <model_name>  # List columns (requires catalog.json)
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh compare               # Compare manifest vs catalog
```

#### Documentation Commands

```bash
# List all docs blocks
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh docs

# View a specific docs block content
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh doc <doc_name>

# Find models/sources without descriptions
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh undocumented --type model
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh undocumented --columns  # Also check column docs

# Search across all descriptions and doc blocks
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh search-docs "<pattern>"
```

### Output Formats

```bash
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh stats                    # Table (default)
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh -f json stats            # JSON
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh -f jsonl nodes           # JSONL
.claude/skills/dbt-snowflake/scripts/explore_dbt_artifacts.sh -f dot upstream <model>  # DOT (GraphViz)
```

### Technical Details

```
explore_dbt_artifacts.sh (bash wrapper)
       │
       └── uv run explore_dbt_artifacts.py (PEP-723 script)
                    │
                    ├── Loads target/manifest.json
                    ├── Loads target/catalog.json (optional)
                    └── Builds NetworkX DiGraph from parent_map/child_map
```

Dependencies (PEP-723):
```python
# /// script
# requires-python = ">=3.12"
# dependencies = ["networkx>=3.0"]
# ///
```

## Snowflake Data Explorer

An efficient data exploration tool using the Snowflake Python connector. **Use this instead of multiple `uvx --from snowflake-cli snow sql` commands** for exploration tasks.

### Why Use This Tool

Each CLI invocation creates a new connection and consumes tokens. The explorer script:
- Uses a **single persistent connection** for multiple queries
- Returns **structured, compact output** (table, JSON, JSONL formats)
- Provides **common exploration patterns** as single commands
- **Reduces token consumption** significantly for exploration tasks

### Prerequisites

Snowflake environment variables must already be loaded in the user's shell
session BEFORE starting Claude Code. See "Environment Setup" above.

Verify connectivity before running exploration commands:
```bash
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh connection-test
```

### Quick Start

```bash
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh --help
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh connection-test
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh tables <DATABASE>.<SCHEMA>
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh columns <DATABASE>.<SCHEMA>.<TABLE>
```

### Available Commands

#### Schema Discovery

```bash
# List schemas in a database
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh schemas <DATABASE>

# List tables in a schema with row counts
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh tables <DATABASE>.<SCHEMA>

# Search for tables/columns matching a pattern
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh search "<pattern>" -d <DATABASE>
```

#### Table Exploration

```bash
# Get column names, types, nullability
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh columns <DATABASE>.<SCHEMA>.<TABLE>

# Get row count and cardinality of each column (first 20)
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh profile <DATABASE>.<SCHEMA>.<TABLE>

# Sample rows (default 10)
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh sample <DATABASE>.<SCHEMA>.<TABLE> [LIMIT]

# Get distinct values of a column with counts
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh distinct <DATABASE>.<SCHEMA>.<TABLE> <COLUMN>
```

#### Running SQL

```bash
# Run arbitrary SQL
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh query "SELECT COUNT(*) FROM <table>"

# Execute SQL from file
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh file <path/to/query.sql>
```

### Output Formats

```bash
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh tables <DB>.<SCHEMA>           # Table (default)
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh -f json tables <DB>.<SCHEMA>   # JSON
.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh -f jsonl columns <DB>.<SCHEMA>.<TABLE>  # JSONL
```

### Common Exploration Workflow

1. **Schema overview**: `.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh -q tables <DB>.<SCHEMA>`
2. **Table structure**: `.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh -q columns <DB>.<SCHEMA>.<TABLE>`
3. **Data quality**: `.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh -q profile <DB>.<SCHEMA>.<TABLE>`
4. **Sample data**: `.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh -q sample <DB>.<SCHEMA>.<TABLE> 5`
5. **Column values**: `.claude/skills/dbt-snowflake/scripts/explore_snowflake.sh -q distinct <DB>.<SCHEMA>.<TABLE> <COLUMN>`

### Technical Details

```
explore_snowflake.sh (bash wrapper)
       │
       └── uv run explore_snowflake.py (PEP-723 script)
                    │
                    └── snowflake-connector-python (persistent connection)
```

Dependencies (PEP-723):
```python
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "snowflake-connector-python>=3.6.0",
#   "cryptography>=42.0.0",
# ]
# ///
```

#### Environment Variables

Required:
- `SNOWFLAKE_ACCOUNT`
- `SNOWFLAKE_USER`
- `SNOWFLAKE_PRIVATE_KEY_PATH`

Optional:
- `SNOWFLAKE_ROLE`
- `SNOWFLAKE_WAREHOUSE`
- `SNOWFLAKE_DATABASE`
- `SNOWFLAKE_SCHEMA`
