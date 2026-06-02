---
name: introspect
description: Introspect Claude Code sessions - query conversation history, tool usage, event trees, and costs. Use when reviewing past sessions, debugging failures, or recovering user intent post-compaction.
user-invocable: true
---

# Claude Code Introspection

Self-introspection and analysis of Claude Code sessions.

## Current Session ID

```
${CLAUDE_SESSION_ID}
```

## Quick Start

```bash
# Most recently updated session for this project (infers project from CWD)
.claude/skills/introspect/scripts/introspect_sessions.sh sessions -n 1

# All events in the current session, flat chronological order
.claude/skills/introspect/scripts/introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all -n 20

# Tool usage events only
.claude/skills/introspect/scripts/introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all -t tool_use

# Per-agent summary (costs, token totals, event counts — includes subagents)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --summary

# Traverse backwards from most recent event (graph mode, no UUID needed)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse ${CLAUDE_SESSION_ID}

# Traverse ancestors of a specific event
.claude/skills/introspect/scripts/introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} UUID --direction ancestors

# All projects
.claude/skills/introspect/scripts/introspect_sessions.sh projects

# Get help
.claude/skills/introspect/scripts/introspect_sessions.sh --help
```

**Project ID inference:** All commands infer the project from the current working directory when `--project` is not set. `sessions` also infers its positional `project_id` the same way.

**Note:** When supplying an explicit project ID starting with `-`, use the `--` separator: `sessions -n 5 -- -Users-...`

## Session Data Location

```
~/.claude/projects/{project-path-kebab-cased}/{session_uuid}.jsonl
~/.claude/projects/{project-path-kebab-cased}/{session_uuid}/*.jsonl  # subagent files
```

## Message Kinds (9 types)

Events carry a `msg_kind` column for fine-grained filtering (use with `-t`):

| `msg_kind` | Description |
|---|---|
| `human` | User-typed prompts (string content) |
| `task_notification` | Injected `<task-notification>` callbacks |
| `tool_result` | Tool execution results |
| `user_text` | User messages with text/other content blocks |
| `meta` | System-injected context (`isMeta=true`) |
| `assistant_text` | Assistant prose responses |
| `thinking` | Claude's thinking blocks |
| `tool_use` | Tool call requests |
| `other` | Progress, system, queue-operation events |

**Subagent prefix:** events in a subagent context (sidechain or `subagent`/`agent_root`
file) carry a `subagent-` prefix on `msg_kind` (e.g. `subagent-tool_use`). Strip the
prefix to match on the base kind; filter `WHERE msg_kind LIKE 'subagent-%'` for
subagent-only activity.

## Cache

SQLite cache is at:

```
~/.claude/cache/introspect_sessions.db
```

Every query auto-updates stale files before executing. Control with global flags:

```bash
--cache-frozen    # Skip update, use existing cache as-is
--cache-rebuild   # Wipe and re-ingest all files before query
```

→ See [resources/cache.md](resources/cache.md) for full schema and management commands.

### Fallback Cascade

When something is broken, escalate through these rungs in order — each one drops a dependency
of the rung above it:

1. **Primary** — `introspect_sessions.sh …` (Python CLI + SQLite cache). Use this normally.
2. **If the CLI errors but the cache DB is intact** — query the cache directly with `sqlite3`.
   Drops the Python/`uv` layer; keeps the cache.
3. **If the cache is stale, won't rebuild, or is missing/corrupt — *or* `uv`/Python itself is
   unavailable** — query the raw `*.jsonl` files directly with the **DuckDB CLI** (the
   `--duckdb` mode below). Drops both the Python layer and the cache. This is the deepest rung:
   its only dependencies are `bash` and the `duckdb` binary, so it survives every failure of
   the rungs above it.

**Rung 2 — direct SQLite** (cache DB intact, CLI broken):

```bash
sqlite3 ~/.claude/cache/introspect_sessions.db

# Key tables: events, sessions, projects, source_files, event_edges
sqlite3 ~/.claude/cache/introspect_sessions.db \
  "SELECT uuid, msg_kind, timestamp, substr(message_content,1,120)
   FROM events WHERE session_id = 'SESSION_ID'
   ORDER BY timestamp LIMIT 20;"

# Full-text search fallback
sqlite3 ~/.claude/cache/introspect_sessions.db \
  "SELECT e.uuid, e.msg_kind, e.timestamp, snippet(events_fts,-1,'>>>','<<<','...',20)
   FROM events_fts
   JOIN events e ON e.rowid = events_fts.rowid
   WHERE events_fts MATCH 'your search term'
   LIMIT 20;"
```

**Rung 3 — DuckDB on raw JSONL:** use the `--duckdb` mode documented in the next section.

→ See [resources/duckdb-fallback.md](resources/duckdb-fallback.md) for verified DuckDB recipes
(sessions, events, prompts, search, **requestId-deduped** cost) and the field mapping.

## DuckDB Fallback Mode (`--duckdb`)

Invoke the skill as **`/introspect --duckdb <subcommand> [args]`** to skip the cache and the
Python script entirely and answer from the raw JSONL via the DuckDB CLI. Strip the `--duckdb`
token and route the rest to the pure-bash helper:

```bash
# Routing contract: /introspect --duckdb <rest>  →
.claude/skills/introspect/scripts/introspect_duckdb.sh <rest>
```

Subcommands mirror the primary tool (project inferred from CWD; `-p ID` / `--all` to override,
`--subagents` to include nested files, `-f json` for JSON):

