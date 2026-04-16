from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kt.db import db


class ClimbVotesRepo:
    async def upsert(
        self,
        session_code: str,
        participant_id: str,
        provider: str,
        climb_id: str,
        quality: float | None = None,
        grade_v: int | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        # Merge: only the supplied dimension is updated; the other keeps its prior value.
        async with db().execute(
            """SELECT quality, grade_v FROM climb_votes
               WHERE session_code=? AND participant_id=? AND provider=? AND climb_id=?""",
            (session_code, participant_id, provider, climb_id),
        ) as cur:
            row = await cur.fetchone()
        prev_quality = row["quality"] if row else None
        prev_grade_v = row["grade_v"] if row else None
        new_quality = quality if quality is not None else prev_quality
        new_grade_v = grade_v if grade_v is not None else prev_grade_v
        await db().execute(
            """INSERT INTO climb_votes(session_code, participant_id, provider, climb_id,
                    quality, grade_v, created_at, updated_at)
               VALUES (?,?,?,?,?,?,?,?)
               ON CONFLICT(session_code, participant_id, provider, climb_id) DO UPDATE SET
                    quality=excluded.quality,
                    grade_v=excluded.grade_v,
                    updated_at=excluded.updated_at""",
            (
                session_code, participant_id, provider, climb_id,
                new_quality, new_grade_v, now, now,
            ),
        )
        await db().commit()

    async def consensus(
        self, session_code: str, provider: str, climb_id: str
    ) -> dict[str, Any]:
        async with db().execute(
            """SELECT participant_id, quality, grade_v
               FROM climb_votes
               WHERE session_code=? AND provider=? AND climb_id=?""",
            (session_code, provider, climb_id),
        ) as cur:
            rows = list(await cur.fetchall())
        qualities = [r["quality"] for r in rows if r["quality"] is not None]
        grades = [r["grade_v"] for r in rows if r["grade_v"] is not None]
        return {
            "vote_count": len(rows),
            "quality_avg": (sum(qualities) / len(qualities)) if qualities else None,
            "quality_count": len(qualities),
            "grade_v_avg": (sum(grades) / len(grades)) if grades else None,
            "grade_v_count": len(grades),
            "grade_v_distribution": {
                v: grades.count(v) for v in sorted(set(grades))
            },
        }

    async def delete_for_session(self, session_code: str) -> int:
        cur = await db().execute(
            "DELETE FROM climb_votes WHERE session_code=?",
            (session_code,),
        )
        await db().commit()
        return cur.rowcount
