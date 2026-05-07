"""Shared pytest fixtures.

The `client` fixture is async and env-var-aware, with DB isolation:

  - `BACKEND_BASE_URL` SET    -> `httpx.AsyncClient(base_url=...)` against a
                                 running server (e.g. dockerized). The
                                 container owns its own DB; `tmp_path` is unused.
  - `BACKEND_BASE_URL` UNSET  -> in-process via `httpx.AsyncClient` over
                                 `ASGITransport(app)`, with `LifespanManager`
                                 driving the FastAPI lifespan, and a
                                 tmp_path-scoped aiosqlite DB so each test
                                 gets a fresh database.

Same test files in `tests/api/` run in both modes — no test code duplication.

This is NOT a mock — both branches return real HTTP clients hitting real
FastAPI handlers backed by a real database. The project's no-mocks rule
(see .claude/rules/python/tests.md) is explicit: no `unittest.mock`, no
`@patch`, no `MagicMock`, no exceptions.
"""

from __future__ import annotations

import os
from collections.abc import AsyncIterator
from pathlib import Path

import httpx
import pytest
from asgi_lifespan import LifespanManager

from server.api.app import create_app


@pytest.fixture
async def client(tmp_path: Path) -> AsyncIterator[httpx.AsyncClient]:
    base_url = os.environ.get("BACKEND_BASE_URL")
    if base_url:
        async with httpx.AsyncClient(base_url=base_url, timeout=10.0) as c:
            yield c
    else:
        db_path = tmp_path / "test.db"
        app = create_app(database_url=f"sqlite+aiosqlite:///{db_path}")
        async with LifespanManager(app):
            transport = httpx.ASGITransport(app=app)
            async with httpx.AsyncClient(
                transport=transport, base_url="http://test"
            ) as c:
                yield c
