#!/usr/bin/env python3
"""Promote candidate ideal labels only when runtime findings provide exact spans."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.engine import PreSendReviewEngine  # noqa: E402
from scripts.candidate_review import labels_path_for, load_labels, utc_now, write_labels  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
DEFAULT_RULES = ("quasi_identifier_combination",)


def _run_findings(text: str, labels: dict[str, Any]) -> set[tuple[str, str, str]]:
    result = PreSendReviewEngine().review(
        text=text,
        source_jurisdiction=str(labels.get("source_jurisdiction") or "SG"),
        destination_jurisdiction=str(labels.get("destination_jurisdiction") or "SG"),
        entity_id=None,
        include_suggestions=False,
        document_type=str(labels.get("document_type") or "generic"),
        review_profile="strict",
    )
    return {(finding.category, finding.rule, finding.matched_text) for finding in result.findings}


def promote_exact_spans(
    *,
    corpus: Path,
    rules: tuple[str, ...] = DEFAULT_RULES,
    dry_run: bool = False,
    actor: str = "",
) -> dict[str, Any]:
    promoted: list[dict[str, str]] = []
    scanned = 0
    ts = utc_now()
    rule_set = set(rules)
    for txt_path in sorted(corpus.glob("**/*.txt")):
        labels_path = labels_path_for(txt_path)
        if not labels_path.exists():
            continue
        scanned += 1
        text = txt_path.read_text(encoding="utf-8")
        labels = load_labels(labels_path)
        runtime = _run_findings(text, labels)
        must = list(labels.get("must_detect") or [])
        existing = {(str(item.get("rule") or ""), str(item.get("matched_text") or "")) for item in must}
        additions: list[dict[str, str]] = []
        for item in labels.get("ideal_must_detect", []) or []:
            category = str(item.get("category") or "PII")
            rule = str(item.get("rule") or "")
            matched_text = str(item.get("matched_text") or "")
            if rule not in rule_set or not matched_text:
                continue
            if (rule, matched_text) in existing:
                continue
            if (category, rule, matched_text) not in runtime:
                continue
            addition = {
                "category": category,
                "rule": rule,
                "matched_text": matched_text,
                "reason": "promoted from ideal_must_detect after exact strict runtime finding",
            }
            must.append(addition)
            additions.append(addition)
            existing.add((rule, matched_text))
        if not additions:
            continue
        entry = {
            "promoted_at_utc": ts,
            "actor": actor,
            "source": "scripts/promote_candidate_exact_spans.py",
            "rules": sorted(rule_set),
            "count": len(additions),
        }
        promoted.append({
            "fixture": str(txt_path.relative_to(REPO_ROOT)),
            "labels": str(labels_path.relative_to(REPO_ROOT)),
            "count": str(len(additions)),
        })
        if dry_run:
            continue
        labels["must_detect"] = must
        history = labels.get("_exact_span_promotion_history")
        if not isinstance(history, list):
            history = []
        history.append(entry)
        labels["_exact_span_promotion"] = entry
        write_labels(labels_path, labels)
    return {
        "corpus": str(corpus),
        "scanned": scanned,
        "promoted_count": sum(int(item["count"]) for item in promoted),
        "promoted_fixtures": promoted,
        "dry_run": dry_run,
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Promote exact runtime spans from ideal candidate labels")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--rule", action="append", default=[], help="Rule to promote; repeatable")
    parser.add_argument("--actor", default="", help="Attribution recorded in label metadata")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args(argv)
    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    if not corpus.exists():
        print(f"candidate corpus missing: {corpus}", file=sys.stderr)
        return 2
    rules = tuple(args.rule) if args.rule else DEFAULT_RULES
    result = promote_exact_spans(corpus=corpus, rules=rules, dry_run=args.dry_run, actor=args.actor)
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
