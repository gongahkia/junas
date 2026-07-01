#!/usr/bin/env python3
"""Export authorized reviewer rejects into a privacy-safe false-positive queue."""

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
    EVENT_DECISION_RECORDED,
    EVENT_REVIEW_STARTED,
    REJECT_ACTIONS,
)

SCHEMA_VERSION = "junas.false_positive_queue.v1"
SIDECAR_SCHEMA_VERSION = "junas.false_positive_fixture_sidecar.v1"


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


def _document_id_hash(review_id: str, start_payload: dict[str, Any]) -> tuple[str, str]:
    text_hash = str(start_payload.get("text_hash") or "").strip()
    if text_hash:
        return _sha256(text_hash), "text_hash"
    return _sha256(review_id), "review_id"


def _is_authorized_reject(payload: dict[str, Any]) -> bool:
    source = str(payload.get("reviewer_identity_source") or "").strip().lower()
    reviewer_id = str(payload.get("reviewer_id") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    return action in REJECT_ACTIONS and source in AUTHORIZED_REVIEWER_IDENTITY_SOURCES and bool(reviewer_id)


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
            "decision_seq": row["decision_seq"],
            "decision_hmac": row["decision_hmac"],
        },
        "detector_issue_category": row["detector_issue_category"],
        "decision_taxonomy": row["decision_taxonomy"],
        "rule": row["rule"],
        "category": row["category"],
        "severity": row["severity"],
        "jurisdiction": row["jurisdiction"],
        "must_not_detect": [
            {
                "category": row["category"],
                "rule": row["rule"],
                "reason": "authorized reviewer rejected this finding; create synthetic reproduction before promotion",
            }
        ],
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
    for entry in entries:
        review_id = str(entry.get("review_id") or "")
        event_type = str(entry.get("event_type") or "")
        payload = entry.get("payload", {})
        if not isinstance(payload, dict):
            continue
        if event_type == EVENT_REVIEW_STARTED:
            starts[review_id] = payload
            continue
        if event_type != EVENT_DECISION_RECORDED or not _is_authorized_reject(payload):
            continue
        start_payload = starts.get(review_id, {})
        finding = _finding_index(start_payload).get(str(payload.get("finding_id") or ""))
        if not finding:
            continue
        detector_feedback = payload.get("detector_feedback", {})
        if not isinstance(detector_feedback, dict):
            detector_feedback = {}
        document_id_hash, document_hash_source = _document_id_hash(review_id, start_payload)
        queue_id = "fpq_" + _sha256(f"{review_id}:{payload.get('finding_id')}:{entry.get('seq')}")[:20]
        rows.append(
            {
                "schema_version": SCHEMA_VERSION,
                "queue_id": queue_id,
                "queue_type": "false_positive_review",
                "review_id_hash": _sha256(review_id),
                "document_id_hash": document_id_hash,
                "document_hash_source": document_hash_source,
                "finding_id": str(payload.get("finding_id") or ""),
                "decision_seq": int(entry.get("seq", -1)),
                "decision_ts": str(entry.get("ts") or ""),
                "decision_hmac": str(entry.get("hmac") or ""),
                "reviewer_id_hash": _sha256(str(payload.get("reviewer_id") or "")),
                "reviewer_identity_source": str(payload.get("reviewer_identity_source") or ""),
                "action": str(payload.get("action") or ""),
                "decision_taxonomy": str(payload.get("decision_taxonomy") or ""),
                "reviewer_confidence": payload.get("reviewer_confidence"),
                "detector_issue_category": str(detector_feedback.get("detector_issue_category") or ""),
                "rule": str(finding.get("rule") or ""),
                "category": str(finding.get("category") or ""),
                "severity": str(finding.get("severity") or ""),
                "jurisdiction": str(finding.get("jurisdiction") or ""),
                "source_verification": str(finding.get("source_verification") or ""),
                "matched_text_sha256": str(finding.get("matched_text_sha256") or ""),
                "matched_text_char_count": finding.get("matched_text_char_count"),
                "requires_human_review": True,
                "raw_text_included": False,
            }
        )
    return rows


def write_queue(rows: list[dict[str, Any]], output: Path, sidecar_dir: Path) -> dict[str, Any]:
    sidecar_dir.mkdir(parents=True, exist_ok=True)
    output.parent.mkdir(parents=True, exist_ok=True)
    written_rows: list[dict[str, Any]] = []
    sidecars: list[str] = []
    for row in rows:
        sidecar_path = sidecar_dir / f"{row['queue_id']}.sidecar.json"
        row_with_sidecar = {**row, "fixture_sidecar_template": str(sidecar_path)}
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
    parser = argparse.ArgumentParser(description="Export authorized reviewer rejects into a false-positive queue")
    parser.add_argument("--journal", type=Path, default=Path("junas-journal/journal.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--sidecar-dir", type=Path)
    args = parser.parse_args(argv)

    sidecar_dir = args.sidecar_dir or args.output.with_suffix("").parent / "false-positive-sidecars"
    summary = write_queue(build_queue(_entries(args.journal)), args.output, sidecar_dir)
    print(json.dumps(summary, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
