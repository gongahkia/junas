"""SGLB-16 builder, task, scorer, and harness smoke tests."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from benchmark.dataset_builders import sglb_16 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_16_PROMPT_VERSION
from benchmark.registry import TASKS, is_benchmark_eligible
from benchmark.runner import run
from benchmark.schema import Case


def _ctx(case: Case, output: str) -> EvaluatorContext:
    return EvaluatorContext(
        case_name=case.name,
        inputs=case.inputs,
        expected_output=case.expected_output,
        metadata=case.metadata,
        output=output,
    )


def test_builder_emits_30_deterministic_cases_with_full_taxonomy():
    cases, stats = builder.build(n=30, sha="testsha")
    assert len(cases) == 30
    assert stats.emitted == 30
    assert stats.by_defect == {defect_type: 20 for defect_type in builder.DEFECT_TYPES}
    assert {case.extraction_rule_sha for case in cases} == {"testsha"}

    repeated, _ = builder.build(n=30, sha="testsha")
    assert [case.as_dict() for case in cases] == [case.as_dict() for case in repeated]


def test_governing_law_defect_span_points_to_planted_text():
    cases, _ = builder.build(n=3, sha="testsha")
    case = next(
        case
        for case in cases
        if any(defect.defect_type == "governing_law_non_singapore" for defect in case.defects)
    )
    defect = next(
        defect
        for defect in case.defects
        if defect.defect_type == "governing_law_non_singapore"
    )
    assert case.contract_text[defect.span_start : defect.span_end] == "State of New York"


def test_missing_clause_defects_use_zero_width_spans():
    cases, _ = builder.build(n=1, sha="testsha")
    missing = [
        defect
        for defect in cases[0].defects
        if defect.defect_type.startswith("missing_")
    ]
    assert missing
    assert all(defect.span_start == defect.span_end for defect in missing)


def test_write_dataset_outputs_harness_yaml(tmp_path: Path):
    cases, _ = builder.build(n=2, sha="testsha")
    output = tmp_path / "sglb_16.yaml"
    builder.write_dataset(cases, output)
    payload = output.read_text(encoding="utf-8")
    assert "sg_contract_template_defect_injection: testsha" in payload
    assert "sglb_16_" in payload


def test_sglb_16_task_registered_ineligible_for_public_leaderboard():
    assert "sglb_16" in TASKS
    assert is_benchmark_eligible("sglb_16") is False


def test_sglb_16_evaluator_registered_strong():
    assert EVALUATORS["sglb_16_redflag_f1"].strength == EvaluatorStrength.STRONG


def test_sglb_16_evaluator_scores_exact_and_near_spans():
    case = Case(
        name="t",
        inputs={"contract_text": "x" * 200},
        expected_output={
            "defects": [
                {"defect_type": "missing_notice_period", "span_start": 100, "span_end": 100}
            ]
        },
        metadata={},
    )
    exact = json.dumps(
        [{"defect_type": "missing_notice_period", "span_start": 100, "span_end": 100}]
    )
    near = json.dumps(
        [{"defect_type": "missing_notice_period", "span_start": 108, "span_end": 109}]
    )
    wrong = json.dumps(
        [{"defect_type": "missing_notice_period", "span_start": 140, "span_end": 140}]
    )

    assert asyncio.run(EVALUATORS["sglb_16_redflag_f1"].evaluate(_ctx(case, exact))).score == 1.0
    assert asyncio.run(EVALUATORS["sglb_16_redflag_f1"].evaluate(_ctx(case, near))).score == 1.0
    assert asyncio.run(EVALUATORS["sglb_16_redflag_f1"].evaluate(_ctx(case, wrong))).score == 0.0


def test_sglb_16_prompt_builder_registered():
    assert "sglb_16" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_16"]
    assert version == SGLB_16_PROMPT_VERSION
    case = Case(name="t", inputs={"contract_text": "Agreement text"}, expected_output={}, metadata={})
    messages = fn(case)
    assert "defect_type" in messages[0]["content"]
    assert "Agreement text" in messages[1]["content"]


def test_sglb_16_harness_oracle_scores_one(tmp_path: Path):
    cases, _ = builder.build(n=5, sha="testsha")
    yaml_path = tmp_path / "sglb_16.yaml"
    builder.write_dataset(cases, yaml_path)
    summary = asyncio.run(
        run(
            workflow="sglb_16",
            dataset_path=yaml_path,
            evaluators=["sglb_16_redflag_f1"],
            strict=True,
        )
    )
    assert summary.total_cases == 5
    assert summary.per_evaluator_mean()["sglb_16_redflag_f1"] == pytest.approx(1.0)
