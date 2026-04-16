from __future__ import annotations

import secrets
from datetime import UTC, datetime
from typing import Any

import aiosqlite

from kt.db import db

ALLOWED_GRADE_SYSTEMS = {"font", "v", "yds", "uiaa"}


class UsersRepo:
    async def create(
        self,
        email: str | None,
        display_name: str,
        password_hash: str | None,
        grade_system_pref: str = "font",
    ) -> dict[str, Any]:
        if grade_system_pref not in ALLOWED_GRADE_SYSTEMS:
            raise ValueError("invalid grade_system_pref")
        uid = secrets.token_urlsafe(12)
        now = datetime.now(UTC).isoformat()
        norm_email = email.strip().lower() if email else None
        try:
            await db().execute(
                """INSERT INTO users(id, email, display_name, password_hash,
                        grade_system_pref, created_at)
                   VALUES (?,?,?,?,?,?)""",
                (uid, norm_email, display_name, password_hash, grade_system_pref, now),
            )
            await db().commit()
        except aiosqlite.IntegrityError as e:
            raise ValueError("email_taken") from e
        return await self.get(uid)  # type: ignore[return-value]

    async def get(self, uid: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT id, email, display_name, password_hash, grade_system_pref,
                      created_at, last_login_at
               FROM users WHERE id=?""",
            (uid,),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def get_by_email(self, email: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT id, email, display_name, password_hash, grade_system_pref,
                      created_at, last_login_at
               FROM users WHERE email=?""",
            (email.strip().lower(),),
        ) as cur:
            row = await cur.fetchone()
        return dict(row) if row else None

    async def touch_login(self, uid: str) -> None:
        await db().execute(
            "UPDATE users SET last_login_at=? WHERE id=?",
            (datetime.now(UTC).isoformat(), uid),
        )
        await db().commit()

    async def update_profile(
        self,
        uid: str,
        display_name: str | None = None,
        grade_system_pref: str | None = None,
    ) -> dict[str, Any] | None:
        sets = []
        args: list[Any] = []
        if display_name is not None:
            sets.append("display_name=?")
            args.append(display_name)
        if grade_system_pref is not None:
            if grade_system_pref not in ALLOWED_GRADE_SYSTEMS:
                raise ValueError("invalid grade_system_pref")
            sets.append("grade_system_pref=?")
            args.append(grade_system_pref)
        if not sets:
            return await self.get(uid)
        args.append(uid)
        await db().execute(f"UPDATE users SET {', '.join(sets)} WHERE id=?", args)
        await db().commit()
        return await self.get(uid)
