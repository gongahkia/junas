"""SGLB-07 Jurisdiction-Routing task runner + builder."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from benchmark.dataset_builders import sglb_07 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_07_PROMPT_VERSION
from benchmark.registry import TASKS
from benchmark.schema import Case


def _make_case(label: str) -> Case:
    return Case(
        name="t",
        inputs={"question": "Whether the doctrine of laches applies in equity claims under SG common-law."},
        expected_output={"labels": [label]},
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


# --- builder unit ---


def test_normalise_label_canonicalises_known():
    assert builder._normalise_label("sg_binding") == "sg_binding"
    assert builder._normalise_label("UK-Persuasive") == "uk_persuasive"


def test_normalise_label_rejects_unknown():
    assert builder._normalise_label("madeup") == ""
    assert builder._normalise_label("") == ""


def test_stable_case_id_deterministic():
    a = builder._stable_case_id("[2018] SGCA 14")
    b = builder._stable_case_id("[2018] SGCA 14")
    assert a == b
    assert a.startswith("sglb_07_")


def test_assign_split_balance():
    splits = [builder._assign_split(i) for i in range(100)]
    assert splits.count("train") == 80
    assert splits.count("dev") == 10
    assert splits.count("test") == 10


def _row(**overrides):
    base = {
        "case_id": "case-1",
        "citation": "[2018] SGCA 14",
        "court_code": "SGCA",
        "decision_date": "2018-04-10",
        "source_url": "http://www.commonlii.org/sg/cases/SGCA/2018/14.html",
        "question": "Whether the doctrine of laches applies in equity claims at common law in Singapore.",
        "jurisdiction_statements": [
            {"label": "uk_persuasive", "quote": "Applying the principle in Donoghue v Stevenson", "paragraph": 14}
        ],
    }
    base.update(overrides)
    return base


def test_build_emits_case_from_single_source_statement(tmp_path: Path):
    jsonl = tmp_path / "cases.jsonl"
    jsonl.write_text(json.dumps(_row()), encoding="utf-8")
    cases = builder.build(jsonl)
    assert len(cases) == 1
    payload = cases[0].as_dict()
    assert payload["expected_output"]["labels"] == ["uk_persuasive"]
    assert payload["metadata"]["dataset_version"] == builder.DATASET_VERSION
    assert payload["metadata"]["label_provenance"].startswith("mechanical-extraction")


def test_build_drops_rows_with_multi_source_statements(tmp_path: Path):
    jsonl = tmp_path / "cases.jsonl"
    row = _row(
        jurisdiction_statements=[
            {"label": "uk_persuasive", "quote": "x", "paragraph": 1},
            {"label": "au_persuasive", "quote": "y", "paragraph": 2},
        ]
    )
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_build_drops_rows_with_unknown_label(tmp_path: Path):
    jsonl = tmp_path / "cases.jsonl"
    row = _row(jurisdiction_statements=[{"label": "made-up", "quote": "x", "paragraph": 1}])
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_build_drops_short_questions(tmp_path: Path):
    jsonl = tmp_path / "cases.jsonl"
    row = _row(question="short")
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_build_drops_non_sg_citation(tmp_path: Path):
    jsonl = tmp_path / "cases.jsonl"
    row = _row(citation="[2018] UKSC 5")
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_build_accepts_catchwords_fallback(tmp_path: Path):
    jsonl = tmp_path / "cases.jsonl"
    row = _row(
        question="",
        catchwords="Equity — laches — claim by long-dormant party — application of doctrine in SG common-law.",
    )
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    cases = builder.build(jsonl)
    assert len(cases) == 1
    assert "laches" in cases[0].question.lower()


# --- task + scorer integration ---


def test_sglb_07_task_registered():
    assert "sglb_07" in TASKS


def test_sglb_07_prompt_builder_registered():
    assert "sglb_07" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_07"]
    assert version == SGLB_07_PROMPT_VERSION
    msgs = fn(_make_case("sg_binding"))
    assert msgs[0]["role"] == "system"
    # System prompt must enumerate the closed taxonomy.
    for label in builder.VALID_LABELS:
        assert label in msgs[0]["content"]


def test_oracle_runner_scores_perfectly_for_each_label():
    for label in builder.VALID_LABELS:
        case = _make_case(label)
        out = asyncio.run(TASKS["sglb_07"](case))
        score = asyncio.run(EVALUATORS["multi_label_f1"].evaluate(_ctx(case, out)))
        assert score.score == pytest.approx(1.0), f"oracle failed for {label}"


def test_oracle_runner_returns_json_list_with_gold_label():
    case = _make_case("au_persuasive")
    out = asyncio.run(TASKS["sglb_07"](case))
    assert json.loads(out) == ["au_persuasive"]
