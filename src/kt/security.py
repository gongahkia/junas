from __future__ import annotations

import json
import secrets
from hashlib import sha256
from typing import Any

from cryptography.fernet import Fernet, InvalidToken


class CredentialCipher:
    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("KT_CRED_KEY is required")
        self._fernet = Fernet(key.encode() if isinstance(key, str) else key)

    def encrypt(self, payload: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(payload).encode()).decode()

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        try:
            raw = self._fernet.decrypt(ciphertext.encode())
        except InvalidToken as e:
            raise ValueError("invalid ciphertext") from e
        return json.loads(raw)


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_secret(secret: str) -> str:
    return sha256(secret.encode()).hexdigest()


def verify_secret(secret: str, expected_hash: str) -> bool:
    return secrets.compare_digest(hash_secret(secret), expected_hash)
