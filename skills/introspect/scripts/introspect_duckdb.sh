#!/usr/bin/env bash
# introspect_duckdb.sh — DuckDB fallback for the introspect skill.
#
# Queries the raw ~/.claude/projects/**/*.jsonl session logs DIRECTLY with the
# DuckDB CLI, bypassing both the SQLite cache and introspect_sessions.py.
#
# WHY PURE BASH (not a uv/Python script): this is the fallback used precisely
# when the Python toolchain is unavailable or broken (missing uv, traceback,
# stale/corrupt cache). A Python implementation would share the same failure
# modes it is meant to rescue. Its only dependencies are `bash` + the `duckdb`
# binary — nothing from the introspect toolchain.
#
# All subcommands query a DuckDB VIEW named `events` defined over the JSONL
# glob. The view adds three computed columns that mirror the Python tool:
#   * msg_kind        — the 9-kind classification, `subagent-` prefixed for
#                       sidechain / nested-subagent events (parity with the cache).
#   * text            — the unwrapped scalar string for string-content events
#                       (NULL for content-block arrays); handy for read/search.
#   * is_human_prompt — TRUE only for GENUINE user typing: msg_kind='human',
#                       not a subagent, AND not a Claude Code wrapper string
#                       (<command-name>, <command-message>, <task-notification>,
#                       <local-command-caveat>, bash-mode tags, system-reminder,
#                       caveat/interrupt notices). This is stricter than
#                       msg_kind='human', which still includes slash-command
#                       expansions and caveats.
#
# Usage: introspect_duckdb.sh <subcommand> [args...]   (run `--help` for details)

set -euo pipefail

PROJECTS_DIR="${HOME}/.claude/projects"

# ── Helpers ────────────────────────────────────────────────────────────────

die() { echo "error: $*" >&2; exit 1; }

# Double single-quotes so a value is safe to interpolate into a SQL literal.
sql_lit() { printf "%s" "${1//\'/\'\'}"; }

infer_project() {
  # CWD → Claude Code project-dir format (every '/' becomes '-').
  printf -- '%s' "${PWD//\//-}"
}

