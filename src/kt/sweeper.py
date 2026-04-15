"""Background task: end idle sessions and drop their credentials."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from kt.db import db
from kt.logging import log


async def sweep_once(idle_max_hours: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=idle_max_hours)).isoformat()
    async with db().execute(
        "SELECT code FROM sessions WHERE ended_at IS NULL AND updated_at < ?",
        (cutoff,),
    ) as cur:
        rows = await cur.fetchall()
    if not rows:
        return 0
    now = datetime.now(timezone.utc).isoformat()
    codes = [r[0] for r in rows]
    for code in codes:
        await db().execute(
            "UPDATE sessions SET ended_at=?, updated_at=? WHERE code=?",
            (now, now, code),
        )
        await db().execute("DELETE FROM host_credentials WHERE session_code=?", (code,))
        await db().execute("DELETE FROM ws_tokens WHERE session_code=?", (code,))
    await db().commit()
    log().info("sweep.ended_idle_sessions", count=len(codes))
    return len(codes)


async def run_forever(idle_max_hours: int, interval_seconds: int) -> None:
    while True:
        try:
            await sweep_once(idle_max_hours)
        except asyncio.CancelledError:
            raise
        except Exception as e:
            log().error("sweep.failed", error=str(e))
        await asyncio.sleep(interval_seconds)
