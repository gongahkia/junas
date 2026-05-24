import importlib
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from test.integration_helpers import ensure_real_artifacts_available, load_json_fixture, require_env_flag


class RuntimeArtifactIntegrationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        require_env_flag(
            "KAYPOH_RUN_REAL_ARTIFACT_INTEGRATION",
            reason="set KAYPOH_RUN_REAL_ARTIFACT_INTEGRATION=1 to run real-artifact runtime tests",
        )
        ensure_real_artifacts_available()

        cls.fixture = load_json_fixture("runtime_golden_corpus.json")
        cls.env_patcher = patch.dict(
            os.environ,
            {
                "KMP_DUPLICATE_LIB_OK": "TRUE",
                "PIPELINE_LAYERS": "model1,model2",
                "KAYPOH_OPTIONAL_LAYERS": "",
                "KAYPOH_FAIL_ON_LAYER_LOAD_ERROR": "1",
                "KAYPOH_LAZY_LOAD_HEAVY": "0",
            },
            clear=False,
        )
        cls.env_patcher.start()

        canonical_main = importlib.import_module("kaypoh.backend.main")
        importlib.reload(canonical_main)
        shim_main = importlib.import_module("backend.main")
        cls.main = importlib.reload(shim_main)
        cls.client = TestClient(cls.main.app)
        cls.client.__enter__()

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.main._state.clear()
        cls.env_patcher.stop()

    def test_ready_endpoint_reports_loaded_runtime(self):
        response = self.client.get("/ready")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["status"], "ok")
        self.assertTrue(payload["ready"])
        self.assertEqual(payload["pipeline"], ["model1", "model2"])
        self.assertEqual(payload["missing_required_layers"], [])
        self.assertEqual(payload["warming_required_layers"], [])
        self.assertEqual(payload["reasons"], [])

    def test_diagnostics_endpoint_reports_no_runtime_layer_errors(self):
        response = self.client.get("/diagnostics")
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(payload["pipeline"], ["model1", "model2"])
        self.assertEqual(payload["runtime_layer_errors"], {})
        self.assertIn("model1", payload["startup_timings_ms"])
        self.assertIn("model2", payload["startup_timings_ms"])

    def test_classify_matches_real_artifact_golden_corpus(self):
        for case in self.fixture["classification_cases"]:
            with self.subTest(case=case["name"]):
                response = self.client.post("/classify", json={"text": case["text"]})
                payload = response.json()

                self.assertEqual(response.status_code, 200)
                self.assertEqual(payload["classification"], case["expected_classification"])
                self.assertIn("request_id", payload)
                self.assertIn("total", payload["timings_ms"])

    def test_batch_classify_preserves_order_for_golden_cases(self):
        response = self.client.post(
            "/classify/batch",
            json={"items": [{"text": case["text"]} for case in self.fixture["classification_cases"]]},
        )
        payload = response.json()

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            [item["classification"] for item in payload["results"]],
            [case["expected_classification"] for case in self.fixture["classification_cases"]],
        )
        self.assertEqual(
            [item["request_id"].split(":")[-1] for item in payload["results"]],
            ["0", "1", "2"],
        )


if __name__ == "__main__":
    unittest.main()
