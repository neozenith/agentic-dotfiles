"""Async database provider — works with SQLite (aiosqlite) or Postgres (asyncpg).

The backend choice is driven entirely by the `DATABASE_URL` env var. SQLAlchemy's
async engine reads the dialect+driver from the URL prefix:

    sqlite+aiosqlite:///./tmp/app.db                 — local file (default)
    sqlite+aiosqlite:////app/data/app.db             — absolute file (Docker)
    postgresql+asyncpg://user:pass@host:5432/dbname  — Postgres

`DatabaseProvider` owns the engine + sessionmaker. `create_app()` instantiates
one per app and stashes it on `app.state.db`. The `get_session` FastAPI
dependency reads it back via `request.app.state.db` so tests can swap in a
tmp_path-backed SQLite without touching module globals.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from pathlib import Path

from fastapi import Request
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. All ORM models inherit from this."""


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """For file-backed SQLite URLs, mkdir the parent dir so create_engine doesn't error.

    Tolerated forms:
      sqlite+aiosqlite:///relative/path.db   (3 slashes => relative)
      sqlite+aiosqlite:////absolute/path.db  (4 slashes => absolute)
      sqlite+aiosqlite:///:memory:           (in-memory; no dir)
    """
    if "sqlite" not in database_url:
        return
    path_part = database_url.split("///", 1)[-1]
    if not path_part or path_part.startswith(":"):
        return
    p = Path(path_part)
    if not p.is_absolute():
        p = Path.cwd() / p
    p.parent.mkdir(parents=True, exist_ok=True)


class DatabaseProvider:
    """Encapsulates the async SQLAlchemy engine + sessionmaker for one app instance.

    Tests instantiate one per fixture (with a tmp_path-based URL) so test
    isolation is automatic. Production / dev code constructs one in
    `create_app()`.
    """

    def __init__(self, database_url: str) -> None:
        _ensure_sqlite_parent_dir(database_url)
        # aiosqlite + ASGI: pass check_same_thread=False so SQLAlchemy doesn't
        # complain when the connection is shared across the event-loop's
        # internal worker pool. asyncpg has no equivalent.
        connect_args: dict[str, object] = {}
        if "sqlite" in database_url:
            connect_args = {"check_same_thread": False}
        self.engine: AsyncEngine = create_async_engine(
            database_url,
            future=True,
            connect_args=connect_args,
        )
        self.session_factory: async_sessionmaker[AsyncSession] = async_sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
            class_=AsyncSession,
        )

    async def create_all(self) -> None:
        """Create every registered table. Call AFTER all model modules are imported."""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        """Close the engine's connection pool. Called on app shutdown."""
        await self.engine.dispose()


async def get_session(request: Request) -> AsyncIterator[AsyncSession]:
    """FastAPI dependency: yields an AsyncSession bound to the request's app DB.

    The DB lives on `app.state.db` (set by create_app). This indirection means
    tests can build an isolated app per fixture without monkey-patching module
    globals.
    """
    db: DatabaseProvider = request.app.state.db
    async with db.session_factory() as session:
        yield session
