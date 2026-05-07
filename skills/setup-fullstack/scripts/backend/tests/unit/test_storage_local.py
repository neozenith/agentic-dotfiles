"""LocalStorage-specific tests beyond the shared protocol contract.

Things only the filesystem backend has:
  * Path-traversal protection on object keys.
  * Atomic writes — a partially-written file must never be visible.
  * The constructor's tempfile fallback when no `base_dir` is given.
  * Files-on-disk inspection (the contract tests treat the backend as a
    black box; here we peek at the underlying filesystem).
"""

from __future__ import annotations

from pathlib import Path

import pytest

from server.storage import LocalStorage, UnsafeStorageKeyError
from server.storage.local import DEFAULT_LOCAL_ROOT

# ---------------------------------------------------------------------------
# Path-traversal protection — these keys must NOT escape base_dir
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "bad_key",
    [
        "../escape.txt",
        "subdir/../../escape.txt",
        "/absolute/path.txt",
        "",
        "./relative.txt",
        "a//b",
    ],
)
async def test_unsafe_keys_rejected(tmp_path: Path, bad_key: str) -> None:
    backend = LocalStorage(base_dir=tmp_path / "store")
    with pytest.raises(UnsafeStorageKeyError):
        await backend.put_object(bad_key, b"x")


# ---------------------------------------------------------------------------
# Filesystem layout — keys map to files under base_dir
# ---------------------------------------------------------------------------


async def test_nested_keys_create_subdirectories(tmp_path: Path) -> None:
    base = tmp_path / "store"
    backend = LocalStorage(base_dir=base)
    await backend.put_object("backups/2026/jan/snapshot.dump", b"data")

    expected_file = base / "backups" / "2026" / "jan" / "snapshot.dump"
    assert expected_file.is_file()
    assert expected_file.read_bytes() == b"data"


async def test_base_dir_property_is_resolved_absolute(tmp_path: Path) -> None:
    rel = tmp_path / "store"
    backend = LocalStorage(base_dir=rel)
    assert backend.base_dir.is_absolute()
    assert backend.base_dir.exists()


# ---------------------------------------------------------------------------
# Atomic write — no partial files visible after a failed write
# ---------------------------------------------------------------------------


async def test_no_temp_files_left_after_successful_put(tmp_path: Path) -> None:
    base = tmp_path / "store"
    backend = LocalStorage(base_dir=base)
    await backend.put_object("foo.dump", b"data")

    # The atomic-write strategy uses a same-directory tempfile; after a
    # successful put nothing should remain except the target file.
    siblings = list((base).iterdir())
    assert len(siblings) == 1
    assert siblings[0].name == "foo.dump"


# ---------------------------------------------------------------------------
# Tempfile fallback — no base_dir → mkdtemp under tmp/local_storage/
# ---------------------------------------------------------------------------


async def test_fallback_creates_dir_under_project_tmp(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """When base_dir is omitted, a directory is created via tempfile.mkdtemp.

    The fallback's parent (DEFAULT_LOCAL_ROOT) is project-local — `tmp/...` —
    never the system /tmp/. This test pins that contract by chdir'ing to a
    scratch dir (so DEFAULT_LOCAL_ROOT resolves there) and checking the
    backend's base_dir is rooted inside it.
    """
    monkeypatch.chdir(tmp_path)

    backend = LocalStorage()  # no base_dir → fallback path

    # The created directory must be inside project-relative DEFAULT_LOCAL_ROOT,
    # not the system temp dir. Compare *resolved* paths to handle macOS's
    # /var → /private/var symlink and similar.
    expected_root = (tmp_path / DEFAULT_LOCAL_ROOT).resolve()
    assert backend.base_dir.is_relative_to(expected_root)
    assert backend.base_dir.name.startswith("store_")


async def test_fallback_directories_are_unique(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """Two fallback backends must get independent directories — the whole
    point of mkdtemp's unique-suffix behavior. Without this, parallel tests
    (and parallel app instances) would clobber each other's data."""
    monkeypatch.chdir(tmp_path)

    a = LocalStorage()
    b = LocalStorage()
    assert a.base_dir != b.base_dir


# ---------------------------------------------------------------------------
# Round-trip persistence — closing one backend and reopening with the same
# base_dir must see the prior data
# ---------------------------------------------------------------------------


async def test_persistence_across_backend_instances(tmp_path: Path) -> None:
    base = tmp_path / "store"

    first = LocalStorage(base_dir=base)
    await first.put_object("k", b"persistent")

    second = LocalStorage(base_dir=base)
    assert await second.get_object("k") == b"persistent"
