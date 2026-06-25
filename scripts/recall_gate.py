#!/usr/bin/env python3
"""Recall (and precision) gate for the legal-contract fixture corpus.

Runs the kaypoh review engine over every `<doc>.txt` in the target corpus, compares the
produced findings against `<doc>.labels.json`, and computes per-rule recall + precision.
Fails (exit 1) when per-rule recall drops below the locked baseline, or when per-rule
precision drops below the locked baseline (when the lock contains a `baseline_precision`
section).

Default corpus: `test/fixtures/legal-corpus/` with `recall.lock.json` (recall-only).
Adversarial corpus: `--corpus test/fixtures/legal-corpus-adversarial/`, gated against
`recall_adversarial.lock.json` (recall + precision). Adversarial fixtures cover NRIC in
URLs, defined-term suppression edge cases, multilingual SG names, and negative-prose probes.

Usage:
    python3 scripts/recall_gate.py
    python3 scripts/recall_gate.py --update --reason "added 5 SPA fixtures"
    python3 scripts/recall_gate.py --corpus test/fixtures/legal-corpus-adversarial
    python3 scripts/recall_gate.py --corpus test/fixtures/legal-corpus-adversarial --update \\
        --reason "baseline adversarial corpus"

Exit codes:
    0 = recall + precision meet baseline
    1 = recall or precision regression, or must_not_detect violation when no precision baseline
    2 = corpus/lock load error, or --update without --reason
"""

from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
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

DEFAULT_CORPUS_DIR = REPO_ROOT / "test" / "fixtures" / "legal-corpus"
REGRESSION_TOLERANCE = 1e-6


def _lock_path_for(corpus_dir: Path) -> Path:
    """Each corpus directory has its own lock keyed off the directory name. Default corpus
    keeps the legacy `recall.lock.json` name; adversarial corpus → `recall_adversarial.lock.json`."""
    name = corpus_dir.name
    if name == "legal-corpus":
        return corpus_dir / "recall.lock.json"
    if name == "legal-corpus-adversarial":
        return corpus_dir / "recall_adversarial.lock.json"
    # generic fallback for arbitrary corpora
    return corpus_dir / f"{name}.lock.json"


def _history_path_for(corpus_dir: Path) -> Path:
    return corpus_dir / "recall.lock.history.jsonl"


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


@dataclass
class DocResult:
    doc_id: str
    per_rule_total: dict[str, int] = field(default_factory=dict)
    per_rule_hits: dict[str, int] = field(default_factory=dict)
    per_rule_false_positives: dict[str, int] = field(default_factory=dict)
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

    forbidden_texts = {label["matched_text"]: label.get("reason", "") for label in labels.get("must_not_detect", [])}
    for finding in findings:
        if finding["matched_text"] in forbidden_texts:
            rule = finding["rule"]
            doc.per_rule_false_positives[rule] = doc.per_rule_false_positives.get(rule, 0) + 1
            doc.violations.append(
                f"{labels['doc_id']}: forbidden '{finding['matched_text']}' detected as {rule}"
                f" ({forbidden_texts[finding['matched_text']]})"
            )
    return doc


def _aggregate_recall(docs: list[DocResult]) -> dict[str, float]:
    totals: dict[str, int] = {}
    hits: dict[str, int] = {}
    for doc in docs:
        for rule, count in doc.per_rule_total.items():
            totals[rule] = totals.get(rule, 0) + count
        for rule, count in doc.per_rule_hits.items():
            hits[rule] = hits.get(rule, 0) + count
    return {rule: round(hits.get(rule, 0) / totals[rule], 4) for rule in totals}


