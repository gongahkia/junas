"""Per-tenant finding surfacing lanes.

The review engine still emits every finding. This module only tags and partitions
findings for default reviewer views.
"""

from __future__ import annotations

import hashlib
import os
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib


VALID_SEVERITIES = frozenset({"low", "medium", "high"})
VALID_ROUTES = frozenset({"default", "batched", "secondary", "threshold_gated"})
CONFIG_ENV = "JUNAS_TENANT_CONFIG_DIR"
EVENT_LANE_CONFIG_UPDATED = "lane_config_updated"
EVENT_LANE_CONFIG_DRIFT_DETECTED = "lane_config_drift_detected"
LANE_REVIEW_ID_PREFIX = "tenant-lane:"
_TENANT_STORAGE_RE = re.compile(r"[^A-Za-z0-9_.-]+")


class SurfacingLaneError(ValueError):
    """Raised when lane config cannot be loaded safely."""


@dataclass(frozen=True)
class LaneRule:
    severity: str
    route: str = "default"
    threshold_value: float | None = None
    digest_cadence: str = ""


@dataclass(frozen=True)
class LaneConfig:
    tenant_id: str
    path: Path
    config_hash: str
    rules: dict[str, LaneRule]


@dataclass(frozen=True)
class SurfacingLaneResult:
    findings: list[Any]
    visible_findings: list[Any]
    suppressed_findings: list[Any]
    config_hash: str
    config_path: str

    @property
    def suppressed_count(self) -> int:
        return len(self.suppressed_findings)


def tenant_config_dir() -> Path | None:
    configured = os.environ.get(CONFIG_ENV, "").strip()
    if not configured:
        return None
    return Path(configured).expanduser()


def safe_tenant_id(tenant_id: str) -> str:
    safe = _TENANT_STORAGE_RE.sub("_", tenant_id.strip())[:128].strip("._-")
    return safe or hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()[:32]


def tenant_lane_config_path(tenant_id: str, *, root: Path | None = None) -> Path | None:
    base = root if root is not None else tenant_config_dir()
    if base is None:
        return None
    return base / f"{safe_tenant_id(tenant_id)}.toml"


def config_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_lane_rule(severity: str, payload: Any) -> LaneRule:
    if severity not in VALID_SEVERITIES:
        raise SurfacingLaneError(f"unknown lane severity: {severity}")
    if payload is None:
        return LaneRule(severity=severity)
    if not isinstance(payload, dict):
        raise SurfacingLaneError(f"lane.{severity} must be a table")
    route = str(payload.get("route") or "default").strip()
    if route not in VALID_ROUTES:
        raise SurfacingLaneError(f"lane.{severity}.route must be one of {sorted(VALID_ROUTES)}")
    threshold_value: float | None = None
    if route == "threshold_gated":
        if "threshold_value" not in payload:
            raise SurfacingLaneError(f"lane.{severity}.threshold_gated requires threshold_value")
        try:
            threshold_value = float(payload["threshold_value"])
        except (TypeError, ValueError) as exc:
            raise SurfacingLaneError(f"lane.{severity}.threshold_value must be numeric") from exc
        if threshold_value < 0.0 or threshold_value > 100.0:
            raise SurfacingLaneError(f"lane.{severity}.threshold_value must be between 0 and 100")
    return LaneRule(
        severity=severity,
        route=route,
        threshold_value=threshold_value,
        digest_cadence=str(payload.get("digest_cadence") or "").strip(),
    )


def load_lane_config(tenant_id: str | None) -> LaneConfig | None:
    if not tenant_id:
        return None
    path = tenant_lane_config_path(tenant_id)
    if path is None or not path.exists():
        return None
    try:
        text = path.read_text(encoding="utf-8")
        raw = tomllib.loads(text)
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as exc:
        raise SurfacingLaneError(f"lane config is not readable TOML: {path}") from exc
    lane = raw.get("lane", {})
    if not isinstance(lane, dict):
        raise SurfacingLaneError("lane config root [lane] must be a table")
    rules = {severity: LaneRule(severity=severity) for severity in VALID_SEVERITIES}
    for severity, payload in lane.items():
        rules[str(severity).strip().lower()] = _parse_lane_rule(str(severity).strip().lower(), payload)
    return LaneConfig(
        tenant_id=tenant_id,
        path=path,
        config_hash=config_hash(text),
        rules=rules,
    )


