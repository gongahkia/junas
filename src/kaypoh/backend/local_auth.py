"""Local-daemon ACL helpers for the offline desktop SKU."""

from __future__ import annotations

import fnmatch
import base64
import hashlib
import hmac
import json
import os
import secrets
import stat
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

from kaypoh.configs.runtime import LocalDaemonSettings

LOCAL_TOKEN_HEADER = "X-Kaypoh-Local-Token"
LOCAL_CLIENT_TOKEN_AUDIENCE = "kaypoh-local-daemon"
LOCAL_CLIENT_TOKEN_ISSUER = "kaypoh-local"
KEYCHAIN_ACCOUNT = "default"
KEYCHAIN_SERVICE = "kaypoh-local-daemon-token"
DEFAULT_TOKEN_FILE = Path.home() / ".kaypoh" / "local_daemon_token"


class LocalDaemonAuthError(RuntimeError):
    """Raised when a local-daemon token cannot be provisioned safely."""


def origin_allowed(origin: str | None, allowed_origins: tuple[str, ...]) -> bool:
    if not origin:
        return True
    normalized = origin.strip()
    if not normalized:
        return True
    return any(fnmatch.fnmatchcase(normalized, pattern.strip()) for pattern in allowed_origins if pattern.strip())


def _read_keychain_token() -> str:
    find = subprocess.run(
        [
            "security",
            "find-generic-password",
            "-a",
            KEYCHAIN_ACCOUNT,
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if find.returncode == 0 and find.stdout.strip():
        return find.stdout.strip()

    token = secrets.token_urlsafe(32)
    add = subprocess.run(
        [
            "security",
            "add-generic-password",
            "-U",
            "-a",
            KEYCHAIN_ACCOUNT,
            "-s",
            KEYCHAIN_SERVICE,
            "-w",
            token,
        ],
        capture_output=True,
        text=True,
        timeout=5,
        check=False,
    )
    if add.returncode != 0:
        raise LocalDaemonAuthError("macOS Keychain token provision failed")
    return token


def _token_file_path(settings: LocalDaemonSettings) -> Path:
    if settings.token_file:
        return Path(settings.token_file).expanduser()
    return DEFAULT_TOKEN_FILE


def _read_token_file(path: Path) -> str:
    try:
        mode = stat.S_IMODE(path.stat().st_mode)
    except OSError as exc:
        raise LocalDaemonAuthError(f"cannot stat local token file: {path}") from exc
    if mode & 0o077:
        raise LocalDaemonAuthError(f"local token file must not be group/world accessible: {path}")
    try:
        return path.read_text(encoding="utf-8").strip()
    except OSError as exc:
        raise LocalDaemonAuthError(f"cannot read local token file: {path}") from exc


def _write_token_file(path: Path) -> str:
    token = secrets.token_urlsafe(32)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(token + "\n")
    except FileExistsError:
        return _read_token_file(path)
    except OSError as exc:
        raise LocalDaemonAuthError(f"cannot create local token file: {path}") from exc
    return token


def _file_token(settings: LocalDaemonSettings) -> str:
    path = _token_file_path(settings)
    if path.exists():
        token = _read_token_file(path)
        if token:
            return token
    return _write_token_file(path)


def resolve_local_daemon_token(settings: LocalDaemonSettings) -> str:
    if settings.token:
        return settings.token
    if sys.platform == "darwin":
        try:
            return _read_keychain_token()
        except (OSError, subprocess.SubprocessError, LocalDaemonAuthError):
            pass
    return _file_token(settings)


def _b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def _b64url_decode(data: str) -> bytes:
    return base64.urlsafe_b64decode((data + "=" * (-len(data) % 4)).encode("ascii"))


def _json_b64(data: dict[str, Any]) -> str:
    return _b64url(json.dumps(data, separators=(",", ":"), sort_keys=True).encode("utf-8"))


def local_pairing_code_digest(secret: str, code: str) -> str:
    return hmac.new(secret.encode("utf-8"), code.encode("utf-8"), hashlib.sha256).hexdigest()


def sign_local_client_token(
    secret: str,
    *,
    client_id: str,
    client_name: str,
    origin: str,
    ttl_seconds: int,
    now: int | None = None,
) -> str:
    issued_at = int(time.time() if now is None else now)
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {
        "aud": LOCAL_CLIENT_TOKEN_AUDIENCE,
        "client_name": client_name[:120],
        "exp": issued_at + ttl_seconds,
        "iat": issued_at,
        "iss": LOCAL_CLIENT_TOKEN_ISSUER,
        "origin": origin[:240],
        "scope": "local_daemon",
        "sub": client_id,
    }
    raw_header = _json_b64(header)
    raw_payload = _json_b64(payload)
    signing_input = f"{raw_header}.{raw_payload}".encode("ascii")
    signature = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return f"{raw_header}.{raw_payload}.{_b64url(signature)}"


def verify_local_client_token(secret: str, token: str, *, now: int | None = None) -> bool:
    try:
        raw_header, raw_payload, raw_signature = token.split(".")
        header = json.loads(_b64url_decode(raw_header).decode("utf-8"))
        payload = json.loads(_b64url_decode(raw_payload).decode("utf-8"))
        supplied = _b64url_decode(raw_signature)
    except Exception:
        return False
    if not isinstance(header, dict) or not isinstance(payload, dict):
        return False
    if header.get("alg") != "HS256":
        return False
    if payload.get("iss") != LOCAL_CLIENT_TOKEN_ISSUER or payload.get("aud") != LOCAL_CLIENT_TOKEN_AUDIENCE:
        return False
    if payload.get("scope") != "local_daemon":
        return False
    try:
        exp = int(payload["exp"])
    except Exception:
        return False
    if exp <= int(time.time() if now is None else now):
        return False
    signing_input = f"{raw_header}.{raw_payload}".encode("ascii")
    expected = hmac.new(secret.encode("utf-8"), signing_input, hashlib.sha256).digest()
    return hmac.compare_digest(expected, supplied)
