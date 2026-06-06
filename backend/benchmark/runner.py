"""Async runner: load dataset → invoke task → score with evaluators."""
from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import yaml

from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength
from benchmark.registry import TASKS, get_provenance
from benchmark.schema import Case, Dataset, EvalCaseResult
from benchmark.stats import bootstrap_ci
from benchmark.contamination import (
    attach_probe_metadata,
    contamination_summary,
    run_probe,
)

logger = logging.getLogger(__name__)

BOOTSTRAP_N = 1000
BOOTSTRAP_SEED_BASE = 1009


@dataclass
class RunSummary:
    workflow: str
    dataset: str
    evaluators: list[str]
    total_cases: int
    results: list[EvalCaseResult] = field(default_factory=list)
    started_at: str = ""
    finished_at: str = ""
    strict: bool = False
    weak_evaluators_used: list[str] = field(default_factory=list)
    data_tier: str = "regulator"
    # Publication-grade provenance (coverage-matrix §4.4). Empty when the
    # runner is an oracle or no LLM provenance was registered.
    provenance: dict[str, Any] = field(default_factory=dict)
    contamination_summary: dict[str, Any] = field(default_factory=dict)

    def per_evaluator_mean(self) -> dict[str, float]:
        sums: dict[str, float] = {}
        counts: dict[str, int] = {}
        for r in self.results:
            if r.error:
                continue
            sums[r.evaluator] = sums.get(r.evaluator, 0.0) + r.score
            counts[r.evaluator] = counts.get(r.evaluator, 0) + 1
        return {k: sums[k] / counts[k] for k in sums if counts[k] > 0}

    def _bootstrap_seed(self, evaluator: str) -> int:
        digest = hashlib.sha256(evaluator.encode("utf-8")).hexdigest()[:8]
        return BOOTSTRAP_SEED_BASE + int(digest, 16)

    def per_evaluator_bootstrap(self) -> dict[str, dict[str, float | int]]:
        values_by_evaluator: dict[str, list[float]] = {name: [] for name in self.evaluators}
        for r in self.results:
            if r.error:
                continue
            values_by_evaluator.setdefault(r.evaluator, []).append(r.score)
        stats: dict[str, dict[str, float | int]] = {}
        for evaluator, values in values_by_evaluator.items():
            seed = self._bootstrap_seed(evaluator)
            ci = bootstrap_ci(values, seed=seed, n=BOOTSTRAP_N)
            stats[evaluator] = {
                "mean": ci.mean,
                "ci_low": ci.ci_low,
                "ci_high": ci.ci_high,
                "n_bootstrap": ci.n_bootstrap,
                "seed": seed,
            }
        return stats

    def to_dict(self) -> dict[str, Any]:
        return {
            "workflow": self.workflow,
            "dataset": self.dataset,
            "evaluators": self.evaluators,
            "total_cases": self.total_cases,
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "strict": self.strict,
            "weak_evaluators_used": self.weak_evaluators_used,
            "data_tier": self.data_tier,
            "provenance": dict(self.provenance),
            "contamination_summary": dict(self.contamination_summary),
            "per_evaluator_mean": self.per_evaluator_mean(),
            "per_evaluator_bootstrap": self.per_evaluator_bootstrap(),
            "results": [r.model_dump() for r in self.results],
        }


def load_dataset(path: str | Path) -> Dataset:
    raw = Path(path).read_text(encoding="utf-8")
    data = yaml.safe_load(raw)
    return Dataset.model_validate(data)


def _infer_data_tier(dataset: Dataset) -> str:
    tiers = {
        str(case.metadata.get("data_tier"))
        for case in dataset.cases
        if case.metadata.get("data_tier")
    }
    if not tiers:
        return "regulator"
    if len(tiers) == 1:
        return next(iter(tiers))
    return "mixed"


