"""Configuration helpers — single point of env-var access.

Only env-var reads in the codebase live here; everything else takes config as
a parameter. Keeps config drift easy to audit.
"""

from __future__ import annotations

import os
from pathlib import Path

# Default to async SQLite for local dev. Override via DATABASE_URL.
# Examples:
#   sqlite+aiosqlite:///./tmp/app.db                 (local file, default)
#   sqlite+aiosqlite:////app/data/app.db             (Docker absolute path)
#   postgresql+asyncpg://user:pass@host:5432/dbname  (Postgres)
DEFAULT_DATABASE_URL = "sqlite+aiosqlite:///./tmp/app.db"

DEFAULT_BACKUP_INTERVAL_SECONDS = 900
"""15 minutes. Configurable via BACKUP_INTERVAL_SECONDS — must be tunable per
the prototype goals; some demos warrant more frequent backups, some less."""

DEFAULT_BACKUP_KEY_PREFIX = "backups/"


def get_database_url() -> str:
    """Return the configured DATABASE_URL, or a sensible local default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_static_dir() -> Path | None:
    """If STATIC_DIR is set, return it as a Path. Used by create_app to mount the SPA."""
    raw = os.environ.get("STATIC_DIR")
    if not raw:
        return None
    return Path(raw)


def get_backup_interval_seconds() -> int:
    """How often the scheduler runs `pg_dump`. Default 900s (15 min)."""
    raw = os.environ.get("BACKUP_INTERVAL_SECONDS", "").strip()
    if not raw:
        return DEFAULT_BACKUP_INTERVAL_SECONDS
    return int(raw)


def get_backup_key_prefix() -> str:
    """Object-key prefix for all backup files (timestamped + latest pointer)."""
    return os.environ.get("BACKUP_KEY_PREFIX", DEFAULT_BACKUP_KEY_PREFIX)


def is_backup_enabled() -> bool:
    """Master kill-switch. If false, no scheduler, no admin routes, no restore.

    Useful for local dev when you don't want to spin up MinIO. Defaults to
    false when STORAGE_BACKEND is empty/missing.
    """
    storage = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    if storage in {"", "none", "disabled"}:
        return False
    explicit = os.environ.get("BACKUP_ENABLED", "").strip().lower()
    return explicit not in {"0", "false", "no", "off"}
