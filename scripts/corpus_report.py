#!/usr/bin/env python3
"""Offline development reporting and one-time consumption of a fresh model-reference holdout."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "src")]

from scripts.corpus_partitions import validate_partition_records  # noqa: E402
from scripts.model_corpus import (  # noqa: E402
    consensus,
    entity_coverage,
    evaluate_records,
    identity,
    input_identity,
    quadrant_coverage,
    require,
    validate_annotations,
    write_new,
)
from scripts.span_metrics import reproducibility  # noqa: E402


def read_records(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text().splitlines() if line.strip()]


def release_holdout(run_dir: Path, development: list[dict], output: Path) -> dict:
    require(not output.exists(), "report destination already exists")
    manifest = json.loads((run_dir / "manifest.json").read_text())
    require(manifest.get("sampling", {}).get("split") == "holdout", "not a reserved holdout run")
    records = read_records(run_dir / "combined-records.jsonl")
    require(bool(records) and all(r.get("split") == "holdout" for r in records), "mixed or empty holdout partition")
    ready = [r for r in records if r.get("accepted") and r.get("status") == "completed"]
    require(bool(ready), "no resolved holdout reference records")
    require(bool(development), "development exclusion sources required")
    config = manifest["config"]
    require(manifest["config_sha256"] == identity(config), "holdout configuration mismatch")
    require(
        quadrant_coverage(records, config)["coverage_passed"] and entity_coverage(records, config)["coverage_passed"],
        "holdout quadrant or entity coverage incomplete",
    )
    for record in ready:
        require(input_identity(record["text"]) == record["text_sha256"], "holdout source mismatch")
        annotations = record["annotations"]
        require(len(annotations) == 3, "three actual judge annotations required")
        for annotation in annotations:
            validate_annotations(annotation["output"], record["text"])
        require(record["consensus"] == consensus([a["output"] for a in annotations]), "holdout consensus mismatch")
    validate_partition_records(development, [r for r in records if "text" in r])
    snapshot = reproducibility(Path(__file__))
    # consume before computing/reporting any metric; a crash leaves the release visible.
    write_new(
        run_dir / "holdout-consumed.json",
        {
            "status": "consumed_for_evaluation",
            "records_sha256": identity(records),
            "development_records_sha256": identity(development),
            "classifier": snapshot,
            "output": str(output.resolve()),
            "independent_ground_truth": False,
        },
    )
    evaluation = evaluate_records([{**r, "split": "released_holdout"} for r in records])
    report = {
        "schema_version": "junas.holdout_release.v1",
        "status": "consumed",
        "documents": len(ready),
        "reference": "fresh model-consensus labels; independent accuracy remains unavailable",
        "reproducibility": snapshot,
        "evaluation": evaluation,
    }
    write_new(output, report)
    return report


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("development", "release-holdout"))
    parser.add_argument("--records", type=Path)
    parser.add_argument("--run-dir", type=Path)
    parser.add_argument("--development-records", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.command == "development":
        require(args.records is not None, "development records required")
        records = read_records(args.records)
        require(all(r.get("split", "development") == "development" for r in records), "development partition required")
        report = evaluate_records(records)
        report.update(reproducibility=reproducibility(Path(__file__)), inputs_sha256=identity(records))
        write_new(args.output, report)
    else:
        require(
            args.run_dir is not None and args.development_records is not None,
            "holdout run and development registry required",
        )
        release_holdout(args.run_dir, read_records(args.development_records), args.output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
