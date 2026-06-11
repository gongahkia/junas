#!/usr/bin/env python3
"""Evaluate quarantine candidate fixtures against the current deterministic engine."""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from collections import Counter
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_PATH = REPO_ROOT / "src"
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from kaypoh.review.engine import PreSendReviewEngine  # noqa: E402
from scripts.candidate_review import collect_review_status_violations  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
LOCK_NAME = "candidate_recall.lock.json"
HISTORY_NAME = "candidate_recall.lock.history.jsonl"
REGRESSION_TOLERANCE = 1e-6
UNEXPECTED_TRIAGE_BUCKETS = (
    "real_detector_hit_missing_from_strict_labels",
    "actual_detector_false_positive",
    "ideal_only_statutory_gap",
    "taxonomy_model_label_mismatch",
)
_ENGINE_CACHE: dict[str, PreSendReviewEngine] = {}


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
    ideal_matched: list[dict[str, str]] = field(default_factory=list)
    ideal_missed: list[dict[str, str]] = field(default_factory=list)
    unexpected: list[dict[str, str]] = field(default_factory=list)
    unexpected_triage: list[dict[str, str]] = field(default_factory=list)
    must_not_detect_violations: list[dict[str, str]] = field(default_factory=list)
    uncertain: list[dict[str, str]] = field(default_factory=list)


def _load_pair(path: Path) -> tuple[str, dict[str, Any]]:
    labels_path = path.with_suffix(".labels.json")
    if not labels_path.exists():
        raise FileNotFoundError(f"missing labels for {path}")
    return path.read_text(encoding="utf-8"), json.loads(labels_path.read_text(encoding="utf-8"))


def _configured_audit_grade_engine() -> PreSendReviewEngine:
    from kaypoh.configs.runtime import get_runtime_settings

    settings = get_runtime_settings()
    public_evidence = None
    if settings.public_evidence.enabled:
        from kaypoh.workflow.layer7_public_evidence.inference import PublicEvidenceRetriever
        from kaypoh.workflow.privacy_guard import PrivacyGuard

        public_evidence = PublicEvidenceRetriever(
            settings.public_evidence,
            PrivacyGuard(
                external_query_policy=settings.privacy.external_query_policy,
                max_query_chars=settings.privacy.max_query_chars,
                redact_exact_numbers=settings.privacy.redact_exact_numbers,
            ),
        )
    llm_adjudicator = None
    if settings.llm.enabled:
        from kaypoh.workflow.layer8_llm_adjudicator.inference import LocalLLMAdjudicator

        llm_adjudicator = LocalLLMAdjudicator(settings.llm)
    llm_defined_term_extractor = None
    llm_coverage_auditor = None
    if settings.llm.enabled and settings.llm_helpers.defined_terms_enabled:
        from kaypoh.workflow.layer8_llm_adjudicator.helpers import build_llm_defined_term_extractor

        llm_defined_term_extractor = build_llm_defined_term_extractor(settings.llm)
    if settings.llm.enabled and settings.llm_helpers.coverage_audit_enabled:
        from kaypoh.workflow.layer8_llm_adjudicator.helpers import build_llm_coverage_auditor

        llm_coverage_auditor = build_llm_coverage_auditor(settings.llm)
    return PreSendReviewEngine(
        public_evidence_retriever=public_evidence,
        llm_adjudicator=llm_adjudicator,
        llm_defined_term_extractor=llm_defined_term_extractor,
        llm_coverage_auditor=llm_coverage_auditor,
    )


def _engine_for_profile(review_profile: str) -> PreSendReviewEngine:
    if review_profile in _ENGINE_CACHE:
        return _ENGINE_CACHE[review_profile]
    if review_profile == "audit_grade":
        engine = _configured_audit_grade_engine()
    else:
        engine = PreSendReviewEngine()
    _ENGINE_CACHE[review_profile] = engine
    return engine


def _run_engine(text: str, labels: dict[str, Any], *, review_profile: str) -> list[dict[str, str]]:
    result = _engine_for_profile(review_profile).review(
        text=text,
        source_jurisdiction=labels.get("source_jurisdiction", "SG"),
        destination_jurisdiction=labels.get("destination_jurisdiction", "SG"),
        entity_id=None,
        include_suggestions=False,
        document_type=labels.get("document_type", "generic"),
        review_profile=review_profile,
    )
    return [
        {
            "category": finding.category,
            "rule": finding.rule,
            "matched_text": finding.matched_text,
        }
        for finding in result.findings
    ]


