"""Operator-facing status, inspection, and validation helpers."""
from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

import yaml
from pydantic import ValidationError

from benchmark.schema import Dataset
from benchmark.synthetic.promoter import AGGREGATE_DATASET
from benchmark.synthetic.reviewer import load_dataset_file, resolve_fixture
from benchmark.synthetic.taxonomy import DATASET_ROOT, GENERATOR_VERSION, PROMPT_VERSION, task_spec

REQUIRED_METADATA = frozenset(
    {
        "data_tier",
        "generator_model",
        "generator_version",
        "prompt_version",
        "seed",
        "generation_timestamp",
        "taxonomy_cell",
        "sglb_task",
    }
)


def _root(base_dir: Path | None) -> Path:
    return base_dir or DATASET_ROOT


def _yaml_files(path: Path) -> list[Path]:
    if not path.exists():
        return []
    return sorted(item for item in path.glob("*.yaml") if item.name != AGGREGATE_DATASET)


def status_for_task(*, task: str, base_dir: Path | None = None) -> dict[str, Any]:
    spec = task_spec(task)
    root = _root(base_dir)
    candidate_dir = root / spec.candidate_dir_name
    reviewed_dir = root / spec.reviewed_dir_name

    candidate_counts: Counter[str] = Counter()
    for path in _yaml_files(candidate_dir):
        try:
            payload = load_dataset_file(path)
            case = (payload.get("cases") or [{}])[0]
            status = str((case.get("metadata") or {}).get("review_status") or "missing")
        except (OSError, yaml.YAMLError, IndexError):
            status = "unreadable"
        candidate_counts[status] += 1

    reviewed_files = _yaml_files(reviewed_dir)
    aggregate = reviewed_dir / AGGREGATE_DATASET
    return {
        "task": task,
        "candidate_dir": str(candidate_dir),
        "reviewed_dir": str(reviewed_dir),
        "candidate_counts": dict(sorted(candidate_counts.items())),
        "candidate_total": sum(candidate_counts.values()),
        "reviewed_total": len(reviewed_files),
        "aggregate_dataset": str(aggregate),
        "aggregate_exists": aggregate.exists(),
    }


def show_fixture(*, fixture: str, task: str | None = None, base_dir: Path | None = None) -> dict[str, Any]:
    path = resolve_fixture(fixture, task=task, base_dir=_root(base_dir))
    payload = load_dataset_file(path)
    cases = payload.get("cases") or []
    if len(cases) != 1:
        raise ValueError(f"{path} must contain exactly one synthetic case")
    case = cases[0]
    metadata = case.get("metadata") or {}
    return {
        "fixture": str(path),
        "case_name": case.get("name"),
        "inputs": case.get("inputs"),
        "expected_output": case.get("expected_output"),
        "metadata": metadata,
        "body": _body_for_case(case),
    }


def _body_for_case(case: dict[str, Any]) -> str:
    inputs = case.get("inputs") or {}
    for key in ("clause_text", "scenario", "drafting_brief"):
        if key in inputs:
            return str(inputs[key])
    return ""


def validate_task(*, task: str, base_dir: Path | None = None) -> dict[str, Any]:
    spec = task_spec(task)
    root = _root(base_dir)
    candidate_dir = root / spec.candidate_dir_name
    reviewed_dir = root / spec.reviewed_dir_name
    errors: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []

    candidate_files = _yaml_files(candidate_dir)
    reviewed_files = _yaml_files(reviewed_dir)
    for path in candidate_files:
        _validate_case_file(path, task=task, expected_stage="candidate", errors=errors, warnings=warnings)
    for path in reviewed_files:
        _validate_case_file(path, task=task, expected_stage="reviewed", errors=errors, warnings=warnings)

    aggregate = reviewed_dir / AGGREGATE_DATASET
    if aggregate.exists():
        _validate_aggregate(aggregate, task=task, reviewed_files=reviewed_files, errors=errors, warnings=warnings)
    elif reviewed_files:
        warnings.append({"path": str(aggregate), "message": "reviewed fixtures exist but aggregate dataset is missing"})

    return {
        "task": task,
        "ok": not errors,
        "candidate_count": len(candidate_files),
        "reviewed_count": len(reviewed_files),
        "errors": errors,
        "warnings": warnings,
    }


def _validate_case_file(
    path: Path,
    *,
    task: str,
    expected_stage: str,
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> None:
    try:
        payload = load_dataset_file(path)
        dataset = Dataset.model_validate(payload)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        errors.append({"path": str(path), "message": f"invalid dataset schema: {exc}"})
        return
    if len(dataset.cases) != 1:
        errors.append({"path": str(path), "message": "synthetic fixture must contain exactly one case"})
        return
    case = dataset.cases[0]
    metadata = case.metadata
    missing = sorted(REQUIRED_METADATA - set(metadata))
    if missing:
        errors.append({"path": str(path), "message": f"missing metadata fields: {missing}"})
    if metadata.get("data_tier") != "synthetic":
        errors.append({"path": str(path), "message": "data_tier must be synthetic"})
    if metadata.get("sglb_task") != task:
        errors.append({"path": str(path), "message": f"sglb_task must be {task}"})
    if metadata.get("review_stage") != expected_stage:
        errors.append({"path": str(path), "message": f"review_stage must be {expected_stage}"})
    if expected_stage == "reviewed" and metadata.get("review_status") != "approved":
        errors.append({"path": str(path), "message": "reviewed fixture must have approved review_status"})
    if expected_stage == "candidate" and metadata.get("review_status") == "approved":
        warnings.append({"path": str(path), "message": "approved candidate is ready for promotion"})
    if metadata.get("generator_version") != GENERATOR_VERSION:
        warnings.append({"path": str(path), "message": "generator_version differs from current generator"})
    if metadata.get("prompt_version") != PROMPT_VERSION:
        warnings.append({"path": str(path), "message": "prompt_version differs from current prompt set"})
    if not _body_for_case(case.model_dump()):
        errors.append({"path": str(path), "message": "case body is empty"})


def _validate_aggregate(
    aggregate: Path,
    *,
    task: str,
    reviewed_files: list[Path],
    errors: list[dict[str, str]],
    warnings: list[dict[str, str]],
) -> None:
    try:
        payload = load_dataset_file(aggregate)
        dataset = Dataset.model_validate(payload)
    except (OSError, yaml.YAMLError, ValidationError) as exc:
        errors.append({"path": str(aggregate), "message": f"invalid aggregate dataset: {exc}"})
        return
    expected_names = {path.stem for path in reviewed_files}
    aggregate_names = {case.name for case in dataset.cases}
    if expected_names != aggregate_names:
        warnings.append(
            {
                "path": str(aggregate),
                "message": "aggregate dataset does not exactly match reviewed fixture filenames",
            }
        )
    for case in dataset.cases:
        if case.metadata.get("sglb_task") != task or case.metadata.get("review_stage") != "reviewed":
            errors.append({"path": str(aggregate), "message": f"aggregate contains non-reviewed case {case.name}"})
