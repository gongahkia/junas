from __future__ import annotations

import asyncio
import time
from typing import Any

from fastapi.testclient import TestClient

from api.main import create_app


class StubContractClassifier:
    async def classify_contract(self, text: str, top_k_types: int = 3) -> list[dict[str, Any]]:
        await asyncio.sleep(0.01)
        return [
            {
                "segment_index": 0,
                "text": text[:80],
                "start": 0,
                "end": len(text),
                "clause_type": "Governing Law",
                "confidence": 0.91,
                "alternatives": [],
            }
        ]


class StubToSScanner:
    async def scan_tos(self, text: str, threshold: float = 0.5) -> dict[str, Any]:
        await asyncio.sleep(0.01)
        return {
            "total_sentences": 1,
            "unfair_count": 1,
            "fair_count": 0,
            "severity_score": 1.0,
            "sentences": [
                {
                    "index": 0,
                    "text": text[:80],
                    "is_unfair": True,
                    "unfair_categories": [{"category": "Choice of Law", "confidence": threshold}],
                }
            ],
            "summary": {"Choice of Law": 1},
        }


def _app():
    app = create_app()
    return app


def _install_stubs(app) -> None:
    app.state.contract_classifier = StubContractClassifier()
    app.state.tos_scanner = StubToSScanner()


def _docs(count: int) -> list[dict[str, str]]:
    return [
        {"id": f"doc-{index}", "file_name": f"doc-{index}.txt", "text": f"Agreement {index}. Singapore law applies."}
        for index in range(count)
    ]


def _wait_for_status(client: TestClient, batch_id: str, status: str, timeout: float = 2.0) -> dict[str, Any]:
    deadline = time.time() + timeout
    while time.time() < deadline:
        body = client.get(f"/api/v1/contracts/batch/{batch_id}").json()
        if body["status"] == status:
            return body
        time.sleep(0.02)
    raise AssertionError(f"batch did not reach {status}")


def test_batch_analysis_completes_and_replays_sse_events() -> None:
    app = _app()
    with TestClient(app) as client:
        _install_stubs(app)
        created = client.post("/api/v1/contracts/batch", json={"documents": _docs(3)})
        assert created.status_code == 200
        batch_id = created.json()["id"]

        body = _wait_for_status(client, batch_id, "completed")
        assert body["completed"] == 3
        assert all(result["status"] == "done" for result in body["results"])
        assert body["results"][0]["flagged_clauses"][0]["unfair_categories"][0]["category"] == "Choice of Law"

        with client.stream("GET", f"/api/v1/contracts/batch/{batch_id}/events") as response:
            assert response.status_code == 200
            text = response.read().decode("utf-8")
        assert "event: document_completed" in text
        assert "event: completed" in text


def test_batch_analysis_enforces_50_doc_cap() -> None:
    app = _app()
    with TestClient(app) as client:
        _install_stubs(app)
        response = client.post("/api/v1/contracts/batch", json={"documents": _docs(51)})
    assert response.status_code == 422


def test_batch_analysis_cancel_mid_run_marks_pending_cancelled() -> None:
    app = _app()
    with TestClient(app) as client:
        _install_stubs(app)
        created = client.post("/api/v1/contracts/batch", json={"documents": _docs(10)})
        assert created.status_code == 200
        batch_id = created.json()["id"]
        time.sleep(0.04)

        cancelled = client.post(f"/api/v1/contracts/batch/{batch_id}/cancel")
        assert cancelled.status_code == 200
        body = cancelled.json()
        assert body["status"] == "cancelled"
        assert body["cancelled"] is True
        assert any(result["status"] == "cancelled" for result in body["results"])
