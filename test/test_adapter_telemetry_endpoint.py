import json
import unittest
from unittest import mock

from fastapi.testclient import TestClient

from junas.backend import main


class AdapterTelemetryEndpointTests(unittest.TestCase):
    def test_adapter_telemetry_endpoint_emits_outlook_and_browser_siem_safe_events(self):
        captured: list[dict] = []

        def capture(event, **kwargs):
            captured.append(dict(event))
            return True

        payload = {
            "events": [
                {
                    "schema_version": "junas.outlook.telemetry.v1",
                    "event_name": "outlook_policy_decision_received",
                    "surface": "outlook",
                    "workflow": "email_send",
                    "timestamp": "2026-07-07T00:00:00Z",
                    "details": {
                        "request_id": "req-outlook",
                        "review_id": "rev-outlook",
                        "policy_id": "default",
                        "policy_version": "2026-07-07",
                        "decision": "warn",
                        "send_allowed": False,
                        "required_actions": ["redact_pii"],
                        "finding_count": 1,
                        "recipient_count": 2,
                        "recipient_domain_count": 2,
                        "attachment_count": 1,
                        "text": "Subject: Dr Jane Tan S1234567D",
                        "authorization": "Bearer secret-token",
                        "endpoint_url": "https://junas.example.com/review",
                        "unexpected_raw_field": "Project Raven raw text",
                    },
                },
                {
                    "schema_version": "junas.browser.telemetry.v1",
                    "event_name": "browser_user_proceeded_after_warning",
                    "surface": "browser_genai",
                    "workflow": "prompt_submit",
                    "details": {
                        "request_id": "req-browser",
                        "review_id": "rev-browser",
                        "decision": "warn",
                        "send_allowed": False,
                        "operation": "review",
                        "finding_count": 1,
                        "selector_kind": "prompt",
                        "prompt": "Paste Dr Jane Tan S1234567D into ChatGPT",
                    },
                },
            ]
        }

        with mock.patch("junas.backend.main.emit_siem_event", side_effect=capture):
            with TestClient(main.app) as client:
                response = client.post("/adapter-telemetry", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["accepted_count"], 2)
        self.assertEqual(body["emitted_count"], 2)
        self.assertEqual(body["events"][0]["outcome"], "succeeded")
        self.assertEqual(body["events"][1]["outcome"], "warned")
        self.assertEqual(len(captured), 2)
        self.assertEqual(captured[0]["event_type"], "adapter_telemetry")
        self.assertEqual(captured[0]["category"], "audit")
        self.assertEqual(captured[0]["action"], "outlook_policy_decision_received")
        self.assertEqual(captured[0]["request_id"], "req-outlook")
        self.assertEqual(captured[0]["review_id"], "rev-outlook")
        self.assertEqual(captured[0]["details"]["surface"], "outlook")
        self.assertEqual(captured[0]["details"]["workflow"], "email_send")
        self.assertEqual(captured[0]["details"]["authorization"], "[redacted]")
        self.assertIn("text_sha256", captured[0]["details"]["text"])
        self.assertIn("endpoint_url_sha256", captured[0]["details"]["endpoint_url"])
        self.assertEqual(captured[0]["details"]["dropped_detail_field_count"], 1)
        self.assertEqual(captured[0]["details"]["sanitized_prohibited_field_count"], 3)

        serialized = json.dumps(captured, sort_keys=True)
        for forbidden in (
            "Dr Jane Tan",
            "S1234567D",
            "secret-token",
            "https://junas.example.com/review",
            "Project Raven raw text",
            "ChatGPT",
        ):
            self.assertNotIn(forbidden, serialized)

    def test_adapter_telemetry_rejects_root_level_raw_content_fields(self):
        payload = {
            "events": [
                {
                    "schema_version": "junas.browser.telemetry.v1",
                    "event_name": "browser_prompt_review_started",
                    "surface": "browser_genai",
                    "workflow": "prompt_submit",
                    "text": "raw prompt must not be accepted at event root",
                    "details": {"timeout_ms": 8000},
                }
            ]
        }

        with TestClient(main.app) as client:
            response = client.post("/adapter-telemetry", json=payload)

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
