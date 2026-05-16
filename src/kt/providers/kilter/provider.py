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
    """Experimental Kilter v2 provider.

    Auth is wired against the new Keycloak realm (idp.kiltergrips.com) and will
    succeed if the host supplies a valid `client_id`. Data fetch still needs a
    first-party PowerSync integration and is intentionally unavailable here.

    Tracking lemeryfertitta/BoardLib#78 — flip to OK status once a PowerSync
    client lands.

    Legacy SQLite catalog support now lives in `kilter_legacy` provider to
    avoid cross-system mixing and ambiguous behavior.
    """

    key = "kilter"
    name = "Kilter Board (v2)"
    status = ProviderStatus.EXPERIMENTAL
    requires_credentials = True
    source = "powersync_pending"
    capabilities = {
        "list_layouts": False,
        "search_climbs": False,
        "get_climb": False,
        "live_data": False,
    }

    def __init__(
        self,
        client: Any = None,
    ) -> None:
        from kt.providers.kilter.client import KilterClient

        self._client = client or KilterClient()

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        token = await self._client.login(
            creds.get("username", ""),
            creds.get("password", ""),
            client_id=creds.get("client_id"),
        )
        username = str(creds.get("username") or "").strip()
        return AuthToken(provider=self.key, value=token, extras={"username": username})

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        raise ProviderUnavailable("kilter v2 layouts unavailable until PowerSync integration")

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        raise ProviderUnavailable("kilter v2 climbs unavailable until PowerSync integration")

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        raise ProviderUnavailable("kilter v2 climb detail unavailable until PowerSync integration")

    def describe(self) -> dict[str, object]:
        return {
            "capabilities": {
                "list_layouts": False,
                "search_climbs": False,
                "get_climb": False,
                "live_data": False,
            },
            "source": self.source,
            "status_reason": "awaiting PowerSync integration for Kilter v2 data APIs",
            "status_reason_code": "kilter_powersync_pending",
        }