def _lane_decision(finding: Any, config: LaneConfig) -> tuple[bool, LaneRule, str]:
    severity = str(getattr(finding, "severity", "") or "").strip().lower()
    rule = config.rules.get(severity, LaneRule(severity=severity or "unknown"))
    if rule.route == "default":
        return False, rule, "default_route"
    if rule.route == "threshold_gated":
        score = float(getattr(finding, "score", 0.0) or 0.0)
        if rule.threshold_value is not None and score >= rule.threshold_value:
            return False, rule, "threshold_met"
        return True, rule, "threshold_not_met"
    return True, rule, f"configured_{rule.route}_lane"


def _set_lane_metadata(finding: Any, *, config: LaneConfig, rule: LaneRule, suppressed: bool, reason: str) -> None:
    metadata = dict(getattr(finding, "metadata", {}) or {})
    metadata["lane_routing"] = {
        "tenant_id": config.tenant_id,
        "severity": str(getattr(finding, "severity", "") or ""),
        "route": rule.route,
        "suppressed": suppressed,
        "reason": reason,
        "threshold_value": rule.threshold_value,
        "digest_cadence": rule.digest_cadence,
        "config_hash": config.config_hash,
    }
    finding.metadata = metadata


def apply_surfacing_lanes(findings: list[Any], *, tenant_id: str | None) -> SurfacingLaneResult:
    config = load_lane_config(tenant_id)
    if config is None:
        return SurfacingLaneResult(
            findings=findings,
            visible_findings=findings,
            suppressed_findings=[],
            config_hash="",
            config_path="",
        )
    visible: list[Any] = []
    suppressed: list[Any] = []
    for finding in findings:
        is_suppressed, rule, reason = _lane_decision(finding, config)
        _set_lane_metadata(finding, config=config, rule=rule, suppressed=is_suppressed, reason=reason)
        if is_suppressed:
            suppressed.append(finding)
        else:
            visible.append(finding)
    detect_config_drift(config)
    return SurfacingLaneResult(
        findings=findings,
        visible_findings=visible,
        suppressed_findings=suppressed,
        config_hash=config.config_hash,
        config_path=str(config.path),
    )


def is_lane_suppressed_finding(finding: Any) -> bool:
    metadata = getattr(finding, "metadata", {}) if not isinstance(finding, dict) else finding.get("metadata", {})
    lane = metadata.get("lane_routing") if isinstance(metadata, dict) else None
    return bool(isinstance(lane, dict) and lane.get("suppressed") is True)


def partition_persisted_findings(findings: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    visible: list[dict[str, Any]] = []
    suppressed: list[dict[str, Any]] = []
    for finding in findings:
        if is_lane_suppressed_finding(finding):
            suppressed.append(finding)
        else:
            visible.append(finding)
    return visible, suppressed


def lane_review_id(tenant_id: str) -> str:
    return f"{LANE_REVIEW_ID_PREFIX}{safe_tenant_id(tenant_id)}"


def detect_config_drift(config: LaneConfig) -> bool:
    try:
        from junas.review.journal import append_event, read_journal
    except Exception:
        return False
    entries = read_journal(review_id=lane_review_id(config.tenant_id), tenant_id=config.tenant_id)
    latest_hash = ""
    for entry in entries:
        if entry.event_type == EVENT_LANE_CONFIG_UPDATED:
            latest_hash = str(entry.payload.get("new_hash") or "")
    if not latest_hash or latest_hash == config.config_hash:
        return False
    append_event(
        event_type=EVENT_LANE_CONFIG_DRIFT_DETECTED,
        review_id=lane_review_id(config.tenant_id),
        tenant_id=config.tenant_id,
        payload={
            "path": str(config.path),
            "expected_hash": latest_hash,
            "actual_hash": config.config_hash,
        },
    )
    return True
