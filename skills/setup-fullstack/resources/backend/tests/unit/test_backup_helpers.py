"""Direct tests for the small helpers inside dump.py / restore.py.

These functions sit just under the subprocess call sites, so they're easy to
exercise directly — no Postgres needed. Covering them here keeps `_run_pg_dump`
/ `_run_pg_restore` (the actual subprocess invocations) as the only lines
under `# pragma: no cover`, and those are exercised by the integration test.
"""

from __future__ import annotations

import shutil

import pytest

from server.backup.dump import (
    PgDumpError,
    _resolve_pg_dump,
)
from server.backup.dump import (
    _build_argv as dump_build_argv,
)
from server.backup.dump import (
    _build_env as dump_build_env,
)
from server.backup.restore import (
    PgRestoreError,
    _resolve_pg_restore,
)
from server.backup.restore import (
    _build_argv as restore_build_argv,
)
from server.backup.restore import (
    _build_env as restore_build_env,
)
from server.backup.url import DatabaseConnection


@pytest.fixture
def conn() -> DatabaseConnection:
    return DatabaseConnection(
        host="db.example",
        port=5433,
        user="alice",
        password="s3cret",
        database="appdb",
    )


# ---------------------------------------------------------------------------
# _resolve_pg_dump / _resolve_pg_restore — both branches: present + missing
# ---------------------------------------------------------------------------


def test_resolve_pg_dump_returns_path_when_present(monkeypatch: pytest.MonkeyPatch) -> None:
    # If pg_dump exists on PATH, the resolver returns shutil.which's answer.
    fake_path = "/usr/bin/pg_dump"
    monkeypatch.setattr(shutil, "which", lambda _: fake_path)
    assert _resolve_pg_dump() == fake_path


def test_resolve_pg_dump_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(PgDumpError, match="not found on PATH"):
        _resolve_pg_dump()


def test_resolve_pg_restore_returns_path_when_present(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: "/usr/bin/pg_restore")
    assert _resolve_pg_restore() == "/usr/bin/pg_restore"


def test_resolve_pg_restore_raises_when_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(shutil, "which", lambda _: None)
    with pytest.raises(PgRestoreError, match="not found on PATH"):
        _resolve_pg_restore()


# ---------------------------------------------------------------------------
# _build_env — password injected, ambient env preserved
# ---------------------------------------------------------------------------


def test_dump_build_env_injects_password(
    conn: DatabaseConnection,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("PATH", "/some/path")
    env = dump_build_env(conn)
    assert env["PGPASSWORD"] == "s3cret"
    assert env["PATH"] == "/some/path"


def test_restore_build_env_injects_password(conn: DatabaseConnection) -> None:
    env = restore_build_env(conn)
    assert env["PGPASSWORD"] == "s3cret"


# ---------------------------------------------------------------------------
# _build_argv — flags + connection params present, password absent
# ---------------------------------------------------------------------------


def test_dump_build_argv_includes_connection_args(conn: DatabaseConnection) -> None:
    argv = dump_build_argv("/usr/bin/pg_dump", conn)
    assert argv[0] == "/usr/bin/pg_dump"
    assert "--format=custom" in argv
    assert "--no-owner" in argv
    assert "--no-acl" in argv
    assert argv[argv.index("--host") : argv.index("--host") + 2] == ["--host", "db.example"]
    assert argv[argv.index("--port") : argv.index("--port") + 2] == ["--port", "5433"]
    assert argv[argv.index("--username") : argv.index("--username") + 2] == ["--username", "alice"]
    assert argv[argv.index("--dbname") : argv.index("--dbname") + 2] == ["--dbname", "appdb"]


def test_dump_build_argv_does_not_leak_password(conn: DatabaseConnection) -> None:
    argv = dump_build_argv("/usr/bin/pg_dump", conn)
    assert "s3cret" not in argv
    assert all("s3cret" not in arg for arg in argv)


def test_restore_build_argv_includes_clean_and_if_exists(conn: DatabaseConnection) -> None:
    argv = restore_build_argv("/usr/bin/pg_restore", conn)
    assert argv[0] == "/usr/bin/pg_restore"
    assert "--clean" in argv
    assert "--if-exists" in argv
    assert "--no-owner" in argv
    assert "--no-acl" in argv
    assert "--exit-on-error" in argv


def test_restore_build_argv_does_not_leak_password(conn: DatabaseConnection) -> None:
    argv = restore_build_argv("/usr/bin/pg_restore", conn)
    assert "s3cret" not in argv