_DATE_OR_IP_LIKE_RE = re.compile(
    r"^(?:\d{4}[-/]\d{1,2}[-/]\d{1,2}(?:\s+\d{1,2})?|"
    r"\d{1,2}[-/]\d{1,2}[-/]\d{2,4}(?:\s+\d{1,2})?|"
    r"\d{1,3}(?:\.\d{1,3}){2,3})$"
)


def _looks_numeric_detector_false_positive(finding: dict[str, str]) -> bool:
    rule = finding["rule"]
    text = finding["matched_text"].strip()
    digits = "".join(ch for ch in text if ch.isdigit())
    if rule == "phone_number":
        if _DATE_OR_IP_LIKE_RE.fullmatch(text):
            return True
        if len(digits) >= 14 and not text.startswith("+"):
            return True
        return False
    if rule == "financial_amount":
        return bool(re.fullmatch(r"\d{6,}\s*[KMBT]", text, re.IGNORECASE))
    if rule == "large_number":
        return bool(re.fullmatch(r"0{6,}", digits))
    return False


def _triage_unexpected(
    finding: dict[str, str],
    *,
    expected: list[dict[str, str]],
    ideal: list[dict[str, str]],
    must_not_detect: list[dict[str, str]],
    uncertain: list[dict[str, str]],
) -> dict[str, str]:
    """Heuristic queueing only. Human review decides final label/detector action."""
    key = (finding["rule"], finding["matched_text"])
    ideal_keys = {(item["rule"], item["matched_text"]) for item in ideal}
    expected_texts = {item["matched_text"] for item in expected}
    ideal_texts = {item["matched_text"] for item in ideal}
    forbidden = {item["matched_text"]: item.get("reason", "") for item in must_not_detect}
    uncertain_by_text = {item["matched_text"]: item.get("concept", "") for item in uncertain}

    if finding["matched_text"] in forbidden:
        bucket = "actual_detector_false_positive"
        reason = f"matched must_not_detect span: {forbidden[finding['matched_text']]}"
    elif key in ideal_keys:
        bucket = "ideal_only_statutory_gap"
        reason = "exact match appears in ideal_must_detect but not detector-aligned must_detect"
    elif finding["matched_text"] in expected_texts or finding["matched_text"] in ideal_texts:
        bucket = "taxonomy_model_label_mismatch"
        reason = "same span is labeled under another rule/category"
    elif finding["matched_text"] in uncertain_by_text:
        bucket = "taxonomy_model_label_mismatch"
        reason = f"same span is marked uncertain: {uncertain_by_text[finding['matched_text']]}"
    elif _looks_numeric_detector_false_positive(finding):
        bucket = "actual_detector_false_positive"
        reason = "numeric shape looks like date/IP/identifier noise rather than the emitted rule"
    else:
        bucket = "real_detector_hit_missing_from_strict_labels"
        reason = "not in must_detect; inspect whether strict labels should include it"

    return {
        "bucket": bucket,
        "rule": finding["rule"],
        "matched_text": finding["matched_text"],
        "reason": reason,
    }


def _evaluate_one(path: Path, *, review_profile: str = "strict") -> CandidateDocReport:
    text, labels = _load_pair(path)
    findings = _run_engine(text, labels, review_profile=review_profile)
    finding_keys = {(f["rule"], f["matched_text"]) for f in findings}
    expected = [
        {
            "category": str(item.get("category") or ""),
            "rule": str(item["rule"]),
            "matched_text": str(item["matched_text"]),
            "concept": str(item.get("concept") or ""),
            "reason": str(item.get("reason") or ""),
        }
        for item in labels.get("must_detect", [])
    ]
    expected_keys = {(item["rule"], item["matched_text"]) for item in expected}
    matched = [item for item in expected if (item["rule"], item["matched_text"]) in finding_keys]
    missed = [item for item in expected if (item["rule"], item["matched_text"]) not in finding_keys]
    ideal = [
        {
            "category": str(item.get("category") or ""),
            "rule": str(item["rule"]),
            "matched_text": str(item["matched_text"]),
            "concept": str(item.get("concept") or ""),
            "reason": str(item.get("reason") or ""),
        }
        for item in labels.get("ideal_must_detect", [])
    ]
    ideal_matched = [item for item in ideal if (item["rule"], item["matched_text"]) in finding_keys]
    ideal_missed = [item for item in ideal if (item["rule"], item["matched_text"]) not in finding_keys]
    unexpected = [item for item in findings if (item["rule"], item["matched_text"]) not in expected_keys]
    must_not_detect = [
        {"matched_text": str(item["matched_text"]), "reason": str(item.get("reason") or "")}
        for item in labels.get("must_not_detect", [])
    ]
    uncertain = [
        {
            "matched_text": str(item.get("matched_text") or ""),
            "concept": str(item.get("concept") or ""),
            "reason": str(item.get("reason") or ""),
        }
        for item in labels.get("uncertain", [])
    ]
    unexpected_triage = [
        _triage_unexpected(
            item,
            expected=expected,
            ideal=ideal,
            must_not_detect=must_not_detect,
            uncertain=uncertain,
        )
        for item in unexpected
    ]
    forbidden = {item["matched_text"]: item["reason"] for item in must_not_detect}
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
        ideal_matched=ideal_matched,
        ideal_missed=ideal_missed,
        unexpected=unexpected,
        unexpected_triage=unexpected_triage,
        must_not_detect_violations=violations,
        uncertain=uncertain,
    )


