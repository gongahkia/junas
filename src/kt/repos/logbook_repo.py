from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from kt.db import db
from kt.grades import parse_to_v

ALLOWED_RESULTS = {"sent", "flash", "onsight", "attempted", "project", "repeat"}


class LogbookRepo:
    async def add(
        self,
        user_id: str,
        provider: str,
        climb_id: str,
        result: str,
        name: str | None = None,
        session_code: str | None = None,
        grade_at_send: str | None = None,
        attempts: int | None = None,
        rpe: int | None = None,
        duration_seconds: int | None = None,
        angle: int | None = None,
        notes: str | None = None,
        climbed_at: str | None = None,
    ) -> dict[str, Any]:
        if result not in ALLOWED_RESULTS:
            raise ValueError(f"invalid result; expected one of {sorted(ALLOWED_RESULTS)}")
        if rpe is not None and not (1 <= rpe <= 10):
            raise ValueError("rpe must be in [1, 10]")
        if attempts is not None and attempts < 0:
            raise ValueError("attempts must be >= 0")
        eid = secrets.token_urlsafe(9)
        now = datetime.now(UTC).isoformat()
        grade_v = parse_to_v(grade_at_send) if grade_at_send else None
        await db().execute(
            """INSERT INTO logbook_entries(id, user_id, provider, climb_id, name,
                    session_code, grade_at_send, grade_v_at_send, result, attempts,
                    rpe, duration_seconds, angle, notes, climbed_at, created_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
            (
                eid, user_id, provider, climb_id, name, session_code,
                grade_at_send, grade_v, result, attempts, rpe,
                duration_seconds, angle, notes, climbed_at or now, now,
            ),
        )
        await db().commit()
        return await self.get(eid)  # type: ignore[return-value]

    async def get(self, entry_id: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT id, user_id, provider, climb_id, name, session_code,
                      grade_at_send, grade_v_at_send, result, attempts, rpe,
                      duration_seconds, angle, notes, climbed_at, created_at
               FROM logbook_entries WHERE id=?""",
            (entry_id,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def list_for_user(
        self,
        user_id: str,
        limit: int = 50,
        before: str | None = None,
        provider: str | None = None,
    ) -> list[dict[str, Any]]:
        sql = [
            """SELECT id, user_id, provider, climb_id, name, session_code,
                      grade_at_send, grade_v_at_send, result, attempts, rpe,
                      duration_seconds, angle, notes, climbed_at, created_at
               FROM logbook_entries
               WHERE user_id=?"""
        ]
        args: list[Any] = [user_id]
        if provider:
            sql.append("AND provider=?")
            args.append(provider)
        if before:
            sql.append("AND climbed_at < ?")
            args.append(before)
        sql.append("ORDER BY climbed_at DESC LIMIT ?")
        args.append(limit)
        async with db().execute(" ".join(sql), args) as cur:
            rows = await cur.fetchall()
        return [dict(r) for r in rows]

    async def delete(self, user_id: str, entry_id: str) -> bool:
        cur = await db().execute(
            "DELETE FROM logbook_entries WHERE user_id=? AND id=?",
            (user_id, entry_id),
        )
        await db().commit()
        return cur.rowcount > 0

    async def count_for_user(self, user_id: str) -> int:
        async with db().execute(
            "SELECT COUNT(*) FROM logbook_entries WHERE user_id=?", (user_id,)
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0
