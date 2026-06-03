"""Promotion from synthetic candidates to reviewed datasets."""
from __future__ import annotations

import json
import shutil
from pathlib import Path
from typing import Any

import yaml

from benchmark.synthetic.reviewer import load_dataset_file, utc_now, write_dataset_file
from benchmark.synthetic.taxonomy import DATASET_ROOT, task_spec

AUDIT_LOG = "promotion_audit.jsonl"
AGGREGATE_DATASET = "dataset.yaml"


def _relative(path: Path) -> str:
    try:
        return str(path.relative_to(Path.cwd()))
    except ValueError:
        return str(path)


def _approved(case: dict[str, Any]) -> bool:
    metadata = case.get("metadata") or {}
    review = metadata.get("_human_review")
    return (
        metadata.get("review_status") == "approved"
        and metadata.get("_human_review_status") == "approved"
        and isinstance(review, dict)
        and bool(str(review.get("reviewer") or "").strip())
    )


def _audit_entry(*, source: Path, target: Path, case: dict[str, Any], promoted_at: str) -> dict[str, Any]:
    metadata = case.get("metadata") or {}
    review = metadata.get("_human_review") or {}
    return {
        "promoted_at_utc": promoted_at,
        "source_fixture": _relative(source),
        "target_fixture": _relative(target),
        "case_name": case.get("name"),
        "task": metadata.get("sglb_task"),
        "data_tier": metadata.get("data_tier"),
        "generator_model": metadata.get("generator_model"),
        "generator_version": metadata.get("generator_version"),
        "prompt_version": metadata.get("prompt_version"),
        "seed": metadata.get("seed"),
        "generation_timestamp": metadata.get("generation_timestamp"),
        "taxonomy_cell": metadata.get("taxonomy_cell"),
        "reviewer": review.get("reviewer"),
        "reviewed_at_utc": review.get("reviewed_at_utc"),
    }


def _single_case_from(path: Path) -> dict[str, Any]:
    payload = load_dataset_file(path)
    cases = payload.get("cases") or []
    if len(cases) != 1:
        raise ValueError(f"{path} must contain exactly one case")
    return cases[0]


def write_aggregate_dataset(reviewed_dir: Path) -> Path:
    cases: list[dict[str, Any]] = []
    for path in sorted(reviewed_dir.glob("*.yaml")):
        if path.name == AGGREGATE_DATASET:
            continue
        cases.append(_single_case_from(path))
    aggregate = reviewed_dir / AGGREGATE_DATASET
    aggregate.write_text(
        yaml.safe_dump({"cases": cases}, sort_keys=False, default_flow_style=False, width=120),
        encoding="utf-8",
    )
    return aggregate


def promote_task(*, task: str, base_dir: Path | None = None) -> dict[str, Any]:
    spec = task_spec(task)
    root = base_dir or DATASET_ROOT
    candidate_dir = root / spec.candidate_dir_name
    reviewed_dir = root / spec.reviewed_dir_name
    reviewed_dir.mkdir(parents=True, exist_ok=True)

    promoted_at = utc_now()
    promoted: list[dict[str, Any]] = []
    skipped: list[dict[str, str]] = []
    errors: list[str] = []

    for source in sorted(candidate_dir.glob("*.yaml")):
        try:
            payload = load_dataset_file(source)
            cases = payload.get("cases") or []
            if len(cases) != 1:
                errors.append(f"{source}: expected exactly one case")
                continue
            case = cases[0]
        except (OSError, yaml.YAMLError) as exc:
            errors.append(f"{source}: unreadable: {exc}")
            continue

        if not _approved(case):
            status = (case.get("metadata") or {}).get("review_status", "missing")
            skipped.append({"fixture": str(source), "reason": f"not_approved:{status}"})
            continue

        metadata = case.setdefault("metadata", {})
        metadata["review_stage"] = "reviewed"
        metadata["review_status"] = "approved"
        target = reviewed_dir / source.name
        if target.exists():
            errors.append(f"refusing to overwrite reviewed fixture: {target}")
            continue
        entry = _audit_entry(source=source, target=target, case=case, promoted_at=promoted_at)
        metadata["_promotion"] = entry
        write_dataset_file(source, payload)
        shutil.move(str(source), str(target))
        with (reviewed_dir / AUDIT_LOG).open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(entry, sort_keys=True, separators=(",", ":")) + "\n")
        promoted.append(entry)

    aggregate = write_aggregate_dataset(reviewed_dir)
    return {
        "task": task,
        "candidate_dir": str(candidate_dir),
        "reviewed_dir": str(reviewed_dir),
        "aggregate_dataset": str(aggregate),
        "promoted": promoted,
        "skipped": skipped,
        "errors": errors,
    }
