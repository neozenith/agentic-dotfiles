"""CRUD tests for the Note resource.

Same dual-transport pattern as test_items.py — see conftest.py for the fixture
that switches between in-process AsyncClient and httpx-against-Docker.
"""

from __future__ import annotations

import httpx


async def test_list_notes_returns_array(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/notes")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


async def test_create_get_delete_round_trip(client: httpx.AsyncClient) -> None:
    r = await client.post(
        "/api/notes",
        json={"title": "shopping", "body": "milk\neggs\nbread"},
    )
    assert r.status_code == 201
    note = r.json()
    assert note["title"] == "shopping"
    note_id = note["id"]

    r = await client.get(f"/api/notes/{note_id}")
    assert r.status_code == 200
    assert r.json()["body"] == "milk\neggs\nbread"

    r = await client.delete(f"/api/notes/{note_id}")
    assert r.status_code == 204

    r = await client.get(f"/api/notes/{note_id}")
    assert r.status_code == 404


async def test_get_missing_note_404(client: httpx.AsyncClient) -> None:
    r = await client.get("/api/notes/99999999")
    assert r.status_code == 404


async def test_delete_missing_note_404(client: httpx.AsyncClient) -> None:
    r = await client.delete("/api/notes/99999999")
    assert r.status_code == 404


async def test_create_rejects_empty_title(client: httpx.AsyncClient) -> None:
    r = await client.post("/api/notes", json={"title": "", "body": "x"})
    assert r.status_code == 422
