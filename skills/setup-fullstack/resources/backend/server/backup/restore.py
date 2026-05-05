"""Read a `-Fc` dump from a StorageBackend and pipe it into `pg_restore`.

`pg_restore --clean --if-exists --no-owner` is the round-trip partner of
`pg_dump -Fc`. The flags do:
  * `--clean`        — DROP each object before recreating it.
  * `--if-exists`    — make the DROP idempotent if the object isn't there.
  * `--no-owner`     — don't try to SET OWNER to the dump's original role.
"""

from __future__ import annotations

import asyncio
import logging
import os
import shutil
import subprocess
from collections.abc import Callable

from server.backup.dump import LATEST_KEY
from server.backup.url import DatabaseConnection, parse_database_url
from server.storage.base import ObjectNotFoundError, StorageBackend

log = logging.getLogger(__name__)

RestoreRunner = Callable[[DatabaseConnection, bytes], None]
"""Sync function that loads dump bytes into Postgres. Real default uses
subprocess; tests inject a lambda that records the call without running PG."""


class PgRestoreError(RuntimeError):
    """Raised when pg_restore exits non-zero. Carries stderr for debuggability."""


class NoBackupAvailableError(LookupError):
    """Raised when the latest-key has nothing behind it. Distinct from generic
    errors so callers can branch on 'first cold start, no prior data'."""


def _resolve_pg_restore() -> str:
    path = shutil.which("pg_restore")
    if path is None:
        raise PgRestoreError(
            "pg_restore not found on PATH. Install postgresql-client in the runtime image."
        )
    return path


def _build_env(conn: DatabaseConnection) -> dict[str, str]:
    env = dict(os.environ)
    env["PGPASSWORD"] = conn.password
    return env


def _build_argv(pg_restore: str, conn: DatabaseConnection) -> list[str]:
    return [
        pg_restore,
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--exit-on-error",
        "--host",
        conn.host,
        "--port",
        str(conn.port),
        "--username",
        conn.user,
        "--dbname",
        conn.database,
    ]


def _run_pg_restore(conn: DatabaseConnection, dump_bytes: bytes) -> None:  # pragma: no cover
    """Subprocess core. Excluded from coverage; covered by the dockerized
    integration test."""
    pg_restore = _resolve_pg_restore()
    argv = _build_argv(pg_restore, conn)
    log.info("Running pg_restore into %s:%s/%s", conn.host, conn.port, conn.database)
    result = subprocess.run(  # noqa: S603 — list invocation, no shell, env-supplied password
        argv,
        input=dump_bytes,
        env=_build_env(conn),
        capture_output=True,
        check=False,
    )
    if result.returncode != 0:
        stderr = result.stderr.decode("utf-8", errors="replace").strip()
        raise PgRestoreError(f"pg_restore exited {result.returncode}: {stderr}")


async def restore_database(
    *,
    database_url: str,
    storage: StorageBackend,
    key_prefix: str = "backups/",
    key: str | None = None,
    runner: RestoreRunner | None = None,
) -> str:
    """Download a dump from `storage` and pipe it into pg_restore.

    `key` defaults to `<prefix>latest.dump`. Returns the key actually used so
    the caller can log / audit which backup was loaded. `runner` is injectable
    for tests (pass a lambda that records the call); production uses
    `_run_pg_restore`.
    """
    conn = parse_database_url(database_url)
    target_key = key if key is not None else f"{key_prefix}{LATEST_KEY}"

    try:
        dump_bytes = await storage.get_object(target_key)
    except ObjectNotFoundError as exc:
        raise NoBackupAvailableError(target_key) from exc

    effective_runner = runner if runner is not None else _run_pg_restore
    await asyncio.to_thread(effective_runner, conn, dump_bytes)
    log.info("pg_restore loaded %d bytes from %s", len(dump_bytes), target_key)
    return target_key
