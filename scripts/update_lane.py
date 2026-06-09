#!/usr/bin/env python3
"""Update tenant surfacing lane config with a journaled reason."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.journal import append_event  # noqa: E402
from kaypoh.review.surfacing_lane import (  # noqa: E402
    CONFIG_ENV,
    EVENT_LANE_CONFIG_UPDATED,
    VALID_ROUTES,
    VALID_SEVERITIES,
    config_hash,
    lane_review_id,
    safe_tenant_id,
    tenant_lane_config_path,
)


def _load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"lane": {}}
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        return {"lane": {}}
    lane = raw.get("lane", {})
    if not isinstance(lane, dict):
        lane = {}
    return {"lane": lane}


def _format_value(value: Any) -> str:
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int | float):
        return str(value)
    return json.dumps(str(value), ensure_ascii=False)


def _render_config(config: dict[str, Any]) -> str:
    lines: list[str] = []
    lane = config.get("lane", {})
    for severity in ("low", "medium", "high"):
        payload = lane.get(severity, {})
        if not isinstance(payload, dict):
            payload = {}
        lines.append(f"[lane.{severity}]")
        for key in ("route", "threshold_value", "digest_cadence"):
            if key in payload and payload[key] not in (None, ""):
                lines.append(f"{key} = {_format_value(payload[key])}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def update_lane_config(
    *,
    tenant: str,
    severity: str,
    route: str,
    threshold_value: float | None,
    digest_cadence: str,
    reason: str,
    actor: str,
    dry_run: bool = False,
) -> dict[str, Any]:
    tenant_id = safe_tenant_id(tenant)
    if severity not in VALID_SEVERITIES:
        raise ValueError(f"severity must be one of {sorted(VALID_SEVERITIES)}")
    if route not in VALID_ROUTES:
        raise ValueError(f"route must be one of {sorted(VALID_ROUTES)}")
    if route == "threshold_gated" and threshold_value is None:
        raise ValueError("threshold_gated route requires --threshold-value")
    if not reason.strip():
        raise ValueError("--reason is required")
    path = tenant_lane_config_path(tenant_id)
    if path is None:
        raise ValueError(f"{CONFIG_ENV} must be set")
    before_text = path.read_text(encoding="utf-8") if path.exists() else ""
    config = _load_config(path)
    lane = dict(config.get("lane", {}))
    payload = dict(lane.get(severity, {}))
    payload["route"] = route
    if route == "threshold_gated":
        payload["threshold_value"] = float(threshold_value)
    else:
        payload.pop("threshold_value", None)
    if digest_cadence:
        payload["digest_cadence"] = digest_cadence
    lane[severity] = payload
    config["lane"] = lane
    after_text = _render_config(config)
    result = {
        "tenant": tenant_id,
        "path": str(path),
        "severity": severity,
        "route": route,
        "old_hash": config_hash(before_text) if before_text else "",
        "new_hash": config_hash(after_text),
        "dry_run": dry_run,
    }
    if dry_run:
        return result
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(after_text, encoding="utf-8")
    append_event(
        event_type=EVENT_LANE_CONFIG_UPDATED,
        review_id=lane_review_id(tenant_id),
        tenant_id=tenant_id,
        payload={
            **result,
            "actor": actor,
            "reason": reason.strip(),
        },
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Update tenant surfacing lane config")
    parser.add_argument("--tenant", required=True)
    parser.add_argument("--severity", required=True, choices=sorted(VALID_SEVERITIES))
    parser.add_argument("--route", required=True, choices=sorted(VALID_ROUTES))
    parser.add_argument("--threshold-value", type=float)
    parser.add_argument("--digest-cadence", default="")
    parser.add_argument("--reason", required=True)
    parser.add_argument("--actor", default=os.environ.get("USER", ""))
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    try:
        result = update_lane_config(
            tenant=args.tenant,
            severity=args.severity,
            route=args.route,
            threshold_value=args.threshold_value,
            digest_cadence=args.digest_cadence,
            reason=args.reason,
            actor=args.actor,
            dry_run=args.dry_run,
        )
    except Exception as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
