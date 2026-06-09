"""MCP wrapper for SAL citation validation."""
from __future__ import annotations

from dataclasses import asdict

from api.services.sal_citation import validate_citation as _validate_citation


def verify_citation(citation: str) -> dict:
    raw = str(citation or "").strip()
    try:
        result = _validate_citation(raw)
    except Exception as exc:  # noqa: BLE001
        return {"citation": raw, "error": str(exc)}
    payload = asdict(result)
    payload["citation"] = raw
    return payload
