#!/usr/bin/env python3
"""Generate detector-level dashboard JSON from candidate eval reports."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT = REPO_ROOT / "reports" / "detector-dashboard.json"


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _empty_rule() -> dict[str, Any]:
    return {
        "rule": "",
        "category": "",
        "matched": 0,
        "missed": 0,
        "unexpected": 0,
        "must_not_detect_violations": 0,
        "override_signals": 0,
        "unexpected_triage": Counter(),
        "by_jurisdiction": Counter(),
        "by_document_type": Counter(),
        "source_reports": Counter(),
    }


def _add_rule_counts(detectors: dict[str, dict[str, Any]], summary: dict[str, Any]) -> None:
    for rule, counts in (summary.get("by_rule") or {}).items():
        entry = detectors.setdefault(str(rule), _empty_rule())
        entry["rule"] = str(rule)
        entry["matched"] += int(counts.get("matched", 0) or 0)
        entry["missed"] += int(counts.get("missed", 0) or 0)


def _add_doc_signals(detectors: dict[str, dict[str, Any]], doc: dict[str, Any], report_path: Path) -> None:
    jurisdiction = str(doc.get("source_jurisdiction") or "UNKNOWN").upper()
    document_type = str(doc.get("document_type") or "unknown")
    report_name = _relative(report_path)
    for section in ("matched", "missed", "unexpected", "must_not_detect_violations"):
        for item in doc.get(section, []) or []:
            rule = str(item.get("rule") or "unknown")
            entry = detectors.setdefault(rule, _empty_rule())
            entry["rule"] = rule
            if item.get("category"):
                entry["category"] = str(item.get("category") or "")
            if section == "unexpected":
                entry["unexpected"] += 1
                entry["override_signals"] += 1
                entry["by_jurisdiction"][jurisdiction] += 1
                entry["by_document_type"][document_type] += 1
                entry["source_reports"][report_name] += 1
            elif section == "must_not_detect_violations":
                entry["must_not_detect_violations"] += 1
                entry["override_signals"] += 1
                entry["by_jurisdiction"][jurisdiction] += 1
                entry["by_document_type"][document_type] += 1
                entry["source_reports"][report_name] += 1
    for item in doc.get("unexpected_triage", []) or []:
        rule = str(item.get("rule") or "unknown")
        bucket = str(item.get("bucket") or "unknown")
        entry = detectors.setdefault(rule, _empty_rule())
        entry["rule"] = rule
        entry["unexpected_triage"][bucket] += 1


def _render_rule(entry: dict[str, Any]) -> dict[str, Any]:
    expected = int(entry["matched"]) + int(entry["missed"])
    emitted = int(entry["matched"]) + int(entry["unexpected"]) + int(entry["must_not_detect_violations"])
    return {
        "rule": entry["rule"],
        "category": entry["category"] or "unknown",
        "matched": entry["matched"],
        "missed": entry["missed"],
        "unexpected": entry["unexpected"],
        "must_not_detect_violations": entry["must_not_detect_violations"],
        "override_signals": entry["override_signals"],
        "recall": round(entry["matched"] / expected, 4) if expected else None,
        "precision_signal": round(entry["matched"] / emitted, 4) if emitted else None,
        "unexpected_triage": dict(sorted(entry["unexpected_triage"].items())),
        "by_jurisdiction": dict(sorted(entry["by_jurisdiction"].items())),
        "by_document_type": dict(sorted(entry["by_document_type"].items())),
        "source_reports": dict(sorted(entry["source_reports"].items())),
    }


def build_dashboard(eval_reports: list[Path], *, top: int = 20) -> dict[str, Any]:
    detectors: dict[str, dict[str, Any]] = {}
    source_reports: list[str] = []
    report_count = 0
    doc_count = 0
    for report_path in eval_reports:
        payload = _read_json(report_path)
        report_count += 1
        source_reports.append(_relative(report_path))
        summary = payload.get("summary") or {}
        doc_count += int(summary.get("doc_count", 0) or len(payload.get("documents", []) or []))
        _add_rule_counts(detectors, summary)
        for doc in payload.get("documents", []) or []:
            _add_doc_signals(detectors, doc, report_path)

    detector_rows = [_render_rule(entry) for entry in detectors.values()]
    detector_rows.sort(key=lambda item: (-int(item["override_signals"]), item["rule"]))
    top_rows = detector_rows[:max(0, top)]
    return {
        "schema_version": "junas.detector_dashboard.v1",
        "generated_at_unix": int(time.time()),
        "source_reports": source_reports,
        "summary": {
            "report_count": report_count,
            "doc_count": doc_count,
            "detector_count": len(detector_rows),
            "total_override_signals": sum(int(item["override_signals"]) for item in detector_rows),
            "total_unexpected": sum(int(item["unexpected"]) for item in detector_rows),
            "total_must_not_detect_violations": sum(
                int(item["must_not_detect_violations"]) for item in detector_rows
            ),
            "top_override_rules": [
                {
                    "rule": item["rule"],
                    "override_signals": item["override_signals"],
                    "unexpected": item["unexpected"],
                    "must_not_detect_violations": item["must_not_detect_violations"],
                }
                for item in top_rows
            ],
        },
        "detectors": detector_rows,
        "note": "Dashboard counts detector-level eval signals only; raw matched text is intentionally omitted.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Generate detector dashboard JSON from eval reports")
    parser.add_argument("--eval-report", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--top", type=int, default=20)
    args = parser.parse_args(argv)

    eval_reports = [path if path.is_absolute() else REPO_ROOT / path for path in args.eval_report]
    for path in eval_reports:
        if not path.exists():
            print(f"eval report missing: {path}", file=sys.stderr)
            return 2
    output = args.output if args.output.is_absolute() else REPO_ROOT / args.output
    dashboard = build_dashboard(eval_reports, top=args.top)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(json.dumps(dashboard, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(f"wrote {_relative(output)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
