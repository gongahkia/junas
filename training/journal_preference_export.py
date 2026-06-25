#!/usr/bin/env python3
"""Sanitise review decisions into preference-training pairs.

This reads Junas's HMAC journal and emits JSONL suitable for item 30 DPO
preparation. It does not train a model and does not include matched text.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from junas.review.decisions import POSITIVE_CORPUS_ACTIONS, REJECT_ACTIONS  # noqa: E402

SENSITIVE_RE = re.compile(
    r"(?i)([A-Z]\d{7,9}[A-Z]?|\b\d{3}-?\d{2}-?\d{4}\b|"
    r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b|"
    r"\+?\d[\d\s().-]{6,}\d)"
)


def _clean(value: str) -> str:
    return SENSITIVE_RE.sub("[REDACTED]", value).strip()


def _load_entries(path: Path) -> list[dict[str, Any]]:
    entries: list[dict[str, Any]] = []
    if not path.exists():
        return entries
    for line in path.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        entries.append(json.loads(line))
    return entries


def export_preferences(journal_path: Path) -> list[dict[str, Any]]:
    entries = _load_entries(journal_path)
    findings_by_review: dict[str, dict[str, dict[str, Any]]] = {}
    rows: list[dict[str, Any]] = []
    for entry in entries:
        if entry.get("event_type") == "review_started":
            findings_by_review[str(entry.get("review_id"))] = {
                str(finding.get("id")): finding
                for finding in entry.get("payload", {}).get("findings", [])
                if isinstance(finding, dict)
            }
            continue
        if entry.get("event_type") != "decision_recorded":
            continue
        review_id = str(entry.get("review_id") or "")
        payload = entry.get("payload", {})
        finding = findings_by_review.get(review_id, {}).get(str(payload.get("finding_id") or ""))
        if not finding:
            continue
        action = str(payload.get("action") or "")
        if action not in POSITIVE_CORPUS_ACTIONS and action not in REJECT_ACTIONS:
            continue
        rows.append(
            {
                "review_id": review_id,
                "finding_id": str(payload.get("finding_id") or ""),
                "chosen": "accept" if action in POSITIVE_CORPUS_ACTIONS else "reject",
                "rejected": "reject" if action in POSITIVE_CORPUS_ACTIONS else "accept",
                "rule": str(finding.get("rule") or ""),
                "category": str(finding.get("category") or ""),
                "severity": str(finding.get("severity") or ""),
                "jurisdiction": str(finding.get("jurisdiction") or ""),
                "rationale": _clean(str(payload.get("rationale") or "")),
                "reviewer_identity_source": str(payload.get("reviewer_identity_source") or ""),
                "sanitized": True,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Export sanitized DPO preference pairs from a Junas journal")
    parser.add_argument("--journal", type=Path, default=Path("junas-journal/journal.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = export_preferences(args.journal)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True, ensure_ascii=False) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