def _aggregate_precision(docs: list[DocResult]) -> dict[str, float]:
    """Per-rule precision = TP / (TP + FP). Rules with neither TP nor FP do not appear in the
    output — there's nothing to measure. Rules with TP=0 and FP>0 get precision 0.0."""
    tp: dict[str, int] = {}
    fp: dict[str, int] = {}
    for doc in docs:
        for rule, count in doc.per_rule_hits.items():
            tp[rule] = tp.get(rule, 0) + count
        for rule, count in doc.per_rule_false_positives.items():
            fp[rule] = fp.get(rule, 0) + count
    out: dict[str, float] = {}
    for rule in set(tp) | set(fp):
        tp_count = tp.get(rule, 0)
        fp_count = fp.get(rule, 0)
        denom = tp_count + fp_count
        out[rule] = round(tp_count / denom, 4) if denom else 1.0
    return out


def _load_lock(lock_path: Path) -> tuple[dict[str, float], dict[str, float]]:
    if not lock_path.exists():
        return {}, {}
    payload = json.loads(lock_path.read_text(encoding="utf-8"))
    return dict(payload.get("baseline_recall", {})), dict(payload.get("baseline_precision", {}))


def _write_lock(lock_path: Path, recall: dict[str, float], precision: dict[str, float]) -> None:
    body: dict[str, Any] = {"baseline_recall": recall}
    if precision:
        # only emit baseline_precision when the corpus actually exercised must_not_detect /
        # must_detect signal — keeps the default corpus's lock unchanged.
        body["baseline_precision"] = precision
    lock_path.write_text(json.dumps(body, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _resolve_actor() -> str:
    env_actor = os.environ.get("KAYPOH_RECALL_ACTOR", "").strip()
    if env_actor:
        return env_actor
    try:
        out = subprocess.run(
            ["git", "config", "--get", "user.email"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=5, check=False,
        )
        if out.returncode == 0 and out.stdout.strip():
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return os.environ.get("USER", "unknown")


def _resolve_commit_sha() -> str:
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, cwd=REPO_ROOT, timeout=5, check=False,
        )
        if out.returncode == 0:
            return out.stdout.strip()
    except (OSError, subprocess.SubprocessError):
        pass
    return ""


def _diff_summary(current: dict[str, float], baseline: dict[str, float]) -> dict[str, dict[str, float | None]]:
    diff: dict[str, dict[str, float | None]] = {}
    all_rules = set(current) | set(baseline)
    for rule in sorted(all_rules):
        old = baseline.get(rule)
        new = current.get(rule)
        if old is None and new is not None:
            diff[rule] = {"old": None, "new": new}
        elif new is None and old is not None:
            diff[rule] = {"old": old, "new": None}
        elif old is not None and new is not None and abs(old - new) > REGRESSION_TOLERANCE:
            diff[rule] = {"old": old, "new": new}
    return diff


def _append_history(
    *,
    history_path: Path,
    reason: str,
    baseline_recall: dict[str, float],
    current_recall: dict[str, float],
    baseline_precision: dict[str, float],
    current_precision: dict[str, float],
) -> dict:
    entry = {
        "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "actor": _resolve_actor(),
        "commit_sha": _resolve_commit_sha(),
        "reason": reason,
        "diff": _diff_summary(current_recall, baseline_recall),
        "precision_diff": _diff_summary(current_precision, baseline_precision),
    }
    history_path.parent.mkdir(parents=True, exist_ok=True)
    with history_path.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":"), ensure_ascii=False) + "\n")
    return entry


def _compare(current: dict[str, float], baseline: dict[str, float], *, label: str) -> list[str]:
    regressions: list[str] = []
    for rule, baseline_value in baseline.items():
        current_value = current.get(rule, 0.0)
        if current_value + REGRESSION_TOLERANCE < baseline_value:
            regressions.append(
                f"{label}/{rule}: regressed {baseline_value:.4f} -> {current_value:.4f}"
            )
    return regressions


