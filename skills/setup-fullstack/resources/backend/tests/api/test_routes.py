"""API integration tests via the env-var-aware async `client` fixture.

The same tests run two ways:
  - default: in-process via httpx.AsyncClient + ASGITransport + LifespanManager
  - BACKEND_BASE_URL set: via httpx.AsyncClient against a running (e.g.
    dockerized) server.

`client` is typed as httpx.AsyncClient — see conftest.py.
"""

from __future__ import annotations

import httpx


async def test_health(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


async def test_echo_round_trip(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/echo", json={"message": "  hi  "})
    assert r.status_code == 200
    assert r.json() == {"message": "hi"}


async def test_echo_rejects_empty(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/echo", json={"message": ""})
    assert r.status_code == 422  # Pydantic validation error


async def test_echo_rejects_too_long(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/echo", json={"message": "x" * 1001})
    assert r.status_code == 422
