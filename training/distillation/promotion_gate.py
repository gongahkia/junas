#!/usr/bin/env python3
"""Gate promotion of a local_distilled adapter.

The repository can carry distillation tooling without carrying a promoted model.
This gate makes that explicit: `promoted=false` is valid only when no adapter path
is configured; `promoted=true` requires model-card, privacy-eval, and invariant
eval artifacts to pass.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

SCHEMA_VERSION = "kaypoh.distillation_promotion.v1"
MODEL_CARD_HEADINGS = (
    "## Promotion Status",
    "## Intended Use",
    "## Training Data",
    "## Evaluation",
    "## Privacy",
    "## Invariants",
)
PRIVACY_SCHEMA_VERSION = "kaypoh.llm_privacy_eval.v1"
REQUIRED_PRIVACY_CHECKS = {
    "structured_tokens_default",
    "remote_raw_text_blocked",
    "tenant_consent_required",
    "privacy_ledger_recorded",
    "pdpc_genai_personal_data_review",
}


def _load_json(path: Path) -> dict[str, Any]:
    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise ValueError(f"missing file: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid JSON: {path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise ValueError(f"JSON root must be object: {path}")
    return payload


def _resolve(base: Path, value: Any) -> Path | None:
    raw = str(value or "").strip()
    if not raw:
        return None
    path = Path(raw)
    return path if path.is_absolute() else (base / path).resolve()


def _validate_model_card(path: Path | None) -> list[str]:
    if path is None:
        return ["model_card_path is required"]
    if not path.exists():
        return [f"model_card_path missing: {path}"]
    text = path.read_text(encoding="utf-8")
    return [f"model card missing heading: {heading}" for heading in MODEL_CARD_HEADINGS if heading not in text]


def _validate_privacy_eval(path: Path | None, *, promoted: bool) -> list[str]:
    if path is None:
        return ["privacy_eval_path is required"]
    failures: list[str] = []
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return [str(exc)]
    if payload.get("schema_version") != PRIVACY_SCHEMA_VERSION:
        failures.append(f"privacy eval schema_version must be {PRIVACY_SCHEMA_VERSION}")
    status = str(payload.get("evaluation_status") or "")
    if promoted and status != "pass":
        failures.append("privacy eval must have evaluation_status=pass for promotion")
    if promoted and payload.get("input_mode") != "structured_tokens":
        failures.append("promoted local_distilled privacy eval must use structured_tokens")
    if promoted and bool(payload.get("raw_text_remote_allowed")):
        failures.append("promoted local_distilled privacy eval must block remote raw text")
    checks = payload.get("checks") or []
    if not isinstance(checks, list):
        return failures + ["privacy eval checks must be an array"]
    by_name = {
        str(item.get("name")): str(item.get("status"))
        for item in checks
        if isinstance(item, dict)
    }
    missing = REQUIRED_PRIVACY_CHECKS - set(by_name)
    if missing:
        failures.append(f"privacy eval missing checks: {', '.join(sorted(missing))}")
    if promoted:
        failed = sorted(name for name, status_value in by_name.items() if status_value != "pass")
        if failed:
            failures.append(f"privacy eval checks not passing: {', '.join(failed)}")
    return failures


def _validate_eval_report(path: Path | None, thresholds: dict[str, Any]) -> list[str]:
    if path is None:
        return ["eval_report_path is required when promoted=true"]
    failures: list[str] = []
    try:
        payload = _load_json(path)
    except ValueError as exc:
        return [str(exc)]
    if payload.get("student_provider") != "local_distilled":
        failures.append("eval report student_provider must be local_distilled")
    overall = payload.get("overall") or {}
    if not isinstance(overall, dict):
        return failures + ["eval report overall must be an object"]
    total = int(overall.get("total") or 0)
    if total <= 0:
        failures.append("eval report must cover at least one document")
    agreement_rate = float(overall.get("agreement_rate") or 0.0)
    min_agreement = float(thresholds.get("min_agreement") or 0.0)
    if agreement_rate < min_agreement:
        failures.append(f"agreement_rate {agreement_rate:.4f} < min_agreement {min_agreement:.4f}")
    violations = int(overall.get("invariant_violations") or 0)
    max_violations = int(thresholds.get("max_invariant_violations") or 0)
    if violations > max_violations:
        failures.append(
            f"invariant_violations {violations} > max_invariant_violations {max_violations}"
        )
    return failures


def validate_manifest(path: Path) -> dict[str, Any]:
    manifest_path = path.resolve()
    payload = _load_json(manifest_path)
    failures: list[str] = []
    if payload.get("schema_version") != SCHEMA_VERSION:
        failures.append(f"schema_version must be {SCHEMA_VERSION}")
    promoted = bool(payload.get("promoted"))
    base = manifest_path.parent
    adapter_path = _resolve(base, payload.get("adapter_path"))
    model_card_path = _resolve(base, payload.get("model_card_path"))
    privacy_eval_path = _resolve(base, payload.get("privacy_eval_path"))
    eval_report_path = _resolve(base, payload.get("eval_report_path"))
    thresholds = payload.get("thresholds") or {}
    if not isinstance(thresholds, dict):
        thresholds = {}
        failures.append("thresholds must be an object")
    failures.extend(_validate_model_card(model_card_path))
    failures.extend(_validate_privacy_eval(privacy_eval_path, promoted=promoted))
    if promoted:
        if adapter_path is None:
            failures.append("adapter_path is required when promoted=true")
        elif not adapter_path.is_dir():
            failures.append(f"adapter_path missing or not a directory: {adapter_path}")
        failures.extend(_validate_eval_report(eval_report_path, thresholds))
    elif adapter_path is not None:
        failures.append("promoted=false must not configure adapter_path")
    status = "pass" if not failures else "fail"
    if status == "pass" and not promoted:
        status = "not_promoted"
    return {
        "status": status,
        "promoted": promoted,
        "manifest_path": str(manifest_path),
        "failures": failures,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Validate local_distilled promotion gates")
    parser.add_argument(
        "--manifest",
        type=Path,
        default=Path(__file__).with_name("promotion_manifest.json"),
    )
    args = parser.parse_args(argv)
    try:
        result = validate_manifest(args.manifest)
    except ValueError as exc:
        result = {"status": "fail", "promoted": False, "failures": [str(exc)]}
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0 if result["status"] in {"pass", "not_promoted"} else 1


if __name__ == "__main__":
    raise SystemExit(main())
