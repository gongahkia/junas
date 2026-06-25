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


def _rate(miss_count: int, doc_count: int) -> dict[str, Any]:
    return {
        "miss_count": miss_count,
        "doc_count": doc_count,
        "misses_per_doc": round(miss_count / doc_count, 4) if doc_count else None,
        "misses_per_100_docs": round((miss_count / doc_count) * 100, 2) if doc_count else None,
    }


def _doc_counts_by_jurisdiction(bucket_report: dict[str, Any]) -> dict[str, int]:
    summary = bucket_report.get("summary", {})
    raw = summary.get("doc_count_by_jurisdiction")
    if isinstance(raw, dict) and raw:
        return {str(key): int(value) for key, value in raw.items()}
    fallback: dict[str, set[str]] = {}
    for miss in bucket_report.get("misses", []):
        jurisdiction = str(miss.get("source_jurisdiction") or "unknown")
        path = str(miss.get("path") or miss.get("doc_id") or "")
        fallback.setdefault(jurisdiction, set()).add(path)
    return {key: len(value) for key, value in fallback.items()}


def concentration_report(bucket_report: dict[str, Any], *, examples_per_cell: int = 3) -> dict[str, Any]:
    cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    by_family: Counter[str] = Counter()
    by_jurisdiction: Counter[str] = Counter()
    by_bucket: Counter[str] = Counter()
    doc_counts = _doc_counts_by_jurisdiction(bucket_report)
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
        rate = _rate(cell["miss_count"], doc_counts.get(cell["jurisdiction"], 0))
        rendered_cells.append({
            "detector_family": cell["detector_family"],
            "jurisdiction": cell["jurisdiction"],
            "bucket": cell["bucket"],
            "miss_count": cell["miss_count"],
            "doc_count": rate["doc_count"],
            "misses_per_doc": rate["misses_per_doc"],
            "misses_per_100_docs": rate["misses_per_100_docs"],
            "rules": dict(sorted(cell["rules"].items())),
            "examples": cell["examples"],
        })
    rendered_cells.sort(
        key=lambda item: (
            -(item["misses_per_100_docs"] or 0),
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
            "doc_count_by_jurisdiction": dict(sorted(doc_counts.items())),
            "by_jurisdiction_normalized": {
                jurisdiction: _rate(miss_count, doc_counts.get(jurisdiction, 0))
                for jurisdiction, miss_count in sorted(by_jurisdiction.items())
            },
        },
        "cells": rendered_cells,
        "note": (
            "concentration report over item-124 heuristic buckets; "
            "inspect examples before prioritising detector work."
        ),
    }


def _format_counter(counter: dict[str, Any], *, limit: int = 10) -> str:
    items = sorted(counter.items(), key=lambda item: (-int(item[1]), item[0]))[:limit]
    return ", ".join(f"{key}: {value}" for key, value in items)


def _format_normalized(counter: dict[str, Any], *, limit: int = 10) -> str:
    items = sorted(
        counter.items(),
        key=lambda item: (
            -float(item[1].get("misses_per_100_docs") or 0),
            -int(item[1].get("miss_count") or 0),
            item[0],
        ),
    )[:limit]
    return ", ".join(
        f"{key}: {value.get('misses_per_100_docs')} per 100 docs ({value.get('miss_count')} raw)"
        for key, value in items
    )


def render_markdown(payload: dict[str, Any], *, max_cells: int = 20) -> str:
    summary = payload.get("summary", {})
    lines = [
        "# Miss Concentration",
        "",
        "This is a heuristic ideal-miss concentration report. Inspect examples before prioritising detector work.",
        "Raw jurisdiction counts reflect fixture volume; compare jurisdictions only at like-for-like stage sizes.",
        "",
        "## Summary",
        "",
        f"- Review profile: {payload.get('source_review_profile', 'unknown')}",
        f"- Miss count: {summary.get('miss_count', 0)}",
        f"- Buckets: {_format_counter(summary.get('by_bucket', {}))}",
        f"- Detector families: {_format_counter(summary.get('by_detector_family', {}))}",
        f"- Jurisdictions by raw misses: {_format_counter(summary.get('by_jurisdiction', {}))}",
        f"- Jurisdictions by misses per 100 docs: {_format_normalized(summary.get('by_jurisdiction_normalized', {}))}",
        "",
        "## Top Cells",
        "",
        "| Detector family | Jurisdiction | Bucket | Misses | Docs | Misses / 100 docs | Top rules | Example |",
        "|---|---|---|---:|---:|---:|---|---|",
    ]
    for cell in payload.get("cells", [])[:max_cells]:
        rules = _format_counter(cell.get("rules", {}), limit=4)
        examples = cell.get("examples", [])
        example = ""
        if examples:
            first = examples[0]
            matched = str(first.get("matched_text") or "").replace("|", "\\|")
            if len(matched) > 80:
                matched = matched[:77] + "..."
            example = f"{first.get('path', '')}: `{matched}`"
        lines.append(
            "| {family} | {jurisdiction} | {bucket} | {misses} | {docs} | {rate} | {rules} | {example} |".format(
                family=cell.get("detector_family", ""),
                jurisdiction=cell.get("jurisdiction", ""),
                bucket=cell.get("bucket", ""),
                misses=cell.get("miss_count", 0),
                docs=cell.get("doc_count", 0),
                rate="" if cell.get("misses_per_100_docs") is None else cell.get("misses_per_100_docs"),
                rules=rules.replace("|", "\\|"),
                example=example,
            )
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build ideal-miss concentration report from bucketed misses")
    parser.add_argument("--bucket-report", type=Path, required=True)
    parser.add_argument("--output", type=Path, help="Write concentration JSON")
    parser.add_argument("--markdown-output", type=Path, help="Write Markdown report")
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
    if args.markdown_output:
        markdown_output = (
            args.markdown_output
            if args.markdown_output.is_absolute()
            else REPO_ROOT / args.markdown_output
        )
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(payload), encoding="utf-8")
        print(f"wrote {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
