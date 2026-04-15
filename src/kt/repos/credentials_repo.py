from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from kt.db import db
from kt.security import CredentialCipher


class CredentialsRepo:
    def __init__(self, cipher: CredentialCipher) -> None:
        self._cipher = cipher

    async def put(self, session_code: str, provider: str, creds: dict[str, Any]) -> None:
        ciphertext = self._cipher.encrypt(creds)
        now = datetime.now(UTC).isoformat()
        await db().execute(
            """
            INSERT INTO host_credentials(session_code, provider, ciphertext, created_at)
            VALUES (?, ?, ?, ?)
            ON CONFLICT(session_code, provider) DO UPDATE SET
                ciphertext = excluded.ciphertext,
                created_at = excluded.created_at
            """,
            (session_code, provider, ciphertext, now),
        )
        await db().commit()

    async def get(self, session_code: str, provider: str) -> dict[str, Any] | None:
        async with db().execute(
            "SELECT ciphertext FROM host_credentials WHERE session_code=? AND provider=?",
            (session_code, provider),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        return self._cipher.decrypt(row[0])

    async def list_providers(self, session_code: str) -> list[str]:
        async with db().execute(
            "SELECT provider FROM host_credentials WHERE session_code=?",
            (session_code,),
        ) as cur:
            return [r[0] async for r in cur]

    async def delete_all(self, session_code: str) -> None:
        await db().execute(
            "DELETE FROM host_credentials WHERE session_code=?", (session_code,)
        )
        await db().commit()
