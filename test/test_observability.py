import pytest

pytest.skip(
    "legacy classifier pipeline archived 2026-05-26; "
    "see ARCHITECTURE-PIVOT-24-MAY.md item 63. Tests reference layer1-6 / mosaic "
    "/ legacy classify shape and need rewriting against the engine.review() wrapper.",
    allow_module_level=True,
)

import json
import os
import shutil
import signal
import subprocess
import sys
import tempfile
import time
import unittest
import urllib.request

os.environ.setdefault("KMP_DUPLICATE_LIB_OK", "TRUE")

from fastapi.testclient import TestClient

from test import observability_test_app as test_app


def parse_metric_value(metrics_text: str, metric_name: str, **labels: str) -> float | None:
    for line in metrics_text.splitlines():
        if not line.startswith(f"{metric_name}" + "{"):
            continue
        if not all(f'{key}="{value}"' in line for key, value in labels.items()):
            continue
        return float(line.rsplit(" ", 1)[-1])
    return None


class ExplodingModel:
    def predict(self, text: str):
        raise RuntimeError("forced model failure")


class ObservabilityApiTests(unittest.TestCase):
    def test_classify_success_and_ready_polling_do_not_affect_classification_metrics(self):
        test_app.seed_test_state(
            pipeline=["lexicon", "embedding", "clustering", "model1", "model2"],
            models={
                "lexicon": test_app.DummyLexiconFilter(),
                "embedding": test_app.DummyEmbedding(),
                "clustering": test_app.DummyClustering(),
                "model1": test_app.DummyModel1(label="safe"),
                "model2": test_app.DummyModel2(label="low_risk"),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post("/classify", json={"text": "public quarterly earnings guidance"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertFalse(payload["observability"]["degraded"])
            self.assertEqual(payload["observability"]["cache_status"], "miss")
            self.assertEqual(payload["observability"]["executed_layers"], ["lexicon", "embedding", "clustering", "model1"])
            self.assertEqual(payload["observability"]["skipped_layers"], ["model2"])

            metrics_before = client.get("/metrics").text
            classify_total_before = parse_metric_value(
                metrics_before,
                "kaypoh_classification_results_total",
                endpoint="/classify",
                classification="SAFE",
                cache_status="miss",
                degraded="false",
            )
            self.assertEqual(classify_total_before, 1.0)

            client.get("/ready")
            client.get("/ready")

            metrics_after = client.get("/metrics").text
            classify_total_after = parse_metric_value(
                metrics_after,
                "kaypoh_classification_results_total",
                endpoint="/classify",
                classification="SAFE",
                cache_status="miss",
                degraded="false",
            )
            self.assertEqual(classify_total_after, 1.0)
            ready_total = parse_metric_value(
                metrics_after,
                "kaypoh_http_requests_total",
                endpoint="/ready",
                method="GET",
                status_code="200",
            )
            self.assertGreaterEqual(ready_total or 0.0, 2.0)

    def test_missing_entity_id_skips_mosaic_without_degrading(self):
        test_app.seed_test_state(
            pipeline=["lexicon", "model1", "model2", "mosaic"],
            models={
                "lexicon": test_app.DummyLexiconFilter(),
                "model1": test_app.DummyModel1(label="risk", confidence=0.82, risk_score=0.88),
                "model2": test_app.DummyModel2(label="low_risk", confidence=0.76, high_risk_score=0.21),
                "mosaic": test_app.DummyMosaic(count=3),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post("/classify", json={"text": "internal operating review deck"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["classification"], "LOW_RISK")
            self.assertFalse(payload["observability"]["degraded"])
            self.assertEqual(payload["observability"]["cache_status"], "disabled")
            self.assertIn("mosaic", payload["observability"]["skipped_layers"])
            self.assertEqual(payload["observability"]["layer_errors"], [])

    def test_mosaic_response_exposes_aggregated_evidence(self):
        test_app.seed_test_state(
            pipeline=["lexicon", "model1", "model2", "mosaic"],
            models={
                "lexicon": test_app.DummyLexiconFilter(),
                "model1": test_app.DummyModel1(label="risk", confidence=0.82, risk_score=0.88),
                "model2": test_app.DummyModel2(label="low_risk", confidence=0.76, high_risk_score=0.21),
                "mosaic": test_app.DummyMosaic(escalated=True, count=3),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify",
                json={"text": "internal operating review deck", "entity_id": "Acme Corp"},
            )
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertEqual(payload["classification"], "HIGH_RISK")
            self.assertEqual(payload["mosaic"]["entity_id"], "Acme Corp")
            self.assertTrue(payload["mosaic"]["escalated"])
            self.assertEqual(payload["mosaic"]["recent_event_count"], 3)
            self.assertEqual(payload["mosaic"]["unique_fragment_count"], 3)
            self.assertEqual(payload["mosaic"]["threshold"], 10)
            self.assertEqual(payload["mosaic"]["matched_event_ids"], ["dummy-event-1"])

    def test_runtime_layer_error_marks_response_and_diagnostics(self):
        test_app.seed_test_state(
            pipeline=["lexicon", "model1"],
            models={
                "lexicon": test_app.DummyLexiconFilter(),
                "model1": ExplodingModel(),
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post("/classify", json={"text": "confidential acquisition target"})
            self.assertEqual(response.status_code, 200)
            payload = response.json()
            self.assertTrue(payload["observability"]["degraded"])
            self.assertEqual(payload["observability"]["layer_errors"][0]["layer"], "model1")
            self.assertEqual(payload["observability"]["layer_errors"][0]["phase"], "runtime")

            diagnostics = client.get("/diagnostics").json()
            self.assertEqual(diagnostics["runtime_layer_errors"]["model1"]["count"], 1)
            self.assertEqual(diagnostics["runtime_layer_errors"]["model1"]["last_message"], "forced model failure")

            metrics_text = client.get("/metrics").text
            layer_error_total = parse_metric_value(
                metrics_text,
                "kaypoh_layer_execution_total",
                layer="model1",
                outcome="error",
            )
            self.assertEqual(layer_error_total, 1.0)


class MultiprocessMetricsSmokeTests(unittest.TestCase):
    def test_metrics_endpoint_works_in_multiprocess_mode(self):
        temp_dir = tempfile.mkdtemp(prefix="kaypoh-prom-")
        port = 8123
        env = {
            **os.environ,
            "PROMETHEUS_MULTIPROC_DIR": temp_dir,
            "PYTHONPATH": os.getcwd(),
        }
        cmd = [
            sys.executable,
            "-m",
            "uvicorn",
            "test.observability_test_app:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
            "--workers",
            "2",
        ]
        proc = subprocess.Popen(cmd, cwd=os.getcwd(), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            deadline = time.time() + 20
            ready = False
            while time.time() < deadline:
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/ready", timeout=1) as response:
                        ready = response.status == 200
                        if ready:
                            break
                except Exception:
                    time.sleep(0.25)
            self.assertTrue(ready, "multiprocess test app did not start in time")

            for _ in range(6):
                request = urllib.request.Request(
                    f"http://127.0.0.1:{port}/classify",
                    data=json.dumps({"text": "hello"}).encode(),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request, timeout=3) as _:
                    pass

            with urllib.request.urlopen(f"http://127.0.0.1:{port}/metrics", timeout=3) as response:
                metrics_text = response.read().decode()

            miss_total = parse_metric_value(
                metrics_text,
                "kaypoh_classification_results_total",
                endpoint="/classify",
                classification="SAFE",
                cache_status="miss",
                degraded="false",
            )
            hit_total = parse_metric_value(
                metrics_text,
                "kaypoh_classification_results_total",
                endpoint="/classify",
                classification="SAFE",
                cache_status="hit",
                degraded="false",
            )
            self.assertEqual((miss_total or 0.0) + (hit_total or 0.0), 6.0)
            self.assertIn("kaypoh_http_requests_total", metrics_text)
            self.assertTrue(any(name.endswith(".db") for name in os.listdir(temp_dir)))
        finally:
            proc.send_signal(signal.SIGTERM)
            proc.wait(timeout=10)
            shutil.rmtree(temp_dir, ignore_errors=True)
