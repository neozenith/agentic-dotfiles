"""Run `pg_dump -Fc` and stream the output bytes into a StorageBackend.

Why `-Fc` (custom format):
  * Single binary stream — easy to upload as one S3 object.
  * Supports `pg_restore --clean --if-exists` for idempotent overwrites.
  * Compresses by default (zstd in PG16; zlib older), so the bytes that hit
    S3 are already small.

The DSN-from-URL parsing lives in `server.backup.url` so this module only
deals with subprocess + I/O.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from collections.abc import Callable
from datetime import UTC, datetime

from server.backup.url import DatabaseConnection, parse_database_url
from server.storage.base import StorageBackend

DumpRunner = Callable[[DatabaseConnection], bytes]
"""Type for the sync function that produces dump bytes given a connection.

Tests inject a lambda that returns canned bytes; production uses `_run_pg_dump`
which spawns the actual `pg_dump` binary. Both are real implementations — the
test injection is dependency injection, not a mock.
"""

log = logging.getLogger(__name__)

LATEST_KEY = "latest.dump"
"""The key that always points at the most recent backup. Cold-start restore reads this."""


class PgDumpError(RuntimeError):
    """Raised when pg_dump exits non-zero. Carries stderr for debuggability."""


def _resolve_pg_dump() -> str:
    path = shutil.which("pg_dump")
    if path is None:
        raise PgDumpError(
            "pg_dump not found on PATH. Install postgresql-client in the runtime image."
        )
    return path


def _build_env(conn: DatabaseConnection) -> dict[str, str]:
    """Inject PGPASSWORD via env so it never appears in argv (where `ps` could see it)."""
    env = dict(os.environ)
    env["PGPASSWORD"] = conn.password
    return env


def _build_argv(pg_dump: str, conn: DatabaseConnection) -> list[str]:
    return [
        pg_dump,
        "--format=custom",
        "--no-owner",
        "--no-acl",
        "--host",
        conn.host,
        "--port",
        str(conn.port),
        "--username",
        conn.user,
        "--dbname",
        conn.database,
    ]


def _run_pg_dump(conn: DatabaseConnection) -> bytes:  # pragma: no cover
    """Sync core: spawn pg_dump, capture stdout. Wrapped in to_thread by callers.

    Excluded from coverage because exercising it requires a real Postgres
    instance — the integration test in `tests/api/` covers it end-to-end
    when the dockerized stack is up (BACKEND_BASE_URL set).
    """
    pg_dump = _resolve_pg_dump()
    argv = _build_argv(pg_dump, conn)
    log.info("Running pg_dump against %s:%s/%s", conn.host, conn.port, conn.database)
    result = subprocess.run(  # noqa: S603 — list invocation, no shell, env-supplied password
        argv,
        env=_build_env(conn),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise PgDumpError(f"pg_dump exited {result.returncode}: {stderr}")
    return result.stdout


async def dump_database(
    *,
    database_url: str,
    storage: StorageBackend,
    key_prefix: str = "backups/",
    runner: DumpRunner | None = None,
) -> str:
    """Run pg_dump against `database_url` and upload the dump to `storage`.

    Returns the timestamped key the dump was written to. Also rewrites the
    `latest.dump` pointer under the same prefix so cold-start restore has a
    stable key to read.

    `runner` is the sync function that produces dump bytes. Defaults to
    `_run_pg_dump` (real subprocess); tests inject a lambda returning canned
    bytes to verify the upload + key-naming logic without needing Postgres.
    """
    conn = parse_database_url(database_url)
    effective_runner = runner if runner is not None else _run_pg_dump
    dump_bytes = await asyncio.to_thread(effective_runner, conn)

    timestamp = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    timestamped_key = f"{key_prefix}{timestamp}.dump"
    latest_key = f"{key_prefix}{LATEST_KEY}"

    await storage.put_object(timestamped_key, dump_bytes)
    await storage.put_object(latest_key, dump_bytes)

    log.info(
        "pg_dump wrote %d bytes to %s (also pointed %s at it)",
        len(dump_bytes),
        timestamped_key,
        latest_key,
    )
    return timestamped_key
