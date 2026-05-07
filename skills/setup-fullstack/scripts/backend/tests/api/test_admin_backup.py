"""Admin route tests — disabled-feature paths exercised in unit mode.

The success path of `POST /api/admin/backup` requires a real Postgres + a
real S3-compatible backend; that round-trip lives in
`tests/api/test_backup_roundtrip.py` and runs only when BACKEND_BASE_URL is
set against the dockerized stack.

The tests here cover:
  * Feature-disabled state (status endpoint reports enabled=false; trigger
    endpoint returns 503).
  * Feature-enabled but no prior backup (status reports null latest_key).

These tests construct their own app per-test so they can vary env vars
through `monkeypatch.setenv` before `create_app` reads them.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from server.api.app import create_app


@pytest.fixture
async def disabled_client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    """An in-process client with backup disabled (default env)."""
    db_path = tmp_path / "disabled.db"
    app = create_app(database_url=f"sqlite+aiosqlite:///{db_path}")
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


@pytest.fixture
async def memory_backend_client(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> AsyncIterator[httpx.AsyncClient]:
    """An in-process client with STORAGE_BACKEND=memory configured.

    The scheduler runs (with a long interval so it doesn't tick during the
    test). The DATABASE_URL is still SQLite, so an actual `pg_dump` would
    fail — but the disabled/status routes don't invoke pg_dump.
    """
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    monkeypatch.setenv("BACKUP_INTERVAL_SECONDS", "3600")
    monkeypatch.delenv("BACKUP_ENABLED", raising=False)

    db_path = tmp_path / "enabled.db"
    app = create_app(database_url=f"sqlite+aiosqlite:///{db_path}")
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            yield c


# ---------------------------------------------------------------------------
# Disabled state
# ---------------------------------------------------------------------------


async def test_status_reports_disabled_when_no_backend(
    disabled_client: httpx.AsyncClient,
) -> None:
    response = await disabled_client.get("/api/admin/backup/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is False
    # Optional fields default to None when disabled
    assert body["interval_seconds"] is None


async def test_trigger_returns_503_when_disabled(
    disabled_client: httpx.AsyncClient,
) -> None:
    response = await disabled_client.post("/api/admin/backup")
    assert response.status_code == 503
    assert "disabled" in response.json()["detail"].lower()


# ---------------------------------------------------------------------------
# Enabled state (memory backend, no backup yet)
# ---------------------------------------------------------------------------


async def test_status_reports_enabled_with_no_latest_key(
    memory_backend_client: httpx.AsyncClient,
) -> None:
    response = await memory_backend_client.get("/api/admin/backup/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    assert body["interval_seconds"] == 3600
    assert body["key_prefix"] == "backups/"
    assert body["bucket"] == "InMemoryBackend"
    assert body["latest_key"] is None
    assert body["latest_size_bytes"] is None


async def test_status_unaffected_by_existing_storage_env_for_disabled(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """BACKUP_ENABLED=false overrides STORAGE_BACKEND=memory."""
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    monkeypatch.setenv("BACKUP_ENABLED", "false")

    db_path = tmp_path / "override.db"
    app = create_app(database_url=f"sqlite+aiosqlite:///{db_path}")
    async with LifespanManager(app):
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
            response = await c.get("/api/admin/backup/status")
    assert response.status_code == 200
    assert response.json()["enabled"] is False


async def test_health_still_works_with_backup_enabled(
    memory_backend_client: httpx.AsyncClient,
) -> None:
    response = await memory_backend_client.get("/api/health")
    assert response.status_code == 200


def test_unit_env_does_not_set_storage_backend() -> None:
    """Sanity check: the unit test runner must not have STORAGE_BACKEND set
    in the ambient process env — otherwise other tests will see the scheduler
    spin up unexpectedly. The fixtures above use monkeypatch to set/unset."""
    assert os.environ.get("STORAGE_BACKEND", "") == ""
