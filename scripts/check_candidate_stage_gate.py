#!/usr/bin/env python3
"""Gate candidate jurisdiction stage advancement and promotion readiness."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.candidate_corpus_report import (  # noqa: E402
    DEFAULT_CORPUS,
    STAGE_A_DOCS,
    STAGE_B_DOCS,
    STAGE_C_DOCS,
    build_report,
)

TARGET_DOCS = {
    "stage_a": STAGE_A_DOCS,
    "stage_b": STAGE_B_DOCS,
    "stage_c": STAGE_C_DOCS,
}


def _clean_eval(evaluation: dict[str, Any]) -> bool:
    if not evaluation.get("eval_report"):
        return False
    return (
        evaluation.get("candidate_recall") == 1.0
        and evaluation.get("candidate_precision") == 1.0
        and int(evaluation.get("missed") or 0) == 0
        and int(evaluation.get("unexpected") or 0) == 0
        and int(evaluation.get("must_not_detect_violations") or 0) == 0
    )


def stage_gate_status(
    *,
    corpus: Path,
    jurisdiction: str,
    target_stage: str,
    eval_reports: list[Path] | None = None,
) -> dict[str, Any]:
    jurisdiction = jurisdiction.upper()
    report = build_report(corpus, eval_reports=eval_reports or [])
    rows = {item["jurisdiction"].upper(): item for item in report["jurisdictions"]}
    if jurisdiction not in rows:
        return {
            "jurisdiction": jurisdiction,
            "target_stage": target_stage,
            "target_docs": TARGET_DOCS[target_stage],
            "status": "missing",
            "promotion_ready": False,
            "violations": [f"{jurisdiction}: no candidate row found"],
        }
    row = rows[jurisdiction]
    review_status = row["review_status"]
    approved = int(review_status.get("approved", 0))
    pending = int(review_status.get("pending", 0))
    rejected = int(review_status.get("rejected", 0))
    needs_edit = int(review_status.get("needs_edit", 0))
    missing_review = int(review_status.get("missing", 0))
    doc_count = int(row["doc_count"])
    target_docs = TARGET_DOCS[target_stage]
    has_target_docs = doc_count >= target_docs
    owner_reviewed = has_target_docs and approved >= target_docs and pending == 0 and rejected == 0 and needs_edit == 0 and missing_review == 0
    clean_eval = _clean_eval(row["evaluation"])
    evaluated = bool(row["evaluation"].get("eval_report"))
    if has_target_docs and clean_eval and owner_reviewed:
        status = "promotion_ready"
    elif has_target_docs and clean_eval:
        status = "evaluated_pending_owner_review"
    elif has_target_docs and evaluated:
        status = "evaluated_needs_cleanup"
    elif has_target_docs:
        status = "generated_not_evaluated"
    else:
        status = "insufficient_docs"
    return {
        "jurisdiction": jurisdiction,
        "target_stage": target_stage,
        "target_docs": target_docs,
        "doc_count": doc_count,
        "review_status": review_status,
        "evaluation": row["evaluation"],
        "has_target_docs": has_target_docs,
        "evaluated": evaluated,
        "clean_eval": clean_eval,
        "owner_reviewed": owner_reviewed,
        "promotion_ready": status == "promotion_ready",
        "status": status,
        "violations": [],
    }


def _requirement_violations(
    status: dict[str, Any],
    *,
    require_clean_eval: bool,
    require_owner_reviewed: bool,
    require_promotion_ready: bool,
) -> list[str]:
    violations: list[str] = []
    jurisdiction = status["jurisdiction"]
    target_stage = status["target_stage"]
    if not status.get("has_target_docs"):
        violations.append(
            f"{jurisdiction}: {target_stage} requires {status['target_docs']} docs; found {status.get('doc_count', 0)}"
        )
    if require_clean_eval and not status.get("clean_eval"):
        evaluation = status.get("evaluation") or {}
        if not evaluation.get("eval_report"):
            violations.append(f"{jurisdiction}: no eval report attached for {target_stage}")
        else:
            violations.append(
                f"{jurisdiction}: eval not clean "
                f"recall={evaluation.get('candidate_recall')} precision={evaluation.get('candidate_precision')} "
                f"missed={evaluation.get('missed')} unexpected={evaluation.get('unexpected')} "
                f"must_not={evaluation.get('must_not_detect_violations')}"
            )
    if require_owner_reviewed and not status.get("owner_reviewed"):
        review_status = status.get("review_status") or {}
        violations.append(
            f"{jurisdiction}: {target_stage} is not owner-reviewed "
            f"(approved={review_status.get('approved', 0)}, pending={review_status.get('pending', 0)}, "
            f"rejected={review_status.get('rejected', 0)}, needs_edit={review_status.get('needs_edit', 0)})"
        )
    if require_promotion_ready and not status.get("promotion_ready"):
        violations.append(f"{jurisdiction}: {target_stage} status={status.get('status')} is not promotion-ready")
    return violations


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Gate candidate stage advancement and promotion readiness")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--jurisdiction", required=True)
    parser.add_argument("--target-stage", choices=tuple(TARGET_DOCS), default="stage_b")
    parser.add_argument("--eval-report", type=Path, action="append", default=[])
    parser.add_argument("--require-clean-eval", action="store_true")
    parser.add_argument("--require-owner-reviewed", action="store_true")
    parser.add_argument("--require-promotion-ready", action="store_true")
    parser.add_argument("--json", action="store_true", help="Print JSON instead of one-line status")
    args = parser.parse_args(argv)

    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    if not corpus.exists():
        print(f"candidate corpus missing: {corpus}", file=sys.stderr)
        return 2
    eval_reports = [(path if path.is_absolute() else REPO_ROOT / path) for path in args.eval_report]
    for path in eval_reports:
        if not path.exists():
            print(f"eval report missing: {path}", file=sys.stderr)
            return 2
    status = stage_gate_status(
        corpus=corpus,
        jurisdiction=args.jurisdiction,
        target_stage=args.target_stage,
        eval_reports=eval_reports,
    )
    violations = list(status.get("violations") or [])
    violations.extend(
        _requirement_violations(
            status,
            require_clean_eval=args.require_clean_eval or args.require_promotion_ready,
            require_owner_reviewed=args.require_owner_reviewed or args.require_promotion_ready,
            require_promotion_ready=args.require_promotion_ready,
        )
    )
    status["violations"] = violations
    if args.json:
        print(json.dumps(status, indent=2, sort_keys=True))
    else:
        review = status.get("review_status") or {}
        evaluation = status.get("evaluation") or {}
        print(
            f"{status['jurisdiction']} {status['target_stage']}: status={status['status']} "
            f"docs={status.get('doc_count', 0)}/{status['target_docs']} "
            f"approved={review.get('approved', 0)} pending={review.get('pending', 0)} "
            f"recall={evaluation.get('candidate_recall')} precision={evaluation.get('candidate_precision')}"
        )
        for violation in violations:
            print(f"stage-gate violation: {violation}", file=sys.stderr)
    return 1 if violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
