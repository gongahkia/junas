"""Canonical Elasticsearch + Qdrant index/collection names.

Region-prefixed pattern adopted from adjacent SG legal ingestion tooling:
``junas_<region>_<doctype>``. Today we ship only ``sg``, but the
constants are namespaced so future Commonwealth-adjacent indices (MY,
HK) can be added without renaming.

Per ``docs/coverage-matrix.md`` §7, IRAS and Hansard indices are
*declared* but not yet populated; populating them is a v0.3 task.
"""
from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import Any

REGION = "sg"
_PREFIX = f"junas_{REGION}"
LEGIS_ID_FIELD = "legis_id"
SORT_DATE_FIELD = "sort_date"
LEGAL_SEARCH_SORT = [
    {SORT_DATE_FIELD: {"order": "desc", "missing": "_last", "unmapped_type": "date"}},
    {LEGIS_ID_FIELD: {"order": "asc", "missing": "_last", "unmapped_type": "keyword"}},
]
LEGIS_ID_COLLAPSE = {"field": LEGIS_ID_FIELD}


@dataclass(frozen=True)
class _Indices:
    statutes: str = f"{_PREFIX}_statutes"
    glossary: str = f"{_PREFIX}_glossary"
    cases: str = f"{_PREFIX}_cases"


@dataclass(frozen=True)
class _Collections:
    statutes: str = f"{_PREFIX}_statutes"
    cases: str = f"{_PREFIX}_cases"


ES = _Indices()
QDRANT = _Collections()


@dataclass(frozen=True)
class PaginationCursor:
    sort_values: list[Any]

    @classmethod
    def from_token(cls, token: str) -> "PaginationCursor":
        raw = str(token or "").strip()
        if not raw:
            raise ValueError("cursor must not be blank")
        padded = raw + "=" * (-len(raw) % 4)
        try:
            decoded = base64.urlsafe_b64decode(padded.encode("ascii")).decode("utf-8")
            values = json.loads(decoded)
        except (ValueError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("cursor is not valid") from exc
        if not isinstance(values, list) or not values:
            raise ValueError("cursor must encode search_after sort values")
        return cls(sort_values=values)

    def to_token(self) -> str:
        if not self.sort_values:
            raise ValueError("cursor must encode search_after sort values")
        raw = json.dumps(self.sort_values, separators=(",", ":"), ensure_ascii=True)
        return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii").rstrip("=")


def all_es_indices() -> list[str]:
    """List of all ES indices junas writes to."""
    return [ES.statutes, ES.glossary, ES.cases]


def all_qdrant_collections() -> list[str]:
    """List of all Qdrant collections junas writes to."""
    return [QDRANT.statutes, QDRANT.cases]
