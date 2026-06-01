#!/usr/bin/env python3
"""Summarise auto-label QA warnings and candidate eval triage."""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.candidate_corpus_report import DEFAULT_CORPUS  # noqa: E402


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def warning_bucket(warning: str) -> str:
    text = warning.casefold()
    if "invalid rule" in text:
        return "invalid_rule"
    if "valid singapore nric/fin" in text or "valid singapore uen" in text:
        return "must_not_conflicts_with_valid_sg_identifier"
    if "text not verbatim" in text:
        return "non_verbatim_span"
    if "empty text" in text:
        return "empty_span"
    if "normalise mismatched category" in text or "normalise category" in text:
        return "category_normalized"
    if text.startswith("drop must_not_detect"):
        return "must_not_dropped"
    if text.startswith("drop uncertain"):
        return "uncertain_dropped"
    if text.startswith("drop ideal_must_detect"):
        return "ideal_dropped"
    if text.startswith("drop must_detect"):
        return "strict_dropped"
    return "other"


def _warning_rule(warning: str) -> str:
    match = re.search(r"rule='([^']+)'|rule=\"([^\"]+)\"", warning)
    if not match:
        return ""
    return match.group(1) or match.group(2) or ""


def _labels_summary(corpus: Path) -> dict[str, Any]:
    warning_counts: Counter[str] = Counter()
    warning_rules: Counter[str] = Counter()
    files_with_warnings: list[dict[str, Any]] = []
    label_sources: Counter[str] = Counter()
    label_models: Counter[str] = Counter()
    review_status: Counter[str] = Counter()
    for labels_path in sorted(corpus.glob("**/*.labels.json")):
        payload = _read_json(labels_path)
        label_sources[str(payload.get("_label_source") or "unknown")] += 1
        label_models[str(payload.get("_label_model") or "unknown")] += 1
        review_status[str(payload.get("_human_review_status") or "missing")] += 1
        warnings = [str(item) for item in payload.get("_label_warnings", [])]
        if not warnings:
            continue
        buckets = Counter(warning_bucket(item) for item in warnings)
        warning_counts.update(buckets)
        for item in warnings:
            rule = _warning_rule(item)
            if rule:
                warning_rules[rule] += 1
        files_with_warnings.append({
            "path": _relative(labels_path),
            "warning_count": len(warnings),
            "buckets": dict(sorted(buckets.items())),
            "warnings": warnings[:10],
        })
    files_with_warnings.sort(key=lambda item: (-item["warning_count"], item["path"]))
    return {
        "label_file_count": sum(review_status.values()),
        "review_status": dict(sorted(review_status.items())),
        "label_sources": dict(sorted(label_sources.items())),
        "label_models": dict(sorted(label_models.items())),
        "warning_count": sum(warning_counts.values()),
        "warning_buckets": dict(sorted(warning_counts.items())),
        "warning_rules": dict(sorted(warning_rules.items())),
        "files_with_warnings": files_with_warnings,
    }


def _eval_summary(eval_report: Path | None) -> dict[str, Any]:
    if not eval_report:
        return {}
    payload = _read_json(eval_report)
    summary = payload.get("summary", {})
    triage: Counter[str] = Counter()
    worst_docs: list[dict[str, Any]] = []
    for doc in payload.get("documents", []):
        unexpected = len(doc.get("unexpected", []))
        missed = len(doc.get("missed", []))
        must_not = len(doc.get("must_not_detect_violations", []))
        for item in doc.get("unexpected_triage", []):
            triage[str(item.get("bucket") or "unknown")] += 1
        score = unexpected + missed + must_not
        if score:
            worst_docs.append({
                "doc_id": doc.get("doc_id", ""),
                "path": doc.get("path", ""),
                "missed": missed,
                "unexpected": unexpected,
                "must_not_detect_violations": must_not,
            })
    worst_docs.sort(key=lambda item: (-(item["missed"] + item["unexpected"] + item["must_not_detect_violations"]), item["path"]))
    return {
        "eval_report": _relative(eval_report),
        "doc_count": summary.get("doc_count"),
        "candidate_recall": summary.get("candidate_recall"),
        "candidate_precision": summary.get("candidate_precision"),
        "ideal_candidate_recall": summary.get("ideal_candidate_recall"),
        "missed": summary.get("missed"),
        "unexpected": summary.get("unexpected"),
        "must_not_detect_violations": summary.get("must_not_detect_violations"),
        "unexpected_triage": dict(sorted((summary.get("unexpected_triage") or triage).items())),
        "worst_docs": worst_docs[:20],
    }


