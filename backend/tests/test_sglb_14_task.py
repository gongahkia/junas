"""SGLB-14 Statutory-Entailment builder + task + scorer."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from benchmark.dataset_builders import sglb_14 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_14_PROMPT_VERSION
from benchmark.registry import TASKS, is_benchmark_eligible
from benchmark.runner import run
from benchmark.schema import Case


def _guideline_row() -> dict:
    return {
        "doc_id": "pdpc_guideline_fixture",
        "source_url": "https://www.pdpc.gov.sg/guidelines",
        "title": "Advisory Guidelines on Key Concepts in the PDPA",
        "pdf_url": "https://www.pdpc.gov.sg/key-concepts.pdf",
        "pub_date": "2026-01-02",
        "section_headings": ["Chapter 12: Consent Obligation"],
        "body_plain": """
Example 1: Organisation A sends a marketing SMS to a Singapore telephone number listed on the Do Not Call Register without checking the DNC Registry. Organisation A would be in breach of section 43 of the PDPA.

Example 2: Organisation B obtains clear and unambiguous consent in evidential form before sending the marketing message. Organisation B would not be in breach of section 43 of the PDPA.

Example 3: Organisation C has an ambiguous record of consent and the facts do not state whether consent was clear. Whether Organisation C would be in breach of section 43 of the PDPA would depend on whether the consent was clear and unambiguous.

Example 4: This example mentions section 44 of the PDPA but does not state any outcome.
""",
    }


def _write_jsonl(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "guidelines.jsonl"
    path.write_text("\n".join(json.dumps(row) for row in rows) + "\n", encoding="utf-8")
    return path


def _case(label: str) -> Case:
    return Case(
        name="t",
        inputs={
            "statute_section": "s 43 of the PDPA",
            "conduct": "Organisation A sends a marketing SMS without checking the DNC Registry.",
        },
        expected_output={"entailment": label},
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


def test_split_examples_extracts_only_marked_examples():
    examples = builder._split_examples(_guideline_row()["body_plain"])
    assert len(examples) == 4
    assert examples[0].startswith("Example 1")


def test_split_examples_handles_pdpc_inline_paragraph_markers():
    body = (
        "17.3 Background paragraph. "
        "17.4 Example: XYZ sends a specified SMS without checking the DNC Register. "
        "XYZ would be i n breach of section 43(1) of the PDPA. "
        "17.5 Consent evidenced in written or other form. "
        "Example 2 Clinic ABC sends an in-service message."
    )
    examples = builder._split_examples(body)
    assert len(examples) == 2
    assert examples[0].startswith("Example:")
    assert examples[1].startswith("Example 2")


@pytest.mark.parametrize(
    ("example", "label", "section"),
    [
        (
            "Example 1: X sends a specified message. X would be in breach of section 43 of the PDPA.",
            "contravenes",
            "s 43 of the PDPA",
        ),
        (
            "Example 2: X has clear consent. X would not be in breach of section 43 of the PDPA.",
            "complies",
            "s 43 of the PDPA",
        ),
        (
            "Example 3: Whether X would be in breach of section 43 of the PDPA would depend on the consent facts.",
            "indeterminate",
            "s 43 of the PDPA",
        ),
        (
            "17.4 Example: X sends a specified message without checking the DNC Register. "
            "X would be i n breach of section 43(1) of the PDPA.",
            "contravenes",
            "s 43(1) of the PDPA",
        ),
        (
            "Example: X fails to implement reasonable security measures and is hence committing a breach of "
            "section 24 of the PDPA.",
            "contravenes",
            "s 24 of the PDPA",
        ),
    ],
)
def test_label_match_recognises_explicit_regulator_phrases(example: str, label: str, section: str):
    got_label, got_section, match = builder._label_match(example)
    assert match is not None
    assert got_label == label
    assert got_section == section


def test_label_match_rejects_section_mentions_without_outcome():
    label, section, match = builder._label_match(
        "Example 4: The facts refer to section 44 of the PDPA but do not state an outcome."
    )
    assert (label, section, match) == ("", "", None)


def test_extract_cases_from_row_emits_only_mechanical_labels():
    cases, excluded = builder.extract_cases_from_row(_guideline_row(), "abcdef1")
    assert len(cases) == 3
    assert {case.entailment for case in cases} == {"contravenes", "complies", "indeterminate"}
    assert cases[0].statute_section == "s 43 of the PDPA"
    assert "would be in breach" not in cases[0].conduct.lower()
    assert excluded == [("pdpc_guideline_fixture:3", "no explicit entailment phrase")]


def test_build_and_write_outputs(tmp_path: Path):
    source = _write_jsonl(tmp_path, [_guideline_row()])
    cases, stats = builder.build(source, "abcdef1")
    assert stats.source_rows == 1
    assert stats.emitted == 3
    assert stats.by_label == {"contravenes": 1, "complies": 1, "indeterminate": 1}

    yaml_path = tmp_path / "sglb_14.yaml"
    split_dir = tmp_path / "splits"
    counts = builder.write_outputs(cases, "abcdef1", yaml_path, split_dir)
    assert sum(counts.values()) == 3
    payload = yaml.safe_load(yaml_path.read_text(encoding="utf-8"))
    assert payload["extraction_rules"] == {builder.EXTRACTION_RULE_NAME: "abcdef1"}
    assert payload["cases"][0]["extraction_rule_sha"] == "abcdef1"
    assert payload["cases"][0]["metadata"]["label_provenance"].startswith("mechanical-extraction")


def test_sglb_14_task_registered_ineligible_until_dataset_lands():
    assert "sglb_14" in TASKS
    assert is_benchmark_eligible("sglb_14") is False


def test_sglb_14_evaluator_registered_strong():
    assert EVALUATORS["sglb_14_entailment_accuracy"].strength == EvaluatorStrength.STRONG


def test_sglb_14_evaluator_scores_json_and_bare_label():
    case = _case("contravenes")
    assert asyncio.run(
        EVALUATORS["sglb_14_entailment_accuracy"].evaluate(
            _ctx(case, json.dumps({"entailment": "contravenes"}))
        )
    ).score == 1.0
    assert asyncio.run(
        EVALUATORS["sglb_14_entailment_accuracy"].evaluate(_ctx(case, "complies"))
    ).score == 0.0


def test_sglb_14_prompt_builder_registered():
    assert "sglb_14" in PROMPT_BUILDERS
    fn, version = PROMPT_BUILDERS["sglb_14"]
    assert version == SGLB_14_PROMPT_VERSION
    messages = fn(_case("complies"))
    assert "contravenes" in messages[0]["content"]
    assert "s 43 of the PDPA" in messages[1]["content"]


def test_sglb_14_harness_oracle_scores_one(tmp_path: Path):
    cases, _ = builder.build(_write_jsonl(tmp_path, [_guideline_row()]), "abcdef1")
    yaml_path = tmp_path / "sglb_14.yaml"
    builder.write_outputs(cases, "abcdef1", yaml_path, tmp_path / "splits")
    summary = asyncio.run(
        run(
            workflow="sglb_14",
            dataset_path=yaml_path,
            evaluators=["sglb_14_entailment_accuracy"],
            strict=True,
        )
    )
    assert summary.total_cases == 3
    assert summary.per_evaluator_mean()["sglb_14_entailment_accuracy"] == 1.0
