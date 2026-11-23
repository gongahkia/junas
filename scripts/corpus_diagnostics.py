#!/usr/bin/env python3
"""Offline development error buckets against provisional model-reference annotations."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from junas.review.engine import PreSendReviewEngine  # noqa: E402
from junas.review.sensitivity import PII_RULE_MAP  # noqa: E402
from scripts.span_metrics import Span, _assignment  # noqa: E402


def diagnose(records: list[dict]) -> dict:
    engine = PreSendReviewEngine()
    counts: Counter = Counter()
    details = []
    by_entity: Counter = Counter()
    by_rule: Counter = Counter()
    for record in records:
        if record.get("split") == "holdout":
            raise ValueError("development diagnostics refuse protected holdout records")
        if not record.get("accepted") or record.get("status") != "completed":
            continue
        text, ref = record["text"], record["consensus"]
        result = engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
        )
        unit = ("development", record["document_id"], "model_reference")
        gold = [Span(unit, s["start_char"], s["end_char"], "PII", s["label"]) for s in ref["pii"]]
        evidence = result.sensitivity["pii"]["evidence"]
        predicted = [Span(unit, s["start_char"], s["end_char"], "PII", s["label"]) for s in evidence]
        exact, overlap = _assignment(gold, predicted, "exact"), _assignment(gold, predicted, "overlap")
        buckets = []
        for i, g in enumerate(gold):
            if i not in exact.values():
                kind = "boundary_error" if i in overlap.values() else "missed_entity"
                counts[kind] += 1
                by_entity[(kind, g.label)] += 1
                buckets.append({"kind": kind, "label": g.label, "start_char": g.start, "end_char": g.end})
        for i, p in enumerate(predicted):
            if i not in overlap:
                kind = "unmatched_prediction" if ref["coverage"] == "exhaustive" else "unjudged_prediction"
                counts[kind] += 1
                by_entity[(kind, p.label)] += 1
                by_rule[(kind, evidence[i]["rule"])] += 1
                buckets.append({"kind": kind, "label": p.label, "start_char": p.start, "end_char": p.end})
        for finding in result.findings:
            if finding.category == "PII" and not any(finding.rule in rules for rules in PII_RULE_MAP.values()):
                counts["unmapped_rule"] += 1
                by_rule[("unmapped_rule", finding.rule)] += 1
            if finding.category in {"PII", "MNPI"}:
                target = finding.category.lower()
                if ref["document_labels"][target]["state"] == "absent":
                    counts["negative_reference_signal"] += 1
                    by_rule[("negative_reference_signal", finding.rule)] += 1
        for target in ("pii", "mnpi"):
            expected = ref["document_labels"][target]["state"]
            state = result.sensitivity[target]["state"]
            if expected != "unknown" and state == "unknown":
                counts[f"{target}_abstention"] += 1
                buckets.append(
                    {
                        "kind": f"{target}_abstention",
                        "expected": expected,
                        "observed": state,
                        "decision_diagnostics": result.sensitivity[target].get("diagnostics", []),
                    }
                )
            elif expected != "unknown" and (expected == "present") != (state == "present"):
                counts[f"{target}_document_disagreement"] += 1
                buckets.append({"kind": f"{target}_document_disagreement", "expected": expected, "observed": state})
        details.append({"document_id": record["document_id"], "quadrant": ref["quadrant"], "buckets": buckets})
    return {
        "schema_version": "junas.corpus_diagnostics.v1",
        "reference": "model agreement, not independent accuracy",
        "documents": len(details),
        "counts": dict(counts),
        "by_entity": [{"kind": k, "label": v, "count": n} for (k, v), n in sorted(by_entity.items())],
        "by_rule": [{"kind": k, "rule": v, "count": n} for (k, v), n in sorted(by_rule.items())],
        "details": details,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.records.read_text().splitlines() if line.strip()]
    report = diagnose(records)
    with args.output.open("x") as stream:
        json.dump(report, stream, indent=2)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
