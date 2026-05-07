"""Build a `StorageBackend` from environment variables.

Configuration knobs:

| Env var             | Required when     | Notes                                  |
|---------------------|-------------------|----------------------------------------|
| STORAGE_BACKEND     | always            | "s3", "local", "memory", or ""         |
| STORAGE_BUCKET      | backend == "s3"   | Bucket / namespace name                |
| S3_ENDPOINT_URL     | optional          | http://minio:9000 for MinIO; AWS omits |
| S3_REGION           | optional          | Defaults to "us-east-1"                |
| S3_ADDRESSING_STYLE | optional          | "path" for MinIO; "auto" for AWS       |
| STORAGE_LOCAL_PATH  | optional          | base_dir for "local"; falls back to    |
|                     |                   | tempfile under tmp/local_storage/      |

Credentials are NOT read here — boto3's standard credential chain handles
them (env vars `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY`, ~/.aws/, EC2
metadata). Letting boto3 own auth is what makes adding GCS later a one-file
change instead of a config-layer rewrite.
"""

from __future__ import annotations

import os
from pathlib import Path

from server.storage.base import StorageBackend
from server.storage.local import LocalStorage
from server.storage.memory import InMemoryBackend
from server.storage.s3 import S3Backend, S3Config


class StorageConfigError(RuntimeError):
    """Raised when env vars do not describe a usable backend."""


def make_storage_backend() -> StorageBackend | None:
    """Construct the backend named by `STORAGE_BACKEND`, or None if disabled.

    Returning None (rather than raising) lets the app boot with backups OFF;
    explicit "this feature is disabled" is more useful than a startup crash
    when a developer just wants to run the rest of the API.
    """
    name = os.environ.get("STORAGE_BACKEND", "").strip().lower()
    if name in {"", "none", "disabled"}:
        return None
    if name == "memory":
        return InMemoryBackend()
    if name == "local":
        return _build_local_backend()
    if name == "s3":
        return _build_s3_backend()
    raise StorageConfigError(
        f"Unknown STORAGE_BACKEND={name!r}. Expected 's3', 'local', 'memory', or ''."
    )


def _build_local_backend() -> LocalStorage:
    raw = os.environ.get("STORAGE_LOCAL_PATH", "").strip()
    base_dir: Path | None = Path(raw) if raw else None
    return LocalStorage(base_dir=base_dir)


def _build_s3_backend() -> S3Backend:
    bucket = os.environ.get("STORAGE_BUCKET", "").strip()
    if not bucket:
        raise StorageConfigError("STORAGE_BACKEND=s3 requires STORAGE_BUCKET to name the bucket.")
    return S3Backend(
        S3Config(
            bucket=bucket,
            region=os.environ.get("S3_REGION", "us-east-1"),
            endpoint_url=(os.environ.get("S3_ENDPOINT_URL") or None),
            addressing_style=os.environ.get("S3_ADDRESSING_STYLE", "auto"),
        )
    )
