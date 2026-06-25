import importlib
import json
import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class PolicyDecisionJournalTests(unittest.TestCase):
    def setUp(self):
        self._tmpdir = tempfile.TemporaryDirectory()
        self.tmpdir = Path(self._tmpdir.name)
        os.environ["JUNAS_JOURNAL_DIR"] = str(self.tmpdir)
        os.environ["JUNAS_JOURNAL_KEY"] = "policy-journal-test-key"
        os.environ["JUNAS_REVIEW_PERSIST"] = "1"
        os.environ["JUNAS_SUBJECT_INDEX_KEY"] = "subject-index-test-key"

        import junas.backend.main as main_mod
        import junas.review.decisions as decisions_mod
        import junas.review.journal as journal_mod

        importlib.reload(journal_mod)
        importlib.reload(decisions_mod)
        importlib.reload(main_mod)
        self.main = main_mod
        self.decisions = decisions_mod
        self.journal = journal_mod
        self.main._state.clear()
        self.main.app.openapi_schema = None
        self.main.app.router.lifespan_context = _noop_lifespan

    def tearDown(self):
        self._tmpdir.cleanup()
        for var in (
            "JUNAS_JOURNAL_DIR",
            "JUNAS_JOURNAL_KEY",
            "JUNAS_REVIEW_PERSIST",
            "JUNAS_SUBJECT_INDEX_KEY",
        ):
            os.environ.pop(var, None)
        import junas.backend.main as main_mod

        importlib.reload(main_mod)

    def test_policy_decision_event_uses_hashes_counts_and_policy_version(self):
        raw_text = "Send Dr Jane Tan S1234567D the confidential draft."
        with TestClient(self.main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": raw_text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        review_id = response.json()["request_id"]
        entries = self.journal.read_journal(review_id=review_id)
        policy_events = [
            entry for entry in entries
            if entry.event_type == self.decisions.EVENT_POLICY_DECISION_RECORDED
        ]
        self.assertEqual(len(policy_events), 1)
        payload = policy_events[0].payload

        self.assertEqual(payload["policy_id"], "default")
        self.assertEqual(payload["policy_version"], "2026-06-14")
        self.assertEqual(len(payload["document_hash"]), 64)
        self.assertGreaterEqual(payload["finding_count"], 1)
        self.assertIn("policy_reason_hashes", payload)
        self.assertIn("required_action_hashes", payload)
        self.assertNotIn("policy_reasons", payload)
        self.assertNotIn("required_actions", payload)

        serialized = json.dumps(payload, sort_keys=True)
        self.assertNotIn(raw_text, serialized)
        self.assertNotIn("Jane Tan", serialized)
        self.assertNotIn("S1234567D", serialized)
        self.assertNotIn("request_approval", serialized)

        state = self.decisions.get_session_state(review_id=review_id)
        self.assertEqual(len(state["policy_decisions"]), 1)


if __name__ == "__main__":
    unittest.main()