async def _run_case(
    workflow: str,
    case: Case,
    evaluators: list[str],
) -> list[EvalCaseResult]:
    task_runner = TASKS.get(workflow)
    if task_runner is None:
        return [
            EvalCaseResult(
                case_name=case.name,
                evaluator=ev,
                score=0.0,
                error=f"unknown workflow {workflow!r}",
            )
            for ev in evaluators
        ]

    try:
        output = await task_runner(case)
    except Exception as exc:  # noqa: BLE001
        return [
            EvalCaseResult(
                case_name=case.name,
                evaluator=ev,
                score=0.0,
                error=f"task failed: {exc}",
            )
            for ev in evaluators
        ]

    results: list[EvalCaseResult] = []
    for ev_name in evaluators:
        evaluator = EVALUATORS.get(ev_name)
        if evaluator is None:
            results.append(
                EvalCaseResult(
                    case_name=case.name,
                    evaluator=ev_name,
                    score=0.0,
                    output=output,
                    error=f"unknown evaluator {ev_name!r}",
                )
            )
            continue
        try:
            outcome = await evaluator.evaluate(
                EvaluatorContext(
                    case_name=case.name,
                    inputs=case.inputs,
                    expected_output=case.expected_output,
                    metadata=case.metadata,
                    output=output,
                )
            )
            results.append(
                EvalCaseResult(
                    case_name=case.name,
                    evaluator=ev_name,
                    score=outcome.score,
                    output=output,
                    metadata=outcome.detail,
                )
            )
        except Exception as exc:  # noqa: BLE001
            results.append(
                EvalCaseResult(
                    case_name=case.name,
                    evaluator=ev_name,
                    score=0.0,
                    output=output,
                    error=f"evaluator failed: {exc}",
                )
            )

    return results


async def run(
    workflow: str,
    dataset_path: str | Path,
    evaluators: list[str],
    max_concurrency: int = 5,
    strict: bool = False,
    contamination_probe: bool = False,
) -> RunSummary:
    """Run ``workflow`` against the dataset, scoring with the named evaluators.

    Args:
        workflow: registered task name (see ``benchmark.registry.TASKS``).
        dataset_path: path to a YAML dataset file.
        evaluators: list of registered evaluator names.
        max_concurrency: maximum concurrent case executions.
        strict: when True, weak-tier evaluators are rejected; coverage
            matrix §4.2 forbids them in publication runs.
        contamination_probe: when True, run a separate per-case recall
            probe and attach memorisation metadata to the receipt.

    Raises:
        ValueError: when ``strict`` is True and any requested evaluator is
            weak-tier.
    """
    weak_used = [
        name
        for name in evaluators
        if name in EVALUATORS and EVALUATORS[name].strength == EvaluatorStrength.WEAK
    ]
    if strict and weak_used:
        raise ValueError(
            f"--strict mode rejects weak evaluators: {weak_used}. "
            "See docs/coverage-matrix.md §4.2."
        )

    dataset = load_dataset(dataset_path)
    # Prefer per-runner provenance (set via register_task(..., provenance=...));
    # fall back to a runner.provenance attribute attached by llm_task_for.
    provenance = get_provenance(workflow)
    if not provenance:
        runner_obj = TASKS.get(workflow)
        provenance = dict(getattr(runner_obj, "provenance", {}))
    summary = RunSummary(
        workflow=workflow,
        dataset=str(dataset_path),
        evaluators=list(evaluators),
        total_cases=len(dataset.cases),
        started_at=datetime.now(timezone.utc).isoformat(),
        strict=strict,
        weak_evaluators_used=weak_used,
        data_tier=_infer_data_tier(dataset),
        provenance=provenance,
    )

    semaphore = asyncio.Semaphore(max_concurrency)

    async def _bounded(case: Case) -> list[EvalCaseResult]:
        async with semaphore:
            return await _run_case(workflow, case, evaluators)

    all_results = await asyncio.gather(*[_bounded(c) for c in dataset.cases])
    for per_case in all_results:
        summary.results.extend(per_case)

    if contamination_probe:
        probe_results, method = await run_probe(
            workflow,
            dataset.cases,
            max_concurrency=max_concurrency,
        )
        attach_probe_metadata(summary.results, probe_results)
        summary.contamination_summary = contamination_summary(
            workflow,
            evaluators,
            summary.results,
            probe_results,
            method=method,
        )

    summary.finished_at = datetime.now(timezone.utc).isoformat()
    return summary


def write_summary(summary: RunSummary, output_path: str | Path) -> None:
    Path(output_path).write_text(
        json.dumps(summary.to_dict(), indent=2, sort_keys=True),
        encoding="utf-8",
    )
