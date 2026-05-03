"""Configuration helpers — single point of env-var access.

Only one helper for now; expand as the app grows. Keeping all
`os.environ.get(...)` calls in this module makes config drift easy to audit.
"""

from __future__ import annotations

import os
from pathlib import Path

DEFAULT_DATABASE_URL = "sqlite:///./tmp/app.db"


def get_database_url() -> str:
    """Return the configured DATABASE_URL, or a sensible local default."""
    return os.environ.get("DATABASE_URL", DEFAULT_DATABASE_URL)


def get_static_dir() -> Path | None:
    """If STATIC_DIR is set, return it as a Path. Used by create_app to mount the SPA."""
    raw = os.environ.get("STATIC_DIR")
    if not raw:
        return None
    return Path(raw)
