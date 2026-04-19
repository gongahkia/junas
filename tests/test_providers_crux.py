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
        if req.url.path == "/api/v1/users/me":
            assert req.headers["authorization"] == "Bearer tok"
            return httpx.Response(200, json={
                "id": 9,
                "name": "Ada",
                "viewed_gyms": [
                    {"url_slug": "known", "name": "Known Gym"},
                ],
            })
        return httpx.Response(404, json={"error": "not_found"})

    client = CruxClient(transport=_mock(h))
    p = CruxProvider(client=client)
    tok = await p.authenticate({"token": "Bearer tok", "gym_slug": "known"})
    assert tok.value == "tok"
    assert tok.extras["gym_slug"] == "known"
    assert tok.extras["user_id"] == 9

    with pytest.raises(ProviderAuthError):
        await p.authenticate({"token": "tok", "gym_slug": "nope"})


async def test_authenticate_without_default_gym_stores_user_context():
    def h(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/api/v1/users/me"
        return httpx.Response(200, json={"id": 4, "name": "Grace"})

    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    tok = await p.authenticate({"token": "tok"})
    assert tok.extras == {"gym_slug": "", "user_id": 4, "user_name": "Grace"}


async def test_search_combines_official_and_custom():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/gyms/g/climbs/official":
            assert req.url.query == b""
            return httpx.Response(200, json=[
                {"id": 1, "name": "Off-One", "grade": "V3", "angle": 35, "number_of_sends": 12},
            ])
        if req.url.path == "/api/v1/gyms/g/climbs/custom":
            assert req.url.query == b""
            return httpx.Response(200, json=[
                {"id": 2, "name": "Custom-Two", "grade": "V5", "angle": 35, "number_of_sends": 1},
            ])
        return httpx.Response(404)

    client = CruxClient(transport=_mock(h))
    p = CruxProvider(client=client)
    out = await p.search_climbs(
        AuthToken("crux", "tok", extras={"gym_slug": "g"}), ClimbQuery(limit=10)
    )
    assert {c.id for c in out} == {"crux:1", "crux:2"}
    assert out[0].id == "crux:1"
    assert out[0].provider == "crux"


async def test_search_sorts_and_windows_locally():
    def h(req: httpx.Request) -> httpx.Response:
        assert req.url.query == b""
        rows = [
            {"id": "custom-a", "name": "Alpha", "number_of_sends": 3},
            {"id": 2, "name": "Beta", "number_of_sends": 8},
        ]
        if "official" in req.url.path:
            return httpx.Response(200, json=[
                {"id": 1, "name": "Gamma", "number_of_sends": 10},
            ])
        return httpx.Response(200, json=rows)

    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    out = await p.search_climbs(
        AuthToken("crux", "tok", extras={"gym_slug": "g"}),
        ClimbQuery(offset=1, limit=2),
    )
    assert [c.id for c in out] == ["crux:2", "crux:custom-a"]


async def test_search_filters_by_text_and_angle():
    def h(req: httpx.Request) -> httpx.Response:
        rows = [
            {"id": 1, "name": "Slabby", "angle": 20, "grade": "V2"},
            {"id": 2, "name": "Overhang", "angle": 40, "grade": "V5"},
            {"id": 3, "name": "Slab Project", "angle": "40°", "grade": "V6"},
        ]
        return httpx.Response(200, json=rows if "official" in req.url.path else [])

    client = CruxClient(transport=_mock(h))
    p = CruxProvider(client=client)
    out = await p.search_climbs(
        AuthToken("crux", "tok", extras={"gym_slug": "g"}),
        ClimbQuery(text="slab", angle=40, limit=10),
    )
    assert [c.id for c in out] == ["crux:3"]


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
                {
                    "id": 7,
                    "name": "Cave",
                    "angle_adjustable": True,
                    "minimum_angle": 30,
                    "maximum_angle": 50,
                    "image_url": "https://img.example/cave.jpg",
                },
                {"id": 8, "name": "Slab", "angle_adjustable": False},
            ])
        return httpx.Response(404)

    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    layouts = await p.list_layouts(AuthToken("crux", "tok", extras={"gym_slug": "g"}))
    assert [layout.id for layout in layouts] == ["7", "8"]
    assert layouts[0].angles == [30, 35, 40, 45, 50]
    assert layouts[0].extras["kind"] == "wall"
    assert layouts[0].extras["image_url"] == "https://img.example/cave.jpg"
    assert layouts[1].angles == []


async def test_list_layouts_discovers_gyms_without_default_slug():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/users/me":
            return httpx.Response(200, json={
                "administrated_gyms": [
                    {"url_slug": "admin", "name": "Admin Gym", "location": "West"},
                ],
                "viewed_gyms": [
                    {"url_slug": "viewed", "name": "Viewed Gym", "icon_url": "https://img.example/icon.png"},
                    {"url_slug": "admin", "name": "Admin Gym Duplicate"},
                ],
            })
        return httpx.Response(404)

    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    layouts = await p.list_layouts(AuthToken("crux", "tok", extras={}))
    assert [layout.id for layout in layouts] == ["admin", "viewed"]
    assert layouts[0].extras == {
        "kind": "gym",
        "parent_id": "",
        "location": "West",
        "icon_url": None,
    }
    assert layouts[1].extras["icon_url"] == "https://img.example/icon.png"


async def test_get_climb_accepts_prefixed_id_and_maps_detail():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path == "/api/v1/climbs/42":
            return httpx.Response(200, json={
                "id": 42,
                "name": "Compression",
                "grade": "V7",
                "angle": "-20 degrees",
                "setter_name": "Sam",
                "number_of_sends": 5,
                "holds": [{"x": 1, "y": 2}],
                "description": "right hand bump",
                "gym_name": "Crux Gym",
                "image_url": "https://img.example/42.jpg",
            })
        return httpx.Response(404)

    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    climb = await p.get_climb(AuthToken("crux", "tok", extras={"gym_slug": "g"}), "crux:42")
    assert climb.id == "crux:42"
    assert climb.setter == "Sam"
    assert climb.angle == -20
    assert climb.extras["external_id"] == "42"
    assert climb.extras["gym_slug"] == "g"
    assert climb.extras["image_url"] == "https://img.example/42.jpg"


async def test_list_official_schema_drift_raises_unavailable():
    def h(req: httpx.Request) -> httpx.Response:
        if req.url.path.endswith("/official"):
            return httpx.Response(200, json={"unexpected": "shape"})
        if req.url.path.endswith("/custom"):
            return httpx.Response(200, json=[])
        return httpx.Response(200, json={})

    p = CruxProvider(client=CruxClient(transport=_mock(h)))
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(
            AuthToken("crux", "tok", extras={"gym_slug": "g"}),
            ClimbQuery(limit=10),
        )
