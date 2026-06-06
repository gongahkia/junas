"""Integration tests for /api/v1/benchmarks/* routes."""
from __future__ import annotations

import json
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from api.main import create_app, settings


AUTH_HEADERS = {"X-API-Key": "test-key"}


def _configure_benchmark_auth(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(settings, "api_keys", ["test-key"])
    monkeypatch.setattr(settings, "require_auth", False)


@pytest.fixture
def client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("JUNAS_BENCHMARK_RUNS_DIR", str(tmp_path / "runs"))
    _configure_benchmark_auth(monkeypatch)
    app = create_app()
    client = TestClient(app)
    client.headers.update(AUTH_HEADERS)
    return client


@pytest.fixture
def unauth_client(tmp_path, monkeypatch) -> TestClient:
    monkeypatch.setenv("JUNAS_BENCHMARK_RUNS_DIR", str(tmp_path / "runs"))
    _configure_benchmark_auth(monkeypatch)
    app = create_app()
    return TestClient(app)


def test_benchmark_routes_require_api_key(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/benchmarks/tasks")
    assert resp.status_code == 401
    assert resp.json()["detail"] == "Invalid API key"


def test_benchmark_routes_accept_api_key(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/benchmarks/tasks", headers=AUTH_HEADERS)
    assert resp.status_code == 200


def test_benchmark_gate_does_not_enable_global_auth(unauth_client: TestClient) -> None:
    resp = unauth_client.get("/api/v1/health")
    assert resp.status_code == 200


def test_list_tasks_includes_sglb_04(client: TestClient) -> None:
    resp = client.get("/api/v1/benchmarks/tasks")
    assert resp.status_code == 200
    names = {item["name"] for item in resp.json()}
    assert "sglb_04" in names
    assert "echo" in names


def test_list_evaluators_returns_tier(client: TestClient) -> None:
    resp = client.get("/api/v1/benchmarks/evaluators")
    assert resp.status_code == 200
    items = resp.json()
    strong = {item["name"] for item in items if item["strength"] == "strong"}
    weak = {item["name"] for item in items if item["strength"] == "weak"}
    assert "multi_label_f1" in strong
    assert "citation_format_valid" in strong
    assert "contains" in weak


def test_run_unknown_workflow_400(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "does_not_exist",
            "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
            "evaluators": ["multi_label_f1"],
        },
    )
    assert resp.status_code == 400
    assert "unknown workflow" in resp.json()["detail"]


def test_run_unknown_evaluator_400(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "sglb_04",
            "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
            "evaluators": ["does_not_exist"],
        },
    )
    assert resp.status_code == 400


def test_run_missing_dataset_404(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "sglb_04",
            "dataset": "benchmark/datasets/nope.yaml",
            "evaluators": ["multi_label_f1"],
        },
    )
    assert resp.status_code == 404


def test_run_strict_mode_rejects_weak_evaluator_400(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "sglb_04",
            "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
            "evaluators": ["contains"],
            "strict": True,
        },
    )
    assert resp.status_code == 400
    assert "weak evaluators" in resp.json()["detail"]


def test_run_sglb_04_oracle_agreement(client: TestClient, tmp_path) -> None:
    resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "sglb_04",
            "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
            "evaluators": ["multi_label_f1"],
            "strict": True,
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # Task wraps the oracle scorer, so agreement is 1.0 on the smoke set.
    assert body["per_evaluator_mean"]["multi_label_f1"] == pytest.approx(1.0)
    assert body["total_cases"] == 30
    assert body["strict"] is True
    assert body["weak_evaluators_used"] == []
    # SGLB-04 uses a regulator-tier (grammar oracle) dataset; default tier.
    assert body["data_tier"] == "regulator"

    # Receipt was persisted.
    runs_dir = Path(os.environ["JUNAS_BENCHMARK_RUNS_DIR"])
    receipts = list(runs_dir.glob("*.json"))
    assert len(receipts) == 1
    payload = json.loads(receipts[0].read_text(encoding="utf-8"))
    assert payload["workflow"] == "sglb_04"
    assert payload["total_cases"] == 30
    assert payload["data_tier"] == "regulator"


