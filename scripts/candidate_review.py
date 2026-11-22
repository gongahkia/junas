"""Helpers for human review and promotion of candidate fixture labels."""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

VALID_DECISIONS = frozenset({"approve", "reject", "needs_edit"})
APPROVED_STATUS = "approved"
STAGE_B_READY_STATUS = "stage_b_ready"
DETECTOR_DERIVED_PROVENANCE_RE = re.compile(
    r"promoted from strict runtime|strict runtime baseline reconciliation|"
    r"strict runtime finding|runtime promotion|runtime-derived|detector-derived",
    re.IGNORECASE,
)


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


def is_stage_a_candidate_label(labels_path: Path, labels: dict[str, Any]) -> bool:
    if not is_candidate_label(labels):
        return False
    doc_id = str(labels.get("doc_id") or labels_path.name.removesuffix(".labels.json"))
    return "_memo_" in doc_id or "_memo_" in labels_path.name


def is_human_approved(labels: dict[str, Any]) -> bool:
    if str(labels.get("_human_review_status") or "") != APPROVED_STATUS:
        return False
    review = labels.get("_human_review")
    return isinstance(review, dict) and bool(str(review.get("reviewer") or "").strip())


def is_stage_b_ready(labels: dict[str, Any]) -> bool:
    readiness = labels.get("_stage_readiness")
    if not isinstance(readiness, dict):
        return False
    return (
        str(readiness.get("status") or "") == STAGE_B_READY_STATUS
        and str(readiness.get("stage_a") or "") == "reviewed"
        and str(readiness.get("stage_b") or "") == "ready"
        and bool(str(readiness.get("reviewer") or "").strip())
    )


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


def collect_review_status_violations(corpus_dir: Path, *, stage_a_only: bool = False) -> list[str]:
    violations: list[str] = []
    for labels_path in sorted(corpus_dir.glob("**/*.labels.json")):
        try:
            labels = load_labels(labels_path)
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"{labels_path}: labels unreadable: {exc}")
            continue
        if stage_a_only and not is_stage_a_candidate_label(labels_path, labels):
            continue
        violation = review_status_violation(labels_path, labels)
        if violation:
            violations.append(violation)
    return violations


def is_detector_derived_provenance(text: str) -> bool:
    return bool(DETECTOR_DERIVED_PROVENANCE_RE.search(text or ""))


def label_item_has_detector_provenance(item: dict[str, Any]) -> bool:
    """Historical item marker filter; absence does not establish independence."""
    return is_detector_derived_provenance(str(item.get("reason") or ""))


def labels_have_detector_source(labels: dict[str, Any]) -> bool:
    """Historical source-string filter retained for locks and provenance sidecars."""
    return is_detector_derived_provenance(str(labels.get("_label_source") or ""))


def detector_provenance_violations(labels_path: Path, labels: dict[str, Any]) -> list[str]:
    violations: list[str] = []
    source = str(labels.get("_label_source") or "")
    if labels_have_detector_source(labels):
        violations.append(f"{labels_path}: _label_source indicates runtime promotion: {source}")
    for section in ("must_detect", "ideal_must_detect", "must_not_detect", "uncertain"):
        items = labels.get(section, [])
        if not isinstance(items, list):
            continue
        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            reason = str(item.get("reason") or "")
            if is_detector_derived_provenance(reason):
                violations.append(f"{labels_path}: {section}[{idx}].reason indicates runtime promotion: {reason}")
    return violations


def collect_detector_provenance_violations(corpus_dir: Path) -> list[str]:
    violations: list[str] = []
    for labels_path in sorted(corpus_dir.glob("**/*.labels.json")):
        try:
            labels = load_labels(labels_path)
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"{labels_path}: labels unreadable: {exc}")
            continue
        violations.extend(detector_provenance_violations(labels_path, labels))
    return violations


