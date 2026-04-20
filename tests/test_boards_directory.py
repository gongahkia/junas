from __future__ import annotations

import json

from httpx import AsyncClient


async def test_boards_sample_autoloaded_on_startup(client: AsyncClient):
    r = await client.get("/api/v1/boards")
    assert r.status_code == 200
    body = r.json()
    assert body["count"] > 0
    for b in body["boards"]:
        assert b["lat"] and b["lon"]
        assert b["board_type"]
        assert b["board_family"]
        assert "is_adjustable" in b


async def test_boards_by_type(client: AsyncClient):
    kil = await client.get("/api/v1/boards?board_type=kilter")
    assert kil.status_code == 200
    for b in kil.json()["boards"]:
        assert b["board_type"] == "kilter"


async def test_boards_nearby_by_coordinates(client: AsyncClient):
    # London area — should include the UK board, exclude Perth
    nearby = await client.get(
        "/api/v1/boards",
        params={"lat": 51.5, "lon": -0.1, "radius_km": 100},
    )
    assert nearby.status_code == 200
    ids = {b["id"] for b in nearby.json()["boards"]}
    assert "moonboard-the-arch-climbing-wall" in ids
    assert "kilter-onsight-rock-gym-perth" not in ids


async def test_boards_types_enumeration(client: AsyncClient):
    r = await client.get("/api/v1/boards/types")
    assert r.status_code == 200
    types = r.json()["types"]
    assert "kilter" in types
    assert "moonboard" in types


async def test_boards_get_returns_properties_and_distance(client: AsyncClient):
    g = await client.get("/api/v1/boards/moonboard-the-arch-climbing-wall")
    assert g.status_code == 200
    body = g.json()
    assert body["city"] == "London"
    assert body["board_family"] == "moonboard"
    assert body["setup_year"] == 2019
    assert body["layout_type"] == "mirror"
    assert body["holdset_version"] == "2019"
    assert body["is_adjustable"] is False
    # raw_json round-trips into properties
    assert body["properties"]["gym_name"] == body["gym_name"]


async def test_boards_nearby_attaches_distance(client: AsyncClient):
    r = await client.get(
        "/api/v1/boards",
        params={"lat": 51.5, "lon": -0.1, "radius_km": 500},
    )
    assert r.status_code == 200
    for b in r.json()["boards"]:
        assert "distance_km" in b
        assert b["distance_km"] >= 0
    # Sorted by distance ascending
    distances = [b["distance_km"] for b in r.json()["boards"]]
    assert distances == sorted(distances)


async def test_boards_reload_is_idempotent(client: AsyncClient):
    first = await client.get("/api/v1/boards")
    before = first.json()["count"]
    r = await client.post(
        "/api/v1/boards/reload",
        headers={"X-Boards-Reload-Secret": "reload-secret"},
    )
    assert r.status_code == 200
    body = r.json()
    assert body["total"] == before
    assert body["loaded"] == before  # upserting the same features


async def test_boards_reload_requires_secret(client: AsyncClient):
    missing = await client.post("/api/v1/boards/reload")
    assert missing.status_code == 401

    bad = await client.post(
        "/api/v1/boards/reload",
        headers={"X-Boards-Reload-Secret": "wrong"},
    )
    assert bad.status_code == 403


async def test_boards_404_for_unknown(client: AsyncClient):
    r = await client.get("/api/v1/boards/does-not-exist")
    assert r.status_code == 404


# Sanity: data file is valid JSON
def test_sample_data_file_is_valid_geojson():
    from importlib import resources

    raw = (
        resources.files("kt.boards.data")
        .joinpath("sample_locations.geojson")
        .read_text()
    )
    data = json.loads(raw)
    assert data["type"] == "FeatureCollection"
    assert len(data["features"]) > 3
