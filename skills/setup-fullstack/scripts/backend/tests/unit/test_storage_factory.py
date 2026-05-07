"""Tests for the env-var-driven storage backend factory.

The S3 backend construction is exercised here too — `S3Backend.__init__`
just builds a boto3 client locally, no network I/O — so the factory paths
are fully covered without a real bucket.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.storage import InMemoryBackend, LocalStorage, S3Backend, make_storage_backend
from server.storage.factory import StorageConfigError


def test_returns_none_when_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("STORAGE_BACKEND", raising=False)
    assert make_storage_backend() is None


def test_explicit_disabled_value_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "disabled")
    assert make_storage_backend() is None


def test_memory_backend(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "memory")
    backend = make_storage_backend()
    assert isinstance(backend, InMemoryBackend)


def test_s3_backend_with_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.setenv("STORAGE_BUCKET", "test-bucket")
    monkeypatch.setenv("S3_ENDPOINT_URL", "http://minio:9000")
    monkeypatch.setenv("S3_REGION", "us-west-2")
    monkeypatch.setenv("S3_ADDRESSING_STYLE", "path")
    backend = make_storage_backend()
    assert isinstance(backend, S3Backend)


def test_s3_backend_requires_bucket(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "s3")
    monkeypatch.delenv("STORAGE_BUCKET", raising=False)
    with pytest.raises(StorageConfigError, match="STORAGE_BUCKET"):
        make_storage_backend()


def test_unknown_backend_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "azure")
    with pytest.raises(StorageConfigError, match="Unknown STORAGE_BACKEND"):
        make_storage_backend()


def test_case_insensitive_backend_name(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "Memory")
    assert isinstance(make_storage_backend(), InMemoryBackend)


def test_local_backend_with_explicit_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", str(tmp_path / "explicit"))
    backend = make_storage_backend()
    assert isinstance(backend, LocalStorage)
    assert backend.base_dir == (tmp_path / "explicit").resolve()


def test_local_backend_falls_back_when_path_unset(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.delenv("STORAGE_LOCAL_PATH", raising=False)
    backend = make_storage_backend()
    assert isinstance(backend, LocalStorage)
    # Fallback path lands inside project-local tmp/local_storage/, not /tmp/.
    assert "local_storage" in str(backend.base_dir)


def test_local_backend_empty_path_falls_back(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Empty STORAGE_LOCAL_PATH should be treated as unset, not as `Path("")`."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("STORAGE_LOCAL_PATH", "   ")  # whitespace-only
    backend = make_storage_backend()
    assert isinstance(backend, LocalStorage)
    assert "local_storage" in str(backend.base_dir)
