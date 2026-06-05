"""Run Google Gemini LLM baselines for the D1 task set.

Writes one existing-shape benchmark receipt per task under
``runs/baselines/gemini``. The per-task receipt payload is exactly
``RunSummary.to_dict()``; provider-specific fields live in ``index.json``.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


BACKEND_ROOT = Path(__file__).resolve().parents[2]
REPO_ROOT = BACKEND_ROOT.parent
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from api.config import Settings  # noqa: E402
from api.services.llm_client import get_llm_client  # noqa: E402
from benchmark.llm_runner import register_llm_task  # noqa: E402
from benchmark.runner import load_dataset, run, write_summary  # noqa: E402


PROVIDER = "gemini"
DEFAULT_MODEL = "gemini-2.0-flash"
OUTPUT_ROOT = REPO_ROOT / "runs" / "baselines" / "gemini"
QUIRKS = (
    "Gemini is routed through get_llm_client(llm_provider='gemini'), which "
    "constructs api.services.chat_service.GeminiClient.",
    "This runner does not request Gemini JSON mode or response schemas; "
    "the task prompts ask for plain JSON text and evaluator parse failures "
    "remain visible in scores.",
)


@dataclass(frozen=True)
class BaselineTask:
    workflow: str
    dataset: Path
    evaluators: tuple[str, ...]
    max_tokens: int = 512


TASKS: tuple[BaselineTask, ...] = (
    BaselineTask(
        workflow="sglb_01",
        dataset=BACKEND_ROOT / "benchmark" / "datasets" / "sglb_01_pdpa.yaml",
        evaluators=("sglb_01_obligations_f1", "penalty_band_mae"),
    ),
    BaselineTask(
        workflow="sglb_02",
        dataset=BACKEND_ROOT / "benchmark" / "datasets" / "sglb_02_statute_qa.yaml",
        evaluators=("sglb_02_citation_match", "rouge_l_answer"),
    ),
    BaselineTask(
        workflow="sglb_04",
        dataset=BACKEND_ROOT / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml",
        evaluators=("multi_label_f1",),
    ),
)


def _read_dotenv_value(env_file: Path, key: str) -> str:
    if not env_file.exists():
        return ""
    prefix = f"{key}="
    export_prefix = f"export {key}="
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith(export_prefix):
            value = line[len(export_prefix) :].strip()
        elif line.startswith(prefix):
            value = line[len(prefix) :].strip()
        else:
            continue
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value.strip()
    return ""


def _settings(env_file: Path, explicit_model: str) -> Settings:
    kwargs: dict[str, Any] = {
        "_env_file": env_file if env_file.exists() else None,
        "llm_provider": PROVIDER,
    }
    if explicit_model:
        kwargs["gemini_model"] = explicit_model
    return Settings(**kwargs)


def _gemini_model(settings: Settings, env_file: Path, explicit_model: str) -> str:
    if explicit_model:
        return explicit_model

    env_model = os.getenv("GEMINI_MODEL", "").strip()
    if env_model:
        return env_model

    dotenv_model = _read_dotenv_value(env_file, "GEMINI_MODEL")
    if dotenv_model:
        return dotenv_model

    settings_model = str(settings.gemini_model or "").strip()
    return settings_model or DEFAULT_MODEL


def _registered_name(task: BaselineTask) -> str:
    return f"{task.workflow}_llm_{PROVIDER}"


def _receipt_name(task: BaselineTask) -> str:
    return f"{task.workflow}.json"


def _score_snapshot(receipt: dict[str, Any]) -> dict[str, float]:
    return {
        str(name): float(score)
        for name, score in receipt.get("per_evaluator_mean", {}).items()
    }


def _selected_tasks(names: list[str] | None) -> list[BaselineTask]:
    if not names:
        return list(TASKS)
    requested = set(names)
    return [task for task in TASKS if task.workflow in requested]


def _dry_run_payload(
    *,
    env_file: Path,
    output_dir: Path,
    model: str,
    tasks: list[BaselineTask],
    missing_reason: str,
    max_concurrency: int,
) -> dict[str, Any]:
    return {
        "dry_run": True,
        "provider": PROVIDER,
        "model": model,
        "env_file": str(env_file),
        "gemini_api_key": "missing in .env" if missing_reason else "present in .env",
        "output_dir": str(output_dir),
        "max_concurrency": max_concurrency,
        "would_run": not missing_reason,
        "stop_reason": missing_reason,
        "tasks": [
            {
                "workflow": task.workflow,
                "dataset": str(task.dataset),
                "evaluators": list(task.evaluators),
                "receipt": _receipt_name(task),
                "max_tokens": task.max_tokens,
            }
            for task in tasks
        ],
        "gemini_quirks": list(QUIRKS),
    }


async def _run_all(args: argparse.Namespace) -> list[dict[str, Any]]:
    env_file = Path(args.env_file).resolve()
    output_dir = Path(args.output_dir).resolve()
    tasks = _selected_tasks(args.task)
    explicit_model = args.model.strip()
    settings = _settings(env_file, explicit_model)

    dotenv_key = _read_dotenv_value(env_file, "GEMINI_API_KEY")
    if not dotenv_key:
        if not env_file.exists():
            raise RuntimeError(f"GEMINI_API_KEY is required in {env_file}; file does not exist")
        raise RuntimeError(f"GEMINI_API_KEY is required in {env_file}")

    model = _gemini_model(settings, env_file, explicit_model)
    settings = settings.model_copy(
        update={"gemini_api_key": dotenv_key, "gemini_model": model}
    )
    client = get_llm_client(settings)
    provider_label = f"{PROVIDER}:{model}"
    output_dir.mkdir(parents=True, exist_ok=True)

    receipts: list[dict[str, Any]] = []
    for task in tasks:
        dataset = load_dataset(task.dataset)
        sample_case = dataset.cases[0] if dataset.cases else None
        name = _registered_name(task)
        register_llm_task(
            name=name,
            workflow=task.workflow,
            client=client,
            provider_label=provider_label,
            max_tokens=task.max_tokens,
            sample_case=sample_case,
        )
        summary = await run(
            workflow=name,
            dataset_path=task.dataset,
            evaluators=list(task.evaluators),
            max_concurrency=args.max_concurrency,
            strict=True,
        )
        receipt_path = output_dir / _receipt_name(task)
        write_summary(summary, receipt_path)
        receipt = summary.to_dict()
        receipts.append(receipt)
        print(
            json.dumps(
                {
                    "workflow": task.workflow,
                    "receipt": str(receipt_path),
                    "total_cases": summary.total_cases,
                    "per_evaluator_mean": _score_snapshot(receipt),
                },
                sort_keys=True,
            )
        )

    index = {
        "provider": PROVIDER,
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "receipts": [_receipt_name(task) for task in tasks],
        "per_task_scores": {
            receipt["workflow"].replace(f"_llm_{PROVIDER}", ""): _score_snapshot(receipt)
            for receipt in receipts
        },
        "gemini_quirks": list(QUIRKS),
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return receipts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print the resolved plan and provider preflight without calling Gemini.",
    )
    parser.add_argument(
        "--env-file",
        default=str(REPO_ROOT / ".env"),
        help="Path to the .env file containing GEMINI_API_KEY/GEMINI_MODEL.",
    )
    parser.add_argument(
        "--model",
        default="",
        help=f"Override Gemini model. Defaults to GEMINI_MODEL or {DEFAULT_MODEL}.",
    )
    parser.add_argument(
        "--output-dir",
        default=str(OUTPUT_ROOT),
        help="Directory for JSON receipts.",
    )
    parser.add_argument(
        "--max-concurrency",
        type=int,
        default=3,
        help="Concurrent cases per task.",
    )
    parser.add_argument(
        "--task",
        action="append",
        choices=tuple(task.workflow for task in TASKS),
        help="Workflow to run; repeat for a subset. Defaults to all D1 target tasks.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    env_file = Path(args.env_file).resolve()
    output_dir = Path(args.output_dir).resolve()
    tasks = _selected_tasks(args.task)
    explicit_model = args.model.strip()
    settings = _settings(env_file, explicit_model)
    model = _gemini_model(settings, env_file, explicit_model)
    missing_reason = ""
    if not _read_dotenv_value(env_file, "GEMINI_API_KEY"):
        missing_reason = (
            f"GEMINI_API_KEY is required in {env_file}; file does not exist"
            if not env_file.exists()
            else f"GEMINI_API_KEY is required in {env_file}"
        )

    if args.dry_run:
        print(
            json.dumps(
                _dry_run_payload(
                    env_file=env_file,
                    output_dir=output_dir,
                    model=model,
                    tasks=tasks,
                    missing_reason=missing_reason,
                    max_concurrency=args.max_concurrency,
                ),
                indent=2,
                sort_keys=True,
            )
        )
        return 1 if missing_reason else 0

    if missing_reason:
        print(f"error: {missing_reason}", file=sys.stderr)
        return 1

    try:
        asyncio.run(_run_all(args))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
