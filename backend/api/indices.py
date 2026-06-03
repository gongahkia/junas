"""Canonical Elasticsearch + Qdrant index/collection names.

Region-prefixed pattern adopted from adjacent SG legal ingestion tooling:
``junas_<region>_<doctype>``. Today we ship only ``sg``, but the
constants are namespaced so future Commonwealth-adjacent indices (MY,
HK) can be added without renaming.

Per ``docs/coverage-matrix.md`` §7, IRAS and Hansard indices are
*declared* but not yet populated; populating them is a v0.3 task.
"""
from __future__ import annotations

from dataclasses import dataclass

REGION = "sg"
_PREFIX = f"junas_{REGION}"


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


def all_es_indices() -> list[str]:
    """List of all ES indices junas writes to."""
    return [ES.statutes, ES.glossary, ES.cases]


def all_qdrant_collections() -> list[str]:
    """List of all Qdrant collections junas writes to."""
    return [QDRANT.statutes, QDRANT.cases]
