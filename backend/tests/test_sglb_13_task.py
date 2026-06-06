"""SGLB-13 Counterfactual-Outcome task runner + builder + scorer."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from benchmark.dataset_builders import sglb_13 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_13_PROMPT_VERSION
from benchmark.registry import TASKS
from benchmark.schema import Case


def _make_case(*, outcome_changes: bool) -> Case:
    return Case(
        name="t",
        inputs={
            "fact_pattern": "A penalty was imposed on X for failing to put in place reasonable security measures.",
            "perturbation": "A penalty was imposed on X.",
        },
        expected_output={"outcome_changes": outcome_changes},
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


def _source_row(*, source_id: str, fact_summary: str, obligations: list[str]) -> dict:
    return {
        "id": source_id,
        "extraction_rule_sha": "abcdef1",
        "inputs": {"fact_summary": fact_summary},
        "expected_output": {"obligations": obligations, "penalty_band": "mid"},
        "metadata": {
            "task": "SGLB-01",
            "split": "train",
            "jurisdiction": "SG",
            "citation": "[2020] SGPDPC 1",
            "source_url": "https://example.test/case",
        },
    }


# --- builder unit ---


def test_find_cue_span_protection():
    text = "A warning was issued for failing to put in place reasonable security arrangements to protect data."
    span, match = builder._find_cue_span(text, "protection")
    assert match is not None
    assert "reasonable security arrangements" in span


def test_find_cue_span_accountability_dpo():
    text = "The organisation failed to appoint a data protection officer."
    span, match = builder._find_cue_span(text, "accountability")
    assert match is not None
    assert "data protection officer" in span.lower()


def test_find_cue_span_missing_returns_none():
    text = "An unrelated narrative without any obligation cue."
    span, match = builder._find_cue_span(text, "protection")
    assert match is None and span == ""


def test_apply_perturbation_strips_trailing_conjunction():
    text = "A penalty was imposed on X for failing to put in place reasonable security arrangements and for failing to appoint a data protection officer."
    _, match = builder._find_cue_span(text, "accountability")
    assert match is not None
    out = builder._apply_perturbation(text, match)
    # no trailing "and ."
    assert not out.endswith("and.")
    assert "data protection officer" not in out.lower()


def test_apply_perturbation_collapses_enum_artifacts():
    text = "Breaches of the PDPA. First, X. Second, Y."
    # synthetic match removing "First, X."
    pattern = builder.re.compile(r"First, X\.", builder.re.IGNORECASE)
    match = pattern.search(text)
    assert match is not None
    out = builder._apply_perturbation(text, match)
    assert "First, Second" not in out


def test_stable_case_id_is_deterministic():
    a = builder._stable_case_id("sglb_01_abc", "protection")
    b = builder._stable_case_id("sglb_01_abc", "protection")
    assert a == b and a.startswith("sglb_13_")
    c = builder._stable_case_id("sglb_01_abc", "accountability")
    assert c != a


def test_build_for_row_single_obligation_label_is_changes(tmp_path: Path):
    row = _source_row(
        source_id="sglb_01_single",
        fact_summary=(
            "A warning was issued to Acme Pte Ltd, a registered consumer-data processor, "
            "for failing to put in place reasonable security arrangements to protect "
            "customer data collected via its website portal."
        ),
        obligations=["protection"],
    )
    cases, reason = builder._build_for_row(row, "train", "rulesha1")
    assert reason == ""
    assert len(cases) == 1
    case = cases[0]
    assert case.outcome_changes is True
    assert case.perturbed_obligation == "protection"
    # perturbation excised the cue clause
    assert "security arrangements" not in case.perturbation.lower()


def test_build_for_row_two_obligations_yield_two_unchanged_rows():
    row = _source_row(
        source_id="sglb_01_multi",
        fact_summary=(
            "An enforcement outcome resulted for The Travel Corporation for breaches of the PDPA. "
            "The Organisation failed to appoint a data protection officer and did not put in place "
            "reasonable security arrangements to protect customer data."
        ),
        obligations=["protection", "accountability"],
    )
    cases, reason = builder._build_for_row(row, "dev", "rulesha2")
    assert reason == ""
    assert len(cases) == 2
    for c in cases:
        # both members of a multi-obligation case must be outcome_unchanged
        assert c.outcome_changes is False
        assert c.split == "dev"
    perturbed = {c.perturbed_obligation for c in cases}
    assert perturbed == {"protection", "accountability"}


def test_build_for_row_rejects_overlapping_cues():
    # cue for "protection" greedy span swallows both obligations' facts.
    row = _source_row(
        source_id="sglb_01_overlap",
        fact_summary=(
            "Penalty for Acme for failing to put in place reasonable security arrangements "
            "to protect data and for not developing and implementing data protection policies."
        ),
        obligations=["protection", "accountability"],
    )
    cases, reason = builder._build_for_row(row, "train", "rulesha3")
    assert cases == []
    assert "overlapping" in reason


def test_build_for_row_rejects_obligation_without_cue():
    row = _source_row(
        source_id="sglb_01_nocue",
        fact_summary="A warning was issued for failing to put in place reasonable security arrangements.",
        obligations=["consent"],  # no consent cue in this text
    )
    cases, reason = builder._build_for_row(row, "train", "x")
    assert cases == []
    assert "no cue" in reason


def test_build_full_pipeline(tmp_path: Path):
    src_dir = tmp_path / "src"
    src_dir.mkdir()
    rows = [
        _source_row(
            source_id="sglb_01_a",
            fact_summary="A warning was issued for failing to put in place reasonable security arrangements to protect customer data.",
            obligations=["protection"],
        ),
        _source_row(
            source_id="sglb_01_b",
            fact_summary=(
                "An enforcement outcome resulted for X for breaches of the PDPA. The organisation "
                "did not make reasonable security arrangements to prevent unauthorised disclosure of "
                "its clients' personal data and failed to put in place data protection policies."
            ),
            obligations=["protection", "accountability"],
        ),
    ]
    (src_dir / "train.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )
    (src_dir / "dev.jsonl").write_text("", encoding="utf-8")
    (src_dir / "test.jsonl").write_text("", encoding="utf-8")
    cases, stats = builder.build(src_dir, "rulesha4")
    assert stats.emitted == 3  # 1 from single-obligation, 2 from multi
    assert stats.by_label["outcome_changes"] == 1
    assert stats.by_label["outcome_unchanged"] == 2
    case_dict = cases[0].as_dict()
    assert case_dict["extraction_rule_sha"] == "rulesha4"
    assert case_dict["metadata"]["label_provenance"].startswith("mechanical-derivation")
    assert case_dict["metadata"]["dataset_version"] == builder.DATASET_VERSION


# --- task + scorer integration ---


def test_sglb_13_task_registered():
    assert "sglb_13" in TASKS


def test_sglb_13_evaluator_registered_strong():
    assert EVALUATORS["sglb_13_outcome_accuracy"].strength == EvaluatorStrength.STRONG


def test_sglb_13_prompt_builder_registered():
    assert "sglb_13" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_13"]
    assert version == SGLB_13_PROMPT_VERSION
    msgs = fn(_make_case(outcome_changes=True))
    assert msgs[0]["role"] == "system"
    assert "outcome_changes" in msgs[0]["content"]
    assert "PDPC" in msgs[0]["content"]


def test_oracle_runner_returns_expected():
    case = _make_case(outcome_changes=True)
    out = asyncio.run(TASKS["sglb_13"](case))
    payload = json.loads(out)
    assert payload == {"outcome_changes": True}


def test_oracle_runner_scores_perfectly():
    case_true = _make_case(outcome_changes=True)
    case_false = _make_case(outcome_changes=False)
    for case in (case_true, case_false):
        out = asyncio.run(TASKS["sglb_13"](case))
        score = asyncio.run(EVALUATORS["sglb_13_outcome_accuracy"].evaluate(_ctx(case, out)))
        assert score.score == pytest.approx(1.0)


def test_accuracy_evaluator_wrong_prediction():
    case = _make_case(outcome_changes=True)
    out = json.dumps({"outcome_changes": False})
    score = asyncio.run(EVALUATORS["sglb_13_outcome_accuracy"].evaluate(_ctx(case, out)))
    assert score.score == 0.0


def test_accuracy_evaluator_malformed_output():
    case = _make_case(outcome_changes=True)
    score = asyncio.run(EVALUATORS["sglb_13_outcome_accuracy"].evaluate(_ctx(case, "not-json")))
    assert score.score == 0.0


def test_accuracy_evaluator_string_booleans():
    case = _make_case(outcome_changes=True)
    out = json.dumps({"outcome_changes": "true"})
    score = asyncio.run(EVALUATORS["sglb_13_outcome_accuracy"].evaluate(_ctx(case, out)))
    assert score.score == 1.0


def test_accuracy_evaluator_missing_expected_returns_zero():
    case = Case(name="t", inputs={}, expected_output={}, metadata={})
    score = asyncio.run(EVALUATORS["sglb_13_outcome_accuracy"].evaluate(_ctx(case, json.dumps({"outcome_changes": True}))))
    assert score.score == 0.0
