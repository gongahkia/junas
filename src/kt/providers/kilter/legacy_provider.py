from __future__ import annotations

from typing import Any

from kt.providers.base import (
    AuthToken,
    Climb,
    ClimbQuery,
    Layout,
    ProviderStatus,
)
from kt.providers.kilter.legacy_catalog import KilterLegacyCatalog


class KilterLegacyProvider:
    """Read-only provider backed by extracted legacy SQLite catalogs."""

    key = "kilter_legacy"
    name = "Kilter Board (legacy catalog)"
    status = ProviderStatus.EXPERIMENTAL
    requires_credentials = False
    source = "legacy_catalog"
    capabilities = {
        "list_layouts": False,
        "search_climbs": False,
        "get_climb": False,
        "live_data": False,
    }

    def __init__(
        self,
        legacy_catalog: KilterLegacyCatalog | None = None,
    ) -> None:
        self._legacy_catalog = legacy_catalog or KilterLegacyCatalog.from_env(
            provider_key=self.key
        )

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        # Provider is intentionally no-auth; this exists for interface compliance.
        return AuthToken(provider=self.key, value="legacy")

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        return self._catalog().list_layouts()

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        return self._catalog().search_climbs(query)

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        board_id, _uuid = self._catalog().parse_climb_id(climb_id)
        angle = token.extras.get("angle") if token else None
        query = ClimbQuery(
            layout_id=str(board_id),
            angle=int(angle) if angle is not None else None,
        )
        return self._catalog().get_climb(climb_id, query)

    def _catalog(self) -> KilterLegacyCatalog:
        return self._legacy_catalog

    def describe(self) -> dict[str, object]:
        legacy_available = self._legacy_catalog.available
        return {
            "capabilities": {
                "list_layouts": legacy_available,
                "search_climbs": legacy_available,
                "get_climb": legacy_available,
                "live_data": False,
            },
            "source": self.source if legacy_available else "none",
            "status_reason": (
                "legacy catalog mode; requires KT_KILTER_LEGACY_DB_PATH"
                if not legacy_available
                else "serving data from local legacy catalog"
            ),
            "status_reason_code": (
                "kilter_legacy_catalog_missing" if not legacy_available else "kilter_legacy_catalog_mode"
            ),
        }
