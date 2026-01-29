#!/usr/bin/env python3
# /// script
# requires-python = ">=3.12"
# dependencies = [
#   "snowflake-connector-python>=3.6.0",
#   "cryptography>=42.0.0",
# ]
# ///
"""
explore_snowflake - Efficient Snowflake exploration for Claude Code sessions.

Provides CLI commands for common data exploration tasks using the Snowflake
Python connector. Uses a persistent connection to minimize overhead compared
to multiple CLI invocations.

Expects Snowflake environment variables to be set:
    SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH, SNOWFLAKE_ROLE

Usage:
    uv run explore_snowflake.py tables <schema>           # List tables in schema
    uv run explore_snowflake.py columns <table>           # Get column metadata
    uv run explore_snowflake.py profile <table>           # Profile table (counts, cardinality)
    uv run explore_snowflake.py sample <table> [limit]    # Sample rows from table
    uv run explore_snowflake.py distinct <table> <column> # Get distinct values
    uv run explore_snowflake.py query <sql>               # Run arbitrary SQL
    uv run explore_snowflake.py file <path>               # Run SQL from file

Examples:
    uv run explore_snowflake.py tables DATAVERSE_LANDING_PROD.S3_IGT_LOYALTY_EXTRACTS
    uv run explore_snowflake.py columns DATAVERSE_LANDING_PROD.S3_IGT_LOYALTY_EXTRACTS.DIMPATRON
    uv run explore_snowflake.py profile DATAVERSE_LANDING_PROD.S3_IGT_LOYALTY_EXTRACTS.FACTPLAYERSESSION
    uv run explore_snowflake.py sample DATAVERSE_LANDING_PROD.S3_IGT_LOYALTY_EXTRACTS.DIMSITE 20
"""
import argparse
import json
import logging
import os
from contextlib import contextmanager
from pathlib import Path
from textwrap import dedent
from typing import Any, Generator

import snowflake.connector
from cryptography.hazmat.backends import default_backend
from cryptography.hazmat.primitives import serialization

# ============================================================================
# Configuration
# ============================================================================

SCRIPT = Path(__file__)
SCRIPT_NAME = SCRIPT.stem
SCRIPT_DIR = SCRIPT.parent.resolve()

# Use current working directory as the project root
# (skill should be invoked from within the project)
PROJECT_ROOT = Path.cwd()

log = logging.getLogger(__name__)

# ============================================================================
# Connection Management
# ============================================================================


def load_private_key(key_path: str) -> bytes:
    """Load and decode a private key for Snowflake authentication."""
    key_path = os.path.expanduser(key_path)
    with open(key_path, "rb") as key_file:
        private_key = serialization.load_pem_private_key(
            key_file.read(),
            password=None,
            backend=default_backend(),
        )
    return private_key.private_bytes(
        encoding=serialization.Encoding.DER,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )


def get_connection_params() -> dict[str, Any]:
    """Build connection parameters from environment variables."""
    required = ["SNOWFLAKE_ACCOUNT", "SNOWFLAKE_USER", "SNOWFLAKE_PRIVATE_KEY_PATH"]
    missing = [k for k in required if not os.environ.get(k)]
    if missing:
        raise EnvironmentError(
            f"Missing required environment variables: {', '.join(missing)}\n"
            "Run: eval \"$(uv run python $(git rev-parse --show-toplevel)/scripts/exportenv.py)\""
        )

    params = {
        "account": os.environ["SNOWFLAKE_ACCOUNT"],
        "user": os.environ["SNOWFLAKE_USER"],
        "private_key": load_private_key(os.environ["SNOWFLAKE_PRIVATE_KEY_PATH"]),
    }

    # Optional params
    if role := os.environ.get("SNOWFLAKE_ROLE"):
        params["role"] = role
    if warehouse := os.environ.get("SNOWFLAKE_WAREHOUSE"):
        params["warehouse"] = warehouse
    if database := os.environ.get("SNOWFLAKE_DATABASE"):
        params["database"] = database
    if schema := os.environ.get("SNOWFLAKE_SCHEMA"):
        params["schema"] = schema

    return params


