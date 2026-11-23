#!/usr/bin/env python3
"""Export consumed model references for development; never retire an unseen holdout."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts import model_corpus as corpus  # noqa: E402
from scripts.corpus_report import read_records  # noqa: E402


def retire(run_dir: Path, output: Path) -> dict:
    corpus.require(not output.resolve().is_relative_to(ROOT), "development references must remain private")
    corpus.require(not output.exists(), "development export already exists")
    marker_path = run_dir / "holdout-consumed.json"
    marker = json.loads(marker_path.read_text())
    corpus.require(marker.get("status") == "consumed_for_evaluation", "unconsumed holdout refused")
    records = read_records(run_dir / "combined-records.jsonl")
    corpus.require(corpus.identity(records) == marker["records_sha256"], "consumed source identity mismatch")
    corpus.require(all(r.get("split") == "holdout" for r in records), "holdout source partition required")
    provenance = {
        "origin": "consumed_model_holdout",
        "source_records_sha256": marker["records_sha256"],
        "consumption_marker_sha256": hashlib.sha256(marker_path.read_bytes()).hexdigest(),
        "fresh_validation_eligible": False,
    }
    exported = []
    for record in records:
        if not record.get("accepted") or record.get("status") != "completed":
            continue
        corpus.require(corpus.input_identity(record["text"]) == record["text_sha256"], "source text changed")
        corpus.require(len(record["annotations"]) == 3, "three actual annotations required")
        for annotation in record["annotations"]:
            corpus.validate_annotations(annotation["output"], record["text"])
        corpus.require(
            record["consensus"] == corpus.consensus([a["output"] for a in record["annotations"]]),
            "reference consensus changed",
        )
        exported.append({**copy.deepcopy(record), "split": "development", "development_provenance": provenance})
    corpus.require(bool(exported), "completed accepted references required")
    corpus.require(len({r["document_id"] for r in exported}) == len(exported), "duplicate document identity")
    with output.open("x") as stream:
        for record in exported:
            stream.write(json.dumps(record, sort_keys=True, ensure_ascii=False) + "\n")
    return {
        "documents": len(exported),
        "dataset_sha256": corpus.identity(exported),
        "reference": "consumed model-reference development replay; never unseen validation",
        **provenance,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    print(json.dumps(retire(args.run_dir, args.output), sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
