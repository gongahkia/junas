from __future__ import annotations

from typing import Any

from kt.providers.base import (
    AuthToken,
    Climb,
    ClimbQuery,
    Layout,
    ProviderStatus,
    ProviderUnavailable,
)


class KilterProvider:
    """Experimental Kilter provider.

    Auth is wired against the new Keycloak realm (idp.kiltergrips.com) and will
    succeed if the host supplies a valid `client_id`. Data fetch is not yet
    implemented because the new app uses PowerSync, not a REST API.

    Tracking lemeryfertitta/BoardLib#78 — flip to OK status and implement
    list_layouts/search_climbs once a PowerSync client lands."""

    key = "kilter"
    name = "Kilter Board"
    status = ProviderStatus.EXPERIMENTAL
    requires_credentials = True

    def __init__(self, client: Any = None) -> None:
        from kt.providers.kilter.client import KilterClient

        self._client = client or KilterClient()

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        token = await self._client.login(
            creds.get("username", ""),
            creds.get("password", ""),
            client_id=creds.get("client_id"),
        )
        return AuthToken(provider=self.key, value=token)

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        raise ProviderUnavailable(
            "kilter data fetch requires PowerSync; not yet implemented"
        )

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        raise ProviderUnavailable(
            "kilter data fetch requires PowerSync; not yet implemented"
        )

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        raise ProviderUnavailable(
            "kilter data fetch requires PowerSync; not yet implemented"
        )
