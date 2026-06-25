import sys
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
SRC_ROOT = ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import junas.backend.main as main
from junas.backend.schemas import PolicyDecisionResponse, SafeRewriteRequest


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class SafeRewriteEndpointTests(unittest.TestCase):
    def setUp(self):
        self._old_lifespan = main.app.router.lifespan_context
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()
        main.app.openapi_schema = None

    def tearDown(self):
        main.app.router.lifespan_context = self._old_lifespan

    def test_safe_rewrite_redacts_policy_approved_pii_spans(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/safe-rewrite",
                json={
                    "text": "Send Dr Jane Tan S1234567D to external counsel.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                    "surface": "outlook",
                    "workflow": "email_send",
                    "requested_action": "safe_rewrite",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["privacy_operation"], "safe_rewrite")
        self.assertEqual(payload["rewrite_policy"], "deterministic_allowed_spans")
        self.assertFalse(payload["mapping_persisted"])
        self.assertIn("[REDACTED PERSONAL DATA]", payload["rewritten_text"])
        self.assertNotIn("S1234567D", payload["rewritten_text"])
        self.assertTrue(payload["replacements"])
        self.assertIn("safe_rewrite", payload["timings_ms"])
        self.assertTrue(all("finding_id" in replacement for replacement in payload["replacements"]))
        self.assertTrue(all(len(replacement["original_text_hash"]) == 64 for replacement in payload["replacements"]))
        self.assertTrue(all("original_text" not in replacement for replacement in payload["replacements"]))

    def test_safe_rewrite_holds_policy_approved_mnpi_spans(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/safe-rewrite",
                json={
                    "text": "Acme Corp will acquire GlobalTech before announcement.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                    "surface": "outlook",
                    "workflow": "email_send",
                    "requested_action": "safe_rewrite",
                    "allowed_actions": ["hold_until_public"],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertIn("[HOLD UNTIL PUBLIC DISCLOSURE OR APPROVAL]", payload["rewritten_text"])
        self.assertTrue(any(replacement["action"] == "hold_until_public" for replacement in payload["replacements"]))

    def test_safe_rewrite_does_not_apply_unapproved_actions(self):
        text = "Send Dr Jane Tan S1234567D to external counsel."
        with TestClient(main.app) as client:
            response = client.post(
                "/safe-rewrite",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                    "allowed_actions": ["hold_until_public"],
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["rewritten_text"], text)
        self.assertEqual(payload["replacements"], [])
        self.assertTrue(payload["skipped_findings"])

    def test_safe_rewrite_handles_mixed_pii_and_mnpi_findings(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/safe-rewrite",
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
        actions = {replacement["action"] for replacement in payload["replacements"]}
        self.assertIn("[REDACTED PERSONAL DATA]", payload["rewritten_text"])
        self.assertIn("[HOLD UNTIL PUBLIC DISCLOSURE OR APPROVAL]", payload["rewritten_text"])
        self.assertTrue(actions & {"redact_pii", "safe_rewrite"})
        self.assertIn("hold_until_public", actions)

    def test_safe_rewrite_resolves_overlapping_spans_deterministically(self):
        request = SafeRewriteRequest.model_validate({"text": "abcdef"})
        policy_decision = PolicyDecisionResponse(
            decision="block",
            send_allowed=False,
            required_actions=["redact_pii", "hold_until_public"],
            recommended_actions=[],
            blocking_findings=["m1", "p1", "p2"],
            policy_id="default",
            policy_version="2026-06-14",
            policy_reasons=[],
            review_id="review-1",
        )
        replacements, skipped = main._safe_rewrite_plan(
            text="abcdef",
            findings=[
                dict(id="m1", category="MNPI", rule="material_event", severity="high", start_char=0, end_char=6),
                dict(id="p1", category="PII", rule="named_person", severity="high", start_char=0, end_char=4),
                dict(id="p2", category="PII", rule="email_address", severity="high", start_char=1, end_char=3),
            ],
            policy_decision=policy_decision,
            req=request,
        )

        self.assertEqual([replacement.finding_id for replacement in replacements], ["p1"])
        self.assertEqual(
            {finding.finding_id: finding.reason for finding in skipped},
            {
                "m1": "overlaps with higher-priority replacement",
                "p2": "overlaps with higher-priority replacement",
            },
        )

    def test_safe_rewrite_noops_safe_documents(self):
        text = "This public update is safe to share."
        with TestClient(main.app) as client:
            response = client.post("/safe-rewrite", json={"text": text})

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["rewritten_text"], text)
        self.assertEqual(payload["replacements"], [])
        self.assertEqual(payload["skipped_findings"], [])


if __name__ == "__main__":
    unittest.main()
