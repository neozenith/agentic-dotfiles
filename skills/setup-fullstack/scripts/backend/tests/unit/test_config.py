"""Unit tests for the configuration helpers (env-var registry)."""

from __future__ import annotations

from pathlib import Path

import pytest

from server.config import DEFAULT_DATABASE_URL, get_database_url, get_static_dir


def test_get_database_url_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("DATABASE_URL", raising=False)
    assert get_database_url() == DEFAULT_DATABASE_URL


def test_get_database_url_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("DATABASE_URL", "postgresql+asyncpg://u:p@h/db")
    assert get_database_url() == "postgresql+asyncpg://u:p@h/db"


def test_get_static_dir_unset(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STATIC_DIR", raising=False)
    assert get_static_dir() is None


def test_get_static_dir_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    result = get_static_dir()
    assert result == tmp_path
