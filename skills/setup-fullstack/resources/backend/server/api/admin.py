"""Admin endpoints for the backup feature.

These exist primarily for the integration test, but are also useful in demos
to demonstrate the round-trip on demand. They are intentionally unauthenticated
in this prototype — productionizing this feature should put them behind an
auth dependency before exposing the service publicly.

Routes:
  * GET  /admin/backup/status — current scheduler config + most recent dump
  * POST /admin/backup        — trigger a backup synchronously (no waiting
                                for the scheduler tick) and return the key

When `app.state.backup_scheduler is None` (storage not configured), every
route here returns 503 with a clear "feature disabled" body.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from server.storage.backup import dump_database, restore_database
from server.storage.backup.pointer import head_latest
from server.storage.backup.restore import NoBackupAvailableError

if TYPE_CHECKING:
    from server.api.app_state import BackupContext

router = APIRouter()


class BackupStatusResponse(BaseModel):
    enabled: bool
    interval_seconds: int | None = None
    key_prefix: str | None = None
    bucket: str | None = None
    latest_key: str | None = None
    latest_size_bytes: int | None = None


class BackupTriggerResponse(BaseModel):
    key: str


class RestoreTriggerResponse(BaseModel):
    key: str


def _get_context(request: Request) -> BackupContext:
    ctx: BackupContext | None = getattr(request.app.state, "backup", None)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Backup feature disabled: STORAGE_BACKEND is not configured",
        )
    return ctx


@router.get("/backup/status", response_model=BackupStatusResponse)
async def backup_status(request: Request) -> BackupStatusResponse:
    ctx: BackupContext | None = getattr(request.app.state, "backup", None)
    if ctx is None:
        return BackupStatusResponse(enabled=False)

    metadata = await head_latest(ctx.storage, ctx.key_prefix)
    return BackupStatusResponse(
        enabled=True,
        interval_seconds=ctx.interval_seconds,
        key_prefix=ctx.key_prefix,
        bucket=ctx.bucket_label,
        latest_key=metadata.key if metadata is not None else None,
        latest_size_bytes=metadata.size if metadata is not None else None,
    )


@router.post(
    "/backup",
    response_model=BackupTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_backup(request: Request) -> BackupTriggerResponse:
    ctx = _get_context(request)
    key = await dump_database(
        database_url=ctx.database_url,
        storage=ctx.storage,
        key_prefix=ctx.key_prefix,
    )
    return BackupTriggerResponse(key=key)


@router.post(
    "/restore",
    response_model=RestoreTriggerResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def trigger_restore(request: Request) -> RestoreTriggerResponse:
    """Manually trigger a restore from the latest backup.

    Same code path as the cold-start restore — this exists so demos and
    integration tests can verify the restore round-trip without restarting
    the container. Returns 404 when no backup is present yet.
    """
    ctx = _get_context(request)
    try:
        key = await restore_database(
            database_url=ctx.database_url,
            storage=ctx.storage,
            key_prefix=ctx.key_prefix,
        )
    except NoBackupAvailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"No backup found at {exc.args[0]}",
        ) from exc
    return RestoreTriggerResponse(key=key)
