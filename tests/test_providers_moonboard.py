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

_LOGIN_HTML = """
<html><body>
  <form action="/Account/Login" method="post">
    <input name="__RequestVerificationToken" type="hidden" value="form-token-xyz" />
    <input name="Login.Username" />
    <input name="Login.Password" />
  </form>
</body></html>
"""


def _mock(handler) -> httpx.MockTransport:
    return httpx.MockTransport(handler)


async def test_login_full_flow():
    state = {"got_post": False}

    def h(req: httpx.Request) -> httpx.Response:
        if req.method == "GET" and req.url.path == "/Account/Login":
            return httpx.Response(
                200, text=_LOGIN_HTML,
                headers={"set-cookie": "__RequestVerificationToken=cookie-tok; Path=/"},
            )
        if req.method == "POST" and req.url.path == "/Account/Login":
            body = req.content.decode()
            assert "__RequestVerificationToken=form-token-xyz" in body
            assert "Login.Username=test-user" in body
            assert "Login.Password=test-pass-not-real" in body
            state["got_post"] = True
            return httpx.Response(
                302,
                headers=[
                    ("set-cookie", "_MoonBoard=auth-cookie-abc; Path=/; HttpOnly"),
                    ("location", "/Dashboard/Index"),
                ],
            )
        if req.method == "GET" and req.url.path == "/Dashboard/Index":
            return httpx.Response(200, text="ok")
        return httpx.Response(404)

    s = MoonboardScraper(transport=_mock(h))
    cookie = await s.login("test-user", "test-pass-not-real")
    assert cookie == "auth-cookie-abc"
    assert state["got_post"]


async def test_login_no_cookie_means_auth_error():
    def h(req: httpx.Request) -> httpx.Response:
        if req.method == "GET":
            return httpx.Response(200, text=_LOGIN_HTML)
        # bad creds → returns 200 with error markup but no _MoonBoard cookie
        return httpx.Response(200, text="<div class='field-validation-error'>bad</div>")

    s = MoonboardScraper(transport=_mock(h))
    with pytest.raises(ProviderAuthError):
        await s.login("a", "b")


async def test_login_missing_creds():
    p = MoonboardProvider(scraper=MoonboardScraper())
    with pytest.raises(ProviderAuthError):
        await p.authenticate({})


async def test_list_logbook_kendo_shape():
    def h(req: httpx.Request) -> httpx.Response:
        assert req.method == "POST"
        assert req.url.path == "/Logbook/GetLogbook"
        assert req.headers["content-type"] == "application/x-www-form-urlencoded"
        body = req.content.decode()
        assert "page=1" in body and "pageSize=20" in body
        return httpx.Response(
            200,
            json={
                "Data": [
                    {"Id": 1, "Name": "Crimpfest", "Grade": "7A", "Repeats": 12},
                    {"Id": 2, "Name": "Slopey", "Grade": "7B", "Repeats": 3},
                ],
                "Total": 2,
                "Errors": None,
            },
        )

    s = MoonboardScraper(transport=_mock(h))
    p = MoonboardProvider(scraper=s)
    out = await p.search_climbs(AuthToken("moonboard", "cookie"), ClimbQuery(limit=20))
    assert [c.id for c in out] == ["1", "2"]
    assert out[0].name == "Crimpfest"
    assert out[0].grade == "7A"
    assert out[0].ascents == 12


async def test_search_5xx_unavailable():
    def h(req): return httpx.Response(503, json={})
    s = MoonboardScraper(transport=_mock(h))
    p = MoonboardProvider(scraper=s)
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(AuthToken("moonboard", "c"), ClimbQuery())


async def test_layouts_static():
    p = MoonboardProvider(scraper=MoonboardScraper())
    layouts = await p.list_layouts(AuthToken("moonboard", "c"))
    assert {layout.id for layout in layouts} == {"2016", "2019", "2024"}


async def test_logbook_schema_drift_raises_unavailable():
    def h(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"Rows": []})

    s = MoonboardScraper(transport=_mock(h))
    p = MoonboardProvider(scraper=s)
    with pytest.raises(ProviderUnavailable):
        await p.search_climbs(AuthToken("moonboard", "c"), ClimbQuery(limit=5))
