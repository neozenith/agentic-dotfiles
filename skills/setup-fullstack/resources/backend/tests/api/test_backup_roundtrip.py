"""End-to-end backup/restore round-trip against a real Postgres + MinIO stack.

Runs ONLY when `BACKEND_BASE_URL` is set — the test depends on the dockerized
stack that `make docker-up-postgres-minio` brings up. The Makefile target
`test-backup-roundtrip` orchestrates the whole thing (boot → run → tear down).

Flow exercised:

  1. POST /api/items — insert a row through the real route + real Postgres.
  2. POST /api/admin/backup — pg_dump runs in the backend container, uploads
     the dump to MinIO via the S3Backend.
  3. GET /api/admin/backup/status — confirms the upload landed (latest_key
     populated, byte size > 0).
  4. DELETE /api/items/{id} — wipe the row through the route, mimicking
     "ephemeral DB lost its state".
  5. GET /api/items — confirm the row is gone.
  6. POST /api/admin/restore — pg_restore loads the dump from MinIO. Same
     code path as the cold-start lifecycle hook.
  7. GET /api/items — confirm the original row is back.

This is THE test that proves the prototype works. Everything else (unit
tests of orchestration, storage abstraction, scheduler) supports this path.
"""

from __future__ import annotations

import os
import uuid
from collections.abc import AsyncIterator

import httpx
import pytest

pytestmark = pytest.mark.skipif(
    not os.environ.get("BACKEND_BASE_URL"),
    reason=(
        "Backup roundtrip requires the dockerized Postgres + MinIO stack; "
        "set BACKEND_BASE_URL or run `make test-backup-roundtrip`."
    ),
)


@pytest.fixture
async def integration_client() -> AsyncIterator[httpx.AsyncClient]:
    base_url = os.environ["BACKEND_BASE_URL"]
    async with httpx.AsyncClient(base_url=base_url, timeout=30.0) as c:
        yield c


@pytest.fixture
async def backup_enabled_client(
    integration_client: httpx.AsyncClient,
) -> httpx.AsyncClient:
    """Skip if the running backend doesn't have the backup feature enabled.

    The backup feature is opt-in via STORAGE_BACKEND env var. When the
    dockerized stack is sqlite-only (the default `ci-docker` flow), backup is
    disabled and any test that depends on it must skip — not fail.
    """
    response = await integration_client.get("/api/admin/backup/status")
    if response.status_code != 200 or not response.json().get("enabled", False):
        pytest.skip(
            "Backup feature is not enabled on the running backend. "
            "Run `make test-backup-roundtrip` for the full Postgres+MinIO stack."
        )
    return integration_client


async def test_backup_status_shows_feature_enabled(
    backup_enabled_client: httpx.AsyncClient,
) -> None:
    response = await backup_enabled_client.get("/api/admin/backup/status")
    assert response.status_code == 200
    body = response.json()
    assert body["enabled"] is True
    # The bucket label is variation-specific:
    #   S3Backend  -> "s3://<bucket>"   (MinIO uses "s3://app-backups", AWS uses
    #                                    whatever STORAGE_BUCKET names)
    #   LocalStorage -> "LocalStorage"
    # Just check it's a non-empty string — the matrix tests run against multiple
    # backends, all of which honor this floor.
    assert isinstance(body["bucket"], str) and body["bucket"]
    assert body["key_prefix"], "key_prefix must be set (defaults to 'backups/')"


async def test_full_backup_restore_roundtrip(
    backup_enabled_client: httpx.AsyncClient,
) -> None:
    # Use a unique name so the test is robust against prior test residue
    # (the postgres volume persists across runs unless the caller does -v).
    marker = f"roundtrip-{uuid.uuid4().hex[:8]}"

    # 1. Insert
    create_response = await backup_enabled_client.post(
        "/api/items",
        json={"name": marker, "description": "round-trip test row"},
    )
    assert create_response.status_code == 201
    item_id = create_response.json()["id"]

    # 2. Trigger backup (pg_dump → MinIO)
    backup_response = await backup_enabled_client.post("/api/admin/backup")
    assert backup_response.status_code == 202, backup_response.text
    backup_key = backup_response.json()["key"]
    assert backup_key.startswith("backups/")

    # 3. Status confirms the dump landed
    status_response = await backup_enabled_client.get("/api/admin/backup/status")
    assert status_response.status_code == 200
    status_body = status_response.json()
    assert status_body["latest_key"] == "backups/latest.dump"
    assert (status_body["latest_size_bytes"] or 0) > 0

    # 4. Delete the row — simulate "ephemeral DB lost state"
    delete_response = await backup_enabled_client.delete(f"/api/items/{item_id}")
    assert delete_response.status_code == 204

    # 5. Confirm it's gone
    missing_response = await backup_enabled_client.get(f"/api/items/{item_id}")
    assert missing_response.status_code == 404

    # 6. Restore from latest backup
    restore_response = await backup_enabled_client.post("/api/admin/restore")
    assert restore_response.status_code == 202, restore_response.text
    assert restore_response.json()["key"] == "backups/latest.dump"

    # 7. The row is back
    items_response = await backup_enabled_client.get("/api/items")
    assert items_response.status_code == 200
    items = items_response.json()
    names = [it["name"] for it in items]
    assert marker in names, f"Restore did not bring back the row {marker!r}. Got items: {names}"
