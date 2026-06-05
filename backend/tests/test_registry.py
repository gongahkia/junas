from __future__ import annotations

import pytest

from benchmark.registry import (
    BENCHMARK_ELIGIBILITY,
    PROVENANCE,
    TASKS,
    is_benchmark_eligible,
    register_task,
)
from benchmark.schema import Case


@pytest.fixture(autouse=True)
def isolate_registry():
    saved_tasks = dict(TASKS)
    saved_provenance = dict(PROVENANCE)
    saved_eligibility = dict(BENCHMARK_ELIGIBILITY)
    yield
    TASKS.clear()
    TASKS.update(saved_tasks)
    PROVENANCE.clear()
    PROVENANCE.update(saved_provenance)
    BENCHMARK_ELIGIBILITY.clear()
    BENCHMARK_ELIGIBILITY.update(saved_eligibility)


async def _runner(case: Case) -> str:
    return str(case.inputs.get("query", ""))


def test_register_task_defaults_benchmark_eligible():
    register_task("unit_default", _runner)
    assert is_benchmark_eligible("unit_default") is True


def test_register_task_marks_ineligible_and_canonical_derivatives_follow():
    register_task("sglb_99", _runner, benchmark_eligible=False)
    assert is_benchmark_eligible("sglb_99") is False
    assert is_benchmark_eligible("sglb_99_llm_mock") is False
    assert is_benchmark_eligible("/tmp/sglb-99/receipt.json") is False


def test_reregister_without_flag_restores_default_eligibility():
    register_task("sglb_99", _runner, benchmark_eligible=False)
    register_task("sglb_99", _runner)
    assert is_benchmark_eligible("sglb_99") is True
    assert is_benchmark_eligible("sglb_99_llm_mock") is True


def test_sglb_05_06_07_ship_ineligible_until_data_lands():
    assert is_benchmark_eligible("sglb_05") is False
    assert is_benchmark_eligible("sglb_06") is False
    assert is_benchmark_eligible("sglb_07") is False
    assert is_benchmark_eligible("sglb_08") is True
