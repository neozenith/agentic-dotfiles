"""Unit tests for the SQLAlchemy provider's URL parsing branches."""

from __future__ import annotations

from pathlib import Path

from server.db import _ensure_sqlite_parent_dir


def test_skips_non_sqlite_urls() -> None:
    # No-op for postgres (and never raises). Asserting absence of side effects
    # is hard to express; the function returns None on the early-return path.
    _ensure_sqlite_parent_dir("postgresql+asyncpg://user:pass@host/db")


def test_skips_memory_urls() -> None:
    _ensure_sqlite_parent_dir("sqlite+aiosqlite:///:memory:")


def test_skips_empty_path() -> None:
    _ensure_sqlite_parent_dir("sqlite+aiosqlite:///")


def test_creates_parent_dir_for_absolute_path(tmp_path: Path) -> None:
    db_path = tmp_path / "sub" / "deep" / "test.db"
    # 4 slashes => absolute path in the SQLAlchemy URL grammar.
    _ensure_sqlite_parent_dir(f"sqlite+aiosqlite:///{db_path}")
    assert db_path.parent.is_dir()


def test_creates_parent_dir_for_relative_path(
    tmp_path: Path, monkeypatch: object
) -> None:
    # Relative paths resolve against cwd; chdir to tmp_path so the resolved
    # parent is inside the test sandbox.
    import os

    os.chdir(tmp_path)
    _ensure_sqlite_parent_dir("sqlite+aiosqlite:///nested/dir/app.db")
    assert (tmp_path / "nested" / "dir").is_dir()
