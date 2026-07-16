# DuckDB Fallback — Query JSONL Directly

**Keywords:** cache out of date · cache stale · cache won't rebuild · `introspect_sessions.py`
broken · script crashes · `uv` unavailable · `ModuleNotFoundError` · SQLite cache missing ·
query raw JSONL · DuckDB fallback · no cache.

When the normal path is unavailable, you can still answer every introspection question by
querying the source `*.jsonl` files **directly with the DuckDB CLI**. The SQLite cache is a
derived convenience — the JSONL logs are the source of truth and are append-only, so a raw
query is always correct, just less ergonomic.

## When To Reach For This

Use this fallback when **any** of these is true:

| Symptom | Why the cache path fails |
|---------|--------------------------|
| `cache status` shows a stale/old event count and `--cache-rebuild` errors or hangs | Cache is behind the JSONL and can't catch up |
| `introspect_sessions.sh …` exits non-zero (Python traceback, `ModuleNotFoundError`, schema-version mismatch) | The script itself is broken |
| `uv` / Python 3.12 not installed, or the PEP-723 env won't resolve | The wrapper can't boot the script |
| `~/.claude/cache/introspect_sessions.db` is missing, locked, or corrupt | No cache to query |
| You want a one-shot read **without** mutating the cache (no incremental ingest side-effects) | Cache auto-update is undesirable right now |

This is a **read-only** path: it never writes the SQLite cache, so it can't corrupt anything
and needs no migration. Once the script/cache is healthy again, prefer the normal CLI — it
gives you cross-agent `event_edges` traversal and the knowledge graph that raw DuckDB does not
(the 9-way `msg_kind` itself **is** reproduced here — see below).

> **Fail loud, don't silently degrade.** This fallback is a deliberate, explicit choice you
> make when the primary path is broken — not an automatic try/except wrapper. If the CLI
> *should* be working, fix it; don't quietly route around it. (See the global
> "no graceful degradation" rule.)

## Prerequisite

```bash
duckdb --version   # any v1.x — reads JSON natively, no extension/install needed
```

If DuckDB is not installed: `brew install duckdb`. It is a single static binary with zero
runtime dependencies — the same zero-dep philosophy as the introspect script itself.

## The `--duckdb` Helper (use this first)

The recipes below are wrapped in a pure-bash helper so you don't have to hand-write SQL —
`scripts/introspect_duckdb.sh`, surfaced through the skill as **`/introspect --duckdb …`**:

```bash
SH=.claude/skills/introspect/scripts/introspect_duckdb.sh
$SH sessions -n 10                     # most-recent sessions for the CWD project
$SH events  SESSION_ID -t tool_use     # chronological events; -t/--kind filters by msg_kind
$SH prompts SESSION_ID                 # GENUINE human prompts only (intent recovery)
$SH prompts SESSION_ID --raw           # …or every string-content user event (slash cmds, caveats)
$SH search  "some text" --human        # search ONLY what you typed (drops tool/wrapper noise)
$SH kinds                              # msg_kind distribution + genuine-human count
$SH cost    [SESSION_ID]               # requestId-deduped cost by model family
$SH sql     "SELECT msg_kind, COUNT(*) FROM events GROUP BY 1"  # raw SQL on the `events` view
$SH --help                             # global opts: -p/--project, --all, --subagents, --human, -f json
```

