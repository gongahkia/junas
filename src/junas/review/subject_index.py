"""Subject-erasure reverse index.

The index maps HMAC(canonical PII value) to persisted mapping/review references so a
subject-erasure request can find reversible mappings without storing raw PII in the
index itself.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
from pathlib import Path
from threading import Lock
from typing import Any

from junas.review.journal import journal_dir

SUBJECT_INDEX_KEY_ENV = "JUNAS_SUBJECT_INDEX_KEY"
STORAGE_FORMAT = "subject-index-v1"

_index_lock = Lock()
_PHONEISH_RE = re.compile(r"^[\s+().#:-]*\d[\d\s+().#:-]*$")


class SubjectIndexError(RuntimeError):
    """Raised when the subject-erasure index cannot safely read or write."""


class SubjectIndexKeyError(SubjectIndexError):
    """Raised when the subject-erasure index HMAC key is missing."""


def require_subject_index_key() -> bytes:
    key = os.environ.get(SUBJECT_INDEX_KEY_ENV, "").strip()
    if not key:
        raise SubjectIndexKeyError(
            f"{SUBJECT_INDEX_KEY_ENV} is required when JUNAS_REVIEW_PERSIST=1"
        )
    return key.encode("utf-8")


def canonicalize_subject_value(value: Any) -> str:
    text = " ".join(str(value or "").split()).strip()
    if not text:
        return ""
    digits = re.sub(r"\D", "", text)
    if len(digits) >= 7 and _PHONEISH_RE.fullmatch(text):
        return digits
    return text.casefold()


def subject_hash(value: Any, *, key: bytes | None = None) -> str:
    canonical = canonicalize_subject_value(value)
    if not canonical:
        raise SubjectIndexError("cannot index empty subject value")
    key_bytes = key if key is not None else require_subject_index_key()
    return hmac.new(key_bytes, canonical.encode("utf-8"), hashlib.sha256).hexdigest()


def subject_index_dir(tenant_id: str | None = None) -> Path:
    return journal_dir(tenant_id) / "subject_index"


def subject_index_path(tenant_id: str | None = None) -> Path:
    return subject_index_dir(tenant_id) / "index.json"


def _now_iso() -> str:
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())


def _empty_index() -> dict[str, Any]:
    return {"storage_format": STORAGE_FORMAT, "entries": {}}


def _load_index(tenant_id: str | None = None) -> dict[str, Any]:
    path = subject_index_path(tenant_id)
    if not path.exists():
        return _empty_index()
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise SubjectIndexError(f"subject index is unreadable: {exc}") from exc
    if payload.get("storage_format") != STORAGE_FORMAT or not isinstance(payload.get("entries"), dict):
        raise SubjectIndexError("subject index has unsupported format")
    return payload


def _write_index(payload: dict[str, Any], tenant_id: str | None = None) -> Path:
    path = subject_index_path(tenant_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    tmp.replace(path)
    return path


def _entry_key(entry: dict[str, Any]) -> tuple[str, ...]:
    return (
        str(entry.get("entry_type", "")),
        str(entry.get("document_hash", "")),
        str(entry.get("review_id", "")),
        str(entry.get("finding_id", "")),
        str(entry.get("placeholder", "")),
    )


def _add_entries(entries_by_hash: dict[str, list[dict[str, Any]]], *, tenant_id: str | None = None) -> int:
    if not entries_by_hash:
        return 0
    require_subject_index_key()
    with _index_lock:
        payload = _load_index(tenant_id)
        all_entries: dict[str, list[dict[str, Any]]] = payload["entries"]
        added = 0
        for pii_hash, incoming in entries_by_hash.items():
            existing = list(all_entries.get(pii_hash, []))
            seen = {_entry_key(entry) for entry in existing}
            for entry in incoming:
                key = _entry_key(entry)
                if key in seen:
                    continue
                existing.append(entry)
                seen.add(key)
                added += 1
            if existing:
                all_entries[pii_hash] = existing
        if added:
            _write_index(payload, tenant_id)
        return added


def index_mapping(
    *,
    document_hash: str,
    mapping: list[Any],
    tenant_id: str | None = None,
) -> int:
    key = require_subject_index_key()
    created_at = _now_iso()
    entries_by_hash: dict[str, list[dict[str, Any]]] = {}
    for entry in mapping:
        if isinstance(entry, dict):
            original = entry.get("original_text", "")
            entity_type = str(entry.get("entity_type", "") or "")
            placeholder = str(entry.get("placeholder", "") or "")
        else:
            original = getattr(entry, "original_text", "")
            entity_type = str(getattr(entry, "entity_type", "") or "")
            placeholder = str(getattr(entry, "placeholder", "") or "")
        canonical = canonicalize_subject_value(original)
        if not canonical:
            continue
        pii_hash = subject_hash(canonical, key=key)
        entries_by_hash.setdefault(pii_hash, []).append(
            {
                "entry_type": "mapping",
                "document_hash": document_hash,
                "entity_type": entity_type,
                "placeholder": placeholder,
                "created_at": created_at,
            }
        )
    return _add_entries(entries_by_hash, tenant_id=tenant_id)


def index_review_findings(
    *,
    review_id: str,
    document_hash: str,
    findings: list[dict[str, Any]],
    tenant_id: str | None = None,
) -> int:
    key = require_subject_index_key()
    created_at = _now_iso()
    entries_by_hash: dict[str, list[dict[str, Any]]] = {}
    for finding in findings:
        if str(finding.get("category", "")).upper() != "PII":
            continue
        matched_text = finding.get("matched_text", "")
        canonical = canonicalize_subject_value(matched_text)
        if not canonical:
            continue
        pii_hash = subject_hash(canonical, key=key)
        entries_by_hash.setdefault(pii_hash, []).append(
            {
                "entry_type": "review",
                "document_hash": document_hash,
                "review_id": review_id,
                "finding_id": str(finding.get("id", "") or ""),
                "rule": str(finding.get("rule", "") or ""),
                "created_at": created_at,
            }
        )
    return _add_entries(entries_by_hash, tenant_id=tenant_id)


def lookup_subject(value: Any, *, tenant_id: str | None = None) -> dict[str, Any]:
    pii_hash = subject_hash(value)
    with _index_lock:
        payload = _load_index(tenant_id)
        entries = list(payload["entries"].get(pii_hash, []))
    return {"pii_hash": pii_hash, "entries": entries}


def remove_subject(value: Any, *, tenant_id: str | None = None) -> int:
    pii_hash = subject_hash(value)
    with _index_lock:
        payload = _load_index(tenant_id)
        entries = payload["entries"].pop(pii_hash, [])
        if entries:
            _write_index(payload, tenant_id)
        return len(entries)


def reset_index(*, tenant_id: str | None = None) -> Path:
    require_subject_index_key()
    with _index_lock:
        return _write_index(_empty_index(), tenant_id)
