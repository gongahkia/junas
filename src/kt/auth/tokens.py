from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta
from hashlib import sha256


def new_token() -> str:
    return secrets.token_urlsafe(32)


def token_hash(raw: str) -> str:
    return sha256(raw.encode()).hexdigest()


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def expires_at(seconds: int) -> str:
    return (datetime.now(UTC) + timedelta(seconds=seconds)).isoformat()
