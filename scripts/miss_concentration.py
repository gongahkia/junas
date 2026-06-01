#!/usr/bin/env python3
"""Summarise candidate ideal misses by detector family, jurisdiction, and bucket."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def concentration_report(bucket_report: dict[str, Any], *, examples_per_cell: int = 3) -> dict[str, Any]:
    cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_family: Counter[str] = Counter()
    by_jurisdiction: Counter[str] = Counter()
    by_bucket: Counter[str] = Counter()
    for miss in bucket_report.get("misses", []):
        family = str(miss.get("detector_family") or "unknown")
        jurisdiction = str(miss.get("source_jurisdiction") or "unknown")
        bucket = str(miss.get("bucket") or "needs_review")
        key = (family, jurisdiction, bucket)
        if key not in cells:
            cells[key] = {
                "detector_family": family,
                "jurisdiction": jurisdiction,
                "bucket": bucket,
                "miss_count": 0,
                "rules": Counter(),
                "examples": [],
            }
        cell = cells[key]
        cell["miss_count"] += 1
        cell["rules"][str(miss.get("rule") or "unknown")] += 1
        if len(cell["examples"]) < examples_per_cell:
            cell["examples"].append({
                "doc_id": miss.get("doc_id", ""),
                "path": miss.get("path", ""),
                "rule": miss.get("rule", ""),
                "matched_text": miss.get("matched_text", ""),
                "bucket_reason": miss.get("bucket_reason", ""),
            })
        by_family[family] += 1
        by_jurisdiction[jurisdiction] += 1
        by_bucket[bucket] += 1

    rendered_cells = []
    for cell in cells.values():
        rendered_cells.append({
            "detector_family": cell["detector_family"],
            "jurisdiction": cell["jurisdiction"],
            "bucket": cell["bucket"],
            "miss_count": cell["miss_count"],
            "rules": dict(sorted(cell["rules"].items())),
            "examples": cell["examples"],
        })
    rendered_cells.sort(
        key=lambda item: (
            -item["miss_count"],
            item["detector_family"],
            item["jurisdiction"],
            item["bucket"],
        )
    )

    return {
        "generated_at_unix": int(time.time()),
        "source_review_profile": bucket_report.get("source_review_profile", "unknown"),
        "summary": {
            "miss_count": sum(by_bucket.values()),
            "by_bucket": dict(sorted(by_bucket.items())),
            "by_detector_family": dict(sorted(by_family.items())),
            "by_jurisdiction": dict(sorted(by_jurisdiction.items())),
        },
        "cells": rendered_cells,
        "note": (
            "concentration report over item-124 heuristic buckets; "
            "inspect examples before prioritising detector work."
        ),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build ideal-miss concentration report from bucketed misses")
    parser.add_argument("--bucket-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Write concentration JSON")
    parser.add_argument("--examples-per-cell", type=int, default=3)
    args = parser.parse_args(argv)

    bucket_report_path = args.bucket_report if args.bucket_report.is_absolute() else REPO_ROOT / args.bucket_report
    if not bucket_report_path.exists():
        print(f"bucket report missing: {bucket_report_path}", file=sys.stderr)
        return 2
    payload = concentration_report(_read_json(bucket_report_path), examples_per_cell=max(0, args.examples_per_cell))
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"wrote {output}")
    else:
        print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
