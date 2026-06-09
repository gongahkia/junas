"""MCP wrapper for local SG-LegalBench runs."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Literal

import benchmark.tasks  # noqa: F401  registration side-effects
from benchmark.evaluators import EVALUATORS
from benchmark.registry import TASKS
from benchmark.runner import run

ModelName = Literal["azure", "anthropic", "gemini", "ollama"]
ALLOWED_MODELS = {"azure", "anthropic", "gemini", "ollama"}
BACKEND_ROOT = Path(__file__).resolve().parents[2]


@dataclass(frozen=True)
class BenchmarkDefault:
    dataset: str
    evaluators: tuple[str, ...]


DEFAULTS: dict[str, BenchmarkDefault] = {
    "sglb_01": BenchmarkDefault(
        "benchmark/datasets/sglb_01_pdpa.yaml",
        ("sglb_01_obligations_f1", "penalty_band_mae"),
    ),
    "sglb_02": BenchmarkDefault(
        "benchmark/datasets/sglb_02_statute_qa.yaml",
        ("sglb_02_citation_match", "rouge_l_answer"),
    ),
    "sglb_04": BenchmarkDefault(
        "benchmark/datasets/sglb_04_citation_verify.yaml",
        ("multi_label_f1",),
    ),
    "sglb_06": BenchmarkDefault(
        "benchmark/datasets/sglb_06_roc_2021.yaml",
        ("order_rule_label_f1", "order_rule_top3"),
    ),
    "sglb_11": BenchmarkDefault(
        "benchmark/datasets/sglb_11_hallucination_smoke.yaml",
        ("citation_hallucination_f1",),
    ),
    "sglb_13": BenchmarkDefault(
        "benchmark/datasets/sglb_13_counterfactual.yaml",
        ("sglb_13_outcome_accuracy",),
    ),
    "sglb_16": BenchmarkDefault(
        "benchmark/datasets/sglb_16_review_redflag.yaml",
        ("sglb_16_redflag_f1",),
    ),
}


async def run_benchmark(task: str, model: ModelName) -> dict:
    """Run a registered local benchmark task.

    The ``model`` argument is validated for MCP compatibility but does not
    trigger provider API calls. This wrapper uses the repo's oracle/local
    harness so it remains free and deterministic.
    """
    task_name = str(task or "").strip()
    model_name = str(model or "").strip().lower()
    if task_name not in TASKS:
        return {"error": f"unknown task {task_name!r}", "known_tasks": sorted(TASKS)}
    if model_name not in ALLOWED_MODELS:
        return {"error": f"unknown model {model_name!r}", "allowed_models": sorted(ALLOWED_MODELS)}

    default = DEFAULTS.get(task_name)
    if default is None:
        return {
            "error": f"no default dataset/evaluator catalog for {task_name!r}",
            "known_defaults": sorted(DEFAULTS),
        }
    unknown_evaluators = [name for name in default.evaluators if name not in EVALUATORS]
    if unknown_evaluators:
        return {"error": f"default evaluators are not registered: {unknown_evaluators}"}

    dataset_path = BACKEND_ROOT / default.dataset
    if not dataset_path.exists():
        return {"error": f"default dataset is missing: {default.dataset}"}

    try:
        summary = await run(
            workflow=task_name,
            dataset_path=dataset_path,
            evaluators=list(default.evaluators),
            strict=True,
        )
    except Exception as exc:  # noqa: BLE001 - MCP tools surface errors as data.
        return {"error": str(exc), "task": task_name, "model": model_name}

    return {
        "task": task_name,
        "model": model_name,
        "external_llm_calls": False,
        "dataset": default.dataset,
        "evaluators": list(default.evaluators),
        "total_cases": summary.total_cases,
        "data_tier": summary.data_tier,
        "per_evaluator_mean": summary.per_evaluator_mean(),
        "per_evaluator_bootstrap": summary.per_evaluator_bootstrap(),
    }
