import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from test import observability_test_app as test_app


class BackendLogPrivacyTests(unittest.TestCase):
    def setUp(self):
        test_app.seed_test_state(pipeline=["lexicon"], models={"lexicon": test_app.DummyLexiconFilter()})

    def test_backend_logs_exclude_request_body_spans_mappings_and_auth_headers(self):
        sensitive_prompt = "GenAI prompt: summarize the client note for Dr Jane Tan."
        sensitive_email_body = "Email body: Dr Jane Tan S1234567D will receive Project Atlas before announcement."
        mapping_secret = "Jane Mapping Secret S7654321A"
        auth_secret = "backend-log-api-secret"
        bearer_secret = "backend-log-bearer-secret"

        with patch.dict(os.environ, {"JUNAS_API_KEY": auth_secret}, clear=False):
            with self.assertLogs("junas.backend", level="INFO") as records:
                with TestClient(test_app.app) as client:
                    review = client.post(
                        "/review",
                        headers={
                            "X-API-Key": auth_secret,
                            "Authorization": f"Bearer {bearer_secret}",
                        },
                        json={
                            "text": f"{sensitive_prompt}\n{sensitive_email_body}",
                            "surface": "browser_genai",
                            "workflow": "prompt_submit",
                            "document_type": "email",
                            "external_destination": True,
                        },
                    )
                    reidentify = client.post(
                        "/reidentify",
                        headers={
                            "X-API-Key": auth_secret,
                            "Authorization": f"Bearer {bearer_secret}",
                        },
                        json={
                            "anonymized_text": "Send [PERSON_1] the file.",
                            "mapping": [{"placeholder": "[PERSON_1]", "original_text": mapping_secret}],
                        },
                    )
                    rejected = client.post(
                        "/review",
                        headers={
                            "X-API-Key": "wrong-backend-log-secret",
                            "Authorization": f"Bearer {bearer_secret}",
                        },
                        json={"text": sensitive_email_body},
                    )

        self.assertEqual(review.status_code, 200)
        self.assertTrue(any(finding["matched_text"] == "S1234567D" for finding in review.json()["findings"]))
        self.assertEqual(reidentify.status_code, 200)
        self.assertEqual(rejected.status_code, 401)

        output = "\n".join(records.output)
        self.assertIn('"event": "request"', output)
        self.assertIn('"event": "review_summary"', output)
        self.assertIn('"path": "/review"', output)
        self.assertIn('"path": "/reidentify"', output)
        for forbidden in (
            sensitive_prompt,
            sensitive_email_body,
            "Dr Jane Tan",
            "S1234567D",
            "Project Atlas",
            mapping_secret,
            auth_secret,
            bearer_secret,
            "wrong-backend-log-secret",
            "Authorization",
            "X-API-Key",
            "original_text",
            "mapping",
        ):
            self.assertNotIn(forbidden, output)


if __name__ == "__main__":
    unittest.main()
