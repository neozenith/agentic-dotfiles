"""Contract tests for the StorageBackend protocol.

The eight assertions below are the *minimum* behavior every backend must
satisfy. They run parametrically against InMemoryBackend AND LocalStorage —
two real implementations of the same interface. The S3Backend is exercised
by the dockerized integration test (it requires a running endpoint), but it
honors the same contract.

Adding a future backend (e.g. GCSBackend) will require only one new entry in
the `_BACKENDS` factory map: the contract is the test, not the impl.
"""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

import pytest

from server.storage import (
    InMemoryBackend,
    LocalStorage,
    ObjectNotFoundError,
    StorageBackend,
)

BackendFactory = Callable[[Path], StorageBackend]

# Each entry produces a fresh backend per test, scoped to the pytest tmp_path
# so test isolation is automatic and no state leaks between tests.
_BACKENDS: dict[str, BackendFactory] = {
    "memory": lambda _tmp: InMemoryBackend(),
    "local": lambda tmp: LocalStorage(base_dir=tmp / "store"),
}


@pytest.fixture(params=sorted(_BACKENDS.keys()))
def backend(request: pytest.FixtureRequest, tmp_path: Path) -> StorageBackend:
    return _BACKENDS[request.param](tmp_path)


# ---------------------------------------------------------------------------
# The contract — must hold for every backend
# ---------------------------------------------------------------------------


async def test_put_then_get_roundtrips_bytes(backend: StorageBackend) -> None:
    await backend.put_object("foo.txt", b"hello world")
    assert await backend.get_object("foo.txt") == b"hello world"


async def test_get_missing_raises_object_not_found(backend: StorageBackend) -> None:
    with pytest.raises(ObjectNotFoundError):
        await backend.get_object("does-not-exist")


async def test_put_overwrites_existing_key(backend: StorageBackend) -> None:
    await backend.put_object("k", b"v1")
    await backend.put_object("k", b"v2")
    assert await backend.get_object("k") == b"v2"


async def test_head_returns_size_and_etag(backend: StorageBackend) -> None:
    await backend.put_object("k", b"abc")
    meta = await backend.head_object("k")
    assert meta.key == "k"
    assert meta.size == 3
    assert meta.etag  # non-empty


async def test_head_missing_raises(backend: StorageBackend) -> None:
    with pytest.raises(ObjectNotFoundError):
        await backend.head_object("nope")


async def test_list_filters_by_prefix_and_sorts(backend: StorageBackend) -> None:
    await backend.put_object("backups/b.dump", b"b")
    await backend.put_object("backups/a.dump", b"a")
    await backend.put_object("other/c.dump", b"c")

    listing = await backend.list_objects("backups/")
    assert [o.key for o in listing] == ["backups/a.dump", "backups/b.dump"]


async def test_list_with_empty_prefix_returns_everything(backend: StorageBackend) -> None:
    await backend.put_object("a", b"1")
    await backend.put_object("b", b"22")
    listing = await backend.list_objects()
    assert {o.key for o in listing} == {"a", "b"}
    assert {o.size for o in listing} == {1, 2}


async def test_list_empty_when_no_match(backend: StorageBackend) -> None:
    await backend.put_object("a", b"1")
    assert await backend.list_objects("nope/") == []
