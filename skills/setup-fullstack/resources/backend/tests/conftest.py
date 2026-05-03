"""Shared pytest fixtures.

The `client` fixture is env-var-aware and DB-isolated:

  - `BACKEND_BASE_URL` SET    -> `httpx.Client(base_url=...)` against a running
                                 server (e.g. dockerized). The container owns
                                 its own SQLite file; `tmp_path` is unused.
  - `BACKEND_BASE_URL` UNSET  -> in-process via `TestClient(create_app(...))`,
                                 with a tmp_path-scoped SQLite file so each
                                 test gets a fresh DB.

Same test files in `tests/api/` run in both modes — no test code duplication.
TestClient is a subclass of httpx.Client, so the Iterator[httpx.Client] type
covers both branches.

This is NOT a mock — both branches return real HTTP clients hitting real
FastAPI handlers backed by real SQLite. The project's no-mocks rule
(see .claude/rules/python/tests.md) is explicit: no `unittest.mock`, no
`@patch`, no `MagicMock`, no exceptions.
"""

from __future__ import annotations

import os
from collections.abc import Iterator
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient

from server.api.app import create_app


@pytest.fixture
def client(tmp_path: Path) -> Iterator[httpx.Client]:
    base_url = os.environ.get("BACKEND_BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, timeout=10.0) as c:
            yield c
    else:
        db_path = tmp_path / "test.db"
        app = create_app(database_url=f"sqlite:///{db_path}")
        with TestClient(app) as c:
            yield c
