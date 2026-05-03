"""API integration tests via the env-var-aware `client` fixture.

The same tests run two ways:
  - default: in-process via TestClient(create_app())
  - BACKEND_BASE_URL set: via httpx.Client against a running (e.g. dockerized) server

`client` is typed as httpx.Client because TestClient is a subclass of it —
the wider type covers both modes. See conftest.py.
"""

from __future__ import annotations

import httpx


def test_health(client: httpx.Client) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_echo_round_trip(client: httpx.Client) -> None:
    r = client.post("/api/echo", json={"message": "  hi  "})
    assert r.status_code == 200
    assert r.json() == {"message": "hi"}


def test_echo_rejects_empty(client: httpx.Client) -> None:
    r = client.post("/api/echo", json={"message": ""})
    assert r.status_code == 422  # Pydantic validation error


def test_echo_rejects_too_long(client: httpx.Client) -> None:
    r = client.post("/api/echo", json={"message": "x" * 1001})
    assert r.status_code == 422
