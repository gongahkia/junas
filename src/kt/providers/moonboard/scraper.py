"""moonboard.com scraper.

The MoonBoard website does NOT expose a public catalog of all community
problems via web — only the user's own logbook is available. The mobile apps
use different infrastructure that is not addressed here.

Auth uses the ASP.NET MVC anti-forgery flow:
  1. GET  /Account/Login → captures `__RequestVerificationToken` cookie + form value.
  2. POST /Account/Login with both → sets `_MoonBoard` auth cookie.

Data:
  * POST /Logbook/GetLogbook (Kendo aspnetmvc-ajax datasource):
      form: page, pageSize, sort, filter
      response: {"Data": [...], "Total": int, "Errors": null}

Verified working April 2026 against moonboard.com.
"""

from __future__ import annotations

import re
from typing import Any
from urllib.parse import urlencode

import httpx

from kt.providers.base import ProviderAuthError, ProviderUnavailable

_BROWSER_UA = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_0) AppleWebKit/605.1.15 "
    "(KHTML, like Gecko) Version/17.0 Safari/605.1.15"
)
_FORM_TOKEN_RE = re.compile(
    r'name="__RequestVerificationToken"\s+type="hidden"\s+value="([^"]+)"'
)


class MoonboardScraper:
    def __init__(
        self,
        base_url: str = "https://moonboard.com",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=30.0,
            transport=self._transport,
            follow_redirects=True,
            headers={
                "User-Agent": _BROWSER_UA,
                "Accept": "text/html,application/xhtml+xml,application/json",
                "Accept-Language": "en-US,en;q=0.9",
            },
        )

    async def login(self, username: str, password: str) -> str:
        if not username or not password:
            raise ProviderAuthError("username and password required")
        try:
            async with self._client() as c:
                r = await c.get("/Account/Login")
                if r.status_code >= 500:
                    raise ProviderUnavailable(f"upstream {r.status_code}")
                m = _FORM_TOKEN_RE.search(r.text)
                if not m:
                    raise ProviderAuthError("could not find anti-forgery token on login page")
                form_token = m.group(1)

                r2 = await c.post(
                    "/Account/Login",
                    data={
                        "__RequestVerificationToken": form_token,
                        "Login.Username": username,
                        "Login.Password": password,
                        "send": "login",
                    },
                    headers={"Referer": f"{self.base_url}/Account/Login"},
                )
                if r2.status_code >= 500:
                    raise ProviderUnavailable(f"upstream {r2.status_code}")
                cookie = c.cookies.get("_MoonBoard")
                if not cookie:
                    # Validation message inline, not always 4xx
                    raise ProviderAuthError("login did not yield _MoonBoard cookie")
                return cookie
        except httpx.TimeoutException as e:
            raise ProviderUnavailable("upstream timeout") from e
        except httpx.RequestError as e:
            raise ProviderUnavailable(f"network error: {type(e).__name__}") from e

    async def list_logbook(
        self,
        session_cookie: str,
        page: int = 1,
        page_size: int = 50,
        sort: str = "",
        filter_expr: str = "",
    ) -> tuple[list[dict[str, Any]], int]:
        body = urlencode({
            "page": page,
            "pageSize": page_size,
            "sort": sort,
            "filter": filter_expr,
        })
        try:
            async with self._client() as c:
                r = await c.post(
                    "/Logbook/GetLogbook",
                    content=body,
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded",
                        "X-Requested-With": "XMLHttpRequest",
                        "Cookie": f"_MoonBoard={session_cookie}",
                    },
                )
        except httpx.TimeoutException as e:
            raise ProviderUnavailable("upstream timeout") from e
        except httpx.RequestError as e:
            raise ProviderUnavailable(f"network error: {type(e).__name__}") from e
        if r.status_code in (401, 403):
            raise ProviderAuthError("session rejected")
        if r.status_code >= 500:
            raise ProviderUnavailable(f"upstream {r.status_code}")
        r.raise_for_status()
        payload = _json_dict(r, context="moonboard logbook")
        if "Data" not in payload or "Total" not in payload:
            raise ProviderUnavailable("upstream_schema_drift: logbook missing Data/Total")
        data = payload.get("Data")
        total = payload.get("Total")
        if not isinstance(data, list):
            raise ProviderUnavailable("upstream_schema_drift: logbook Data is not a list")
        if not isinstance(total, (int, str, bytes)):
            raise ProviderUnavailable("upstream_schema_drift: logbook Total is not numeric")
        try:
            total_int = int(total)
        except (TypeError, ValueError) as e:
            raise ProviderUnavailable("upstream_schema_drift: logbook Total is not numeric") from e
        return data, total_int


def _json_dict(response: httpx.Response, *, context: str) -> dict[str, Any]:
    try:
        payload = response.json()
    except ValueError as e:
        raise ProviderUnavailable(f"upstream_schema_drift: invalid json in {context}") from e
    if not isinstance(payload, dict):
        raise ProviderUnavailable(f"upstream_schema_drift: expected object in {context}")
    return payload
