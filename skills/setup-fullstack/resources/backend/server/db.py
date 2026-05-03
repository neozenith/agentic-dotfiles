"""Database provider — SQLAlchemy 2.x sync sessions, swappable engine.

`DatabaseProvider` owns the engine + sessionmaker. `create_app()` instantiates
one per app instance and stashes it on `app.state.db`. The `get_session`
dependency reads it back via `request.app.state.db` so tests can swap in a
tmp_path SQLite without touching module globals.

The default URL is `sqlite:///./tmp/app.db` (relative to cwd). Override via
the `DATABASE_URL` env var. The container sets `DATABASE_URL=sqlite:////app/data/app.db`.
"""

from __future__ import annotations

from collections.abc import Iterator
from pathlib import Path

from fastapi import Request
from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker


class Base(DeclarativeBase):
    """SQLAlchemy declarative base. All ORM models inherit from this."""


def _ensure_sqlite_parent_dir(database_url: str) -> None:
    """For file-backed SQLite URLs, mkdir the parent dir so create_engine doesn't error.

    Tolerated forms:
      sqlite:///relative/path.db   (3 slashes => relative)
      sqlite:////absolute/path.db  (4 slashes => absolute)
      sqlite:///:memory:           (in-memory; no dir)
    """
    if not database_url.startswith("sqlite:"):
        return
    path_part = database_url.split("///", 1)[-1]
    if not path_part or path_part.startswith(":"):
        return
    p = Path(path_part)
    if not p.is_absolute():
        p = Path.cwd() / p
    p.parent.mkdir(parents=True, exist_ok=True)


class DatabaseProvider:
    """Encapsulates the SQLAlchemy engine + sessionmaker for one app instance.

    Tests instantiate one per fixture (with a tmp_path-based URL) so test
    isolation is automatic. Production / dev code constructs one in
    `create_app()`.
    """

    def __init__(self, database_url: str) -> None:
        _ensure_sqlite_parent_dir(database_url)
        # check_same_thread=False is required for SQLite when used by multiple
        # FastAPI worker threads (TestClient + uvicorn both use threads).
        connect_args = (
            {"check_same_thread": False} if database_url.startswith("sqlite:") else {}
        )
        self.engine: Engine = create_engine(
            database_url,
            future=True,
            connect_args=connect_args,
        )
        self.session_factory: sessionmaker[Session] = sessionmaker(
            self.engine,
            expire_on_commit=False,
            autoflush=False,
        )

    def create_all(self) -> None:
        """Create every registered table. Call AFTER all model modules are imported."""
        Base.metadata.create_all(self.engine)


def get_session(request: Request) -> Iterator[Session]:
    """FastAPI dependency: yields a Session bound to the request's app DB.

    The DB lives on `app.state.db` (set by create_app). This indirection means
    tests can build an isolated app per fixture without monkey-patching module
    globals.
    """
    db: DatabaseProvider = request.app.state.db
    with db.session_factory() as session:
        yield session
