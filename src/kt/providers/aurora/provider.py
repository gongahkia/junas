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
        rows = await self._client.fetch_table(token.value, "layouts")
        return [
            Layout(
                id=str(r.get("id")),
                name=str(r.get("name", "")),
                angles=list(r.get("angles") or []),
            )
            for r in rows
        ]

    async def search_climbs(
        self, token: AuthToken | None, query: ClimbQuery
    ) -> list[Climb]:
        if token is None:
            raise ProviderAuthError("auth required")
        rows = await self._client.fetch_table(token.value, "climbs")
        if query.layout_id:
            rows = [r for r in rows if str(r.get("layout_id")) == str(query.layout_id)]
        if query.angle is not None:
            rows = [r for r in rows if r.get("angle") == query.angle]
        if query.text:
            t = query.text.lower()
            rows = [r for r in rows if t in str(r.get("name", "")).lower()]
        rows = rows[query.offset : query.offset + query.limit]
        return [_to_climb(self.key, r) for r in rows]

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        if token is None:
            raise ProviderAuthError("auth required")
        rows = await self._client.fetch_table(token.value, "climbs")
        for r in rows:
            if str(r.get("uuid") or r.get("id")) == climb_id:
                return _to_climb(self.key, r)
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
