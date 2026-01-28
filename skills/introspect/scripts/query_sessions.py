#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "duckdb>=1.0.0",
#   "pytz",
# ]
# ///
"""
query_sessions - Query and analyze Claude Code session logs using DuckDB.

A self-contained CLI for querying session JSONL files stored at:
    ~/.claude/projects/{project-path-kebab-cased}/{session_uuid}.jsonl

Usage:
    uv run query_sessions.py projects              # List all projects
    uv run query_sessions.py sessions PROJECT      # List sessions for a project
    uv run query_sessions.py turns SESSION         # Show turns in a session
    uv run query_sessions.py tools SESSION         # Show tool usage in a session
    uv run query_sessions.py search PATTERN        # Search across all sessions
"""
import argparse
import json
import logging
from datetime import datetime, timedelta
from pathlib import Path
from textwrap import dedent
from typing import Any

import duckdb

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

CLAUDE_HOME = Path.home() / ".claude"
PROJECTS_PATH = CLAUDE_HOME / "projects"

# Logging setup
log = logging.getLogger(__name__)

# Helper lambdas
_run = lambda cmd: __import__("subprocess").check_output(__import__("shlex").split(cmd), text=True).strip()  # noqa: E731

# ============================================================================
# DuckDB Query Helpers
# ============================================================================


def get_connection() -> duckdb.DuckDBPyConnection:
    """Create an in-memory DuckDB connection."""
    return duckdb.connect(":memory:")