def _summary(reports: list[CandidateDocReport]) -> dict[str, Any]:
    total_expected = sum(len(report.matched) + len(report.missed) for report in reports)
    total_matched = sum(len(report.matched) for report in reports)
    total_missed = sum(len(report.missed) for report in reports)
    total_ideal = sum(len(report.ideal_matched) + len(report.ideal_missed) for report in reports)
    total_ideal_matched = sum(len(report.ideal_matched) for report in reports)
    total_ideal_missed = sum(len(report.ideal_missed) for report in reports)
    total_unexpected = sum(len(report.unexpected) for report in reports)
    total_violations = sum(len(report.must_not_detect_violations) for report in reports)
    by_rule: dict[str, dict[str, int]] = {}
    ideal_by_rule: dict[str, dict[str, int]] = {}
    unexpected_triage = Counter[str]()
    for report in reports:
        for item in report.matched:
            by_rule.setdefault(item["rule"], {"matched": 0, "missed": 0})["matched"] += 1
        for item in report.missed:
            by_rule.setdefault(item["rule"], {"matched": 0, "missed": 0})["missed"] += 1
        for item in report.ideal_matched:
            ideal_by_rule.setdefault(item["rule"], {"matched": 0, "missed": 0})["matched"] += 1
        for item in report.ideal_missed:
            ideal_by_rule.setdefault(item["rule"], {"matched": 0, "missed": 0})["missed"] += 1
        for item in report.unexpected_triage:
            unexpected_triage[item["bucket"]] += 1
    return {
        "doc_count": len(reports),
        "expected_labels": total_expected,
        "matched": total_matched,
        "missed": total_missed,
        "ideal_labels": total_ideal,
        "ideal_matched": total_ideal_matched,
        "ideal_missed": total_ideal_missed,
        "unexpected": total_unexpected,
        "must_not_detect_violations": total_violations,
        "candidate_recall": round(total_matched / total_expected, 4) if total_expected else 0.0,
        "candidate_precision": round(total_matched / (total_matched + total_unexpected), 4)
        if total_matched + total_unexpected
        else 0.0,
        "ideal_candidate_recall": round(total_ideal_matched / total_ideal, 4) if total_ideal else 0.0,
        "by_rule": by_rule,
        "ideal_by_rule": ideal_by_rule,
        "unexpected_triage": {
            bucket: unexpected_triage.get(bucket, 0)
            for bucket in UNEXPECTED_TRIAGE_BUCKETS
        },
    }


def _lock_path_for(corpus: Path) -> Path:
    return corpus / LOCK_NAME


def _history_path_for(corpus: Path) -> Path:
    return corpus / HISTORY_NAME


def _resolve_actor() -> str:
    try:
        out = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
            check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return "unknown"


def _resolve_commit_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            timeout=5,
            check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _lock_baseline(summary: dict[str, Any]) -> dict[str, Any]:
    return {
        "doc_count": summary["doc_count"],
        "expected_labels": summary["expected_labels"],
        "matched": summary["matched"],
        "missed": summary["missed"],
        "unexpected": summary["unexpected"],
        "must_not_detect_violations": summary["must_not_detect_violations"],
        "candidate_recall": summary["candidate_recall"],
        "candidate_precision": summary["candidate_precision"],
        "ideal_candidate_recall": summary["ideal_candidate_recall"],
        "by_rule": summary["by_rule"],
        "ideal_by_rule": summary["ideal_by_rule"],
        "unexpected_triage": summary["unexpected_triage"],
    }


def _load_lock(lock_path: Path) -> dict[str, Any]:
    if not lock_path.exists():
        return {}
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    baseline = payload.get("baseline", {})
    return dict(baseline) if isinstance(baseline, dict) else {}


