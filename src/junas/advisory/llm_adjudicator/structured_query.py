"""Structured-tokens-in/out mode for the LLM adjudicator (item 27).

The default LLM path sends the raw document text plus a runtime-context blob. That gives
the LLM the most signal but also exposes raw bytes to the model. For regulated tenants
who can't allow raw document text to leave the process boundary even once, this module
provides a stronger privacy guarantee: the LLM sees only a constrained vocabulary of
structured tokens that the server has already validated.

Wire shape into the LLM (structured mode):
    {
        "mode": "structured_tokens",
        "current_classification": "LOW_RISK",
        "entity_id": "<caller-supplied sanitised id, may be empty>",
        "body_hash": "<sha256 of document body>",
        "findings": [
            {
                "rule": "transaction_codename",
                "category": "MNPI",
                "severity": "high",
                "jurisdiction": "SG",
                "context_window_hash": "<sha256 of ±200 char window>"
            },
            ...
        ],
        "public_evidence_summary": {
            "status": "queried"|"skipped"|...,
            "source_count": <int>,
            "blocked_query_count": <int>
        }
    }

What is NOT sent (the leak surfaces present in raw_text mode):
- `document_text` — never included
- `matched_text` per finding — never included
- `start_char` / `end_char` — never included
- exact public-evidence URLs, titles, highlights — only counts

Wire shape coming back from the LLM (structured mode response validation):
    The LLM returns the same JSON shape as raw_text mode, BUT the server validates
    materiality_reason against a closed vocabulary (`STRUCTURED_REASONS`). Any value
    not in the whitelist is replaced with `"ambiguous_unconstrained"` and a
    privacy_ledger entry is recorded so the auditor can see how often the LLM
    attempted to emit free-form prose (which is a privacy risk in structured mode).
"""

from __future__ import annotations

import hashlib
from typing import Any

STRUCTURED_CONTEXT_WINDOW_CHARS = 200

# closed-vocabulary materiality_reason values the LLM is allowed to emit in
# structured mode. anything else gets clamped server-side.
STRUCTURED_REASONS = frozenset({
    "public_source_match",
    "no_public_source_match",
    "nonpublic_context_marker",
    "ambiguous_score_band",
    "embargo_marker_present",
    "deal_codename_present",
    "deterministic_high_floor",
    "ambiguous_unconstrained",
})


def _sha256_of_window(text: str, start: int, end: int) -> str:
    """SHA-256 of the ±STRUCTURED_CONTEXT_WINDOW_CHARS char window around a span.
    Used as proof-of-locality without revealing content."""
    lo = max(0, start - STRUCTURED_CONTEXT_WINDOW_CHARS)
    hi = min(len(text), end + STRUCTURED_CONTEXT_WINDOW_CHARS)
    return hashlib.sha256(text[lo:hi].encode("utf-8")).hexdigest()


def _sha256_of_body(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def build_structured_query(
    *,
    text: str,
    findings: list,
    entity_id: str | None,
    current_classification: str,
    public_evidence: dict | None,
) -> dict[str, Any]:
    """Build the structured-tokens payload. Caller passes the same arguments it would
    pass to _build_messages in raw_text mode; this builder strips raw text and span
    offsets, replacing them with hashes."""
    finding_tokens: list[dict[str, Any]] = []
    for f in findings:
        finding_tokens.append({
            "rule": f.rule,
            "category": f.category,
            "severity": f.severity,
            "jurisdiction": f.jurisdiction,
            "context_window_hash": _sha256_of_window(text, f.start_char, f.end_char),
        })

    pe_summary: dict[str, Any] = {"status": "skipped", "source_count": 0, "blocked_query_count": 0}
    if public_evidence:
        pe_summary["status"] = str(public_evidence.get("status", "skipped"))
        sources = public_evidence.get("sources") or []
        pe_summary["source_count"] = len(sources) if isinstance(sources, list) else 0
        queries = public_evidence.get("queries") or []
        pe_summary["blocked_query_count"] = sum(
            1 for q in queries if isinstance(q, dict) and q.get("blocked")
        )

    return {
        "mode": "structured_tokens",
        "current_classification": current_classification,
        "entity_id": entity_id or "",
        "body_hash": _sha256_of_body(text),
        "findings": finding_tokens,
        "public_evidence_summary": pe_summary,
    }


def clamp_structured_output(payload: dict[str, Any]) -> tuple[dict[str, Any], bool]:
    """Validate the LLM's response against the structured-mode whitelist.
    Returns (clamped_payload, was_clamped) so the caller can log a privacy_ledger
    entry when clamping occurred."""
    clamped = dict(payload)
    reason = str(clamped.get("materiality_reason", "") or "").strip().lower()
    was_clamped = False
    if reason not in STRUCTURED_REASONS:
        # the LLM tried to emit free-form prose (or an unknown closed-set value).
        # clamp to the catch-all and flag for auditor visibility.
        clamped["materiality_reason"] = "ambiguous_unconstrained"
        was_clamped = True
    # matched_public_sources can also leak — in structured mode the LLM should only
    # echo source counts, not URLs. truncate to empty so an off-script model can't
    # exfil via this field.
    clamped["matched_public_sources"] = []
    # unverified_claims similarly: free-form text. clamp to empty.
    clamped["unverified_claims"] = []
    # review_recommendation: trimmed to a short non-content marker.
    rec = str(clamped.get("review_recommendation", "") or "")
    if len(rec) > 80:
        clamped["review_recommendation"] = "see_audit_pack"
        was_clamped = True
    return clamped, was_clamped
