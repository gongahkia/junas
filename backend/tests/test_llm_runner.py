"""Tests for benchmark.llm_runner.

Every test uses ``MockLLMClient``. There are no real-network calls.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from benchmark.llm_runner import (
    LLMRunnerConfig,
    MockLLMClient,
    PROMPT_BUILDERS,
    build_llm_task,
    llm_task_for,
    prompt_sha,
    sglb_04_prompt_builder,
    sglb_08_prompt_builder,
    sglb_11_prompt_builder,
    sglb_12_prompt_builder,
)
from benchmark.runner import run
from benchmark.schema import Case


# === Mock client ===


def test_mock_client_counts_calls():
    client = MockLLMClient(default_response='["valid"]')
    asyncio.run(client.generate([{"role": "user", "content": "x"}]))
    asyncio.run(client.generate([{"role": "user", "content": "y"}]))
    assert client.calls == 2


def test_mock_client_returns_canned_for_match():
    client = MockLLMClient(
        canned={"hello": '["yes"]', "world": '["no"]'},
        default_response="default",
    )
    out = asyncio.run(client.generate([{"role": "user", "content": "hello"}]))
    assert out == '["yes"]'


def test_mock_client_returns_default_for_unknown():
    client = MockLLMClient(canned={"x": "y"}, default_response="fallback")
    out = asyncio.run(client.generate([{"role": "user", "content": "z"}]))
    assert out == "fallback"


# === Prompt builders ===


def test_sglb_04_prompt_has_system_and_user_roles():
    case = Case(name="c1", inputs={"citation": "[2023] SGCA 5"})
    msgs = sglb_04_prompt_builder(case)
    roles = [m["role"] for m in msgs]
    assert "system" in roles
    assert "user" in roles
    # The citation appears verbatim in the user message.
    user = next(m for m in msgs if m["role"] == "user")
    assert user["content"].strip() == "[2023] SGCA 5"


def test_sglb_11_prompt_carries_passage():
    case = Case(name="c1", inputs={"passage": "passage with [2023] SGCA 5"})
    msgs = sglb_11_prompt_builder(case)
    user = next(m for m in msgs if m["role"] == "user")
    assert "[2023] SGCA 5" in user["content"]


def test_sglb_08_prompt_includes_clause_type_and_text():
    case = Case(
        name="c1",
        inputs={"clause_text": "The party shall...", "clause_type": "indemnification"},
    )
    msgs = sglb_08_prompt_builder(case)
    user = next(m for m in msgs if m["role"] == "user")
    assert "indemnification" in user["content"]
    assert "The party shall" in user["content"]


def test_sglb_12_prompt_carries_scenario():
    case = Case(name="c1", inputs={"scenario": "A company collected PII without consent."})
    msgs = sglb_12_prompt_builder(case)
    user = next(m for m in msgs if m["role"] == "user")
    assert "PII" in user["content"]


# === Build LLM task ===


def test_build_llm_task_calls_client():
    client = MockLLMClient(default_response='["valid"]')
    runner = build_llm_task(
        client=client,
        config=LLMRunnerConfig(
            prompt_builder=sglb_04_prompt_builder,
            prompt_version="sglb-04-test",
        ),
    )
    case = Case(name="c1", inputs={"citation": "[2023] SGCA 5"})
    out = asyncio.run(runner(case))
    assert out == '["valid"]'
    assert client.calls == 1


def test_build_llm_task_returns_empty_on_provider_error():
    class _Broken:
        async def generate(self, messages, max_tokens=1024):  # noqa: ARG002
            raise RuntimeError("provider down")

    runner = build_llm_task(
        client=_Broken(),
        config=LLMRunnerConfig(
            prompt_builder=sglb_04_prompt_builder,
            prompt_version="sglb-04-test",
        ),
    )
    case = Case(name="c1", inputs={"citation": "[2023] SGCA 5"})
    # The runner must NOT raise — failures surface as empty output so
    # the evaluator scores 0 against that case.
    out = asyncio.run(runner(case))
    assert out == ""


def test_build_llm_task_coerces_non_string_output():
    class _ReturnsInt:
        async def generate(self, messages, max_tokens=1024):  # noqa: ARG002
            return 42  # type: ignore[return-value]

    runner = build_llm_task(
        client=_ReturnsInt(),
        config=LLMRunnerConfig(prompt_builder=sglb_04_prompt_builder, prompt_version="v"),
    )
    case = Case(name="c1", inputs={"citation": "x"})
    out = asyncio.run(runner(case))
    assert out == "42"


# === llm_task_for convenience ===


def test_llm_task_for_resolves_registered_workflow():
    client = MockLLMClient(default_response='["invalid"]')
    runner = llm_task_for(workflow="sglb_04", client=client, provider_label="mock:test")
    case = Case(name="c1", inputs={"citation": "garbage"})
    out = asyncio.run(runner(case))
    assert out == '["invalid"]'


def test_llm_task_for_rejects_unknown_workflow():
    client = MockLLMClient()
    with pytest.raises(ValueError, match="no prompt builder registered"):
        llm_task_for(workflow="does_not_exist", client=client)


# === Reproducibility: prompt_sha ===


def test_prompt_sha_is_deterministic():
    case = Case(name="c1", inputs={"citation": "[2023] SGCA 5"})
    a = prompt_sha(sglb_04_prompt_builder, case)
    b = prompt_sha(sglb_04_prompt_builder, case)
    assert a == b
    assert len(a) == 16


def test_prompt_sha_differs_across_inputs():
    case_a = Case(name="a", inputs={"citation": "[2023] SGCA 5"})
    case_b = Case(name="b", inputs={"citation": "[2024] SGHC 99"})
    assert prompt_sha(sglb_04_prompt_builder, case_a) != prompt_sha(
        sglb_04_prompt_builder, case_b
    )


# === Registry contains shipped/scaffolded LLM prompt builders ===


def test_prompt_builders_registry_complete():
    assert set(PROMPT_BUILDERS) == {
        "sglb_01",
        "sglb_02",
        "sglb_04",
        "sglb_05",
        "sglb_06",
        "sglb_07",
        "sglb_08",
        "sglb_09",
        "sglb_10",
        "sglb_11",
        "sglb_12",
        "sglb_13",
        "sglb_14",
        "sglb_16",
    }


def test_prompt_builders_each_carry_version():
    for workflow, (_builder, version) in PROMPT_BUILDERS.items():
        assert version, f"{workflow} prompt has no version"
        assert workflow.replace("_", "-") in version.lower()


# === End-to-end with the harness ===


def test_end_to_end_oracle_perfect_scoring_via_mock():
    """Wire a MockLLMClient that returns the gold answer for every SGLB-04
    citation, register the runner, and run the smoke dataset through the
    harness. Should score 1.0 on multi_label_f1."""
    from benchmark.registry import register_task

    # Build a mock that always says "valid" for grammar-clean citations.
    # Lookup table mirrors validate_citation: known well-formed → ["valid"],
    # known malformed → ["invalid"].
    from api.services.sal_citation import validate_citation

    class _GoldOracleClient:
        async def generate(self, messages, max_tokens=1024):  # noqa: ARG002
            user_content = next(
                (m.get("content", "") for m in reversed(messages) if m.get("role") == "user"),
                "",
            )
            return json.dumps(["valid"]) if validate_citation(user_content).valid else json.dumps(["invalid"])

    runner = llm_task_for(workflow="sglb_04", client=_GoldOracleClient(), provider_label="mock:gold")
    register_task("sglb_04_llm_gold", runner)

    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml"
    summary = asyncio.run(
        run(
            workflow="sglb_04_llm_gold",
            dataset_path=smoke,
            evaluators=["multi_label_f1"],
            strict=True,
        )
    )
    assert summary.total_cases == 30
    assert summary.per_evaluator_mean()["multi_label_f1"] == pytest.approx(1.0)


def test_end_to_end_provider_error_scores_zero():
    """A provider that always errors out must yield score=0 on every
    case, not crash the harness."""
    from benchmark.registry import register_task

    class _BrokenClient:
        async def generate(self, messages, max_tokens=1024):  # noqa: ARG002
            raise RuntimeError("provider down")

    runner = llm_task_for(workflow="sglb_04", client=_BrokenClient())
    register_task("sglb_04_llm_broken", runner)

    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml"
    summary = asyncio.run(
        run(
            workflow="sglb_04_llm_broken",
            dataset_path=smoke,
            evaluators=["multi_label_f1"],
        )
    )
    # Every case scores 0 since the model returns "" (no labels parsed).
    assert summary.per_evaluator_mean()["multi_label_f1"] == 0.0


def test_end_to_end_partial_correctness_via_canned():
    """A model that gets some answers right and some wrong should
    produce an intermediate score, not 0 or 1."""
    from benchmark.registry import register_task

    # Always returns ["valid"] regardless of input. The smoke dataset
    # has both valid and invalid citations, so the score should be
    # close to (# valid) / 30.
    class _AlwaysValidClient:
        async def generate(self, messages, max_tokens=1024):  # noqa: ARG002
            return json.dumps(["valid"])

    runner = llm_task_for(workflow="sglb_04", client=_AlwaysValidClient())
    register_task("sglb_04_llm_alwaysvalid", runner)

    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml"
    summary = asyncio.run(
        run(
            workflow="sglb_04_llm_alwaysvalid",
            dataset_path=smoke,
            evaluators=["multi_label_f1"],
        )
    )
    score = summary.per_evaluator_mean()["multi_label_f1"]
    # Must be strictly between 0 and 1 — proves the harness is producing
    # real numbers, not vacuous oracle scores.
    assert 0.0 < score < 1.0, f"expected partial score, got {score}"
