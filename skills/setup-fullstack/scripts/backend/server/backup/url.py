"""Parse a SQLAlchemy DATABASE_URL into the connection bits pg_dump needs.

`pg_dump` does not understand SQLAlchemy URLs (with the `+asyncpg` driver
suffix), so we strip the driver, then either:

  * pass the URL via `-d` (libpq parses it), OR
  * fan out to `-h/-U/-p` plus `PGPASSWORD` env var.

The fan-out form is what we use here, because it puts the password in the
process environment instead of `argv` (where `ps` would expose it).
"""

from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import unquote, urlparse


class UnsupportedDatabaseUrlError(ValueError):
    """Raised when DATABASE_URL points at something pg_dump can't speak to.

    SQLite, in particular, is silently a no-op for backup/restore — the file
    is already file-backed, so `cp` is the right tool. This module raises so
    callers can decide whether to skip or escalate.
    """


@dataclass(frozen=True, slots=True)
class DatabaseConnection:
    """libpq connection parameters extracted from a DATABASE_URL.

    Password is included so callers can put it in `PGPASSWORD` instead of
    on the command line. `database` is the bare DB name, never a URL.
    """

    host: str
    port: int
    user: str
    password: str
    database: str


def parse_database_url(database_url: str) -> DatabaseConnection:
    """Parse a SQLAlchemy postgres URL. Raise on non-postgres or malformed input."""
    if not database_url:
        raise UnsupportedDatabaseUrlError("DATABASE_URL is empty")

    # Strip the driver suffix so urlparse handles the host correctly:
    #   postgresql+asyncpg://...  ->  postgresql://...
    scheme_prefix, sep, rest = database_url.partition("://")
    if not sep:
        raise UnsupportedDatabaseUrlError(f"DATABASE_URL has no scheme: {database_url!r}")
    base_scheme = scheme_prefix.split("+", 1)[0]
    if base_scheme not in {"postgresql", "postgres"}:
        raise UnsupportedDatabaseUrlError(
            f"Backup only supports Postgres URLs; got scheme {base_scheme!r}"
        )

    parsed = urlparse(f"{base_scheme}://{rest}")
    if not parsed.hostname:
        raise UnsupportedDatabaseUrlError(f"DATABASE_URL has no hostname: {database_url!r}")

    database = (parsed.path or "").lstrip("/")
    if not database:
        raise UnsupportedDatabaseUrlError(f"DATABASE_URL has no database name: {database_url!r}")

    return DatabaseConnection(
        host=parsed.hostname,
        port=parsed.port or 5432,
        user=unquote(parsed.username or ""),
        password=unquote(parsed.password or ""),
        database=database,
    )
