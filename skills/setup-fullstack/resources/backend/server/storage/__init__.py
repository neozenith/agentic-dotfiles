"""Object-storage abstraction for the backup/restore feature.

The `StorageBackend` protocol is the seam that lets the same backup/restore
code target AWS S3, MinIO (locally), and — once added — GCS, without the
caller knowing which.

Concrete backends:
  * `S3Backend` — boto3-based; works against AWS S3 and MinIO (the latter via
    a configurable `endpoint_url`). MinIO targets the S3 wire protocol so a
    single backend covers both deployment modes.
  * `InMemoryBackend` — dict-backed; used in unit tests and for local dev when
    no real bucket is configured. Genuine implementation, not a test double.

Pick a backend at runtime via `make_storage_backend()` which reads env vars.
"""

from server.storage.base import (
    ObjectInfo,
    ObjectMetadata,
    ObjectNotFoundError,
    StorageBackend,
)
from server.storage.factory import make_storage_backend
from server.storage.local import LocalStorage, UnsafeStorageKeyError
from server.storage.memory import InMemoryBackend
from server.storage.s3 import S3Backend

__all__ = [
    "InMemoryBackend",
    "LocalStorage",
    "ObjectInfo",
    "ObjectMetadata",
    "ObjectNotFoundError",
    "S3Backend",
    "StorageBackend",
    "UnsafeStorageKeyError",
    "make_storage_backend",
]
