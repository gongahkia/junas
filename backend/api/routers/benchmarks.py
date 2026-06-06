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
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field

from benchmark.evaluators import EVALUATORS
from benchmark.registry import TASKS, is_benchmark_eligible
from benchmark.runner import RunSummary, load_dataset, run as runner_run, write_summary

router = APIRouter(prefix="/benchmarks")


def _runs_dir() -> Path:
    raw = os.environ.get("JUNAS_BENCHMARK_RUNS_DIR")
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent.parent / "benchmark" / "runs"


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


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
    data_tier: str = "regulator"


class LeaderboardEntry(BaseModel):
    run_id: str
    workflow: str
    dataset: str
    finished_at: str
    total_cases: int
    per_evaluator_mean: dict[str, float]
    strict: bool
    data_tier: str = "regulator"


class LeaderboardResponse(BaseModel):
    entries: list[LeaderboardEntry]
    aggregated_per_workflow: dict[str, dict[str, float]]


class CaseEvaluatorScore(BaseModel):
    score: float
    error: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class RunCaseDetail(BaseModel):
    case_name: str
    input: dict[str, Any] = Field(default_factory=dict)
    expected: dict[str, Any] | None = None
    actual: Any = ""
    evaluator_scores: dict[str, CaseEvaluatorScore] = Field(default_factory=dict)


class RunDetailResponse(RunResponse):
    evaluators: list[str]
    provenance: dict[str, Any] = Field(default_factory=dict)
    contamination_summary: dict[str, Any] = Field(default_factory=dict)
    per_evaluator_bootstrap: dict[str, dict[str, float | int]] = Field(default_factory=dict)
    results: list[dict[str, Any]] = Field(default_factory=list)
    cases: list[RunCaseDetail] = Field(default_factory=list)


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


def _receipt_benchmark_eligible(payload: dict[str, Any]) -> bool:
    values = (
        str(payload.get("workflow") or ""),
        str(payload.get("dataset") or ""),
    )
    return all(is_benchmark_eligible(value) for value in values if value)


def _unique_paths(paths: list[Path]) -> list[Path]:
    seen: set[Path] = set()
    unique: list[Path] = []
    for path in paths:
        resolved = path.expanduser()
        if resolved in seen:
            continue
        seen.add(resolved)
        unique.append(resolved)
    return unique


def _baseline_roots() -> list[Path]:
    raw = os.environ.get("JUNAS_BENCHMARK_RUNS_DIR")
    if raw:
        root = Path(raw)
        return _unique_paths([root if root.name == "baselines" else root / "baselines"])
    return _unique_paths([
        _repo_root() / "runs" / "baselines",
        _runs_dir() / "baselines",
    ])


def _baseline_run_id(root: Path, receipt: Path) -> str:
    try:
        relative = receipt.relative_to(root)
    except ValueError:
        return ""
    if len(relative.parts) < 3:
        return ""
    provider, task = relative.parts[0], relative.parts[1]
    return f"{provider}__{task}__{receipt.stem}"


def _iter_receipts() -> list[tuple[str, Path]]:
    receipts: list[tuple[str, Path]] = []
    seen: set[Path] = set()
    flat_root = _runs_dir()
    if flat_root.exists() and flat_root.name != "baselines":
        for receipt in sorted(flat_root.glob("*.json")):
            if receipt.name == "leaderboard.json" or receipt in seen:
                continue
            seen.add(receipt)
            receipts.append((receipt.stem, receipt))
    for root in _baseline_roots():
        if not root.exists():
            continue
        for receipt in sorted(root.rglob("*.json")):
            if receipt.name == "leaderboard.json" or receipt in seen:
                continue
            run_id = _baseline_run_id(root, receipt)
            if not run_id:
                continue
            seen.add(receipt)
            receipts.append((run_id, receipt))
    return receipts


def _find_receipt(run_id: str) -> tuple[str, Path] | None:
    for candidate_run_id, receipt in _iter_receipts():
        if candidate_run_id == run_id:
            return candidate_run_id, receipt
    return None


def _read_receipt(receipt: Path) -> dict[str, Any]:
    try:
        return json.loads(receipt.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"receipt is not valid JSON: {receipt}",
        ) from exc


def _dataset_candidates(raw: str) -> list[Path]:
    path = Path(raw)
    if path.is_absolute():
        return [path]
    backend_root = Path(__file__).resolve().parent.parent.parent
    return _unique_paths([backend_root / path, _repo_root() / path, path])


def _cases_by_name(payload: dict[str, Any]) -> dict[str, Any]:
    raw = str(payload.get("dataset") or "")
    if not raw:
        return {}
    for path in _dataset_candidates(raw):
        if path.exists():
            dataset = load_dataset(path)
            return {case.name: case for case in dataset.cases}
    return {}


