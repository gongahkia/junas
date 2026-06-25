import json
import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from test import observability_test_app as test_app


class ResponseFormattingTests(unittest.TestCase):
    def setUp(self):
        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={"lexicon": test_app.DummyLexiconFilter(flagged=False)},
        )

    def test_classify_response_is_pretty_json(self):
        with TestClient(test_app.app) as client:
            response = client.post("/classify", json={"text": "public update"})

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.text.startswith("{\n"))
        self.assertIn('\n  "classification": "SAFE"', response.text)
        self.assertEqual(json.loads(response.text)["classification"], "SAFE")

    def test_batch_response_is_pretty_json(self):
        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify/batch",
                json={"items": [{"text": "public update"}, {"text": "another public update"}]},
            )

        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.text.startswith("{\n"))
        self.assertIn('\n  "results": [', response.text)
        self.assertEqual(len(json.loads(response.text)["results"]), 2)

    def test_http_error_response_is_pretty_json(self):
        with patch.dict(os.environ, {"JUNAS_API_KEY": "top-secret"}, clear=False):
            with TestClient(test_app.app) as client:
                response = client.post("/classify", json={"text": "public update"})

        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.text.startswith("{\n"))
        self.assertIn('\n  "detail": "invalid or missing API key"\n', response.text)
        self.assertEqual(json.loads(response.text)["detail"], "invalid or missing API key")

    def test_request_body_limit_returns_pretty_413_before_validation(self):
        with patch.dict(os.environ, {"JUNAS_MAX_REQUEST_BYTES": "1024"}, clear=False):
            with TestClient(test_app.app) as client:
                response = client.post("/classify", json={"text": "x" * 2000})

        self.assertEqual(response.status_code, 413)
        self.assertTrue(response.text.startswith("{\n"))
        self.assertIn("request body exceeds configured limit", response.json()["detail"])

    def test_invalid_content_length_returns_pretty_400_before_validation(self):
        with TestClient(test_app.app) as client:
            response = client.post(
                "/classify",
                content=b'{"text":"public update"}',
                headers={"Content-Length": "bogus", "Content-Type": "application/json"},
            )

        self.assertEqual(response.status_code, 400)
        self.assertTrue(response.text.startswith("{\n"))
        self.assertEqual(response.json()["detail"], "invalid Content-Length header")

    def test_invalid_degraded_policy_returns_pretty_422_contract_error(self):
        with TestClient(test_app.app) as client:
            response = client.post(
                "/review",
                json={"text": "public update", "degraded_policy": "fail_closed"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertTrue(response.text.startswith("{\n"))
        self.assertIn("degraded_policy", response.text)


if __name__ == "__main__":
    unittest.main()
