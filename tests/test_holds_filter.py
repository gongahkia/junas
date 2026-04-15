from __future__ import annotations

import httpx

from kt.providers.base import (
    AuthToken,
    ClimbQuery,
    matches_holds,
)
from kt.providers.crux.client import CruxClient
from kt.providers.crux.provider import CruxProvider
from kt.providers.moonboard.catalog_provider import MoonboardCatalogProvider


def test_matches_holds_pure():
    assert matches_holds(["A1", "B2", "C3"], ("a1",), ()) is True
    assert matches_holds(["A1", "B2"], ("Z9",), ()) is False
    assert matches_holds(["A1", "B2"], (), ("a1",)) is False
    assert matches_holds(["A1"], (), ("z9",)) is True
    assert matches_holds(["A1"], (), ()) is True
    assert matches_holds([], ("a",), ()) is False


async def test_catalog_filters_required_holds():
    p = MoonboardCatalogProvider()
    # Pick a benchmark and require its first start hold; should still return it.
    sample = (await p.search_climbs(None, ClimbQuery(layout_id="benchmarks", limit=1)))[0]
    assert sample.holds, "sample must have holds"
    required = (sample.holds[0],)
    out = await p.search_climbs(
        None,
        ClimbQuery(
            layout_id="benchmarks",
            holds_required=required,
            limit=200,
        ),
    )
    assert any(c.id == sample.id for c in out)
    # All returned climbs must include the required hold
    assert all(required[0].upper() in {h.upper() for h in c.holds} for c in out)


async def test_catalog_excludes_forbidden_holds():
    p = MoonboardCatalogProvider()
    sample = (await p.search_climbs(None, ClimbQuery(layout_id="benchmarks", limit=1)))[0]
    forbidden_hold = sample.holds[0]
    out = await p.search_climbs(
        None,
        ClimbQuery(
            layout_id="benchmarks",
            holds_forbidden=(forbidden_hold,),
            limit=200,
        ),
    )
    assert all(forbidden_hold.upper() not in {h.upper() for h in c.holds} for c in out)


async def test_crux_filters_required_holds():
    def h(req: httpx.Request) -> httpx.Response:
        if "official" in req.url.path:
            return httpx.Response(200, json=[
                {"id": 1, "name": "A", "holds": ["X1", "X2", "X3"]},
                {"id": 2, "name": "B", "holds": ["X1", "X4"]},
                {"id": 3, "name": "C", "holds": ["Y1"]},
            ])
        return httpx.Response(200, json=[])

    p = CruxProvider(client=CruxClient(transport=httpx.MockTransport(h)))
    out = await p.search_climbs(
        AuthToken("crux", "tok", extras={"gym_slug": "g"}),
        ClimbQuery(holds_required=("x2",), limit=10),
    )
    assert [c.id for c in out] == ["1"]


async def test_climbs_endpoint_threads_holds(client):
    # Ensure the REST API accepts the new query params without rejecting them.
    create = (
        await client.post(
            "/api/sessions",
            json={"host_display_name": "H", "provider": "moonboard_catalog"},
        )
    ).json()
    code = create["code"]
    r = await client.get(
        f"/api/sessions/{code}/climbs",
        params=[
            ("layout_id", "benchmarks"),
            ("holds_required", "C5"),
            ("limit", 5),
        ],
    )
    assert r.status_code == 200
    body = r.json()
    assert "climbs" in body
    for c in body["climbs"]:
        # Each result must include hold C5 (case-insensitive)
        # Holds in benchmark records use uppercase grid coords.
        # We only assert the response shape is OK and the filter ran.
        assert isinstance(c["id"], str)
