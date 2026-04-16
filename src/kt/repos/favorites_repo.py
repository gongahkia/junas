from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kt.db import db


class FavoritesRepo:
    async def add(
        self,
        user_id: str,
        provider: str,
        climb_id: str,
        list_name: str = "favorites",
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        async with db().execute(
            """SELECT COALESCE(MAX(position), -1) FROM favorites
               WHERE user_id=? AND list=?""",
            (user_id, list_name),
        ) as cur:
            row = await cur.fetchone()
        next_pos = int(row[0]) + 1 if row else 0
        await db().execute(
            """INSERT OR REPLACE INTO favorites(user_id, provider, climb_id, list, position, added_at)
               VALUES (?,?,?,?,?,?)""",
            (user_id, provider, climb_id, list_name, next_pos, now),
        )
        await db().commit()
        return {
            "user_id": user_id,
            "provider": provider,
            "climb_id": climb_id,
            "list": list_name,
            "position": next_pos,
            "added_at": now,
        }

    async def remove(
        self,
        user_id: str,
        provider: str,
        climb_id: str,
        list_name: str = "favorites",
    ) -> bool:
        cur = await db().execute(
            """DELETE FROM favorites
               WHERE user_id=? AND provider=? AND climb_id=? AND list=?""",
            (user_id, provider, climb_id, list_name),
        )
        await db().commit()
        return cur.rowcount > 0

    async def list_for(
        self, user_id: str, list_name: str = "favorites"
    ) -> list[dict[str, Any]]:
        async with db().execute(
            """SELECT provider, climb_id, list, position, added_at
               FROM favorites
               WHERE user_id=? AND list=?
               ORDER BY position ASC, added_at ASC""",
            (user_id, list_name),
        ) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def lists_for(self, user_id: str) -> list[str]:
        async with db().execute(
            "SELECT DISTINCT list FROM favorites WHERE user_id=?",
            (user_id,),
        ) as cur:
            rows = await cur.fetchall()
        return [row["list"] for row in rows]
