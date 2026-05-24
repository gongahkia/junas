"""Persistent per-document mapping store keyed by document text SHA-256.

When `KAYPOH_REVIEW_PERSIST=1`, the `/anonymize` endpoint writes its mapping table to
`${KAYPOH_JOURNAL_DIR}/mappings/<document_hash>.json` so a later `/reidentify` call can
recover the mapping with just the hash, without the client retaining it.

Storage shape:
    {
        "document_hash": "<sha256 hex>",
        "created_at": "<UTC ISO 8601>",
        "mapping": [
            {"placeholder": "[PERSON_1]", "entity_type": "PERSON", "original_text": "Dr Jane Tan",
             "occurrence_count": 2}
        ]
    }

Lookup returns the raw list; reidentify only needs (placeholder, original_text).
The store is intentionally append-only by design — the document_hash collisions write
identical content, so blind overwrite is safe.
"""

from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from threading import Lock
from typing import Any

from kaypoh.review.journal import journal_dir


_mapping_lock = Lock()


def compute_document_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _mapping_dir() -> Path:
    return journal_dir() / "mappings"


def _mapping_path(document_hash: str) -> Path:
    # safety: hashes are hex so they cannot contain path separators, but normalise anyway
    safe = "".join(ch for ch in document_hash if ch.isalnum())[:128]
    return _mapping_dir() / f"{safe}.json"


def save_mapping(*, document_hash: str, mapping: list[Any]) -> Path:
    """Persist a mapping table for a document. Overwrite-safe."""
    payload = {
        "document_hash": document_hash,
        "created_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "mapping": [_serialize_entry(entry) for entry in mapping],
    }
    with _mapping_lock:
        path = _mapping_path(document_hash)
        path.parent.mkdir(parents=True, exist_ok=True)
        # atomic write: full payload to a temp file then rename so a crash mid-write cannot
        # leave a half-written mapping that would silently round-trip wrong later.
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        tmp.replace(path)
    return path


def load_mapping(document_hash: str) -> list[dict[str, Any]] | None:
    path = _mapping_path(document_hash)
    if not path.exists():
        return None
    with _mapping_lock:
        data = json.loads(path.read_text(encoding="utf-8"))
    return list(data.get("mapping", []))


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
