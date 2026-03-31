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

Returns all events in the session in flat chronological order, including subagent events.

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

Example output (one event, `--all` normal mode):
```json
{
  "turn_num": 1,
  "type": "user",
  "msg_kind": "human",
  "timestamp": "2026-03-31T00:36:50.123Z",
  "model_id": null,
  "input_tokens": 0,
  "output_tokens": 0,
  "cache_read_tokens": 0,
  "cache_creation_tokens": 0,
  "token_rate": 0.0,
  "billable_tokens": 0.0,
  "total_cost_usd": 0.0,
  "uuid": "a3c261ab-c1c2-4b56-893b-d25bf2149353",
  "parent_uuid": null,
  "agent_id": null,
  "agent_slug": "main-session-slug",
  "filepath": "/path/to/session.jsonl",
  "line_number": 1,
  "content": "What should we build today?",
  "role": "user"
}
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

Returns per-agent aggregated stats — event counts, token totals, and costs — for all agents and subagents in the session. Uses stored `billable_tokens` for accurate cost calculation (correct output/cache multipliers).

```bash
# Per-agent token and cost breakdown
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID --summary

# Sort by cost descending
.claude/skills/introspect/scripts/introspect_sessions.sh -f json traverse SESSION_ID --summary | jq 'sort_by(-.total_cost_usd)'
```

Example output (two agents: main session + one subagent):
```json
[
  {
    "agent_id": null,
    "agent_slug": "main-session-slug",
    "is_sidechain": 0,
    "first_event": "2026-03-31T00:36:50.000Z",
    "last_event": "2026-03-31T01:12:30.000Z",
    "event_count": 142,
    "input_tokens": 45230,
    "output_tokens": 8120,
    "cache_read_tokens": 312000,
    "cache_creation_tokens": 180000,
    "total_billable_tokens": 314783.0,
    "total_cost_usd": 0.944349
  },
  {
    "agent_id": "a4edad53bda26e591",
    "agent_slug": "merry-splashing-barto",
    "is_sidechain": 1,
    "first_event": "2026-03-31T00:36:54.489Z",
    "last_event": "2026-03-31T00:38:12.000Z",
    "event_count": 18,
    "input_tokens": 3200,
    "output_tokens": 980,
    "cache_read_tokens": 28000,
    "cache_creation_tokens": 14000,
    "total_billable_tokens": 29380.0,
    "total_cost_usd": 0.088140
  }
]
```

Summary mode options:
- `--summary` — enable per-agent aggregation mode
- `-p, --project PROJECT` — restrict to events for a specific project_id

### Graph traversal mode (default)

Walks the `event_edges` graph via recursive CTE. Used for tracing causality — "how did we get here?" or "what did this event spawn?". **Subagents are integrated:** at cache-update time, each subagent's first event (which has `parentUuid=null`) is linked to the parent's triggering `tool_use` event via a synthetic bridge edge. The join uses `promptId` — a UUID written to both the subagent's first event and the parent's matching `tool_result` event, whose `parentUuid` points to the `tool_use`. This exact key (no heuristics) makes subagent threads fully reachable from the parent graph.

```bash
# Start from most recent event and walk backwards (UUID omitted = default)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID

# Walk a specific UUID (ancestors + descendants, depth 3)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID

# Ancestors only — typical for "how did we get here?"
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID --direction ancestors

# Descendants only — walk the full subagent thread spawned by this event
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID TOOL_USE_UUID --direction descendants --depth 10

# Full raw detail for a single event
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID --depth 0 --detail full

# Filter by type and limit results
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID UUID -t tool_use -n 5
```

Example output (one node, graph traversal normal mode):
```json
{
  "uuid": "d7ef7fbd-69b9-461f-91b8-7cdc5c697975",
  "parent_uuid": "04dce4af-8dd3-402f-9f29-f8202f58d6bd",
  "event_type": "assistant",
  "msg_kind": "tool_use",
  "timestamp": "2026-03-31T00:36:54.486Z",
  "model_id": "claude-sonnet-4-6",
  "input_tokens": 3,
  "output_tokens": 492,
  "cache_read_tokens": 11541,
  "cache_creation_tokens": 127980,
  "token_rate": 3.0,
  "billable_tokens": 162454.5,
  "total_cost_usd": 0.487364,
  "role": "assistant",
  "content": [{"type": "tool_use", "name": "Agent", "id": "toolu_01Ko...", "input": {"description": "..."}}],
  "agent_id": null,
  "agent_slug": "main-session-slug",
  "filepath": "/path/to/session.jsonl",
  "line_number": 42
}
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
.claude/skills/introspect/scripts/introspect_sessions.sh --project=$PROJECT traverse SESSION_ID --all -t human --since 24h
```

Returns `{"project_id": "..."}`.

## projects

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh projects
```

Lists all projects with session count, first/last activity.
