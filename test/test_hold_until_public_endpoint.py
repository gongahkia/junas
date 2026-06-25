import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import kaypoh.backend.main as main


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class HoldUntilPublicEndpointTests(unittest.TestCase):
    def setUp(self):
        self._old_lifespan = main.app.router.lifespan_context
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()
        main.app.openapi_schema = None

    def tearDown(self):
        main.app.router.lifespan_context = self._old_lifespan

    def test_hold_until_public_returns_user_reason_and_audit_rationale(self):
        text = "Acme Corp will acquire GlobalTech before announcement."
        with TestClient(main.app) as client:
            response = client.post(
                "/hold-until-public",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["privacy_operation"], "hold_until_public")
        self.assertEqual(payload["rewrite_policy"], "mnpi_hold_allowed_spans")
        self.assertEqual(payload["rewritten_text"], "[HOLD UNTIL PUBLIC DISCLOSURE OR APPROVAL]")
        self.assertTrue(payload["replacements"])
        self.assertTrue(all(replacement["action"] == "hold_until_public" for replacement in payload["replacements"]))
        self.assertTrue(payload["hold_reasons"])
        reason = payload["hold_reasons"][0]
        self.assertIn("public disclosure", reason["user_reason"])
        self.assertIn("policy default@2026-06-14", reason["audit_rationale"])
        self.assertIn(reason["finding_id"], reason["audit_rationale"])
        self.assertNotIn("GlobalTech", reason["user_reason"])
        self.assertNotIn("GlobalTech", reason["audit_rationale"])
        self.assertFalse(payload["mapping_persisted"])
        self.assertIn("hold_until_public", payload["timings_ms"])

    def test_hold_until_public_rejects_non_hold_actions(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/hold-until-public",
                json={
                    "text": "Send Dr Jane Tan S1234567D to external counsel.",
                    "allowed_actions": ["redact_pii"],
                },
            )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
