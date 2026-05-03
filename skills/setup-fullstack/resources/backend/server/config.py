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


def get_database_url() -> str:
    """Return the configured DATABASE_URL, or a sensible local default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_static_dir() -> Path | None:
    """If STATIC_DIR is set, return it as a Path. Used by create_app to mount the SPA."""
    raw = os.environ.get("STATIC_DIR")
    if not raw:
        return None
    return Path(raw)
