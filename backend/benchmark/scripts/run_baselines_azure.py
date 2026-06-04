"""Run Azure OpenAI LLM baselines for shipped SG-LegalBench tasks."""
from __future__ import annotations

import argparse
import asyncio
import json
import math
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
from api.services.llm_client import AzureOpenAIClient  # noqa: E402
from benchmark.llm_runner import PROMPT_BUILDERS, register_llm_task  # noqa: E402
from benchmark.runner import load_dataset, run, write_summary  # noqa: E402
from benchmark.schema import Case  # noqa: E402


@dataclass(frozen=True)
class TaskSpec:
    label: str
    workflow: str
    dataset_path: Path
    evaluators: tuple[str, ...]
    max_tokens: int


@dataclass(frozen=True)
class Pricing:
    input_usd_per_1m: float
    output_usd_per_1m: float
    reasoning_usd_per_1m: float


@dataclass(frozen=True)
class CostEstimate:
    task: TaskSpec
    total_cases: int
    estimated_input_tokens: int
    estimated_visible_output_tokens: int
    token_model_estimate_usd: float
    per_case_floor_estimate_usd: float
    estimated_cost_usd: float
    budget_gate_usd: float


TASK_ORDER = ("sglb_04", "sglb_01", "sglb_02", "sglb_08")
TASK_SPECS: dict[str, TaskSpec] = {
    "sglb_04": TaskSpec(
        label="SGLB-04",
        workflow="sglb_04",
        dataset_path=BACKEND_ROOT / "benchmark/datasets/sglb_04_citation_verify.yaml",
        evaluators=("multi_label_f1",),
        max_tokens=64,
    ),
    "sglb_01": TaskSpec(
        label="SGLB-01",
        workflow="sglb_01",
        dataset_path=BACKEND_ROOT / "benchmark/datasets/sglb_01_pdpa.yaml",
        evaluators=("sglb_01_obligations_f1", "penalty_band_mae"),
        max_tokens=256,
    ),
    "sglb_02": TaskSpec(
        label="SGLB-02",
        workflow="sglb_02",
        dataset_path=BACKEND_ROOT / "benchmark/datasets/sglb_02_statute_qa.yaml",
        evaluators=("sglb_02_citation_match", "rouge_l_answer"),
        max_tokens=384,
    ),
    "sglb_08": TaskSpec(
        label="SGLB-08",
        workflow="sglb_08",
        dataset_path=BACKEND_ROOT / "benchmark/datasets/sglb_08_clause_tone_reviewed/dataset.yaml",
        evaluators=("multi_label_f1",),
        max_tokens=64,
    ),
}
PER_CASE_AZURE_ESTIMATE_USD = 0.015


class UsageTrackingAzureOpenAIClient(AzureOpenAIClient):
    """Azure client that records response usage without changing llm_runner."""

    def __init__(self, *, api_key: str, endpoint: str, api_version: str, deployment: str, workflow: str):
        super().__init__(
            api_key=api_key,
            endpoint=endpoint,
            api_version=api_version,
            deployment=deployment,
        )
        self.workflow = workflow
        self.usage_records: list[dict[str, Any]] = []
        self.outputs: list[dict[str, Any]] = []
        self.provider_errors: list[dict[str, Any]] = []
        self.legacy_fallbacks = 0
        self.progress_total = 0

    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        budget = max(int(max_tokens), self._REASONING_BUDGET_FLOOR)
        try:
            response = await self.client.chat.completions.create(
                model=self.deployment,
                messages=messages,
                max_completion_tokens=budget,
            )
        except Exception as exc:  # noqa: BLE001
            message = str(exc)
            if "max_completion_tokens" in message and "max_tokens" in message:
                self.legacy_fallbacks += 1
                try:
                    response = await self.client.chat.completions.create(
                        model=self.deployment,
                        messages=messages,
                        max_tokens=int(max_tokens),
                    )
                except Exception as retry_exc:  # noqa: BLE001
                    self._record_error(retry_exc)
                    raise
            else:
                self._record_error(exc)
                raise
        self._record_usage(getattr(response, "usage", None))
        choice = response.choices[0].message.content
        content = choice if isinstance(choice, str) else ""
        self.outputs.append(
            {
                "json_ok": _output_json_ok(self.workflow, content),
                "empty": content.strip() == "",
                "chars": len(content),
            }
        )
        self._print_progress()
        return content

    def _record_usage(self, usage: Any) -> None:
        if usage is None:
            return
        self.usage_records.append(_plain(usage))

    def _record_error(self, exc: Exception) -> None:
        status_code = getattr(exc, "status_code", None)
        response = getattr(exc, "response", None)
        if status_code is None and response is not None:
            status_code = getattr(response, "status_code", None)
        message = str(exc)
        kind = "rate_limit" if status_code == 429 or "rate limit" in message.lower() else exc.__class__.__name__
        self.provider_errors.append(
            {
                "kind": kind,
                "status_code": status_code,
                "message": message[:500],
            }
        )
        self._print_progress()

    def _print_progress(self) -> None:
        done = len(self.outputs) + len(self.provider_errors)
        if done == 0 or not self.progress_total:
            return
        if done == self.progress_total or done % 10 == 0:
            print(f"{self.workflow}: completed {done}/{self.progress_total}", flush=True)


