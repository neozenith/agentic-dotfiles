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

> The full entity-relationship diagram (kept current with `SCHEMA_VERSION`,
> presently **`17`**) lives in the human-facing
> [**README › Data model**](../README.md#data-model). This section is the
> column quick-reference for direct `sqlite3` fallback.

The tables you'll touch most for introspection queries:

| Table | What it holds |
|-------|---------------|
| `events` | One row per content block (see column groups below) |
| `sessions` | Per-session rollups incl. v17 timing (`avg_tps`, `total_idle_ms`, `total_active_ms`, `peak_context_ratio`) |
| `source_files` | Ingested JSONL files (`file_type` = `main_session`/`subagent`/`agent_root`) |
| `projects` | Per-project activity + counts |
| `event_edges` | `event_uuid` → `parent_event_uuid` for tree traversal (incl. cross-agent) |
| `event_calls` | One row per tool/skill/subagent/cli/rule call inside an event |
| `agg` | Time-bucketed rollups, grain `(granularity, time_bucket, project_id, session_id, model_id)` |

`events` columns, grouped:

- **Identity / routing**: `uuid`, `parent_uuid`, `prompt_id`, `session_id`, `project_id`, `source_file_id`, `line_number`.
- **Classification**: `event_type`, `msg_kind` (9 kinds; `subagent-` prefixed for sidechain events), `is_sidechain`, `model_id`, `timestamp`.
- **Usage**: `input_tokens`, `output_tokens`, `cache_read_tokens`, `cache_creation_tokens`.
- **Cost** (pre-computed at ingest): `token_rate`, `billable_tokens`, `total_cost_usd`.
- **Response accounting (v14)**: `request_id`, `stop_reason`, `is_response_head`.
- **Context utilization (v15)**: `context_tokens`, `context_window`, `context_ratio` (raw fraction, no zones).
- **Performance (v16)**: `response_duration_ms` (TPS = `output_tokens / (response_duration_ms/1000)`).

⚠️ **`is_response_head`** — a response is N blocks repeating identical usage; only the
head keeps the usage (non-heads are zeroed), so token/cost `SUM()`s are correct
**without** a head filter. When *counting responses*, filter `is_response_head = 1`.
See the [README invariant](../README.md#the-is_response_head-invariant-read-this-before-summing).

**FTS5 virtual tables** (auto-synced via triggers):
- `events_fts` — full-text search on `events.message_content`

**Key relationships:**
- `events.source_file_id` → `source_files.id` (CASCADE delete)
- `event_edges` links `event_uuid` → `parent_event_uuid` for tree traversal
- `agg` table uses grain `(granularity, time_bucket, project_id, session_id, model_id)` — `granularity` discriminates `'hourly'`/`'daily'`/`'weekly'`/`'monthly'`; NULL `session_id`/`model_id` stored as `''` for PK uniqueness

**Notes on the `events` table:**
- `raw_json` is **intentionally empty**. Reconstruct the raw payload by reading `source_files.filepath` at `line_number`. The column is retained only to keep the read-path error handling simple (`json.loads("")` raises `JSONDecodeError` which callers already treat as "no raw payload").
- `prompt_id` is the join key for bridging subagent first events (`parentUuid=NULL`) back to the parent session's `tool_use` event. The bridge is materialized into `event_edges` at ingest time by `build_cross_agent_edges()`.
- `token_rate`, `billable_tokens`, `total_cost_usd` are pre-computed at ingest (see below).

## Dimensional Aggregates (`agg` table)

A single pre-aggregated table rolls `events` up by time bucket, discriminated by the `granularity` column:

| Table | Bucket expression |
|-------|-------------------|
| Granularity | Bucket expression |
|-------------|-------------------|
| `hourly`  | `strftime('%Y-%m-%dT%H:00:00', timestamp)` |
| `daily`   | `date(timestamp)` |
| `weekly`  | `date(timestamp, 'weekday 0', '-6 days')` (Monday-start weeks) |
| `monthly` | `strftime('%Y-%m-01', timestamp)` |

New granularities (e.g., `quarterly`) are added by inserting a row into `_AGG_BUCKET_EXPRS` — no DDL migration needed.

**Maintenance:** `cache update` calls `refresh_aggregates_for_range(start, end)` scoped to the timestamp window of the sessions touched in that batch, so cost is proportional to changed data — not the full event history. On a cold cache (empty `agg` table) it falls back to a full rebuild. All aggregates are stored as `SUM()`s of the already-denormalized cost columns on `events`, so there is no per-query CASE expression needed to price rows by model family.

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
| `fable` | 10.0 |
| `opus` | 5.0 |
| `sonnet` | 3.0 |
| `haiku` | 1.0 |
| unknown | 0.0 |

Model family is detected from `model_id` via substring match (`fable`, `opus`, `sonnet`, `haiku`). New model versions are handled automatically without config changes.

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
