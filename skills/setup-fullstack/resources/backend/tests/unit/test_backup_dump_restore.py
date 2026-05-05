"""Orchestration tests for dump_database / restore_database.

The subprocess core (`_run_pg_dump`, `_run_pg_restore`) is excluded from
coverage and exercised by the integration test that runs against a real
Postgres + MinIO stack. These tests verify the surrounding logic: the
right key is written, the latest pointer is updated, ObjectNotFound
becomes NoBackupAvailableError, the runner is called with the right
DatabaseConnection.
"""

from __future__ import annotations

import pytest

from server.backup.dump import LATEST_KEY, dump_database
from server.backup.restore import NoBackupAvailableError, restore_database
from server.backup.url import DatabaseConnection
from server.storage import InMemoryBackend


@pytest.fixture
def storage() -> InMemoryBackend:
    return InMemoryBackend()


@pytest.fixture
def database_url() -> str:
    return "postgresql://test_user:test_pw@db.test:5432/testdb"


async def test_dump_writes_timestamped_and_latest_keys(
    storage: InMemoryBackend, database_url: str
) -> None:
    fake_bytes = b"PGDMP-fake-custom-format-bytes"

    captured: list[DatabaseConnection] = []

    def fake_runner(conn: DatabaseConnection) -> bytes:
        captured.append(conn)
        return fake_bytes

    timestamped_key = await dump_database(
        database_url=database_url,
        storage=storage,
        runner=fake_runner,
    )

    assert timestamped_key.startswith("backups/")
    assert timestamped_key.endswith(".dump")
    assert await storage.get_object(timestamped_key) == fake_bytes
    assert await storage.get_object(f"backups/{LATEST_KEY}") == fake_bytes

    # Runner saw the parsed connection
    assert len(captured) == 1
    assert captured[0].host == "db.test"
    assert captured[0].database == "testdb"
    assert captured[0].user == "test_user"
    assert captured[0].password == "test_pw"


async def test_dump_respects_custom_key_prefix(storage: InMemoryBackend, database_url: str) -> None:
    fake = lambda conn: b"x"  # noqa: E731

    timestamped_key = await dump_database(
        database_url=database_url,
        storage=storage,
        key_prefix="archived/",
        runner=fake,
    )

    assert timestamped_key.startswith("archived/")
    assert await storage.head_object(f"archived/{LATEST_KEY}")


async def test_restore_loads_latest_when_no_key_specified(
    storage: InMemoryBackend, database_url: str
) -> None:
    payload = b"PGDMP-existing-backup"
    await storage.put_object(f"backups/{LATEST_KEY}", payload)

    received: list[tuple[DatabaseConnection, bytes]] = []

    def fake_restorer(conn: DatabaseConnection, data: bytes) -> None:
        received.append((conn, data))

    used_key = await restore_database(
        database_url=database_url,
        storage=storage,
        runner=fake_restorer,
    )

    assert used_key == f"backups/{LATEST_KEY}"
    assert len(received) == 1
    assert received[0][1] == payload
    assert received[0][0].database == "testdb"


async def test_restore_loads_explicit_key(storage: InMemoryBackend, database_url: str) -> None:
    await storage.put_object("backups/2025-01-01.dump", b"snapshot")

    received: list[bytes] = []

    used_key = await restore_database(
        database_url=database_url,
        storage=storage,
        key="backups/2025-01-01.dump",
        runner=lambda _conn, data: received.append(data),
    )

    assert used_key == "backups/2025-01-01.dump"
    assert received == [b"snapshot"]


async def test_restore_raises_when_no_backup_present(
    storage: InMemoryBackend, database_url: str
) -> None:
    with pytest.raises(NoBackupAvailableError):
        await restore_database(
            database_url=database_url,
            storage=storage,
            runner=lambda _c, _d: None,
        )