def _plain(value: Any) -> Any:
    if value is None or isinstance(value, str | int | float | bool):
        return value
    if isinstance(value, list | tuple):
        return [_plain(item) for item in value]
    if isinstance(value, dict):
        return {str(k): _plain(v) for k, v in value.items()}
    if hasattr(value, "model_dump"):
        return _plain(value.model_dump())
    attrs = {
        key: getattr(value, key)
        for key in dir(value)
        if not key.startswith("_") and not callable(getattr(value, key))
    }
    return _plain(attrs)


def _output_json_ok(workflow: str, output: str) -> bool:
    text = (output or "").strip()
    if not text:
        return False
    try:
        parsed = json.loads(text)
    except json.JSONDecodeError:
        return False
    if workflow in {"sglb_04", "sglb_08"}:
        return isinstance(parsed, list)
    if workflow == "sglb_01":
        return isinstance(parsed, dict) and isinstance(parsed.get("obligations"), list) and isinstance(parsed.get("penalty_band"), str)
    if workflow == "sglb_02":
        return isinstance(parsed, dict) and isinstance(parsed.get("citation"), str) and isinstance(parsed.get("answer"), str)
    return True


def _settings() -> Settings:
    return Settings(_env_file=REPO_ROOT / ".env", llm_provider="azure")


def _azure_config(settings: Settings) -> dict[str, str]:
    config = {
        "api_key": settings.azure_openai_api_key.strip(),
        "endpoint": settings.azure_openai_endpoint.strip(),
        "api_version": settings.azure_openai_api_version.strip(),
        "deployment": settings.azure_openai_deployment.strip(),
    }
    missing = [
        name
        for name, value in (
            ("AZURE_OPENAI_API_KEY", config["api_key"]),
            ("AZURE_OPENAI_ENDPOINT", config["endpoint"]),
            ("AZURE_OPENAI_API_VERSION", config["api_version"]),
            ("AZURE_OPENAI_DEPLOYMENT", config["deployment"]),
        )
        if not value
    ]
    if missing:
        raise RuntimeError(f"azure baseline requires: {', '.join(missing)}")
    return config


def _pricing() -> Pricing:
    input_rate = float(os.environ.get("AZURE_BASELINE_INPUT_USD_PER_1M", "5.0"))
    output_rate = float(os.environ.get("AZURE_BASELINE_OUTPUT_USD_PER_1M", "15.0"))
    reasoning_rate = float(os.environ.get("AZURE_BASELINE_REASONING_USD_PER_1M", str(output_rate)))
    return Pricing(
        input_usd_per_1m=input_rate,
        output_usd_per_1m=output_rate,
        reasoning_usd_per_1m=reasoning_rate,
    )


def _normalise_task(raw: str) -> str:
    token = raw.strip().lower().replace("-", "_")
    aliases = {
        "all": "all",
        "04": "sglb_04",
        "1": "sglb_01",
        "01": "sglb_01",
        "2": "sglb_02",
        "02": "sglb_02",
        "8": "sglb_08",
        "08": "sglb_08",
    }
    if token in aliases:
        return aliases[token]
    if token.startswith("sglb_"):
        return token
    raise ValueError(f"unknown --task {raw!r}")


def _select_tasks(raw_task: str) -> list[TaskSpec]:
    requested = [_normalise_task(part) for part in raw_task.split(",") if part.strip()]
    if not requested:
        requested = ["all"]
    if "all" in requested:
        requested = list(TASK_ORDER)
    specs: list[TaskSpec] = []
    for workflow in requested:
        spec = TASK_SPECS.get(workflow)
        if spec is None:
            raise ValueError(f"unknown --task workflow {workflow!r}")
        if workflow == "sglb_08" and not _dataset_has_cases(spec.dataset_path):
            print("Skipping SGLB-08: no reviewed dataset cases found.")
            continue
        specs.append(spec)
    return specs


def _dataset_has_cases(path: Path) -> bool:
    if not path.exists():
        return False
    return bool(load_dataset(path).cases)


def _approx_tokens(text: str) -> int:
    return max(1, math.ceil(len(text) / 4))