def _result_actual(result: dict[str, Any]) -> Any:
    for key in ("output", "actual", "raw_output"):
        if key in result and result[key] not in (None, ""):
            return result[key]
    metadata = result.get("metadata") or {}
    if isinstance(metadata, dict):
        for key in ("output", "actual", "raw_output", "prediction"):
            if key in metadata and metadata[key] not in (None, ""):
                return metadata[key]
    return ""


def _case_details(payload: dict[str, Any]) -> list[RunCaseDetail]:
    results = [r for r in (payload.get("results") or []) if isinstance(r, dict)]
    by_case: dict[str, list[dict[str, Any]]] = {}
    for result in results:
        case_name = str(result.get("case_name") or "")
        if case_name:
            by_case.setdefault(case_name, []).append(result)
    cases = _cases_by_name(payload)
    case_names = list(cases)
    for case_name in by_case:
        if case_name not in cases:
            case_names.append(case_name)
    details: list[RunCaseDetail] = []
    for case_name in case_names:
        case = cases.get(case_name)
        per_case = by_case.get(case_name, [])
        scores: dict[str, CaseEvaluatorScore] = {}
        for result in per_case:
            evaluator = str(result.get("evaluator") or "")
            if not evaluator:
                continue
            scores[evaluator] = CaseEvaluatorScore(
                score=float(result.get("score") or 0.0),
                error=result.get("error"),
                metadata=dict(result.get("metadata") or {}),
            )
        actual = next((value for value in (_result_actual(r) for r in per_case) if value != ""), "")
        details.append(
            RunCaseDetail(
                case_name=case_name,
                input=dict(case.inputs) if case is not None else {},
                expected=case.expected_output if case is not None else None,
                actual=actual,
                evaluator_scores=scores,
            )
        )
    return details


def _run_detail(run_id: str, payload: dict[str, Any]) -> RunDetailResponse:
    results = [r for r in (payload.get("results") or []) if isinstance(r, dict)]
    evaluators = [str(e) for e in (payload.get("evaluators") or [])]
    if not evaluators:
        evaluators = sorted({str(r.get("evaluator")) for r in results if r.get("evaluator")})
    return RunDetailResponse(
        run_id=run_id,
        workflow=str(payload.get("workflow") or ""),
        dataset=str(payload.get("dataset") or ""),
        evaluators=evaluators,
        total_cases=int(payload.get("total_cases", 0) or 0),
        per_evaluator_mean={
            k: float(v) for k, v in (payload.get("per_evaluator_mean") or {}).items()
        },
        per_evaluator_bootstrap={
            str(evaluator): dict(stats)
            for evaluator, stats in (payload.get("per_evaluator_bootstrap") or {}).items()
            if isinstance(stats, dict)
        },
        started_at=str(payload.get("started_at") or ""),
        finished_at=str(payload.get("finished_at") or ""),
        strict=bool(payload.get("strict", False)),
        weak_evaluators_used=[str(e) for e in (payload.get("weak_evaluators_used") or [])],
        data_tier=str(payload.get("data_tier") or "regulator"),
        provenance=dict(payload.get("provenance") or {}),
        contamination_summary=dict(payload.get("contamination_summary") or {}),
        results=results,
        cases=_case_details(payload),
    )


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
        data_tier=summary.data_tier,
    )


@router.get("/leaderboard", response_model=LeaderboardResponse)
async def leaderboard() -> LeaderboardResponse:
    entries: list[LeaderboardEntry] = []
    for run_id, receipt in _iter_receipts():
        try:
            payload = json.loads(receipt.read_text(encoding="utf-8"))
        except json.JSONDecodeError:
            continue
        if not _receipt_benchmark_eligible(payload):
            continue
        entries.append(
            LeaderboardEntry(
                run_id=run_id,
                workflow=payload.get("workflow", ""),
                dataset=payload.get("dataset", ""),
                finished_at=payload.get("finished_at", ""),
                total_cases=int(payload.get("total_cases", 0) or 0),
                per_evaluator_mean={
                    k: float(v) for k, v in (payload.get("per_evaluator_mean") or {}).items()
                },
                strict=bool(payload.get("strict", False)),
                data_tier=str(payload.get("data_tier") or "regulator"),
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


@router.get("/runs/{run_id}", response_model=RunDetailResponse)
async def get_run(run_id: str) -> RunDetailResponse:
    found = _find_receipt(run_id)
    if found is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"run not found: {run_id}",
        )
    canonical_run_id, receipt = found
    return _run_detail(canonical_run_id, _read_receipt(receipt))
