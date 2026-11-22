#!/usr/bin/env python3
"""Offline development gates; never a replacement for fresh independent evaluation."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts import model_corpus as corpus  # noqa: E402
from scripts.span_metrics import reproducibility  # noqa: E402


def scorecard(records: list[dict], targets: dict) -> dict:
    corpus.require(bool(records), "development records required")
    identities: set[str] = set()
    for record in records:
        document_id = record.get("document_id")
        corpus.require(isinstance(document_id, str) and bool(document_id), "document identity required")
        corpus.require(document_id not in identities, "duplicate document identity; evaluate source runs separately")
        identities.add(document_id)
        corpus.require(record.get("split", "development") == "development", "development only; holdout refused")
        corpus.require(
            record.get("status") == "completed" and record.get("accepted") is True,
            "accepted completed references required",
        )
        corpus.require(corpus.input_identity(record["text"]) == record["text_sha256"], "source identity mismatch")
        annotations = record["annotations"]
        corpus.require(len(annotations) == 3, "three actual annotations required")
        for a in annotations:
            corpus.validate_annotations(a["output"], record["text"])
        corpus.require(
            record["consensus"] == corpus.consensus([a["output"] for a in annotations]), "reference consensus mismatch"
        )
    evaluation = corpus.evaluate_records(records)
    presence = evaluation["contextual_document_presence"]
    measurements = {}
    for category, positive_quadrants in (("pii", ("pii_only", "both")), ("mnpi", ("mnpi_only", "both"))):
        totals = presence["counts"][category]
        unknown_positive = sum(presence["by_quadrant"][q][category]["unknown"] for q in positive_quadrants)
        unknown_negative = totals["unknown"] - unknown_positive
        positives = totals["tp"] + totals["fn"] + unknown_positive
        negatives = totals["fp"] + totals["tn"] + unknown_negative
        corpus.require(positives > 0 and negatives > 0, "both reference states required for each target")
        measurements.update(
            {
                category + "_positive_detection": totals["tp"] / positives,
                category + "_negative_flag_rate": totals["fp"] / negatives,
                category + "_positive_abstention_rate": unknown_positive / positives,
                category + "_negative_abstention_rate": unknown_negative / negatives,
            }
        )
    for mode in ("exact", "overlap"):
        metric = evaluation["contextual_pii"][mode]
        corpus.require(metric["gold"] > 0, "positive reference spans required")
        measurements["pii_" + mode + "_span_agreement"] = metric["matched"] / metric["gold"]
    corpus.require(isinstance(targets, dict) and bool(targets), "explicit engineering targets required")
    checks = {}
    for name, threshold in targets.items():
        corpus.require(name.endswith(("_min", "_max")) and name[:-4] in measurements, "unknown engineering target")
        corpus.require(type(threshold) in (int, float) and 0 <= threshold <= 1, "target must be in [0,1]")
        value = measurements[name[:-4]]
        checks[name] = {
            "target": threshold,
            "observed": value,
            "passed": value >= threshold if name.endswith("_min") else value <= threshold,
        }
    return {
        "schema_version": "junas.sensitivity_development.v1",
        "passed": all(c["passed"] for c in checks.values()),
        "reference": "development model-reference agreement after tuning; not independent accuracy",
        "dataset_sha256": corpus.identity(records),
        "targets": checks,
        "measurements": measurements,
        "evaluation": evaluation,
        "reproducibility": reproducibility(Path(__file__)),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--records", required=True, type=Path)
    parser.add_argument("--targets", type=Path, default=ROOT / "config/sensitivity-development-gates.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    records = [json.loads(line) for line in args.records.read_text().splitlines() if line.strip()]
    result = scorecard(records, json.loads(args.targets.read_text()))
    corpus.write_new(args.output, result)
    print(json.dumps({k: result[k] for k in ("passed", "measurements")}, sort_keys=True))
    return 0 if result["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