@contextmanager
def get_connection() -> Generator[snowflake.connector.SnowflakeConnection, None, None]:
    """Create a Snowflake connection as a context manager."""
    conn = None
    try:
        params = get_connection_params()
        log.debug(f"Connecting to Snowflake account: {params['account']}")
        conn = snowflake.connector.connect(**params)
        yield conn
    finally:
        if conn:
            conn.close()


def execute_query(conn: snowflake.connector.SnowflakeConnection, sql: str) -> list[dict[str, Any]]:
    """Execute a SQL query and return results as list of dicts."""
    log.debug(f"Executing SQL:\n{sql[:500]}...")
    cur = conn.cursor()
    try:
        cur.execute(sql)
        columns = [desc[0] for desc in cur.description] if cur.description else []
        rows = cur.fetchall()
        return [dict(zip(columns, row, strict=False)) for row in rows]
    finally:
        cur.close()


# ============================================================================
# Exploration Commands
# ============================================================================


def cmd_tables(conn: snowflake.connector.SnowflakeConnection, schema: str) -> list[dict[str, Any]]:
    """List tables in a schema."""
    log.info(f"Listing tables in schema: {schema}")
    sql = f"""
    SELECT
        table_name,
        table_type,
        row_count,
        bytes,
        created,
        last_altered
    FROM {schema.split('.')[0]}.INFORMATION_SCHEMA.TABLES
    WHERE table_schema = '{schema.split('.')[-1]}'
    ORDER BY table_name
    """
    return execute_query(conn, sql)


def cmd_columns(conn: snowflake.connector.SnowflakeConnection, table: str) -> list[dict[str, Any]]:
    """Get column metadata for a table."""
    log.info(f"Getting columns for table: {table}")
    parts = table.split(".")
    if len(parts) == 3:
        db, schema, tbl = parts
    elif len(parts) == 2:
        db = os.environ.get("SNOWFLAKE_DATABASE", "")
        schema, tbl = parts
    else:
        db = os.environ.get("SNOWFLAKE_DATABASE", "")
        schema = os.environ.get("SNOWFLAKE_SCHEMA", "")
        tbl = parts[0]

    sql = f"""
    SELECT
        column_name,
        data_type,
        is_nullable,
        column_default,
        ordinal_position
    FROM {db}.INFORMATION_SCHEMA.COLUMNS
    WHERE table_schema = '{schema}'
      AND table_name = '{tbl}'
    ORDER BY ordinal_position
    """
    return execute_query(conn, sql)


def cmd_profile(conn: snowflake.connector.SnowflakeConnection, table: str) -> list[dict[str, Any]]:
    """Profile a table: row count and cardinality of each column."""
    log.info(f"Profiling table: {table}")

    # First get row count
    count_sql = f"SELECT COUNT(*) AS row_count FROM {table}"
    count_result = execute_query(conn, count_sql)
    row_count = count_result[0]["ROW_COUNT"] if count_result else 0

    # Get columns
    columns = cmd_columns(conn, table)

    results = [{"metric": "total_rows", "value": row_count}]

    # Get cardinality for each column (limit to avoid long-running queries)
    for col in columns[:20]:  # Limit to first 20 columns
        col_name = col.get("COLUMN_NAME") or col.get("column_name")
        try:
            card_sql = f"SELECT COUNT(DISTINCT \"{col_name}\") AS cardinality FROM {table}"
            card_result = execute_query(conn, card_sql)
            cardinality = card_result[0]["CARDINALITY"] if card_result else 0
            results.append({
                "metric": f"distinct_{col_name}",
                "value": cardinality,
                "pct_unique": round(cardinality / row_count * 100, 2) if row_count > 0 else 0,
            })
        except Exception as e:
            log.warning(f"Could not profile column {col_name}: {e}")

    return results


def cmd_sample(
    conn: snowflake.connector.SnowflakeConnection, table: str, limit: int = 10
) -> list[dict[str, Any]]:
    """Sample rows from a table."""
    log.info(f"Sampling {limit} rows from table: {table}")
    sql = f"SELECT * FROM {table} LIMIT {limit}"
    return execute_query(conn, sql)


