"""Persistent per-document mapping store keyed by document text SHA-256.

When `JUNAS_REVIEW_PERSIST=1`, the `/anonymize` endpoint writes its mapping table to
`${JUNAS_JOURNAL_DIR}/mappings/<document_hash>.json` so a later `/reidentify` call can
recover the mapping with just the hash, without the client retaining it.

Plaintext storage shape:
    {
        "storage_format": "plaintext-v1",
        "encrypted": false,
        "document_hash": "<sha256 hex>",
        "created_at": "<UTC ISO 8601>",
        "mapping": [
            {"placeholder": "[PERSON_1]", "entity_type": "PERSON", "original_text": "Dr Jane Tan",
             "occurrence_count": 2}
        ]
    }

When `JUNAS_MAPPING_STORE_KEY` is set to a Fernet key, the persisted file stores a
`fernet-v1` envelope with metadata plus ciphertext, and decryption fails closed if
the key is missing or wrong.

Lookup returns the raw list; reidentify only needs (placeholder, original_text).
Retention and deletion are explicit operator actions via purge helpers / CLI.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from threading import Lock
from typing import Any

from junas.review.journal import journal_dir
from junas.review.subject_index import SubjectIndexError, index_mapping, require_subject_index_key

_mapping_lock = Lock()
MAPPING_STORE_KEY_ENV = "JUNAS_MAPPING_STORE_KEY"


class MappingStoreError(RuntimeError):
    """Raised when the persisted mapping store cannot safely read or write data."""


class MappingStoreKeyError(MappingStoreError):
    """Raised when an encrypted mapping cannot be decrypted with the configured key."""


def compute_document_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mapping_dir(tenant_id: str | None = None) -> Path:
    return journal_dir(tenant_id) / "mappings"


def _mapping_path(document_hash: str, tenant_id: str | None = None) -> Path:
    # safety: hashes are hex so they cannot contain path separators, but normalise anyway
    safe = "".join(ch for ch in document_hash if ch.isalnum())[:128]
    return _mapping_dir(tenant_id) / f"{safe}.json"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _parse_iso(value: str) -> datetime | None:
    try:
        return datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return None


def _fernet_from_env():
    key = os.environ.get(MAPPING_STORE_KEY_ENV, "").strip()
    if not key:
        return None
    try:
        from cryptography.fernet import Fernet

        return Fernet(key.encode("ascii"))
    except Exception as exc:
        raise MappingStoreKeyError(
            f"{MAPPING_STORE_KEY_ENV} must be a valid Fernet key"
        ) from exc


def _build_plain_payload(*, document_hash: str, mapping: list[Any]) -> dict[str, Any]:
    return {
        "storage_format": "plaintext-v1",
        "encrypted": False,
        "document_hash": document_hash,
        "created_at": _now_iso(),
        "mapping": [_serialize_entry(entry) for entry in mapping],
    }


def save_mapping(*, document_hash: str, mapping: list[Any], tenant_id: str | None = None) -> Path:
    """Persist a mapping table for a document. Overwrite-safe."""
    require_subject_index_key()
    plain_payload = _build_plain_payload(document_hash=document_hash, mapping=mapping)
    fernet = _fernet_from_env()
    if fernet is None:
        payload = plain_payload
    else:
        ciphertext = fernet.encrypt(
            json.dumps(plain_payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")
        ).decode("ascii")
        payload = {
            "storage_format": "fernet-v1",
            "encrypted": True,
            "document_hash": document_hash,
            "created_at": plain_payload["created_at"],
            "ciphertext": ciphertext,
        }
    with _mapping_lock:
        path = _mapping_path(document_hash, tenant_id)
        path.parent.mkdir(parents=True, exist_ok=True)
        # atomic write: full payload to a temp file then rename so a crash mid-write cannot
        # leave a half-written mapping that would silently round-trip wrong later.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    try:
        index_mapping(document_hash=document_hash, mapping=mapping, tenant_id=tenant_id)
    except SubjectIndexError:
        with _mapping_lock:
            path.unlink(missing_ok=True)
        raise
    return path


def load_mapping(document_hash: str, *, tenant_id: str | None = None) -> list[dict[str, Any]] | None:
    path = _mapping_path(document_hash, tenant_id)
    if not path.exists():
        return None
    with _mapping_lock:
        data = json.loads(path.read_text(encoding="utf-8"))
    if bool(data.get("encrypted")) or data.get("storage_format") == "fernet-v1":
        fernet = _fernet_from_env()
        if fernet is None:
            raise MappingStoreKeyError(
                f"encrypted mapping requires {MAPPING_STORE_KEY_ENV}"
            )
        try:
            plaintext = fernet.decrypt(str(data.get("ciphertext", "")).encode("ascii"))
            data = json.loads(plaintext.decode("utf-8"))
        except Exception as exc:
            raise MappingStoreKeyError(
                "encrypted mapping could not be decrypted with the configured key"
            ) from exc
    if str(data.get("document_hash", "")) != document_hash:
        raise MappingStoreError("mapping document_hash does not match requested hash")
    return list(data.get("mapping", []))


def purge_mapping(document_hash: str, *, tenant_id: str | None = None) -> bool:
    """Delete a single mapping by document hash. Returns True when a file was removed."""
    with _mapping_lock:
        path = _mapping_path(document_hash, tenant_id)
        if not path.exists():
            return False
        path.unlink()
        return True


def mapping_exists(document_hash: str, *, tenant_id: str | None = None) -> bool:
    """Return True when a persisted mapping file exists for the document hash."""
    with _mapping_lock:
        return _mapping_path(document_hash, tenant_id).exists()


def _mapping_created_at(path: Path) -> datetime | None:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    created = _parse_iso(str(payload.get("created_at", "") or ""))
    if created is not None:
        return created
    try:
        return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc)
    except OSError:
        return None


def purge_expired_mappings(
    *,
    older_than_days: int,
    dry_run: bool = False,
    tenant_id: str | None = None,
) -> list[dict[str, Any]]:
    """List or delete mappings older than the supplied age threshold."""
    if older_than_days < 0:
        raise ValueError("older_than_days must be >= 0")
    cutoff = datetime.now(timezone.utc) - timedelta(days=older_than_days)
    removed: list[dict[str, Any]] = []
    with _mapping_lock:
        mapping_dir = _mapping_dir(tenant_id)
        if not mapping_dir.exists():
            return []
        for path in sorted(mapping_dir.glob("*.json")):
            created_at = _mapping_created_at(path)
            if created_at is None or created_at > cutoff:
                continue
            item = {
                "document_hash": path.stem,
                "path": str(path),
                "created_at": created_at.strftime("%Y-%m-%dT%H:%M:%SZ"),
                "deleted": False,
            }
            if not dry_run:
                path.unlink()
                item["deleted"] = True
            removed.append(item)
    return removed


def _serialize_entry(entry: Any) -> dict[str, Any]:
    if isinstance(entry, dict):
        return {
            "placeholder": str(entry.get("placeholder", "") or ""),
            "entity_type": str(entry.get("entity_type", "") or ""),
            "original_text": str(entry.get("original_text", "") or ""),
            "occurrence_count": int(entry.get("occurrence_count", 0) or 0),
        }
    return {
        "placeholder": str(getattr(entry, "placeholder", "") or ""),
        "entity_type": str(getattr(entry, "entity_type", "") or ""),
        "original_text": str(getattr(entry, "original_text", "") or ""),
        "occurrence_count": int(getattr(entry, "occurrence_count", 0) or 0),
    }
