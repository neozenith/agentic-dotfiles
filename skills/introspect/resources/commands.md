# Command Reference

All commands use the bash wrapper:
```
.claude/skills/introspect/scripts/introspect_sessions.sh [global-flags] COMMAND [args]
```

## sessions

```bash
# Infer project from CWD — most recently active session
.claude/skills/introspect/scripts/introspect_sessions.sh sessions -n 1

# Most recent N sessions for current project
.claude/skills/introspect/scripts/introspect_sessions.sh sessions -n 20 --since 7d

# Explicit project ID (use -- prefix because IDs start with -)
.claude/skills/introspect/scripts/introspect_sessions.sh sessions -n 20 --since 7d -- PROJECT_ID
```

`project_id` is inferred from the current working directory when omitted — results are sorted by `last_timestamp DESC`, so `-n 1` returns the most recently updated session for this project.

Note: `--` is only needed when supplying an explicit project ID that starts with a hyphen.

## search

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh search "error pattern" -n 20
.claude/skills/introspect/scripts/introspect_sessions.sh search "benchmark" --since 1h -t human
.claude/skills/introspect/scripts/introspect_sessions.sh search "implement" -t human --since 7d
```

Uses FTS5 syntax. Options: `-t MSG_KIND [...]`, `-n LIMIT`, `--since TIME`.

## traverse

`traverse` is the primary command for sub-selecting events from a session. It has three modes:

### Flat mode: `--all`

Returns all events in the session in flat chronological order. Equivalent to the former `turns` command.

```bash
# All events, most recent 20
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --all -n 20

# Filter by msg_kind
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --all -t tool_use

# Paginate (skip first 50, then next 20)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --all --offset 50 -n 20

# Time-bounded slice
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --all --since 1h

# Omit message content (faster for token/cost analysis)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --all --no-content

# Full raw JSON for each event
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --all --detail full
```

Flat mode options:
- `--all` — enable flat chronological mode
- `-t, --types MSG_KIND [...]` — filter by msg_kind (human, assistant_text, tool_use, tool_result, thinking, meta, user_text, task_notification, other)
- `--since TIME` / `--until TIME` — ISO or relative (`1h`, `30m`, `7d`, `2w`)
- `-n, --limit N` — max events to return
- `--offset N` — skip first N events (for pagination)
- `--no-content` — exclude message content (returns token/cost fields only)
- `--detail {normal,full}` — `normal` returns key fields + parsed content (default); `full` adds `raw_json` and `message_json`

### Summary mode: `--summary`

Returns per-agent aggregated stats — event counts, token totals, and costs — for all agents and subagents in the session. Equivalent to the former `agents` command, but with accurate cost calculation using stored `billable_tokens`.

```bash
# Per-agent token and cost breakdown
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --summary

# Sort by cost descending
.claude/skills/introspect/scripts/introspect_sessions.sh -f json traverse SESSION_ID --summary | jq 'sort_by(-.total_cost_usd)'
```

Returns per-agent: `agent_id`, `agent_slug`, `is_sidechain`, `first_event`, `last_event`, `event_count`, `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`, `total_billable_tokens`, `total_cost_usd`.

Summary mode options:
- `--summary` — enable per-agent aggregation mode
- `-p, --project PROJECT` — restrict to events for a specific project_id

### Graph traversal mode (default)

Walks the `event_edges` graph via recursive CTE. Used for tracing causality — "how did we get here?" or "what did this event spawn?".

```bash
# Start from most recent event and walk backwards (UUID omitted = default)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID

# Walk a specific UUID (ancestors + descendants, depth 3)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID

# Ancestors only — typical for "how did we get here?"
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID --direction ancestors

# Full raw detail for a single event
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID --depth 0 --detail full

# Filter by type and limit results
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID -t tool_use -n 5
```

**UUID is optional.** When omitted, `traverse` automatically starts from the most recent event and walks backwards.

Graph traversal options:
- `--direction {ancestors,descendants,both}` — traversal direction (default: both)
- `--depth N` — max hops from starting UUID; 0 = unlimited (default: 3)
- `-t, --types MSG_KIND [...]` — filter results by msg_kind (applied after traversal)
- `--since TIME` / `--until TIME` — ISO or relative time bounds
- `-n, --limit N` — max events to return
- `--detail {normal,full}` — `full` adds `raw_json` and `message_json` (equivalent to former `event` subcommand with `--depth 0`)

## project-id

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh project-id SESSION_ID

# Composable
PROJECT=$(.claude/skills/introspect/scripts/introspect_sessions.sh project-id SESSION_ID | jq -r '.project_id')
.claude/skills/introspect/scripts/introspect_sessions.sh --project=$PROJECT turns -t human --since 24h
```

Returns `{"project_id": "..."}`.

## projects

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh projects
```

Lists all projects with session count, first/last activity.
