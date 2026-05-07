"""Filesystem-backed `StorageBackend` — third implementation alongside S3 + memory.

Use cases:
  * **Local dev without Docker** — point at any folder, get persistent storage
    across process restarts without standing up MinIO.
  * **CI integration tests** — the storage half of "real Postgres + storage"
    can run without spinning up a MinIO container; only `pg_dump`/`pg_restore`
    need real Postgres.
  * **Demo persistence on a single host** — a Cloud Run sidecar with an
    attached EFS / Persistent Disk could use this directly.

Constructor takes `base_dir`. If omitted, falls back to a deterministic
project-local temp dir via `tempfile.mkdtemp(dir=Path("tmp/local_storage"))`
— the stdlib API the user requested, scoped to the project tree to honor the
"no system /tmp/" rule.

Object keys map onto filesystem paths. Keys containing `..` segments or
absolute-path components are rejected before any filesystem operation; this
matches S3's behavior (which simply treats them as opaque key strings) and
prevents a malicious caller from escaping `base_dir`.
"""

from __future__ import annotations

import asyncio
import hashlib
import os
import tempfile
from datetime import UTC, datetime
from pathlib import Path

from server.storage.base import (
    ObjectInfo,
    ObjectMetadata,
    ObjectNotFoundError,
    StorageBackend,
)

DEFAULT_LOCAL_ROOT = Path("tmp") / "local_storage"
"""Project-local fallback root. `tempfile.mkdtemp(dir=...)` creates a unique
subdirectory inside this so concurrent backends don't collide."""


class UnsafeStorageKeyError(ValueError):
    """Raised when an object key would escape the base directory.

    Examples: keys containing `..` segments, absolute paths, or empty strings.
    These are rejected before any filesystem call so a hostile or buggy
    caller can't read/write files outside `base_dir`.
    """


def _validate_key(key: str) -> None:
    if not key:
        raise UnsafeStorageKeyError("Object key must be non-empty")
    if key.startswith("/") or key.startswith("\\"):
        raise UnsafeStorageKeyError(f"Object key must be relative: {key!r}")
    parts = key.replace("\\", "/").split("/")
    if any(p in {"", ".", ".."} for p in parts):
        raise UnsafeStorageKeyError(
            f"Object key must not contain empty / '.' / '..' segments: {key!r}"
        )


class LocalStorage(StorageBackend):
    """`StorageBackend` storing each object as a file under `base_dir`.

    `put_object` writes atomically (temp file in the same directory + rename)
    so an interrupted dump can never leave a half-written `latest.dump` for
    the next cold-start restore to consume.
    """

    def __init__(self, base_dir: Path | str | None = None) -> None:
        if base_dir is None:
            DEFAULT_LOCAL_ROOT.mkdir(parents=True, exist_ok=True)
            # mkdtemp creates a uniquely-named subdir inside DEFAULT_LOCAL_ROOT.
            # The result is a real path, not a NamedTemporaryFile handle, so
            # the directory persists across the constructor call.
            resolved = Path(tempfile.mkdtemp(dir=DEFAULT_LOCAL_ROOT, prefix="store_"))
        else:
            resolved = Path(base_dir)
            resolved.mkdir(parents=True, exist_ok=True)
        self._base = resolved.resolve()

    @property
    def base_dir(self) -> Path:
        """The resolved root directory. Useful for tests + status responses."""
        return self._base

    def _key_to_path(self, key: str) -> Path:
        _validate_key(key)
        return self._base / key

    async def put_object(self, key: str, data: bytes) -> None:
        target = self._key_to_path(key)
        target.parent.mkdir(parents=True, exist_ok=True)
        # Atomic write: same-directory tempfile + rename. Prevents a partial
        # `latest.dump` from being seen by a concurrent reader.
        tmp_fd, tmp_name = tempfile.mkstemp(
            dir=target.parent, prefix=f".{target.name}.", suffix=".tmp"
        )
        tmp_path = Path(tmp_name)
        try:
            await asyncio.to_thread(_write_and_close, tmp_fd, data)
            await asyncio.to_thread(os.replace, str(tmp_path), str(target))
        except BaseException:
            # Don't leak temp files on failure. `missing_ok=True` keeps this
            # safe even if os.replace already consumed the temp.
            tmp_path.unlink(missing_ok=True)
            raise

    async def get_object(self, key: str) -> bytes:
        target = self._key_to_path(key)
        if not target.is_file():
            raise ObjectNotFoundError(key)
        return await asyncio.to_thread(target.read_bytes)

    async def head_object(self, key: str) -> ObjectMetadata:
        target = self._key_to_path(key)
        if not target.is_file():
            raise ObjectNotFoundError(key)
        stat = await asyncio.to_thread(target.stat)
        # Hash on demand — small backups (single-MB scale for demos) are fine
        # to read into memory; head_object is not on the hot path.
        data = await asyncio.to_thread(target.read_bytes)
        etag = hashlib.md5(data, usedforsecurity=False).hexdigest()
        return ObjectMetadata(
            key=key,
            size=stat.st_size,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            etag=etag,
        )

    async def list_objects(self, prefix: str = "") -> list[ObjectInfo]:
        # Walk the whole tree, then filter by prefix on the *relative* key.
        # Sync I/O bounded by directory size; bounce to a thread.
        entries = await asyncio.to_thread(self._list_sync, prefix)
        entries.sort(key=lambda e: e.key)
        return entries

    def _list_sync(self, prefix: str) -> list[ObjectInfo]:
        out: list[ObjectInfo] = []
        if not self._base.is_dir():
            return out
        for path in self._base.rglob("*"):
            if not path.is_file():
                continue
            relative = path.relative_to(self._base).as_posix()
            if not relative.startswith(prefix):
                continue
            stat = path.stat()
            out.append(
                ObjectInfo(
                    key=relative,
                    size=stat.st_size,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                )
            )
        return out


def _write_and_close(fd: int, data: bytes) -> None:
    """Write all bytes to the open fd and close it. Helper for to_thread."""
    try:
        # os.write may write fewer bytes than requested on some platforms.
        # Loop until the full payload is flushed.
        view = memoryview(data)
        offset = 0
        while offset < len(view):
            offset += os.write(fd, view[offset:])
    finally:
        os.close(fd)
