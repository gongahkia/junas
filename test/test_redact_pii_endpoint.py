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


class RedactPiiEndpointTests(unittest.TestCase):
    def setUp(self):
        self._old_lifespan = main.app.router.lifespan_context
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()
        main.app.openapi_schema = None

    def tearDown(self):
        main.app.router.lifespan_context = self._old_lifespan

    def test_redact_pii_only_leaves_mnpi_visible_and_flagged(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/redact-pii",
                json={
                    "text": (
                        "Send Dr Jane Tan S1234567D to external counsel.\n\n"
                        "Acme Corp will acquire GlobalTech before announcement."
                    ),
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["privacy_operation"], "redact_pii")
        self.assertEqual(payload["rewrite_policy"], "pii_only_allowed_spans")
        self.assertIn("[REDACTED PERSONAL DATA]", payload["rewritten_text"])
        self.assertNotIn("S1234567D", payload["rewritten_text"])
        self.assertIn("Acme Corp will acquire GlobalTech before announcement", payload["rewritten_text"])
        self.assertNotIn("[HOLD UNTIL PUBLIC DISCLOSURE OR APPROVAL]", payload["rewritten_text"])
        self.assertTrue(payload["replacements"])
        self.assertTrue(all(replacement["action"] == "redact_pii" for replacement in payload["replacements"]))
        self.assertTrue(any(finding["category"] == "MNPI" for finding in payload["findings"]))
        self.assertTrue(any("leaves MNPI visible" in finding["reason"] for finding in payload["skipped_findings"]))
        self.assertFalse(payload["mapping_persisted"])
        self.assertIn("redact_pii", payload["timings_ms"])

    def test_redact_pii_rejects_non_pii_actions(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/redact-pii",
                json={
                    "text": "Acme Corp will acquire GlobalTech before announcement.",
                    "allowed_actions": ["hold_until_public"],
                },
            )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
