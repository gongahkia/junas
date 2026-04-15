from __future__ import annotations

from typing import Any

from kt.providers.aurora.client import AuroraClient
from kt.providers.base import (
    AuthToken,
    Climb,
    ClimbQuery,
    Layout,
    ProviderAuthError,
    ProviderStatus,
)

AURORA_BOARDS: dict[str, str] = {
    "tension": "Tension Board",
    "grasshopper": "Grasshopper Board",
    "decoy": "Decoy Board",
    "soill": "So iLL Board",
    "touchstone": "Touchstone Board",
    "aurora": "Aurora Board",
}


class AuroraProvider:
    status = ProviderStatus.OK
    requires_credentials = True

    def __init__(
        self, key: str, name: str, client: AuroraClient | None = None
    ) -> None:
        self.key = key
        self.name = name
        self._client = client or AuroraClient(key)

    async def authenticate(self, creds: dict[str, Any]) -> AuthToken:
        username = creds.get("username")
        password = creds.get("password")
        if not username or not password:
            raise ProviderAuthError("username and password required")
        token = await self._client.login(username, password)
        return AuthToken(provider=self.key, value=token)

    async def list_layouts(self, token: AuthToken | None) -> list[Layout]:
        if token is None:
            raise ProviderAuthError("auth required")
        raw = await self._client.list_layouts(token.value)
        return [
            Layout(
                id=str(item.get("id")),
                name=str(item.get("name", "")),
                angles=list(item.get("angles") or []),
            )
            for item in raw
        ]

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        if token is None:
            raise ProviderAuthError("auth required")
        raw = await self._client.sync_climbs(token.value, layout_id=query.layout_id)
        climbs = [_to_climb(self.key, c) for c in raw]
        if query.text:
            t = query.text.lower()
            climbs = [c for c in climbs if t in c.name.lower()]
        if query.angle is not None:
            climbs = [c for c in climbs if c.angle == query.angle]
        return climbs[query.offset : query.offset + query.limit]

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        results = await self.search_climbs(token, ClimbQuery(limit=10_000))
        for c in results:
            if c.id == climb_id:
                return c
        raise KeyError(climb_id)


def _to_climb(provider: str, raw: dict[str, Any]) -> Climb:
    return Climb(
        id=str(raw.get("uuid") or raw.get("id")),
        provider=provider,
        name=str(raw.get("name", "")),
        setter=raw.get("setter_username") or raw.get("setter"),
        grade=raw.get("grade") or raw.get("difficulty"),
        angle=raw.get("angle"),
        ascents=raw.get("ascensionist_count"),
        holds=list(raw.get("frames") or raw.get("holds") or []),
        extras={k: v for k, v in raw.items() if k not in {"uuid", "id", "name"}},
    )
