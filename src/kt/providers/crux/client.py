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
        try:
            async with self._client(token) as c:
                r = await c.get(path, params=params or {})
        except httpx.TimeoutException as e:
            raise ProviderUnavailable("upstream timeout") from e
        except httpx.RequestError as e:
            raise ProviderUnavailable(f"network error: {type(e).__name__}") from e
        if r.status_code == 401:
            raise ProviderAuthError("token rejected")
        if r.status_code == 404:
            raise KeyError(path)
        if r.status_code >= 500:
            raise ProviderUnavailable(f"upstream {r.status_code}")
        r.raise_for_status()
        return _json_payload(r, context=f"crux GET {path}")

    async def get_gym(self, token: str, gym_slug: str) -> dict[str, Any]:
        return await self.get(token, f"/gyms/{gym_slug}")

    async def get_me(self, token: str) -> dict[str, Any]:
        return await self.get(token, "/users/me")

    async def list_walls(self, token: str, gym_slug: str) -> list[dict[str, Any]]:
        data = await self.get(token, f"/gyms/{gym_slug}/gym_walls")
        return _as_list(data, context="crux gym_walls")

    async def list_official_climbs(
        self, token: str, gym_slug: str
    ) -> list[dict[str, Any]]:
        data = await self.get(token, f"/gyms/{gym_slug}/climbs/official")
        return _as_list(data, context="crux official climbs")

    async def list_custom_climbs(
        self, token: str, gym_slug: str
    ) -> list[dict[str, Any]]:
        data = await self.get(token, f"/gyms/{gym_slug}/climbs/custom")
        return _as_list(data, context="crux custom climbs")

    async def get_climb(self, token: str, climb_id: str) -> dict[str, Any]:
        return await self.get(token, f"/climbs/{climb_id}")


def _json_payload(response: httpx.Response, *, context: str) -> Any:
    try:
        payload = response.json()
    except ValueError as e:
        raise ProviderUnavailable(f"upstream_schema_drift: invalid json in {context}") from e
    if not isinstance(payload, (dict, list)):
        raise ProviderUnavailable(f"upstream_schema_drift: unexpected payload type in {context}")
    return payload


def _as_list(payload: Any, *, context: str) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        if not all(isinstance(item, dict) for item in payload):
            raise ProviderUnavailable(f"upstream_schema_drift: non-object row in {context}")
        return payload
    if isinstance(payload, dict):
        for key in ("data", "climbs", "results", "items"):
            v = payload.get(key)
            if isinstance(v, list):
                if not all(isinstance(item, dict) for item in v):
                    raise ProviderUnavailable(f"upstream_schema_drift: non-object row in {context}")
                return v
    raise ProviderUnavailable(f"upstream_schema_drift: no list field found in {context}")
