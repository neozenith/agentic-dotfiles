"""Shared pytest fixtures.

The `client` fixture is env-var-aware:

  - `BACKEND_BASE_URL` UNSET (default) -> `TestClient(create_app())`, in-process.
  - `BACKEND_BASE_URL` SET             -> `httpx.Client(base_url=...)` against
                                          a running server (e.g. dockerized).

Same test files in `tests/api/` run in both modes — no test code duplication.
TestClient is a subclass of httpx.Client, so the Iterator[httpx.Client] type
covers both branches.

This is NOT a mock — both branches return real HTTP clients hitting real
FastAPI handlers. The project's no-mocks rule (see .claude/rules/python/tests.md)
is explicit: no `unittest.mock`, no `@patch`, no `MagicMock`, no exceptions.
"""

from __future__ import annotations

import os
from collections.abc import Iterator

import httpx
import pytest
from fastapi.testclient import TestClient

from server.api.app import create_app


@pytest.fixture
def client() -> Iterator[httpx.Client]:
    base_url = os.environ.get("BACKEND_BASE_URL")
    if base_url:
        with httpx.Client(base_url=base_url, timeout=10.0) as c:
            yield c
    else:
        with TestClient(create_app()) as c:
            yield c
