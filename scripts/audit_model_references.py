"""Read-only reference QA for a consumed cohort; never relabel model votes."""

from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from junas.review.sensitivity import DOB_CONTEXT, valid_birth_date  # noqa: E402
from scripts import model_corpus as corpus  # noqa: E402
from scripts.corpus_report import read_records  # noqa: E402


def audit(run: Path) -> dict:
    marker = json.loads((run / "holdout-consumed.json").read_text())
    corpus.require(marker.get("status") == "consumed_for_evaluation", "unconsumed cohort refused")
    records = read_records(run / "combined-records.jsonl")
    corpus.require(corpus.identity(records) == marker["records_sha256"], "consumed source identity mismatch")
    states: Counter = Counter()
    flags: Counter = Counter()
    unresolved_elements: Counter = Counter()
    details = []
    for record in records:
        if record["status"] != "completed":
            continue
        text = record["text"]
        corpus.require(corpus.input_identity(text) == record["text_sha256"], "source text changed")
        annotations = record["annotations"]
        corpus.require(len(annotations) == 3, "three actual annotations required")
        for annotation in annotations:
            corpus.validate_annotations(annotation["output"], text)
        reference = corpus.consensus([a["output"] for a in annotations])
        corpus.require(reference == record["consensus"], "reference consensus changed")
        states[reference["quadrant"]] += 1
        issues = []
        if reference["quadrant"] == "unknown":
            issues.append("unresolved_document_votes")
            for annotation in annotations:
                for span in annotation["output"]["mnpi"]:
                    unresolved_elements.update(
                        {
                            "public_status:" + span["public_status"]: 1,
                            "potential_materiality:" + span["potential_materiality"]: 1,
                        }
                    )
        for span in reference["pii"]:
            if span["label"] != "QUASI_IDENTIFIER_COMBINATION":
                continue
            start, end = span["start_char"], span["end_char"]
            if text[end : end + 1] == ")" and "(" in span["matched_text"]:
                issues.append("trailing_delimiter_boundary")
            for birth in DOB_CONTEXT.finditer(text):
                a, b = birth.span("value")
                if (
                    start <= a < b <= end
                    and valid_birth_date(birth.group("value"))
                    and not any(
                        s["label"] == "DATE_OF_BIRTH" and (s["start_char"], s["end_char"]) == (a, b)
                        for s in reference["pii"]
                    )
                ):
                    issues.append("unlabelled_birth_subentity")
        flags.update(set(issues))
        if issues:
            details.append(
                {
                    "document_id": record["document_id"],
                    "accepted": record["accepted"],
                    "flags": sorted(set(issues)),
                    "votes": {
                        c: dict(Counter(v["state"] for v in reference["document_labels"][c]["votes"]))
                        for c in ("pii", "mnpi")
                    },
                }
            )
    return {
        "schema_version": "junas.reference_audit.v1",
        "records_sha256": marker["records_sha256"],
        "candidates": len(records),
        "completed_reference_states": dict(states),
        "flagged_documents": dict(flags),
        "unresolved_mnpi_span_vote_elements": dict(unresolved_elements),
        "details": details,
        "reference_labels_changed": False,
        "paid_api_calls": 0,
        "calibrated_confidence": None,
        "independent_ground_truth": False,
        "interpretation": "QA candidates only; flags neither adjudicate correctness nor resolve unknown votes",
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = audit(args.run_dir)
    corpus.write_new(args.output, result)
    print(json.dumps({"candidates": result["candidates"], "flagged_documents": result["flagged_documents"]}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
