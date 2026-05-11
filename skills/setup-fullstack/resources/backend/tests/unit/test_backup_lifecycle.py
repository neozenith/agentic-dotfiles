"""Tests for the lifespan glue: is_database_empty, restore_if_database_empty, BackupScheduler.

All tests use a real SQLite DatabaseProvider (no Postgres required), real
InMemoryBackend, and real callable injection — no mocks, per the project
rule. The actual subprocess invocation is exercised by the integration test.
"""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from sqlalchemy import insert

from server.storage.backup.dump import dump_database
from server.storage.backup.lifecycle import (
    BackupScheduler,
    is_database_empty,
    restore_if_database_empty,
)
from server.storage.backup.pointer import latest_pointer_key
from server.storage.backup.url import DatabaseConnection
from server.db import DatabaseProvider
from server.models import Item
from server.storage import InMemoryBackend


@pytest.fixture
async def db(tmp_path: Path) -> AsyncIterator[DatabaseProvider]:
    provider = DatabaseProvider(f"sqlite+aiosqlite:///{tmp_path}/test.db")
    await provider.create_all()
    try:
        yield provider
    finally:
        await provider.dispose()


@pytest.fixture
def storage() -> InMemoryBackend:
    return InMemoryBackend()


@pytest.fixture
def pg_url() -> str:
    """Postgres URL used only for parsing; the runner is always faked."""
    return "postgresql://u:p@localhost:5432/db"


# ---------------------------------------------------------------------------
# is_database_empty
# ---------------------------------------------------------------------------


async def test_is_database_empty_true_for_fresh_db(db: DatabaseProvider) -> None:
    assert await is_database_empty(db) is True


async def test_is_database_empty_false_after_insert(db: DatabaseProvider) -> None:
    async with db.session_factory() as session:
        await session.execute(insert(Item).values(name="x", description=""))
        await session.commit()
    assert await is_database_empty(db) is False


# ---------------------------------------------------------------------------
# restore_if_database_empty — three branches
# ---------------------------------------------------------------------------


async def test_restore_skipped_when_db_has_data(
    db: DatabaseProvider, storage: InMemoryBackend, pg_url: str
) -> None:
    async with db.session_factory() as session:
        await session.execute(insert(Item).values(name="seeded", description=""))
        await session.commit()
    await storage.put_object(latest_pointer_key("backups/"), b"PGDMP-x")

    called: list[bool] = []

    def runner(_conn: DatabaseConnection, _data: bytes) -> None:
        called.append(True)

    result = await restore_if_database_empty(
        db=db,
        database_url=pg_url,
        storage=storage,
        restore_runner=runner,
    )
    assert result is None
    assert called == []  # restore was not called


async def test_restore_skipped_when_no_backup(
    db: DatabaseProvider, storage: InMemoryBackend, pg_url: str
) -> None:
    # DB empty, storage empty -> first cold start; returns None gracefully.
    result = await restore_if_database_empty(
        db=db,
        database_url=pg_url,
        storage=storage,
        restore_runner=lambda _c, _d: None,
    )
    assert result is None


async def test_restore_runs_when_db_empty_and_backup_present(
    db: DatabaseProvider, storage: InMemoryBackend, pg_url: str
) -> None:
    payload = b"PGDMP-cold-start"
    await storage.put_object(latest_pointer_key("backups/"), payload)

    received: list[bytes] = []

    def runner(_conn: DatabaseConnection, data: bytes) -> None:
        received.append(data)

    result = await restore_if_database_empty(
        db=db,
        database_url=pg_url,
        storage=storage,
        restore_runner=runner,
    )
    assert result == latest_pointer_key("backups/")
    assert received == [payload]


# ---------------------------------------------------------------------------
# BackupScheduler — runs, recovers from per-iter exceptions, final dump on stop
# ---------------------------------------------------------------------------


async def test_scheduler_runs_periodic_dump(storage: InMemoryBackend, pg_url: str) -> None:
    call_count = 0

    async def fake_dump(**kwargs: object) -> str:
        nonlocal call_count
        call_count += 1
        return f"backups/call-{call_count}.dump"

    scheduler = BackupScheduler(
        database_url=pg_url,
        storage=storage,
        interval_seconds=1,  # intentionally tight for the test
        dump_fn=fake_dump,
    )
    scheduler.start()
    # Allow the loop to tick at least twice
    await asyncio.sleep(2.2)
    await scheduler.stop(final_dump=False)

    assert call_count >= 2


async def test_scheduler_survives_a_failing_iteration(
    storage: InMemoryBackend, pg_url: str
) -> None:
    call_count = 0

    async def flaky_dump(**kwargs: object) -> str:
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            raise RuntimeError("simulated transient failure")
        return "ok"

    scheduler = BackupScheduler(
        database_url=pg_url,
        storage=storage,
        interval_seconds=1,
        dump_fn=flaky_dump,
    )
    scheduler.start()
    await asyncio.sleep(2.2)
    await scheduler.stop(final_dump=False)

    # Both attempts ran — the failure didn't abort the loop.
    assert call_count >= 2


async def test_scheduler_final_dump_on_stop(storage: InMemoryBackend, pg_url: str) -> None:
    calls: list[str] = []

    async def fake_dump(**kwargs: object) -> str:
        calls.append("dump")
        return "backups/ok"

    scheduler = BackupScheduler(
        database_url=pg_url,
        storage=storage,
        interval_seconds=600,  # long; no periodic ticks during this test
        dump_fn=fake_dump,
    )
    scheduler.start()
    await asyncio.sleep(0.05)
    await scheduler.stop(final_dump=True)

    assert calls == ["dump"]


async def test_scheduler_double_start_raises(storage: InMemoryBackend, pg_url: str) -> None:
    scheduler = BackupScheduler(
        database_url=pg_url,
        storage=storage,
        interval_seconds=600,
        dump_fn=lambda **_kw: _coro_returning_str(),
    )
    scheduler.start()
    try:
        with pytest.raises(RuntimeError, match="already running"):
            scheduler.start()
    finally:
        await scheduler.stop(final_dump=False)


async def test_scheduler_final_dump_failure_is_logged_not_raised(
    storage: InMemoryBackend, pg_url: str, caplog: pytest.LogCaptureFixture
) -> None:
    async def failing_dump(**kwargs: object) -> str:
        raise RuntimeError("S3 unreachable")

    scheduler = BackupScheduler(
        database_url=pg_url,
        storage=storage,
        interval_seconds=600,
        dump_fn=failing_dump,
    )
    scheduler.start()
    await asyncio.sleep(0.05)
    # Should not raise even though final dump errors.
    await scheduler.stop(final_dump=True)
    assert any("Final backup on shutdown failed" in r.message for r in caplog.records)


async def test_scheduler_default_dump_fn_is_dump_database(
    storage: InMemoryBackend, pg_url: str
) -> None:
    """If `dump_fn` is omitted, the scheduler defaults to the real `dump_database`.

    This test verifies the default wiring; we don't actually invoke it
    (it would call pg_dump). Just check the attribute identity.
    """
    scheduler = BackupScheduler(
        database_url=pg_url,
        storage=storage,
        interval_seconds=600,
    )
    assert scheduler._dump is dump_database


# Small helper for the double-start test
async def _coro_returning_str() -> str:
    return "backups/dummy"
