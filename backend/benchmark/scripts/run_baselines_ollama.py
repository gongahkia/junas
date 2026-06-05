"""Run SG-LegalBench baselines against local Ollama models.

This script intentionally never pulls models. It shells out to
``ollama list`` first, selects an already-pulled target, then runs the
publication harness with strict evaluators.
"""
from __future__ import annotations

import argparse
import asyncio
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

import benchmark.tasks  # noqa: F401  registration side effects
from benchmark.llm_runner import register_llm_task
from benchmark.registry import get_provenance, register_provenance
from benchmark.runner import load_dataset, run, write_summary

REPO_ROOT = Path(__file__).resolve().parents[3]
BACKEND_ROOT = REPO_ROOT / "backend"
RUNS_ROOT = REPO_ROOT / "runs" / "baselines" / "ollama"
OLLAMA_URL = "http://127.0.0.1:11434"


@dataclass(frozen=True)
class TaskConfig:
    workflow: str
    dataset: Path
    evaluators: tuple[str, ...]
    max_tokens: int


TASKS: dict[str, TaskConfig] = {
    "sglb_04": TaskConfig(
        workflow="sglb_04",
        dataset=BACKEND_ROOT / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml",
        evaluators=("multi_label_f1",),
        max_tokens=64,
    ),
    "sglb_01": TaskConfig(
        workflow="sglb_01",
        dataset=BACKEND_ROOT / "benchmark" / "datasets" / "sglb_01_pdpa.yaml",
        evaluators=("sglb_01_obligations_f1", "penalty_band_mae"),
        max_tokens=128,
    ),
    "sglb_02": TaskConfig(
        workflow="sglb_02",
        dataset=BACKEND_ROOT / "benchmark" / "datasets" / "sglb_02_statute_qa.yaml",
        evaluators=("sglb_02_citation_match", "rouge_l_answer"),
        max_tokens=512,
    ),
}
DEFAULT_ORDER = ("sglb_04", "sglb_01", "sglb_02")
DATASET_VERSION_BY_NAME = {
    "sglb_01_pdpa.yaml": "sglb-01-v0.1",
    "sglb_02_statute_qa.yaml": "sglb-02-v0.1",
    "sglb_04_citation_verify.yaml": "sglb-04-v0.1",
}
TARGET_PATTERNS = (
    re.compile(r"llama3(?:\.\d+)?(?::|-)?8b", re.IGNORECASE),
    re.compile(r"qwen3(?::|-)?4b", re.IGNORECASE),
    re.compile(r"qwen.*(?:4b|7b)", re.IGNORECASE),
    re.compile(r"llama.*(?:7b|8b)", re.IGNORECASE),
)


@dataclass(frozen=True)
class OllamaModel:
    name: str
    model_id: str
    size: str
    modified: str


class OllamaClient:
    def __init__(self, *, model: str, base_url: str, temperature: float, seed: int) -> None:
        self.model = model
        self.base_url = base_url.rstrip("/")
        self.temperature = temperature
        self.seed = seed

    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "seed": self.seed,
                "num_predict": max_tokens,
            },
        }
        async with httpx.AsyncClient(timeout=httpx.Timeout(180.0)) as client:
            response = await client.post(f"{self.base_url}/api/chat", json=payload)
            response.raise_for_status()
        data = response.json()
        message = data.get("message") or {}
        return str(message.get("content") or "")


def _slug(value: str) -> str:
    slug = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return slug or "model"


def _git_sha() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
            text=True,
        )
    except (OSError, subprocess.CalledProcessError):
        return ""
    return completed.stdout.strip()


def _dataset_version(dataset: Path) -> str:
    cases = load_dataset(dataset).cases
    versions = {
        str(case.metadata.get("dataset_version"))
        for case in cases
        if case.metadata.get("dataset_version")
    }
    if len(versions) == 1:
        return next(iter(versions))
    if not versions:
        return DATASET_VERSION_BY_NAME.get(dataset.name, "")
    return "mixed"


