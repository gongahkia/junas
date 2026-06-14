"""SGLB-10 Citation-Generation builder, task, scorer, and harness smoke."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from benchmark.dataset_builders import sglb_10 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_10_PROMPT_VERSION
from benchmark.registry import TASKS, is_benchmark_eligible
from benchmark.runner import run
from benchmark.schema import Case


def _case(citation: str = "Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] 4 SLR(R) 100") -> Case:
    return Case(
        name="t",
        inputs={"fact_pattern": "A negligence brief asks for the Singapore authority on duty of care."},
        expected_output={"citations": [citation]},
        metadata={},
    )


def _ctx(case: Case, output: str) -> EvaluatorContext:
    return EvaluatorContext(
        case_name=case.name,
        inputs=case.inputs,
        expected_output=case.expected_output,
        metadata=case.metadata,
        output=output,
    )


def test_builder_emits_40_deterministic_smoke_cases():
    cases, stats = builder.build(n=40, sha="testsha")
    repeated, _ = builder.build(n=40, sha="testsha")
    assert len(cases) == 40
    assert stats.emitted == 40
    assert sum(stats.by_domain.values()) == 40
    assert {"tort", "contract", "equity", "public", "criminal", "family", "ip", "company", "procedure"} <= set(stats.by_domain)
    assert [case.as_dict() for case in cases] == [case.as_dict() for case in repeated]
    assert all(case.extraction_rule_sha == "testsha" for case in cases)
    assert all(case.as_dict()["metadata"]["data_tier"] == "synthetic" for case in cases)


def test_builder_rejects_pool_overflow():
    with pytest.raises(ValueError):
        builder.build(n=10_000, sha="testsha")


def test_write_dataset_outputs_harness_yaml(tmp_path: Path):
    cases, _ = builder.build(n=3, sha="testsha")
    output = tmp_path / "sglb_10.yaml"
    builder.write_dataset(cases, output)
    payload = yaml.safe_load(output.read_text(encoding="utf-8"))
    assert payload["extraction_rules"] == {builder.EXTRACTION_RULE_NAME: "testsha"}
    assert payload["cases"][0]["expected_output"]["citations"]
    assert payload["cases"][0]["metadata"]["label_provenance"].startswith("mechanical-copy")


def test_sglb_10_task_registered_ineligible_for_public_leaderboard():
    assert "sglb_10" in TASKS
    assert is_benchmark_eligible("sglb_10") is False


def test_sglb_10_evaluators_registered_strong():
    assert EVALUATORS["citation_generation_top1"].strength == EvaluatorStrength.STRONG
    assert EVALUATORS["citation_generation_top3"].strength == EvaluatorStrength.STRONG


def test_sglb_10_prompt_builder_registered():
    assert "sglb_10" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_10"]
    assert version == SGLB_10_PROMPT_VERSION
    messages = fn(_case())
    assert messages[0]["role"] == "system"
    assert "JSON array" in messages[0]["content"]
    assert "duty of care" in messages[1]["content"]


def test_oracle_runner_returns_expected_citation_array():
    case = _case()
    out = asyncio.run(TASKS["sglb_10"](case))
    assert json.loads(out) == case.expected_output["citations"]


def test_top1_and_top3_score_perfect_oracle_output():
    case = _case()
    out = asyncio.run(TASKS["sglb_10"](case))
    assert asyncio.run(EVALUATORS["citation_generation_top1"].evaluate(_ctx(case, out))).score == 1.0
    assert asyncio.run(EVALUATORS["citation_generation_top3"].evaluate(_ctx(case, out))).score == 1.0


def test_top1_misses_when_gold_is_second_but_top3_hits():
    case = _case("RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd [2007] 4 SLR(R) 413")
    out = json.dumps([
        "Spandeck Engineering (S) Pte Ltd v Defence Science & Technology Agency [2007] 4 SLR(R) 100",
        "RDC Concrete Pte Ltd v Sato Kogyo (S) Pte Ltd [2007] 4 SLR(R) 413",
    ])
    assert asyncio.run(EVALUATORS["citation_generation_top1"].evaluate(_ctx(case, out))).score == 0.0
    assert asyncio.run(EVALUATORS["citation_generation_top3"].evaluate(_ctx(case, out))).score == 1.0


def test_shipped_smoke_dataset_yaml_loads():
    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_10_citation_generation_smoke.yaml"
    assert smoke.exists()
    raw = yaml.safe_load(smoke.read_text(encoding="utf-8"))
    assert 30 <= len(raw["cases"]) <= 50
    assert raw["cases"][0]["metadata"]["data_tier"] == "synthetic"


def test_sglb_10_harness_oracle_scores_one(tmp_path: Path):
    cases, _ = builder.build(n=5, sha="testsha")
    yaml_path = tmp_path / "sglb_10.yaml"
    builder.write_dataset(cases, yaml_path)
    summary = asyncio.run(
        run(
            workflow="sglb_10",
            dataset_path=yaml_path,
            evaluators=["citation_generation_top1", "citation_generation_top3"],
            strict=True,
        )
    )
    assert summary.total_cases == 5
    means = summary.per_evaluator_mean()
    assert means["citation_generation_top1"] == pytest.approx(1.0)
    assert means["citation_generation_top3"] == pytest.approx(1.0)
