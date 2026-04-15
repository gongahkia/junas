from __future__ import annotations

import json

import httpx
import pytest

from kt.providers.aurora.client import AuroraClient
from kt.providers.aurora.provider import AURORA_BOARDS, AuroraProvider
from kt.providers.base import (
    AuthToken,
    ClimbQuery,
    ProviderAuthError,
    ProviderUnavailable,
)


def _mock(responses: dict[str, httpx.Response]) -> httpx.MockTransport:
    def handler(request: httpx.Request) -> httpx.Response:
        key = f"{request.method} {request.url.path}"
        if key in responses:
            return responses[key]
        return httpx.Response(404, json={"error": "no mock", "key": key})

    return httpx.MockTransport(handler)


@pytest.mark.parametrize("key", list(AURORA_BOARDS.keys()))
def test_all_aurora_keys_in_hosts(key):
    from kt.providers.aurora.client import AURORA_HOSTS
    assert key in AURORA_HOSTS


async def test_login_success():
    transport = _mock({
        "POST /sessions": httpx.Response(200, json={"token": "tok123"}),
    })
    client = AuroraClient("tension", transport=transport)
    p = AuroraProvider("tension", "Tension", client=client)
    token = await p.authenticate({"username": "a", "password": "b"})
    assert token.value == "tok123"
    assert token.provider == "tension"


async def test_login_bad_creds():
    transport = _mock({
        "POST /sessions": httpx.Response(401, json={"error": "bad"}),
    })
    client = AuroraClient("tension", transport=transport)
    p = AuroraProvider("tension", "Tension", client=client)
    with pytest.raises(ProviderAuthError):
        await p.authenticate({"username": "a", "password": "b"})


async def test_login_missing_creds():
    p = AuroraProvider("tension", "Tension", client=AuroraClient("tension"))
    with pytest.raises(ProviderAuthError):
        await p.authenticate({})


async def test_search_climbs_filters_and_paginates():
    raw = [
        {"uuid": "1", "name": "Alpha", "angle": 40, "grade": "V5", "ascensionist_count": 12},
        {"uuid": "2", "name": "Beta", "angle": 50, "grade": "V6", "ascensionist_count": 3},
        {"uuid": "3", "name": "alpha-two", "angle": 40, "grade": "V4", "ascensionist_count": 1},
    ]
    transport = _mock({
        "POST /sync": httpx.Response(200, json={"PUT": {"climbs": raw}}),
    })
    p = AuroraProvider(
        "tension", "Tension", client=AuroraClient("tension", transport=transport)
    )
    token = AuthToken(provider="tension", value="tok")
    out = await p.search_climbs(token, ClimbQuery(text="alpha", angle=40, limit=10))
    assert [c.id for c in out] == ["1", "3"]


async def test_search_climbs_upstream_5xx_raises_unavailable():
    transport = _mock({
        "POST /sync": httpx.Response(503, json={}),
    })
    p = AuroraProvider(
        "tension", "Tension", client=AuroraClient("tension", transport=transport)
    )
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(AuthToken("tension", "tok"), ClimbQuery())


async def test_list_layouts():
    transport = _mock({
        "GET /api/v1/layouts": httpx.Response(
            200, content=json.dumps([{"id": 7, "name": "Spray", "angles": [20, 40]}])
        ),
    })
    p = AuroraProvider(
        "tension", "Tension", client=AuroraClient("tension", transport=transport)
    )
    layouts = await p.list_layouts(AuthToken("tension", "tok"))
    assert layouts[0].id == "7"
    assert layouts[0].angles == [20, 40]


def test_unknown_board_rejected():
    with pytest.raises(KeyError):
        AuroraClient("nonsense")
