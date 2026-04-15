"""Crux Climbing API client.

Docs: https://docs.cruxapp.ca/api-documentation/api-reference
Base: https://www.cruxapp.ca/api/v1
Auth: Bearer token from a user's settings → API Authentication.

Note: docs label some endpoints "Public" but live probes return 401 without a
Bearer token, so we treat all GETs as requiring credentials.
"""

from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from kt.providers.base import ProviderAuthError, ProviderUnavailable

BASE_URL = "https://www.cruxapp.ca/api/v1"

_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=0.05, max=0.2),
    retry=retry_if_exception_type(ProviderUnavailable),
    reraise=True,
)


class CruxClient:
    def __init__(
        self,
        base_url: str = BASE_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self.base_url = base_url
        self._transport = transport

    def _client(self, token: str) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=20.0,
            transport=self._transport,
            headers={
                "Authorization": f"Bearer {token}",
                "Accept": "application/json",
                "User-Agent": "kilter-together/2.0",
            },
        )

    @_retry
    async def get(self, token: str, path: str, params: dict[str, Any] | None = None) -> Any:
        async with self._client(token) as c:
            r = await c.get(path, params=params or {})
            if r.status_code == 401:
                raise ProviderAuthError("token rejected")
            if r.status_code == 404:
                raise KeyError(path)
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            r.raise_for_status()
            return r.json()

    async def get_gym(self, token: str, gym_slug: str) -> dict[str, Any]:
        return await self.get(token, f"/gyms/{gym_slug}")

    async def get_me(self, token: str) -> dict[str, Any]:
        return await self.get(token, "/users/me")

    async def list_walls(self, token: str, gym_slug: str) -> list[dict[str, Any]]:
        data = await self.get(token, f"/gyms/{gym_slug}/gym_walls")
        return _as_list(data)

    async def list_official_climbs(
        self, token: str, gym_slug: str
    ) -> list[dict[str, Any]]:
        data = await self.get(token, f"/gyms/{gym_slug}/climbs/official")
        return _as_list(data)

    async def list_custom_climbs(
        self, token: str, gym_slug: str
    ) -> list[dict[str, Any]]:
        data = await self.get(token, f"/gyms/{gym_slug}/climbs/custom")
        return _as_list(data)

    async def get_climb(self, token: str, climb_id: str) -> dict[str, Any]:
        return await self.get(token, f"/climbs/{climb_id}")


def _as_list(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in ("data", "climbs", "results", "items"):
            v = payload.get(key)
            if isinstance(v, list):
                return v
    return []