```bash
SH=.claude/skills/introspect/scripts/introspect_duckdb.sh
$SH sessions -n 10                 # sessions, most-recent first
$SH events  SESSION_ID -t tool_use    # chronological events; -t filters by msg_kind
$SH prompts SESSION_ID             # GENUINE human prompts only (see msg_kind note below)
$SH prompts SESSION_ID --raw       # …or every string-content user event (slash cmds, caveats)
$SH search "some text" --human     # search ONLY what you typed (drops tool/wrapper noise)
$SH kinds                          # msg_kind distribution + genuine-human count (sanity check)
$SH cost    [SESSION_ID]           # requestId-deduped cost rollup by model family
$SH sql "SELECT msg_kind, COUNT(*) FROM events GROUP BY 1"   # raw SQL over the `events` view
$SH --help
```

**`msg_kind` classification is reproduced in SQL.** The `events` view adds three computed
columns that mirror `introspect_sessions.py`:

- `msg_kind` — the full 9-kind classification, `subagent-` prefixed for sidechain / nested
  subagent events. Validated against the cache: **every message-bearing kind matches exactly**
  (only the `other` system-noise bucket may diverge).
- `text` — the unwrapped scalar string for string-content events (NULL for block arrays).
- `is_human_prompt` — **TRUE only for genuine user typing.** This is stricter than
  `msg_kind = 'human'`, which still includes slash-command expansions (`<command-name>`,
  `<command-message>`), `<task-notification>`, `<local-command-caveat>`, bash-mode tags, etc.
  Use `--human` on `events`/`search`, or `prompts` (which implies it), to get only what a human
  actually typed. `-t/--kind KIND` filters by any `msg_kind` (matches the `subagent-` variant too).

**Why bash, not Python:** this is the rung that must work when `uv`/Python is broken, so the
helper depends only on `bash` + `duckdb` — never on the toolchain it is rescuing. Every
subcommand defines a DuckDB view named `events` over the JSONL glob, so `sql` passthroughs can
`SELECT … FROM events` (including `msg_kind` / `text` / `is_human_prompt`) too.

**Caveats vs. the primary tool:** no cross-agent `event_edges` traversal and no knowledge
graph (cache-only features). You **must** dedup by `requestId` before summing tokens/cost (the
`cost` subcommand already does); see
[resources/duckdb-fallback.md](resources/duckdb-fallback.md).

## Knowledge Graph

The cache hosts a resolved-entity knowledge graph (`nodes`, `edges`,
`entity_clusters`, `leiden_communities`, …) over the prompt history. Build it with
`cache update`/`rebuild` (embeddings enabled); query the tables directly.

→ See [resources/kg.md](resources/kg.md) for tables, query recipes, and update commands.

## Command Reference

| Command | Description |
|---|---|
| `traverse SESSION --all` | Flat chronological event list with filtering (`-t`, `--since`, `-n`, `--offset`, `--no-content`) |
| `traverse SESSION --summary` | Per-agent aggregated stats (costs, tokens, event counts — includes subagents) |
| `traverse SESSION [UUID]` | Ancestor/descendant graph walk; `--detail full` for single-event detail |
| `sessions -- PROJECT` | List sessions for a project |
| `search "pattern"` | FTS5 cross-session search |
| `project-id SESSION` | Resolve project ID from session ID |
| `cache {init,status,update,rebuild,clear}` | Manual cache management |
| `--duckdb {sessions,events,prompts,search,kinds,cost,sql}` | **Fallback** — query raw JSONL via DuckDB (no cache, no Python); derives `msg_kind` + `--human` filter. See [DuckDB Fallback Mode](#duckdb-fallback-mode---duckdb) |

→ See [resources/commands.md](resources/commands.md) for full options and examples.

## Output Formats

Default is JSON. Override with `-f/--format`:

```bash
-f json    # Default — pipe to jq
-f table   # Human-readable
-f jsonl   # One object per line
```

Common jq patterns:
```bash
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all -t tool_use | jq '.[] | .content'
introspect_sessions.sh sessions -- PROJECT_ID | jq '.[0].session_id'

# Cost queries (every event has token_rate, billable_tokens, total_cost_usd)
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all | jq '[.[].total_cost_usd] | add'
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all | jq 'sort_by(-.total_cost_usd) | .[:5]'

# Per-agent cost breakdown
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --summary | jq 'sort_by(-.total_cost_usd)'
```

**Analytics fields (tokenometrics).** Events: `context_ratio`, `is_response_head`,
`response_duration_ms`, derived `tps` (on heads). Sessions: `avg_tps`, `total_idle_ms`,
`total_active_ms`, `peak_context_ratio`. Definitions: [README](README.md#analytics-fields-tokenometrics).

```bash
sqlite3 ~/.claude/cache/introspect_sessions.db \
  "SELECT session_id, ROUND(peak_context_ratio,3) AS peak, total_output_tokens, ROUND(avg_tps,1) AS tps
   FROM sessions ORDER BY peak DESC LIMIT 10;"
```

## Resources

- [README.md](README.md) — human-facing explainer: overview, data model (ERD), analytics fields, cost model
- [resources/cache.md](resources/cache.md) — cache flags, management commands, column quick-reference, SQL fallback recipes
- [resources/duckdb-fallback.md](resources/duckdb-fallback.md) — **fallback** when the cache is stale/broken or the script won't run: query raw JSONL directly with the DuckDB CLI
- [resources/kg.md](resources/kg.md) — knowledge-graph tables, query recipes, update commands
- [resources/commands.md](resources/commands.md) — Full command reference with all options
- [resources/use-cases.md](resources/use-cases.md) — Workflows, post-compaction recovery, architecture, JSONL schema
