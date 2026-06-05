"""Run Anthropic LLM baselines for the D1 task set.

Writes one existing-shape benchmark receipt per task under
``runs/baselines/anthropic``. The receipt payload is exactly
``RunSummary.to_dict()``; do not add provider-specific fields here.
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
from api.services.llm_client import AnthropicClient  # noqa: E402
from benchmark.llm_runner import register_llm_task  # noqa: E402
from benchmark.runner import load_dataset, run, write_summary  # noqa: E402


CONFIG_DEFAULT_MODEL = "claude-sonnet-4-20250514"
DEFAULT_MODEL = "claude-sonnet-4-6"
OUTPUT_ROOT = REPO_ROOT / "runs" / "baselines" / "anthropic"


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
    for raw_line in env_file.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or not line.startswith(prefix):
            continue
        value = line[len(prefix) :].strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        return value.strip()
    return ""


def _settings(env_file: Path) -> Settings:
    return Settings(_env_file=env_file if env_file.exists() else None, llm_provider="anthropic")


def _anthropic_model(settings: Settings, env_file: Path, explicit_model: str) -> str:
    if explicit_model:
        return explicit_model

    env_model = os.getenv("ANTHROPIC_MODEL", "").strip()
    if env_model:
        return env_model

    dotenv_model = _read_dotenv_value(env_file, "ANTHROPIC_MODEL")
    if dotenv_model:
        return dotenv_model

    settings_model = str(settings.anthropic_model or "").strip()
    if settings_model and settings_model != CONFIG_DEFAULT_MODEL:
        return settings_model

    # Settings currently defaults to the 2025 Sonnet 4 ID; D2 baselines
    # should use the current Sonnet default unless the user overrides it.
    return DEFAULT_MODEL


def _registered_name(task: BaselineTask) -> str:
    return f"{task.workflow}_llm_anthropic"


def _receipt_name(task: BaselineTask) -> str:
    return f"{task.workflow}.json"


def _score_snapshot(receipt: dict[str, Any]) -> dict[str, float]:
    return {
        str(name): float(score)
        for name, score in receipt.get("per_evaluator_mean", {}).items()
    }


async def _run_all(args: argparse.Namespace) -> list[dict[str, Any]]:
    env_file = Path(args.env_file).resolve()
    settings = _settings(env_file)
    api_key = str(settings.anthropic_api_key or "").strip()
    if not api_key:
        raise RuntimeError(
            f"ANTHROPIC_API_KEY is required in {env_file} or the process environment"
        )

    model = _anthropic_model(settings, env_file, args.model.strip())
    client = AnthropicClient(api_key=api_key, model=model)
    provider_label = f"anthropic:{model}"
    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    receipts: list[dict[str, Any]] = []
    for task in TASKS:
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
        "provider": "anthropic",
        "model": model,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "receipts": [_receipt_name(task) for task in TASKS],
        "per_task_scores": {
            receipt["workflow"].replace("_llm_anthropic", ""): _score_snapshot(receipt)
            for receipt in receipts
        },
    }
    (output_dir / "index.json").write_text(
        json.dumps(index, indent=2, sort_keys=True),
        encoding="utf-8",
    )
    return receipts


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--env-file",
        default=str(REPO_ROOT / ".env"),
        help="Path to the .env file containing ANTHROPIC_API_KEY/ANTHROPIC_MODEL.",
    )
    parser.add_argument(
        "--model",
        default="",
        help=f"Override Anthropic model. Defaults to ANTHROPIC_MODEL or {DEFAULT_MODEL}.",
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
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        asyncio.run(_run_all(args))
    except Exception as exc:  # noqa: BLE001
        print(f"error: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
