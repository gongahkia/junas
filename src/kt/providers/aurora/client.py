from __future__ import annotations

from typing import Any

import httpx
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from kt.providers.base import ProviderAuthError, ProviderUnavailable

_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=0.05, max=0.2),
    retry=retry_if_exception_type(ProviderUnavailable),
    reraise=True,
)

# Aurora-ecosystem hosts (reverse-engineered via lemeryfertitta/BoardLib).
# Subject to change upstream; verify against BoardLib if a board breaks.
AURORA_HOSTS: dict[str, str] = {
    "tension": "https://tensionboardapp2.com",
    "grasshopper": "https://grasshopperboardapp.com",
    "decoy": "https://decoyboardapp.com",
    "soill": "https://soillboardapp.com",
    "touchstone": "https://touchstoneboardapp.com",
    "aurora": "https://auroraboardapp.com",
}


class AuroraClient:
    def __init__(self, board_key: str, transport: httpx.AsyncBaseTransport | None = None) -> None:
        if board_key not in AURORA_HOSTS:
            raise KeyError(f"unknown aurora board: {board_key}")
        self.board_key = board_key
        self.base_url = AURORA_HOSTS[board_key]
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self.base_url,
            timeout=15.0,
            transport=self._transport,
            headers={"User-Agent": "kilter-together/2.0"},
        )

    @_retry
    async def login(self, username: str, password: str) -> str:
        async with self._client() as c:
            r = await c.post("/sessions", json={"username": username, "password": password})
            if r.status_code in (401, 403):
                raise ProviderAuthError("invalid credentials")
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            r.raise_for_status()
            data = r.json()
            token = data.get("token") or data.get("session", {}).get("token")
            if not token:
                raise ProviderAuthError("no token in response")
            return token

    @_retry
    async def sync_climbs(self, token: str, layout_id: str | None = None) -> list[dict[str, Any]]:
        params: dict[str, Any] = {}
        if layout_id is not None:
            params["layout_id"] = layout_id
        async with self._client() as c:
            r = await c.post(
                "/sync",
                headers={"Cookie": f"token={token}"},
                params=params,
                json={"client_subscriptions": [{"table_name": "climbs", "last_synchronized_at": 0}]},
            )
            if r.status_code in (401, 403):
                raise ProviderAuthError("token rejected")
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            r.raise_for_status()
            payload = r.json()
            return payload.get("PUT", {}).get("climbs", []) or []

    @_retry
    async def list_layouts(self, token: str) -> list[dict[str, Any]]:
        async with self._client() as c:
            r = await c.get("/api/v1/layouts", headers={"Cookie": f"token={token}"})
            if r.status_code in (401, 403):
                raise ProviderAuthError("token rejected")
            if r.status_code >= 500:
                raise ProviderUnavailable(f"upstream {r.status_code}")
            r.raise_for_status()
            return r.json() or []
