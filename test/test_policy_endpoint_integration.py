import sys
import unittest
from datetime import UTC, datetime
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

from junas.backend import main
from junas.policy import ACTION_CATALOG


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
        self.assertIn("junas_policy_decision_duration_seconds_bucket", metrics.text)

    def test_review_metrics_include_surface_decision_and_required_actions(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": "Send Dr Jane Tan S1234567D to external counsel before filing.",
                    "surface": "outlook",
                    "workflow": "email_send",
                    "document_type": "email",
                    "destination_jurisdiction": "US",
                    "external_destination": True,
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["policy_decision"]["decision"], "rewrite_required")
            metrics = client.get("/metrics")

        self.assertEqual(metrics.status_code, 200, metrics.text)
        self.assertIn(
            'junas_review_surface_total{decision="rewrite_required",endpoint="/review",surface="outlook",workflow="email_send"}',
            metrics.text,
        )
        self.assertIn(
            'junas_policy_decisions_total{decision="rewrite_required",surface="outlook",workflow="email_send"}',
            metrics.text,
        )
        self.assertIn(
            'junas_policy_required_actions_total{action="safe_rewrite",decision="rewrite_required",surface="outlook",workflow="email_send"}',
            metrics.text,
        )

    def test_safe_rewrite_metric_counts_applied_replacements(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/safe-rewrite",
                json={
                    "text": "Paste Dr Jane Tan S1234567D into the model.",
                    "surface": "browser_genai",
                    "workflow": "prompt_submit",
                    "requested_action": "safe_rewrite",
                    "allowed_actions": ["safe_rewrite"],
                },
            )
            self.assertEqual(response.status_code, 200, response.text)
            self.assertTrue(response.json()["replacements"])
            metrics = client.get("/metrics")

        self.assertEqual(metrics.status_code, 200, metrics.text)
        self.assertIn(
            'junas_safe_rewrite_applied_total{action="safe_rewrite",endpoint="/safe-rewrite",surface="browser_genai",workflow="prompt_submit"}',
            metrics.text,
        )


if __name__ == "__main__":
    unittest.main()
