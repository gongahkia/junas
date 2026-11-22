"""Optional inverse audit over closed metadata; all model output remains advisory.

Detected information is not public merely because a detector found it. Free-form
reasons, source text, offsets and caller document-type strings are not sent here.
Hashes permit linkage and are not proof of coverage, anonymity or public status.
"""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any, Protocol

from junas.advisory.llm_adjudicator.contracts import model_provenance
from junas.advisory.llm_adjudicator.structured_query import safe_document_type, safe_finding_metadata


class LLMCoverageAuditor(Protocol):
    def audit(self, *, findings: list[dict[str, Any]], body_hash: str, document_type: str) -> list[dict[str, Any]]:
        """Return unverified hypotheses; exceptions are failures, never findings."""
        ...


def _summarize_for_audit(findings: list) -> list[dict[str, Any]]:
    return [safe_finding_metadata(finding) for finding in findings]


def compute_body_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def normalize_warnings(warnings, *, body_hash, provenance):
    if not isinstance(warnings, list):
        raise ValueError("coverage auditor returned non-list output")
    normalized, seen = [], set()
    for warning in warnings:
        if not isinstance(warning, dict):
            raise ValueError("coverage warning must be an object")
        if {"matched_text", "start_char", "end_char", "source_verification", "verified", "risk_label"} & warning.keys():
            raise ValueError("coverage warnings cannot assert detector evidence or verification")
        for key in ("rule_guess", "why"):
            if not isinstance(warning.get(key), str) or not warning[key].strip():
                raise ValueError(f"coverage warning requires nonempty {key}")
        confidence = warning.get("confidence")
        if "confidence" in warning and (
            type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1
        ):
            raise ValueError("coverage confidence must be a finite number in [0, 1]")
        item = {"rule_guess": warning["rule_guess"].strip(), "why": warning["why"].strip(), "confidence": confidence}
        for key, allowed in (("category", {"PII", "MNPI"}), ("severity", {"low", "medium", "high"})):
            if key in warning:
                if not isinstance(warning[key], str) or warning[key] not in allowed:
                    raise ValueError(f"invalid coverage warning {key}")
                item[key] = warning[key]
        key = json.dumps(item, sort_keys=True)
        if key in seen:
            continue
        seen.add(key)
        item.update(
            {
                "body_hash": body_hash,
                "source": "llm_coverage_audit",
                "origin": "llm",
                "advisory_only": True,
                "evidence_status": "unverified",
                "classification_applied": False,
                "provenance": dict(provenance),
                "provider": provenance["provider"],
                "model": provenance["model"],
                "prompt_version": provenance["prompt_version"],
            }
        )
        normalized.append(item)
    return normalized


def run_coverage_audit(
    *,
    text: str,
    findings: list,
    document_type: str,
    auditor: LLMCoverageAuditor,
    fail_closed: bool = False,
) -> list[dict[str, Any]]:
    try:
        body_hash = compute_body_hash(text)
        warnings = auditor.audit(
            findings=_summarize_for_audit(findings),
            body_hash=body_hash,
            document_type=safe_document_type(document_type),
        )
        return normalize_warnings(warnings, body_hash=body_hash, provenance=model_provenance(auditor))
    except Exception as exc:
        if fail_closed:
            raise RuntimeError(f"coverage auditor failed: {exc}") from exc
        return []
