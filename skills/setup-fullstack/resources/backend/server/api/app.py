"""FastAPI app factory — async lifespan-driven init/dispose of the DB engine.

Tests build isolated apps per fixture by calling `create_app(database_url=...)`
directly. asgi-lifespan's LifespanManager drives the lifespan in tests.
Production / dev: uvicorn invokes the lifespan when it boots the app.

When STATIC_DIR is set (Docker image bundles the built frontend), the factory
mounts the SPA at `/`. API routes under `/api/*` keep precedence because they
are registered BEFORE the catchall mount.

The lifespan also (a) attempts a cold-start restore from the configured
StorageBackend if the DB is empty, and (b) starts the periodic-backup
scheduler. Both are skipped silently when STORAGE_BACKEND is not set, so
local dev without a bucket still boots fine.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import models so they register with Base BEFORE create_all is called.
from server import models  # noqa: F401
from server.api.admin import router as admin_router
from server.api.app_state import BackupContext
from server.api.routes import router
from server.storage.backup.lifecycle import BackupScheduler, restore_if_database_empty
from server.config import (
    get_backup_interval_seconds,
    get_backup_key_prefix,
    get_database_url,
    get_static_dir,
    is_backup_enabled,
)
from server.db import DatabaseProvider
from server.storage import make_storage_backend
from server.storage.s3 import S3Backend

log = logging.getLogger(__name__)


def _build_backup_context(database_url: str) -> BackupContext | None:
    """Construct the backup feature glue from env, or return None if disabled."""
    if not is_backup_enabled():
        return None
    storage = make_storage_backend()
    if storage is None:
        return None
    interval = get_backup_interval_seconds()
    key_prefix = get_backup_key_prefix()
    scheduler = BackupScheduler(
        database_url=database_url,
        storage=storage,
        interval_seconds=interval,
        key_prefix=key_prefix,
    )
    bucket_label = (
        f"s3://{storage._bucket}" if isinstance(storage, S3Backend) else type(storage).__name__
    )
    return BackupContext(
        storage=storage,
        scheduler=scheduler,
        database_url=database_url,
        interval_seconds=interval,
        key_prefix=key_prefix,
        bucket_label=bucket_label,
    )


def create_app(database_url: str | None = None) -> FastAPI:
    resolved_url = database_url or get_database_url()
    db = DatabaseProvider(resolved_url)
    backup_ctx = _build_backup_context(resolved_url)

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await db.create_all()
        if backup_ctx is not None:
            try:
                restored_key = await restore_if_database_empty(
                    db=db,
                    database_url=backup_ctx.database_url,
                    storage=backup_ctx.storage,
                    key_prefix=backup_ctx.key_prefix,
                )
                if restored_key:
                    log.info("Cold-start restore completed from %s", restored_key)
            except Exception:
                # Restore failure must not block boot — but it MUST be loud.
                log.exception("Cold-start restore failed; continuing with empty DB")
            backup_ctx.scheduler.start()
        try:
            yield
        finally:
            if backup_ctx is not None:
                await backup_ctx.scheduler.stop(final_dump=True)
            await db.dispose()

    app = FastAPI(title="server", version="0.1.0", lifespan=lifespan)
    app.state.db = db
    app.state.backup = backup_ctx

    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://127.0.0.1:5173",
            "http://127.0.0.1:5174",
            "http://localhost:5173",
            "http://localhost:5174",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router, prefix="/api")
    app.include_router(admin_router, prefix="/api/admin")

    # Mount the built SPA at `/` if STATIC_DIR is configured. `html=True`
    # serves index.html for paths that don't match a file (SPA routing).
    static_dir = get_static_dir()
    if static_dir is not None:
        if not static_dir.is_dir():
            raise RuntimeError(f"STATIC_DIR={static_dir} does not exist")
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="spa")

    return app
