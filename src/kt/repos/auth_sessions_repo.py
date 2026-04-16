from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

from kt.db import db


class AuthSessionsRepo:
    async def create(
        self,
        user_id: str,
        access_hash: str,
        refresh_hash: str,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
    ) -> str:
        from datetime import timedelta

        sid = secrets.token_urlsafe(12)
        now = datetime.now(UTC)
        await db().execute(
            """INSERT INTO auth_sessions(id, user_id, access_hash, refresh_hash,
                    created_at, access_expires_at, refresh_expires_at)
               VALUES (?,?,?,?,?,?,?)""",
            (
                sid,
                user_id,
                access_hash,
                refresh_hash,
                now.isoformat(),
                (now + timedelta(seconds=access_ttl_seconds)).isoformat(),
                (now + timedelta(seconds=refresh_ttl_seconds)).isoformat(),
            ),
        )
        await db().commit()
        return sid

    async def get_by_access_hash(self, access_hash: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT id, user_id, access_hash, refresh_hash, created_at,
                      access_expires_at, refresh_expires_at, revoked_at
               FROM auth_sessions WHERE access_hash=?""",
            (access_hash,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_by_refresh_hash(self, refresh_hash: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT id, user_id, access_hash, refresh_hash, created_at,
                      access_expires_at, refresh_expires_at, revoked_at
               FROM auth_sessions WHERE refresh_hash=?""",
            (refresh_hash,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def revoke(self, sid: str) -> None:
        await db().execute(
            "UPDATE auth_sessions SET revoked_at=? WHERE id=?",
            (datetime.now(UTC).isoformat(), sid),
        )
        await db().commit()

    async def rotate(
        self,
        sid: str,
        access_hash: str,
        refresh_hash: str,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
    ) -> None:
        from datetime import timedelta

        now = datetime.now(UTC)
        await db().execute(
            """UPDATE auth_sessions
               SET access_hash=?, refresh_hash=?, access_expires_at=?, refresh_expires_at=?
               WHERE id=? AND revoked_at IS NULL""",
            (
                access_hash,
                refresh_hash,
                (now + timedelta(seconds=access_ttl_seconds)).isoformat(),
                (now + timedelta(seconds=refresh_ttl_seconds)).isoformat(),
                sid,
            ),
        )
        await db().commit()
