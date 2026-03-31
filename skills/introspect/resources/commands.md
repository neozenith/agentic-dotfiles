# Command Reference

All commands use the bash wrapper:
```
.claude/skills/introspect/scripts/introspect_sessions.sh [global-flags] COMMAND [args]
```

## turns

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh turns SESSION_ID -n 20
.claude/skills/introspect/scripts/introspect_sessions.sh turns SESSION_ID -t user assistant
.claude/skills/introspect/scripts/introspect_sessions.sh turns SESSION_ID --since 1h
```

Options:
- `-t, --types TYPE [TYPE...]` — Filter by `msg_kind` (human, assistant_text, tool_use, tool_result, thinking, meta, user_text, task_notification, other)
- `--since TIME` / `--until TIME` — ISO or relative (`1h`, `30m`, `7d`, `2w`)
- `-n, --limit N` — Max turns (default: 100)
- `--offset N` — Skip first N turns
- `--no-content` — Exclude message content (faster)
- `-p, --project PROJECT` — Specify project for faster queries

## agents

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh agents SESSION_ID
.claude/skills/introspect/scripts/introspect_sessions.sh -f json agents SESSION_ID | jq 'sort_by(-.total_billable_tokens)'
```

Returns per-subagent: agent_id, slug, is_sidechain, event_count, tool_calls, token breakdown.

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

```bash
# Start from most recent event and walk backwards (UUID omitted = default)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID

# Walk a specific UUID (ancestors + descendants, depth 3)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID

# Ancestors only — typical for "how did we get here?"
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID --direction ancestors

# Full raw detail for a single event (replaces former `event` subcommand)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID --depth 0 --detail full

# Filter by type and limit results
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID -t tool_use -n 5
```

Walks the `event_edges` graph via recursive CTE. Default: both directions, depth 3.

**UUID is optional.** When omitted, `traverse` automatically starts from the most recent event in the session and walks backwards — useful for inspecting the tail of a session without needing to copy a UUID first.

Options:
- `--direction {ancestors,descendants,both}` — traversal direction (default: both)
- `--depth N` — max hops from starting UUID; 0 = unlimited (default: 3)
- `-t, --types MSG_KIND [...]` — filter results by msg_kind (applied after traversal)
- `--since TIME` / `--until TIME` — ISO or relative time bounds (e.g. `1h`, `30m`)
- `-n, --limit N` — max events to return (default: all)
- `--detail {normal,full}` — `normal` returns key fields + parsed content (default); `full` adds `raw_json` and `message_json`

**Note:** `--detail full` is the equivalent of the former `event` subcommand — pass a single UUID with `--depth 0` to fetch one event's complete data.

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
