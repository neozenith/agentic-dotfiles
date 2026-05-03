"""FastAPI app factory — async lifespan-driven init/dispose of the DB engine.

Tests build isolated apps per fixture by calling `create_app(database_url=...)`
directly. asgi-lifespan's LifespanManager drives the lifespan in tests.
Production / dev: uvicorn invokes the lifespan when it boots the app.

When STATIC_DIR is set (Docker image bundles the built frontend), the factory
mounts the SPA at `/`. API routes under `/api/*` keep precedence because they
are registered BEFORE the catchall mount.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

# Import models so they register with Base BEFORE create_all is called.
from server import models  # noqa: F401
from server.api.routes import router
from server.config import get_database_url, get_static_dir
from server.db import DatabaseProvider


def create_app(database_url: str | None = None) -> FastAPI:
    db = DatabaseProvider(database_url or get_database_url())

    @asynccontextmanager
    async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
        await db.create_all()
        try:
            yield
        finally:
            await db.dispose()

    app = FastAPI(title="server", version="0.1.0", lifespan=lifespan)
    app.state.db = db

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

    # Mount the built SPA at `/` if STATIC_DIR is configured. `html=True`
    # serves index.html for paths that don't match a file (SPA routing).
    static_dir = get_static_dir()
    if static_dir is not None:
        if not static_dir.is_dir():
            raise RuntimeError(f"STATIC_DIR={static_dir} does not exist")
        app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="spa")

    return app
