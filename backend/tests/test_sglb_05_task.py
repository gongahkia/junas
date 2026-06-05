"""SGLB-05 Employment-Issue task runner + builder."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from benchmark.dataset_builders import sglb_05 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_05_PROMPT_VERSION
from benchmark.registry import TASKS
from benchmark.schema import Case


def _make_case(*, labels: list[str]) -> Case:
    return Case(
        name="t",
        inputs={"scenario": "Employee X was dismissed without notice."},
        expected_output={"labels": labels},
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


def test_normalise_issue_snakecases():
    assert builder._normalise_issue("Notice Period Breach") == "notice_period_breach"
    assert builder._normalise_issue("CPF non-contribution") == "cpf_non_contribution"
    assert builder._normalise_issue("  Overtime  Pay  ") == "overtime_pay"


def test_normalise_issues_deduplicates():
    assert builder._normalise_issues(["Notice Period", "notice period", "Overtime"]) == [
        "notice_period",
        "overtime",
    ]


def test_redact_scenario_masks_amounts():
    text = "MOM imposed a financial penalty of $50,000 against the employer for breach."
    out = builder._redact_scenario(text)
    assert "$50,000" not in out
    assert "MOM imposed" not in out
    assert "[AMOUNT_REDACTED]" in out


def test_redact_scenario_truncates_at_sentence_boundary():
    long_text = ("Acme Pte Ltd employed several workers. " * 100)
    out = builder._redact_scenario(long_text)
    assert len(out) <= builder._MAX_SCENARIO_CHARS + 5


def test_stable_case_id_is_deterministic():
    a = builder._stable_case_id("mom-press-2024-01-15-abc")
    b = builder._stable_case_id("mom-press-2024-01-15-abc")
    assert a == b
    assert a.startswith("sglb_05_")


def test_assign_split_balance():
    splits = [builder._assign_split(i) for i in range(100)]
    assert splits.count("train") == 80
    assert splits.count("dev") == 10
    assert splits.count("test") == 10


def test_build_emits_case_from_minimal_row(tmp_path: Path):
    jsonl = tmp_path / "mom.jsonl"
    row = {
        "doc_id": "mom-press-2024-01-15-abc",
        "subsource": "press_release",
        "title": "Action against Acme",
        "body_plain": (
            "Acme Pte Ltd terminated the employment of Mr X without giving him "
            "the contractually required notice period and failed to make CPF "
            "contributions for three months. The matter was referred to the "
            "Tripartite Alliance for Dispute Management."
        ),
        "stated_breaches": ["Notice Period Breach", "CPF non-contribution"],
        "act_references": ["s 10 of the Employment Act"],
        "subject_organisation": "Acme Pte Ltd",
        "pub_date": "2024-01-15",
        "source_url": "https://www.mom.gov.sg/example",
        "extraction_rule_sha": "abcdef1",
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    cases = builder.build(jsonl)
    assert len(cases) == 1
    payload = cases[0].as_dict()
    assert payload["extraction_rule_sha"] == "abcdef1"
    assert payload["expected_output"]["labels"] == ["notice_period_breach", "cpf_non_contribution"]
    assert payload["metadata"]["dataset_version"] == builder.DATASET_VERSION
    assert payload["metadata"]["label_provenance"].startswith("mechanical-extraction")


def test_build_drops_rows_without_labels(tmp_path: Path):
    jsonl = tmp_path / "mom.jsonl"
    row = {
        "doc_id": "x",
        "body_plain": "X" * 300,
        "stated_breaches": [],
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_build_drops_short_scenarios(tmp_path: Path):
    jsonl = tmp_path / "mom.jsonl"
    row = {
        "doc_id": "x",
        "body_plain": "short",
        "stated_breaches": ["foo"],
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_build_deduplicates_doc_ids(tmp_path: Path):
    jsonl = tmp_path / "mom.jsonl"
    row = {
        "doc_id": "duplicate-id",
        "body_plain": "X" * 300,
        "stated_breaches": ["notice_period_breach"],
        "pub_date": "2024-01-01",
        "extraction_rule_sha": "abcdef1",
    }
    jsonl.write_text("\n".join(json.dumps(row) for _ in range(3)), encoding="utf-8")
    assert len(builder.build(jsonl)) == 1


def test_build_rejects_valid_rows_without_extraction_rule_sha(tmp_path: Path):
    jsonl = tmp_path / "mom.jsonl"
    row = {
        "doc_id": "mom-press-2024-01-15-abc",
        "body_plain": "X" * 300,
        "stated_breaches": ["notice_period_breach"],
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    with pytest.raises(ValueError, match="missing extraction_rule_sha"):
        builder.build(jsonl)


# --- task + scorer integration ---


def test_sglb_05_task_registered():
    assert "sglb_05" in TASKS


def test_sglb_05_prompt_builder_registered():
    assert "sglb_05" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_05"]
    assert version == SGLB_05_PROMPT_VERSION
    msgs = fn(_make_case(labels=["notice_period_breach"]))
    assert msgs[0]["role"] == "system"
    assert "Employment Act" in msgs[0]["content"]
    assert "snake_case" in msgs[0]["content"]
    assert "JSON array" in msgs[0]["content"]


def test_oracle_runner_scores_perfectly():
    case = _make_case(labels=["notice_period_breach", "cpf_non_contribution"])
    out = asyncio.run(TASKS["sglb_05"](case))
    score = asyncio.run(EVALUATORS["multi_label_f1"].evaluate(_ctx(case, out)))
    assert score.score == pytest.approx(1.0)


def test_oracle_runner_returns_empty_list_for_no_labels():
    case = _make_case(labels=[])
    out = asyncio.run(TASKS["sglb_05"](case))
    assert json.loads(out) == []
