from typing import Any, Callable

from junas.review.detectors.addresses import detect_address_findings
from junas.review.detectors.identifiers import (
    detect_core_identifier_findings,
    detect_sg_wedge_remainder_findings,
    detect_us_driver_license_findings,
    driver_license_coverage_warnings,
)
from junas.review.detectors.personal_attributes import detect_personal_attribute_inferences
from junas.review.detectors.registry import DetectorContext, DetectorRegistry
from junas.review.detectors.semantic import (
    detect_semantic_pii_fallback_findings as _detect_semantic_pii_fallback_findings,
)
from junas.review.detectors.semantic import semantic_pii_degraded_modes
from junas.review.secret_rulepacks import detect_secret_findings, load_secret_rule_packs_from_env


def detect_semantic_pii_fallback_findings(
    ctx: DetectorContext,
    idx_start: int,
    new_finding: Callable[..., Any],
) -> list[Any]:
    findings = _detect_semantic_pii_fallback_findings(ctx, idx_start, new_finding)
    rule_packs = load_secret_rule_packs_from_env()
    if rule_packs:
        findings.extend(
            detect_secret_findings(
                text=ctx.text,
                rule_packs=rule_packs,
                jurisdiction=ctx.jurisdiction,
                idx_start=idx_start + len(findings),
                new_finding=new_finding,
            )
        )
    return findings


__all__ = [
    "DetectorContext",
    "DetectorRegistry",
    "detect_address_findings",
    "detect_core_identifier_findings",
    "detect_personal_attribute_inferences",
    "detect_sg_wedge_remainder_findings",
    "detect_semantic_pii_fallback_findings",
    "detect_us_driver_license_findings",
    "driver_license_coverage_warnings",
    "semantic_pii_degraded_modes",
]
