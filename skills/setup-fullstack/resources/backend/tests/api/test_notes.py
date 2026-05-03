"""CRUD tests for the Note resource.

Same dual-transport pattern as test_items.py — see conftest.py for the fixture
that switches between in-process TestClient and httpx-against-Docker.
"""

from __future__ import annotations

import httpx


def test_list_notes_returns_array(client: httpx.Client) -> None:
    r = client.get("/api/notes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_get_delete_round_trip(client: httpx.Client) -> None:
    r = client.post(
        "/api/notes",
        json={"title": "shopping", "body": "milk\neggs\nbread"},
    )
    assert r.status_code == 201
    note = r.json()
    assert note["title"] == "shopping"
    note_id = note["id"]

    r = client.get(f"/api/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["body"] == "milk\neggs\nbread"

    r = client.delete(f"/api/notes/{note_id}")
    assert r.status_code == 204

    r = client.get(f"/api/notes/{note_id}")
    assert r.status_code == 404


def test_get_missing_note_404(client: httpx.Client) -> None:
    r = client.get("/api/notes/99999999")
    assert r.status_code == 404


def test_delete_missing_note_404(client: httpx.Client) -> None:
    r = client.delete("/api/notes/99999999")
    assert r.status_code == 404


def test_create_rejects_empty_title(client: httpx.Client) -> None:
    r = client.post("/api/notes", json={"title": "", "body": "x"})
    assert r.status_code == 422
