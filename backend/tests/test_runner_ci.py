from __future__ import annotations

import json
from pathlib import Path

import pytest

from benchmark.cli import main as cli_main
from benchmark.registry import PROVENANCE, TASKS, register_task
from benchmark.schema import Case
from benchmark.stats import bootstrap_ci


@pytest.fixture(autouse=True)
def isolate_registry():
    saved_tasks = dict(TASKS)
    saved_provenance = dict(PROVENANCE)
    yield
    TASKS.clear()
    TASKS.update(saved_tasks)
    PROVENANCE.clear()
    PROVENANCE.update(saved_provenance)


def _dataset(path: Path) -> None:
    path.write_text(
        "cases:\n"
        "  - name: c1\n"
        "    inputs:\n"
        "      prediction: ok\n"
        "    expected_output:\n"
        "      span: ok\n"
        "      contains: [ok]\n"
        "  - name: c2\n"
        "    inputs:\n"
        "      prediction: bad\n"
        "    expected_output:\n"
        "      span: ok\n"
        "      contains: [ok]\n"
        "  - name: c3\n"
        "    inputs:\n"
        "      prediction: ok\n"
        "    expected_output:\n"
        "      span: ok\n"
        "      contains: [ok]\n"
        "  - name: c4\n"
        "    inputs:\n"
        "      prediction: ok extra\n"
        "    expected_output:\n"
        "      span: ok\n"
        "      contains: [ok]\n",
        encoding="utf-8",
    )


def _register_mock_task() -> None:
    async def mock_task(case: Case) -> str:
        return str(case.inputs.get("prediction", ""))

    register_task("ci_receipt_mock", mock_task)


def _run_cli(dataset: Path, output: Path) -> dict:
    rc = cli_main(
        [
            "run",
            "--workflow",
            "ci_receipt_mock",
            "--dataset",
            str(dataset),
            "--evaluator",
            "exact_match",
            "--evaluator",
            "contains",
            "--output",
            str(output),
        ]
    )
    assert rc == 0
    return json.loads(output.read_text(encoding="utf-8"))


def test_cli_receipt_contains_per_evaluator_ci_fields(tmp_path: Path):
    _register_mock_task()
    dataset = tmp_path / "dataset.yaml"
    _dataset(dataset)

    payload = _run_cli(dataset, tmp_path / "receipt.json")

    assert payload["per_evaluator_mean"] == {
        "exact_match": 0.5,
        "contains": 0.75,
    }
    stats = payload["per_evaluator_bootstrap"]
    assert set(stats) == {"exact_match", "contains"}
    for evaluator in ("exact_match", "contains"):
        assert set(stats[evaluator]) == {
            "mean",
            "ci_low",
            "ci_high",
            "n_bootstrap",
            "seed",
        }
        assert stats[evaluator]["mean"] == payload["per_evaluator_mean"][evaluator]
        assert stats[evaluator]["ci_low"] <= stats[evaluator]["mean"]
        assert stats[evaluator]["ci_high"] >= stats[evaluator]["mean"]
        assert stats[evaluator]["n_bootstrap"] == 1000
        assert isinstance(stats[evaluator]["seed"], int)


def test_cli_receipt_bootstrap_seed_is_deterministic(tmp_path: Path):
    _register_mock_task()
    dataset = tmp_path / "dataset.yaml"
    _dataset(dataset)

    first = _run_cli(dataset, tmp_path / "receipt-a.json")
    second = _run_cli(dataset, tmp_path / "receipt-b.json")

    assert first["per_evaluator_bootstrap"] == second["per_evaluator_bootstrap"]
    exact = first["per_evaluator_bootstrap"]["exact_match"]
    expected = bootstrap_ci([1.0, 0.0, 1.0, 0.0], seed=exact["seed"])
    assert exact["mean"] == expected.mean
    assert exact["ci_low"] == expected.ci_low
    assert exact["ci_high"] == expected.ci_high
    assert exact["n_bootstrap"] == expected.n_bootstrap
