"""Backup-feature context attached to `app.state`.

A small dataclass that admin routes pull off the FastAPI request to reach the
storage backend, current key prefix, and the (optional) backup scheduler.
Lives outside `app.py` to break a TYPE_CHECKING cycle: `admin.py` needs to
type-annotate the dependency, and `app.py` constructs it.
"""

from __future__ import annotations

from dataclasses import dataclass

from server.backup.lifecycle import BackupScheduler
from server.storage.base import StorageBackend


@dataclass(slots=True)
class BackupContext:
    """Runtime config + handles the backup feature exposes via `app.state.backup`."""

    storage: StorageBackend
    scheduler: BackupScheduler
    database_url: str
    interval_seconds: int
    key_prefix: str
    bucket_label: str
    """Human-readable identifier for status responses (e.g. "s3://my-bucket")."""
