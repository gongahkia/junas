"""Synthetic candidate generation with provider rotation."""
from __future__ import annotations

import json
import os
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Protocol

import yaml

from api.services.llm_client import get_llm_client
from benchmark.synthetic.planner import parse_providers
from benchmark.synthetic.planner import PlanItem
from benchmark.synthetic.prompts import render_prompt
from benchmark.synthetic.quality import check_case_quality
from benchmark.synthetic.taxonomy import GENERATOR_VERSION, PROMPT_VERSION


class LLMLike(Protocol):
    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        ...


@dataclass
class MockLLM:
    provider: str = "mock"
    calls: int = 0

    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        del messages, max_tokens
        self.calls += 1
        return (
            f"Mock synthetic body generated for {self.provider}. "
            "This fictional Singapore legal scenario concerns Acme Pte Ltd and Beacon Pte Ltd. "
            "The parties exchange operational facts, contract terms, dates, and compliance context in neutral prose. "
            "The example is intentionally plain so tests can exercise the pipeline without external providers."
        )


class SyntheticGenerator:
    def __init__(self, clients: dict[str, LLMLike] | None = None) -> None:
        self.clients = clients or {}
        self.call_counts: dict[str, int] = {}

    def _client_for(self, provider: str) -> LLMLike:
        if provider in self.clients:
            return self.clients[provider]
        if provider == "mock":
            client = MockLLM(provider="mock")
            self.clients[provider] = client
            return client

        settings = _settings_for_provider(provider)
        client = get_llm_client(settings)
        self.clients[provider] = client
        return client

    async def generate_body(self, item: PlanItem) -> str:
        rendered = render_prompt(item.cell)
        client = self._client_for(item.provider)
        self.call_counts[item.provider] = self.call_counts.get(item.provider, 0) + 1
        return await client.generate(rendered.messages, max_tokens=rendered.max_tokens)


def load_env_file(path: Path) -> int:
    if not path.exists():
        return 0
    loaded = 0
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if line.startswith("export "):
            line = line.removeprefix("export ").strip()
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or not (key[0].isalpha() or key[0] == "_"):
            continue
        if not all(char.isalnum() or char == "_" for char in key):
            continue
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {"'", '"'}:
            value = value[1:-1]
        if key not in os.environ:
            os.environ[key] = value
            loaded += 1
    return loaded


def preflight_providers(providers: str | tuple[str, ...] | list[str]) -> dict[str, Any]:
    provider_list = parse_providers(providers)
    missing: list[str] = []
    configured: dict[str, str] = {}
    for provider in provider_list:
        if provider == "mock":
            configured[provider] = "mock-synthetic-v1"
            continue
        settings = _settings_for_provider(provider)
        if provider == "openai":
            if not getattr(settings, "openai_api_key", ""):
                missing.append("OPENAI_API_KEY")
            configured[provider] = getattr(settings, "openai_model", "")
        elif provider == "azure":
            for env_name, attr in (
                ("AZURE_OPENAI_API_KEY", "azure_openai_api_key"),
                ("AZURE_OPENAI_ENDPOINT", "azure_openai_endpoint"),
                ("AZURE_OPENAI_API_VERSION", "azure_openai_api_version"),
                ("AZURE_OPENAI_DEPLOYMENT", "azure_openai_deployment"),
            ):
                if not getattr(settings, attr, ""):
                    missing.append(env_name)
            configured[provider] = getattr(settings, "azure_openai_deployment", "")
        elif provider == "anthropic":
            if not getattr(settings, "anthropic_api_key", ""):
                missing.append("ANTHROPIC_API_KEY")
            configured[provider] = getattr(settings, "anthropic_model", "")
        elif provider in {"google", "gemini"}:
            if not getattr(settings, "gemini_api_key", ""):
                missing.append("GEMINI_API_KEY")
            configured[provider] = getattr(settings, "gemini_model", "")
    blank_models = [provider for provider, model in configured.items() if not str(model).strip()]
    if blank_models:
        missing.extend(f"{provider.upper()} model name" for provider in blank_models)
    return {
        "ok": not missing,
        "providers": list(provider_list),
        "configured_models": configured,
        "missing": sorted(set(missing)),
    }


