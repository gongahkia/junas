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
        with patch.dict(os.environ, {"KAYPOH_API_KEY": "top-secret"}, clear=False):
            with TestClient(test_app.app) as client:
                response = client.post("/classify", json={"text": "public update"})

        self.assertEqual(response.status_code, 401)
        self.assertTrue(response.text.startswith("{\n"))
        self.assertIn('\n  "detail": "invalid or missing API key"\n', response.text)
        self.assertEqual(json.loads(response.text)["detail"], "invalid or missing API key")


if __name__ == "__main__":
    unittest.main()
