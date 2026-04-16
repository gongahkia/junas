from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from kt.db import db


class SessionEventsRepo:
    async def append(
        self, session_code: str, type_: str, payload: dict[str, Any]
    ) -> int:
        now = datetime.now(UTC).isoformat()
        async with db().execute(
            "SELECT COALESCE(MAX(seq), 0) FROM session_events WHERE session_code=?",
            (session_code,),
        ) as cur:
            row = await cur.fetchone()
        seq = int(row[0]) + 1 if row else 1
        await db().execute(
            """INSERT INTO session_events(session_code, seq, type, payload_json, created_at)
               VALUES (?,?,?,?,?)""",
            (session_code, seq, type_, json.dumps(payload), now),
        )
        await db().commit()
        return seq

    async def list_since(
        self, session_code: str, since_seq: int, limit: int = 500
    ) -> list[dict[str, Any]]:
        async with db().execute(
            """SELECT seq, type, payload_json, created_at
               FROM session_events
               WHERE session_code=? AND seq > ?
               ORDER BY seq ASC
               LIMIT ?""",
            (session_code, since_seq, limit),
        ) as cur:
            rows = await cur.fetchall()
        return [
            {
                "seq": row["seq"],
                "type": row["type"],
                "payload": json.loads(row["payload_json"]),
                "created_at": row["created_at"],
            }
            for row in rows
        ]

    async def latest_seq(self, session_code: str) -> int:
        async with db().execute(
            "SELECT COALESCE(MAX(seq), 0) FROM session_events WHERE session_code=?",
            (session_code,),
        ) as cur:
            row = await cur.fetchone()
        return int(row[0]) if row else 0

    async def delete_for(self, session_code: str) -> int:
        cur = await db().execute(
            "DELETE FROM session_events WHERE session_code=?", (session_code,)
        )
        await db().commit()
        return cur.rowcount
