"""Helpers for human review and promotion of candidate fixture labels."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_DECISIONS = frozenset({"approve", "reject", "needs_edit"})
APPROVED_STATUS = "approved"


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def labels_path_for(fixture_path: Path) -> Path:
    return fixture_path.with_suffix(".labels.json")


def load_labels(labels_path: Path) -> dict[str, Any]:
    return json.loads(labels_path.read_text(encoding="utf-8"))


def write_labels(labels_path: Path, labels: dict[str, Any]) -> None:
    labels_path.write_text(json.dumps(labels, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def is_auto_labeled(labels: dict[str, Any]) -> bool:
    source = str(labels.get("_label_source") or "")
    return source.endswith("-auto")


def is_candidate_label(labels: dict[str, Any]) -> bool:
    return (
        "_taxonomy_concept" in labels
        or "_generation_note" in labels
        or "_human_review_status" in labels
        or is_auto_labeled(labels)
    )


def is_human_approved(labels: dict[str, Any]) -> bool:
    if str(labels.get("_human_review_status") or "") != APPROVED_STATUS:
        return False
    review = labels.get("_human_review")
    return isinstance(review, dict) and bool(str(review.get("reviewer") or "").strip())


def record_human_review(
    labels: dict[str, Any],
    *,
    decision: str,
    reviewer: str,
    notes: str = "",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(sorted(VALID_DECISIONS))}")
    reviewer = reviewer.strip()
    if not reviewer:
        raise ValueError("reviewer must not be empty")
    status = {
        "approve": "approved",
        "reject": "rejected",
        "needs_edit": "needs_edit",
    }[decision]
    entry = {
        "decision": decision,
        "status": status,
        "reviewer": reviewer,
        "notes": notes.strip(),
        "reviewed_at_utc": reviewed_at or utc_now(),
        "reviewed_label_source": str(labels.get("_label_source") or ""),
        "reviewed_label_model": str(labels.get("_label_model") or ""),
    }
    history = labels.get("_human_review_history")
    if not isinstance(history, list):
        history = []
    history.append(entry)
    labels["_human_review_status"] = status
    labels["_human_review"] = entry
    labels["_human_review_history"] = history
    return labels


def review_status_violation(labels_path: Path, labels: dict[str, Any]) -> str:
    if not is_candidate_label(labels):
        return ""
    if is_human_approved(labels):
        return ""
    source = str(labels.get("_label_source") or "unknown")
    status = str(labels.get("_human_review_status") or "missing")
    return f"{labels_path}: candidate/auto label source={source} human_review_status={status}"


def collect_review_status_violations(corpus_dir: Path) -> list[str]:
    violations: list[str] = []
    for labels_path in sorted(corpus_dir.glob("**/*.labels.json")):
        try:
            labels = load_labels(labels_path)
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"{labels_path}: labels unreadable: {exc}")
            continue
        violation = review_status_violation(labels_path, labels)
        if violation:
            violations.append(violation)
    return violations


def approved_reviewer(labels: dict[str, Any]) -> str:
    review = labels.get("_human_review") or {}
    return str(review.get("reviewer") or "") if isinstance(review, dict) else ""


def approved_reviewed_at(labels: dict[str, Any]) -> str:
    review = labels.get("_human_review") or {}
    return str(review.get("reviewed_at_utc") or "") if isinstance(review, dict) else ""
