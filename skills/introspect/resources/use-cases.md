# Common Use Cases & Architecture

## Introspect the Current Session

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all -t tool_use
.claude/skills/introspect/scripts/introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all -t human assistant_text
```

## Debug a Previous Session

```bash
# Find recent sessions
.claude/skills/introspect/scripts/introspect_sessions.sh sessions -n 5 -- PROJECT_ID

# View tool results (where errors often appear)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse OTHER_SESSION_ID --all -t tool_result
```

## Analyze Tool Patterns

```bash
# Search for specific tool usage across all sessions
.claude/skills/introspect/scripts/introspect_sessions.sh search "Edit" -t tool_use

# Search for errors
.claude/skills/introspect/scripts/introspect_sessions.sh search "error" -n 20
```

## Trace a Conversation Thread

```bash
# Walk ancestors and descendants of a specific event (includes subagent threads via bridge edges)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID TARGET_UUID

# Just the response chain (descendants — follows into spawned subagents)
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID TARGET_UUID --direction descendants --depth 10

# Ancestors only — typical for "how did we get here?"
.claude/skills/introspect/scripts/introspect_sessions.sh traverse SESSION_ID TARGET_UUID --direction ancestors
```

## Token Usage by Subagent

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh -f json traverse SESSION_ID --summary \
    | jq 'sort_by(-.total_billable_tokens)'
```

## Post-Compaction User Intent Recovery

Claude Code's JSONL session logs are **append-only**. Context compaction only affects the
in-memory window — the on-disk log preserves every event. Use this to recover the full
user intent timeline after compaction:

```bash
# All human-typed prompts in the last 24h
.claude/skills/introspect/scripts/introspect_sessions.sh \
    --project=PROJECT_ID traverse SESSION_ID --all -t human --since 24h

# Compact timeline view
.claude/skills/introspect/scripts/introspect_sessions.sh \
    --project=PROJECT_ID traverse SESSION_ID --all -t human --since 24h \
    | jq '[.[] | {timestamp, session: .agent_slug, content: (.content[:100])}]'
```

## Common jq Patterns

```bash
# Find tool calls with high frequency
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all -t tool_use \
    | jq '[group_by(.agent_slug)[] | {tool: .[0].agent_slug, count: length}] | sort_by(-.count)'

# Get all sessions for a project
introspect_sessions.sh sessions -- PROJECT_ID | jq '.[].session_id'

# Extract first and last UUIDs from a session
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all | jq '.[0].uuid, .[-1].uuid'

# Total cost for a session
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all --no-content \
    | jq '[.[].total_cost_usd] | add'

# Top 5 most expensive events
introspect_sessions.sh traverse ${CLAUDE_SESSION_ID} --all \
    | jq 'sort_by(-.total_cost_usd) | .[:5] | .[] | {uuid, msg_kind, total_cost_usd}'

# Cost breakdown by agent/subagent
introspect_sessions.sh -f json traverse ${CLAUDE_SESSION_ID} --summary \
    | jq '.[] | {agent: (.agent_slug // "main"), cost: .total_cost_usd}'
```

## Architecture

```
introspect_sessions.sh (bash wrapper)
       │
       └── uv run introspect_sessions.py (PEP-723 script)
                    │
                    └── Pure Python parsing of ~/.claude/projects/**/*.jsonl
                                └── SQLite cache at ~/.claude/cache/introspect_sessions.db
```

The bash wrapper is needed because Claude Code skills cannot directly invoke `uv`.

**Zero-dependency script** — uses only Python 3.12+ stdlib (sqlite3, json, argparse, subprocess). No DuckDB or third-party packages required at runtime. ML engines (`--engine`) inject HuggingFace dependencies at runtime via `uv run --with`.

**String substitution:** `${CLAUDE_SESSION_ID}` is substituted with the current session UUID by Claude Code at skill invocation time.

### Subagent Integration

Subagent JSONL files are stored under `{session_id}/subagents/` and ingested with
`session_id = parent_session_uuid`. Their first event always has `parentUuid=null`
(a root with no pointer back to the parent). At cache-update time, a **synthetic bridge
edge** is created from each subagent's first event to the parent's triggering `tool_use`
event using `promptId` as the natural join key — the same UUID is written to both the
subagent's first event and the parent's `tool_result` event, whose `parentUuid` points
to the `tool_use`. This exact join requires no timestamp heuristics.

After bridge edges are built, graph traversal with `--direction descendants` naturally
follows into spawned subagent threads. The `--all` and `--summary` modes always include
subagent events since they share the same `session_id`.

### JSONL Event Structure

```json
{
  "type": "user|assistant|system|queue-operation|...",
  "timestamp": "2025-01-14T10:00:00.000Z",
  "uuid": "unique-event-id",
  "parentUuid": "parent-event-id",
  "sessionId": "session-uuid",
  "agentId": "agent-id-for-subagents",
  "isSidechain": true,
  "isMeta": false,
  "slug": "human-readable-agent-name",
  "message": {
    "role": "user|assistant",
    "content": "string or content-block array",
    "model": "claude-opus-4-6",
    "usage": {
      "input_tokens": 1000,
      "output_tokens": 500,
      "cache_read_input_tokens": 200,
      "cache_creation_input_tokens": 100,
      "cache_creation": { "ephemeral_5m_input_tokens": 50 }
    }
  }
}
```

Content blocks in `message.content` determine `msg_kind`:
- String → `human` or `task_notification`
- `[{type: "text"}]` → `assistant_text` or `user_text`
- `[{type: "thinking"}]` → `thinking` (note: `signature` field is stripped on ingest)
- `[{type: "tool_use"}]` → `tool_use`
- `[{type: "tool_result"}]` → `tool_result`
- `isMeta: true` → `meta`
