from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from benchmark.cli import _build_parser
from benchmark.contamination import build_probe_prompt, probe_status, score_probe_output
from benchmark.llm_runner import MockLLMClient, llm_task_for
from benchmark.registry import PROVENANCE, TASKS, register_task
from benchmark.runner import run
from benchmark.schema import Case


@pytest.fixture(autouse=True)
def isolate_registry():
    saved_tasks = dict(TASKS)
    saved_provenance = dict(PROVENANCE)
    yield
    TASKS.clear()
    TASKS.update(saved_tasks)
    PROVENANCE.clear()
    PROVENANCE.update(saved_provenance)


def _pdpa_case(name: str, fact_summary: str, citation: str, obligations: list[str], band: str) -> Case:
    return Case(
        name=name,
        inputs={"fact_summary": fact_summary},
        expected_output={"obligations": obligations, "penalty_band": band},
        metadata={"task": "SGLB-01", "citation": citation},
    )


def _write_dataset(path: Path, cases: list[Case]) -> None:
    payload = {
        "cases": [
            {
                "name": case.name,
                "inputs": case.inputs,
                "expected_output": case.expected_output,
                "metadata": case.metadata,
            }
            for case in cases
        ]
    }
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def _last_user(messages: list[dict[str, str]]) -> str:
    return next(
        message["content"]
        for message in reversed(messages)
        if message.get("role") == "user"
    )


def test_probe_prompt_builders_do_not_include_task_inputs():
    pdpa = _pdpa_case(
        "sglb_01_a",
        "SECRET FACT SUMMARY",
        "[2016] SGPDPC 9",
        ["protection"],
        "none",
    )
    pdpa_user = _last_user(build_probe_prompt("sglb_01", pdpa))
    assert "SECRET FACT SUMMARY" not in pdpa_user
    assert "[2016] SGPDPC 9" in pdpa_user

    statute = Case(
        name="sglb_02_a",
        inputs={
            "question": "SECRET QUESTION",
            "act_full_name": "Personal Data Protection Act 2012",
        },
        expected_output={"answer_span": "An organisation must not collect personal data."},
        metadata={"section_number": "13"},
    )
    statute_user = _last_user(build_probe_prompt("sglb_02", statute))
    assert "SECRET QUESTION" not in statute_user
    assert "Personal Data Protection Act 2012 section 13" in statute_user

    clause = Case(
        name="sglb_08_a",
        inputs={"clause_text": "SECRET CLAUSE TEXT"},
        expected_output={"labels": ["aggressive"]},
        metadata={"taxonomy_cell": {"params": {"clause_id": "confidentiality-sg"}}},
    )
    clause_user = _last_user(build_probe_prompt("sglb_08", clause))
    assert "SECRET CLAUSE TEXT" not in clause_user
    assert "confidentiality-sg" in clause_user


def test_probe_scorers_assign_memorisation_scores():
    pdpa = _pdpa_case("sglb_01_a", "facts", "[2016] SGPDPC 9", ["protection"], "none")
    assert score_probe_output(
        "sglb_01",
        pdpa,
        json.dumps({"obligations": ["protection"], "penalty_band": "none"}),
    ) == pytest.approx(1.0)
    assert score_probe_output("sglb_01", pdpa, "unknown") == pytest.approx(0.0)

    statute = Case(
        name="sglb_02_a",
        expected_output={"answer_span": "An organisation must protect personal data."},
    )
    assert score_probe_output(
        "sglb_02",
        statute,
        "An organisation must protect personal data.",
    ) == pytest.approx(1.0)
    assert score_probe_output("sglb_02", statute, "unrelated words") == pytest.approx(0.0)

    clause = Case(name="sglb_08_a", expected_output={"labels": ["balanced"]})
    assert score_probe_output("sglb_08", clause, '["balanced"]') == pytest.approx(1.0)
    assert score_probe_output("sglb_08", clause, '["protective"]') == pytest.approx(0.0)


