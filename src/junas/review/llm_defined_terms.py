"""Unverified defined-term proposals and attributable v2 cache (audit_grade only).

Only the first PREAMBLE_CHAR_CAP characters are sent to an explicitly enabled
extractor. The review engine does not use model proposals for suppression.
Legacy document-only cache entries are ignored, never upgraded or overwritten.
Unattributed injected extractors run without disk caching.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
import time
from pathlib import Path
from threading import Lock
from typing import Protocol

PREAMBLE_CHAR_CAP = 2000
_cache_lock = Lock()


class LLMDefinedTermExtractor(Protocol):
    def extract(self, preamble: str) -> list[str]:
        """Return unverified surface-form proposals, not suppression authority."""
        ...


class LLMDefinedTermError(RuntimeError):
    """The configured helper or its attributable cache could not be used safely."""


def document_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_dir() -> Path:
    return Path(os.environ.get("JUNAS_CACHE_DIR", "./.junas-cache")) / "llm_defined_terms" / "v2"


def _cache_path(cache_key: str) -> Path:
    return _cache_dir() / f"{cache_key}.json"


def _identity(extractor):
    method = getattr(extractor, "cache_identity", None)
    if not callable(method):
        return None
    identity = method()  # runtime helpers recheck privacy/configuration gates here.
    required = {"provider", "model", "prompt_version", "prompt_sha256"}
    if (
        not isinstance(identity, dict)
        or not required <= identity.keys()
        or any(not isinstance(k, str) or not isinstance(v, str) or not v for k, v in identity.items())
        or any(identity[k] == "unattributed" for k in required)
        or re.fullmatch(r"[0-9a-f]{64}", identity["prompt_sha256"]) is None
    ):
        raise LLMDefinedTermError("extractor cache identity is incomplete")
    return {**identity, "preamble_char_cap": str(PREAMBLE_CHAR_CAP), "cache_contract": "v2"}


def _validated_terms(raw) -> set[str]:
    if not isinstance(raw, list) or any(not isinstance(t, str) or not t.strip() for t in raw):
        raise LLMDefinedTermError("extractor terms must be an array of nonempty strings")
    return {t.strip().casefold() for t in raw}


def _load_cache(cache_key: str, doc_hash: str, identity: dict) -> set[str] | None:
    try:
        payload = json.loads(_cache_path(cache_key).read_text(encoding="utf-8"))
        if (
            not isinstance(payload, dict)
            or payload.get("schema_version") != "junas.defined_terms_cache.v2"
            or payload.get("body_hash") != doc_hash
            or payload.get("identity") != identity
        ):
            return None
        return _validated_terms(payload.get("terms"))
    except (OSError, ValueError):
        return None


def _store_cache(cache_key: str, doc_hash: str, identity: dict, terms: set[str]) -> None:
    path = _cache_path(cache_key)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "schema_version": "junas.defined_terms_cache.v2",
        "body_hash": doc_hash,
        "identity": identity,
        "terms": sorted(terms),
        "evidence_status": "unverified",
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", dir=path.parent, delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(json.dumps(payload, indent=2) + "\n")
        os.replace(temporary, path)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


def extract_with_cache(*, text: str, extractor: LLMDefinedTermExtractor, fail_closed: bool = False) -> set[str]:
    try:
        doc_hash = document_hash(text)
        identity = _identity(extractor)
        cache_key = document_hash(json.dumps({"body_hash": doc_hash, "identity": identity}, sort_keys=True))
        if identity is not None:
            with _cache_lock:
                cached = _load_cache(cache_key, doc_hash, identity)
            if cached is not None:
                return cached
        terms = _validated_terms(extractor.extract(text[:PREAMBLE_CHAR_CAP]))
        if identity is not None:
            with _cache_lock:
                _store_cache(cache_key, doc_hash, identity, terms)
        return terms
    except Exception as exc:
        if fail_closed:
            raise LLMDefinedTermError(f"defined-term helper failed: {exc}") from exc
        return set()