def _estimate_task(spec: TaskSpec, pricing: Pricing) -> CostEstimate:
    dataset = load_dataset(spec.dataset_path)
    builder, _version = PROMPT_BUILDERS[spec.workflow]
    input_tokens = 0
    for case in dataset.cases:
        messages = builder(case)
        input_tokens += sum(_approx_tokens(message.get("content", "")) + 4 for message in messages)
    output_tokens = len(dataset.cases) * spec.max_tokens
    token_model_estimate = (
        (input_tokens * pricing.input_usd_per_1m)
        + (output_tokens * pricing.output_usd_per_1m)
    ) / 1_000_000
    floor_estimate = len(dataset.cases) * PER_CASE_AZURE_ESTIMATE_USD
    estimate = max(token_model_estimate, floor_estimate)
    return CostEstimate(
        task=spec,
        total_cases=len(dataset.cases),
        estimated_input_tokens=input_tokens,
        estimated_visible_output_tokens=output_tokens,
        token_model_estimate_usd=round(token_model_estimate, 6),
        per_case_floor_estimate_usd=round(floor_estimate, 6),
        estimated_cost_usd=round(estimate, 6),
        budget_gate_usd=round(estimate * 1.5, 6),
    )


def _print_estimates(estimates: list[CostEstimate], pricing: Pricing, deployment: str) -> None:
    total = sum(item.estimated_cost_usd for item in estimates)
    gate = total * 1.5
    print(f"Azure deployment: {deployment}")
    print(
        "Pricing used for usage invoice estimate: "
        f"input=${pricing.input_usd_per_1m}/1M, "
        f"output=${pricing.output_usd_per_1m}/1M, "
        f"reasoning=${pricing.reasoning_usd_per_1m}/1M"
    )
    if _is_reasoning_deployment(deployment):
        print("!!! COST WARNING: Azure gpt-5 reasoning-token cost is not modeled by the pre-run estimate.")
        print("!!! Actual spend may be 5-10x the estimate. Response usage is recorded after each run.")
    for item in estimates:
        print(
            f"{item.task.label}: cases={item.total_cases} "
            f"estimate=${item.estimated_cost_usd:.6f} "
            f"gate_1.5x=${item.budget_gate_usd:.6f} "
            f"input_tokens~{item.estimated_input_tokens} "
            f"visible_output_tokens_cap~{item.estimated_visible_output_tokens}"
        )
    print(f"Total estimate=${total:.6f}; 1.5x gate=${gate:.6f}")


def _is_reasoning_deployment(deployment: str) -> bool:
    lowered = deployment.lower()
    return "gpt-5" in lowered or lowered.startswith("o1") or lowered.startswith("o3") or lowered.startswith("o4")


def _enforce_cost_gate(estimates: list[CostEstimate], max_cost_usd: float | None) -> None:
    if max_cost_usd is None:
        return
    estimated = sum(item.estimated_cost_usd for item in estimates)
    gate = estimated * 1.5
    if gate > max_cost_usd:
        raise RuntimeError(
            f"refusing to run: 1.5x estimate ${gate:.6f} exceeds --max-cost-usd ${max_cost_usd:.6f}"
        )


def _usage_totals(records: list[dict[str, Any]]) -> dict[str, int]:
    totals = {
        "prompt_tokens": 0,
        "completion_tokens": 0,
        "total_tokens": 0,
        "reasoning_tokens": 0,
        "cached_prompt_tokens": 0,
        "responses_with_usage": 0,
    }
    for record in records:
        prompt_tokens = int(record.get("prompt_tokens") or record.get("input_tokens") or 0)
        completion_tokens = int(record.get("completion_tokens") or record.get("output_tokens") or 0)
        total_tokens = int(record.get("total_tokens") or (prompt_tokens + completion_tokens))
        completion_details = record.get("completion_tokens_details") or record.get("output_tokens_details") or {}
        prompt_details = record.get("prompt_tokens_details") or record.get("input_tokens_details") or {}
        totals["prompt_tokens"] += prompt_tokens
        totals["completion_tokens"] += completion_tokens
        totals["total_tokens"] += total_tokens
        totals["reasoning_tokens"] += int(completion_details.get("reasoning_tokens") or 0)
        totals["cached_prompt_tokens"] += int(prompt_details.get("cached_tokens") or 0)
        totals["responses_with_usage"] += 1
    return totals


def _usage_cost_usd(totals: dict[str, int], pricing: Pricing) -> float:
    reasoning_tokens = totals["reasoning_tokens"]
    visible_completion_tokens = max(0, totals["completion_tokens"] - reasoning_tokens)
    cost = (
        (totals["prompt_tokens"] * pricing.input_usd_per_1m)
        + (visible_completion_tokens * pricing.output_usd_per_1m)
        + (reasoning_tokens * pricing.reasoning_usd_per_1m)
    ) / 1_000_000
    return round(cost, 6)


