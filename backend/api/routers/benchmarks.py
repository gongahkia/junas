"""SG-LegalBench HTTP surface.

Wraps the in-process ``benchmark`` harness behind a small REST API. All
runs are synchronous in v0 to keep semantics simple; queueing moves to
Celery once we have task volumes that need it.

Receipts are persisted to ``$JUNAS_BENCHMARK_RUNS_DIR`` (defaults to
``backend/benchmark/runs/``). The leaderboard endpoint reads every JSON
in that directory and aggregates per-task means.
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from benchmark.evaluators import EVALUATORS
from benchmark.registry import TASKS
from benchmark.runner import RunSummary, run as runner_run, write_summary

router = APIRouter(prefix="/benchmarks")


def _runs_dir() -> Path:
    raw = os.environ.get("JUNAS_BENCHMARK_RUNS_DIR")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent.parent / "benchmark" / "runs"


class RunRequest(BaseModel):
    workflow: str = Field(..., min_length=1)
    dataset: str = Field(..., min_length=1, description="path or relative key to a YAML dataset")
    evaluators: list[str] = Field(..., min_length=1)
    max_concurrency: int = Field(5, ge=1, le=64)
    strict: bool = Field(
        False,
        description="reject weak-tier evaluators (publication mode; see docs/coverage-matrix.md §4.2)",
    )

    model_config = ConfigDict(
        json_schema_extra={
            "examples": [
                {
                    "workflow": "sglb_04",
                    "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
                    "evaluators": ["multi_label_f1"],
                    "strict": True,
                }
            ]
        }
    )


class RunResponse(BaseModel):
    run_id: str
    workflow: str
    dataset: str
    total_cases: int
    per_evaluator_mean: dict[str, float]
    started_at: str
    finished_at: str
    strict: bool
    weak_evaluators_used: list[str]


class LeaderboardEntry(BaseModel):
    run_id: str
    workflow: str
    dataset: str
    finished_at: str
    total_cases: int
    per_evaluator_mean: dict[str, float]
    strict: bool


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    aggregated_per_workflow: dict[str, dict[str, float]]


class TaskInfo(BaseModel):
    name: str


class EvaluatorInfo(BaseModel):
    name: str
    strength: str


def _resolve_dataset_path(raw: str) -> Path:
    candidate = Path(raw)
    if candidate.is_absolute() and candidate.exists():
        return candidate
    backend_root = Path(__file__).resolve().parent.parent.parent
    rel = backend_root / raw
    if rel.exists():
        return rel
    if candidate.exists():
        return candidate
    raise HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail=f"dataset not found: {raw}",
    )


def _run_id(summary: RunSummary) -> str:
    started = summary.started_at.replace(":", "").replace("-", "").replace(".", "")
    return f"{started[:15]}-{summary.workflow}"


@router.get("/tasks", response_model=list[TaskInfo])
async def list_tasks() -> list[TaskInfo]:
    return [TaskInfo(name=name) for name in sorted(TASKS)]


@router.get("/evaluators", response_model=list[EvaluatorInfo])
async def list_evaluators() -> list[EvaluatorInfo]:
    return [
        EvaluatorInfo(name=name, strength=ev.strength.value)
        for name, ev in sorted(EVALUATORS.items())
    ]


@router.post("/run", response_model=RunResponse)
async def run_benchmark(body: RunRequest) -> RunResponse:
    if body.workflow not in TASKS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown workflow: {body.workflow!r}",
        )
    unknown_evaluators = [e for e in body.evaluators if e not in EVALUATORS]
    if unknown_evaluators:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"unknown evaluators: {unknown_evaluators}",
        )

    dataset_path = _resolve_dataset_path(body.dataset)

    try:
        summary = await runner_run(
            workflow=body.workflow,
            dataset_path=dataset_path,
            evaluators=body.evaluators,
            max_concurrency=body.max_concurrency,
            strict=body.strict,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    runs_dir = _runs_dir()
    runs_dir.mkdir(parents=True, exist_ok=True)
    run_id = _run_id(summary)
    receipt_path = runs_dir / f"{run_id}.json"
    write_summary(summary, receipt_path)

    return RunResponse(
        run_id=run_id,
        workflow=summary.workflow,
        dataset=summary.dataset,
        total_cases=summary.total_cases,
        per_evaluator_mean=summary.per_evaluator_mean(),
        started_at=summary.started_at,
        finished_at=summary.finished_at,
        strict=summary.strict,
        weak_evaluators_used=summary.weak_evaluators_used,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard() -> LeaderboardResponse:
    runs_dir = _runs_dir()
    entries: list[LeaderboardEntry] = []
    if runs_dir.exists():
        for receipt in sorted(runs_dir.glob("*.json")):
            try:
                payload: dict[str, Any] = json.loads(receipt.read_text(encoding="utf-8"))
            except json.JSONDecodeError:
                continue
            entries.append(
                LeaderboardEntry(
                    run_id=receipt.stem,
                    workflow=payload.get("workflow", ""),
                    dataset=payload.get("dataset", ""),
                    finished_at=payload.get("finished_at", ""),
                    total_cases=int(payload.get("total_cases", 0) or 0),
                    per_evaluator_mean={
                        k: float(v) for k, v in (payload.get("per_evaluator_mean") or {}).items()
                    },
                    strict=bool(payload.get("strict", False)),
                )
            )

    aggregated: dict[str, dict[str, list[float]]] = {}
    for entry in entries:
        wf = aggregated.setdefault(entry.workflow, {})
        for evaluator, score in entry.per_evaluator_mean.items():
            wf.setdefault(evaluator, []).append(score)

    aggregated_mean: dict[str, dict[str, float]] = {
        workflow: {
            evaluator: sum(scores) / len(scores) if scores else 0.0
            for evaluator, scores in evaluators.items()
        }
        for workflow, evaluators in aggregated.items()
    }

    entries.sort(key=lambda e: e.finished_at, reverse=True)
    return LeaderboardResponse(entries=entries, aggregated_per_workflow=aggregated_mean)
