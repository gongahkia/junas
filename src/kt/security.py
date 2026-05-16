from __future__ import annotations

import json
import secrets
from hashlib import sha256
from typing import Any

from cryptography.fernet import Fernet, InvalidToken, MultiFernet


class CredentialCipher:
    """Symmetric cipher for host-supplied provider credentials.

    Key input is either a single Fernet key or a comma-separated list
    (primary first) — the latter enables zero-downtime rotation via
    MultiFernet: any listed key can decrypt, but only the primary encrypts.
    """

    def __init__(self, key: str) -> None:
        if not key:
            raise ValueError("KT_CRED_KEY is required")
        keys = [k.strip() for k in key.split(",") if k.strip()]
        if not keys:
            raise ValueError("KT_CRED_KEY is required")
        fernets = [Fernet(k.encode() if isinstance(k, str) else k) for k in keys]
        self._fernet: Fernet | MultiFernet
        self._fernet = fernets[0] if len(fernets) == 1 else MultiFernet(fernets)

    def encrypt(self, payload: dict[str, Any]) -> str:
        return self._fernet.encrypt(json.dumps(payload).encode()).decode()

    def decrypt(self, ciphertext: str) -> dict[str, Any]:
        try:
            raw = self._fernet.decrypt(ciphertext.encode())
        except InvalidToken as e:
            raise ValueError("invalid ciphertext") from e
        return json.loads(raw)

    def rewrap(self, ciphertext: str) -> str:
        """Re-encrypt with the current primary key (MultiFernet rotate)."""
        if isinstance(self._fernet, MultiFernet):
            return self._fernet.rotate(ciphertext.encode()).decode()
        return ciphertext


def new_secret(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def hash_secret(secret: str) -> str:
    return sha256(secret.encode()).hexdigest()


def verify_secret(secret: str, expected_hash: str) -> bool:
    return secrets.compare_digest(hash_secret(secret), expected_hash)