def test_run_response_carries_data_tier(client: TestClient) -> None:
    resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "sglb_04",
            "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
            "evaluators": ["multi_label_f1"],
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    # Default tier when no case carries data_tier metadata.
    assert body["data_tier"] == "regulator"


def test_run_detail_reflects_persisted_receipt(client: TestClient) -> None:
    run_resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "echo",
            "dataset": "benchmark/datasets/example_echo.yaml",
            "evaluators": ["contains"],
        },
    )
    assert run_resp.status_code == 200
    run_id = run_resp.json()["run_id"]

    resp = client.get(f"/api/v1/benchmarks/runs/{run_id}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == run_id
    assert body["workflow"] == "echo"
    assert body["per_evaluator_mean"]["contains"] == pytest.approx(1.0)
    assert len(body["cases"]) == 3

    case = next(c for c in body["cases"] if c["case_name"] == "pdpa_simple")
    assert case["input"]["query"] == "The Employment Act (Cap. 91) applies in Singapore."
    assert case["expected"]["span"] == "The Employment Act (Cap. 91) applies in Singapore."
    assert case["actual"] == "The Employment Act (Cap. 91) applies in Singapore."
    assert case["evaluator_scores"]["contains"]["score"] == pytest.approx(1.0)
    assert body["results"][0]["output"]


def test_run_detail_globs_baseline_receipt(client: TestClient) -> None:
    run_resp = client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "echo",
            "dataset": "benchmark/datasets/example_echo.yaml",
            "evaluators": ["contains"],
        },
    )
    assert run_resp.status_code == 200

    runs_dir = Path(os.environ["JUNAS_BENCHMARK_RUNS_DIR"])
    flat_receipt = next(runs_dir.glob("*.json"))
    baseline_receipt = runs_dir / "baselines" / "mock" / "echo" / "1700000000.json"
    baseline_receipt.parent.mkdir(parents=True, exist_ok=True)
    baseline_receipt.write_text(flat_receipt.read_text(encoding="utf-8"), encoding="utf-8")

    resp = client.get("/api/v1/benchmarks/runs/mock__echo__1700000000")
    assert resp.status_code == 200
    body = resp.json()
    assert body["run_id"] == "mock__echo__1700000000"
    assert body["cases"][0]["actual"] == body["cases"][0]["input"]["query"]


def test_leaderboard_entry_carries_data_tier(client: TestClient) -> None:
    # Produce a run, then verify the leaderboard echoes data_tier.
    client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "sglb_04",
            "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
            "evaluators": ["multi_label_f1"],
        },
    )
    resp = client.get("/api/v1/benchmarks/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"], "expected at least one leaderboard entry"
    assert all("data_tier" in entry for entry in body["entries"])
    assert body["entries"][0]["data_tier"] == "regulator"


def test_leaderboard_empty_when_no_receipts(client: TestClient) -> None:
    resp = client.get("/api/v1/benchmarks/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert body["entries"] == []
    assert body["aggregated_per_workflow"] == {}


def test_leaderboard_reflects_run(client: TestClient) -> None:
    client.post(
        "/api/v1/benchmarks/run",
        json={
            "workflow": "sglb_04",
            "dataset": "benchmark/datasets/sglb_04_citation_verify.yaml",
            "evaluators": ["multi_label_f1"],
            "strict": True,
        },
    )
    resp = client.get("/api/v1/benchmarks/leaderboard")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["entries"]) == 1
    entry = body["entries"][0]
    assert entry["workflow"] == "sglb_04"
    assert entry["per_evaluator_mean"]["multi_label_f1"] == pytest.approx(1.0)
    assert entry["total_cases"] == 30
    assert body["aggregated_per_workflow"]["sglb_04"]["multi_label_f1"] == pytest.approx(1.0)
