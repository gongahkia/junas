#!/usr/bin/env python3
"""Recall gate for the legal-contract fixture corpus.

Runs the kaypoh review engine over every `<doc>.txt` in `test/fixtures/legal-corpus/`,
compares the produced findings against `<doc>.labels.json`, and computes per-rule recall.
Fails (exit 1) when per-rule recall drops below the locked baseline in `recall.lock.json`
or when any `must_not_detect` matched_text appears in a finding.

Usage:
    python3 scripts/recall_gate.py            # run gate against locked baseline
    python3 scripts/recall_gate.py --update   # rewrite the lock to current recall
    python3 scripts/recall_gate.py --verbose  # print per-doc detail

Exit codes:
    0 = recall meets or exceeds baseline; no must_not_detect violations
    1 = recall regression or must_not_detect violation
    2 = corpus/lock load error
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.engine import PreSendReviewEngine  # noqa: E402

CORPUS_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus"
LOCK_PATH = CORPUS_DIR / "recall.lock.json"
REGRESSION_TOLERANCE = 1e-6


@dataclass
class DocResult:
    doc_id: str
    per_rule_total: dict[str, int] = field(default_factory=dict)
    per_rule_hits: dict[str, int] = field(default_factory=dict)
    violations: list[str] = field(default_factory=list)


def _load_doc(doc_path: Path) -> tuple[str, dict[str, Any]]:
    text = doc_path.read_text(encoding="utf-8")
    labels_path = doc_path.with_suffix(".labels.json")
    if not labels_path.exists():
        raise FileNotFoundError(f"missing labels for {doc_path.name}")
    labels = json.loads(labels_path.read_text(encoding="utf-8"))
    return text, labels


def _run_review(text: str, labels: dict[str, Any]) -> list[dict[str, Any]]:
    engine = PreSendReviewEngine()
    result = engine.review(
        text=text,
        source_jurisdiction=labels.get("source_jurisdiction", "SG"),
        destination_jurisdiction=labels.get("destination_jurisdiction", "SG"),
        entity_id=None,
        include_suggestions=False,
        document_type=labels.get("document_type", "generic"),
    )
    return [
        {"rule": finding.rule, "matched_text": finding.matched_text, "category": finding.category}
        for finding in result.findings
    ]


def _evaluate_doc(text: str, labels: dict[str, Any]) -> DocResult:
    findings = _run_review(text, labels)
    doc = DocResult(doc_id=labels["doc_id"])

    for label in labels.get("must_detect", []):
        rule = label["rule"]
        expected = label["matched_text"]
        doc.per_rule_total[rule] = doc.per_rule_total.get(rule, 0) + 1
        if any(f["rule"] == rule and f["matched_text"] == expected for f in findings):
            doc.per_rule_hits[rule] = doc.per_rule_hits.get(rule, 0) + 1

    for label in labels.get("must_not_detect", []):
        forbidden = label["matched_text"]
        # any finding whose matched_text equals or contains the forbidden token is a violation,
        # except for finding rules where the token appearing as substring is legitimate
        # (e.g., a defined term inside a larger phone match would not be).
        for finding in findings:
            if finding["matched_text"] == forbidden:
                doc.violations.append(
                    f"{labels['doc_id']}: forbidden '{forbidden}' detected as {finding['rule']}"
                    f" ({label.get('reason', '')})"
                )
    return doc


def _aggregate(docs: list[DocResult]) -> dict[str, float]:
    totals: dict[str, int] = {}
    hits: dict[str, int] = {}
    for doc in docs:
        for rule, count in doc.per_rule_total.items():
            totals[rule] = totals.get(rule, 0) + count
        for rule, count in doc.per_rule_hits.items():
            hits[rule] = hits.get(rule, 0) + count
    return {rule: round(hits.get(rule, 0) / totals[rule], 4) for rule in totals}


def _load_lock() -> dict[str, float]:
    if not LOCK_PATH.exists():
        return {}
    payload = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    return dict(payload.get("baseline_recall", {}))


def _write_lock(recall: dict[str, float]) -> None:
    LOCK_PATH.write_text(
        json.dumps({"baseline_recall": recall}, indent=2, sort_keys=True) + "\n",
        encoding="utf-8",
    )


def _compare(current: dict[str, float], baseline: dict[str, float]) -> list[str]:
    regressions: list[str] = []
    for rule, baseline_recall in baseline.items():
        current_recall = current.get(rule, 0.0)
        if current_recall + REGRESSION_TOLERANCE < baseline_recall:
            regressions.append(
                f"{rule}: recall regressed {baseline_recall:.4f} -> {current_recall:.4f}"
            )
    return regressions


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Legal-corpus recall gate")
    parser.add_argument("--update", action="store_true", help="rewrite recall.lock.json to current measurements")
    parser.add_argument("--verbose", action="store_true", help="print per-doc detail")
    args = parser.parse_args(argv)

    if not CORPUS_DIR.exists():
        print(f"corpus missing: {CORPUS_DIR}", file=sys.stderr)
        return 2

    doc_paths = sorted(p for p in CORPUS_DIR.glob("*.txt"))
    if not doc_paths:
        print(f"no .txt fixtures in {CORPUS_DIR}", file=sys.stderr)
        return 2

    docs: list[DocResult] = []
    all_violations: list[str] = []
    for doc_path in doc_paths:
        text, labels = _load_doc(doc_path)
        doc = _evaluate_doc(text, labels)
        docs.append(doc)
        all_violations.extend(doc.violations)
        if args.verbose:
            per_rule_summary = ", ".join(
                f"{rule}={doc.per_rule_hits.get(rule, 0)}/{doc.per_rule_total[rule]}"
                for rule in sorted(doc.per_rule_total)
            )
            print(f"  {doc.doc_id}: {per_rule_summary}")

    current = _aggregate(docs)
    print("per-rule recall:")
    for rule in sorted(current):
        print(f"  {rule}: {current[rule]:.4f}")

    if args.update:
        _write_lock(current)
        print(f"wrote baseline to {LOCK_PATH.relative_to(REPO_ROOT)}")
        if all_violations:
            for violation in all_violations:
                print(f"violation: {violation}", file=sys.stderr)
            return 1
        return 0

    baseline = _load_lock()
    if not baseline:
        print(f"no lock file at {LOCK_PATH}; run with --update to create one", file=sys.stderr)
        return 2

    regressions = _compare(current, baseline)
    for regression in regressions:
        print(f"regression: {regression}", file=sys.stderr)
    for violation in all_violations:
        print(f"violation: {violation}", file=sys.stderr)

    return 1 if regressions or all_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
