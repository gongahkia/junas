import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

from junas.backend import main


@asynccontextmanager
async def _noop_lifespan(app):
    yield


RATE_LIMIT_ENV = (
    "JUNAS_RATE_LIMIT_ENABLED",
    "JUNAS_RATE_LIMIT_WINDOW_SECONDS",
    "JUNAS_RATE_LIMIT_REVIEW",
    "JUNAS_RATE_LIMIT_BATCH_CLASSIFY",
    "JUNAS_RATE_LIMIT_REIDENTIFY",
    "JUNAS_RATE_LIMIT_LOCAL_PAIRING",
    "JUNAS_RATE_LIMIT_DECISION",
    "JUNAS_LOCAL_DAEMON_ACL_ENABLED",
    "JUNAS_LOCAL_DAEMON_TOKEN",
    "JUNAS_JOURNAL_DIR",
    "JUNAS_JOURNAL_KEY",
    "JUNAS_REVIEW_PERSIST",
    "JUNAS_SUBJECT_INDEX_KEY",
)


class RateLimitTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        self._old_env = {key: os.environ.get(key) for key in RATE_LIMIT_ENV}
        for key in RATE_LIMIT_ENV:
            os.environ.pop(key, None)
        os.environ["JUNAS_RATE_LIMIT_ENABLED"] = "1"
        os.environ["JUNAS_RATE_LIMIT_WINDOW_SECONDS"] = "60"
        self._old_lifespan = main.app.router.lifespan_context
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()

    def tearDown(self):
        main.app.router.lifespan_context = self._old_lifespan
        main._state.clear()
        self._tmpdir.cleanup()
        for key, old_value in self._old_env.items():
            if old_value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = old_value

    def test_reidentify_rate_limit_returns_429_with_headers(self):
        os.environ["JUNAS_RATE_LIMIT_REIDENTIFY"] = "1"
        payload = {
            "anonymized_text": "Send [PERSON_1] the draft.",
            "mapping": [{"placeholder": "[PERSON_1]", "original_text": "Dr Jane Tan"}],
        }

        with TestClient(main.app) as client:
            first = client.post("/reidentify", json=payload)
            second = client.post("/reidentify", json=payload)

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], "reidentify rate limit exceeded")
        self.assertEqual(second.headers["X-RateLimit-Limit"], "1")
        self.assertEqual(second.headers["X-RateLimit-Remaining"], "0")
        self.assertIn("Retry-After", second.headers)

    def test_review_and_batch_classify_have_separate_rate_limit_buckets(self):
        os.environ["JUNAS_RATE_LIMIT_REVIEW"] = "1"
        os.environ["JUNAS_RATE_LIMIT_BATCH_CLASSIFY"] = "1"

        with TestClient(main.app) as client:
            review_first = client.post("/review", json={"text": "Internal lunch note."})
            review_second = client.post("/review", json={"text": "Internal lunch note."})
            batch_first = client.post("/classify/batch", json={"items": [{"text": "Internal lunch note."}]})
            batch_second = client.post("/classify/batch", json={"items": [{"text": "Internal lunch note."}]})

        self.assertEqual(review_first.status_code, 200, review_first.text)
        self.assertEqual(review_second.status_code, 429)
        self.assertEqual(review_second.json()["detail"], "review rate limit exceeded")
        self.assertEqual(batch_first.status_code, 200, batch_first.text)
        self.assertEqual(batch_second.status_code, 429)
        self.assertEqual(batch_second.json()["detail"], "batch_classify rate limit exceeded")

    def test_local_pairing_start_is_rate_limited(self):
        os.environ["JUNAS_RATE_LIMIT_LOCAL_PAIRING"] = "1"
        os.environ["JUNAS_LOCAL_DAEMON_ACL_ENABLED"] = "1"
        os.environ["JUNAS_LOCAL_DAEMON_TOKEN"] = "local-secret"
        headers = {"Origin": "https://chatgpt.com"}

        with TestClient(main.app) as client:
            first = client.post("/local/pairing/start", headers=headers, json={"client_name": "browser"})
            second = client.post("/local/pairing/start", headers=headers, json={"client_name": "browser"})

        self.assertEqual(first.status_code, 200, first.text)
        self.assertEqual(second.status_code, 429)
        self.assertEqual(second.json()["detail"], "local_pairing rate limit exceeded")

    def test_decision_rate_limit_covers_approval_and_decision_endpoints(self):
        os.environ["JUNAS_RATE_LIMIT_DECISION"] = "1"
        os.environ["JUNAS_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["JUNAS_JOURNAL_KEY"] = "rate-limit-journal-key"
        os.environ["JUNAS_REVIEW_PERSIST"] = "1"
        os.environ["JUNAS_SUBJECT_INDEX_KEY"] = "rate-limit-subject-index-key"

        with TestClient(main.app) as client:
            review = client.post("/review", json={"text": "Send Dr Jane Tan the draft."})
            self.assertEqual(review.status_code, 200, review.text)
            payload = review.json()
            finding_id = payload["findings"][0]["id"]
            approval = client.post(
                "/request-approval",
                json={"review_id": payload["request_id"], "finding_ids": [finding_id]},
            )
            decision = client.post(
                f"/review/{payload['request_id']}/decision",
                json={"finding_id": finding_id, "action": "approve"},
            )

        self.assertEqual(approval.status_code, 200, approval.text)
        self.assertEqual(decision.status_code, 429)
        self.assertEqual(decision.json()["detail"], "decision rate limit exceeded")


if __name__ == "__main__":
    unittest.main()
