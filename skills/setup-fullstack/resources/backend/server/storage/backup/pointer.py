"""The latest-dump pointer convention.

A backup prefix in object storage contains immutable timestamped dumps
(`<prefix><yyyymmddThhmmssZ>.dump`) plus one always-current pointer
(`<prefix>latest.dump`). This module is the single owner of that filename
and of the "two writes per dump" pattern that advances the pointer.

Three sites used to know this convention directly: `dump.py` defined the
constant and wrote the pointer; `restore.py` imported the constant for its
default key; `api/admin.py` re-built the literal in the status endpoint.
After deepening, only this module knows the filename — changing the scheme
(e.g. to a manifest.json with multiple historical pointers) is a one-file
edit with no string-literal hunt across the codebase.
"""

from __future__ import annotations

from datetime import UTC, datetime

from server.storage.base import ObjectMetadata, ObjectNotFoundError, StorageBackend

_POINTER_FILENAME = "latest.dump"


def latest_pointer_key(prefix: str) -> str:
    """Return the key that always names the most recent backup under `prefix`."""
    return f"{prefix}{_POINTER_FILENAME}"


def timestamped_key(prefix: str, *, when: datetime | None = None) -> str:
    """Return a UTC-timestamped key for a fresh dump under `prefix`."""
    moment = when if when is not None else datetime.now(UTC)
    return f"{prefix}{moment.strftime('%Y%m%dT%H%M%SZ')}.dump"


async def record_dump(
    storage: StorageBackend,
    prefix: str,
    dump_bytes: bytes,
    *,
    when: datetime | None = None,
) -> str:
    """Write `dump_bytes` to a fresh timestamped key AND advance the latest pointer.

    Returns the timestamped key. The two writes are intentional: the
    timestamped key is the canonical immutable record, and the pointer is a
    convenience for cold-start restore so a worker can fetch "the latest"
    without listing the prefix.
    """
    ts_key = timestamped_key(prefix, when=when)
    await storage.put_object(ts_key, dump_bytes)
    await storage.put_object(latest_pointer_key(prefix), dump_bytes)
    return ts_key


async def head_latest(storage: StorageBackend, prefix: str) -> ObjectMetadata | None:
    """Metadata for the latest dump, or None if no backup exists yet under `prefix`."""
    try:
        return await storage.head_object(latest_pointer_key(prefix))
    except ObjectNotFoundError:
        return None
