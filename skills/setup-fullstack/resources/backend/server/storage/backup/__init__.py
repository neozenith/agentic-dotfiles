"""Postgres backup/restore against a `StorageBackend`.

Public surface:

  * `dump_database()` — async; runs `pg_dump -Fc` against the configured
    DATABASE_URL and uploads the bytes to a `StorageBackend` under a key.
  * `restore_database()` — async; downloads a key from a `StorageBackend`
    and pipes it into `pg_restore`.
  * `BackupScheduler` — owns the periodic-dump asyncio.Task wired into the
    FastAPI lifespan.
  * `restore_if_database_empty()` — startup hook that restores the latest
    backup iff the DB has no rows in any user-table.

The dump format is `-Fc` (custom). It is denser than `-Fp` and supports
`pg_restore --clean --if-exists` for idempotent restores.

Layout convention (see `pointer.py`): each backup prefix holds timestamped
immutable dumps plus a single `latest.dump` pointer. Only `pointer.py`
knows the pointer's filename — every other module goes through it.
"""

from server.storage.backup.dump import dump_database
from server.storage.backup.lifecycle import BackupScheduler, restore_if_database_empty
from server.storage.backup.restore import restore_database
from server.storage.backup.url import DatabaseConnection, parse_database_url

__all__ = [
    "BackupScheduler",
    "DatabaseConnection",
    "dump_database",
    "parse_database_url",
    "restore_database",
    "restore_if_database_empty",
]
