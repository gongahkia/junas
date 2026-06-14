"""SGLB-09 Summary-Faithfulness builder, task, scorer, and harness smoke."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from benchmark.dataset_builders import sglb_09 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_09_PROMPT_VERSION
from benchmark.registry import TASKS, is_benchmark_eligible
from benchmark.runner import run
from benchmark.schema import Case


def _case() -> Case:
    return Case(
        name="t",
        inputs={
            "source_text": "A warning was issued to Acme for failing to protect customer data.",
            "summary": "A warning was issued to Acme for failing to protect customer data.",
        },
        expected_output={
            "atomic_facts": [
                {
                    "fact": "A warning was issued to Acme for failing to protect customer data.",
                    "supported": True,
                }
            ]
        },
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


def _source_row(source_id: str, fact_summary: str) -> dict:
    return {
        "id": source_id,
        "inputs": {"fact_summary": fact_summary},
        "expected_output": {"obligations": ["protection"], "penalty_band": "none"},
        "metadata": {
            "case_name": "Re Acme",
            "citation": "[2026] SGPDPC 1",
            "source_url": "https://example.test/acme",
            "split": "train",
            "task": "SGLB-01",
        },
    }


def test_builder_emits_20_deterministic_smoke_cases():
    src = Path(__file__).parent.parent / "data" / "benchmarks" / "sglb_01_pdpa"
    cases, stats = builder.build(src, "testsha", n=20)
    repeated, _ = builder.build(src, "testsha", n=20)
    assert len(cases) == 20
    assert stats.emitted == 20
    assert stats.by_split == {"train": 16, "dev": 2, "test": 2}
    assert set(stats.by_variant) == {"faithful", "mild_hallucination", "wholesale_fabrication"}
    assert [case.as_dict() for case in cases] == [case.as_dict() for case in repeated]
    assert all(case.extraction_rule_sha == "testsha" for case in cases)
    assert all(case.as_dict()["metadata"]["benchmark_eligible"] is False for case in cases)


def test_build_from_temp_source_rejects_empty_n(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    (src / "train.jsonl").write_text("", encoding="utf-8")
    with pytest.raises(ValueError, match="n must be positive"):
        builder.build(src, "testsha", n=0)


def test_write_outputs_writes_yaml_and_split_jsonl(tmp_path: Path):
    src = tmp_path / "src"
    src.mkdir()
    rows = [
        _source_row(f"sglb_01_{idx}", f"A warning was issued to Acme {idx} for failing to protect data.")
        for idx in range(3)
    ]
    (src / "train.jsonl").write_text(
        "\n".join(json.dumps(row) for row in rows) + "\n",
        encoding="utf-8",
    )
    cases, _ = builder.build(src, "testsha", n=3)
    yaml_path = tmp_path / "sglb_09.yaml"
    jsonl_dir = tmp_path / "jsonl"
    counts = builder.write_outputs(cases, "testsha", yaml_path, jsonl_dir)
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert payload["extraction_rules"] == {builder.EXTRACTION_RULE_NAME: "testsha"}
    assert payload["cases"][0]["inputs"]["source_text"]
    assert payload["cases"][0]["expected_output"]["atomic_facts"]
    assert sum(counts.values()) == 3
    assert (jsonl_dir / "train.jsonl").exists()


def test_sglb_09_task_registered_ineligible_for_public_leaderboard():
    assert "sglb_09" in TASKS
    assert is_benchmark_eligible("sglb_09") is False


def test_atomic_fact_score_registered_strong():
    assert EVALUATORS["atomic_fact_score"].strength == EvaluatorStrength.STRONG


def test_sglb_09_prompt_builder_registered():
    assert "sglb_09" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_09"]
    assert version == SGLB_09_PROMPT_VERSION
    messages = fn(_case())
    assert messages[0]["role"] == "system"
    assert "atomic_facts" in messages[0]["content"]
    assert "Source text:" in messages[1]["content"]
    assert "Candidate summary:" in messages[1]["content"]


def test_oracle_runner_returns_expected_atomic_facts():
    case = _case()
    out = asyncio.run(TASKS["sglb_09"](case))
    assert json.loads(out) == case.expected_output


def test_atomic_fact_score_perfect_oracle_output():
    case = _case()
    out = asyncio.run(TASKS["sglb_09"](case))
    result = asyncio.run(EVALUATORS["atomic_fact_score"].evaluate(_ctx(case, out)))
    assert result.score == pytest.approx(1.0)
    assert result.detail["source_supported_count"] == 1


def test_atomic_fact_score_penalises_unsupported_claim_marked_supported():
    case = _case()
    output = json.dumps(
        {
            "atomic_facts": [
                {
                    "fact": "A warning was issued to Acme for failing to protect customer data.",
                    "supported": True,
                },
                {"fact": "The directors were imprisoned.", "supported": True},
            ]
        }
    )
    result = asyncio.run(EVALUATORS["atomic_fact_score"].evaluate(_ctx(case, output)))
    assert result.score == pytest.approx(0.5)
    assert result.detail["unsupported_supported_facts"] == ["The directors were imprisoned."]


def test_atomic_fact_score_scores_malformed_output_zero_when_gold_has_supported_fact():
    case = _case()
    result = asyncio.run(EVALUATORS["atomic_fact_score"].evaluate(_ctx(case, "not-json")))
    assert result.score == 0.0


def test_shipped_smoke_dataset_yaml_loads():
    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_09_summary_faithfulness.yaml"
    assert smoke.exists()
    raw = yaml.safe_load(smoke.read_text(encoding="utf-8"))
    assert len(raw["cases"]) == 20
    assert raw["cases"][0]["metadata"]["data_tier"] == "synthetic"


def test_sglb_09_harness_oracle_scores_one(tmp_path: Path):
    src = Path(__file__).parent.parent / "data" / "benchmarks" / "sglb_01_pdpa"
    cases, _ = builder.build(src, "testsha", n=5)
    yaml_path = tmp_path / "sglb_09.yaml"
    builder.write_outputs(cases, "testsha", yaml_path, tmp_path / "jsonl")
    summary = asyncio.run(
        run(
            workflow="sglb_09",
            dataset_path=yaml_path,
            evaluators=["atomic_fact_score"],
            strict=True,
        )
    )
    assert summary.total_cases == 5
    assert summary.per_evaluator_mean()["atomic_fact_score"] == pytest.approx(1.0)
