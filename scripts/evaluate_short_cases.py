#!/usr/bin/env python3
"""Replay authored short development cases locally; no model calls or holdout claims."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from junas import classify_text  # noqa: E402


def evaluate(cases: list[dict]) -> list[dict]:
    ids: set[str] = set()
    rows = []
    for case in cases:
        if (
            case.get("split") != "development"
            or case.get("reference_kind") != "authored_synthetic_development_expectation"
            or not isinstance(case.get("id"), str)
            or case["id"] in ids
        ):
            raise ValueError("unique authored development cases required; holdout refused")
        ids.add(case["id"])
        started = time.perf_counter()
        result = classify_text(case["text"], source_jurisdiction="SG", destination_jurisdiction="SG")
        rows.append(
            {
                "id": case["id"],
                "text": case["text"],
                "text_sha256": hashlib.sha256(case["text"].encode()).hexdigest(),
                "states": {key: result.sensitivity[key]["state"] for key in ("pii", "mnpi")},
                "pii_evidence": result.sensitivity["pii"]["evidence"],
                "inference_ms": (time.perf_counter() - started) * 1000,
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cases", type=Path, default=ROOT / "browser/eval/cases.json")
    parser.add_argument("--output", required=True, type=Path)
    args = parser.parse_args()
    cases = json.loads(args.cases.read_text())
    rows = evaluate(cases)
    with args.output.open("x") as stream:
        json.dump(rows, stream, indent=2)
        stream.write("\n")
    print(json.dumps({"documents": len(rows), "output": str(args.output)}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
