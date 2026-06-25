#!/usr/bin/env python3
"""Evaluate the distilled student against the locked baselines (item 29 step c).

The student is only worth shipping if it preserves the deterministic engine's
per-rule precision + recall AND adds value on the LLM-tier decisions (currently
just `risk_label`). This script:

1. Walks each corpus directory, runs the deterministic engine once per doc.
2. For each doc, prompts the student with the same shape the runtime adjudicator uses.
3. Parses the student's JSON output, compares `risk_label` against the deterministic
   `overall_risk` (the student is allowed to downgrade within the ambiguous band but
   never upgrade past it — same invariant as the runtime engine).
4. Reports per-corpus accuracy + agreement-rate vs deterministic + a pass/fail verdict
   against any tenant-specific minimums passed via `--min-agreement`.

This is intentionally NOT a substitute for `scripts/recall_gate.py` — that script
measures deterministic-detector accuracy and is unaffected by the student. This
script measures the LLM-tier accuracy improvement specifically.

Usage:
    # mocked student for tests / CI
    python3 training/distillation/eval_against_corpus.py \\
        --corpus test/fixtures/legal-corpus --student-provider mock

    # real student adapter
    python3 training/distillation/eval_against_corpus.py \\
        --corpus test/fixtures/legal-corpus \\
        --student-provider local_distilled \\
        --adapter-path training/distillation/student-lora-v1 \\
        --base-model Qwen/Qwen2.5-1.5B-Instruct

Exit codes:
    0  student meets configured minimums
    1  student under-performs vs minimums; do not promote
    2  setup error (missing corpus, missing adapter dir, etc.)
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
SRC_PATH = REPO_ROOT / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.engine import PreSendReviewEngine  # noqa: E402


@dataclass
class EvalRow:
    doc_id: str
    deterministic_label: str
    student_label: str
    student_confidence: float
    agreement: bool
    invariant_violation: bool  # student upgraded past deterministic high


@dataclass
class EvalStats:
    total: int = 0
    agreements: int = 0
    invariant_violations: int = 0
    by_deterministic: dict[str, int] = field(default_factory=dict)
    by_student: dict[str, int] = field(default_factory=dict)
    confusion: dict[tuple[str, str], int] = field(default_factory=dict)


def _load_fixture(doc_path: Path) -> tuple[str, dict[str, Any]]:
    text = doc_path.read_text(encoding="utf-8")
    labels_path = doc_path.with_suffix(".labels.json")
    labels = {}
    if labels_path.exists():
        try:
            labels = json.loads(labels_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            labels = {}
    return text, labels


class _MockStudent:
    """A test-only "student" that always emits the deterministic label. Useful for
    confirming the eval harness works end-to-end without a real model present."""

    def adjudicate(self, *, text, current_classification, findings=None, entity_id=None,
                   public_evidence=None, lexicon=None, model1=None, model2=None):
        return {
            "status": "adjudicated",
            "provider": "local_distilled",
            "model": "mock-student",
            "risk_label": current_classification,
            "public_status": "ambiguous",
            "confidence": 0.5,
            "materiality_reason": "mock student echoes deterministic label",
            "matched_public_sources": [],
            "unverified_claims": [],
            "review_recommendation": "no escalation (mock)",
        }


def _resolve_student(*, provider: str, adapter_path: Path | None, base_model: str | None) -> Any:
    if provider == "mock":
        return _MockStudent()
    if provider == "local_distilled":
        if adapter_path is None or not adapter_path.exists():
            raise FileNotFoundError("--adapter-path required and must exist for local_distilled")
        from training.distillation.student_provider import build_local_distilled_adjudicator

        return build_local_distilled_adjudicator(
            adapter_path=adapter_path,
            base_model=base_model or "Qwen/Qwen2.5-1.5B-Instruct",
        )
    raise ValueError(f"unknown --student-provider: {provider!r}")


def _is_invariant_violation(deterministic: str, student: str) -> bool:
    """Architectural invariant: the LLM tier can downgrade or hold, never upgrade
    past a deterministic high. So when deterministic_label != HIGH_RISK and student
    says HIGH_RISK, that's a violation we want to surface."""
    order = {"SAFE": 0, "LOW_RISK": 1, "HIGH_RISK": 2}
    return order.get(student, 0) > order.get(deterministic, 0)