def cmd_distinct(
    conn: snowflake.connector.SnowflakeConnection, table: str, column: str, limit: int = 100
) -> list[dict[str, Any]]:
    """Get distinct values of a column."""
    log.info(f"Getting distinct values of {column} from {table}")
    sql = f"""
    SELECT DISTINCT "{column}" AS value, COUNT(*) AS count
    FROM {table}
    GROUP BY "{column}"
    ORDER BY count DESC
    LIMIT {limit}
    """
    return execute_query(conn, sql)


def cmd_query(conn: snowflake.connector.SnowflakeConnection, sql: str) -> list[dict[str, Any]]:
    """Run arbitrary SQL."""
    log.info("Executing custom query")
    return execute_query(conn, sql)


def cmd_file(conn: snowflake.connector.SnowflakeConnection, path: str) -> list[dict[str, Any]]:
    """Run SQL from a file."""
    log.info(f"Executing SQL from file: {path}")
    sql_path = Path(path)
    if not sql_path.is_absolute():
        sql_path = PROJECT_ROOT / path
    if not sql_path.exists():
        raise FileNotFoundError(f"SQL file not found: {sql_path}")
    sql = sql_path.read_text(encoding="utf-8")
    return execute_query(conn, sql)


def cmd_schemas(conn: snowflake.connector.SnowflakeConnection, database: str) -> list[dict[str, Any]]:
    """List schemas in a database."""
    log.info(f"Listing schemas in database: {database}")
    sql = f"""
    SELECT
        schema_name,
        created,
        last_altered
    FROM {database}.INFORMATION_SCHEMA.SCHEMATA
    ORDER BY schema_name
    """
    return execute_query(conn, sql)


def cmd_search(
    conn: snowflake.connector.SnowflakeConnection,
    pattern: str,
    database: str | None = None,
    schema: str | None = None,
) -> list[dict[str, Any]]:
    """Search for tables/columns matching a pattern."""
    log.info(f"Searching for pattern: {pattern}")

    db = database or os.environ.get("SNOWFLAKE_DATABASE", "")
    if not db:
        raise ValueError("Database must be specified or SNOWFLAKE_DATABASE must be set")

    schema_filter = f"AND table_schema = '{schema}'" if schema else ""

    # Search tables
    table_sql = f"""
    SELECT
        'TABLE' AS object_type,
        table_schema || '.' || table_name AS object_name,
        NULL AS column_name
    FROM {db}.INFORMATION_SCHEMA.TABLES
    WHERE UPPER(table_name) LIKE UPPER('%{pattern}%')
      {schema_filter}
    """

    # Search columns
    column_sql = f"""
    SELECT
        'COLUMN' AS object_type,
        table_schema || '.' || table_name AS object_name,
        column_name
    FROM {db}.INFORMATION_SCHEMA.COLUMNS
    WHERE UPPER(column_name) LIKE UPPER('%{pattern}%')
      {schema_filter}
    """

    sql = f"{table_sql} UNION ALL {column_sql} ORDER BY object_type, object_name LIMIT 100"
    return execute_query(conn, sql)


# ============================================================================
# Output Formatting
# ============================================================================


def format_output(data: Any, output_format: str = "table") -> str:
    """Format output data for display."""
    if output_format == "json":
        return json.dumps(data, indent=2, default=str)

    if output_format == "jsonl":
        if isinstance(data, list):
            return "\n".join(json.dumps(item, default=str) for item in data)
        return json.dumps(data, default=str)

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
        widths[col] = max(len(str(col)), max(len(str(row.get(col, ""))[:60]) for row in data))

    lines = []
    header = " | ".join(str(col).ljust(widths[col])[:60] for col in columns)
    lines.append(header)
    lines.append("-" * len(header))

    for row in data:
        line = " | ".join(str(row.get(col, ""))[:60].ljust(widths[col]) for col in columns)
        lines.append(line)

    return "\n".join(lines)


# ============================================================================
# Main CLI
# ============================================================================


