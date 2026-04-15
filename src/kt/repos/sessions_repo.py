from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from kt.db import db


class SessionsRepo:
    async def create(
        self,
        code: str,
        host_participant_id: str,
        host_secret_hash: str,
        provider: str,
        state: dict[str, Any],
        enabled_providers: list[str] | None = None,
    ) -> None:
        now = datetime.now(UTC).isoformat()
        enabled = enabled_providers or [provider]
        await db().execute(
            """
            INSERT INTO sessions(code, host_participant_id, host_secret_hash,
                enabled_providers, state_json, created_at, updated_at)
            VALUES (?,?,?,?,?,?,?)
            """,
            (
                code,
                host_participant_id,
                host_secret_hash,
                json.dumps(enabled),
                json.dumps(state),
                now,
                now,
            ),
        )
        await db().commit()

    async def get(self, code: str) -> dict[str, Any] | None:
        async with db().execute(
            """SELECT code, host_participant_id, host_secret_hash, enabled_providers,
                      state_json, created_at, updated_at, ended_at
               FROM sessions WHERE code=?""",
            (code,),
        ) as cur:
            row = await cur.fetchone()
        if not row:
            return None
        enabled_providers = _parse_enabled_providers(row["enabled_providers"])
        provider = enabled_providers[0] if enabled_providers else ""
        return {
            "code": row["code"],
            "host_participant_id": row["host_participant_id"],
            "host_secret_hash": row["host_secret_hash"],
            "provider": provider,
            "enabled_providers": enabled_providers,
            "state": json.loads(row["state_json"]),
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
            "ended_at": row["ended_at"],
        }

    async def save_state(self, code: str, state: dict[str, Any]) -> None:
        now = datetime.now(UTC).isoformat()
        enabled_providers = state.get("enabled_providers")
        if isinstance(enabled_providers, list):
            await db().execute(
                "UPDATE sessions SET enabled_providers=?, state_json=?, updated_at=? WHERE code=?",
                (json.dumps(enabled_providers), json.dumps(state), now, code),
            )
            await db().commit()
            return
        await db().execute(
            "UPDATE sessions SET state_json=?, updated_at=? WHERE code=?",
            (json.dumps(state), now, code),
        )
        await db().commit()

    async def end(self, code: str) -> None:
        now = datetime.now(UTC).isoformat()
        await db().execute(
            "UPDATE sessions SET ended_at=?, updated_at=? WHERE code=?",
            (now, now, code),
        )
        await db().commit()

    async def put_ws_token(
        self, token: str, session_code: str, participant_id: str, ttl_seconds: int
    ) -> None:
        from datetime import timedelta

        now = datetime.now(UTC)
        await db().execute(
            """INSERT INTO ws_tokens(token, session_code, participant_id, created_at, expires_at)
               VALUES (?,?,?,?,?)""",
            (
                token,
                session_code,
                participant_id,
                now.isoformat(),
                (now + timedelta(seconds=ttl_seconds)).isoformat(),
            ),
        )
        await db().commit()

    async def consume_ws_token(self, token: str) -> dict[str, Any] | None:
        now = datetime.now(UTC).isoformat()
        async with db().execute(
            """SELECT token, session_code, participant_id, expires_at, used_at
               FROM ws_tokens WHERE token=?""",
            (token,),
        ) as cur:
            row = await cur.fetchone()
        if not row or row["used_at"] is not None or row["expires_at"] < now:
            return None
        await db().execute("UPDATE ws_tokens SET used_at=? WHERE token=?", (now, token))
        await db().commit()
        return {
            "session_code": row["session_code"],
            "participant_id": row["participant_id"],
        }

    async def delete_expired_ws_tokens(self) -> int:
        now = datetime.now(UTC).isoformat()
        cur = await db().execute(
            "DELETE FROM ws_tokens WHERE expires_at <= ? OR used_at IS NOT NULL",
            (now,),
        )
        await db().commit()
        return cur.rowcount


def _parse_enabled_providers(raw: str) -> list[str]:
    try:
        parsed = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        parsed = raw
    if isinstance(parsed, list):
        return [str(p) for p in parsed if str(p)]
    if isinstance(parsed, str) and parsed:
        return [parsed]
    return []
