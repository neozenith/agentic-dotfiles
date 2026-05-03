"""CRUD tests for the Item resource.

These tests are written so they pass in BOTH transports:

  - in-process (TestClient + tmp_path SQLite, fresh per test)
  - against a dockerized backend (httpx + container's persistent SQLite)

The dockerized backend's DB persists across requests, so tests cannot assume
an empty initial state. Each test creates its own row, asserts behaviour,
then deletes it as cleanup.
"""

from __future__ import annotations

import httpx


def test_list_items_returns_array(client: httpx.Client) -> None:
    r = client.get("/api/items")
    assert r.status_code == 200
    assert isinstance(r.json(), list)


def test_create_get_delete_round_trip(client: httpx.Client) -> None:
    # Create
    r = client.post(
        "/api/items",
        json={"name": "widget", "description": "a small thing"},
    )
    assert r.status_code == 201
    item = r.json()
    assert item["name"] == "widget"
    assert item["description"] == "a small thing"
    assert isinstance(item["id"], int)
    item_id = item["id"]

    # Get by id
    r = client.get(f"/api/items/{item_id}")
    assert r.status_code == 200
    assert r.json()["id"] == item_id

    # Delete
    r = client.delete(f"/api/items/{item_id}")
    assert r.status_code == 204

    # Subsequent get is 404
    r = client.get(f"/api/items/{item_id}")
    assert r.status_code == 404


def test_get_missing_item_404(client: httpx.Client) -> None:
    r = client.get("/api/items/99999999")
    assert r.status_code == 404


def test_delete_missing_item_404(client: httpx.Client) -> None:
    r = client.delete("/api/items/99999999")
    assert r.status_code == 404


def test_create_rejects_empty_name(client: httpx.Client) -> None:
    r = client.post("/api/items", json={"name": "", "description": "x"})
    assert r.status_code == 422


def test_create_accepts_default_description(client: httpx.Client) -> None:
    r = client.post("/api/items", json={"name": "no-desc"})
    assert r.status_code == 201
    item = r.json()
    assert item["description"] == ""
    # cleanup
    client.delete(f"/api/items/{item['id']}")