def main(args: argparse.Namespace) -> None:
    """Main entry point."""
    try:
        with get_connection() as conn:
            if args.command == "tables":
                result = cmd_tables(conn, args.schema)
            elif args.command == "columns":
                result = cmd_columns(conn, args.table)
            elif args.command == "profile":
                result = cmd_profile(conn, args.table)
            elif args.command == "sample":
                result = cmd_sample(conn, args.table, args.limit)
            elif args.command == "distinct":
                result = cmd_distinct(conn, args.table, args.column, args.limit)
            elif args.command == "query":
                result = cmd_query(conn, args.sql)
            elif args.command == "file":
                result = cmd_file(conn, args.path)
            elif args.command == "schemas":
                result = cmd_schemas(conn, args.database)
            elif args.command == "search":
                result = cmd_search(conn, args.pattern, args.database, args.schema)
            else:
                log.error(f"Unknown command: {args.command}")
                return

            print(format_output(result, args.format))

    except EnvironmentError as e:
        log.error(str(e))
        raise SystemExit(1) from e
    except Exception as e:
        log.exception(f"Error: {e}")
        raise SystemExit(1) from e


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=dedent(f"""\
        {SCRIPT_NAME} - Efficient Snowflake exploration for Claude Code sessions.

        Uses the Snowflake Python connector with persistent connection for efficient
        data exploration. Much faster than multiple CLI invocations.

        Environment variables required:
            SNOWFLAKE_ACCOUNT, SNOWFLAKE_USER, SNOWFLAKE_PRIVATE_KEY_PATH, SNOWFLAKE_ROLE

        Examples:
            uv run {SCRIPT_NAME}.py tables DB.SCHEMA
            uv run {SCRIPT_NAME}.py columns DB.SCHEMA.TABLE
            uv run {SCRIPT_NAME}.py profile DB.SCHEMA.TABLE
            uv run {SCRIPT_NAME}.py sample DB.SCHEMA.TABLE 20
            uv run {SCRIPT_NAME}.py query "SELECT COUNT(*) FROM table"
        """),
    )

    # Global options
    parser.add_argument("-q", "--quiet", action="store_true", help="Show only errors")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable debug logging")
    parser.add_argument(
        "-f",
        "--format",
        choices=["table", "json", "jsonl"],
        default="table",
        help="Output format (default: table)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # tables command
    tables_parser = subparsers.add_parser("tables", help="List tables in a schema")
    tables_parser.add_argument("schema", help="Schema path (e.g., DATABASE.SCHEMA)")

    # columns command
    columns_parser = subparsers.add_parser("columns", help="Get column metadata for a table")
    columns_parser.add_argument("table", help="Table path (e.g., DATABASE.SCHEMA.TABLE)")

    # profile command
    profile_parser = subparsers.add_parser("profile", help="Profile table (counts, cardinality)")
    profile_parser.add_argument("table", help="Table path (e.g., DATABASE.SCHEMA.TABLE)")

    # sample command
    sample_parser = subparsers.add_parser("sample", help="Sample rows from a table")
    sample_parser.add_argument("table", help="Table path (e.g., DATABASE.SCHEMA.TABLE)")
    sample_parser.add_argument("limit", nargs="?", type=int, default=10, help="Number of rows (default: 10)")

    # distinct command
    distinct_parser = subparsers.add_parser("distinct", help="Get distinct values of a column")
    distinct_parser.add_argument("table", help="Table path (e.g., DATABASE.SCHEMA.TABLE)")
    distinct_parser.add_argument("column", help="Column name")
    distinct_parser.add_argument("--limit", type=int, default=100, help="Max values (default: 100)")

    # query command
    query_parser = subparsers.add_parser("query", help="Run arbitrary SQL")
    query_parser.add_argument("sql", help="SQL query to execute")

    # file command
    file_parser = subparsers.add_parser("file", help="Run SQL from a file")
    file_parser.add_argument("path", help="Path to SQL file")

    # schemas command
    schemas_parser = subparsers.add_parser("schemas", help="List schemas in a database")
    schemas_parser.add_argument("database", help="Database name")

    # search command
    search_parser = subparsers.add_parser("search", help="Search for tables/columns matching a pattern")
    search_parser.add_argument("pattern", help="Search pattern (case-insensitive)")
    search_parser.add_argument("--database", "-d", help="Database to search in")
    search_parser.add_argument("--schema", "-s", help="Schema to search in")

    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.ERROR if args.quiet else logging.INFO,
        format="%(asctime)s|%(name)s|%(levelname)s|%(filename)s:%(lineno)d - %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    if not args.command:
        parser.print_help()
    else:
        main(args)
