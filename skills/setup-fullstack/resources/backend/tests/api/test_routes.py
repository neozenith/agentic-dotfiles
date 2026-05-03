"""API integration tests via FastAPI's TestClient."""

from __future__ import annotations

from fastapi.testclient import TestClient


def test_health(client: TestClient) -> None:
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json() == {"status": "ok"}


def test_echo_round_trip(client: TestClient) -> None:
    r = client.post("/api/echo", json={"message": "  hi  "})
    assert r.status_code == 200
    assert r.json() == {"message": "hi"}


def test_echo_rejects_empty(client: TestClient) -> None:
    r = client.post("/api/echo", json={"message": ""})
    assert r.status_code == 422  # Pydantic validation error


def test_echo_rejects_too_long(client: TestClient) -> None:
    r = client.post("/api/echo", json={"message": "x" * 1001})
    assert r.status_code == 422
