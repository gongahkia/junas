"""Transparent advisory signals for audit-grade MNPI review.

These helpers are intentionally deterministic and side-effect free. They provide
the item 66/67/68 substrate without changing `engine.review()` scoring until an
explicit audit-grade integration gate is added.
"""

from __future__ import annotations

import hashlib
import math
import re
from dataclasses import dataclass, field
from typing import Any

_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z0-9_-]{1,}")
_MNPI_TERMS = {
    "acquisition",
    "announcement",
    "blackout",
    "board",
    "confidential",
    "earnings",
    "embargo",
    "insider",
    "material",
    "merger",
    "nonpublic",
    "placement",
    "price",
    "project",
    "results",
    "revenue",
    "term",
}


@dataclass(frozen=True)
class AdvisorySignal:
    name: str
    score: float
    weight: float
    contribution: float
    rationale: str
    metadata: dict[str, Any] = field(default_factory=dict)


def _tokens(text: str) -> list[str]:
    return [match.group(0).lower() for match in _TOKEN_RE.finditer(text)]


def classifier_signal(text: str) -> AdvisorySignal:
    tokens = _tokens(text)
    if not tokens:
        return AdvisorySignal("classifier", 0.0, 0.0, 0.0, "no lexical substrate")
    hits = sorted(set(tokens) & _MNPI_TERMS)
    density = len(hits) / max(1, len(_MNPI_TERMS))
    score = min(1.0, density * 2.5)
    return AdvisorySignal(
        name="classifier",
        score=score,
        weight=0.18,
        contribution=round(score * 0.18, 6),
        rationale="deterministic lexical advisory proxy; not a trained classifier",
        metadata={"term_hits": hits},
    )


def fingerprint(text: str, *, buckets: int = 256) -> dict[int, float]:
    counts: dict[int, float] = {}
    for token in _tokens(text):
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        bucket = int.from_bytes(digest[:2], "big") % buckets
        counts[bucket] = counts.get(bucket, 0.0) + 1.0
    norm = math.sqrt(sum(value * value for value in counts.values())) or 1.0
    return {bucket: value / norm for bucket, value in counts.items()}


def cosine_similarity(left: dict[int, float], right: dict[int, float]) -> float:
    if len(left) > len(right):
        left, right = right, left
    return sum(value * right.get(bucket, 0.0) for bucket, value in left.items())


def similarity_signal(text: str, exemplars: list[dict[str, Any]]) -> AdvisorySignal:
    if not exemplars:
        return AdvisorySignal("similarity", 0.0, 0.0, 0.0, "no exemplar index configured")
    target = fingerprint(text)
    best: dict[str, Any] | None = None
    best_score = 0.0
    for exemplar in exemplars:
        vector = exemplar.get("fingerprint")
        if not isinstance(vector, dict):
            vector = fingerprint(str(exemplar.get("text") or ""))
        score = cosine_similarity(target, {int(k): float(v) for k, v in vector.items()})
        if score > best_score:
            best_score = score
            best = exemplar
    return AdvisorySignal(
        name="similarity",
        score=round(best_score, 6),
        weight=0.08,
        contribution=round(best_score * 0.08, 6),
        rationale="nearest reviewed-document similarity; advisory only",
        metadata={"nearest_doc_hash": (best or {}).get("doc_hash", "")},
    )


def aggregate_signals(
    *,
    deterministic_score: float,
    public_evidence_score: float = 0.0,
    llm_score: float = 0.0,
    extra_signals: list[AdvisorySignal] | None = None,
) -> dict[str, Any]:
    deterministic_norm = max(0.0, min(1.0, deterministic_score / 100.0))
    signals = [
        AdvisorySignal(
            "deterministic",
            deterministic_norm,
            0.55,
            round(deterministic_norm * 0.55, 6),
            "statute-cited deterministic anchor",
        ),
        AdvisorySignal(
            "public_evidence",
            max(-1.0, min(1.0, public_evidence_score)),
            0.20,
            round(max(-1.0, min(1.0, public_evidence_score)) * 0.20, 6),
            "public-status verification adjustment",
        ),
        AdvisorySignal(
            "llm",
            max(0.0, min(1.0, llm_score)),
            0.15,
            round(max(0.0, min(1.0, llm_score)) * 0.15, 6),
            "capped audit-grade LLM advisory signal",
        ),
    ]
    signals.extend(extra_signals or [])
    total = max(0.0, min(1.0, sum(signal.contribution for signal in signals)))
    return {
        "aggregated_mnpi_score": round(total * 100.0, 2),
        "signals": [signal.__dict__ for signal in signals],
        "deterministic_high_preserved": deterministic_score >= 85.0,
    }
