"""SGLB-01 task runner + evaluator + prompt builder integration."""
from __future__ import annotations

import asyncio
import json

import pytest

from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_01_PROMPT_VERSION
from benchmark.registry import TASKS
from benchmark.schema import Case


def _make_case(*, obligations: list[str], band: str) -> Case:
    return Case(
        name="t",
        inputs={"fact_summary": "redacted facts"},
        expected_output={"obligations": obligations, "penalty_band": band},
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


def test_sglb_01_task_registered():
    assert "sglb_01" in TASKS


def test_sglb_01_evaluators_registered_strong():
    assert EVALUATORS["sglb_01_obligations_f1"].strength == EvaluatorStrength.STRONG
    assert EVALUATORS["penalty_band_mae"].strength == EvaluatorStrength.STRONG


def test_oracle_runner_returns_expected_as_json():
    case = _make_case(obligations=["protection"], band="mid")
    output = asyncio.run(TASKS["sglb_01"](case))
    payload = json.loads(output)
    assert payload["obligations"] == ["protection"]
    assert payload["penalty_band"] == "mid"


def test_oracle_runner_scores_perfectly_against_both_evaluators():
    case = _make_case(obligations=["protection", "accountability"], band="high")
    output = asyncio.run(TASKS["sglb_01"](case))
    f1 = asyncio.run(EVALUATORS["sglb_01_obligations_f1"].evaluate(_ctx(case, output)))
    mae = asyncio.run(EVALUATORS["penalty_band_mae"].evaluate(_ctx(case, output)))
    assert f1.score == pytest.approx(1.0)
    assert mae.score == pytest.approx(1.0)


def test_obligations_f1_partial_overlap():
    case = _make_case(obligations=["protection", "accountability"], band="mid")
    output = json.dumps({"obligations": ["protection"], "penalty_band": "mid"})
    f1 = asyncio.run(EVALUATORS["sglb_01_obligations_f1"].evaluate(_ctx(case, output)))
    # tp=1, p=1.0, r=0.5 → f1 = 2*1*0.5/(1.5) = 2/3
    assert f1.score == pytest.approx(2 / 3)


def test_obligations_f1_handles_malformed_json():
    case = _make_case(obligations=["protection"], band="mid")
    f1 = asyncio.run(EVALUATORS["sglb_01_obligations_f1"].evaluate(_ctx(case, "not-json")))
    assert f1.score == 0.0


def test_penalty_band_mae_off_by_one():
    case = _make_case(obligations=["protection"], band="mid")
    output = json.dumps({"obligations": ["protection"], "penalty_band": "high"})
    mae = asyncio.run(EVALUATORS["penalty_band_mae"].evaluate(_ctx(case, output)))
    # diff=1, score = 1 - 1/3 = 2/3
    assert mae.score == pytest.approx(2 / 3)
    assert mae.detail["mae"] == 1.0


def test_penalty_band_mae_max_distance():
    case = _make_case(obligations=["protection"], band="none")
    output = json.dumps({"obligations": ["protection"], "penalty_band": "high"})
    mae = asyncio.run(EVALUATORS["penalty_band_mae"].evaluate(_ctx(case, output)))
    assert mae.score == 0.0


def test_penalty_band_mae_unparseable_prediction():
    case = _make_case(obligations=["protection"], band="mid")
    mae = asyncio.run(EVALUATORS["penalty_band_mae"].evaluate(_ctx(case, "garbage")))
    assert mae.score == 0.0


def test_sglb_01_prompt_builder_registered():
    assert "sglb_01" in PROMPT_BUILDERS
    builder, version = PROMPT_BUILDERS["sglb_01"]
    assert version == SGLB_01_PROMPT_VERSION
    case = _make_case(obligations=["protection"], band="mid")
    messages = builder(case)
    assert messages[0]["role"] == "system"
    assert messages[-1]["role"] == "user"
    assert "redacted facts" in messages[-1]["content"]
    # The closed taxonomy must appear in the system prompt for the model.
    assert "protection" in messages[0]["content"]
    assert "accountability" in messages[0]["content"]
    assert "penalty_band" in messages[0]["content"]
