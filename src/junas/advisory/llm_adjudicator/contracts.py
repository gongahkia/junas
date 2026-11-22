"""Validation and provenance for unverified model advice, never detector evidence."""

from __future__ import annotations

import hashlib
import math
from typing import Any

ALLOWED_LABELS = frozenset({"SAFE", "LOW_RISK", "HIGH_RISK"})
ALLOWED_PUBLIC_STATUS = frozenset({"public", "not_public", "ambiguous", "not_checked"})


def model_provenance(component: Any) -> dict[str, str]:
    """Configuration attribution; hashes are not proof of model weights or authorship."""

    def field(name: str) -> str:
        value = getattr(component, name, None)
        return value if isinstance(value, str) and value else "unattributed"

    prompt = getattr(component, "system_prompt", "")
    endpoint = getattr(component, "base_url", "")
    if getattr(component, "provider", None) == "local_distilled":
        endpoint = ""
    return {
        "provider": field("provider"),
        "model": field("model"),
        "prompt_version": field("prompt_version"),
        "prompt_sha256": hashlib.sha256(prompt.encode()).hexdigest() if isinstance(prompt, str) and prompt else "",
        "endpoint_sha256": hashlib.sha256(endpoint.encode()).hexdigest()
        if isinstance(endpoint, str) and endpoint
        else "",
        "implementation": f"{type(component).__module__}.{type(component).__qualname__}",
    }


def validate_model_payload(payload: Any) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise ValueError("LLM output must be an object")
    required = {
        "risk_label",
        "public_status",
        "confidence",
        "materiality_reason",
        "matched_public_sources",
        "unverified_claims",
        "review_recommendation",
    }
    if not required <= payload.keys():
        raise ValueError("LLM output is missing required fields")
    result = {k: payload[k] for k in required}
    for key in ("risk_label", "public_status", "materiality_reason", "review_recommendation"):
        if not isinstance(result[key], str):
            raise ValueError(f"LLM {key} must be a string")
    result["risk_label"] = result["risk_label"].strip().upper()
    result["public_status"] = result["public_status"].strip().lower()
    if result["risk_label"] not in ALLOWED_LABELS or result["public_status"] not in ALLOWED_PUBLIC_STATUS:
        raise ValueError("LLM output contains an invalid risk/public-status label")
    confidence = result["confidence"]
    if type(confidence) not in (int, float) or not math.isfinite(confidence) or not 0 <= confidence <= 1:
        raise ValueError("LLM confidence must be a finite number in [0, 1]")
    for key in ("matched_public_sources", "unverified_claims"):
        if not isinstance(result[key], list) or any(not isinstance(x, str) for x in result[key]):
            raise ValueError(f"LLM {key} must be an array of strings")
        result[key] = list(result[key])
    return result


def advisory_result(payload: dict[str, Any], *, provenance: dict[str, str]) -> dict[str, Any]:
    raw = dict(payload)
    # rewrapping a validated provider result must retain its original proposal.
    if payload.get("advisory_only") is True:
        raw["public_status"] = payload.get("proposed_public_status")
        raw["matched_public_sources"] = payload.get("proposed_public_sources")
    result = validate_model_payload(raw)
    result.update(
        {
            "status": "adjudicated",
            "origin": "llm",
            "advisory_only": True,
            "evidence_status": "unverified",
            "classification_applied": False,
            "proposed_public_status": result["public_status"],
            "public_status": "not_checked",
            "proposed_public_sources": result["matched_public_sources"],
            "matched_public_sources": [],
            "confidence_kind": "model_self_report",
            "provenance": dict(provenance),
            "provider": provenance["provider"],
            "model": provenance["model"],
        }
    )
    return result
