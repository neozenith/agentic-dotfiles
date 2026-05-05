"""StorageBackend protocol — the seam for cloud-agnostic object storage.

The contract is small on purpose: put / get / head / list. Anything more
complex (multipart, presigned URLs, lifecycle rules) lives outside the
abstraction because it is provider-specific or naturally configured at the
bucket level (e.g. server-side lifecycle).

All methods are async so backends can do I/O on the event loop without the
caller having to think about it. Sync SDKs (boto3) are wrapped via
`asyncio.to_thread` inside their backend. Native-async SDKs slot in directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Protocol


class ObjectNotFoundError(LookupError):
    """Raised by `get_object` / `head_object` when the key does not exist.

    A subclass of `LookupError` so callers using `except LookupError` (the
    stdlib idiom for missing-key errors) catch it naturally.
    """


@dataclass(frozen=True, slots=True)
class ObjectMetadata:
    """What `head_object` returns: enough to make decisions without downloading.

    `last_modified` is provider-supplied (timezone-aware UTC). `size` is bytes.
    `etag` is opaque — useful for cache invalidation but not for identity
    across regions or multipart boundaries.
    """

    key: str
    size: int
    last_modified: datetime
    etag: str


@dataclass(frozen=True, slots=True)
class ObjectInfo:
    """Listing-shape — same fields as ObjectMetadata, but as plain entries.

    Kept distinct from ObjectMetadata so a future backend can return richer
    head info (storage class, encryption, custom metadata) without bloating
    listings.
    """

    key: str
    size: int
    last_modified: datetime


class StorageBackend(Protocol):
    """The cloud-agnostic object-storage seam.

    Implementations MUST raise `ObjectNotFoundError` for missing-key gets.
    Implementations MUST treat `put_object` as overwrite-on-existing-key
    (the caller decides retention via versioning / unique keys).
    """

    async def put_object(self, key: str, data: bytes) -> None:
        """Upload `data` under `key`. Overwrites any existing object."""
        ...  # pragma: no cover

    async def get_object(self, key: str) -> bytes:
        """Return the bytes stored under `key`. Raises `ObjectNotFoundError` if missing."""
        ...  # pragma: no cover

    async def head_object(self, key: str) -> ObjectMetadata:
        """Return metadata for `key` without downloading. Raises `ObjectNotFoundError`."""
        ...  # pragma: no cover

    async def list_objects(self, prefix: str = "") -> list[ObjectInfo]:
        """Return all objects whose key starts with `prefix`, sorted by key ascending."""
        ...  # pragma: no cover
