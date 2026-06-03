"""Human-review metadata for synthetic candidate fixtures."""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from benchmark.synthetic.taxonomy import DATASET_ROOT, task_spec

VALID_DECISIONS = frozenset({"approve", "reject", "needs_edit"})


def utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")


def load_dataset_file(path: Path) -> dict[str, Any]:
    return yaml.safe_load(path.read_text(encoding="utf-8")) or {"cases": []}


def write_dataset_file(path: Path, payload: dict[str, Any]) -> None:
    path.write_text(
        yaml.safe_dump(payload, sort_keys=False, default_flow_style=False, width=120),
        encoding="utf-8",
    )


def resolve_fixture(fixture: str, *, task: str | None = None, base_dir: Path | None = None) -> Path:
    raw = Path(fixture)
    if raw.exists():
        return raw
    root = base_dir or DATASET_ROOT
    name = raw.name
    if not name.endswith(".yaml"):
        name = f"{name}.yaml"
    search_dirs: list[Path]
    if task:
        search_dirs = [root / task_spec(task).candidate_dir_name]
    else:
        search_dirs = [root / spec.candidate_dir_name for spec in task_spec_map()]
    matches = [candidate for directory in search_dirs for candidate in directory.glob(name) if candidate.exists()]
    if len(matches) == 1:
        return matches[0]
    if not matches:
        raise FileNotFoundError(f"fixture not found: {fixture}")
    raise ValueError(f"fixture is ambiguous: {fixture}")


def task_spec_map():
    from benchmark.synthetic.taxonomy import SYNTHETIC_TASKS

    return SYNTHETIC_TASKS.values()


def record_decision(
    *,
    fixture_path: Path,
    decision: str,
    reviewer: str | None = None,
    notes: str = "",
    reviewed_at: str | None = None,
) -> dict[str, Any]:
    if decision not in VALID_DECISIONS:
        raise ValueError(f"decision must be one of: {', '.join(sorted(VALID_DECISIONS))}")
    reviewer = (reviewer or os.environ.get("JUNAS_SYNTH_REVIEWER") or "local-reviewer").strip()
    if decision == "approve" and not reviewer:
        raise ValueError("reviewer is required for approval")

    payload = load_dataset_file(fixture_path)
    cases = payload.get("cases") or []
    if len(cases) != 1:
        raise ValueError("synthetic review expects one case per candidate fixture")
    case = cases[0]
    metadata = case.setdefault("metadata", {})
    status = {"approve": "approved", "reject": "rejected", "needs_edit": "needs_edit"}[decision]
    entry = {
        "decision": decision,
        "status": status,
        "reviewer": reviewer,
        "notes": notes.strip(),
        "reviewed_at_utc": reviewed_at or utc_now(),
        "generator_model": metadata.get("generator_model", ""),
        "generator_version": metadata.get("generator_version", ""),
        "prompt_version": metadata.get("prompt_version", ""),
    }
    history = metadata.get("_human_review_history")
    if not isinstance(history, list):
        history = []
    history.append(entry)
    metadata["review_status"] = status
    metadata["_human_review_status"] = status
    metadata["_human_review"] = entry
    metadata["_human_review_history"] = history
    write_dataset_file(fixture_path, payload)
    return entry


def review_summary(fixture_path: Path) -> dict[str, Any]:
    payload = load_dataset_file(fixture_path)
    case = (payload.get("cases") or [{}])[0]
    metadata = case.get("metadata") or {}
    return {
        "fixture": str(fixture_path),
        "case": case.get("name", fixture_path.stem),
        "review_status": metadata.get("review_status", "missing"),
        "review": metadata.get("_human_review"),
        "taxonomy_cell": metadata.get("taxonomy_cell"),
        "generator_model": metadata.get("generator_model"),
    }


def summary_json(fixture_path: Path) -> str:
    return json.dumps(review_summary(fixture_path), indent=2, sort_keys=True)