def list_local_models() -> list[OllamaModel]:
    completed = subprocess.run(
        ["ollama", "list"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    if completed.returncode != 0:
        raise SystemExit(
            "ollama list failed. Start the local Ollama server with "
            "`ollama serve` before running baselines.\n"
            f"{completed.stderr.strip()}"
        )
    models: list[OllamaModel] = []
    for line in completed.stdout.splitlines()[1:]:
        if not line.strip():
            continue
        parts = re.split(r"\s{2,}", line.strip(), maxsplit=3)
        if len(parts) < 4:
            continue
        name, model_id, size, modified = parts
        models.append(
            OllamaModel(name=name, model_id=model_id, size=size, modified=modified)
        )
    return models


def choose_model(models: list[OllamaModel], requested: str | None) -> OllamaModel:
    if requested:
        for model in models:
            if model.name == requested:
                return model
        names = ", ".join(model.name for model in models) or "(none)"
        raise SystemExit(f"requested model {requested!r} is not pulled. Local models: {names}")
    for pattern in TARGET_PATTERNS:
        for model in models:
            if pattern.search(model.name):
                return model
    if models:
        return models[0]
    raise SystemExit("no local Ollama models found; refusing to pull a model")


def model_display_name(model_name: str) -> str:
    lowered = model_name.lower()
    if "llama3" in lowered and "8b" in lowered:
        return "Llama 3 8B"
    if "qwen3" in lowered and "4b" in lowered:
        return "Qwen 3 4B"
    if "qwen2.5vl" in lowered:
        return "Qwen 2.5 VL 7B"
    if "llama2" in lowered and "7b" in lowered:
        return "Llama 2 7B"
    return model_name


def selected_tasks(task_args: list[str]) -> list[TaskConfig]:
    if not task_args or "all" in task_args:
        return [TASKS[name] for name in DEFAULT_ORDER]
    return [TASKS[name] for name in task_args]


def receipt_path(config: TaskConfig, model_name: str, timestamp: str) -> Path:
    filename = f"{timestamp}-{_slug(model_name)}.json"
    return RUNS_ROOT / config.workflow / filename


async def run_task(
    *,
    config: TaskConfig,
    model: OllamaModel,
    args: argparse.Namespace,
    timestamp: str,
) -> Path:
    dataset = load_dataset(config.dataset)
    sample = dataset.cases[0] if dataset.cases else None
    provider_label = f"ollama:{model.name}"
    workflow_name = f"{config.workflow}_ollama_{_slug(model.name)}_{timestamp}"
    register_llm_task(
        name=workflow_name,
        workflow=config.workflow,
        client=OllamaClient(
            model=model.name,
            base_url=args.base_url,
            temperature=args.temperature,
            seed=args.seed,
        ),
        provider_label=provider_label,
        max_tokens=config.max_tokens,
        sample_case=sample,
    )
    provenance = get_provenance(workflow_name)
    provenance.update(
        {
            "model": model.name,
            "model_id": model.model_id,
            "model_display_name": model_display_name(model.name),
            "model_size": model.size,
            "model_modified": model.modified,
            "temperature": args.temperature,
            "seed": args.seed,
            "scorer_git_sha": _git_sha(),
            "dataset_version": _dataset_version(config.dataset),
        }
    )
    register_provenance(workflow_name, provenance)
    summary = await run(
        workflow=workflow_name,
        dataset_path=config.dataset,
        evaluators=list(config.evaluators),
        max_concurrency=args.max_concurrency,
        strict=True,
    )
    output = receipt_path(config, model.name, timestamp)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.exists() and not args.force:
        raise SystemExit(f"receipt already exists: {output}; pass --force to overwrite")
    write_summary(summary, output)
    return output


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run local Ollama SG-LegalBench baselines")
    parser.add_argument(
        "--task",
        action="append",
        choices=("all", *TASKS.keys()),
        default=[],
        help="task to run; repeatable; default all regulator leaderboard tasks",
    )
    parser.add_argument("--model", default="", help="exact Ollama model name; must already be pulled")
    parser.add_argument("--base-url", default=OLLAMA_URL)
    parser.add_argument("--max-concurrency", type=int, default=1)
    parser.add_argument("--temperature", type=float, default=0.0)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true")
    return parser


async def amain(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    models = list_local_models()
    model = choose_model(models, args.model or None)
    tasks = selected_tasks(args.task)
    print("Local Ollama models:")
    for item in models:
        marker = "*" if item.name == model.name else " "
        print(f" {marker} {item.name} ({item.model_id}, {item.size}, modified {item.modified})")
    print(f"Selected open-weight baseline: {model_display_name(model.name)} [{model.name}]")
    print("Tasks:")
    for task in tasks:
        cases = len(load_dataset(task.dataset).cases)
        print(f" - {task.workflow}: {cases} cases, evaluators={','.join(task.evaluators)}")
    if args.dry_run:
        return 0
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    for task in tasks:
        output = await run_task(config=task, model=model, args=args, timestamp=timestamp)
        print(f"wrote {output.relative_to(REPO_ROOT)}")
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(amain(argv))


if __name__ == "__main__":
    raise SystemExit(main())
