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

**If the CLI fails**, fall back to direct SQLite queries:

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

→ See [resources/cache.md](resources/cache.md) for full schema and management commands.

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
- [resources/kg.md](resources/kg.md) — knowledge-graph tables, query recipes, update commands
- [resources/commands.md](resources/commands.md) — Full command reference with all options
- [resources/use-cases.md](resources/use-cases.md) — Workflows, post-compaction recovery, architecture, JSONL schema