It is **pure bash** (only `bash` + `duckdb`) on purpose — the helper must work when the
`uv`/Python toolchain it backstops is itself broken; a Python wrapper would share the same
failure modes. Each subcommand defines a DuckDB view named `events` over the JSONL glob, which
is also what the `sql` passthrough queries. **The view adds the `msg_kind`, `text`, and
`is_human_prompt` columns** described under [Deriving `msg_kind`](#deriving-msg_kind-and-genuine-human-prompts)
below. The hand-written recipes are the same SQL the helper emits — reach for them when you
need a shape the helper doesn't cover.

## Data Location

```
~/.claude/projects/{project-dir}/{session_uuid}.jsonl          # main session
~/.claude/projects/{project-dir}/{session_uuid}/**/*.jsonl     # subagent + tool-result files
```

`{project-dir}` is the kebab-cased absolute project path (e.g. a path like
`/Users/me/play/foo` becomes `-Users-me-play-foo`). Set two shell vars once and reuse them:

```bash
PROJECTS=~/.claude/projects
PROJECT="$PROJECTS/-Users-me-play-foo"     # <- your kebab-cased project dir
```

### The read function

Every recipe below reads JSONL with the same three options — always include them:

```sql
read_json_auto('<glob>', union_by_name => true, ignore_errors => true)
```

| Option | Why it is mandatory |
|--------|---------------------|
| `union_by_name => true` | Event rows are heterogeneous (user/assistant/system/queue-operation). Without this, DuckDB infers one rigid schema from the first rows and drops columns absent there. |
| `ignore_errors => true` | A single malformed line (partial write, in-flight append) would otherwise abort the whole scan. |
| `filename => true` *(optional)* | Adds a `filename` column so you can report results as `filename:session` — the source-of-truth pointer. |

Globs:
- `'$PROJECT/*.jsonl'` — main session files only (most queries want this).
- `'$PROJECT/**/*.jsonl'` — include subagent and tool-result files nested under `{session_uuid}/`.

## ⚠️ Critical Gotcha: Deduplicate by `requestId` Before Summing Tokens/Cost

A single assistant response is written to the JSONL as **N rows** (one per content block:
thinking, text, each tool_use), and **every row repeats the identical `message.usage`**.
The SQLite cache solves this with the `is_response_head` invariant (it zeroes usage on all
but the head row). **Raw JSONL has no such flag**, so a naive `SUM(usage…)` over-counts
tokens and cost by the block-multiplier — often **2–3×**.

> Measured on a real project: naive sum reported **$6,969**; the correct `requestId`-deduped
> figure was **$2,161**. The same `requestId` appeared on up to 64 repeated block-rows.

**Rule:** for any token/cost aggregate, collapse to one row per `requestId` *first*
(`GROUP BY requestId` + `ANY_VALUE(...)`), then aggregate. For non-cost queries (listing
events, searching text, reading prompts) the repetition is harmless.

## Field Mapping: JSONL Path → Cache Column

DuckDB reads nested JSON as structs — use dotted access. The fields you'll need:

| Cache column | DuckDB expression on the raw row |
|--------------|----------------------------------|
| `uuid` | `uuid` |
| `parent_uuid` | `parentUuid` |
| `session_id` | `sessionId` |
| `event_type` | `type` |
| `timestamp` | `timestamp` (ISO-8601 string; sorts lexicographically) |
| `model_id` | `message.model` |
| `input_tokens` | `message.usage.input_tokens` |
| `output_tokens` | `message.usage.output_tokens` |
| `cache_read_tokens` | `message.usage.cache_read_input_tokens` |
| `cache_creation_tokens` | `message.usage.cache_creation_input_tokens` |
| `request_id` | `requestId` |
| `is_sidechain` | `isSidechain` |
| *(message body)* | `message.content` — **polymorphic**: a `VARCHAR` for human prompts, a `LIST<STRUCT>` of content blocks otherwise. Use `TRY_CAST(message.content AS VARCHAR)` to test/extract the string form. |

`msg_kind` has no single source field — it is derived from `type`, `isMeta`, and the
content-block shape. The helper reproduces it exactly in SQL; see
[Deriving `msg_kind`](#deriving-msg_kind-and-genuine-human-prompts) below.

## Recipes

All verified against live data. Pipe through `-json` / `-markdown` for machine- or
human-readable output, or use `-c "<sql>"` for a one-shot.

### List sessions for a project (most-recent first)

```bash
duckdb -markdown -c "
SELECT sessionId,
       COUNT(*)            AS events,
       MIN(timestamp)      AS started,
       MAX(timestamp)      AS last_active
FROM read_json_auto('$PROJECT/*.jsonl', union_by_name => true, ignore_errors => true)
GROUP BY sessionId
ORDER BY last_active DESC
LIMIT 20;"
```

### Events in a session, chronological (the `traverse --all` analog)

```bash
SID=<session-uuid>
duckdb -markdown -c "
SELECT timestamp,
       type,
       LEFT(COALESCE(TRY_CAST(message.content AS VARCHAR), CAST(message.content AS VARCHAR)), 100) AS preview
FROM read_json_auto('$PROJECT/*.jsonl', union_by_name => true, ignore_errors => true)
WHERE sessionId = '$SID'
ORDER BY timestamp
LIMIT 50;"
```

### Human prompts only — post-compaction intent recovery

The on-disk log is append-only, so compaction never erases prompts. For genuine human typing,
use the `prompts` helper subcommand (it applies the `is_human_prompt` predicate from
[Deriving `msg_kind`](#deriving-msg_kind-and-genuine-human-prompts)):

```bash
.claude/skills/introspect/scripts/introspect_duckdb.sh prompts SESSION_ID
```

Inline equivalent — string-content user events that are **not** a Claude Code wrapper
(slash-command expansion, task-notification, caveat, …):

```bash
duckdb -markdown -c "
SELECT timestamp, json_extract_string(message.content, '\$') AS prompt
FROM read_json_auto('$PROJECT/*.jsonl', union_by_name => true, ignore_errors => true)
WHERE type = 'user'
  AND COALESCE(isMeta, false) = false
  AND json_type(message.content) = 'VARCHAR'           -- string scalar, not a block array
  AND NOT regexp_matches(
        ltrim(json_extract_string(message.content, '\$')),
        '^(<(command-name|command-message|command-args|task-notification|local-command-caveat)>|Caveat:|[[]Request interrupted)')
ORDER BY timestamp;"
```

> Drop the final `regexp_matches` clause to get the *loose* `msg_kind='human'` set (every
> string-content user event, including `/slash` commands and caveats) — that is what
> `prompts --raw` returns.

### Full-text search across all sessions (the `search` / FTS5 analog)

Add `filename => true` to get the source file back as the result pointer:

```bash
duckdb -markdown -c "
SELECT filename, timestamp,
       LEFT(TRY_CAST(message.content AS VARCHAR), 120) AS hit
FROM read_json_auto('$PROJECT/**/*.jsonl',
       union_by_name => true, ignore_errors => true, filename => true)
WHERE TRY_CAST(message.content AS VARCHAR) ILIKE '%your search term%'
ORDER BY timestamp DESC
LIMIT 20;"
```

### Accurate cost rollup (requestId-deduped — see the gotcha above)

Pricing mirrors the cache's pre-computed cost: family rate × billable tokens, where
`billable = input + output×5 + cache_read×0.1 + cache_creation×1.25`, priced at
fable 10.0 / opus 5.0 / sonnet 3.0 / haiku 1.0 $ per Mtok.

```bash
duckdb -markdown -c "
WITH per_req AS (   -- collapse N block-rows to one row per request
  SELECT requestId,
         ANY_VALUE(message.model) AS model_id,
         ANY_VALUE(
             COALESCE(message.usage.input_tokens,0)
           + COALESCE(message.usage.output_tokens,0)         * 5.0
           + COALESCE(message.usage.cache_read_input_tokens,0)     * 0.1
           + COALESCE(message.usage.cache_creation_input_tokens,0) * 1.25
         ) AS billable
  FROM read_json_auto('$PROJECT/*.jsonl', union_by_name => true, ignore_errors => true)
  WHERE requestId IS NOT NULL AND message.usage IS NOT NULL
  GROUP BY requestId
)
SELECT
  CASE WHEN model_id LIKE '%fable%'  THEN 'fable'
       WHEN model_id LIKE '%opus%'   THEN 'opus'
       WHEN model_id LIKE '%sonnet%' THEN 'sonnet'
       WHEN model_id LIKE '%haiku%'  THEN 'haiku' ELSE 'unknown' END AS family,
  ROUND(SUM(billable * CASE WHEN model_id LIKE '%fable%'  THEN 10.0
                            WHEN model_id LIKE '%opus%'   THEN 5.0
                            WHEN model_id LIKE '%sonnet%' THEN 3.0
                            WHEN model_id LIKE '%haiku%'  THEN 1.0 ELSE 0.0 END / 1e6), 2) AS cost_usd
FROM per_req
GROUP BY 1
ORDER BY cost_usd DESC;"
```

### Deriving `msg_kind` and genuine human prompts

`message.content` is read by DuckDB as a **`JSON`** column, so the kind can be classified
precisely — `json_type(...)` distinguishes a string scalar (`'VARCHAR'`) from a content-block
array (`'ARRAY'`), and `json_extract_string(content, '$[0].type')` reads the first block's
type. This reproduces `introspect_sessions.py`'s 9-kind logic faithfully. The `--duckdb`
helper bakes the three expressions below into its `events` view; lift them into any ad-hoc
query.

**Base kind** (mirrors `_base_message_kind`):

```sql
CASE
  WHEN type = 'user' AND COALESCE(isMeta, false) THEN 'meta'
  WHEN type = 'user' AND json_type(message.content) = 'VARCHAR'
       THEN CASE WHEN ltrim(json_extract_string(message.content, '$')) LIKE '<task-notification>%'
                 THEN 'task_notification' ELSE 'human' END
  WHEN type = 'user' AND json_extract_string(message.content, '$[0].type') = 'tool_result' THEN 'tool_result'
  WHEN type = 'user' THEN 'user_text'
  WHEN type = 'assistant' AND json_extract_string(message.content, '$[0].type') = 'thinking' THEN 'thinking'
  WHEN type = 'assistant' AND json_extract_string(message.content, '$[0].type') = 'tool_use' THEN 'tool_use'
  WHEN type = 'assistant' THEN 'assistant_text'
  ELSE 'other'
END
```

**Subagent prefix** — an event is subagent context if it's a sidechain OR its file is nested
under a `{session_uuid}/` dir (so detect it from `isSidechain` plus the `filename`):

```sql
COALESCE(isSidechain, false)
  OR regexp_matches(filename, '/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/')
-- msg_kind = (is_subagent ? 'subagent-' || base_kind : base_kind)
```

**Genuine human prompts** — `msg_kind = 'human'` is *not* "what the user typed": it still
includes slash-command expansions and caveats that Claude Code injects as string-content user
events. The stricter `is_human_prompt` predicate excludes a known, evidence-derived set of
wrapper prefixes:

```sql
base_kind = 'human'
AND NOT is_subagent
AND NOT regexp_matches(
      ltrim(json_extract_string(message.content, '$')),
      '^(<(command-name|command-message|command-args|task-notification|local-command-caveat'
      || '|bash-input|bash-stdout|bash-stderr|system-reminder|user-prompt-submit-hook)>'
      || '|Caveat:|[[]Request interrupted)')
```

> **Parity check.** On a real session, this SQL `msg_kind` matched the SQLite cache's
> `msg_kind` **exactly for every message-bearing kind** (`human`, `tool_use`, `tool_result`,
> `thinking`, `assistant_text`, `task_notification`, `user_text`, and all `subagent-*`
> variants). Only the `other` bucket — pure system/progress rows (`attachment`, `mode`,
> `file-history-snapshot`, `queue-operation`, …) that are never introspection targets — may
> diverge in count.

## What You Lose vs. the Cache

This fallback answers the high-value questions (what happened, what was said, what it cost,
**and the 9-way `msg_kind` incl. genuine-human filtering** — see above), but the following are
**cache-only** features, computed at ingest with no raw-JSONL equivalent:

- **`event_edges` / cross-agent bridge traversal** (`promptId`-joined subagent threads).
- **Pre-computed `is_response_head`** (you must dedup by `requestId` yourself — see above).
- **Tokenometrics** (`context_ratio`, `tps`, `response_duration_ms`, session timing rollups).
- **The knowledge graph** (`nodes`, `edges`, `entity_clusters`, `leiden_communities`).

Treat DuckDB as the triage tool that keeps you unblocked. Once `introspect_sessions.sh
cache rebuild` succeeds again, switch back to the CLI for the full feature set.
