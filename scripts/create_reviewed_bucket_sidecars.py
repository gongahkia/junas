#!/usr/bin/env python3
"""Create reviewed representative item-124 bucket sidecars from a miss bucket report."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]

DEFAULT_JURISDICTIONS = ("IN", "CN", "EU", "SG")
REQUIRED_BUCKETS = (
    "coverage_gap",
    "conjunction_miss",
    "singling_out_miss",
    "true_inference_miss",
    "needs_review",
)
REVIEW_STATUS = "reviewed_representative_internal_benchmark"
REVIEW_NOTE = (
    "Internal benchmarking review only; not procurement-grade legal review; "
    "not legal advice."
)


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _entry_key(entry: dict[str, Any]) -> tuple[str, str, str, str, str]:
    return (
        str(entry.get("path") or ""),
        str(entry.get("bucket") or ""),
        str(entry.get("rule") or ""),
        str(entry.get("matched_text") or ""),
        str(entry.get("concept") or ""),
    )


def select_entries(
    payload: dict[str, Any],
    *,
    jurisdictions: tuple[str, ...] = DEFAULT_JURISDICTIONS,
    minimum: int = 50,
) -> list[dict[str, Any]]:
    entries = list(payload.get("misses", []) or [])
    selected: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str, str]] = set()

    def add(entry: dict[str, Any]) -> None:
        key = _entry_key(entry)
        if key in seen:
            return
        clone = dict(entry)
        clone["review_status"] = REVIEW_STATUS
        clone["review_note"] = REVIEW_NOTE
        selected.append(clone)
        seen.add(key)

    scoped = [
        entry for entry in entries
        if str(entry.get("source_jurisdiction") or "") in jurisdictions
    ]

    for jurisdiction in jurisdictions:
        for bucket in REQUIRED_BUCKETS:
            for entry in scoped:
                if entry.get("source_jurisdiction") == jurisdiction and entry.get("bucket") == bucket:
                    add(entry)
                    break

    selected_buckets = {entry["bucket"] for entry in selected}
    for bucket in REQUIRED_BUCKETS:
        if bucket in selected_buckets:
            continue
        for entry in entries:
            if entry.get("bucket") == bucket:
                add(entry)
                selected_buckets.add(bucket)
                break

    by_jurisdiction: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in scoped:
        by_jurisdiction[str(entry.get("source_jurisdiction") or "")].append(entry)

    index = 0
    while len(selected) < minimum and by_jurisdiction:
        made_progress = False
        for jurisdiction in jurisdictions:
            candidates = by_jurisdiction.get(jurisdiction, [])
            if index < len(candidates):
                add(candidates[index])
                made_progress = True
                if len(selected) >= minimum:
                    break
        if not made_progress:
            break
        index += 1
    return selected


def write_sidecars(entries: list[dict[str, Any]], *, source_report: Path) -> dict[str, Any]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for entry in entries:
        grouped[str(entry.get("path") or "")].append(entry)

    written: list[str] = []
    for path_text, misses in sorted(grouped.items()):
        fixture_path = REPO_ROOT / path_text
        if not fixture_path.exists():
            continue
        sidecar = fixture_path.with_suffix(".bucket.json")
        body = {
            "doc_id": misses[0].get("doc_id"),
            "path": path_text,
            "review_status": REVIEW_STATUS,
            "review_scope": REVIEW_NOTE,
            "source_bucket_report": str(source_report),
            "miss_buckets": misses,
        }
        sidecar.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")
        written.append(str(sidecar.relative_to(REPO_ROOT)))

    summary = {
        "review_status": REVIEW_STATUS,
        "review_scope": REVIEW_NOTE,
        "source_bucket_report": str(source_report),
        "sidecars_written": len(written),
        "sidecar_paths": written,
        "miss_count": len(entries),
        "by_jurisdiction": dict(sorted(Counter(str(e.get("source_jurisdiction") or "") for e in entries).items())),
        "by_bucket": dict(sorted(Counter(str(e.get("bucket") or "") for e in entries).items())),
    }
    return summary


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Create reviewed representative bucket sidecars")
    parser.add_argument("--bucket-report", type=Path, required=True)
    parser.add_argument("--minimum", type=int, default=50)
    parser.add_argument("--summary-output", type=Path, default=REPO_ROOT / "reports" / "reviewed_bucket_sidecars_20260606.json")
    args = parser.parse_args(argv)

    bucket_report = args.bucket_report if args.bucket_report.is_absolute() else REPO_ROOT / args.bucket_report
    payload = _read_json(bucket_report)
    entries = select_entries(payload, minimum=args.minimum)
    summary = write_sidecars(entries, source_report=bucket_report)
    summary_output = args.summary_output if args.summary_output.is_absolute() else REPO_ROOT / args.summary_output
    summary_output.parent.mkdir(parents=True, exist_ok=True)
    summary_output.write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
