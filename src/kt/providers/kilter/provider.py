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
from kt.providers.kilter.legacy_catalog import KilterLegacyCatalog


class KilterProvider:
    """Experimental Kilter provider.

    Auth is wired against the new Keycloak realm (idp.kiltergrips.com) and will
    succeed if the host supplies a valid `client_id`. Current first-party data
    fetch still needs PowerSync; meanwhile, a read-only legacy SQLite catalog
    can be supplied through `KT_KILTER_LEGACY_DB_PATH`.

    Tracking lemeryfertitta/BoardLib#78 — flip to OK status once a PowerSync
    client lands."""

    key = "kilter"
    name = "Kilter Board"
    status = ProviderStatus.EXPERIMENTAL
    requires_credentials = True

    def __init__(
        self,
        client: Any = None,
        legacy_catalog: KilterLegacyCatalog | None = None,
    ) -> None:
        from kt.providers.kilter.client import KilterClient

        self._client = client or KilterClient()
        self._legacy_catalog = legacy_catalog or KilterLegacyCatalog.from_env()

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        token = await self._client.login(
            creds.get("username", ""),
            creds.get("password", ""),
            client_id=creds.get("client_id"),
        )
        username = str(creds.get("username") or "").strip()
        return AuthToken(provider=self.key, value=token, extras={"username": username})

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        return self._catalog().list_layouts()

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        return self._catalog().search_climbs(query)

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        board_id = token.extras.get("board_id") if token else None
        angle = token.extras.get("angle") if token else None
        query = ClimbQuery(
            layout_id=str(board_id) if board_id else None,
            angle=int(angle) if angle is not None else None,
        )
        return self._catalog().get_climb(climb_id, query)

    def _catalog(self) -> KilterLegacyCatalog:
        if not self._legacy_catalog.available:
            raise ProviderUnavailable(
                "kilter data fetch requires PowerSync, or set KT_KILTER_LEGACY_DB_PATH "
                "to an extracted legacy SQLite catalog"
            )
        return self._legacy_catalog
