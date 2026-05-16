from __future__ import annotations

import asyncio
from collections.abc import Callable
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


_PK_BY_TABLE: dict[str, tuple[str, ...]] = {
    "climbs": ("uuid",),
    "layouts": ("id",),
    "climb_stats": ("climb_uuid", "angle"),
    "ascents": ("uuid",),
    "products": ("id",),
    "users": ("id",),
}


def _row_key(table: str, row: dict[str, Any]) -> str:
    pk = _PK_BY_TABLE.get(table)
    if pk:
        return "|".join(str(row.get(k)) for k in pk)
    return str(row.get("uuid") or row.get("id") or id(row))


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
                    store[_row_key(table, row)] = row
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
    source = "upstream_api"
    capabilities = {
        "list_layouts": True,
        "search_climbs": True,
        "get_climb": True,
        "live_data": True,
    }

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
        climbs_rows, stats_by_uuid = await self._climbs_and_stats(token.value)

        if query.layout_id:
            climbs_rows = [
                r for r in climbs_rows if str(r.get("layout_id")) == str(query.layout_id)
            ]
        if query.text:
            t = query.text.lower()
            climbs_rows = [r for r in climbs_rows if t in str(r.get("name", "")).lower()]

        materialized: list[Climb] = []
        for c in climbs_rows:
            uuid = str(c.get("uuid") or c.get("id"))
            stats_list = stats_by_uuid.get(uuid, [])
            if query.angle is not None:
                stats_list = [s for s in stats_list if s.get("angle") == query.angle]
            if not stats_list:
                if query.angle is not None:
                    continue
                materialized.append(_to_climb(self.key, c, None))
            else:
                # Pick the most-ascended stats row to represent the climb
                best = max(stats_list, key=lambda s: s.get("ascensionist_count") or 0)
                materialized.append(_to_climb(self.key, c, best))

        return materialized[query.offset : query.offset + query.limit]

    async def get_climb(self, token: AuthToken | None, climb_id: str) -> Climb:
        if token is None:
            raise ProviderAuthError("auth required")
        climbs_rows, stats_by_uuid = await self._climbs_and_stats(token.value)
        for r in climbs_rows:
            if str(r.get("uuid") or r.get("id")) == climb_id:
                stats_list = stats_by_uuid.get(climb_id, [])
                stats = max(stats_list, key=lambda s: s.get("ascensionist_count") or 0) if stats_list else None
                return _to_climb(self.key, r, stats)
        raise KeyError(climb_id)

    async def _climbs_and_stats(
        self, token: str
    ) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
        climbs = await self._cache.get_rows(
            self._client, token, "climbs", self._max_sync_pages
        )
        stats = await self._cache.get_rows(
            self._client, token, "climb_stats", self._max_sync_pages
        )
        index: dict[str, list[dict[str, Any]]] = {}
        for s in stats:
            uuid = s.get("climb_uuid")
            if not uuid:
                continue
            index.setdefault(str(uuid), []).append(s)
        return climbs, index


def _to_climb(provider: str, raw: dict[str, Any], stats: dict[str, Any] | None) -> Climb:
    grade: str | None = None
    angle: int | None = None
    ascents: int | None = None
    if stats:
        difficulty = stats.get("difficulty_average")
        if difficulty is not None:
            grade = str(difficulty)
        angle = stats.get("angle")
        ascents = stats.get("ascensionist_count")
    return Climb(
        id=str(raw.get("uuid") or raw.get("id")),
        provider=provider,
        name=str(raw.get("name", "")),
        setter=raw.get("setter_username") or raw.get("setter"),
        grade=grade,
        angle=angle,
        ascents=ascents,
        holds=list(raw.get("frames") or raw.get("holds") or []),
        extras={k: v for k, v in raw.items() if k not in {"uuid", "id", "name"}},
    )