def stage_b_readiness_violation(labels_path: Path, labels: dict[str, Any]) -> str:
    if not is_stage_a_candidate_label(labels_path, labels):
        return ""
    if not is_candidate_label(labels):
        return ""
    if is_stage_b_ready(labels):
        return ""
    readiness = labels.get("_stage_readiness")
    status = "missing"
    if isinstance(readiness, dict):
        status = str(readiness.get("status") or "missing")
    return f"{labels_path}: candidate label stage_b_readiness={status}"


def collect_stage_b_readiness_violations(corpus_dir: Path) -> list[str]:
    violations: list[str] = []
    for labels_path in sorted(corpus_dir.glob("**/*.labels.json")):
        try:
            labels = load_labels(labels_path)
        except (OSError, json.JSONDecodeError) as exc:
            violations.append(f"{labels_path}: labels unreadable: {exc}")
            continue
        violation = stage_b_readiness_violation(labels_path, labels)
        if violation:
            violations.append(violation)
    return violations


def approved_reviewer(labels: dict[str, Any]) -> str:
    review = labels.get("_human_review") or {}
    return str(review.get("reviewer") or "") if isinstance(review, dict) else ""


def approved_reviewed_at(labels: dict[str, Any]) -> str:
    review = labels.get("_human_review") or {}
    return str(review.get("reviewed_at_utc") or "") if isinstance(review, dict) else ""


def assess_annotation_provenance(labels: dict[str, Any], item: dict[str, Any] | None = None) -> dict[str, Any]:
    """Conservative v1 audit; historical exclusion filters above remain unchanged."""
    item = item or {}
    metadata = {key: value for key, value in labels.items() if key.startswith("_")}
    item_metadata = {
        key: value
        for key, value in item.items()
        if key in {"reason", "annotation_provenance", "provenance", "label_source", "label_model"}
    }
    evidence = json.dumps({"metadata": metadata, "item": item_metadata}, sort_keys=True).lower()
    categories: set[str] = set()
    reconciled = any("reconcil" in key or "strict_realign" in key or key == "_strict_label_cleanup" for key in metadata)
    reconciled |= bool(re.search(r"detector.aligned|detector.reconcil|runtime.*reconcil", evidence))
    derived = is_detector_derived_provenance(evidence)
    if reconciled:
        categories.add("reconciled_against_detector_output")
    if derived:
        categories.add("detector_derived")
    model_name = str(labels.get("_label_model") or "").strip().lower()
    origin_evidence = json.dumps(
        {key: labels.get(key) for key in ("_label_model", "_label_source", "_label_note")}, sort_keys=True
    ).lower()
    model = model_name not in {"", "none", "manual", "human", "n/a"} or bool(
        re.search(r"auto.label|gpt|model.generated", origin_evidence)
    )
    if model:
        categories.add("model_derived")
        if is_human_approved(labels):
            categories.add("human_reviewed_model_proposals")
    if labels.get("_generation_note") or model or "synthetic" in str(labels.get("_label_source", "")).lower():
        categories.add("synthetic_generated_labels")
    protocol = item.get("annotation_provenance", labels.get("_annotation_provenance", {}))
    declared = (
        isinstance(protocol, dict)
        and protocol.get("origin") == "independent_human"
        and (
            protocol.get("blinded_to_detector") is True
            and bool(protocol.get("author"))
            and bool(protocol.get("protocol_id"))
        )
    )
    if declared:
        categories.add("declared_independent_human_annotations")
    if not categories:
        categories.add("unknown_or_insufficient")
    return {
        "schema_version": "junas.annotation_provenance.v1",
        "categories": sorted(categories),
        "human_review_recorded": is_human_approved(labels),
        "independence_status": "declared_not_verified"
        if declared and not (model or derived or reconciled)
        else "not_established",
        "note": "Metadata declarations are not independent verification; reconciliation markers apply file-wide.",
        "classification_basis": (
            "Recorded metadata, not authenticated authorship or item-by-item derivation reconstruction."
        ),
    }
