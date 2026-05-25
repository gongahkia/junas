"""Append-only HMAC-chained event journal for review decisions and audit-pack contents.

Every event written here is sealed: it carries `prev_hash` (the HMAC of the previous entry)
and `hmac` (HMAC-SHA256 of the canonical event message keyed by the resolved journal key).
Any mutation to a prior line invalidates every subsequent HMAC, so internal audit can detect
tampering with a single sweep.

Storage is a single append-only JSONL file at `${KAYPOH_JOURNAL_DIR:-./kaypoh-journal}/journal.jsonl`.
One file simplifies chain verification at the cost of unbounded growth; rotation is a future
concern that needs a documented cross-file chain link.

Key resolution priority (per entry):
1. If the entry's `key_version` field is non-empty, look up that version in the keystore
   pointed at by `KAYPOH_JOURNAL_KEYS_FILE` (TOML).
2. Otherwise (legacy entries written before per-org rotation existed), use `KAYPOH_JOURNAL_KEY`.

Rotation: writing a `journal_key_rolled` event under the new active key transitions the
chain. The rotation sentinel records `{from_version, to_version, reason}` and is itself
sealed by the new key — so an auditor with both old and new keys can replay across the
boundary, while an actor with only the OLD key cannot forge events past the rotation.

The TOML keystore schema:

    active = "v2"

    [keys.v1]
    secret = "first-tenant-secret"

    [keys.v2]
    secret = "rotated-tenant-secret"
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from dataclasses import dataclass
from pathlib import Path
from threading import Lock
from typing import Any

import tomllib

GENESIS_HASH = "GENESIS"
DEFAULT_JOURNAL_DIR_NAME = "kaypoh-journal"
DEFAULT_DEV_KEY = b"kaypoh-default-dev-key"  # production must set KAYPOH_JOURNAL_KEY
LEGACY_KEY_VERSION = ""  # sentinel: entries without a key_version field use the legacy env-var key
_TENANT_STORAGE_RE = re.compile(r"[^A-Za-z0-9_.-]+")

_journal_lock = Lock()


class KeyResolutionError(RuntimeError):
    """Raised when a key version cannot be resolved against the configured keystore."""


@dataclass(frozen=True)
class JournalEntry:
    seq: int
    ts: str
    event_type: str
    review_id: str
    payload: dict[str, Any]
    prev_hash: str
    hmac: str
    key_version: str = LEGACY_KEY_VERSION

    def to_json(self) -> str:
        # legacy entries written before rotation existed must serialise without the
        # `key_version` field so the bytes-on-disk format and HMAC computation stay byte-identical
        # to their original. only newly-versioned entries emit the field.
        data: dict[str, Any] = {
            "seq": self.seq,
            "ts": self.ts,
            "event_type": self.event_type,
            "review_id": self.review_id,
            "payload": self.payload,
            "prev_hash": self.prev_hash,
            "hmac": self.hmac,
        }
        if self.key_version:
            data["key_version"] = self.key_version
        return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=False)

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "JournalEntry":
        return cls(
            seq=int(data["seq"]),
            ts=str(data["ts"]),
            event_type=str(data["event_type"]),
            review_id=str(data["review_id"]),
            payload=dict(data["payload"]),
            prev_hash=str(data["prev_hash"]),
            hmac=str(data["hmac"]),
            key_version=str(data.get("key_version", LEGACY_KEY_VERSION)),
        )


def _tenant_storage_dir_name(tenant_id: str) -> str:
    safe = _TENANT_STORAGE_RE.sub("_", tenant_id.strip())[:128].strip("._-")
    return safe or hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:32]


def journal_dir(tenant_id: str | None = None) -> Path:
    base = Path(os.environ.get("KAYPOH_JOURNAL_DIR", f"./{DEFAULT_JOURNAL_DIR_NAME}"))
    if not tenant_id:
        return base
    return base / "tenants" / _tenant_storage_dir_name(tenant_id)


def journal_path(tenant_id: str | None = None) -> Path:
    return journal_dir(tenant_id) / "journal.jsonl"


def _legacy_journal_key() -> bytes:
    key = os.environ.get("KAYPOH_JOURNAL_KEY", "")
    return key.encode("utf-8") if key else DEFAULT_DEV_KEY


def _journal_key() -> bytes:
    """Legacy single-key resolver. Retained for callers that pre-date the keystore (e.g.,
    `scripts/export_audit_pack.py::_seal_manifest`) which seal artefacts under the active key.
    Returns the active keystore key when a keystore is configured; falls back to the legacy
    env-var key otherwise."""
    store = _load_keystore()
    if store is None:
        return _legacy_journal_key()
    active = store.get("active")
    if active and active in store.get("keys", {}):
        return store["keys"][active]
    return _legacy_journal_key()


def _load_keystore() -> dict[str, Any] | None:
    """Read the TOML keystore pointed at by KAYPOH_JOURNAL_KEYS_FILE. Returns
    {"active": str, "keys": {version: bytes}} or None when no keystore is configured.
    Missing or malformed keystore returns None so callers fall through to the legacy key."""
    path_str = os.environ.get("KAYPOH_JOURNAL_KEYS_FILE", "").strip()
    if not path_str:
        return None
    path = Path(path_str).expanduser()
    if not path.exists():
        return None
    try:
        raw = tomllib.loads(path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, OSError, UnicodeDecodeError):
        return None
    keys_section = raw.get("keys", {}) or {}
    if not isinstance(keys_section, dict):
        return None
    keys: dict[str, bytes] = {}
    for version, body in keys_section.items():
        if isinstance(body, dict) and "secret" in body:
            keys[str(version)] = str(body["secret"]).encode("utf-8")
    active = str(raw.get("active", "")).strip()
    return {"active": active, "keys": keys}


def _active_key_version() -> str:
    """Returns the active key version for new entries; empty string when no keystore is
    configured (so new entries serialise without `key_version`, matching legacy format)."""
    store = _load_keystore()
    if store is None:
        return LEGACY_KEY_VERSION
    active = store.get("active", "")
    if active and active in store.get("keys", {}):
        return active
    return LEGACY_KEY_VERSION


def _resolve_key_for_version(version: str) -> bytes:
    """Look up the HMAC key for a given key_version. Empty version → legacy env-var key."""
    if not version or version == LEGACY_KEY_VERSION:
        return _legacy_journal_key()
    store = _load_keystore()
    if store is None or version not in store.get("keys", {}):
        raise KeyResolutionError(f"no key configured for version {version!r}")
    return store["keys"][version]


def _canonical_payload(payload: dict[str, Any]) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _compute_hmac(
    *,
    seq: int,
    ts: str,
    event_type: str,
    review_id: str,
    payload: dict[str, Any],
    prev_hash: str,
    key_bytes: bytes,
) -> str:
    message = f"{seq}|{ts}|{event_type}|{review_id}|{_canonical_payload(payload)}|{prev_hash}".encode("utf-8")
    return hmac.new(key_bytes, message, hashlib.sha256).hexdigest()


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _read_last_entry(path: Path) -> JournalEntry | None:
    if not path.exists():
        return None
    last_line: str | None = None
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if stripped:
                last_line = stripped
    if last_line is None:
        return None
    return JournalEntry.from_dict(json.loads(last_line))


def append_event(
    *,
    event_type: str,
    review_id: str,
    payload: dict[str, Any],
    tenant_id: str | None = None,
) -> JournalEntry:
    """Append a single event, chained to the previous entry. Thread-safe within a process.
    Uses the active key version from the keystore; falls back to the legacy single-key when
    no keystore is configured."""
    with _journal_lock:
        path = journal_path(tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        last = _read_last_entry(path)
        seq = (last.seq + 1) if last else 0
        prev_hash = last.hmac if last else GENESIS_HASH
        ts = _now_iso()
        key_version = _active_key_version()
        key_bytes = _resolve_key_for_version(key_version)
        entry_hmac = _compute_hmac(
            seq=seq,
            ts=ts,
            event_type=event_type,
            review_id=review_id,
            payload=payload,
            prev_hash=prev_hash,
            key_bytes=key_bytes,
        )
        entry = JournalEntry(
            seq=seq,
            ts=ts,
            event_type=event_type,
            review_id=review_id,
            payload=payload,
            prev_hash=prev_hash,
            hmac=entry_hmac,
            key_version=key_version,
        )
        with path.open("a", encoding="utf-8") as fh:
            fh.write(entry.to_json() + "\n")
        try:
            from kaypoh.backend.siem import emit_journal_event

            emit_journal_event(entry)
        except Exception:
            # SIEM export must never weaken the journal's append-only durability.
            pass
        return entry


def read_journal(*, review_id: str | None = None, tenant_id: str | None = None) -> list[JournalEntry]:
    path = journal_path(tenant_id)
    if not path.exists():
        return []
    entries: list[JournalEntry] = []
    with path.open("r", encoding="utf-8") as fh:
        for line in fh:
            stripped = line.strip()
            if not stripped:
                continue
            entry = JournalEntry.from_dict(json.loads(stripped))
            if review_id is None or entry.review_id == review_id:
                entries.append(entry)
    return entries


def verify_chain(entries: list[JournalEntry] | None = None, *, tenant_id: str | None = None) -> tuple[bool, list[str]]:
    """Recompute the HMAC chain over `entries` (or the whole journal). Returns (valid, errors).
    Each entry's key is resolved by its `key_version`; entries whose version is not in the
    keystore record a key-resolution error and the chain is marked invalid."""
    if entries is None:
        entries = read_journal(tenant_id=tenant_id)
    errors: list[str] = []
    prev_hash = GENESIS_HASH
    expected_seq = 0
    for entry in entries:
        if entry.seq != expected_seq:
            errors.append(f"seq mismatch at expected {expected_seq}: got {entry.seq}")
        if entry.prev_hash != prev_hash:
            errors.append(f"prev_hash mismatch at seq {entry.seq}")
        try:
            key_bytes = _resolve_key_for_version(entry.key_version)
        except KeyResolutionError as exc:
            errors.append(f"key resolution failed at seq {entry.seq}: {exc}")
            prev_hash = entry.hmac
            expected_seq = entry.seq + 1
            continue
        expected_hmac = _compute_hmac(
            seq=entry.seq,
            ts=entry.ts,
            event_type=entry.event_type,
            review_id=entry.review_id,
            payload=entry.payload,
            prev_hash=entry.prev_hash,
            key_bytes=key_bytes,
        )
        if entry.hmac != expected_hmac:
            errors.append(f"hmac mismatch at seq {entry.seq}")
        prev_hash = entry.hmac
        expected_seq = entry.seq + 1
    return len(errors) == 0, errors


EVENT_JOURNAL_KEY_ROLLED = "journal_key_rolled"


def rotate_journal_key(
    *,
    to_version: str,
    reason: str,
    review_id: str = "system",
    tenant_id: str | None = None,
) -> JournalEntry:
    """Mark a key rotation in the chain. The keystore must already have `to_version` configured
    and set as `active`; this function just emits the sentinel event sealed under the new key.
    The sentinel records the prior active version (read from the last entry's key_version) so
    auditors can replay across the boundary."""
    store = _load_keystore()
    if store is None:
        raise KeyResolutionError("rotation requires a configured KAYPOH_JOURNAL_KEYS_FILE")
    if to_version not in store.get("keys", {}):
        raise KeyResolutionError(f"to_version {to_version!r} is not in the keystore")
    if store.get("active") != to_version:
        raise KeyResolutionError(
            f"rotation expects the keystore's active version to already be {to_version!r}; "
            f"got {store.get('active')!r}"
        )
    last = _read_last_entry(journal_path(tenant_id))
    from_version = last.key_version if last else LEGACY_KEY_VERSION
    return append_event(
        event_type=EVENT_JOURNAL_KEY_ROLLED,
        review_id=review_id,
        payload={
            "from_version": from_version,
            "to_version": to_version,
            "reason": reason,
        },
        tenant_id=tenant_id,
    )
