#!/usr/bin/env python3
"""Build a JSON ledger for candidate generation/autolabel/eval runs."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.candidate_corpus_report import DEFAULT_CORPUS  # noqa: E402


def _read_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _read_jsonl(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip():
            rows.append(json.loads(line))
    return rows


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(REPO_ROOT))
    except ValueError:
        return str(path)


def _pipeline_summary(run_dir: Path) -> dict[str, Any]:
    rows = _read_jsonl(run_dir / "pipeline_manifest.jsonl")
    finish_rows = [row for row in rows if row.get("event") == "finish"]
    return {
        "manifest": _relative(run_dir / "pipeline_manifest.jsonl") if rows else "",
        "steps": [
            {
                "step": row.get("step"),
                "returncode": row.get("returncode"),
                "elapsed_seconds": row.get("elapsed_seconds"),
            }
            for row in finish_rows
        ],
        "elapsed_seconds": sum(int(row.get("elapsed_seconds") or 0) for row in finish_rows),
        "failed_steps": [row.get("step") for row in finish_rows if int(row.get("returncode") or 0) != 0],
    }


def _generation_summary(run_dir: Path) -> dict[str, Any]:
    rows = _read_jsonl(run_dir / "generation_manifest.jsonl")
    events = Counter(str(row.get("event") or "unknown") for row in rows)
    summary = next((row for row in reversed(rows) if row.get("event") == "summary"), {})
    return {
        "manifest": _relative(run_dir / "generation_manifest.jsonl") if rows else "",
        "provider": summary.get("provider", ""),
        "model": summary.get("model", ""),
        "expected": int(summary.get("expected") or 0),
        "planned": int(summary.get("planned") or events.get("planned", 0)),
        "generated": int(summary.get("generated") or events.get("generated", 0)),
        "failed": int(summary.get("failed") or events.get("failed", 0)),
        "skipped_existing_or_complete": int(summary.get("skipped_existing_or_complete") or 0),
        "elapsed_seconds": int(summary.get("elapsed_seconds") or 0),
        "events": dict(sorted(events.items())),
    }


def _autolabel_summary(run_dir: Path) -> dict[str, Any]:
    rows = _read_jsonl(run_dir / "autolabel_manifest.jsonl")
    events = [row for row in rows if row.get("event") == "fixture"]
    statuses = Counter(str(row.get("status") or "unknown") for row in events)
    warnings = sum(int(row.get("warnings") or 0) for row in events)
    summary = next((row for row in reversed(rows) if row.get("event") == "summary"), {})
    skipped = sum(count for status, count in statuses.items() if status.startswith("skipped"))
    return {
        "manifest": _relative(run_dir / "autolabel_manifest.jsonl") if rows else "",
        "provider": summary.get("provider", ""),
        "model": summary.get("model", ""),
        "label_model": summary.get("label_model", ""),
        "fixtures": len(events),
        "labeled": int(summary.get("labeled") or statuses.get("labeled", 0)),
        "skipped": int(summary.get("skipped") or skipped),
        "errors": int(summary.get("errors") or statuses.get("error", 0)),
        "warnings": warnings,
        "elapsed_seconds": int(summary.get("elapsed_seconds") or 0),
        "workers": int(summary.get("workers") or 0),
        "statuses": dict(sorted(statuses.items())),
    }


def _evaluation_summary(run_dir: Path) -> dict[str, Any]:
    path = run_dir / "candidate_evaluation.json"
    if not path.exists():
        return {"report": "", "summary": {}}
    payload = _read_json(path)
    return {
        "report": _relative(path),
        "summary": payload.get("summary", {}),
    }


def _cost_summary(candidate_dir: Path) -> dict[str, Any]:
    text_chars = 0
    label_chars = 0
    txt_count = 0
    labels_count = 0
    for path in candidate_dir.glob("**/*.txt"):
        txt_count += 1
        text_chars += len(path.read_text(encoding="utf-8"))
    for path in candidate_dir.glob("**/*.labels.json"):
        labels_count += 1
        label_chars += len(path.read_text(encoding="utf-8"))
    approx_tokens = math.ceil((text_chars + label_chars) / 4)
    price_env = {
        key: os.environ.get(key, "")
        for key in (
            "KAYPOH_FIXTURE_INPUT_PRICE_PER_1M",
            "KAYPOH_FIXTURE_OUTPUT_PRICE_PER_1M",
            "KAYPOH_AUTOLABEL_INPUT_PRICE_PER_1M",
            "KAYPOH_AUTOLABEL_OUTPUT_PRICE_PER_1M",
        )
        if os.environ.get(key, "")
    }
    return {
        "status": "estimate_only_no_provider_token_usage",
        "fixture_text_files": txt_count,
        "label_files": labels_count,
        "fixture_text_chars": text_chars,
        "label_json_chars": label_chars,
        "approx_fixture_and_label_tokens": approx_tokens,
        "price_env_present": sorted(price_env),
        "note": (
            "Provider request/response token usage is not exposed by the current batch scripts. "
            "This lower-bound text/label token estimate is for run sizing, not billing reconciliation."
        ),
    }


def build_ledger(run_dir: Path, *, candidate_dir: Path = DEFAULT_CORPUS) -> dict[str, Any]:
    run_dir = run_dir.resolve()
    candidate_dir = candidate_dir.resolve()
    return {
        "generated_at_unix": int(time.time()),
        "run_dir": _relative(run_dir),
        "candidate_dir": _relative(candidate_dir),
        "pipeline": _pipeline_summary(run_dir),
        "generation": _generation_summary(run_dir),
        "autolabel": _autolabel_summary(run_dir),
        "evaluation": _evaluation_summary(run_dir),
        "cost": _cost_summary(candidate_dir),
        "note": "candidate run ledger; cost is approximate unless provider token usage is wired into manifests.",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build candidate run ledger")
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--candidate-dir", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--output", type=Path, help="Write JSON ledger")
    args = parser.parse_args(argv)

    run_dir = args.run_dir if args.run_dir.is_absolute() else REPO_ROOT / args.run_dir
    candidate_dir = args.candidate_dir if args.candidate_dir.is_absolute() else REPO_ROOT / args.candidate_dir
    if not run_dir.exists():
        print(f"run dir missing: {run_dir}", file=sys.stderr)
        return 2
    if not candidate_dir.exists():
        print(f"candidate dir missing: {candidate_dir}", file=sys.stderr)
        return 2
    ledger = build_ledger(run_dir, candidate_dir=candidate_dir)
    rendered = json.dumps(ledger, indent=2, sort_keys=True) + "\n"
    output = args.output if args.output else run_dir / "run_ledger.json"
    output = output if output.is_absolute() else REPO_ROOT / output
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(rendered, encoding="utf-8")
    print(f"wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
