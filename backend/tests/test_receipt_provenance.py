"""Receipt provenance (#72) — coverage matrix §4.4.

Every JSON receipt for a workflow with a registered provenance record
must carry: prompt_version, prompt_sha, provider_label, max_tokens.
"""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest

from benchmark.llm_runner import MockLLMClient, llm_task_for, register_llm_task
from benchmark.registry import (
    PROVENANCE,
    TASKS,
    get_provenance,
    register_provenance,
    register_task,
)
from benchmark.runner import run, write_summary
from benchmark.schema import Case


@pytest.fixture(autouse=True)
def isolate_registry():
    """Snapshot + restore registry state so cross-test pollution doesn't
    leak provenance entries."""
    saved_provenance = dict(PROVENANCE)
    saved_tasks = dict(TASKS)
    yield
    PROVENANCE.clear()
    PROVENANCE.update(saved_provenance)
    # Restore any newly-added task names (only remove the keys we added).
    for k in set(TASKS) - set(saved_tasks):
        TASKS.pop(k, None)


def test_get_provenance_empty_when_unregistered():
    assert get_provenance("does-not-exist") == {}


def test_register_task_with_provenance_attaches():
    async def runner(case: Case) -> str:
        return ""

    register_task(
        "test-task-with-prov",
        runner,
        provenance={"prompt_version": "v1", "max_tokens": 64},
    )
    got = get_provenance("test-task-with-prov")
    assert got["prompt_version"] == "v1"
    assert got["max_tokens"] == 64


def test_register_task_without_provenance_clears_old():
    async def r(case: Case) -> str:
        return ""

    register_task("t1", r, provenance={"prompt_version": "v1"})
    assert get_provenance("t1") == {"prompt_version": "v1"}
    register_task("t1", r)  # re-register without provenance
    assert get_provenance("t1") == {}


def test_register_provenance_sets_independently():
    async def r(case: Case) -> str:
        return ""

    register_task("t2", r)
    register_provenance("t2", {"prompt_version": "vX", "provider_label": "mock:x"})
    got = get_provenance("t2")
    assert got["prompt_version"] == "vX"
    assert got["provider_label"] == "mock:x"


def test_llm_task_for_attaches_provenance_to_runner():
    client = MockLLMClient(default_response='["valid"]')
    case = Case(name="sample", inputs={"citation": "[2023] SGCA 5"}, expected_output=None, metadata={})
    runner = llm_task_for(
        workflow="sglb_04",
        client=client,
        provider_label="mock:smoke",
        sample_case=case,
    )
    prov = runner.provenance  # type: ignore[attr-defined]
    assert prov["prompt_version"] == "sglb-04-v1"
    assert prov["provider_label"] == "mock:smoke"
    assert prov["max_tokens"] == 512
    assert len(prov["prompt_sha"]) == 16


def test_register_llm_task_attaches_provenance_to_registry():
    client = MockLLMClient(default_response='["valid"]')
    sample = Case(name="s", inputs={"citation": "[2023] SGCA 5"}, expected_output=None, metadata={})
    register_llm_task(
        name="sglb_04_llm_mock_prov",
        workflow="sglb_04",
        client=client,
        provider_label="mock:smoke",
        sample_case=sample,
    )
    prov = get_provenance("sglb_04_llm_mock_prov")
    assert prov["prompt_version"] == "sglb-04-v1"
    assert prov["provider_label"] == "mock:smoke"
    assert prov["prompt_sha"]
    assert prov["max_tokens"] == 512


def test_run_summary_carries_provenance_through_receipt(tmp_path: Path):
    client = MockLLMClient(default_response='["valid"]')
    sample = Case(name="s", inputs={"citation": "[2023] SGCA 5"}, expected_output=None, metadata={})
    register_llm_task(
        name="sglb_04_llm_receipt_test",
        workflow="sglb_04",
        client=client,
        provider_label="mock:receipt",
        sample_case=sample,
    )
    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml"
    summary = asyncio.run(
        run(
            workflow="sglb_04_llm_receipt_test",
            dataset_path=smoke,
            evaluators=["multi_label_f1"],
            max_concurrency=4,
        )
    )
    payload = summary.to_dict()
    assert payload["provenance"]["prompt_version"] == "sglb-04-v1"
    assert payload["provenance"]["provider_label"] == "mock:receipt"
    assert payload["provenance"]["prompt_sha"]
    assert payload["provenance"]["max_tokens"] == 512

    receipt = tmp_path / "receipt.json"
    write_summary(summary, receipt)
    on_disk = json.loads(receipt.read_text(encoding="utf-8"))
    assert on_disk["provenance"]["prompt_version"] == "sglb-04-v1"
    assert on_disk["provenance"]["provider_label"] == "mock:receipt"


def test_oracle_workflow_has_empty_provenance():
    """Oracle runners (sglb_01, sglb_02, ...) register without
    provenance — their receipts should record an empty provenance dict
    to clearly distinguish them from LLM-backed runs."""
    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml"
    summary = asyncio.run(
        run(
            workflow="sglb_04",
            dataset_path=smoke,
            evaluators=["multi_label_f1"],
            max_concurrency=4,
        )
    )
    assert summary.provenance == {}
    assert "provenance" in summary.to_dict()
    assert summary.to_dict()["provenance"] == {}


def test_runner_falls_back_to_attribute_when_registry_unset():
    """A runner that has ``.provenance`` set but was registered without
    explicit provenance argument should still surface its provenance."""
    client = MockLLMClient(default_response='["valid"]')
    sample = Case(name="s", inputs={"citation": "[2023] SGCA 5"}, expected_output=None, metadata={})
    runner = llm_task_for(
        workflow="sglb_04",
        client=client,
        provider_label="mock:attr-fallback",
        sample_case=sample,
    )
    # Bypass register_llm_task — register the bare runner.
    register_task("sglb_04_attr_fallback", runner)
    assert get_provenance("sglb_04_attr_fallback") == {}
    smoke = Path(__file__).parent.parent / "benchmark" / "datasets" / "sglb_04_citation_verify.yaml"
    summary = asyncio.run(
        run(
            workflow="sglb_04_attr_fallback",
            dataset_path=smoke,
            evaluators=["multi_label_f1"],
        )
    )
    assert summary.provenance["provider_label"] == "mock:attr-fallback"
    assert summary.provenance["prompt_version"] == "sglb-04-v1"