usage() {
  cat <<'EOF'
introspect_duckdb.sh — DuckDB fallback for the introspect skill

Queries raw ~/.claude/projects JSONL directly via the duckdb CLI (no cache, no Python).

USAGE:
  introspect_duckdb.sh [global-opts] <subcommand> [args]

GLOBAL OPTS:
  -p, --project ID   Project dir (kebab-cased path). Default: inferred from CWD.
      --all          Query ALL projects (overrides --project).
      --subagents    Include nested subagent/tool-result files (**/*.jsonl).
  -t, --kind KIND    Filter by msg_kind (human, tool_use, thinking, assistant_text,
                     tool_result, user_text, task_notification, meta, other). Matches
                     the `subagent-` variant too.
      --human        Only GENUINE human-typed prompts (excludes slash-command /
                     caveat / notification wrappers). Stricter than --kind human.
  -f, --format FMT   duckdb output: markdown (default) | table | box | json | jsonl
  -n, --limit N      Row limit (subcommands that list rows).
  -h, --help         Show this help.

SUBCOMMANDS:
  sessions                 List sessions (most-recent first): events, started, last_active.
  events <session-id>      Chronological events. Honors --kind / --human.
  prompts [session-id]     GENUINE human prompts (--human implied). Add --raw to include
                           every string-content user event (slash commands, caveats, …).
  search <term>            Substring search across message content. Honors --kind / --human
                           — e.g. search only what YOU typed:  search "foo" --human
  kinds                    Show the msg_kind distribution (a quick classification sanity check).
  cost [session-id]        requestId-deduped cost rollup by model family.
  sql <query>              Raw SQL against the `events` view (incl. msg_kind / text /
                           is_human_prompt), e.g.  sql "SELECT msg_kind, COUNT(*) FROM events GROUP BY 1"

NOTES:
  * Cost is deduped by requestId FIRST — raw JSONL repeats usage across content
    blocks, so a naive SUM over-counts 2-3x. See resources/duckdb-fallback.md.
  * msg_kind / is_human_prompt are derived in SQL to mirror introspect_sessions.py;
    they have no cross-agent event_edges or knowledge graph (cache-only features).
  * This is read-only; it never touches the SQLite cache.
EOF
}

# ── Arg parsing (global opts may precede the subcommand) ────────────────────

PROJECT=""
ALL_PROJECTS=0
SUBAGENTS=0
FORMAT="markdown"
LIMIT=""
KIND=""
HUMAN=0
RAW=0
POSITIONAL=()

while [[ $# -gt 0 ]]; do
  case "$1" in
    -p|--project)   PROJECT="$2"; shift 2 ;;
    --all)          ALL_PROJECTS=1; shift ;;
    --subagents)    SUBAGENTS=1; shift ;;
    -f|--format)    FORMAT="$2"; shift 2 ;;
    -n|--limit)     LIMIT="$2"; shift 2 ;;
    -t|--kind|-k)   KIND="$2"; shift 2 ;;
    --human)        HUMAN=1; shift ;;
    --raw)          RAW=1; shift ;;
    -h|--help)      usage; exit 0 ;;
    --)             shift; while [[ $# -gt 0 ]]; do POSITIONAL+=("$1"); shift; done ;;
    *)              POSITIONAL+=("$1"); shift ;;
  esac
done

[[ ${#POSITIONAL[@]} -eq 0 ]] && { usage; exit 2; }

SUBCMD="${POSITIONAL[0]}"
ARGS=("${POSITIONAL[@]:1}")

command -v duckdb >/dev/null 2>&1 || die "duckdb not found on PATH. Install with: brew install duckdb"

# ── Resolve the JSONL glob ──────────────────────────────────────────────────

if [[ "$ALL_PROJECTS" -eq 1 ]]; then
  PROJECT_GLOB_ROOT="$PROJECTS_DIR/*"
else
  [[ -z "$PROJECT" ]] && PROJECT="$(infer_project)"
  PROJECT_GLOB_ROOT="$PROJECTS_DIR/$PROJECT"
  [[ -d "$PROJECT_GLOB_ROOT" ]] || die "project dir not found: $PROJECT_GLOB_ROOT (use --project or --all)"
fi

if [[ "$SUBAGENTS" -eq 1 ]]; then
  GLOB="$PROJECT_GLOB_ROOT/**/*.jsonl"
else
  GLOB="$PROJECT_GLOB_ROOT/*.jsonl"
fi

# ── The `events` view: msg_kind / text / is_human_prompt computed in SQL ────
#
# Inner SELECT derives base_kind, is_subagent, and the unwrapped text once;
# the outer SELECT prefixes the subagent marker and applies the genuine-human
# predicate (a known set of Claude Code wrapper tags, evidence-derived).

# A literal-[ in a POSIX-ish regexp; use [[] to dodge backslash-escaping quirks.
_WRAPPER_RE='^(<(command-name|command-message|command-args|task-notification|local-command-caveat|bash-input|bash-stdout|bash-stderr|system-reminder|user-prompt-submit-hook)>|Caveat:|[[]Request interrupted)'

VIEW="CREATE VIEW events AS
SELECT *,
       CASE WHEN is_subagent THEN 'subagent-' || base_kind ELSE base_kind END AS msg_kind,
       (base_kind = 'human'
        AND NOT is_subagent
        AND NOT regexp_matches(ltrim(text), '${_WRAPPER_RE}')) AS is_human_prompt
FROM (
  SELECT *,
    CASE
      WHEN type = 'user' AND COALESCE(isMeta, false) THEN 'meta'
      WHEN type = 'user' AND json_type(message.content) = 'VARCHAR'
           THEN CASE WHEN ltrim(json_extract_string(message.content, '\$')) LIKE '<task-notification>%'
                     THEN 'task_notification' ELSE 'human' END
      WHEN type = 'user' AND json_extract_string(message.content, '\$[0].type') = 'tool_result' THEN 'tool_result'
      WHEN type = 'user' THEN 'user_text'
      WHEN type = 'assistant' AND json_extract_string(message.content, '\$[0].type') = 'thinking' THEN 'thinking'
      WHEN type = 'assistant' AND json_extract_string(message.content, '\$[0].type') = 'tool_use' THEN 'tool_use'
      WHEN type = 'assistant' THEN 'assistant_text'
      ELSE 'other'
    END AS base_kind,
    ( COALESCE(isSidechain, false)
      OR regexp_matches(filename, '/[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}/') ) AS is_subagent,
    CASE WHEN json_type(message.content) = 'VARCHAR'
         THEN json_extract_string(message.content, '\$') END AS text
  FROM read_json_auto('${GLOB}', union_by_name => true, ignore_errors => true, filename => true)
);"

# Map -f to a duckdb output flag.
case "$FORMAT" in
  markdown) FMT_FLAG="-markdown" ;;
  table)    FMT_FLAG="-table" ;;
  box)      FMT_FLAG="-box" ;;
  json)     FMT_FLAG="-json" ;;
  jsonl)    FMT_FLAG="-jsonlines" ;;
  *)        die "unknown --format '$FORMAT' (markdown|table|box|json|jsonl)" ;;
esac

# NB: these emit optional SQL fragments via command substitution into an
# assignment. They MUST always return 0 — under `set -e`, a helper that ends on
# a false `[[ … ]]` test returns 1, and if it is the last substitution in an
# assignment it aborts the whole script. Hence `if` blocks, not `&&` chains.
limit_clause() { if [[ -n "$LIMIT" ]]; then printf ' LIMIT %s' "$((LIMIT))"; fi; }

