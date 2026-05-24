"""LLM-assisted defined-term extraction (audit_grade only).

The deterministic `extract_defined_terms` regex catches the two most common preamble
patterns (`(the "Purchaser")` and `"Purchaser" means …`). The LLM tier exists to catch
looser introductions the regex misses:

    Acme Pte. Ltd. (hereinafter referred to as "the Seller")
    we will use "X" to refer to Y throughout this document
    For purposes of this Agreement, "Material" means …

This module wraps any extractor that implements `extract(preamble) -> list[str]` and
caches results by SHA-256 of the full document text. The preamble (first ~500 tokens
≈ 2000 chars) is the only thing sent to the LLM; the document body never leaves the
process boundary via this path.

Cache layout: `${KAYPOH_JOURNAL_DIR}/llm_defined_terms/{document_hash}.json` carrying
`{"terms": [casefolded, sorted], "ts": "<iso utc>"}`. Cache reads tolerate a missing
or malformed entry by returning an empty set and re-running the extractor.
"""

from __future__ import annotations

import hashlib
import json
import os
import time
from pathlib import Path
from threading import Lock
from typing import Protocol

# preamble length cap for the LLM call. ~500 GPT tokens ≈ 2000 chars; we cap on chars to
# stay provider-agnostic. Defined-term preambles in legal docs are essentially always
# inside this window.
PREAMBLE_CHAR_CAP = 2000

_cache_lock = Lock()


class LLMDefinedTermExtractor(Protocol):
    """Minimal contract for the LLM-tier defined-term helper."""

    def extract(self, preamble: str) -> list[str]:
        """Return a list of defined-term surface forms found in the preamble.
        Implementations should:
          - never send the full document body, only the `preamble` they receive
          - return the surface forms (e.g. ['Purchaser', 'the Seller']) without quotes
          - return an empty list if nothing is found or the call fails
        """
        ...


def _journal_dir() -> Path:
    return Path(os.environ.get("KAYPOH_JOURNAL_DIR", "./kaypoh-journal"))


def _cache_dir() -> Path:
    return _journal_dir() / "llm_defined_terms"


def document_hash(text: str) -> str:
    """SHA-256 of the document text. Stable cache key across reviews of the same document."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _cache_path(doc_hash: str) -> Path:
    return _cache_dir() / f"{doc_hash}.json"


def _load_cache(doc_hash: str) -> set[str] | None:
    path = _cache_path(doc_hash)
    if not path.exists():
        return None
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    terms = payload.get("terms", [])
    if not isinstance(terms, list):
        return None
    return {str(t).strip().casefold() for t in terms if t}


def _store_cache(doc_hash: str, terms: set[str]) -> None:
    path = _cache_path(doc_hash)
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "terms": sorted(terms),
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")


def extract_with_cache(
    *,
    text: str,
    extractor: LLMDefinedTermExtractor,
) -> set[str]:
    """Return the casefolded set of LLM-extracted defined terms for `text`, using the
    on-disk cache when present. Cache key is SHA-256 of the full document text.

    Caller guarantees `extractor` is the audit_grade-opt-in LLM helper. We send only
    the preamble (first PREAMBLE_CHAR_CAP chars) to the extractor; this module never
    forwards the document body."""
    doc_hash = document_hash(text)
    with _cache_lock:
        cached = _load_cache(doc_hash)
        if cached is not None:
            return cached
    preamble = text[:PREAMBLE_CHAR_CAP]
    try:
        raw_terms = extractor.extract(preamble) or []
    except Exception:
        # extractor failure (network error, malformed model output) is non-fatal — the
        # deterministic regex still ran. fall through to an empty LLM contribution.
        raw_terms = []
    terms = {str(t).strip().casefold() for t in raw_terms if t and isinstance(t, str)}
    with _cache_lock:
        _store_cache(doc_hash, terms)
    return terms
