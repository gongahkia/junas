"""Local-daemon ACL helpers for the offline desktop SKU."""

from __future__ import annotations

import fnmatch
import os
import secrets
import stat
import subprocess
import sys
from pathlib import Path

from kaypoh.configs.runtime import LocalDaemonSettings

LOCAL_TOKEN_HEADER = "X-Kaypoh-Local-Token"
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
