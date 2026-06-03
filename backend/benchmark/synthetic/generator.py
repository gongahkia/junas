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
from benchmark.synthetic.planner import PlanItem
from benchmark.synthetic.prompts import render_prompt
from benchmark.synthetic.taxonomy import GENERATOR_VERSION, PROMPT_VERSION


class LLMLike(Protocol):
    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        ...


@dataclass
class MockLLM:
    provider: str = "mock"
    calls: int = 0

    async def generate(self, messages: list[dict[str, str]], max_tokens: int = 1024) -> str:
        del max_tokens
        self.calls += 1
        prompt = "\n".join(message.get("content", "") for message in messages)
        return f"Mock synthetic body generated for {self.provider}. Prompt digest: {prompt[:180]}"


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


def _settings_for_provider(provider: str) -> SimpleNamespace:
    if provider == "google":
        provider = "gemini"
    if provider == "openai":
        return SimpleNamespace(
            llm_provider="openai",
            openai_api_key=os.environ.get("OPENAI_API_KEY", ""),
            openai_model=os.environ.get("JUNAS_SYNTH_OPENAI_MODEL", os.environ.get("OPENAI_MODEL", "gpt-4o-mini")),
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

    return {
        "name": item.slug,
        "inputs": inputs,
        "expected_output": dict(item.cell.label),
        "metadata": metadata,
    }


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