def _bucket_summary(bucket_report: Path | None) -> dict[str, Any]:
    if not bucket_report:
        return {}
    payload = _read_json(bucket_report)
    summary = payload.get("summary", {})
    return {
        "bucket_report": _relative(bucket_report),
        "miss_count": summary.get("miss_count"),
        "by_bucket": summary.get("by_bucket", {}),
        "by_detector_family": summary.get("by_detector_family", {}),
        "by_jurisdiction": summary.get("by_jurisdiction", {}),
    }


def build_report(
    corpus: Path,
    *,
    eval_report: Path | None = None,
    bucket_report: Path | None = None,
) -> dict[str, Any]:
    corpus = corpus.resolve()
    eval_report = eval_report.resolve() if eval_report else None
    bucket_report = bucket_report.resolve() if bucket_report else None
    return {
        "generated_at_unix": int(time.time()),
        "corpus": _relative(corpus),
        "labels": _labels_summary(corpus),
        "evaluation": _eval_summary(eval_report),
        "ideal_miss_buckets": _bucket_summary(bucket_report),
        "note": "auto-label QA report; warnings and heuristic buckets require human spot-check before baseline promotion.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    labels = report["labels"]
    evaluation = report.get("evaluation") or {}
    buckets = report.get("ideal_miss_buckets") or {}
    lines = [
        "# Auto-label QA Report",
        "",
        "Warnings and heuristic buckets are review queues, not legal truth.",
        "",
        "## Label Warnings",
        "",
        f"- Label files: {labels['label_file_count']}",
        f"- Warning count: {labels['warning_count']}",
        f"- Review status: {labels['review_status']}",
        f"- Warning buckets: {labels['warning_buckets']}",
    ]
    if evaluation:
        lines.extend([
            "",
            "## Candidate Eval",
            "",
            f"- Eval report: {evaluation.get('eval_report', '')}",
            f"- Strict recall / precision: {evaluation.get('candidate_recall')} / {evaluation.get('candidate_precision')}",
            f"- Missed / unexpected / must-not: {evaluation.get('missed')} / {evaluation.get('unexpected')} / {evaluation.get('must_not_detect_violations')}",
            f"- Unexpected triage: {evaluation.get('unexpected_triage', {})}",
        ])
    if buckets:
        lines.extend([
            "",
            "## Ideal Miss Buckets",
            "",
            f"- Bucket report: {buckets.get('bucket_report', '')}",
            f"- Miss count: {buckets.get('miss_count')}",
            f"- By bucket: {buckets.get('by_bucket', {})}",
        ])
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarise auto-label warnings and candidate eval QA")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--eval-report", type=Path)
    parser.add_argument("--bucket-report", type=Path)
    parser.add_argument("--output", type=Path, help="Write JSON report")
    parser.add_argument("--markdown-output", type=Path, help="Write Markdown report")
    args = parser.parse_args(argv)

    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    if not corpus.exists():
        print(f"candidate corpus missing: {corpus}", file=sys.stderr)
        return 2
    eval_report = args.eval_report if not args.eval_report or args.eval_report.is_absolute() else REPO_ROOT / args.eval_report
    bucket_report = args.bucket_report if not args.bucket_report or args.bucket_report.is_absolute() else REPO_ROOT / args.bucket_report
    for path in (eval_report, bucket_report):
        if path and not path.exists():
            print(f"report missing: {path}", file=sys.stderr)
            return 2
    report = build_report(corpus, eval_report=eval_report, bucket_report=bucket_report)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"wrote {output}")
    else:
        print(rendered, end="")
    if args.markdown_output:
        markdown_output = args.markdown_output if args.markdown_output.is_absolute() else REPO_ROOT / args.markdown_output
        markdown_output.parent.mkdir(parents=True, exist_ok=True)
        markdown_output.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
