import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace

from fastapi.testclient import TestClient

import backend.main as main
from kaypoh.workflow.layer7_public_evidence.inference import PublicEvidenceRetriever
from kaypoh.workflow.privacy_guard import PrivacyGuard
from test import observability_test_app as test_app


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


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


class DummyLLMAdjudicator:
    def adjudicate(self, **kwargs):
        self.last_payload = kwargs
        return {
            "status": "adjudicated",
            "provider": "vllm",
            "model": "gpt-oss-20b",
            "risk_label": "SAFE",
            "public_status": "public",
            "confidence": 0.91,
            "materiality_reason": "The risky claim is matched to public evidence.",
            "matched_public_sources": ["https://example.com/acme-acquisition"],
            "unverified_claims": [],
            "review_recommendation": "No reviewer escalation required.",
            "input_mode": "structured_tokens",
            "output_clamped": False,
        }


class PublicEvidencePrivacyTests(unittest.TestCase):
    def test_public_evidence_queries_do_not_include_offending_values_or_pii(self):
        settings = SimpleNamespace(
            enabled=True,
            provider="exa",
            api_key="",
            endpoint="https://api.exa.ai/search",
            max_results=5,
            timeout_seconds=1.0,
        )
        guard = PrivacyGuard(max_query_chars=140, redact_exact_numbers=True)
        retriever = PublicEvidenceRetriever(settings, guard)

        payload = retriever.retrieve(
            text=(
                "Acme Corp will acquire GlobalTech for $2.5 billion. "
                "Contact banker jane.doe@example.com before announcement."
            ),
            entity_id="Acme Corp",
        )

        self.assertEqual(payload["status"], "skipped")
        self.assertTrue(payload["queries"])
        for item in payload["queries"]:
            query = item["query"]
            self.assertNotIn("$2.5", query)
            self.assertNotIn("billion", query.lower())
            self.assertNotIn("jane.doe", query)
            self.assertNotIn("example.com", query)
        self.assertTrue(all(entry["allowed"] for entry in payload["privacy_ledger"]))

    def test_public_evidence_does_not_infer_entities_from_private_text(self):
        settings = SimpleNamespace(
            enabled=True,
            provider="exa",
            api_key="",
            endpoint="https://api.exa.ai/search",
            max_results=5,
            timeout_seconds=1.0,
        )
        retriever = PublicEvidenceRetriever(settings, PrivacyGuard())

        payload = retriever.retrieve(
            text="Project Raven Holdings will acquire GlobalTech before the public announcement.",
            entity_id=None,
        )

        self.assertEqual(payload["status"], "skipped")
        self.assertEqual(payload["queries"], [])
        self.assertEqual(payload["privacy_ledger"], [])


class PublicEvidenceLLMApiTests(unittest.TestCase):
    def test_local_llm_adjudication_can_downgrade_public_model_only_risk(self):
        text = "Acme Corp announced its acquisition of GlobalTech in a public press release."
        llm = DummyLLMAdjudicator()
        test_app.seed_test_state(
            pipeline=["lexicon", "model1", "public_evidence", "llm_adjudicator"],
            models={
                "lexicon": test_app.DummyLexiconFilter(flagged=False),
                "model1": test_app.DummyModel1(label="risk", confidence=0.8, risk_score=0.8),
                "public_evidence": DummyPublicEvidence(),
                "llm_adjudicator": llm,
            },
        )

        with TestClient(test_app.app) as client:
            response = client.post("/classify", json={"text": text, "entity_id": "Acme Corp"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["classification"], "SAFE")
        self.assertEqual(payload["public_evidence"]["status"], "queried")
        self.assertEqual(payload["llm_adjudication"]["public_status"], "public")
        self.assertEqual(payload["privacy_ledger"][0]["destination"], "exa")
        self.assertEqual(payload["privacy_ledger"][1]["operation"], "llm_adjudication")
        self.assertEqual(payload["privacy_ledger"][1]["input_mode"], "structured_tokens")
        self.assertEqual(llm.last_payload["text"], text)


if __name__ == "__main__":
    unittest.main()
