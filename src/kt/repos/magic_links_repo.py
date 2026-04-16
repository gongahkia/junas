from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kt.db import db


class MagicLinksRepo:
    async def put(
        self,
        token_hash: str,
        email: str,
        purpose: str,
        ttl_seconds: int,
    ) -> None:
        from datetime import timedelta

        now = datetime.now(UTC)
        await db().execute(
            """INSERT OR REPLACE INTO magic_links(token_hash, email, purpose, created_at, expires_at)
               VALUES (?,?,?,?,?)""",
            (
                token_hash,
                email.strip().lower(),
                purpose,
                now.isoformat(),
                (now + timedelta(seconds=ttl_seconds)).isoformat(),
            ),
        )
        await db().commit()

    async def consume(self, token_hash: str) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        async with db().execute(
            """SELECT token_hash, email, purpose, expires_at, used_at
               FROM magic_links WHERE token_hash=?""",
            (token_hash,),
        ) as cur:
            row = await cur.fetchone()
        if not row or row["used_at"] is not None or row["expires_at"] < now:
            return None
        await db().execute(
            "UPDATE magic_links SET used_at=? WHERE token_hash=?", (now, token_hash)
        )
        await db().commit()
        return {"email": row["email"], "purpose": row["purpose"]}

    async def delete_expired(self) -> int:
        now = datetime.now(UTC).isoformat()
        cur = await db().execute(
            "DELETE FROM magic_links WHERE expires_at <= ? OR used_at IS NOT NULL",
            (now,),
        )
        await db().commit()
        return cur.rowcount
