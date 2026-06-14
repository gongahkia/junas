import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from kaypoh.backend import main
from kaypoh.policy import ACTION_CATALOG


class PolicyEndpointIntegrationTests(unittest.TestCase):
    def _assert_review_expiry(self, payload):
        self.assertIn("review_expires_at", payload)
        expires_at = datetime.fromisoformat(payload["review_expires_at"].replace("Z", "+00:00"))
        self.assertGreater(expires_at, datetime.now(UTC))

    def test_review_response_includes_policy_decision_and_send_allowed(self):
        with TestClient(main.app) as client:
            response = client.post("/review", json={"text": "This public update is safe to share."})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("send_allowed", payload)
        self.assertIn("policy_decision", payload)
        self._assert_review_expiry(payload)
        self.assertEqual(payload["action_catalog"], list(ACTION_CATALOG))
        self.assertIn("policy_decision_ms", payload["timings_ms"])
        self.assertEqual(payload["policy_decision"]["decision"], "allow")
        self.assertEqual(payload["send_allowed"], payload["policy_decision"]["send_allowed"])

    def test_rewrite_responses_include_policy_decision_and_send_allowed(self):
        for endpoint in ("/pseudonymize", "/anonymize", "/redact"):
            with self.subTest(endpoint=endpoint):
                with TestClient(main.app) as client:
                    response = client.post(endpoint, json={"text": "This public update is safe to share."})

                self.assertEqual(response.status_code, 200, response.text)
                payload = response.json()
                self.assertIn("send_allowed", payload)
                self.assertIn("policy_decision", payload)
                self._assert_review_expiry(payload)
                self.assertEqual(payload["action_catalog"], list(ACTION_CATALOG))
                self.assertIn("policy_decision_ms", payload["timings_ms"])
                self.assertEqual(payload["policy_decision"]["decision"], "allow")
                self.assertEqual(payload["send_allowed"], payload["policy_decision"]["send_allowed"])

    def test_policy_decision_metric_is_exported(self):
        with TestClient(main.app) as client:
            response = client.post("/review", json={"text": "This public update is safe to share."})
            self.assertEqual(response.status_code, 200, response.text)
            metrics = client.get("/metrics")

        self.assertEqual(metrics.status_code, 200, metrics.text)
        self.assertIn("kaypoh_policy_decision_duration_seconds_bucket", metrics.text)


if __name__ == "__main__":
    unittest.main()
