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


@asynccontextmanager
async def _noop_lifespan(app):
    yield


class DummyPublicEvidence:
    def retrieve(self, *, text: str, entity_id: str | None = None, lexicon=None):
        return {
            "status": "queried",
            "provider": "exa",
            "detail": "retrieved 1 public sources",
            "queries": [
                {
                    "query": "Acme Corp acquisition SEC filing news",
                    "blocked": False,
                    "reason": "sanitized query approved",
                }
            ],
            "sources": [
                {
                    "title": "Acme announces acquisition",
                    "url": "https://example.com/acme-acquisition",
                    "published_date": "2026-01-02",
                    "author": "",
                    "highlights": ["Acme announced the transaction publicly."],
                    "text": "Acme announced the transaction publicly.",
                    "score": 0.9,
                }
            ],
            "privacy_ledger": [
                {
                    "destination": "exa",
                    "operation": "external_query",
                    "allowed": True,
                    "reason": "sanitized query approved",
                    "query": "Acme Corp acquisition SEC filing news",
                    "redactions": [],
                }
            ],
        }


class CitePublicSourceEndpointTests(unittest.TestCase):
    def setUp(self):
        self._old_lifespan = main.app.router.lifespan_context
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()
        main.app.openapi_schema = None

    def tearDown(self):
        main.app.router.lifespan_context = self._old_lifespan

    def test_cite_public_source_requires_url_timestamp_and_ledger(self):
        main._state["models"] = {"public_evidence": DummyPublicEvidence()}
        with TestClient(main.app) as client:
            response = client.post(
                "/cite-public-source",
                json={
                    "text": "Acme Corp announced its acquisition of GlobalTech in a public press release.",
                    "entity_id": "Acme Corp",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "email",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertEqual(payload["privacy_operation"], "cite_public_source")
        self.assertEqual(payload["citation_policy"], "audit_grade_public_evidence")
        self.assertEqual(payload["review_profile"], "audit_grade")
        self.assertEqual(payload["policy_decision"]["decision"], "warn")
        self.assertIn("cite_public_source", payload["policy_decision"]["recommended_actions"])
        citation = payload["citations"][0]
        self.assertEqual(citation["source_url"], "https://example.com/acme-acquisition")
        self.assertRegex(citation["retrieval_timestamp"], r"^20\d{2}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$")
        self.assertTrue(citation["privacy_ledger_entry"]["allowed"])
        self.assertEqual(citation["privacy_ledger_entry"]["operation"], "external_query")
        self.assertTrue(citation["finding_ids"])
        self.assertIn("policy default@2026-06-14", citation["audit_rationale"])
        self.assertNotIn("GlobalTech", citation["audit_rationale"])
        self.assertTrue(payload["public_evidence"]["sources"])
        self.assertTrue(payload["privacy_ledger"])
        self.assertIn("cite_public_source", payload["timings_ms"])

    def test_cite_public_source_fails_without_public_evidence_source_and_ledger(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/cite-public-source",
                json={
                    "text": "Acme Corp will acquire GlobalTech before announcement.",
                    "entity_id": "Acme Corp",
                },
            )

        self.assertEqual(response.status_code, 409)
        self.assertIn("source URL", response.text)

    def test_cite_public_source_rejects_strict_profile(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/cite-public-source",
                json={
                    "text": "Acme Corp will acquire GlobalTech before announcement.",
                    "review_profile": "strict",
                },
            )

        self.assertEqual(response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
