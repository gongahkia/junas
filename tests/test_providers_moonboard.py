from __future__ import annotations

import httpx
import pytest

from kt.providers.base import (
    AuthToken,
    ClimbQuery,
    ProviderAuthError,
    ProviderUnavailable,
)
from kt.providers.moonboard.provider import MoonboardProvider
from kt.providers.moonboard.scraper import MoonboardScraper


def _mock(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def test_login_returns_cookie():
    def h(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/account/login"
        return httpx.Response(302, headers={"set-cookie": ".ASPXAUTH=cookie123; Path=/"})

    s = MoonboardScraper(transport=_mock(h))
    p = MoonboardProvider(scraper=s)
    tok = await p.authenticate({"username": "u", "password": "p"})
    assert tok.value == "cookie123"


async def test_login_missing_creds():
    p = MoonboardProvider(scraper=MoonboardScraper())
    with pytest.raises(ProviderAuthError):
        await p.authenticate({})


async def test_search_problems():
    def h(req: httpx.Request) -> httpx.Response:
        assert req.url.path == "/problems/v3/list"
        return httpx.Response(
            200,
            json={
                "Data": [
                    {"id": 1, "name": "P1", "grade": "7A", "ascents": 5},
                    {"id": 2, "name": "P2", "grade": "7B", "ascents": 1},
                ]
            },
        )

    s = MoonboardScraper(transport=_mock(h))
    p = MoonboardProvider(scraper=s)
    out = await p.search_climbs(AuthToken("moonboard", "cookie"), ClimbQuery(text="p", limit=10))
    assert [c.id for c in out] == ["1", "2"]


async def test_search_5xx_unavailable():
    def h(req): return httpx.Response(503, json={})
    s = MoonboardScraper(transport=_mock(h))
    p = MoonboardProvider(scraper=s)
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(AuthToken("moonboard", "c"), ClimbQuery())


async def test_layouts_static():
    p = MoonboardProvider(scraper=MoonboardScraper())
    layouts = await p.list_layouts(AuthToken("moonboard", "c"))
    assert {l.id for l in layouts} == {"2016", "2019", "2024"}
