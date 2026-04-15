from __future__ import annotations

from typing import Any

import httpx

from kt.providers.base import ProviderAuthError, ProviderUnavailable


class MoonboardScraper:
    """Thin wrapper over moonboard.com. Exact endpoints vary by site iteration;
    treat this as an integration surface that can be swapped in tests."""

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
            timeout=20.0,
            transport=self._transport,
            headers={"User-Agent": "kilter-together/2.0"},
        )

    async def login(self, username: str, password: str) -> str:
        if not username or not password:
            raise ProviderAuthError("username and password required")
        async with self._client() as c:
            r = await c.post(
                "/account/login",
                data={"Login.Username": username, "Login.Password": password},
                follow_redirects=False,
            )
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            cookie = r.cookies.get(".ASPXAUTH") or r.cookies.get("ASP.NET_SessionId")
            if not cookie:
                raise ProviderAuthError("login did not yield session cookie")
            return cookie

    async def list_problems(
        self,
        session_cookie: str,
        layout_id: str,
        text: str | None,
        limit: int,
        offset: int,
    ) -> list[dict[str, Any]]:
        async with self._client() as c:
            r = await c.get(
                "/problems/v3/list",
                params={
                    "layout": layout_id,
                    "q": text or "",
                    "take": limit,
                    "skip": offset,
                },
                cookies={".ASPXAUTH": session_cookie},
            )
            if r.status_code in (401, 403):
                raise ProviderAuthError("session rejected")
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            r.raise_for_status()
            payload = r.json()
            data = payload.get("Data") if isinstance(payload, dict) else None
            if isinstance(data, list):
                return data
            if isinstance(payload, list):
                return payload
            return []
