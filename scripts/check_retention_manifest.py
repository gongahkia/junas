#!/usr/bin/env python3
"""Check operational retention controls for subject-erasure readiness."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_MANIFEST = ROOT / "retention_manifest.json"
REQUIRED_CONTROLS = ("journal", "mapping_store", "logs", "siem", "backups")


def _manifest_path(raw: str | None = None) -> Path:
    path = raw or os.environ.get("JUNAS_RETENTION_MANIFEST", "").strip() or str(DEFAULT_MANIFEST)
    return Path(path).expanduser().resolve()


def _load_manifest(path: Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, f"retention manifest not found: {path}"
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        return None, f"retention manifest parse failed: {exc}"
    if not isinstance(payload, dict):
        return None, "retention manifest root must be a JSON object"
    return payload, ""


def _has_nonempty_string(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _has_retention_window(value: Any) -> bool:
    if isinstance(value, bool):
        return False
    if isinstance(value, int):
        return value >= 0
    if isinstance(value, str):
        text = value.strip().lower()
        if text in {"indefinite", "permanent"}:
            return True
        try:
            return int(text) >= 0
        except ValueError:
            return False
    return False


def _evaluate_control(name: str, body: Any) -> dict[str, Any]:
    if not isinstance(body, dict):
        return {"control": name, "status": "missing", "reason": "control object missing"}
    if body.get("configured") is False or body.get("enabled") is False:
        return {"control": name, "status": "missing", "reason": "control is explicitly disabled"}

    keys = ("retention_days", "delete_after_days", "retain_for_days")
    if any(_has_retention_window(body.get(key)) for key in keys):
        return {"control": name, "status": "configured", "reason": "retention window configured"}
    if _has_nonempty_string(body.get("policy")) or _has_nonempty_string(body.get("external_policy_ref")):
        return {"control": name, "status": "configured", "reason": "external retention policy referenced"}
    return {
        "control": name,
        "status": "invalid",
        "reason": "expected retention_days/delete_after_days/retain_for_days or external policy reference",
    }


def check_manifest(path: Path) -> dict[str, Any]:
    manifest, error = _load_manifest(path)
    controls: list[dict[str, Any]] = []
    if manifest is None:
        controls = [
            {"control": name, "status": "missing", "reason": error}
            for name in REQUIRED_CONTROLS
        ]
        return {
            "schema_version": "junas.retention_manifest.v1",
            "manifest_path": str(path),
            "ok": False,
            "error": error,
            "controls": controls,
        }

    controls_section = manifest.get("controls", manifest)
    if not isinstance(controls_section, dict):
        controls_section = {}
    controls = [_evaluate_control(name, controls_section.get(name)) for name in REQUIRED_CONTROLS]
    ok = all(item["status"] == "configured" for item in controls)
    return {
        "schema_version": "junas.retention_manifest.v1",
        "manifest_path": str(path),
        "ok": ok,
        "error": "",
        "controls": controls,
    }


def render_text(payload: dict[str, Any]) -> str:
    lines = ["=== Junas Retention Manifest ===", f"manifest_path: {payload['manifest_path']}"]
    if payload.get("error"):
        lines.append(f"error: {payload['error']}")
    lines.append("controls:")
    for item in payload["controls"]:
        lines.append(f"  - {item['control']}: {item['status']} ({item['reason']})")
    lines.append(f"ok: {str(payload['ok']).lower()}")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check Junas retention controls manifest")
    parser.add_argument("--manifest", help="path to retention manifest JSON")
    parser.add_argument("--strict", action="store_true", help="exit non-zero when any control is missing or invalid")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    args = parser.parse_args(argv)

    payload = check_manifest(_manifest_path(args.manifest))
    if args.json:
        print(json.dumps(payload, indent=2, sort_keys=True))
    else:
        print(render_text(payload))
    if args.strict and not payload["ok"]:
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