def _failure_counts(client: UsageTrackingAzureOpenAIClient) -> dict[str, Any]:
    json_failures = sum(1 for item in client.outputs if not item["json_ok"])
    empty_outputs = sum(1 for item in client.outputs if item["empty"])
    rate_limits = sum(1 for item in client.provider_errors if item["kind"] == "rate_limit")
    return {
        "json_parse_or_contract_failures": json_failures,
        "empty_outputs": empty_outputs,
        "provider_errors": len(client.provider_errors),
        "rate_limit_errors": rate_limits,
        "legacy_max_tokens_fallbacks": client.legacy_fallbacks,
        "provider_error_samples": client.provider_errors[:5],
    }


def _receipt_path(spec: TaskSpec) -> Path:
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return REPO_ROOT / "runs/baselines/azure" / spec.workflow / f"{timestamp}.json"


async def _run_one(
    *,
    spec: TaskSpec,
    azure_config: dict[str, str],
    pricing: Pricing,
    estimate: CostEstimate,
    max_concurrency: int,
) -> Path:
    dataset = load_dataset(spec.dataset_path)
    sample_case: Case = dataset.cases[0]
    provider_label = f"azure:{azure_config['deployment']}"
    client = UsageTrackingAzureOpenAIClient(workflow=spec.workflow, **azure_config)
    client.progress_total = len(dataset.cases)
    registered_name = f"{spec.workflow}_llm_azure"
    register_llm_task(
        name=registered_name,
        workflow=spec.workflow,
        client=client,
        provider_label=provider_label,
        max_tokens=spec.max_tokens,
        sample_case=sample_case,
    )
    summary = await run(
        workflow=registered_name,
        dataset_path=spec.dataset_path,
        evaluators=list(spec.evaluators),
        max_concurrency=max_concurrency,
        strict=True,
    )
    usage_totals = _usage_totals(client.usage_records)
    usage_cost = _usage_cost_usd(usage_totals, pricing)
    summary.provenance.update(
        {
            "azure_api_version": azure_config["api_version"],
            "estimated_cost_usd_pre_run": estimate.estimated_cost_usd,
            "estimated_cost_gate_usd_1_5x": estimate.budget_gate_usd,
            "usage_invoice_usd": usage_cost,
            "usage_invoice_note": "Estimated from response usage tokens and script pricing rates; Azure bills may differ by region, SKU, and contract.",
            "usage_totals": usage_totals,
            "usage_pricing_usd_per_1m": {
                "input": pricing.input_usd_per_1m,
                "output": pricing.output_usd_per_1m,
                "reasoning": pricing.reasoning_usd_per_1m,
            },
            "failures": _failure_counts(client),
        }
    )
    output_path = _receipt_path(spec)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    write_summary(summary, output_path)
    print(
        json.dumps(
            {
                "task": spec.label,
                "receipt": str(output_path),
                "per_evaluator_mean": summary.per_evaluator_mean(),
                "usage_invoice_usd": usage_cost,
                "usage_totals": usage_totals,
                "failures": summary.provenance["failures"],
            },
            indent=2,
            sort_keys=True,
        )
    )
    return output_path


def _build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run Azure OpenAI SG-LegalBench baselines")
    parser.add_argument(
        "--task",
        default="all",
        help="Task to run: all, SGLB-04, SGLB-01, SGLB-02, SGLB-08, or a comma list.",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print estimates without API calls")
    parser.add_argument("--max-cost-usd", type=float, default=None, help="Abort if 1.5x estimate exceeds this budget")
    parser.add_argument("--max-concurrency", type=int, default=1, help="Harness/provider concurrency")
    return parser


async def _amain(args: argparse.Namespace) -> int:
    settings = _settings()
    azure_config = _azure_config(settings)
    pricing = _pricing()
    specs = _select_tasks(args.task)
    estimates = [_estimate_task(spec, pricing) for spec in specs]
    _print_estimates(estimates, pricing, azure_config["deployment"])
    _enforce_cost_gate(estimates, args.max_cost_usd)
    if args.dry_run:
        return 0
    receipts: list[Path] = []
    estimate_by_workflow = {item.task.workflow: item for item in estimates}
    for spec in specs:
        print(f"Running {spec.label} via Azure OpenAI...")
        receipts.append(
            await _run_one(
                spec=spec,
                azure_config=azure_config,
                pricing=pricing,
                estimate=estimate_by_workflow[spec.workflow],
                max_concurrency=args.max_concurrency,
            )
        )
    print(json.dumps({"receipts": [str(path) for path in receipts]}, indent=2))
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)
    try:
        return asyncio.run(_amain(args))
    except (RuntimeError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
