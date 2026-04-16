from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kt.auth.tokens import expires_at as _expires_at
from kt.auth.tokens import new_token, token_hash
from kt.config import Settings
from kt.repos.auth_sessions_repo import AuthSessionsRepo
from kt.repos.users_repo import UsersRepo


class AuthService:
    def __init__(
        self,
        settings: Settings,
        users: UsersRepo | None = None,
        auth_sessions: AuthSessionsRepo | None = None,
    ) -> None:
        self.settings = settings
        self.users = users or UsersRepo()
        self.auth_sessions = auth_sessions or AuthSessionsRepo()

    async def issue_tokens(self, user_id: str) -> dict[str, Any]:
        access = new_token()
        refresh = new_token()
        await self.auth_sessions.create(
            user_id=user_id,
            access_hash=token_hash(access),
            refresh_hash=token_hash(refresh),
            access_ttl_seconds=self.settings.auth_access_ttl_seconds,
            refresh_ttl_seconds=self.settings.auth_refresh_ttl_seconds,
        )
        await self.users.touch_login(user_id)
        return {
            "access_token": access,
            "refresh_token": refresh,
            "access_expires_at": _expires_at(self.settings.auth_access_ttl_seconds),
            "refresh_expires_at": _expires_at(self.settings.auth_refresh_ttl_seconds),
            "user_id": user_id,
        }

    async def user_by_access(self, access_token: str) -> dict[str, Any] | None:
        row = await self.auth_sessions.get_by_access_hash(token_hash(access_token))
        if not row or row["revoked_at"]:
            return None
        if row["access_expires_at"] < datetime.now(UTC).isoformat():
            return None
        return await self.users.get(row["user_id"])

    async def rotate(self, refresh_token: str) -> dict[str, Any] | None:
        row = await self.auth_sessions.get_by_refresh_hash(token_hash(refresh_token))
        if not row or row["revoked_at"]:
            return None
        if row["refresh_expires_at"] < datetime.now(UTC).isoformat():
            return None
        new_access = new_token()
        new_refresh = new_token()
        await self.auth_sessions.rotate(
            sid=row["id"],
            access_hash=token_hash(new_access),
            refresh_hash=token_hash(new_refresh),
            access_ttl_seconds=self.settings.auth_access_ttl_seconds,
            refresh_ttl_seconds=self.settings.auth_refresh_ttl_seconds,
        )
        return {
            "access_token": new_access,
            "refresh_token": new_refresh,
            "access_expires_at": _expires_at(self.settings.auth_access_ttl_seconds),
            "refresh_expires_at": _expires_at(self.settings.auth_refresh_ttl_seconds),
            "user_id": row["user_id"],
        }

    async def logout(self, refresh_token: str) -> bool:
        row = await self.auth_sessions.get_by_refresh_hash(token_hash(refresh_token))
        if not row or row["revoked_at"]:
            return False
        await self.auth_sessions.revoke(row["id"])
        return True