def _settings_for_provider(provider: str) -> SimpleNamespace:
    if provider == "google":
        provider = "gemini"
    if provider == "openai":
        return SimpleNamespace(
            llm_provider="openai",
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("JUNAS_SYNTH_OPENAI_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")),
        )
    if provider == "azure":
        return SimpleNamespace(
            llm_provider="azure",
            azure_openai_api_key=os.environ.get("AZURE_OPENAI_API_KEY", ""),
            azure_openai_endpoint=os.environ.get("AZURE_OPENAI_ENDPOINT", ""),
            azure_openai_api_version=os.environ.get(
                "AZURE_OPENAI_API_VERSION", "2024-08-01-preview"
            ),
            azure_openai_deployment=os.environ.get(
                "JUNAS_SYNTH_AZURE_DEPLOYMENT",
                os.environ.get("AZURE_OPENAI_DEPLOYMENT", ""),
            ),
        )
    if provider == "anthropic":
        return SimpleNamespace(
            llm_provider="anthropic",
            anthropic_api_key=os.environ.get("ANTHROPIC_API_KEY", ""),
            anthropic_model=os.environ.get(
                "JUNAS_SYNTH_ANTHROPIC_MODEL",
                os.environ.get("ANTHROPIC_MODEL", "claude-sonnet-4-20250514"),
            ),
        )
    if provider == "gemini":
        return SimpleNamespace(
            llm_provider="gemini",
            gemini_api_key=os.environ.get("GEMINI_API_KEY", ""),
            gemini_model=os.environ.get("JUNAS_SYNTH_GOOGLE_MODEL", os.environ.get("GEMINI_MODEL", "gemini-2.0-flash")),
        )
    raise ValueError(f"unsupported provider: {provider}")


def generator_model_name(provider: str) -> str:
    if provider == "mock":
        return "mock:mock-synthetic-v1"
    settings = _settings_for_provider(provider)
    model = {
        "openai": getattr(settings, "openai_model", ""),
        "azure": getattr(settings, "azure_openai_deployment", ""),
        "anthropic": getattr(settings, "anthropic_model", ""),
        "gemini": getattr(settings, "gemini_model", ""),
    }.get(getattr(settings, "llm_provider", ""), "")
    return f"{provider}:{model or 'unknown'}"


def deterministic_generation_timestamp(seed: int, index: int) -> str:
    stamp = datetime(2026, 1, 1, tzinfo=timezone.utc) + timedelta(seconds=max(0, seed) + index)
    return stamp.replace(microsecond=0).isoformat().replace("+00:00", "Z")


def case_from_body(*, item: PlanItem, body: str, seed: int) -> dict[str, Any]:
    metadata = {
        "task": item.task.upper().replace("_", "-"),
        "sglb_task": item.task,
        "data_tier": "synthetic",
        "review_stage": "candidate",
        "review_status": "pending",
        "_human_review_status": "pending",
        "generator_provider": item.provider,
        "generator_model": generator_model_name(item.provider),
        "generator_version": GENERATOR_VERSION,
        "prompt_version": PROMPT_VERSION,
        "seed": seed,
        "generation_timestamp": deterministic_generation_timestamp(seed, item.index),
        "taxonomy_cell": item.cell.as_metadata(),
    }
    if item.task == "sglb_08":
        inputs = {
            "clause_text": body,
            "clause_type": item.cell.params["clause_type"],
        }
    elif item.task == "sglb_12":
        inputs = {"scenario": body}
    elif item.task == "sglb_15":
        inputs = {
            "drafting_brief": body,
            "constraints": item.cell.label["constraints"],
        }
    else:
        raise ValueError(f"unsupported synthetic task: {item.task}")

    case = {
        "name": item.slug,
        "inputs": inputs,
        "expected_output": dict(item.cell.label),
        "metadata": metadata,
    }
    metadata["quality"] = check_case_quality(case).as_dict()
    return case


def dataset_for_case(case: dict[str, Any]) -> dict[str, Any]:
    return {"cases": [case]}


def write_candidate_case(*, item: PlanItem, case: dict[str, Any]) -> Path:
    item.candidate_path.parent.mkdir(parents=True, exist_ok=True)
    item.candidate_path.write_text(
        yaml.safe_dump(dataset_for_case(case), sort_keys=False, default_flow_style=False, width=120),
        encoding="utf-8",
    )
    return item.candidate_path


async def generate_candidate(*, item: PlanItem, seed: int, generator: SyntheticGenerator | None = None) -> Path:
    active_generator = generator or SyntheticGenerator()
    body = await active_generator.generate_body(item)
    case = case_from_body(item=item, body=body, seed=seed)
    return write_candidate_case(item=item, case=case)


def plan_json(plan: list[PlanItem], *, estimated_cost_usd: float) -> str:
    payload = {
        "estimated_cost_usd": estimated_cost_usd,
        "items": [item.as_dict() for item in plan],
    }
    return json.dumps(payload, indent=2, sort_keys=True)
