"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from server.api.app import create_app


@pytest.fixture
def client() -> Iterator[TestClient]:
    """A TestClient bound to a freshly-built app instance.

    Each test gets its own app; nothing leaks across tests at module scope.
    """
    with TestClient(create_app()) as c:
        yield c
