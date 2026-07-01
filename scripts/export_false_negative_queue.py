#!/usr/bin/env python3
"""Export reviewer-added and unresolved approval items into a false-negative queue."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.review.decisions import (  # noqa: E402
    AUTHORIZED_REVIEWER_IDENTITY_SOURCES,
    EVENT_APPROVAL_REQUESTED,
    EVENT_DECISION_RECORDED,
    EVENT_REVIEW_STARTED,
)

SCHEMA_VERSION = "junas.false_negative_queue.v1"
SIDECAR_SCHEMA_VERSION = "junas.false_negative_candidate_sidecar.v1"
REVIEWER_ADDED_EVENT_TYPES = frozenset({"reviewer_finding_added", "finding_added", "reviewer_added_finding"})


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def _finding_index(start_payload: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        str(finding.get("id") or ""): finding
        for finding in start_payload.get("findings", [])
        if isinstance(finding, dict) and str(finding.get("id") or "")
    }


def _document_id_hash(review_id: str, start_payload: dict[str, Any], payload: dict[str, Any]) -> tuple[str, str]:
    for key in ("text_hash", "document_hash"):
        value = str(payload.get(key) or start_payload.get(key) or "").strip()
        if value:
            return _sha256(value), key
    return _sha256(review_id), "review_id"


def _matched_text_sha256(*payloads: dict[str, Any]) -> str:
    for payload in payloads:
        existing = str(payload.get("matched_text_sha256") or "").strip()
        if existing:
            return existing
    for payload in payloads:
        raw = str(payload.get("matched_text") or "")
        if raw:
            return _sha256(raw)
    return ""


def _matched_text_char_count(*payloads: dict[str, Any]) -> int | None:
    for payload in payloads:
        if payload.get("matched_text_char_count") is not None:
            return int(payload["matched_text_char_count"])
    for payload in payloads:
        raw = str(payload.get("matched_text") or "")
        if raw:
            return len(raw)
    return None


def _is_authorized_reviewer(payload: dict[str, Any]) -> bool:
    source = str(payload.get("reviewer_identity_source") or "").strip().lower()
    reviewer_id = str(payload.get("reviewer_id") or "").strip()
    return source in AUTHORIZED_REVIEWER_IDENTITY_SOURCES and bool(reviewer_id)


def _decision_keys_after(entries: list[dict[str, Any]], seq: int) -> set[tuple[str, str]]:
    keys: set[tuple[str, str]] = set()
    for entry in entries:
        if str(entry.get("event_type") or "") != EVENT_DECISION_RECORDED:
            continue
        if int(entry.get("seq", -1)) <= seq:
            continue
        payload = entry.get("payload", {})
        if isinstance(payload, dict):
            keys.add((str(entry.get("review_id") or ""), str(payload.get("finding_id") or "")))
    return keys


def _base_row(
    *,
    entry: dict[str, Any],
    start_payload: dict[str, Any],
    payload: dict[str, Any],
    signal_type: str,
    finding_id: str,
    finding: dict[str, Any],
) -> dict[str, Any]:
    review_id = str(entry.get("review_id") or "")
    document_id_hash, document_hash_source = _document_id_hash(review_id, start_payload, payload)
    queue_id = "fnq_" + _sha256(f"{signal_type}:{review_id}:{finding_id}:{entry.get('seq')}")[:20]
    reviewer_id = str(payload.get("reviewer_id") or payload.get("requester_id") or "")
    return {
        "schema_version": SCHEMA_VERSION,
        "queue_id": queue_id,
        "queue_type": "false_negative_candidate",
        "signal_type": signal_type,
        "review_id_hash": _sha256(review_id),
        "document_id_hash": document_id_hash,
        "document_hash_source": document_hash_source,
        "finding_id": finding_id,
        "source_seq": int(entry.get("seq", -1)),
        "source_ts": str(entry.get("ts") or ""),
        "source_hmac": str(entry.get("hmac") or ""),
        "reviewer_id_hash": _sha256(reviewer_id) if reviewer_id else "",
        "reviewer_identity_source": str(
            payload.get("reviewer_identity_source") or payload.get("requester_identity_source") or ""
        ),
        "decision_taxonomy": str(payload.get("decision_taxonomy") or "false_negative"),
        "reason_code": str(payload.get("reason_code") or ""),
        "rule": str(payload.get("rule") or finding.get("rule") or ""),
        "category": str(payload.get("category") or finding.get("category") or ""),
        "severity": str(payload.get("severity") or finding.get("severity") or ""),
        "jurisdiction": str(payload.get("jurisdiction") or finding.get("jurisdiction") or ""),
        "source_verification": str(payload.get("source_verification") or finding.get("source_verification") or ""),
        "matched_text_sha256": _matched_text_sha256(payload, finding),
        "matched_text_char_count": _matched_text_char_count(payload, finding),
        "requires_human_review": True,
        "raw_text_included": False,
    }


def _build_sidecar_template(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "schema_version": SIDECAR_SCHEMA_VERSION,
        "queue_id": row["queue_id"],
        "fixture_status": "template",
        "source_kind": "synthetic_required",
        "customer_sample_approved": False,
        "requires_human_review": True,
        "source": {
            "review_id_hash": row["review_id_hash"],
            "document_id_hash": row["document_id_hash"],
            "document_hash_source": row["document_hash_source"],
            "finding_id": row["finding_id"],
            "source_seq": row["source_seq"],
            "source_hmac": row["source_hmac"],
            "signal_type": row["signal_type"],
        },
        "candidate_label_template": {
            "must_detect": [],
            "ideal_must_detect": [
                {
                    "category": row["category"],
                    "rule": row["rule"],
                    "reason": "false-negative candidate signal; create synthetic reproduction before promotion",
                }
            ],
            "must_not_detect": [],
            "uncertain": [],
        },
        "privacy": {
            "raw_text_included": False,
            "matched_text_included": False,
            "matched_text_sha256": row["matched_text_sha256"],
            "matched_text_char_count": row["matched_text_char_count"],
        },
    }


def build_queue(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    starts: dict[str, dict[str, Any]] = {}
    rows: list[dict[str, Any]] = []
    resolved_after_by_seq = {
        int(entry.get("seq", -1)): _decision_keys_after(entries, int(entry.get("seq", -1)))
        for entry in entries
        if str(entry.get("event_type") or "") == EVENT_APPROVAL_REQUESTED
    }
    for entry in entries:
        review_id = str(entry.get("review_id") or "")
        event_type = str(entry.get("event_type") or "")
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if event_type == EVENT_REVIEW_STARTED:
            starts[review_id] = payload
            continue
        start_payload = starts.get(review_id, {})
        findings = _finding_index(start_payload)
        if event_type == EVENT_APPROVAL_REQUESTED and payload.get("approval_status") == "pending":
            resolved = resolved_after_by_seq.get(int(entry.get("seq", -1)), set())
            for finding_id in [str(item) for item in payload.get("finding_ids", []) if str(item)]:
                if (review_id, finding_id) in resolved:
                    continue
                finding = findings.get(finding_id, {})
                rows.append(
                    _base_row(
                        entry=entry,
                        start_payload=start_payload,
                        payload=payload,
                        signal_type="approval_required_unresolved",
                        finding_id=finding_id,
                        finding=finding,
                    )
                )
        elif event_type in REVIEWER_ADDED_EVENT_TYPES and _is_authorized_reviewer(payload):
            finding_id = str(payload.get("finding_id") or payload.get("id") or "")
            if not finding_id:
                finding_id = "reviewer_added:" + _sha256(json.dumps(payload, sort_keys=True))[:20]
            rows.append(
                _base_row(
                    entry=entry,
                    start_payload=start_payload,
                    payload=payload,
                    signal_type="reviewer_added",
                    finding_id=finding_id,
                    finding={},
                )
            )
    return rows


def write_queue(rows: list[dict[str, Any]], output: Path, sidecar_dir: Path) -> dict[str, Any]:
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    written_rows: list[dict[str, Any]] = []
    sidecars: list[str] = []
    for row in rows:
        sidecar_path = sidecar_dir / f"{row['queue_id']}.sidecar.json"
        row_with_sidecar = {**row, "candidate_sidecar_template": str(sidecar_path)}
        sidecar_path.write_text(
            json.dumps(_build_sidecar_template(row_with_sidecar), indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        written_rows.append(row_with_sidecar)
        sidecars.append(str(sidecar_path))
    output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in written_rows),
        encoding="utf-8",
    )
    return {"rows": len(written_rows), "output": str(output), "sidecars": sidecars}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export false-negative candidate signals from the review journal")
    parser.add_argument("--journal", type=Path, default=Path("junas-journal/journal.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path)
    args = parser.parse_args(argv)

    sidecar_dir = args.sidecar_dir or args.output.with_suffix("").parent / "false-negative-sidecars"
    summary = write_queue(build_queue(_entries(args.journal)), args.output, sidecar_dir)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
