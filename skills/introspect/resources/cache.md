# Cache Reference

## Automatic Cache Updates

Every query command checks file mtimes and incrementally updates before executing. Control with global flags:

```bash
# Default: check staleness, incrementally update changed files
.claude/skills/introspect/scripts/introspect_sessions.sh turns ${CLAUDE_SESSION_ID}

# Skip auto-update (use existing cache as-is, faster)
.claude/skills/introspect/scripts/introspect_sessions.sh --cache-frozen turns ${CLAUDE_SESSION_ID}

# Wipe and rebuild cache from scratch before query
.claude/skills/introspect/scripts/introspect_sessions.sh --cache-rebuild turns ${CLAUDE_SESSION_ID}
```

| Flag | Behavior |
|------|----------|
| *(default)* | Check file mtimes, incrementally update changed files |
| `--cache-frozen` | Skip all cache updates, use existing data |
| `--cache-rebuild` | Wipe cache and re-ingest all files from scratch |

## Manual Cache Management

```bash
.claude/skills/introspect/scripts/introspect_sessions.sh cache init      # Initialize new cache DB
.claude/skills/introspect/scripts/introspect_sessions.sh cache status    # File count, event count, size
.claude/skills/introspect/scripts/introspect_sessions.sh cache update    # Incremental update only
.claude/skills/introspect/scripts/introspect_sessions.sh cache rebuild   # Clear and re-ingest all
.claude/skills/introspect/scripts/introspect_sessions.sh cache clear     # Clear all cached data
```

Cache is stored at `~/.claude/cache/introspect_sessions.db`.

## Schema

```mermaid
erDiagram
    cache_metadata {
        TEXT key PK
        TEXT value
    }

    source_files {
        INTEGER id PK
        TEXT filepath UK
        REAL mtime
        INTEGER size_bytes
        INTEGER line_count
        TEXT last_ingested_at
        TEXT project_id
        TEXT session_id "nullable for orphan agents"
        TEXT file_type "main_session subagent agent_root"
    }

    projects {
        INTEGER id PK
        TEXT project_id UK
        TEXT first_activity
        TEXT last_activity
        INTEGER session_count
        INTEGER event_count
    }

    sessions {
        INTEGER id PK
        TEXT session_id
        TEXT project_id
        TEXT first_timestamp
        TEXT last_timestamp
        INTEGER event_count
        INTEGER subagent_count
        INTEGER total_input_tokens
        INTEGER total_output_tokens
        INTEGER total_cache_read_tokens
        INTEGER total_cache_creation_tokens
        REAL total_cost_usd
    }

    events {
        INTEGER id PK
        TEXT uuid
        TEXT parent_uuid
        TEXT event_type "raw: user assistant system etc"
        TEXT msg_kind "human task_notification tool_result user_text meta assistant_text thinking tool_use other"
        TEXT timestamp
        TEXT session_id
        TEXT project_id
        INTEGER is_sidechain
        TEXT agent_id
        TEXT message_role
        TEXT message_content "plain text for FTS"
        TEXT model_id
        INTEGER input_tokens
        INTEGER output_tokens
        INTEGER cache_read_tokens
        INTEGER cache_creation_tokens
        REAL token_rate "$/Mtok input rate for this event's model"
        REAL billable_tokens "weighted input-equivalent token count"
        REAL total_cost_usd "cost for this event in USD"
        INTEGER source_file_id FK
        INTEGER line_number
        TEXT raw_json
    }

    event_edges {
        INTEGER id PK
        TEXT project_id
        TEXT session_id
        TEXT event_uuid
        TEXT parent_event_uuid
        INTEGER source_file_id FK
    }

    reflections {
        INTEGER id PK
        TEXT project_id
        TEXT session_id
        TEXT reflection_prompt
        TEXT created_at
    }

    event_annotations {
        INTEGER id PK
        TEXT project_id
        TEXT session_id
        TEXT event_uuid
        INTEGER reflection_id FK
        TEXT annotation_result
        TEXT created_at
    }

    source_files ||--o{ events : "contains"
    source_files ||--o{ event_edges : "tracks"
    events ||--o{ event_annotations : "annotated by"
    reflections ||--o{ event_annotations : "produces"
```

**FTS5 virtual tables** (auto-synced via triggers):
- `events_fts` — full-text search on `events.message_content`
- `reflections_fts` — full-text search on `reflections.reflection_prompt`

**Key relationships:**
- `events.source_file_id` → `source_files.id` (CASCADE delete)
- `event_edges` links `event_uuid` → `parent_event_uuid` for tree traversal
- `event_annotations.(project_id, session_id, event_uuid)` → `events` (composite FK)
- `event_annotations.reflection_id` → `reflections.id` (CASCADE delete)

## Event Cost Enrichment

Three cost fields are computed at ingestion time and **stored** in the `events` table. They are available on every event-returning command (`turns`, `traverse`, `event`) directly from the database without any per-query computation.

| Field | Type | Description |
|-------|------|-------------|
| `token_rate` | `float` | Input $/Mtok for the event's model family |
| `billable_tokens` | `float` | Weighted input-equivalent token count |
| `total_cost_usd` | `float` | Cost for this event in USD |

### Token Rate by Model Family

| Family | `token_rate` ($/Mtok) |
|--------|-----------------------|
| `opus` | 15.0 |
| `sonnet` | 3.0 |
| `haiku` | 1.0 |
| unknown | 0.0 |

Model family is detected from `model_id` via substring match (`opus`, `sonnet`, `haiku`). New model versions are handled automatically without config changes.

### Billable Tokens Formula

```
billable_tokens = input_tokens
                + output_tokens        × 5.0
                + cache_read_tokens    × 0.1
                + cache_creation_tokens × 1.25
```

All model families share identical relative multipliers, so a single formula covers all events regardless of which model was active.

### Cost Formula

```
total_cost_usd = billable_tokens × token_rate / 1_000_000
```

### Example jq Queries

```bash
# Total cost for a session
turns SESSION_ID | jq '[.[].total_cost_usd] | add'

# Most expensive events (tool_use calls)
turns SESSION_ID -t tool_use | jq 'sort_by(-.total_cost_usd) | .[:5]'

# Cost breakdown by msg_kind
turns SESSION_ID | jq 'group_by(.msg_kind) | map({kind: .[0].msg_kind, cost: ([.[].total_cost_usd] | add)})'

# Events where model switched mid-session
turns SESSION_ID | jq '[.[] | {uuid, model_id, token_rate}] | unique_by(.model_id)'
```
