"""Lifespan-side wiring: scheduler + cold-start restore.

Two pieces glued into `create_app`:
  * `restore_if_database_empty()` — startup hook: if the DB has no user rows,
    download the latest dump and pg_restore it. Idempotent — second boot with
    data present skips the restore.
  * `BackupScheduler` — owns an asyncio.Task that runs `dump_database` every
    `interval_seconds`. `start()` kicks the loop; `stop()` cancels it and
    runs one final best-effort dump so SIGTERM doesn't lose the latest writes.

The scheduler swallows + logs per-iteration exceptions so a transient network
blip on backup #N doesn't kill the loop and silently disable backup #N+1.
This is "the operation legitimately can fail and we keep going," NOT
"graceful degradation that hides a missing requirement" — the requirement
("back up periodically") is satisfied iff the loop is alive.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable

from sqlalchemy import func, select

from server.db import Base, DatabaseProvider
from server.storage.backup.dump import dump_database
from server.storage.backup.restore import (
    NoBackupAvailableError,
    RestoreRunner,
    restore_database,
)
from server.storage.base import StorageBackend

log = logging.getLogger(__name__)


async def is_database_empty(db: DatabaseProvider) -> bool:
    """True iff every table registered on Base has zero rows.

    Generic across the model set: as we add models, this stays correct without
    edits. Walks `Base.metadata.sorted_tables` so dependency order is honored
    (not strictly needed for COUNT, but it's the canonical iteration order).
    """
    async with db.session_factory() as session:
        for table in Base.metadata.sorted_tables:
            count = await session.scalar(select(func.count()).select_from(table))
            if count and count > 0:
                return False
    return True


async def restore_if_database_empty(
    *,
    db: DatabaseProvider,
    database_url: str,
    storage: StorageBackend,
    key_prefix: str = "backups/",
    restore_runner: RestoreRunner | None = None,
) -> str | None:
    """If the DB has no rows, pull the latest dump and restore. Return the key used, or None.

    Returns None when:
      * the DB already has data (no restore performed), OR
      * no backup exists yet under the prefix (first-ever cold start).

    `restore_runner` lets tests substitute the subprocess invocation with a
    real callable that records the call, so the empty/non-empty branches and
    the missing-backup branch can be verified without running pg_restore.
    """
    if not await is_database_empty(db):
        log.info("Database already has data; skipping cold-start restore")
        return None

    log.info("Database is empty; attempting cold-start restore from %s", key_prefix)
    try:
        return await restore_database(
            database_url=database_url,
            storage=storage,
            key_prefix=key_prefix,
            runner=restore_runner,
        )
    except NoBackupAvailableError:
        log.info("No prior backup found at %s; first cold start", key_prefix)
        return None


class BackupScheduler:
    """Owns the periodic-backup asyncio.Task. Wired into the FastAPI lifespan.

    Per-iteration exceptions are caught + logged so the loop survives. A
    final `dump_database()` runs on `stop()` so a clean shutdown writes the
    most recent state. The final dump is best-effort: failures are logged
    but not raised, so a flaky network at SIGTERM doesn't keep the process
    from exiting.
    """

    def __init__(
        self,
        *,
        database_url: str,
        storage: StorageBackend,
        interval_seconds: int,
        key_prefix: str = "backups/",
        dump_fn: Callable[..., Awaitable[str]] | None = None,
    ) -> None:
        self._database_url = database_url
        self._storage = storage
        self._interval = interval_seconds
        self._key_prefix = key_prefix
        self._dump = dump_fn or dump_database
        self._task: asyncio.Task[None] | None = None
        self._stopping = asyncio.Event()

    async def _one_dump(self) -> None:
        await self._dump(
            database_url=self._database_url,
            storage=self._storage,
            key_prefix=self._key_prefix,
        )

    async def _loop(self) -> None:
        while not self._stopping.is_set():
            try:
                await asyncio.wait_for(self._stopping.wait(), timeout=self._interval)
                # If wait() resolved (vs. timed out), we're stopping — exit the loop.
                return
            except TimeoutError:
                pass
            try:
                await self._one_dump()
            except Exception:
                log.exception("Periodic backup failed; will retry in %ds", self._interval)

    def start(self) -> None:
        if self._task is not None:
            raise RuntimeError("BackupScheduler is already running")
        self._task = asyncio.create_task(self._loop(), name="backup-scheduler")
        log.info("BackupScheduler started (interval=%ds)", self._interval)

    async def stop(self, *, final_dump: bool = True) -> None:
        self._stopping.set()
        if self._task is not None:
            with contextlib.suppress(asyncio.CancelledError):
                await self._task
            self._task = None
        if final_dump:
            try:
                await self._one_dump()
            except Exception:
                log.exception("Final backup on shutdown failed")
        log.info("BackupScheduler stopped")
