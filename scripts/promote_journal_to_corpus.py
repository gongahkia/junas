#!/usr/bin/env python3
"""Queue journal decisions for corpus promotion review.

The script does not add fixtures to locked corpora. It emits a JSONL queue of
accepted misses and rejected findings for human review before any recall lock
change.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.decisions import POSITIVE_CORPUS_ACTIONS, REJECT_ACTIONS  # noqa: E402


def _entries(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    return [
        json.loads(line)
        for line in path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]


def build_queue(journal: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    starts: dict[str, dict[str, Any]] = {}
    for entry in _entries(journal):
        review_id = str(entry.get("review_id") or "")
        if entry.get("event_type") == "review_started":
            starts[review_id] = entry.get("payload", {})
            continue
        if entry.get("event_type") != "decision_recorded":
            continue
        payload = entry.get("payload", {})
        action = str(payload.get("action") or "")
        findings = {
            str(finding.get("id")): finding
            for finding in starts.get(review_id, {}).get("findings", [])
            if isinstance(finding, dict)
        }
        finding = findings.get(str(payload.get("finding_id") or ""))
        if not finding:
            continue
        if action not in POSITIVE_CORPUS_ACTIONS and action not in REJECT_ACTIONS:
            continue
        rows.append(
            {
                "review_id": review_id,
                "finding_id": str(payload.get("finding_id") or ""),
                "action": action,
                "queue": (
                    "positive_candidate"
                    if action in POSITIVE_CORPUS_ACTIONS
                    else "adversarial_candidate"
                ),
                "rule": str(finding.get("rule") or ""),
                "category": str(finding.get("category") or ""),
                "severity": str(finding.get("severity") or ""),
                "jurisdiction": str(finding.get("jurisdiction") or ""),
                "matched_text_hash": str(
                    finding.get("context_window_hash") or finding.get("body_hash") or ""
                ),
                "requires_human_review": True,
            }
        )
    return rows


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Queue journal decisions for human-reviewed corpus promotion")
    parser.add_argument("--journal", type=Path, default=Path("kaypoh-journal/journal.jsonl"))
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    rows = build_queue(args.journal)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "".join(json.dumps(row, sort_keys=True) + "\n" for row in rows),
        encoding="utf-8",
    )
    print(json.dumps({"rows": len(rows), "output": str(args.output)}, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
