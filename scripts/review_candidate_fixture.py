#!/usr/bin/env python3
"""Record human review status for a candidate fixture labels file."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from scripts.candidate_review import labels_path_for, load_labels, record_human_review, write_labels  # noqa: E402
from scripts.evaluate_candidate_corpus import _evaluate_one  # noqa: E402


def _summary(fixture_path: Path, labels: dict) -> dict:
    try:
        report = _evaluate_one(fixture_path)
        engine = {
            "matched": len(report.matched),
            "missed": len(report.missed),
            "unexpected": len(report.unexpected),
            "must_not_detect_violations": len(report.must_not_detect_violations),
            "uncertain": len(report.uncertain),
        }
    except Exception as exc:  # noqa: BLE001
        engine = {"error": str(exc)}
    return {
        "fixture": str(fixture_path),
        "labels": str(labels_path_for(fixture_path)),
        "doc_id": labels.get("doc_id"),
        "source_jurisdiction": labels.get("source_jurisdiction"),
        "destination_jurisdiction": labels.get("destination_jurisdiction"),
        "document_type": labels.get("document_type"),
        "taxonomy_concept": labels.get("_taxonomy_concept"),
        "label_source": labels.get("_label_source"),
        "label_model": labels.get("_label_model"),
        "human_review_status": labels.get("_human_review_status"),
        "must_detect": len(labels.get("must_detect", []) or []),
        "must_not_detect": len(labels.get("must_not_detect", []) or []),
        "uncertain": len(labels.get("uncertain", []) or []),
        "engine": engine,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Record human review for a candidate fixture")
    parser.add_argument("fixture_path", type=Path)
    parser.add_argument("--decision", choices=("approve", "reject", "needs_edit"))
    parser.add_argument("--reviewer", default="")
    parser.add_argument("--notes", default="")
    parser.add_argument("--show-only", action="store_true", help="print summary without writing review metadata")
    args = parser.parse_args(argv)

    fixture_path = args.fixture_path if args.fixture_path.is_absolute() else REPO_ROOT / args.fixture_path
    labels_path = labels_path_for(fixture_path)
    if not fixture_path.exists():
        print(f"fixture missing: {fixture_path}", file=sys.stderr)
        return 2
    if not labels_path.exists():
        print(f"labels missing: {labels_path}", file=sys.stderr)
        return 2
    try:
        labels = load_labels(labels_path)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"labels unreadable: {exc}", file=sys.stderr)
        return 2

    before = _summary(fixture_path, labels)
    print(json.dumps(before, indent=2, sort_keys=True))
    if args.show_only:
        return 0
    if not args.decision or not args.reviewer.strip():
        print("--decision and --reviewer are required unless --show-only is set", file=sys.stderr)
        return 2
    try:
        updated = record_human_review(
            labels,
            decision=args.decision,
            reviewer=args.reviewer,
            notes=args.notes,
        )
    except ValueError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    write_labels(labels_path, updated)
    print(f"recorded {updated['_human_review_status']} review in {labels_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