def _reason_mentions_human_review(reason: str) -> bool:
    normalized = reason.strip().lower()
    return "candidate" in normalized and ("human" in normalized or "review" in normalized or "approved" in normalized)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Legal-corpus recall + precision gate")
    parser.add_argument(
        "--corpus",
        type=Path,
        default=DEFAULT_CORPUS_DIR,
        help="path to the corpus dir (default: test/fixtures/legal-corpus)",
    )
    parser.add_argument("--update", action="store_true", help="rewrite the lock to current measurements")
    parser.add_argument(
        "--reason",
        default="",
        help="required when --update is set; one-line attribution recorded in <corpus>/recall.lock.history.jsonl",
    )
    parser.add_argument(
        "--require-human-reviewed",
        action="store_true",
        help="fail if generated/candidate labels in the corpus lack explicit human approval",
    )
    parser.add_argument("--verbose", action="store_true", help="print per-doc detail")
    args = parser.parse_args(argv)

    corpus_dir = args.corpus if args.corpus.is_absolute() else (REPO_ROOT / args.corpus).resolve()
    if not corpus_dir.exists():
        print(f"corpus missing: {corpus_dir}", file=sys.stderr)
        return 2

    lock_path = _lock_path_for(corpus_dir)
    history_path = _history_path_for(corpus_dir)

    doc_paths = sorted(p for p in corpus_dir.glob("*.txt"))
    if not doc_paths:
        print(f"no .txt fixtures in {corpus_dir}", file=sys.stderr)
        return 2

    if args.require_human_reviewed:
        review_violations = collect_review_status_violations(corpus_dir)
        if review_violations:
            print("generated/candidate labels require human approval:", file=sys.stderr)
            for violation in review_violations:
                print(f"human-review violation: {violation}", file=sys.stderr)
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

    current_recall = _aggregate_recall(docs)
    current_precision = _aggregate_precision(docs)

    print("per-rule recall:")
    for rule in sorted(current_recall):
        print(f"  {rule}: {current_recall[rule]:.4f}")
    if current_precision:
        print("per-rule precision:")
        for rule in sorted(current_precision):
            print(f"  {rule}: {current_precision[rule]:.4f}")

    if args.update:
        if not args.reason.strip():
            print(
                "--update requires --reason \"<one-line attribution>\" so auditors can reconstruct"
                " why the baseline moved",
                file=sys.stderr,
            )
            return 2
        if args.require_human_reviewed and not _reason_mentions_human_review(args.reason):
            print(
                "--update with --require-human-reviewed requires --reason to mention candidate human review provenance",
                file=sys.stderr,
            )
            return 2
        prev_recall, prev_precision = _load_lock(lock_path)
        _write_lock(lock_path, current_recall, current_precision)
        history_entry = _append_history(
            history_path=history_path,
            reason=args.reason.strip(),
            baseline_recall=prev_recall,
            current_recall=current_recall,
            baseline_precision=prev_precision,
            current_precision=current_precision,
        )
        print(f"wrote baseline to {_relative(lock_path)}")
        print(
            f"appended attribution to {_relative(history_path)} "
            f"(actor={history_entry['actor']}, commit={history_entry['commit_sha'][:12] or 'none'})"
        )
        if all_violations:
            for violation in all_violations:
                print(f"violation: {violation}", file=sys.stderr)
            return 1
        return 0

    baseline_recall, baseline_precision = _load_lock(lock_path)
    if not baseline_recall:
        print(f"no lock file at {lock_path}; run with --update to create one", file=sys.stderr)
        return 2

    regressions = _compare(current_recall, baseline_recall, label="recall")
    regressions.extend(_compare(current_precision, baseline_precision, label="precision"))
    for regression in regressions:
        print(f"regression: {regression}", file=sys.stderr)
    # when no precision baseline exists, must_not_detect violations still gate the run.
    # when a precision baseline DOES exist, the precision comparison subsumes the violation list.
    surface_violations = all_violations if not baseline_precision else []
    for violation in surface_violations:
        print(f"violation: {violation}", file=sys.stderr)

    return 1 if regressions or surface_violations else 0


if __name__ == "__main__":
    raise SystemExit(main())
