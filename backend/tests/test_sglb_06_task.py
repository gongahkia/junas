"""SGLB-06 ROC-2021 task runner + scorers + dataset builder."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from benchmark.dataset_builders import sglb_06 as builder
from benchmark.evaluators import (
    EVALUATORS,
    EvaluatorContext,
    EvaluatorStrength,
    _normalise_order_rule,
)
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_06_PROMPT_VERSION
from benchmark.registry import TASKS
from benchmark.schema import Case


def _make_case(*, labels: list[str]) -> Case:
    return Case(
        name="t",
        inputs={"scenario": "A party wishes to commence proceedings by writ."},
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


# --- normalisation unit ---


def test_normalise_canonical_form_passes_through():
    assert _normalise_order_rule("O. 9, r. 1") == "O. 9, r. 1"


def test_normalise_handles_long_form():
    assert _normalise_order_rule("Order 9, Rule 1") == "O. 9, r. 1"


def test_normalise_handles_no_punctuation():
    assert _normalise_order_rule("O 9 r 1") == "O. 9, r. 1"


def test_normalise_handles_dotted_no_space():
    assert _normalise_order_rule("O.9, r.1") == "O. 9, r. 1"


def test_normalise_empty_returns_empty():
    assert _normalise_order_rule("") == ""


def test_normalise_garbage_returns_empty():
    assert _normalise_order_rule("not a rule reference") == ""


def test_normalise_handles_alpha_suffix():
    assert _normalise_order_rule("O 8A, r 2B") == "O. 8A, r. 2B"


# --- evaluators ---


def test_order_rule_label_f1_perfect_match():
    case = _make_case(labels=["O. 9, r. 1"])
    out = json.dumps(["O. 9, r. 1"])
    r = asyncio.run(EVALUATORS["order_rule_label_f1"].evaluate(_ctx(case, out)))
    assert r.score == pytest.approx(1.0)


def test_order_rule_label_f1_normalises_surface_variant():
    case = _make_case(labels=["O. 9, r. 1"])
    out = json.dumps(["Order 9, Rule 1"])
    r = asyncio.run(EVALUATORS["order_rule_label_f1"].evaluate(_ctx(case, out)))
    assert r.score == pytest.approx(1.0)


def test_order_rule_label_f1_partial():
    case = _make_case(labels=["O. 9, r. 1", "O. 6, r. 3"])
    out = json.dumps(["O. 9, r. 1"])
    r = asyncio.run(EVALUATORS["order_rule_label_f1"].evaluate(_ctx(case, out)))
    # p=1.0, r=0.5, f1 = 2/3
    assert r.score == pytest.approx(2 / 3)


def test_order_rule_label_f1_handles_malformed_json():
    case = _make_case(labels=["O. 9, r. 1"])
    r = asyncio.run(EVALUATORS["order_rule_label_f1"].evaluate(_ctx(case, "not-json")))
    assert r.score == 0.0


def test_order_rule_top3_hit_in_first_three():
    case = _make_case(labels=["O. 9, r. 1"])
    out = json.dumps(["O. 10, r. 2", "O. 9, r. 1", "O. 5, r. 1"])
    r = asyncio.run(EVALUATORS["order_rule_top3"].evaluate(_ctx(case, out)))
    assert r.score == pytest.approx(1.0)


def test_order_rule_top3_miss_outside_first_three():
    case = _make_case(labels=["O. 9, r. 1"])
    out = json.dumps(["O. 1, r. 1", "O. 2, r. 1", "O. 3, r. 1", "O. 9, r. 1"])
    r = asyncio.run(EVALUATORS["order_rule_top3"].evaluate(_ctx(case, out)))
    assert r.score == 0.0


def test_order_rule_top3_multi_gold_partial():
    case = _make_case(labels=["O. 9, r. 1", "O. 6, r. 3"])
    out = json.dumps(["O. 9, r. 1", "O. 5, r. 1", "O. 1, r. 2"])
    r = asyncio.run(EVALUATORS["order_rule_top3"].evaluate(_ctx(case, out)))
    assert r.score == pytest.approx(0.5)


# --- builder unit ---


def test_order_from_part_extracts_number():
    assert builder._order_from_part("Order 9 PRE-ACTION PROTOCOLS") == "9"
    assert builder._order_from_part("Order 8A INTERIM RELIEF") == "8A"
    assert builder._order_from_part("not an order header") == ""


def test_normalise_label_canonical():
    assert builder._normalise_label("9", "1") == "O. 9, r. 1"


def test_stable_case_id_is_deterministic():
    a = builder._stable_case_id("ROC2021@2021-12-31", "9", "1")
    b = builder._stable_case_id("ROC2021@2021-12-31", "9", "1")
    assert a == b
    assert a.startswith("sglb_06_")


def test_assign_split_balance():
    splits = [builder._assign_split(i) for i in range(100)]
    assert splits.count("train") == 80
    assert splits.count("dev") == 10
    assert splits.count("test") == 10


def test_builder_filters_non_roc2021_rows(tmp_path: Path):
    """The builder must ignore non-ROC2021 chapter rows so it can share
    the SSO JSONL with SGLB-02."""
    jsonl = tmp_path / "statutes.jsonl"
    rows = [
        # PDPA row should be filtered out
        {
            "chapter_number": "PDPA2012",
            "name": "Functions of Commission",
            "number": "6",
            "part": "Part 2 ADMINISTRATION",
            "text_plain": "6. The functions of the Commission are ..."
            + (" content " * 30),
            "source_url": "https://x/pdpa#pr6-",
            "version_id": "PDPA2012@2020",
            "valid_start_date": "2021-12-31",
        },
        # ROC2021 row should land
        {
            "chapter_number": "ROC2021",
            "name": "Commencement of action",
            "number": "1",
            "part": "Order 9 PRE-ACTION PROTOCOLS AND ORIGINATING PROCESSES",
            "text_plain": "1. Subject to this Order, every action in the General Division must be commenced by an originating claim. The originating claim must comply with Form 7 of the Forms.",
            "source_url": "https://x/roc#pr1-",
            "version_id": "ROC2021@2021-12-31",
            "valid_start_date": "2021-12-31",
        },
    ]
    jsonl.write_text("\n".join(json.dumps(r) for r in rows), encoding="utf-8")
    cases = builder.build(jsonl)
    assert len(cases) == 1
    assert cases[0].label == "O. 9, r. 1"
    payload = cases[0].as_dict()
    assert payload["metadata"]["order"] == "9"
    assert payload["metadata"]["rule"] == "1"
    assert payload["metadata"]["dataset_version"] == builder.DATASET_VERSION
    assert payload["extraction_rule_sha"]
    assert len(payload["extraction_rule_sha"]) == 7


def test_write_outputs_includes_extraction_rules(tmp_path: Path):
    jsonl = tmp_path / "statutes.jsonl"
    row = {
        "chapter_number": "ROC2021",
        "name": "Commencement of action",
        "number": "1",
        "part": "Order 9 PRE-ACTION PROTOCOLS AND ORIGINATING PROCESSES",
        "text_plain": "1. Subject to this Order, every action in the General Division must be commenced by an originating claim. The originating claim must comply with Form 7 of the Forms.",
        "source_url": "https://x/roc#pr1-",
        "version_id": "ROC2021@2021-12-31",
        "valid_start_date": "2021-12-31",
        "extraction_rule_sha": "abcdef1",
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    cases = builder.build(jsonl)
    yaml_path = tmp_path / "sglb_06.yaml"
    out_dir = tmp_path / "splits"
    builder.write_outputs(cases, yaml_path, out_dir)
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert payload["extraction_rules"] == {"sso": "abcdef1"}
    assert payload["cases"][0]["extraction_rule_sha"] == "abcdef1"


def test_builder_drops_rows_without_order_header(tmp_path: Path):
    jsonl = tmp_path / "statutes.jsonl"
    row = {
        "chapter_number": "ROC2021",
        "name": "Some Rule",
        "number": "5",
        "part": "Part A INTRODUCTION",  # no "Order N"
        "text_plain": "5. " + ("content " * 40),
        "source_url": "x",
        "version_id": "ROC2021@2021-12-31",
        "valid_start_date": "2021-12-31",
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_builder_drops_repealed(tmp_path: Path):
    jsonl = tmp_path / "statutes.jsonl"
    row = {
        "chapter_number": "ROC2021",
        "name": "[Repealed]",
        "number": "5",
        "part": "Order 9 PRE-ACTION",
        "text_plain": "5. " + ("content " * 40),
        "source_url": "x",
        "version_id": "ROC2021@2021-12-31",
        "valid_start_date": "2021-12-31",
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


def test_builder_drops_short_scenarios(tmp_path: Path):
    jsonl = tmp_path / "statutes.jsonl"
    row = {
        "chapter_number": "ROC2021",
        "name": "Brief",
        "number": "5",
        "part": "Order 9 PRE-ACTION",
        "text_plain": "5. short",
        "source_url": "x",
        "version_id": "ROC2021@2021-12-31",
        "valid_start_date": "2021-12-31",
    }
    jsonl.write_text(json.dumps(row), encoding="utf-8")
    assert builder.build(jsonl) == []


# --- task registration ---


def test_sglb_06_task_registered():
    assert "sglb_06" in TASKS


def test_sglb_06_prompt_builder_registered():
    assert "sglb_06" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_06"]
    assert version == SGLB_06_PROMPT_VERSION
    msgs = fn(_make_case(labels=["O. 9, r. 1"]))
    assert msgs[0]["role"] == "system"
    assert "Rules of Court 2021" in msgs[0]["content"]
    assert "JSON array" in msgs[0]["content"]
    assert "originating proceedings" not in msgs[-1]["content"]  # sanity
    assert msgs[-1]["content"].startswith("A party wishes to commence")


def test_oracle_runner_scores_perfectly():
    case = _make_case(labels=["O. 9, r. 1"])
    out = asyncio.run(TASKS["sglb_06"](case))
    f1 = asyncio.run(EVALUATORS["order_rule_label_f1"].evaluate(_ctx(case, out)))
    top3 = asyncio.run(EVALUATORS["order_rule_top3"].evaluate(_ctx(case, out)))
    assert f1.score == pytest.approx(1.0)
    assert top3.score == pytest.approx(1.0)


def test_sglb_06_evaluators_registered_strong():
    assert EVALUATORS["order_rule_label_f1"].strength == EvaluatorStrength.STRONG
    assert EVALUATORS["order_rule_top3"].strength == EvaluatorStrength.STRONG
