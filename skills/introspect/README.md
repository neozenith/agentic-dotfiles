# Introspect — Claude Code session analytics

A self-introspection toolkit for Claude Code. It turns the raw JSONL transcripts
that Claude Code writes under `~/.claude/projects/` into a queryable SQLite cache,
so you can ask questions about your own sessions: what was said, which tools ran,
how the event tree branches across subagents, what it cost, how fast the model
generated, and how much of the context window each response consumed.

> This README is the **human-facing explainer** — the *why* and the *shape* of the
> data. For the operating manual (commands, flags, query recipes) the agent uses,
> see [SKILL.md](SKILL.md) and [resources/](resources/).

## What it's for

- **Review past sessions** — reconstruct a conversation, flat or as an event tree.
- **Debug failures** — walk ancestors/descendants of a specific event across agents.
- **Recover intent post-compaction** — search the full transcript history (FTS5).
- **Account for cost & performance** — every event carries pre-computed cost,
  throughput, and context-utilization figures.
- **Explore structure** — a resolved-entity knowledge graph over the prompt history.

## How it works

```
~/.claude/projects/**/*.jsonl        the source of truth (append-only logs)
        │  incremental ingest (mtime/size check, only changed files)
        ▼
~/.claude/cache/introspect_sessions.db   SQLite cache (this skill owns it)
        │  CLI queries  /  direct sqlite3  /  the FastAPI dashboard
        ▼
   traverse · sessions · search · cache · /api/*
```

The cache is **derived state** — it can be deleted and rebuilt from the JSONL at
any time. Every query checks file mtimes and incrementally re-ingests only what
changed, so reads are normally instant. Two ingesters share one on-disk schema
(`SCHEMA_VERSION`): the dashboard backend (`src/claude_code_sessions/database/sqlite/`)
and this skill's standalone script — kept in lockstep and guarded by
`tests/test_introspect_parity.py`.

### Schema migrations

The schema is versioned by `SCHEMA_VERSION`. **Adding columns requires bumping it**
— `CREATE TABLE IF NOT EXISTS` can't add columns to an existing table, so a bump is
what triggers the DROP+recreate (and a one-time reingest). The current version is
**`17`**; it grew through the tokenometrics initiative (v14 response accounting,
v15 context, v16 duration, v17 session-timing rollups).

## Data model