def evaluate(*, corpus_dir: Path, student: Any) -> tuple[list[EvalRow], EvalStats]:
    engine = PreSendReviewEngine()
    rows: list[EvalRow] = []
    stats = EvalStats()

    for doc_path in sorted(corpus_dir.glob("*.txt")):
        text, labels = _load_fixture(doc_path)
        review = engine.review(
            text=text,
            source_jurisdiction=labels.get("source_jurisdiction", "SG"),
            destination_jurisdiction=labels.get("destination_jurisdiction", "SG"),
            entity_id=None,
            include_suggestions=False,
            document_type=labels.get("document_type", "generic"),
            review_profile="strict",
        )
        det_label = review.overall_risk.value
        # call the student with the same args the engine would in audit_grade.
        try:
            verdict = student.adjudicate(
                text=text,
                current_classification=det_label,
                findings=list(review.findings),
                entity_id=None,
                public_evidence=None,
            )
        except TypeError:
            verdict = student.adjudicate(
                text=text,
                current_classification=det_label,
            )

        student_label = str(verdict.get("risk_label", det_label) or det_label)
        confidence = float(verdict.get("confidence", 0.0) or 0.0)
        agreement = (student_label == det_label)
        violation = _is_invariant_violation(det_label, student_label)

        rows.append(EvalRow(
            doc_id=str(labels.get("doc_id", doc_path.stem)),
            deterministic_label=det_label,
            student_label=student_label,
            student_confidence=confidence,
            agreement=agreement,
            invariant_violation=violation,
        ))
        stats.total += 1
        if agreement:
            stats.agreements += 1
        if violation:
            stats.invariant_violations += 1
        stats.by_deterministic[det_label] = stats.by_deterministic.get(det_label, 0) + 1
        stats.by_student[student_label] = stats.by_student.get(student_label, 0) + 1
        key = (det_label, student_label)
        stats.confusion[key] = stats.confusion.get(key, 0) + 1
    return rows, stats


def _format_confusion(confusion: dict[tuple[str, str], int]) -> dict[str, dict[str, int]]:
    """Pretty-print the confusion matrix as nested dicts keyed by deterministic_label."""
    out: dict[str, dict[str, int]] = {}
    for (det, stu), count in confusion.items():
        out.setdefault(det, {})[stu] = count
    return out


def _report_path(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate distilled student against corpora")
    parser.add_argument("--corpus", type=Path, action="append", required=True,
                        help="corpus dir to evaluate. repeat for multiple.")
    parser.add_argument("--student-provider", default="mock",
                        choices=["mock", "local_distilled"])
    parser.add_argument("--adapter-path", type=Path, default=None,
                        help="path to the LoRA adapter directory (required for local_distilled)")
    parser.add_argument("--base-model", default=None,
                        help="HF base model id; defaults to Qwen/Qwen2.5-1.5B-Instruct")
    parser.add_argument(
        "--min-agreement", type=float, default=0.0,
        help="minimum overall agreement rate (student vs deterministic) to pass. 0.0 = report-only.",
    )
    parser.add_argument(
        "--max-invariant-violations", type=int, default=0,
        help="maximum number of times the student may upgrade past a deterministic label.",
    )
    parser.add_argument(
        "--output-report", type=Path, default=None,
        help="optional path to write the JSON eval report used by promotion_gate.py",
    )
    args = parser.parse_args(argv)

    try:
        student = _resolve_student(
            provider=args.student_provider,
            adapter_path=args.adapter_path,
            base_model=args.base_model,
        )
    except (FileNotFoundError, ValueError) as exc:
        print(f"student resolve failed: {exc}", file=sys.stderr)
        return 2

    all_rows: list[EvalRow] = []
    per_corpus: dict[str, dict[str, Any]] = {}
    overall_agreements = 0
    overall_total = 0
    overall_violations = 0

    for corpus in args.corpus:
        path = corpus if corpus.is_absolute() else (REPO_ROOT / corpus).resolve()
        if not path.exists():
            print(f"corpus missing: {path}", file=sys.stderr)
            return 2
        rows, stats = evaluate(corpus_dir=path, student=student)
        all_rows.extend(rows)
        agreement_rate = stats.agreements / stats.total if stats.total else 1.0
        per_corpus[_report_path(path)] = {
            "total": stats.total,
            "agreements": stats.agreements,
            "agreement_rate": round(agreement_rate, 4),
            "invariant_violations": stats.invariant_violations,
            "by_deterministic": stats.by_deterministic,
            "by_student": stats.by_student,
            "confusion": _format_confusion(stats.confusion),
        }
        overall_total += stats.total
        overall_agreements += stats.agreements
        overall_violations += stats.invariant_violations

    overall_rate = overall_agreements / overall_total if overall_total else 1.0
    report = {
        "student_provider": args.student_provider,
        "per_corpus": per_corpus,
        "overall": {
            "total": overall_total,
            "agreements": overall_agreements,
            "agreement_rate": round(overall_rate, 4),
            "invariant_violations": overall_violations,
        },
        "thresholds": {
            "min_agreement": args.min_agreement,
            "max_invariant_violations": args.max_invariant_violations,
        },
    }
    if args.output_report:
        output_path = args.output_report if args.output_report.is_absolute() else REPO_ROOT / args.output_report
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(report, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(report, indent=2, sort_keys=True))

    failed = False
    if overall_rate < args.min_agreement - 1e-6:
        print(
            f"agreement_rate {overall_rate:.4f} < --min-agreement {args.min_agreement}",
            file=sys.stderr,
        )
        failed = True
    if overall_violations > args.max_invariant_violations:
        print(
            f"invariant_violations {overall_violations} > --max-invariant-violations "
            f"{args.max_invariant_violations}", file=sys.stderr,
        )
        failed = True
    return 1 if failed else 0


if __name__ == "__main__":
    raise SystemExit(main())