def execute_query(sql: str, params: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as list of dicts."""
    conn = get_connection()
    try:
        if params:
            for key, value in params.items():
                sql = sql.replace(f"__{key}__", str(value))
        log.debug(f"Executing SQL:\n{sql[:500]}...")
        result = conn.execute(sql).fetchall()
        columns = [desc[0] for desc in conn.description]
        return [dict(zip(columns, row, strict=False)) for row in result]
    finally:
        conn.close()


def get_projects_glob(project_filter: str | None = None) -> str:
    """Get the glob pattern for session files."""
    if project_filter:
        return f"{PROJECTS_PATH}/{project_filter}/*.jsonl"
    return f"{PROJECTS_PATH}/**/*.jsonl"


# ============================================================================
# Core Query Functions
# ============================================================================


def list_projects() -> list[dict[str, Any]]:
    """List all projects with session counts and date ranges."""
    log.info("Listing all projects...")
    sql = f"""
    WITH session_data AS (
        SELECT
            regexp_extract(filename, 'projects/([^/]+)/', 1) AS project_id,
            regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) AS session_id,
            MIN(TRY_CAST(timestamp AS TIMESTAMPTZ)) AS first_event,
            MAX(TRY_CAST(timestamp AS TIMESTAMPTZ)) AS last_event
        FROM read_json_auto('{PROJECTS_PATH}/**/*.jsonl',
                            format='newline_delimited',
                            filename=true,
                            ignore_errors=true,
                            maximum_object_size=10485760)
        WHERE timestamp IS NOT NULL
        GROUP BY 1, 2
    )
    SELECT
        project_id,
        COUNT(DISTINCT session_id) AS session_count,
        MIN(first_event) AS first_activity,
        MAX(last_event) AS last_activity
    FROM session_data
    GROUP BY project_id
    ORDER BY last_activity DESC
    """
    return execute_query(sql)


def list_sessions(
    project_id: str,
    limit: int = 20,
    since: str | None = None
) -> list[dict[str, Any]]:
    """List sessions for a project with event counts and time info."""
    log.info(f"Listing sessions for project: {project_id}")
    glob_pattern = get_projects_glob(project_id)

    where_clause = ""
    if since:
        since_ts = parse_time_filter(since)
        where_clause = f"AND TRY_CAST(timestamp AS TIMESTAMPTZ) >= TIMESTAMPTZ '{since_ts}'"

    sql = f"""
    WITH event_data AS (
        SELECT
            regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) AS session_id,
            type,
            TRY_CAST(timestamp AS TIMESTAMPTZ) AS ts
        FROM read_json_auto('{glob_pattern}',
                            format='newline_delimited',
                            filename=true,
                            ignore_errors=true,
                            maximum_object_size=10485760)
        WHERE timestamp IS NOT NULL
        {where_clause}
    )
    SELECT
        session_id,
        COUNT(*) AS event_count,
        COUNT(CASE WHEN type = 'user' THEN 1 END) AS user_turns,
        COUNT(CASE WHEN type = 'assistant' THEN 1 END) AS assistant_turns,
        COUNT(CASE WHEN type = 'tool_use' THEN 1 END) AS tool_calls,
        MIN(ts) AS started_at,
        MAX(ts) AS last_activity,
        MAX(ts) - MIN(ts) AS duration
    FROM event_data
    GROUP BY session_id
    ORDER BY last_activity DESC
    LIMIT {limit}
    """
    return execute_query(sql)


def get_session_turns(
    session_id: str,
    project_id: str | None = None,
    event_types: list[str] | None = None,
    since: str | None = None,
    until: str | None = None,
    limit: int = 100,
    offset: int = 0,
    include_content: bool = True
) -> list[dict[str, Any]]:
    """Get turns (events) for a session with filtering options."""
    log.info(f"Getting turns for session: {session_id}")
    glob_pattern = get_projects_glob(project_id)

    where_clauses = [f"session_id = '{session_id}'"]

    if event_types:
        types_list = ", ".join(f"'{t}'" for t in event_types)
        where_clauses.append(f"type IN ({types_list})")

    if since:
        since_ts = parse_time_filter(since)
        where_clauses.append(f"ts >= TIMESTAMPTZ '{since_ts}'")

    if until:
        until_ts = parse_time_filter(until)
        where_clauses.append(f"ts <= TIMESTAMPTZ '{until_ts}'")

    where_sql = " AND ".join(where_clauses)

    content_cols = """
        message.content AS content,
        message.role AS role,
    """ if include_content else ""

    sql = f"""
    WITH raw_events AS (
        SELECT
            regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) AS session_id,
            type,
            TRY_CAST(timestamp AS TIMESTAMPTZ) AS ts,
            {content_cols}
            message.model AS model,
            message.usage.input_tokens AS input_tokens,
            message.usage.output_tokens AS output_tokens,
            uuid,
            parentUuid
        FROM read_json_auto('{glob_pattern}',
                            format='newline_delimited',
                            filename=true,
                            ignore_errors=true,
                            maximum_object_size=10485760)
    )
    SELECT
        ROW_NUMBER() OVER (ORDER BY ts) AS turn_num,
        type,
        ts AS timestamp,
        {'content, role,' if include_content else ''}
        model,
        COALESCE(input_tokens, 0) AS input_tokens,
        COALESCE(output_tokens, 0) AS output_tokens,
        uuid,
        parentUuid AS parent_uuid
    FROM raw_events
    WHERE {where_sql}
    ORDER BY ts
    LIMIT {limit} OFFSET {offset}
    """
    return execute_query(sql)


def get_tool_usage(
    session_id: str,
    project_id: str | None = None,
    tool_name: str | None = None
) -> list[dict[str, Any]]:
    """Get tool usage details for a session.

    Tool use is nested inside assistant messages:
    event.type = "assistant" -> event.message.content[].type = "tool_use"
    """
    log.info(f"Getting tool usage for session: {session_id}")
    glob_pattern = get_projects_glob(project_id)

    tool_filter = ""
    if tool_name:
        tool_filter = f"AND json_extract_string(content_item, '$.name') LIKE '%{tool_name}%'"

    sql = f"""
    WITH assistant_events AS (
        SELECT
            regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) AS session_id,
            TRY_CAST(timestamp AS TIMESTAMPTZ) AS ts,
            CAST(message.content AS JSON) AS content_json
        FROM read_json_auto('{glob_pattern}',
                            format='newline_delimited',
                            filename=true,
                            ignore_errors=true,
                            maximum_object_size=10485760)
        WHERE type = 'assistant'
          AND regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) = '{session_id}'
          AND message.content IS NOT NULL
    ),
    unnested AS (
        SELECT
            session_id,
            ts,
            UNNEST(from_json(content_json, '["json"]')) AS content_item
        FROM assistant_events
    )
    SELECT
        session_id,
        ts AS timestamp,
        json_extract_string(content_item, '$.name') AS tool_name,
        json_extract_string(content_item, '$.id') AS tool_call_id,
        json_extract(content_item, '$.input') AS tool_input
    FROM unnested
    WHERE json_extract_string(content_item, '$.type') = 'tool_use'
      {tool_filter}
    ORDER BY ts
    """
    return execute_query(sql)


def get_tool_summary(
    session_id: str,
    project_id: str | None = None
) -> list[dict[str, Any]]:
    """Get summary of tool usage in a session.

    Tool use is nested inside assistant messages:
    event.type = "assistant" -> event.message.content[].type = "tool_use"
    """
    log.info(f"Getting tool summary for session: {session_id}")
    glob_pattern = get_projects_glob(project_id)

    sql = f"""
    WITH assistant_events AS (
        SELECT
            TRY_CAST(timestamp AS TIMESTAMPTZ) AS ts,
            CAST(message.content AS JSON) AS content_json
        FROM read_json_auto('{glob_pattern}',
                            format='newline_delimited',
                            filename=true,
                            ignore_errors=true,
                            maximum_object_size=10485760)
        WHERE type = 'assistant'
          AND regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) = '{session_id}'
          AND message.content IS NOT NULL
    ),
    unnested AS (
        SELECT
            ts,
            UNNEST(from_json(content_json, '["json"]')) AS content_item
        FROM assistant_events
    ),
    tool_uses AS (
        SELECT
            json_extract_string(content_item, '$.name') AS tool_name,
            ts
        FROM unnested
        WHERE json_extract_string(content_item, '$.type') = 'tool_use'
    )
    SELECT
        tool_name,
        COUNT(*) AS call_count,
        MIN(ts) AS first_used,
        MAX(ts) AS last_used
    FROM tool_uses
    GROUP BY tool_name
    ORDER BY call_count DESC
    """
    return execute_query(sql)


def search_sessions(
    pattern: str,
    project_id: str | None = None,
    event_types: list[str] | None = None,
    limit: int = 50
) -> list[dict[str, Any]]:
    """Search across sessions for a pattern in message content."""
    log.info(f"Searching for pattern: {pattern}")
    glob_pattern = get_projects_glob(project_id)

    type_filter = ""
    if event_types:
        types_list = ", ".join(f"'{t}'" for t in event_types)
        type_filter = f"AND type IN ({types_list})"

    sql = f"""
    SELECT
        regexp_extract(filename, 'projects/([^/]+)/', 1) AS project_id,
        regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) AS session_id,
        type,
        TRY_CAST(timestamp AS TIMESTAMPTZ) AS timestamp,
        CASE
            WHEN message.content IS NOT NULL THEN LEFT(CAST(message.content AS VARCHAR), 200)
            ELSE NULL
        END AS content_preview
    FROM read_json_auto('{glob_pattern}',
                        format='newline_delimited',
                        filename=true,
                        ignore_errors=true,
                        maximum_object_size=10485760)
    WHERE CAST(message.content AS VARCHAR) ILIKE '%{pattern}%'
      {type_filter}
    ORDER BY timestamp DESC
    LIMIT {limit}
    """
    return execute_query(sql)


def get_session_summary(
    session_id: str,
    project_id: str | None = None
) -> dict[str, Any]:
    """Get a comprehensive summary of a session."""
    log.info(f"Getting summary for session: {session_id}")
    glob_pattern = get_projects_glob(project_id)

    # Get basic counts
    sql = f"""
    SELECT
        COUNT(*) AS total_events,
        COUNT(CASE WHEN type = 'user' THEN 1 END) AS user_messages,
        COUNT(CASE WHEN type = 'assistant' THEN 1 END) AS assistant_messages,
        COUNT(CASE WHEN type = 'thinking' THEN 1 END) AS thinking_blocks,
        MIN(TRY_CAST(timestamp AS TIMESTAMPTZ)) AS started_at,
        MAX(TRY_CAST(timestamp AS TIMESTAMPTZ)) AS ended_at,
        MAX(TRY_CAST(timestamp AS TIMESTAMPTZ)) - MIN(TRY_CAST(timestamp AS TIMESTAMPTZ)) AS duration,
        COUNT(DISTINCT message.model) AS models_used
    FROM read_json_auto('{glob_pattern}',
                        format='newline_delimited',
                        filename=true,
                        ignore_errors=true,
                        maximum_object_size=10485760)
    WHERE regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) = '{session_id}'
    """
    results = execute_query(sql)
    summary = results[0] if results else {}

    # Get token usage from assistant messages (more reliable nested JSON parsing)
    token_sql = f"""
    SELECT
        COALESCE(SUM(TRY_CAST(json_extract(message, '$.usage.input_tokens') AS BIGINT)), 0) AS input_tokens,
        COALESCE(SUM(TRY_CAST(json_extract(message, '$.usage.output_tokens') AS BIGINT)), 0) AS output_tokens,
        COALESCE(SUM(TRY_CAST(json_extract(message, '$.usage.cache_read_input_tokens') AS BIGINT)), 0) AS cache_read_tokens,
        COALESCE(SUM(TRY_CAST(json_extract(message, '$.usage.cache_creation_input_tokens') AS BIGINT)), 0) AS cache_creation_tokens
    FROM read_json_auto('{glob_pattern}',
                        format='newline_delimited',
                        filename=true,
                        ignore_errors=true,
                        maximum_object_size=10485760)
    WHERE regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) = '{session_id}'
      AND type = 'assistant'
      AND message IS NOT NULL
    """
    token_results = execute_query(token_sql)
    if token_results:
        summary.update(token_results[0])
        # Calculate total billable tokens
        summary["total_billable_tokens"] = (
            summary.get("input_tokens", 0) +
            summary.get("output_tokens", 0) +
            summary.get("cache_creation_tokens", 0)
        )

    # Get tool call count
    tool_sql = f"""
    WITH assistant_events AS (
        SELECT CAST(message.content AS JSON) AS content_json
        FROM read_json_auto('{glob_pattern}',
                            format='newline_delimited',
                            filename=true,
                            ignore_errors=true,
                            maximum_object_size=10485760)
        WHERE type = 'assistant'
          AND regexp_extract(filename, '/([^/]+)\\.jsonl$', 1) = '{session_id}'
          AND message.content IS NOT NULL
    ),
    unnested AS (
        SELECT UNNEST(from_json(content_json, '["json"]')) AS content_item
        FROM assistant_events
    )
    SELECT COUNT(*) AS tool_calls
    FROM unnested
    WHERE json_extract_string(content_item, '$.type') = 'tool_use'
    """
    tool_results = execute_query(tool_sql)
    if tool_results:
        summary["tool_calls"] = tool_results[0].get("tool_calls", 0)

    return summary


def get_session_cost(
    session_id: str,
    project_id: str | None = None,
    model: str | None = None,
) -> dict[str, Any]:
    """Estimate cost for a session based on token usage.

    Pricing (per 1M tokens, as of Jan 2025):
        Claude Opus 4.5: $15 input, $75 output
        Claude Sonnet 3.5: $3 input, $15 output
        Cache reads: 90% discount (0.1x)
        Cache writes: 25% premium (1.25x)
    """
    log.info(f"Getting cost estimate for session: {session_id}")

    summary = get_session_summary(session_id, project_id)
    if not summary:
        return {"error": "Session not found"}

    input_tokens = summary.get("input_tokens", 0)
    output_tokens = summary.get("output_tokens", 0)
    cache_read = summary.get("cache_read_tokens", 0)
    cache_creation = summary.get("cache_creation_tokens", 0)

    # Detect model from session or use provided/default
    if not model:
        model = "opus"  # Default assumption

    # Pricing per million tokens
    if "opus" in model.lower():
        input_price = 15.0
        output_price = 75.0
    else:  # sonnet
        input_price = 3.0
        output_price = 15.0

    # Calculate costs
    input_cost = (input_tokens / 1_000_000) * input_price
    output_cost = (output_tokens / 1_000_000) * output_price
    cache_read_cost = (cache_read / 1_000_000) * input_price * 0.1  # 90% discount
    cache_write_cost = (cache_creation / 1_000_000) * input_price * 1.25  # 25% premium

    total_cost = input_cost + output_cost + cache_read_cost + cache_write_cost

    return {
        "session_id": session_id,
        "model": model,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cache_read_tokens": cache_read,
        "cache_creation_tokens": cache_creation,
        "input_cost_usd": round(input_cost, 4),
        "output_cost_usd": round(output_cost, 4),
        "cache_read_cost_usd": round(cache_read_cost, 4),
        "cache_write_cost_usd": round(cache_write_cost, 4),
        "total_cost_usd": round(total_cost, 4),
    }


def get_session_agents(
    session_id: str,
    project_id: str | None = None,
) -> list[dict[str, Any]]:
    """List all subagents (sidechains) within a session.

    Subagents are identified by:
    - isSidechain: true
    - agentId: unique identifier
    - slug: human-readable name

    Returns summary of each subagent including tool counts and token usage.
    """
    log.info(f"Getting subagents for session: {session_id}")

    glob_pattern = get_projects_glob(project_id)

    # Find session file
    import glob as glob_module
    session_files = glob_module.glob(str(glob_pattern))
    session_file = None
    for f in session_files:
        if session_id in f:
            session_file = f
            break

    if not session_file:
        return [{"error": f"Session not found: {session_id}"}]

    # Parse and collect agent info
    agents: dict[str, dict[str, Any]] = {}

    with open(session_file, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)

                # agentId can be at top level or nested in data
                agent_id = obj.get("agentId")
                if not agent_id:
                    data = obj.get("data", {})
                    if isinstance(data, dict):
                        agent_id = data.get("agentId")
                if not agent_id:
                    continue

                is_sidechain = obj.get("isSidechain", False)
                slug = obj.get("slug", "")
                timestamp = obj.get("timestamp", "")
                event_type = obj.get("type", "")

                if agent_id not in agents:
                    agents[agent_id] = {
                        "agent_id": agent_id,
                        "slug": slug,
                        "is_sidechain": is_sidechain,
                        "first_event": timestamp,
                        "last_event": timestamp,
                        "event_count": 0,
                        "tool_calls": 0,
                        "input_tokens": 0,
                        "output_tokens": 0,
                        "cache_read_tokens": 0,
                        "cache_creation_tokens": 0,
                    }

                agent = agents[agent_id]
                agent["event_count"] += 1
                agent["last_event"] = timestamp

                # Count tool calls
                if event_type == "assistant":
                    msg = obj.get("message", {})
                    content = msg.get("content", [])
                    if isinstance(content, list):
                        for block in content:
                            if isinstance(block, dict) and block.get("type") == "tool_use":
                                agent["tool_calls"] += 1

                    # Sum tokens
                    usage = msg.get("usage", {})
                    agent["input_tokens"] += usage.get("input_tokens", 0)
                    agent["output_tokens"] += usage.get("output_tokens", 0)
                    agent["cache_read_tokens"] += usage.get("cache_read_input_tokens", 0)
                    agent["cache_creation_tokens"] += usage.get("cache_creation_input_tokens", 0)

            except json.JSONDecodeError:
                continue

    # Convert to list and sort by first_event
    result = sorted(agents.values(), key=lambda x: x["first_event"])

    # Add total billable calculation
    for agent in result:
        agent["total_billable_tokens"] = (
            agent["input_tokens"] +
            agent["output_tokens"] +
            agent["cache_creation_tokens"]
        )

    return result


def get_session_messages(
    session_id: str,
    project_id: str | None = None,
    role: str | None = None,
    limit: int = 100,
    agent_id: str | None = None,
) -> list[dict[str, Any]]:
    """Extract user and/or assistant messages from a session.

    Useful for introspection - reviewing what was asked/answered in a session.
    Returns messages in chronological order with their content.

    Args:
        session_id: The session UUID
        project_id: Optional project filter for faster queries
        role: Filter by role ('user', 'assistant', or None for both)
        limit: Max messages to return
        agent_id: Filter to specific subagent (if None, includes all agents)
    """
    log.info(f"Getting messages for session: {session_id}")

    # Use Python-based extraction for reliable nested JSON handling
    # DuckDB struggles with deeply nested content arrays
    glob_pattern = get_projects_glob(project_id)

    # First, find the session file
    import glob as glob_module
    session_files = glob_module.glob(str(glob_pattern))
    session_file = None
    for f in session_files:
        if session_id in f:
            session_file = f
            break

    if not session_file:
        return [{"error": f"Session not found: {session_id}"}]

    messages = []
    with open(session_file, encoding="utf-8") as f:
        for line in f:
            try:
                obj = json.loads(line)
                event_type = obj.get("type")

                # Filter by agent_id if specified
                if agent_id and obj.get("agentId") != agent_id:
                    continue

                # Filter by role if specified
                if role == "user" and event_type != "user":
                    continue
                if role == "assistant" and event_type != "assistant":
                    continue
                if role is None and event_type not in ("user", "assistant"):
                    continue

                msg = obj.get("message", {})
                content = msg.get("content", "")
                timestamp = obj.get("timestamp", "")

                # Handle content - can be string or array
                if isinstance(content, list):
                    # Extract text from content blocks
                    text_parts = []
                    for block in content:
                        if isinstance(block, dict):
                            if block.get("type") == "text":
                                text_parts.append(block.get("text", ""))
                        elif isinstance(block, str):
                            text_parts.append(block)
                    content = "\n".join(text_parts)

                if content and isinstance(content, str) and content.strip():
                    messages.append({
                        "role": event_type,
                        "timestamp": timestamp,
                        "content": content.strip()[:2000],  # Truncate long messages
                    })

                    if len(messages) >= limit:
                        break
            except json.JSONDecodeError:
                continue

    return messages


# ============================================================================
# Utility Functions
# ============================================================================


def parse_time_filter(time_str: str) -> str:
    """Parse a time filter string into an ISO timestamp.

    Supports:
        - ISO format: '2025-01-14T10:00:00'
        - Relative: '1h' (1 hour ago), '30m' (30 minutes ago), '7d' (7 days ago)
    """
    time_str = time_str.strip()

    if time_str.endswith(("h", "m", "d", "w")):
        unit = time_str[-1]
        try:
            value = int(time_str[:-1])
        except ValueError:
            return time_str

        now = datetime.now()
        if unit == "m":
            delta = timedelta(minutes=value)
        elif unit == "h":
            delta = timedelta(hours=value)
        elif unit == "d":
            delta = timedelta(days=value)
        elif unit == "w":
            delta = timedelta(weeks=value)
        else:
            return time_str

        return (now - delta).isoformat()

    return time_str


def format_output(data: Any, output_format: str = "table") -> str:
    """Format output data for display."""
    if output_format == "json":
        return json.dumps(data, indent=2, default=str)

    if output_format == "jsonl":
        return "\n".join(json.dumps(row, default=str) for row in data)

    # Table format
    if not data:
        return "No results found."

    if isinstance(data, dict):
        data = [data]

    if not data:
        return "No results found."

    columns = list(data[0].keys())

    widths = {}
    for col in columns:
        widths[col] = max(
            len(str(col)),
            max(len(str(row.get(col, ""))[:50]) for row in data)
        )

    lines = []
    header = " | ".join(str(col).ljust(widths[col])[:50] for col in columns)
    lines.append(header)
    lines.append("-" * len(header))

    for row in data:
        line = " | ".join(
            str(row.get(col, ""))[:50].ljust(widths[col])
            for col in columns
        )
        lines.append(line)

    return "\n".join(lines)


# ============================================================================
# CLI Interface
# ============================================================================


def main(args: argparse.Namespace) -> None:
    """Main entry point."""
    try:
        if args.command == "projects":
            result = list_projects()

        elif args.command == "sessions":
            result = list_sessions(
                args.project_id,
                limit=args.limit,
                since=args.since
            )

        elif args.command == "turns":
            result = get_session_turns(
                args.session_id,
                project_id=args.project,
                event_types=args.types,
                since=args.since,
                until=args.until,
                limit=args.limit,
                offset=args.offset,
                include_content=not args.no_content
            )

        elif args.command == "tools":
            if args.detail:
                result = get_tool_usage(
                    args.session_id,
                    project_id=args.project,
                    tool_name=args.tool
                )
            else:
                result = get_tool_summary(
                    args.session_id,
                    project_id=args.project
                )

        elif args.command == "search":
            result = search_sessions(
                args.pattern,
                project_id=args.project,
                event_types=args.types,
                limit=args.limit
            )

        elif args.command == "summary":
            result = get_session_summary(
                args.session_id,
                project_id=args.project
            )

        elif args.command == "cost":
            result = get_session_cost(
                args.session_id,
                project_id=args.project,
                model=args.model
            )

        elif args.command == "messages":
            result = get_session_messages(
                args.session_id,
                project_id=args.project,
                role=args.role,
                limit=args.limit,
                agent_id=getattr(args, 'agent', None)
            )

        elif args.command == "agents":
            result = get_session_agents(
                args.session_id,
                project_id=args.project
            )
        else:
            log.error(f"Unknown command: {args.command}")
            return

        log.info(format_output(result, args.format))

    except Exception as e:
        log.exception(f"Error: {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} - Query and analyze Claude Code session logs using DuckDB.

        Session files are stored at:
            ~/.claude/projects/{{project-path-kebab-cased}}/{{session_uuid}}.jsonl

        Event types in session files:
            user        - User messages
            assistant   - Claude's responses
            tool_use    - Tool call requests
            tool_result - Tool execution results
            thinking    - Claude's thinking blocks
            summary     - Session summary

        INPUTS:
            {PROJECTS_PATH}/**/*.jsonl

        Examples:
            uv run {SCRIPT_NAME}.py projects
            uv run {SCRIPT_NAME}.py sessions -Users-joshpeak-play-myproject
            uv run {SCRIPT_NAME}.py turns SESSION_ID -t user assistant
            uv run {SCRIPT_NAME}.py tools SESSION_ID --detail
            uv run {SCRIPT_NAME}.py search "error" -p PROJECT
        """)
    )

    # Global options
    parser.add_argument("-q", "--quiet", action="store_true", help="Show only errors")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "-f", "--format",
        choices=["table", "json", "jsonl"],
        default="table",
        help="Output format (default: table)"
    )
    parser.add_argument(
        "-p", "--project",
        help="Filter to specific project ID (speeds up queries)"
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # projects command
    subparsers.add_parser("projects", help="List all projects with session counts")

    # sessions command
    sessions_parser = subparsers.add_parser("sessions", help="List sessions for a project")
    sessions_parser.add_argument("project_id", help="Project ID (kebab-cased path)")
    sessions_parser.add_argument("-n", "--limit", type=int, default=20, help="Max sessions (default: 20)")
    sessions_parser.add_argument("--since", help="Filter since timestamp (ISO or relative: 7d, 1h)")

    # turns command
    turns_parser = subparsers.add_parser("turns", help="Show turns in a session")
    turns_parser.add_argument("session_id", help="Session UUID")
    turns_parser.add_argument("-t", "--types", nargs="+", help="Filter event types (user, assistant, tool_use, etc.)")
    turns_parser.add_argument("--since", help="Filter events since timestamp")
    turns_parser.add_argument("--until", help="Filter events until timestamp")
    turns_parser.add_argument("-n", "--limit", type=int, default=100, help="Max turns (default: 100)")
    turns_parser.add_argument("--offset", type=int, default=0, help="Skip first N turns")
    turns_parser.add_argument("--no-content", action="store_true", help="Exclude message content (faster)")

    # tools command
    tools_parser = subparsers.add_parser("tools", help="Show tool usage in a session")
    tools_parser.add_argument("session_id", help="Session UUID")
    tools_parser.add_argument("--detail", action="store_true", help="Show all tool calls (not just summary)")
    tools_parser.add_argument("--tool", help="Filter to specific tool name")

    # search command
    search_parser = subparsers.add_parser("search", help="Search across sessions")
    search_parser.add_argument("pattern", help="Search pattern (case-insensitive)")
    search_parser.add_argument("-t", "--types", nargs="+", help="Filter event types")
    search_parser.add_argument("-n", "--limit", type=int, default=50, help="Max results (default: 50)")

    # summary command
    summary_parser = subparsers.add_parser("summary", help="Get comprehensive session summary")
    summary_parser.add_argument("session_id", help="Session UUID")

    # cost command
    cost_parser = subparsers.add_parser("cost", help="Estimate cost for a session")
    cost_parser.add_argument("session_id", help="Session UUID")
    cost_parser.add_argument("--model", choices=["opus", "sonnet"], default="opus",
                            help="Model for pricing (default: opus)")

    # messages command
    messages_parser = subparsers.add_parser("messages", help="Extract user/assistant messages from a session")
    messages_parser.add_argument("session_id", help="Session UUID")
    messages_parser.add_argument("--role", choices=["user", "assistant"],
                                help="Filter by role (default: both)")
    messages_parser.add_argument("-n", "--limit", type=int, default=100,
                                help="Max messages to return (default: 100)")
    messages_parser.add_argument("--agent", help="Filter to specific agent ID (subagent)")

    # agents command
    agents_parser = subparsers.add_parser("agents", help="List subagents (sidechains) within a session")
    agents_parser.add_argument("session_id", help="Session UUID")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S"
    )

    if not args.command:
        parser.print_help()
    else:
        main(args)
