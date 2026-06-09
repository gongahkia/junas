"""MCP wrapper for SG compliance checks."""
from __future__ import annotations

from dataclasses import asdict
from typing import Literal

from api.services.compliance_service import check_compliance as _check_compliance
from api.services.compliance_service import get_default_rules

Regime = Literal["pdpa", "employment_act", "roc_2021"]
ALLOWED_REGIMES = {"pdpa", "employment_act", "roc_2021"}

REGIME_RULE_MARKERS = {
    "pdpa": ("pdpa-",),
    "employment_act": ("employment-act", "cpf-"),
    "roc_2021": ("roc-2021",),
}


def check_compliance(text: str, regime: Regime) -> dict:
    raw = str(text or "")
    regime_name = str(regime or "").strip().lower()
    if regime_name not in ALLOWED_REGIMES:
        return {"error": f"unknown regime {regime_name!r}", "allowed_regimes": sorted(ALLOWED_REGIMES)}
    if not raw.strip():
        return {"error": "text must not be blank", "regime": regime_name}

    markers = REGIME_RULE_MARKERS[regime_name]
    rules = [
        rule
        for rule in get_default_rules("sg")
        if rule.id.startswith(markers)
    ]
    results = _check_compliance(raw, rules)
    summary = {
        "total": len(results),
        "passed": sum(1 for row in results if row.status == "pass"),
        "warnings": sum(1 for row in results if row.status == "warning"),
        "failed": sum(1 for row in results if row.status == "fail"),
    }
    return {
        "regime": regime_name,
        "summary": summary,
        "results": [asdict(row) for row in results],
    }
