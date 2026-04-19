from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta
from typing import Any

from kt.db import db


class ClimbsCacheRepo:
    async def get(self, provider: str, cache_key: str) -> Any | None:
        entry = await self.get_with_meta(provider, cache_key, allow_stale=False)
        return entry["payload"] if entry else None

    async def get_with_meta(
        self,
        provider: str,
        cache_key: str,
        *,
        allow_stale: bool = False,
    ) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        if allow_stale:
            sql = """
            SELECT payload_json, created_at, expires_at FROM climbs_cache
            WHERE provider=? AND cache_key=?
            """
            args: tuple[Any, ...] = (provider, cache_key)
        else:
            sql = """
            SELECT payload_json, created_at, expires_at FROM climbs_cache
            WHERE provider=? AND cache_key=? AND expires_at > ?
            """
            args = (provider, cache_key, now)
        async with db().execute(sql, args) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        stale = str(row["expires_at"]) <= now
        return {
            "payload": json.loads(row["payload_json"]),
            "created_at": row["created_at"],
            "expires_at": row["expires_at"],
            "stale": stale,
        }

    async def put(
        self,
        provider: str,
        cache_key: str,
        payload: Any,
        ttl_seconds: int,
    ) -> None:
        now = datetime.now(UTC)
        await db().execute(
            """
            INSERT INTO climbs_cache(provider, cache_key, payload_json, created_at, expires_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(provider, cache_key) DO UPDATE SET
                payload_json = excluded.payload_json,
                created_at = excluded.created_at,
                expires_at = excluded.expires_at
            """,
            (
                provider,
                cache_key,
                json.dumps(payload),
                now.isoformat(),
                (now + timedelta(seconds=ttl_seconds)).isoformat(),
            ),
        )
        await db().commit()

    async def delete_expired(self) -> int:
        now = datetime.now(UTC).isoformat()
        cur = await db().execute("DELETE FROM climbs_cache WHERE expires_at <= ?", (now,))
        await db().commit()
        return cur.rowcount
