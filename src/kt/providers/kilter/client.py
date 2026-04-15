"""Post-2026-03 Kilter client.

Endpoints documented at lemeryfertitta/BoardLib#78 (open as of April 2026):

  Keycloak:    https://idp.kiltergrips.com/realms/kilter/protocol/openid-connect/token
  REST API:    https://portal.kiltergrips.com/api
  PowerSync:   https://sync1.kiltergrips.com

Status: Keycloak password grant is wired but requires the mobile-app `client_id`
which has not been published. Until the host supplies one (via
KT_KILTER_CLIENT_ID env or the credentials payload), authentication will fail
fast. Data fetch over PowerSync is not implemented — use of climb listing still
returns ProviderUnavailable.
"""

from __future__ import annotations

import os

import httpx

from kt.providers.base import (
    ProviderAuthError,
    ProviderUnavailable,
)

KEYCLOAK_TOKEN_URL = (
    "https://idp.kiltergrips.com/realms/kilter/protocol/openid-connect/token"
)
PORTAL_API_BASE = "https://portal.kiltergrips.com/api"
POWERSYNC_BASE = "https://sync1.kiltergrips.com"


class KilterClient:
    def __init__(
        self,
        client_id: str | None = None,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._client_id = client_id or os.environ.get("KT_KILTER_CLIENT_ID") or ""
        self._transport = transport

    async def login(self, username: str, password: str, client_id: str | None = None) -> str:
        cid = client_id or self._client_id
        if not cid:
            raise ProviderAuthError(
                "kilter client_id not configured; set KT_KILTER_CLIENT_ID or pass "
                "credentials.client_id (the mobile-app client_id is not yet public)"
            )
        if not username or not password:
            raise ProviderAuthError("username and password required")
        async with httpx.AsyncClient(timeout=15.0, transport=self._transport) as c:
            r = await c.post(
                KEYCLOAK_TOKEN_URL,
                data={
                    "grant_type": "password",
                    "client_id": cid,
                    "username": username,
                    "password": password,
                    "scope": "openid",
                },
            )
            if r.status_code in (400, 401, 403):
                raise ProviderAuthError(f"keycloak rejected: {r.text[:200]}")
            if r.status_code >= 500:
                raise ProviderUnavailable(f"keycloak {r.status_code}")
            r.raise_for_status()
            data = r.json()
            token = data.get("access_token")
            if not token:
                raise ProviderAuthError("keycloak returned no access_token")
            return token
