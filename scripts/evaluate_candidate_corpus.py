#!/usr/bin/env python3
"""Evaluate quarantine candidate fixtures against the current deterministic engine."""

from __future__ import annotations

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.engine import PreSendReviewEngine  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"


@dataclass
class CandidateDocReport:
    doc_id: str
    path: str
    source_jurisdiction: str
    destination_jurisdiction: str
    document_type: str
    human_review_status: str
    label_source: str
    matched: list[dict[str, str]] = field(default_factory=list)
    missed: list[dict[str, str]] = field(default_factory=list)
    unexpected: list[dict[str, str]] = field(default_factory=list)
    must_not_detect_violations: list[dict[str, str]] = field(default_factory=list)
    uncertain: list[dict[str, str]] = field(default_factory=list)


def _load_pair(path: Path) -> tuple[str, dict[str, Any]]:
    labels_path = path.with_suffix(".labels.json")
    if not labels_path.exists():
        raise FileNotFoundError(f"missing labels for {path}")
    return path.read_text(encoding="utf-8"), json.loads(labels_path.read_text(encoding="utf-8"))


def _run_engine(text: str, labels: dict[str, Any]) -> list[dict[str, str]]:
    result = PreSendReviewEngine().review(
        text=text,
        source_jurisdiction=labels.get("source_jurisdiction", "SG"),
        destination_jurisdiction=labels.get("destination_jurisdiction", "SG"),
        entity_id=None,
        include_suggestions=False,
        document_type=labels.get("document_type", "generic"),
        review_profile="strict",
    )
    return [
        {
            "category": finding.category,
            "rule": finding.rule,
            "matched_text": finding.matched_text,
        }
        for finding in result.findings
    ]


def _evaluate_one(path: Path) -> CandidateDocReport:
    text, labels = _load_pair(path)
    findings = _run_engine(text, labels)
    finding_keys = {(f["rule"], f["matched_text"]) for f in findings}
    expected = [
        {
            "category": str(item.get("category") or ""),
            "rule": str(item["rule"]),
            "matched_text": str(item["matched_text"]),
        }
        for item in labels.get("must_detect", [])
    ]
    expected_keys = {(item["rule"], item["matched_text"]) for item in expected}
    matched = [item for item in expected if (item["rule"], item["matched_text"]) in finding_keys]
    missed = [item for item in expected if (item["rule"], item["matched_text"]) not in finding_keys]
    unexpected = [item for item in findings if (item["rule"], item["matched_text"]) not in expected_keys]
    forbidden = {str(item["matched_text"]): str(item.get("reason") or "") for item in labels.get("must_not_detect", [])}
    violations = [
        {
            "rule": finding["rule"],
            "matched_text": finding["matched_text"],
            "reason": forbidden[finding["matched_text"]],
        }
        for finding in findings
        if finding["matched_text"] in forbidden
    ]
    return CandidateDocReport(
        doc_id=str(labels.get("doc_id") or path.stem),
        path=str(path.relative_to(REPO_ROOT) if path.is_relative_to(REPO_ROOT) else path),
        source_jurisdiction=str(labels.get("source_jurisdiction") or "SG"),
        destination_jurisdiction=str(labels.get("destination_jurisdiction") or "SG"),
        document_type=str(labels.get("document_type") or "generic"),
        human_review_status=str(labels.get("_human_review_status") or "unknown"),
        label_source=str(labels.get("_label_source") or "unknown"),
        matched=matched,
        missed=missed,
        unexpected=unexpected,
        must_not_detect_violations=violations,
        uncertain=[
            {
                "matched_text": str(item.get("matched_text") or ""),
                "concept": str(item.get("concept") or ""),
                "reason": str(item.get("reason") or ""),
            }
            for item in labels.get("uncertain", [])
        ],
    )


def _summary(reports: list[CandidateDocReport]) -> dict[str, Any]:
    total_expected = sum(len(report.matched) + len(report.missed) for report in reports)
    total_matched = sum(len(report.matched) for report in reports)
    total_missed = sum(len(report.missed) for report in reports)
    total_unexpected = sum(len(report.unexpected) for report in reports)
    total_violations = sum(len(report.must_not_detect_violations) for report in reports)
    by_rule: dict[str, dict[str, int]] = {}
    for report in reports:
        for item in report.matched:
            by_rule.setdefault(item["rule"], {"matched": 0, "missed": 0})["matched"] += 1
        for item in report.missed:
            by_rule.setdefault(item["rule"], {"matched": 0, "missed": 0})["missed"] += 1
    return {
        "doc_count": len(reports),
        "expected_labels": total_expected,
        "matched": total_matched,
        "missed": total_missed,
        "unexpected": total_unexpected,
        "must_not_detect_violations": total_violations,
        "candidate_recall": round(total_matched / total_expected, 4) if total_expected else 0.0,
        "by_rule": by_rule,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate candidate fixtures without updating recall locks")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, help="Write JSON report to this path")
    parser.add_argument("--fail-on-missed", action="store_true")
    args = parser.parse_args(argv)

    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    paths = sorted(corpus.glob("**/*.txt"))
    if not paths:
        print(f"no candidate fixtures found in {corpus}", file=sys.stderr)
        return 2

    reports = [_evaluate_one(path) for path in paths]
    payload = {
        "generated_at_unix": int(time.time()),
        "corpus": str(corpus),
        "summary": _summary(reports),
        "documents": [report.__dict__ for report in reports],
        "note": "candidate report only; do not update recall locks without human review.",
    }
    rendered = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    if args.output:
        output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(rendered, encoding="utf-8")
        print(f"wrote {output}")
    else:
        print(rendered, end="")
    bad = payload["summary"]["missed"] or payload["summary"]["must_not_detect_violations"]
    return 1 if args.fail_on_missed and bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
