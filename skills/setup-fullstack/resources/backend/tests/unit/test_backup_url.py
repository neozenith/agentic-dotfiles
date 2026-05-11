"""Tests for the SQLAlchemy-URL → libpq-connection-args parser."""

from __future__ import annotations

import pytest

from server.storage.backup.url import UnsupportedDatabaseUrlError, parse_database_url


def test_parses_canonical_postgres_url() -> None:
    conn = parse_database_url("postgresql://user:pw@db.example:5433/appdb")
    assert conn.host == "db.example"
    assert conn.port == 5433
    assert conn.user == "user"
    assert conn.password == "pw"
    assert conn.database == "appdb"


def test_strips_asyncpg_driver_suffix() -> None:
    conn = parse_database_url("postgresql+asyncpg://u:p@h:5432/d")
    assert conn.host == "h"
    assert conn.database == "d"


def test_defaults_port_to_5432() -> None:
    conn = parse_database_url("postgresql://u:p@h/d")
    assert conn.port == 5432


def test_url_decodes_password() -> None:
    conn = parse_database_url("postgresql://u:p%40ss@h/d")
    assert conn.password == "p@ss"


def test_accepts_postgres_alias_scheme() -> None:
    conn = parse_database_url("postgres://u:p@h/d")
    assert conn.database == "d"


def test_rejects_empty_url() -> None:
    with pytest.raises(UnsupportedDatabaseUrlError):
        parse_database_url("")


def test_rejects_sqlite_url() -> None:
    with pytest.raises(UnsupportedDatabaseUrlError, match="Postgres"):
        parse_database_url("sqlite+aiosqlite:///./tmp/app.db")


def test_rejects_url_without_database_name() -> None:
    with pytest.raises(UnsupportedDatabaseUrlError, match="database name"):
        parse_database_url("postgresql://u:p@h:5432/")


def test_rejects_url_without_scheme() -> None:
    with pytest.raises(UnsupportedDatabaseUrlError, match="scheme"):
        parse_database_url("user:pw@host/db")


def test_rejects_url_without_host() -> None:
    with pytest.raises(UnsupportedDatabaseUrlError, match="hostname"):
        parse_database_url("postgresql:///dbname")