def _write_lock(lock_path: Path, *, summary: dict[str, Any], reason: str) -> None:
    payload = {
        "baseline": _lock_baseline(summary),
        "reason": reason,
        "updated_at_unix": int(time.time()),
    }
    lock_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _diff_scalar(current: dict[str, Any], baseline: dict[str, Any]) -> dict[str, dict[str, Any]]:
    keys = (
        "doc_count",
        "expected_labels",
        "matched",
        "missed",
        "unexpected",
        "must_not_detect_violations",
        "candidate_recall",
        "candidate_precision",
        "ideal_candidate_recall",
    )
    out: dict[str, dict[str, Any]] = {}
    for key in keys:
        old = baseline.get(key)
        new = current.get(key)
        if old != new:
            out[key] = {"old": old, "new": new}
    return out


def _append_history(history_path: Path, *, reason: str, baseline: dict[str, Any], current: dict[str, Any]) -> None:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": _resolve_actor(),
        "commit_sha": _resolve_commit_sha(),
        "reason": reason,
        "diff": _diff_scalar(current, baseline),
    }
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")


def _compare_to_lock(summary: dict[str, Any], baseline: dict[str, Any]) -> list[str]:
    failures: list[str] = []
    for key in ("candidate_recall", "candidate_precision", "ideal_candidate_recall"):
        old = float(baseline.get(key, 0.0) or 0.0)
        new = float(summary.get(key, 0.0) or 0.0)
        if new + REGRESSION_TOLERANCE < old:
            failures.append(f"{key}: regressed {old:.4f} -> {new:.4f}")
    for key in ("missed", "unexpected", "must_not_detect_violations"):
        old = int(baseline.get(key, 0) or 0)
        new = int(summary.get(key, 0) or 0)
        if new > old:
            failures.append(f"{key}: regressed {old} -> {new}")
    return failures


def _reason_mentions_human_review(reason: str) -> bool:
    normalized = reason.strip().lower()
    return "candidate" in normalized and ("human" in normalized or "review" in normalized or "approved" in normalized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Evaluate candidate fixtures without updating recall locks")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, help="Write JSON report to this path")
    parser.add_argument("--profile", choices=("strict", "audit_grade"), default="strict")
    parser.add_argument("--fail-on-missed", action="store_true")
    parser.add_argument("--update-lock", action="store_true", help=f"Write {LOCK_NAME} for this candidate corpus")
    parser.add_argument("--reason", default="", help="Required with --update-lock")
    parser.add_argument("--require-human-reviewed", action="store_true")
    args = parser.parse_args(argv)

    corpus = args.corpus if args.corpus.is_absolute() else REPO_ROOT / args.corpus
    paths = sorted(corpus.glob("**/*.txt"))
    if not paths:
        print(f"no candidate fixtures found in {corpus}", file=sys.stderr)
        return 2
    if args.require_human_reviewed:
        review_violations = collect_review_status_violations(corpus)
        if review_violations:
            print("generated/candidate labels require human approval:", file=sys.stderr)
            for violation in review_violations:
                print(f"human-review violation: {violation}", file=sys.stderr)
            return 2

    reports = [_evaluate_one(path, review_profile=args.profile) for path in paths]
    payload = {
        "generated_at_unix": int(time.time()),
        "corpus": str(corpus),
        "review_profile": args.profile,
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
    lock_path = _lock_path_for(corpus)
    history_path = _history_path_for(corpus)
    if args.update_lock:
        if not args.reason.strip():
            print("--update-lock requires --reason", file=sys.stderr)
            return 2
        if args.require_human_reviewed and not _reason_mentions_human_review(args.reason):
            print(
                "--update-lock with --require-human-reviewed requires --reason to mention candidate human review",
                file=sys.stderr,
            )
            return 2
        baseline = _load_lock(lock_path)
        _write_lock(lock_path, summary=payload["summary"], reason=args.reason.strip())
        _append_history(
            history_path,
            reason=args.reason.strip(),
            baseline=baseline,
            current=_lock_baseline(payload["summary"]),
        )
        print(f"wrote candidate baseline to {lock_path}")
    else:
        baseline = _load_lock(lock_path)
        if baseline:
            failures = _compare_to_lock(payload["summary"], baseline)
            for failure in failures:
                print(f"candidate-lock regression: {failure}", file=sys.stderr)
            if failures:
                return 1
    bad = payload["summary"]["missed"] or payload["summary"]["must_not_detect_violations"]
    return 1 if args.fail_on_missed and bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
