from __future__ import annotations

from httpx import AsyncClient


async def test_v1_prefix_works(client: AsyncClient):
    resp = await client.get("/api/v1/providers")
    assert resp.status_code == 200
    assert isinstance(resp.json(), list)
    assert "Deprecation" not in resp.headers


async def test_legacy_prefix_still_works_with_deprecation_headers(client: AsyncClient):
    resp = await client.get("/api/providers")
    assert resp.status_code == 200
    assert resp.headers.get("Deprecation") == "true"
    assert resp.headers.get("Sunset")
    link = resp.headers.get("Link", "")
    assert "/api/v1/providers" in link


async def test_v1_session_create_and_join(client: AsyncClient):
    create = await client.post(
        "/api/v1/sessions",
        json={"host_display_name": "Host", "provider": "tension"},
    )
    assert create.status_code == 200
    code = create.json()["code"]

    join = await client.post(
        f"/api/v1/sessions/{code}/join", json={"display_name": "Guest"}
    )
    assert join.status_code == 200

    summary = await client.get(f"/api/v1/sessions/{code}")
    assert summary.status_code == 200
    assert summary.json()["participant_count"] == 2
