"""Verifies create_app mounts the SPA when STATIC_DIR is set.

Uses pytest's `monkeypatch` to set the env var (real, not a mock), and a
real tmp_path to host the static directory. No mocking — this is a real
FastAPI app instance with a real route registered.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.api.app import create_app


def test_mounts_spa_when_static_dir_set(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    static_dir = tmp_path / "static"
    static_dir.mkdir()
    (static_dir / "index.html").write_text("<html>ok</html>")

    monkeypatch.setenv("STATIC_DIR", str(static_dir))
    db_path = tmp_path / "test.db"
    app = create_app(database_url=f"sqlite+aiosqlite:///{db_path}")

    # The catchall mount registers under the name "spa" — see app.py.
    assert any(getattr(r, "name", None) == "spa" for r in app.routes)


def test_raises_when_static_dir_missing(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("STATIC_DIR", str(tmp_path / "does-not-exist"))
    db_path = tmp_path / "test.db"
    with pytest.raises(RuntimeError, match="STATIC_DIR"):
        create_app(database_url=f"sqlite+aiosqlite:///{db_path}")
