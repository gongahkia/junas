from __future__ import annotations

import json

import httpx
import pytest

from kt.providers.aurora.client import AURORA_HOSTS, AuroraClient
from kt.providers.aurora.provider import AURORA_BOARDS, AuroraProvider
from kt.providers.base import (
    AuthToken,
    ClimbQuery,
    ProviderAuthError,
    ProviderUnavailable,
)


def _mock(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


@pytest.mark.parametrize("key", list(AURORA_BOARDS.keys()))
def test_all_aurora_keys_in_hosts(key):
    assert key in AURORA_HOSTS


async def test_login_success_extracts_session():
    captured: dict = {}

    def h(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/sessions"
        captured["body"] = json.loads(req.content)
        captured["ua"] = req.headers.get("user-agent")
        return httpx.Response(200, json={"session": "tok123", "user": {}})

    p = AuroraProvider("tension", "Tension", client=AuroraClient("tension", transport=_mock(h)))
    tok = await p.authenticate({"username": "a", "password": "b"})
    assert tok.value == "tok123"
    assert captured["body"]["tou"] == "accepted"
    assert captured["body"]["pp"] == "accepted"
    assert captured["body"]["ua"] == "app"
    assert "Kilter" in captured["ua"]


async def test_login_422_is_auth_error():
    def h(req): return httpx.Response(422, json={"error": "bad"})
    p = AuroraProvider("tension", "Tension", client=AuroraClient("tension", transport=_mock(h)))
    with pytest.raises(ProviderAuthError):
        await p.authenticate({"username": "a", "password": "b"})


async def test_login_missing_creds():
    p = AuroraProvider("tension", "Tension", client=AuroraClient("tension"))
    with pytest.raises(ProviderAuthError):
        await p.authenticate({})


async def test_search_climbs_paginates_via_complete_flag():
    pages = [
        {
            "_complete": False,
            "climbs": [{"uuid": "1", "name": "Alpha", "angle": 40}],
            "shared_syncs": [{"table_name": "climbs", "last_synchronized_at": "2026-01-01"}],
        },
        {
            "_complete": True,
            "climbs": [{"uuid": "2", "name": "Beta", "angle": 50}],
        },
    ]
    call_count = {"n": 0}

    def h(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/sync"
        assert req.headers["content-type"] == "application/x-www-form-urlencoded"
        page = pages[call_count["n"]]
        call_count["n"] += 1
        return httpx.Response(200, json=page)

    p = AuroraProvider(
        "tension", "Tension", client=AuroraClient("tension", transport=_mock(h))
    )
    out = await p.search_climbs(AuthToken("tension", "tok"), ClimbQuery(limit=10))
    assert [c.id for c in out] == ["1", "2"]
    assert call_count["n"] == 2


async def test_search_climbs_filters():
    page = {
        "_complete": True,
        "climbs": [
            {"uuid": "1", "name": "Alpha", "angle": 40},
            {"uuid": "2", "name": "Beta", "angle": 50},
            {"uuid": "3", "name": "Alpha-2", "angle": 40},
        ],
    }

    def h(req): return httpx.Response(200, json=page)

    p = AuroraProvider(
        "tension", "Tension", client=AuroraClient("tension", transport=_mock(h))
    )
    out = await p.search_climbs(
        AuthToken("tension", "tok"), ClimbQuery(text="alpha", angle=40, limit=10)
    )
    assert [c.id for c in out] == ["1", "3"]


async def test_search_climbs_5xx_unavailable():
    def h(req): return httpx.Response(503)
    p = AuroraProvider(
        "tension", "Tension", client=AuroraClient("tension", transport=_mock(h))
    )
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(AuthToken("tension", "tok"), ClimbQuery())


async def test_list_layouts_via_sync():
    page = {
        "_complete": True,
        "layouts": [
            {"id": 7, "name": "Spray", "angles": [20, 40]},
            {"id": 9, "name": "Home", "angles": [40]},
        ],
    }

    def h(req): return httpx.Response(200, json=page)

    p = AuroraProvider(
        "tension", "Tension", client=AuroraClient("tension", transport=_mock(h))
    )
    layouts = await p.list_layouts(AuthToken("tension", "tok"))
    assert [l.id for l in layouts] == ["7", "9"]
    assert layouts[0].angles == [20, 40]


def test_unknown_board_rejected():
    with pytest.raises(KeyError):
        AuroraClient("nonsense")
