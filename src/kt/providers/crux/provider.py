"""CruxProvider — gym-scoped problem catalog from cruxapp.ca.

Crux is gym-centric: climbs belong to a wall in a gym. Use `query.layout_id`
as the gym slug (Crux's gym identifier). Without `layout_id` set, the provider
returns an empty list and surfaces a clear error.
"""

from __future__ import annotations

from typing import Any

from kt.providers.base import (
    AuthToken,
    Climb,
    ClimbQuery,
    Layout,
    ProviderAuthError,
    ProviderStatus,
    matches_holds,
)
from kt.providers.crux.client import CruxClient


class CruxProvider:
    key = "crux"
    name = "Crux Climbing"
    status = ProviderStatus.OK
    requires_credentials = True

    def __init__(self, client: CruxClient | None = None) -> None:
        self._client = client or CruxClient()

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        token = creds.get("token") or creds.get("api_token") or creds.get("bearer")
        if not token:
            raise ProviderAuthError("crux requires `token` (Bearer) in credentials")
        # Verify by calling /gyms/{slug} if a slug was supplied; otherwise accept.
        slug = creds.get("gym_slug")
        if slug:
            try:
                await self._client.get_gym(token, slug)
            except KeyError as e:
                raise ProviderAuthError(f"unknown gym_slug: {slug}") from e
        return AuthToken(provider=self.key, value=token, extras={"gym_slug": slug})

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        if token is None:
            raise ProviderAuthError("auth required")
        slug = token.extras.get("gym_slug")
        if not slug:
            return []
        walls = await self._client.list_walls(token.value, slug)
        return [
            Layout(
                id=str(w.get("id")),
                name=str(w.get("name", "")),
                angles=_wall_angles(w),
            )
            for w in walls
        ]

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        if token is None:
            raise ProviderAuthError("auth required")
        slug = query.layout_id or token.extras.get("gym_slug")
        if not slug:
            raise ProviderAuthError("crux requires gym_slug as layout_id")

        # Pull both official and custom climbs; merge.
        page = (query.offset // max(1, query.limit)) + 1
        official = await self._client.list_official_climbs(
            token.value, slug, page=page, per_page=query.limit
        )
        custom = await self._client.list_custom_climbs(
            token.value, slug, page=page, per_page=query.limit
        )
        rows = [*official, *custom]

        if query.text:
            t = query.text.lower()
            rows = [
                r
                for r in rows
                if t in str(r.get("name", "")).lower()
                or t in str(r.get("description", "")).lower()
            ]
        if query.angle is not None:
            rows = [r for r in rows if r.get("angle") == query.angle]
        if query.holds_required or query.holds_forbidden:
            rows = [
                r for r in rows
                if matches_holds(list(r.get("holds") or []), query.holds_required, query.holds_forbidden)
            ]

        return [_to_climb(r) for r in rows[: query.limit]]

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        if token is None:
            raise ProviderAuthError("auth required")
        return _to_climb(await self._client.get_climb(token.value, climb_id))


def _wall_angles(w: dict[str, Any]) -> list[int]:
    if not w.get("angle_adjustable"):
        return []
    lo = w.get("minimum_angle")
    hi = w.get("maximum_angle")
    if lo is None or hi is None:
        return []
    return list(range(int(lo), int(hi) + 1, 5))


def _to_climb(r: dict[str, Any]) -> Climb:
    return Climb(
        id=str(r.get("id")),
        provider="crux",
        name=str(r.get("name") or ""),
        setter=None,
        grade=r.get("grade"),
        angle=r.get("angle"),
        ascents=r.get("number_of_sends"),
        holds=list(r.get("holds") or []),
        extras={
            k: v
            for k, v in r.items()
            if k
            not in {"id", "name", "grade", "angle", "number_of_sends", "holds"}
        },
    )