def test_runner_attaches_contamination_summary_and_per_case_scores(tmp_path: Path):
    case_a = _pdpa_case("sglb_01_a", "facts a", "[2016] SGPDPC 9", ["protection"], "none")
    case_b = _pdpa_case("sglb_01_b", "facts b", "[2016] SGPDPC 10", ["accountability"], "mid")
    dataset_path = tmp_path / "sglb_01.yaml"
    _write_dataset(dataset_path, [case_a, case_b])

    canned = {
        "facts a": json.dumps({"obligations": ["accountability"], "penalty_band": "high"}),
        "facts b": json.dumps({"obligations": ["accountability"], "penalty_band": "mid"}),
        _last_user(build_probe_prompt("sglb_01_llm_probe_test", case_a)): json.dumps(
            {"obligations": ["protection"], "penalty_band": "none"}
        ),
        _last_user(build_probe_prompt("sglb_01_llm_probe_test", case_b)): "unknown",
    }
    client = MockLLMClient(canned=canned)
    runner = llm_task_for(
        workflow="sglb_01",
        client=client,
        provider_label="mock:contamination",
        sample_case=case_a,
    )
    register_task("sglb_01_llm_probe_test", runner, provenance=runner.provenance)  # type: ignore[attr-defined]

    summary = asyncio.run(
        run(
            workflow="sglb_01_llm_probe_test",
            dataset_path=dataset_path,
            evaluators=["sglb_01_obligations_f1"],
            max_concurrency=2,
            contamination_probe=True,
        )
    )

    assert client.calls == 4
    assert summary.per_evaluator_mean()["sglb_01_obligations_f1"] == pytest.approx(0.5)
    assert summary.contamination_summary["mean_memorisation_rate"] == pytest.approx(0.5)
    assert summary.contamination_summary["contamination_adjusted_score"][
        "sglb_01_obligations_f1"
    ] == pytest.approx(1.0)

    by_case = {result.case_name: result.metadata for result in summary.results}
    assert by_case["sglb_01_a"]["memorisation_score"] == pytest.approx(1.0)
    assert by_case["sglb_01_a"]["memorisation_flag"] is True
    assert by_case["sglb_01_b"]["memorisation_score"] == pytest.approx(0.0)
    assert by_case["sglb_01_b"]["memorisation_flag"] is False

    payload = summary.to_dict()
    assert payload["contamination_summary"]["status"] == "completed"
    assert "memorisation_score" in payload["results"][0]["metadata"]


def test_sglb_04_probe_is_skipped_without_extra_llm_call(tmp_path: Path):
    case = Case(
        name="citation_case",
        inputs={"citation": "[2023] SGCA 5"},
        expected_output={"labels": ["valid"]},
    )
    dataset_path = tmp_path / "sglb_04.yaml"
    _write_dataset(dataset_path, [case])

    client = MockLLMClient(default_response='["valid"]')
    runner = llm_task_for(workflow="sglb_04", client=client)
    register_task("sglb_04_llm_probe_test", runner)
    summary = asyncio.run(
        run(
            workflow="sglb_04_llm_probe_test",
            dataset_path=dataset_path,
            evaluators=["multi_label_f1"],
            contamination_probe=True,
        )
    )

    assert client.calls == 1
    assert probe_status("sglb_04")[0] is False
    assert summary.contamination_summary["status"] == "skipped"
    assert summary.contamination_summary["mean_memorisation_rate"] == 0.0
    assert summary.results[0].metadata["memorisation_probe_skipped"] is True


def test_cli_accepts_contamination_probe_flag():
    parser = _build_parser()
    args = parser.parse_args(
        [
            "run",
            "--workflow",
            "sglb_01",
            "--dataset",
            "dataset.yaml",
            "--evaluator",
            "sglb_01_obligations_f1",
            "--contamination-probe",
        ]
    )
    assert args.contamination_probe is True
