from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from kt.db import db


class ClimbNotesRepo:
    async def put(
        self,
        user_id: str,
        provider: str,
        climb_id: str,
        body: str,
        tags: list[str] | None = None,
    ) -> dict[str, Any]:
        now = datetime.now(UTC).isoformat()
        await db().execute(
            """INSERT INTO climb_notes(user_id, provider, climb_id, body, tags_json, updated_at)
               VALUES (?,?,?,?,?,?)
               ON CONFLICT(user_id, provider, climb_id) DO UPDATE SET
                   body=excluded.body,
                   tags_json=excluded.tags_json,
                   updated_at=excluded.updated_at""",
            (user_id, provider, climb_id, body, json.dumps(tags or []), now),
        )
        await db().commit()
        return {
            "user_id": user_id,
            "provider": provider,
            "climb_id": climb_id,
            "body": body,
            "tags": tags or [],
            "updated_at": now,
        }

    async def get(
        self, user_id: str, provider: str, climb_id: str
    ) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT user_id, provider, climb_id, body, tags_json, updated_at
               FROM climb_notes
               WHERE user_id=? AND provider=? AND climb_id=?""",
            (user_id, provider, climb_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        d = dict(row)
        d["tags"] = json.loads(d.pop("tags_json") or "[]")
        return d

    async def delete(self, user_id: str, provider: str, climb_id: str) -> bool:
        cur = await db().execute(
            """DELETE FROM climb_notes
               WHERE user_id=? AND provider=? AND climb_id=?""",
            (user_id, provider, climb_id),
        )
        await db().commit()
        return cur.rowcount > 0

    async def list_for_user(
        self, user_id: str, limit: int = 100
    ) -> list[dict[str, Any]]:
        async with db().execute(
            """SELECT user_id, provider, climb_id, body, tags_json, updated_at
               FROM climb_notes
               WHERE user_id=?
               ORDER BY updated_at DESC LIMIT ?""",
            (user_id, limit),
        ) as cur:
            rows = await cur.fetchall()
        out = []
        for row in rows:
            d = dict(row)
            d["tags"] = json.loads(d.pop("tags_json") or "[]")
            out.append(d)
        return out
