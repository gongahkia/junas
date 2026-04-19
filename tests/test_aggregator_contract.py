from __future__ import annotations

from httpx import AsyncClient


async def test_providers_contract_shape(client: AsyncClient):
    r = await client.get("/api/v1/providers")
    assert r.status_code == 200
    providers = r.json()
    assert providers

    first = providers[0]
    assert {
        "key",
        "name",
        "status",
        "requires_credentials",
        "capabilities",
        "source",
        "status_reason",
        "status_reason_code",
        "is_data_ready",
        "readiness",
        "taxonomy_version",
    } <= set(first.keys())
    assert first["taxonomy_version"] == "2026-04-aggregator-v1"
    assert {
        "list_layouts",
        "search_climbs",
        "get_climb",
        "live_data",
    } == set(first["capabilities"].keys())


async def test_climbs_response_contract_shape(client: AsyncClient):
    create = await client.post(
        "/api/v1/sessions",
        json={"host_display_name": "Host", "provider": "moonboard_catalog"},
    )
    assert create.status_code == 200, create.text
    payload = create.json()
    headers = {"X-Session-Read-Token": payload["session_read_token"]}

    r = await client.get(
        f"/api/v1/sessions/{payload['code']}/climbs",
        params={"layout_id": "2016", "limit": 2},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert {
        "climbs",
        "next_cursor",
        "total_estimate",
        "meta",
        "warnings",
    } <= set(body.keys())

    meta = body["meta"]
    assert {"provider", "fetched_at", "cache", "served_by"} <= set(meta.keys())
    assert {"hit", "stale", "cached_at", "expires_at"} <= set(meta["cache"].keys())

    climb = body["climbs"][0]
    assert "extras" in climb
    provenance = climb["extras"].get("_provenance")
    assert provenance is not None
    assert {"source_provider", "fetched_at", "normalized_fields"} <= set(provenance.keys())


async def test_layouts_response_contract_shape(client: AsyncClient):
    create = await client.post(
        "/api/v1/sessions",
        json={"host_display_name": "Host", "provider": "moonboard_catalog"},
    )
    assert create.status_code == 200, create.text
    payload = create.json()
    headers = {"X-Session-Read-Token": payload["session_read_token"]}

    r = await client.get(
        f"/api/v1/sessions/{payload['code']}/layouts",
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()

    assert {"layouts", "meta", "warnings"} <= set(body.keys())
    meta = body["meta"]
    assert {"provider", "fetched_at", "cache", "served_by"} <= set(meta.keys())

    layout = body["layouts"][0]
    provenance = layout["extras"].get("_provenance")
    assert provenance is not None
    assert {"source_provider", "fetched_at", "normalized_fields"} <= set(provenance.keys())


async def test_multi_provider_partial_warning_contract(client: AsyncClient):
    create = await client.post(
        "/api/v1/sessions",
        json={
            "host_display_name": "Host",
            "enabled_providers": ["moonboard_catalog", "crux"],
        },
    )
    assert create.status_code == 200, create.text
    payload = create.json()
    headers = {"X-Session-Read-Token": payload["session_read_token"]}

    r = await client.get(
        f"/api/v1/sessions/{payload['code']}/climbs",
        params={"layout_id": "2016", "limit": 5},
        headers=headers,
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["meta"]["provider"] == "multi"

    warnings = body["warnings"]
    assert warnings
    warning = warnings[0]
    assert {"provider", "error", "detail", "stale_cache_served"} <= set(warning.keys())
