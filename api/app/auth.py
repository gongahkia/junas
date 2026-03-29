from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def hash_password(password: str) -> str:
    return hashlib.sha256(password.encode("utf-8")).hexdigest()


def verify_password(password: str, password_hash: str) -> bool:
    return hash_password(password) == password_hash


def generate_id(prefix: str) -> str:
    return f"{prefix}_{secrets.token_hex(8)}"


def generate_session_token() -> str:
    return secrets.token_urlsafe(32)
