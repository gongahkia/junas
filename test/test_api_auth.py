import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from test import observability_test_app as test_app


class ApiAuthTests(unittest.TestCase):
    def setUp(self):
        test_app.seed_test_state(
            pipeline=["lexicon"],
            models={"lexicon": test_app.DummyLexiconFilter(flagged=False)},
        )

    def test_classify_rejects_missing_api_key_when_configured(self):
        with patch.dict(os.environ, {"JUNAS_API_KEY": "top-secret"}, clear=False):
            with TestClient(test_app.app) as client:
                response = client.post("/classify", json={"text": "public update"})

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "invalid or missing API key")

    def test_classify_accepts_matching_api_key(self):
        with patch.dict(os.environ, {"JUNAS_API_KEY": "top-secret"}, clear=False):
            with TestClient(test_app.app) as client:
                response = client.post(
                    "/classify",
                    json={"text": "public update"},
                    headers={"X-API-Key": "top-secret"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["classification"], "SAFE")

    def test_batch_rejects_wrong_api_key_when_configured(self):
        with patch.dict(os.environ, {"JUNAS_API_KEY": "top-secret"}, clear=False):
            with TestClient(test_app.app) as client:
                response = client.post(
                    "/classify/batch",
                    json={"items": [{"text": "public update"}]},
                    headers={"X-API-Key": "wrong-key"},
                )

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["detail"], "invalid or missing API key")

    def test_batch_accepts_matching_api_key(self):
        with patch.dict(os.environ, {"JUNAS_API_KEY": "top-secret"}, clear=False):
            with TestClient(test_app.app) as client:
                response = client.post(
                    "/classify/batch",
                    json={"items": [{"text": "public update"}, {"text": "another public update"}]},
                    headers={"X-API-Key": "top-secret"},
                )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.json()["results"]), 2)


if __name__ == "__main__":
    unittest.main()
