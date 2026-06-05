from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from api.main import create_app
from benchmark.scripts.build_leaderboard import build_leaderboard


def _receipt(workflow: str) -> dict:
    return {
        "workflow": workflow,
        "dataset": f"benchmark/datasets/{workflow}.yaml",
        "finished_at": "2026-06-05T00:00:00+00:00",
        "total_cases": 1,
        "strict": True,
        "data_tier": "regulator",
        "per_evaluator_mean": {"multi_label_f1": 1.0},
        "results": [
            {
                "case_name": "c1",
                "evaluator": "multi_label_f1",
                "score": 1.0,
                "metadata": {},
                "error": None,
            }
        ],
    }


def test_static_leaderboard_rows_are_v01_eligible_only(tmp_path: Path):
    payload = build_leaderboard(
        root=tmp_path,
        required_providers=(),
        allow_missing=True,
    )
    tasks = {row["task"] for row in payload["rows"]}
    assert tasks == {"SGLB-01", "SGLB-02", "SGLB-04", "SGLB-08"}


def test_static_leaderboard_ignores_ineligible_receipts(tmp_path: Path):
    provider = tmp_path / "mock"
    provider.mkdir()
    (provider / "sglb_05.json").write_text(json.dumps(_receipt("sglb_05")), encoding="utf-8")
    (provider / "sglb_08.json").write_text(json.dumps(_receipt("sglb_08")), encoding="utf-8")

    payload = build_leaderboard(
        root=tmp_path,
        required_providers=("mock",),
        allow_missing=True,
    )

    assert "SGLB-05" not in {row["task"] for row in payload["rows"]}
    sglb_08 = next(row for row in payload["rows"] if row["task"] == "SGLB-08")
    assert "mock" in sglb_08["cells"]


def test_api_leaderboard_filters_ineligible_receipts(tmp_path: Path, monkeypatch):
    runs_dir = tmp_path / "runs"
    runs_dir.mkdir()
    monkeypatch.setenv("JUNAS_BENCHMARK_RUNS_DIR", str(runs_dir))
    (runs_dir / "eligible.json").write_text(json.dumps(_receipt("sglb_04")), encoding="utf-8")
    (runs_dir / "ineligible.json").write_text(json.dumps(_receipt("sglb_05")), encoding="utf-8")

    client = TestClient(create_app())
    body = client.get("/api/v1/benchmarks/leaderboard").json()

    assert [entry["workflow"] for entry in body["entries"]] == ["sglb_04"]
    assert "sglb_05" not in body["aggregated_per_workflow"]