The core ingestion + analytics tables. The knowledge-graph tables are a separate
subsystem (listed under [Knowledge graph](#knowledge-graph) below).

```mermaid
erDiagram
    source_files {
        INTEGER id PK
        TEXT filepath UK
        REAL mtime
        INTEGER size_bytes
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
        REAL total_cost_usd
        REAL avg_tps "v17: tokens/sec over response heads"
        INTEGER total_idle_ms "v17: human think-time between turns"
        INTEGER total_active_ms "v17: prompt to turn-end"
        REAL peak_context_ratio "v17: fullest the window got"
    }

    events {
        INTEGER id PK
        TEXT uuid
        TEXT parent_uuid
        TEXT prompt_id "bridges subagent first events to parent"
        TEXT event_type "raw: user assistant system"
        TEXT msg_kind "9 kinds; subagent- prefixed in sidechains"
        TEXT timestamp
        TEXT session_id
        TEXT project_id
        INTEGER is_sidechain
        TEXT model_id
        TEXT request_id "v14: the response unit (one per requestId)"
        TEXT stop_reason "v14: end_turn tool_use etc"
        INTEGER is_response_head "v14: 1 = canonical row; non-heads zeroed"
        INTEGER input_tokens
        INTEGER output_tokens
        INTEGER cache_read_tokens
        INTEGER cache_creation_tokens
        INTEGER context_tokens "v15: live window occupancy"
        INTEGER context_window "v15: per-model budget (200k/1M/32k...)"
        REAL context_ratio "v15: occupancy / window (raw, no zones)"
        INTEGER response_duration_ms "v16: trigger to head; basis of TPS"
        REAL token_rate "input $/Mtok for this model"
        REAL billable_tokens "weighted input-equivalent tokens"
        REAL total_cost_usd "cost for this event"
        INTEGER source_file_id FK
        INTEGER line_number
    }

    event_calls {
        INTEGER id PK
        INTEGER event_id FK
        TEXT call_type "tool skill subagent cli rule make_target ..."
        TEXT call_name
        TEXT project_id
        TEXT session_id
    }

    event_edges {
        INTEGER id PK
        TEXT event_uuid
        TEXT parent_event_uuid
        INTEGER source_file_id FK
    }

    agg {
        TEXT granularity PK "hourly daily weekly monthly"
        TEXT time_bucket PK
        TEXT project_id PK
        TEXT session_id PK "'' for NULL"
        TEXT model_id PK "'' for NULL"
        INTEGER event_count
        INTEGER output_tokens
        REAL total_cost_usd
    }

    source_files ||--o{ events : "contains"
    source_files ||--o{ event_edges : "tracks"
    events ||--o{ event_calls : "emits"
    events ||--o{ agg : "rolled up into"
```

### The `is_response_head` invariant (read this before summing)

A single model response (one `requestId`) is logged as **N content-block events**
(thinking + text + each tool_use), and **every block repeats the same request-level
usage**. Summing per event over-counts ~2.4×. The ingest pass marks exactly one
**head** per `requestId` (the last block, which carries the final `stop_reason`)
and **zeroes the duplicated token/cost columns on the non-heads**. So:

- `SUM(output_tokens)`, `SUM(total_cost_usd)`, etc. are **correct as-is** — no
  `WHERE is_response_head = 1` needed; the non-heads contribute zero.
- `context_tokens` / `context_window` / `context_ratio` are **not** zeroed (they're
  a *level*, not an additive measure, and are genuinely true of every block). If you
  count responses, filter `is_response_head = 1` to avoid double-counting.

## Analytics fields (tokenometrics)

Beyond raw tokens, every event and session carries derived analytics, computed
once at ingest:

| Field | Grain | Meaning |
|-------|-------|---------|
| `token_rate`, `billable_tokens`, `total_cost_usd` | event | Cost (see [Cost model](#cost-model)) |
| `context_tokens` | event (assistant) | Live window occupancy = `input + cache_read + cache_creation` |
| `context_window` | event | The model's advertised window (curated map: opus-4.6/4.7/4.8 + sonnet-4.6 = 1M; *-4.5 = 200k; qwen2.5-coder = 32k; …). `NULL` for unknown/synthetic models |
| `context_ratio` | event | `context_tokens / context_window` — raw utilization fraction, `NULL` when window unknown. **No categorical "zones"** — utilization is reported quantitatively |
| `response_duration_ms` | head | Triggering-event → head timestamp (the JSONL has no per-assistant duration) |
| `tps` | head (derived) | `output_tokens / (response_duration_ms / 1000)` — model throughput |
| `avg_tps` | session | Σ output ÷ Σ duration over heads |
| `total_active_ms` / `total_idle_ms` | session | Working time (prompt → turn-end) vs. human think-time (turn-end → next prompt). Subagent/tool gaps are excluded — idle is human-only |
| `peak_context_ratio` | session | The fullest the window got in the session |
| `too_fast` | turn (API) | Heuristic flag: the human replied faster than even a fast skim (`< output / 8 tok·s⁻¹`) of a ≥200-token response could be read |

These feed the dashboard's **Performance** page (TPS by model, a context-utilization
histogram, idle-vs-active split) and the SessionDetail occupancy/TPS/idle markers.

### Subagent labeling

Events in a subagent context (`is_sidechain = 1` **or** the source file is a
`subagent`/`agent_root` file) get their `msg_kind` prefixed with `subagent-`
(e.g. `subagent-tool_use`). The base kind is recovered by stripping the prefix, so a
filter on `tool_use` matches both main-thread and subagent tool calls unless a scope
is applied. This fixes ~1,335 subagent prompts that previously masqueraded as
main-thread `human` events.

## Cost model

Costs are denormalized onto every event at ingest, so cost queries are plain `SUM()`s
— no per-query pricing joins.

```
billable_tokens = input_tokens
                + output_tokens         × 5.0
                + cache_read_tokens     × 0.1
                + cache_creation_tokens × 1.25
total_cost_usd  = billable_tokens × token_rate / 1_000_000
```

`token_rate` ($/Mtok input) is by model **family**, detected from `model_id` by
substring (`opus` 15.0, `sonnet` 3.0, `haiku` 1.0, unknown 0.0) — so new model
versions price automatically. All families share the relative multipliers above.

## Knowledge graph

The cache also hosts a resolved-entity knowledge graph derived from chunked
human-prompt content (incremental, built at backend start). It is an independent
SQL surface — any introspection query can read it directly.

| Table | Holds |
|-------|-------|
| `entities` / `relations` | Per-mention extractions |
| `entity_clusters` | name → canonical (synonym resolution) |
| `nodes` / `edges` | Canonical entities / coalesced relations |
| `leiden_communities` | Multi-resolution community membership |
| `entity_cluster_labels` / `community_labels` | LLM-generated labels |

## Relationship to the dashboard

This skill and the FastAPI + React dashboard (`src/claude_code_sessions/`,
`frontend/`) read the **same** schema. The skill is the CLI/SQL surface; the
dashboard is the visual surface. `tests/test_introspect_parity.py` asserts both
ingesters produce byte-identical event rows at the same `SCHEMA_VERSION`.

## Pointers

- [SKILL.md](SKILL.md) — agent operating manual (commands, message kinds, output formats)
- [resources/cache.md](resources/cache.md) — cache flags, management commands, SQL fallback recipes
- [resources/commands.md](resources/commands.md) — full command reference
- [resources/use-cases.md](resources/use-cases.md) — workflows, post-compaction recovery
- [resources/reflect.md](resources/reflect.md) — reflection workflow
