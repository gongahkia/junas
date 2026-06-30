import os
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

from junas.backend import main

DEMO_ENV = (
    "JUNAS_PUBLIC_DEMO_ENABLED",
    "JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES",
    "JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS",
    "JUNAS_PUBLIC_DEMO_RATE_LIMIT",
    "JUNAS_PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS",
    "JUNAS_REVIEW_PERSIST",
)


class PublicDemoTests(unittest.TestCase):
    def setUp(self):
        self._env = {key: os.environ.get(key) for key in DEMO_ENV}
        for key in DEMO_ENV:
            os.environ.pop(key, None)
        main._state.pop("public_demo_rate_limit", None)

    def tearDown(self):
        for key, value in self._env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value
        main._state.pop("public_demo_rate_limit", None)

    def _enable_demo(self):
        os.environ["JUNAS_PUBLIC_DEMO_ENABLED"] = "1"
        main._state.pop("public_demo_rate_limit", None)

    def test_public_demo_is_disabled_by_default(self):
        with TestClient(main.app) as client:
            self.assertEqual(client.get("/demo").status_code, 404)
            self.assertEqual(client.post("/demo/review", json={"text": "safe"}).status_code, 404)

    def test_public_demo_page_declares_deterministic_non_persistent_scope(self):
        self._enable_demo()
        with TestClient(main.app) as client:
            response = client.get("/demo")

        self.assertEqual(response.status_code, 200)
        self.assertIn("text/html", response.headers["content-type"])
        html = response.text
        for token in (
            "Junas deterministic demo",
            "Strict-profile demo",
            "No LLM, no public evidence, no persistence",
            "Use synthetic text only",
            "SG NRIC prompt",
            "M&amp;A MNPI email",
            "Clean internal note",
            "/demo/review",
            "Profile",
            "strict deterministic",
        ):
            self.assertIn(token, html)

    def test_public_demo_docs_describe_gates_and_limits(self):
        doc = (main.PROJECT_ROOT / "docs" / "public-demo.md").read_text(encoding="utf-8")
        index = (main.PROJECT_ROOT / "docs" / "README.md").read_text(encoding="utf-8")
        for token in (
            "disabled by default",
            "JUNAS_PUBLIC_DEMO_ENABLED=1",
            "JUNAS_REVIEW_PERSIST=0",
            "PIPELINE_LAYERS=\"\"",
            "GET /demo",
            "POST /demo/review",
            "forces `review_profile=\"strict\"`",
            "fresh `PreSendReviewEngine()`",
            "bypasses review-session persistence",
            "JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES",
            "JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS",
            "JUNAS_PUBLIC_DEMO_RATE_LIMIT",
            "synthetic, non-confidential text only",
            "does not include a live hosted URL",
        ):
            self.assertIn(token, doc)
        self.assertIn("public-demo.md", index)

    def test_public_demo_review_is_unauthenticated_strict_and_non_persistent(self):
        self._enable_demo()
        os.environ["JUNAS_REVIEW_PERSIST"] = "1"
        payload = {
            "text": (
                "Project Raven will acquire GlobalTech for USD 2.5 billion before announcement. "
                "Send Dr Jane Tan S1234567D the draft."
            ),
            "source_jurisdiction": "SG",
            "destination_jurisdiction": "US",
            "review_profile": "audit_grade",
        }
        with patch("junas.backend.main.start_review_session") as start_review_session:
            with TestClient(main.app) as client:
                response = client.post("/demo/review", json=payload)

        self.assertEqual(response.status_code, 200, response.text)
        body = response.json()
        self.assertEqual(body["review_profile"], "strict")
        self.assertEqual(body["document_type"], "genai_prompt")
        self.assertFalse(body["send_allowed"])
        self.assertEqual(body["policy_decision"]["decision"], "block")
        self.assertIsNone(body["public_evidence"])
        self.assertIsNone(body["llm_adjudication"])
        self.assertEqual(body["privacy_ledger"], [])
        self.assertTrue(any(finding["category"] == "PII" for finding in body["findings"]))
        self.assertTrue(any(finding["category"] == "MNPI" for finding in body["findings"]))
        start_review_session.assert_not_called()

    def test_public_demo_enforces_body_and_text_caps(self):
        self._enable_demo()
        os.environ["JUNAS_PUBLIC_DEMO_BODY_MAX_BYTES"] = "512"
        os.environ["JUNAS_PUBLIC_DEMO_TEXT_MAX_CHARS"] = "100"
        with TestClient(main.app) as client:
            body_response = client.post("/demo/review", json={"text": "x" * 1000})
            text_response = client.post("/demo/review", json={"text": "x" * 101})

        self.assertEqual(body_response.status_code, 413)
        self.assertEqual(text_response.status_code, 413)

    def test_public_demo_rate_limits_by_client(self):
        self._enable_demo()
        os.environ["JUNAS_PUBLIC_DEMO_RATE_LIMIT"] = "2"
        os.environ["JUNAS_PUBLIC_DEMO_RATE_LIMIT_WINDOW_SECONDS"] = "60"
        payload = {"text": "Internal lunch note.", "source_jurisdiction": "SG", "destination_jurisdiction": "SG"}
        with TestClient(main.app) as client:
            first = client.post("/demo/review", json=payload)
            second = client.post("/demo/review", json=payload)
            third = client.post("/demo/review", json=payload)

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 200)
        self.assertEqual(third.status_code, 429)


if __name__ == "__main__":
    unittest.main()
