from __future__ import annotations

import asyncio
from typing import Any, Callable

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


class _TableCache:
    """In-memory per-(token, table) cache with delta sync via shared_syncs."""

    def __init__(self) -> None:
        self._rows: dict[tuple[str, str], dict[str, dict[str, Any]]] = {}
        self._sync_dates: dict[tuple[str, str], str] = {}
        self._locks: dict[tuple[str, str], asyncio.Lock] = {}

    def _lock(self, key: tuple[str, str]) -> asyncio.Lock:
        lock = self._locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            self._locks[key] = lock
        return lock

    async def get_rows(
        self,
        client: AuroraClient,
        token: str,
        table: str,
        max_pages: int,
        on_page: Callable[[int, int], None] | None = None,
    ) -> list[dict[str, Any]]:
        key = (token, table)
        async with self._lock(key):
            sync_date = self._sync_dates.get(key, "1970-01-01 00:00:00.000000")
            pages = await client.sync(token, {table: sync_date}, max_pages=max_pages)
            store = self._rows.setdefault(key, {})
            latest = sync_date
            for i, page in enumerate(pages, 1):
                chunk = page.get(table) or (page.get("PUT") or {}).get(table) or []
                for row in chunk:
                    rid = str(row.get("uuid") or row.get("id") or row.get("name"))
                    store[rid] = row
                for ss in page.get("shared_syncs", []) or []:
                    if ss.get("table_name") == table and ss.get("last_synchronized_at"):
                        latest = ss["last_synchronized_at"]
                if on_page is not None:
                    on_page(i, len(store))
            self._sync_dates[key] = latest
            return list(store.values())


class AuroraProvider:
    status = ProviderStatus.OK
    requires_credentials = True

    def __init__(
        self,
        key: str,
        name: str,
        client: AuroraClient | None = None,
        max_sync_pages: int = 100,
    ) -> None:
        self.key = key
        self.name = name
        self._client = client or AuroraClient(key)
        self._cache = _TableCache()
        self._max_sync_pages = max_sync_pages

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
        rows = await self._cache.get_rows(
            self._client, token.value, "layouts", self._max_sync_pages
        )
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
        rows = await self._cache.get_rows(
            self._client, token.value, "climbs", self._max_sync_pages
        )
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
        rows = await self._cache.get_rows(
            self._client, token.value, "climbs", self._max_sync_pages
        )
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
