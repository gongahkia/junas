import unittest
from types import SimpleNamespace

from junas.external.privacy_guard import PrivacyGuard
from junas.external.public_evidence.inference import PublicEvidenceRetriever


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


if __name__ == "__main__":
    unittest.main()
