from __future__ import annotations

import httpx
import pytest

from kt.providers.base import (
    AuthToken,
    ClimbQuery,
    ProviderAuthError,
    ProviderStatus,
    ProviderUnavailable,
)
from kt.providers.crux.client import CruxClient
from kt.providers.crux.provider import CruxProvider


def _mock(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


def test_provider_metadata():
    p = CruxProvider()
    assert p.key == "crux"
    assert p.status is ProviderStatus.OK
    assert p.requires_credentials


async def test_authenticate_requires_token():
    p = CruxProvider(client=CruxClient())
    with pytest.raises(ProviderAuthError):
        await p.authenticate({})


async def test_authenticate_validates_gym_slug():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/gyms/known":
            assert req.headers["authorization"] == "Bearer tok"
            return httpx.Response(200, json={"id": 1, "slug": "known", "name": "Known Gym"})
        return httpx.Response(404, json={"error": "not_found"})

    client = CruxClient(transport=_mock(h))
    p = CruxProvider(client=client)
    tok = await p.authenticate({"token": "tok", "gym_slug": "known"})
    assert tok.value == "tok"
    assert tok.extras["gym_slug"] == "known"

    with pytest.raises(ProviderAuthError):
        await p.authenticate({"token": "tok", "gym_slug": "nope"})


async def test_search_combines_official_and_custom():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/gyms/g/climbs/official":
            return httpx.Response(200, json=[
                {"id": 1, "name": "Off-One", "grade": "V3", "angle": 35, "number_of_sends": 12},
            ])
        if req.url.path == "/api/v1/gyms/g/climbs/custom":
            return httpx.Response(200, json=[
                {"id": 2, "name": "Custom-Two", "grade": "V5", "angle": 35, "number_of_sends": 1},
            ])
        return httpx.Response(404)

    client = CruxClient(transport=_mock(h))
    p = CruxProvider(client=client)
    out = await p.search_climbs(
        AuthToken("crux", "tok", extras={"gym_slug": "g"}), ClimbQuery(limit=10)
    )
    assert {c.id for c in out} == {"1", "2"}
    assert out[0].provider == "crux"


async def test_search_filters_by_text_and_angle():
    def h(req: httpx.Request) -> httpx.Response:
        rows = [
            {"id": 1, "name": "Slabby", "angle": 20, "grade": "V2"},
            {"id": 2, "name": "Overhang", "angle": 40, "grade": "V5"},
            {"id": 3, "name": "Slab Project", "angle": 40, "grade": "V6"},
        ]
        return httpx.Response(200, json=rows if "official" in req.url.path else [])

    client = CruxClient(transport=_mock(h))
    p = CruxProvider(client=client)
    out = await p.search_climbs(
        AuthToken("crux", "tok", extras={"gym_slug": "g"}),
        ClimbQuery(text="slab", angle=40, limit=10),
    )
    assert [c.id for c in out] == ["3"]


async def test_search_requires_layout_or_gym_slug():
    p = CruxProvider(client=CruxClient(transport=_mock(lambda r: httpx.Response(200, json=[]))))
    with pytest.raises(ProviderAuthError):
        await p.search_climbs(AuthToken("crux", "tok", extras={}), ClimbQuery(limit=10))


async def test_5xx_unavailable():
    def h(req): return httpx.Response(503)
    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(
            AuthToken("crux", "tok", extras={"gym_slug": "g"}), ClimbQuery()
        )


async def test_unauthorized_is_auth_error():
    def h(req): return httpx.Response(401, json={"error": "Unauthorized"})
    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    with pytest.raises(ProviderAuthError):
        await p.search_climbs(
            AuthToken("crux", "tok", extras={"gym_slug": "g"}), ClimbQuery()
        )


async def test_list_walls():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/gyms/g/gym_walls":
            return httpx.Response(200, json=[
                {"id": 7, "name": "Cave", "angle_adjustable": True, "minimum_angle": 30, "maximum_angle": 50},
                {"id": 8, "name": "Slab", "angle_adjustable": False},
            ])
        return httpx.Response(404)

    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    layouts = await p.list_layouts(AuthToken("crux", "tok", extras={"gym_slug": "g"}))
    assert [layout.id for layout in layouts] == ["7", "8"]
    assert layouts[0].angles == [30, 35, 40, 45, 50]
    assert layouts[1].angles == []
