"""Password hashing with stdlib scrypt.

Stored format: ``scrypt$<N>$<r>$<p>$<salt_b64>$<hash_b64>``.
"""

from __future__ import annotations

import base64
import hashlib
import secrets

_N = 2**14
_R = 8
_P = 1
_KEY_LEN = 32
_SALT_LEN = 16


def hash_password(password: str) -> str:
    if not password or len(password) < 8:
        raise ValueError("password must be >= 8 chars")
    salt = secrets.token_bytes(_SALT_LEN)
    derived = hashlib.scrypt(
        password.encode("utf-8"), salt=salt, n=_N, r=_R, p=_P, dklen=_KEY_LEN
    )
    s = base64.b64encode(salt).decode()
    h = base64.b64encode(derived).decode()
    return f"scrypt${_N}${_R}${_P}${s}${h}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, s, h = stored.split("$", 5)
    except ValueError:
        return False
    if scheme != "scrypt":
        return False
    try:
        salt = base64.b64decode(s)
        expected = base64.b64decode(h)
        derived = hashlib.scrypt(
            password.encode("utf-8"),
            salt=salt,
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(expected),
        )
    except (ValueError, TypeError):
        return False
    return secrets.compare_digest(derived, expected)