# Shared msg_kind / --human predicates appended to a WHERE clause.
kind_clause() {
  if [[ -n "$KIND" ]]; then
    printf " AND (msg_kind = '%s' OR msg_kind = 'subagent-%s')" \
      "$(sql_lit "$KIND")" "$(sql_lit "$KIND")"
  fi
}
human_clause() { if [[ "$HUMAN" -eq 1 ]]; then printf ' AND is_human_prompt'; fi; }

run_sql() { duckdb "$FMT_FLAG" -c "$VIEW $1"; }

# ── Subcommand dispatch ─────────────────────────────────────────────────────

case "$SUBCMD" in
  sessions)
    run_sql "SELECT sessionId AS session_id, COUNT(*) AS events,
                    MIN(timestamp) AS started, MAX(timestamp) AS last_active
             FROM events GROUP BY sessionId ORDER BY last_active DESC$(limit_clause);"
    ;;

  events)
    [[ ${#ARGS[@]} -ge 1 ]] || die "events needs a <session-id>"
    where="WHERE sessionId = '$(sql_lit "${ARGS[0]}")'$(kind_clause)$(human_clause)"
    run_sql "SELECT timestamp, msg_kind, requestId,
                    LEFT(COALESCE(text, CAST(message.content AS VARCHAR)), 120) AS preview
             FROM events ${where} ORDER BY timestamp$(limit_clause);"
    ;;

  prompts)
    # Genuine human typing by default; --raw widens to every string-content user event.
    if [[ "$RAW" -eq 1 ]]; then
      where="WHERE msg_kind = 'human'"
    else
      where="WHERE is_human_prompt"
    fi
    [[ ${#ARGS[@]} -ge 1 ]] && where="$where AND sessionId = '$(sql_lit "${ARGS[0]}")'"
    run_sql "SELECT timestamp, sessionId AS session_id, text AS prompt
             FROM events ${where} ORDER BY timestamp$(limit_clause);"
    ;;

  search)
    [[ ${#ARGS[@]} -ge 1 ]] || die "search needs a <term>"
    term="$(sql_lit "${ARGS[*]}")"
    [[ -z "$LIMIT" ]] && LIMIT=50
    where="WHERE TRY_CAST(message.content AS VARCHAR) ILIKE '%${term}%'$(kind_clause)$(human_clause)"
    run_sql "SELECT filename, timestamp, sessionId AS session_id, msg_kind,
                    LEFT(COALESCE(text, CAST(message.content AS VARCHAR)), 120) AS hit
             FROM events ${where} ORDER BY timestamp DESC$(limit_clause);"
    ;;

  kinds)
    run_sql "SELECT msg_kind, COUNT(*) AS n,
                    SUM(CASE WHEN is_human_prompt THEN 1 ELSE 0 END) AS human_prompts
             FROM events GROUP BY msg_kind ORDER BY n DESC;"
    ;;

  cost)
    extra=""
    [[ ${#ARGS[@]} -ge 1 ]] && extra="AND sessionId = '$(sql_lit "${ARGS[0]}")'"
    run_sql "WITH per_req AS (
               SELECT requestId,
                      ANY_VALUE(message.model) AS model_id,
                      ANY_VALUE(
                          COALESCE(message.usage.input_tokens,0)
                        + COALESCE(message.usage.output_tokens,0)             * 5.0
                        + COALESCE(message.usage.cache_read_input_tokens,0)   * 0.1
                        + COALESCE(message.usage.cache_creation_input_tokens,0) * 1.25
                      ) AS billable
               FROM events
               WHERE requestId IS NOT NULL AND message.usage IS NOT NULL ${extra}
               GROUP BY requestId
             )
             SELECT CASE WHEN model_id LIKE '%fable%'  THEN 'fable'
                         WHEN model_id LIKE '%opus%'   THEN 'opus'
                         WHEN model_id LIKE '%sonnet%' THEN 'sonnet'
                         WHEN model_id LIKE '%haiku%'  THEN 'haiku' ELSE 'unknown' END AS family,
                    COUNT(*) AS requests,
                    ROUND(SUM(billable * CASE WHEN model_id LIKE '%fable%'  THEN 10.0
                                              WHEN model_id LIKE '%opus%'   THEN 5.0
                                              WHEN model_id LIKE '%sonnet%' THEN 3.0
                                              WHEN model_id LIKE '%haiku%'  THEN 1.0
                                              ELSE 0.0 END / 1e6), 2) AS cost_usd
             FROM per_req GROUP BY 1 ORDER BY cost_usd DESC;"
    ;;

  sql)
    [[ ${#ARGS[@]} -ge 1 ]] || die "sql needs a <query> (use the \`events\` view)"
    run_sql "${ARGS[*]}"
    ;;

  *)
    die "unknown subcommand '$SUBCMD' (run --help)"
    ;;
esac
