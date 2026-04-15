"""MoonboardCatalogProvider — read-only static catalog, no auth required.

Backed by the MIT-licensed lucien1011/MoonBoard-Route dataset bundled at
src/kt/providers/moonboard/data/. Useful for sessions where the host wants a
queueable problem pool without a MoonBoard account, and complements the
authenticated `moonboard` provider (which only exposes the host's own
logbook)."""

from __future__ import annotations

from typing import Any

from kt.providers.base import (
    AuthToken,
    Climb,
    ClimbQuery,
    Layout,
    ProviderStatus,
)
from kt.providers.moonboard import static_catalog


class MoonboardCatalogProvider:
    key = "moonboard_catalog"
    name = "MoonBoard (catalog)"
    status = ProviderStatus.OK
    requires_credentials = False

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        # No auth needed; return a token-shaped sentinel.
        return AuthToken(provider=self.key, value="public")

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        return [Layout(id=l, name=f"MoonBoard {l}") for l in static_catalog.supported_layouts()]

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        layout = query.layout_id or "benchmarks"
        rows = static_catalog.search(
            layout=layout,
            text=query.text,
            grade=query.grade_min,
            limit=query.limit,
            offset=query.offset,
        )
        return [_to_climb(r) for r in rows]

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        for layout in static_catalog.supported_layouts():
            rec = static_catalog.get(layout, climb_id)
            if rec:
                return _to_climb(rec)
        raise KeyError(climb_id)


def _to_climb(rec: dict[str, Any]) -> Climb:
    return Climb(
        id=rec["id"],
        provider="moonboard_catalog",
        name=rec["name"],
        setter=rec.get("setter"),
        grade=rec["grade"],
        angle=None,
        ascents=rec.get("repeats"),
        holds=list(rec["holds"]),
        extras={
            "layout": rec["layout"],
            "user_rating": rec.get("user_rating"),
            "mb_type": rec.get("mb_type"),
            "start_holds": rec.get("start_holds") or [],
            "mid_holds": rec.get("mid_holds") or [],
            "end_holds": rec.get("end_holds") or [],
        },
    )
