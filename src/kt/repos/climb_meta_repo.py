from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from kt.db import db


class ClimbMetaRepo:
    async def upsert(
        self,
        provider: str,
        climb_id: str,
        grade_raw: str | None,
        grade_v: int | None,
        stars: float | None,
        ascents: int | None,
        tags: list[str] | None = None,
        media: list[dict[str, Any]] | None = None,
        setter: dict[str, Any] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        await db().execute(
            """INSERT INTO climb_meta(provider, climb_id, grade_raw, grade_v,
                    stars, ascents, tags_json, media_json, setter_json, updated_at)
               VALUES (?,?,?,?,?,?,?,?,?,?)
               ON CONFLICT(provider, climb_id) DO UPDATE SET
                    grade_raw=excluded.grade_raw,
                    grade_v=excluded.grade_v,
                    stars=excluded.stars,
                    ascents=excluded.ascents,
                    tags_json=excluded.tags_json,
                    media_json=excluded.media_json,
                    setter_json=excluded.setter_json,
                    updated_at=excluded.updated_at""",
            (
                provider,
                climb_id,
                grade_raw,
                grade_v,
                stars,
                ascents,
                json.dumps(tags or []),
                json.dumps(media or []),
                json.dumps(setter) if setter else None,
                now,
            ),
        )
        await db().commit()

    async def get(self, provider: str, climb_id: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT provider, climb_id, grade_raw, grade_v, stars, ascents,
                      tags_json, media_json, setter_json, updated_at
               FROM climb_meta WHERE provider=? AND climb_id=?""",
            (provider, climb_id),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return _unpack(dict(row))

    async def bulk_get(
        self, provider: str, climb_ids: list[str]
    ) -> dict[str, dict[str, Any]]:
        if not climb_ids:
            return {}
        placeholders = ",".join("?" * len(climb_ids))
        async with db().execute(
            f"""SELECT provider, climb_id, grade_raw, grade_v, stars, ascents,
                       tags_json, media_json, setter_json, updated_at
                FROM climb_meta
                WHERE provider=? AND climb_id IN ({placeholders})""",
            (provider, *climb_ids),
        ) as cur:
            rows = await cur.fetchall()
        return {row["climb_id"]: _unpack(dict(row)) for row in rows}


def _unpack(row: dict[str, Any]) -> dict[str, Any]:
    row["tags"] = json.loads(row.pop("tags_json") or "[]")
    row["media"] = json.loads(row.pop("media_json") or "[]")
    setter_json = row.pop("setter_json")
    row["setter"] = json.loads(setter_json) if setter_json else None
    return row
