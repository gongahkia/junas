#!/usr/bin/env python3
"""Summarise candidate corpus stage, review, and eval posture by jurisdiction."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.fixture_taxonomy import CONCEPTS, JURISDICTIONS  # noqa: E402

DEFAULT_CORPUS = REPO_ROOT / "test" / "fixtures" / "legal-corpus-candidates"
DEFAULT_DOC_TYPES = ("memo", "term_sheet", "privacy_notice", "incident_report")
DEFAULT_VARIANTS = ("default", "adversarial", "negative")
STAGE_A_DOCS = len(CONCEPTS) * 1 * len(DEFAULT_VARIANTS)
STAGE_B_DOCS = len(CONCEPTS) * len(DEFAULT_DOC_TYPES) * len(DEFAULT_VARIANTS)
STAGE_C_DOCS = STAGE_B_DOCS * 3


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _jurisdiction_from_path(corpus: Path, labels_path: Path, labels: dict[str, Any]) -> str:
    raw = str(labels.get("source_jurisdiction") or "").upper()
    if raw:
        return raw
    try:
        return labels_path.relative_to(corpus).parts[0].upper()
    except (IndexError, ValueError):
        return "UNKNOWN"


def _fixture_path_for(labels_path: Path) -> Path:
    if labels_path.name.endswith(".labels.json"):
        return labels_path.with_name(labels_path.name.removesuffix(".labels.json") + ".txt")
    return labels_path.with_suffix(".txt")


def _stage_from_count(doc_count: int) -> str:
    if doc_count >= STAGE_C_DOCS:
        return "stage_c_or_more"
    if doc_count >= STAGE_B_DOCS:
        return "stage_b"
    if doc_count >= STAGE_A_DOCS:
        return "stage_a"
    if doc_count:
        return "partial"
    return "missing"


def _empty_eval_summary() -> dict[str, Any]:
    return {
        "eval_report": "",
        "strict_labels": 0,
        "matched": 0,
        "missed": 0,
        "unexpected": 0,
        "must_not_detect_violations": 0,
        "candidate_recall": None,
        "independent_candidate_recall": None,
        "candidate_precision": None,
        "ideal_labels": 0,
        "ideal_matched": 0,
        "ideal_missed": 0,
        "ideal_candidate_recall": None,
    }


def _ratio(numerator: int, denominator: int) -> float | None:
    if denominator <= 0:
        return None
    return round(numerator / denominator, 4)


def _eval_by_jurisdiction(eval_reports: list[Path]) -> dict[str, dict[str, Any]]:
    by_jurisdiction: dict[str, dict[str, Any]] = {}
    for report_path in eval_reports:
        payload = _read_json(report_path)
        per_jurisdiction: dict[str, dict[str, int]] = defaultdict(lambda: {
            "strict_labels": 0,
            "matched": 0,
            "missed": 0,
            "independent_labels": 0,
            "independent_matched": 0,
            "independent_missed": 0,
            "unexpected": 0,
            "must_not_detect_violations": 0,
            "ideal_labels": 0,
            "ideal_matched": 0,
            "ideal_missed": 0,
        })
        for doc in payload.get("documents", []):
            jurisdiction = str(doc.get("source_jurisdiction") or "UNKNOWN").upper()
            bucket = per_jurisdiction[jurisdiction]
            matched = len(doc.get("matched", []))
            missed = len(doc.get("missed", []))
            independent_matched = len(doc.get("independent_matched", doc.get("matched", [])))
            independent_missed = len(doc.get("independent_missed", doc.get("missed", [])))
            ideal_matched = len(doc.get("ideal_matched", []))
            ideal_missed = len(doc.get("ideal_missed", []))
            bucket["matched"] += matched
            bucket["missed"] += missed
            bucket["strict_labels"] += matched + missed
            bucket["independent_matched"] += independent_matched
            bucket["independent_missed"] += independent_missed
            bucket["independent_labels"] += independent_matched + independent_missed
            bucket["unexpected"] += len(doc.get("unexpected", []))
            bucket["must_not_detect_violations"] += len(doc.get("must_not_detect_violations", []))
            bucket["ideal_matched"] += ideal_matched
            bucket["ideal_missed"] += ideal_missed
            bucket["ideal_labels"] += ideal_matched + ideal_missed
        for jurisdiction, values in per_jurisdiction.items():
            strict_labels = values["strict_labels"]
            matched = values["matched"]
            ideal_labels = values["ideal_labels"]
            ideal_matched = values["ideal_matched"]
            denominator = matched + values["unexpected"]
            by_jurisdiction[jurisdiction] = {
                "eval_report": _relative(report_path),
                **values,
                "candidate_recall": _ratio(matched, strict_labels),
                "independent_candidate_recall": _ratio(
                    values["independent_matched"],
                    values["independent_labels"],
                ),
                "candidate_precision": _ratio(matched, denominator),
                "ideal_candidate_recall": _ratio(ideal_matched, ideal_labels),
            }
    return by_jurisdiction


def build_report(corpus: Path, *, eval_reports: list[Path] | None = None) -> dict[str, Any]:
    corpus = corpus.resolve()
    eval_reports = [path.resolve() for path in eval_reports or []]
    eval_summary = _eval_by_jurisdiction(eval_reports)
    jurisdictions: dict[str, dict[str, Any]] = {}
    for labels_path in sorted(corpus.glob("**/*.labels.json")):
        labels = _read_json(labels_path)
        jurisdiction = _jurisdiction_from_path(corpus, labels_path, labels)
        entry = jurisdictions.setdefault(
            jurisdiction,
            {
                "jurisdiction": jurisdiction,
                "doc_count": 0,
                "txt_count": 0,
                "label_count": 0,
                "stage_by_doc_count": "missing",
                "taxonomy_concepts": Counter(),
                "document_types": Counter(),
                "variants": Counter(),
                "review_status": Counter(),
                "stage_readiness": Counter(),
                "label_sources": Counter(),
                "label_models": Counter(),
                "pending_examples": [],
            },
        )
        entry["label_count"] += 1
        txt_path = _fixture_path_for(labels_path)
        if txt_path.exists():
            entry["txt_count"] += 1
            entry["doc_count"] += 1
        entry["taxonomy_concepts"][str(labels.get("_taxonomy_concept") or "unknown")] += 1
        entry["document_types"][str(labels.get("document_type") or "unknown")] += 1
        stem_parts = txt_path.stem.split("_")
        variant = stem_parts[-2] if len(stem_parts) >= 2 and stem_parts[-1].isdigit() else "unknown"
        entry["variants"][variant] += 1
        status = str(labels.get("_human_review_status") or "missing")
        entry["review_status"][status] += 1
        readiness = labels.get("_stage_readiness")
        readiness_status = str(readiness.get("status") or "missing") if isinstance(readiness, dict) else "missing"
        entry["stage_readiness"][readiness_status] += 1
        entry["label_sources"][str(labels.get("_label_source") or "unknown")] += 1
        entry["label_models"][str(labels.get("_label_model") or "unknown")] += 1
        if status != "approved" and len(entry["pending_examples"]) < 5:
            entry["pending_examples"].append(_relative(labels_path))

    rendered: list[dict[str, Any]] = []
    for jurisdiction in sorted(set(JURISDICTIONS) | set(jurisdictions)):
        entry = jurisdictions.get(
            jurisdiction,
            {
                "jurisdiction": jurisdiction,
                "doc_count": 0,
                "txt_count": 0,
                "label_count": 0,
                "taxonomy_concepts": Counter(),
                "document_types": Counter(),
                "variants": Counter(),
                "review_status": Counter(),
                "stage_readiness": Counter(),
                "label_sources": Counter(),
                "label_models": Counter(),
                "pending_examples": [],
            },
        )
        doc_count = int(entry["doc_count"])
        row = {
            "jurisdiction": jurisdiction,
            "doc_count": doc_count,
            "txt_count": int(entry["txt_count"]),
            "label_count": int(entry["label_count"]),
            "stage_by_doc_count": _stage_from_count(doc_count),
            "stage_targets": {
                "stage_a": STAGE_A_DOCS,
                "stage_b": STAGE_B_DOCS,
                "stage_c": STAGE_C_DOCS,
            },
            "taxonomy_concepts": dict(sorted(entry["taxonomy_concepts"].items())),
            "document_types": dict(sorted(entry["document_types"].items())),
            "variants": dict(sorted(entry["variants"].items())),
            "review_status": dict(sorted(entry["review_status"].items())),
            "stage_readiness": dict(sorted(entry["stage_readiness"].items())),
            "label_sources": dict(sorted(entry["label_sources"].items())),
            "label_models": dict(sorted(entry["label_models"].items())),
            "pending_examples": entry["pending_examples"],
            "evaluation": eval_summary.get(jurisdiction, _empty_eval_summary()),
        }
        rendered.append(row)

    total_docs = sum(item["doc_count"] for item in rendered)
    total_pending = sum(item["review_status"].get("pending", 0) for item in rendered)
    total_approved = sum(item["review_status"].get("approved", 0) for item in rendered)
    return {
        "generated_at_unix": int(time.time()),
        "corpus": _relative(corpus),
        "eval_reports": [_relative(path) for path in eval_reports],
        "stage_targets": {
            "stage_a": STAGE_A_DOCS,
            "stage_b": STAGE_B_DOCS,
            "stage_c": STAGE_C_DOCS,
        },
        "summary": {
            "jurisdiction_count": len(rendered),
            "doc_count": total_docs,
            "approved_labels": total_approved,
            "pending_labels": total_pending,
            "stage_b_or_better": sum(1 for item in rendered if item["doc_count"] >= STAGE_B_DOCS),
            "stage_a_or_better": sum(1 for item in rendered if item["doc_count"] >= STAGE_A_DOCS),
        },
        "jurisdictions": rendered,
        "note": "candidate report only; pending labels are not promotion-ready legal baselines.",
    }


def render_markdown(report: dict[str, Any]) -> str:
    summary = report["summary"]
    eval_reports = ", ".join(report.get("eval_reports") or []) or "none"
    lines = [
        "# Candidate Corpus Report",
        "",
        "Candidate fixtures are quarantine material. Pending labels are not promotion-ready legal baselines.",
        "",
        "## Summary",
        "",
        f"- Corpus: {report['corpus']}",
        f"- Evaluation reports: {eval_reports}",
        f"- Jurisdictions: {summary['jurisdiction_count']}",
        f"- Docs: {summary['doc_count']}",
        f"- Approved labels: {summary['approved_labels']}",
        f"- Pending labels: {summary['pending_labels']}",
        f"- Stage B or better: {summary['stage_b_or_better']}",
        "",
        "## Jurisdictions",
        "",
        (
            "| Jurisdiction | Docs | Stage | Review | Strict recall | Independent recall | "
            "Strict precision | Ideal recall | Eval report |"
        ),
        "|---|---:|---|---|---:|---:|---:|---:|---|",
    ]
    for item in report["jurisdictions"]:
        review = ", ".join(f"{key}:{value}" for key, value in item["review_status"].items()) or "none"
        evaluation = item["evaluation"]
        recall = evaluation.get("candidate_recall")
        independent = evaluation.get("independent_candidate_recall")
        precision = evaluation.get("candidate_precision")
        ideal = evaluation.get("ideal_candidate_recall")
        lines.append(
            (
                "| {jurisdiction} | {docs} | {stage} | {review} | {recall} | "
                "{independent} | {precision} | {ideal} | {eval_report} |"
            ).format(
                jurisdiction=item["jurisdiction"],
                docs=item["doc_count"],
                stage=item["stage_by_doc_count"],
                review=review,
                recall="" if recall is None else f"{recall:.4f}",
                independent="" if independent is None else f"{independent:.4f}",
                precision="" if precision is None else f"{precision:.4f}",
                ideal="" if ideal is None else f"{ideal:.4f}",
                eval_report=evaluation.get("eval_report") or "",
            )
        )
    lines.append("")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Summarise candidate corpus stage/review/eval posture")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--eval-report", type=Path, action="append", default=[])
    parser.add_argument("--output", type=Path, help="Write JSON report")
    parser.add_argument("--markdown-output", type=Path, help="Write Markdown report")
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
    report = build_report(corpus, eval_reports=eval_reports)
    rendered = json.dumps(report, indent=2, sort_keys=True) + "\n"
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
        markdown_output.write_text(render_markdown(report), encoding="utf-8")
        print(f"wrote {markdown_output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
