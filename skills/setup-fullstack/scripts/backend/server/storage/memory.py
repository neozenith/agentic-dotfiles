"""In-memory `StorageBackend` — used by unit tests and as a no-config fallback.

This is NOT a mock. It is a real, complete implementation of the protocol
backed by a dict. Tests that exercise backup/restore against this backend
verify the same contract the S3 backend honors.
"""

from __future__ import annotations

import asyncio
import hashlib
from dataclasses import dataclass, field
from datetime import UTC, datetime

from server.storage.base import (
    ObjectInfo,
    ObjectMetadata,
    ObjectNotFoundError,
    StorageBackend,
)


@dataclass(slots=True)
class _StoredObject:
    data: bytes
    last_modified: datetime
    etag: str


@dataclass(slots=True)
class InMemoryBackend(StorageBackend):
    """Dict-backed object store. Thread-safe via an asyncio.Lock."""

    _objects: dict[str, _StoredObject] = field(default_factory=dict)
    _lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    async def put_object(self, key: str, data: bytes) -> None:
        etag = hashlib.md5(data, usedforsecurity=False).hexdigest()
        async with self._lock:
            self._objects[key] = _StoredObject(
                data=data,
                last_modified=datetime.now(UTC),
                etag=etag,
            )

    async def get_object(self, key: str) -> bytes:
        async with self._lock:
            obj = self._objects.get(key)
        if obj is None:
            raise ObjectNotFoundError(key)
        return obj.data

    async def head_object(self, key: str) -> ObjectMetadata:
        async with self._lock:
            obj = self._objects.get(key)
        if obj is None:
            raise ObjectNotFoundError(key)
        return ObjectMetadata(
            key=key,
            size=len(obj.data),
            last_modified=obj.last_modified,
            etag=obj.etag,
        )

    async def list_objects(self, prefix: str = "") -> list[ObjectInfo]:
        async with self._lock:
            entries = [
                ObjectInfo(
                    key=k,
                    size=len(v.data),
                    last_modified=v.last_modified,
                )
                for k, v in self._objects.items()
                if k.startswith(prefix)
            ]
        entries.sort(key=lambda e: e.key)
        return entries
