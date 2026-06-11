import unittest
from contextlib import asynccontextmanager
from types import SimpleNamespace
from unittest import mock

from fastapi.testclient import TestClient

import kaypoh.backend.main as main
from kaypoh.external.privacy_guard import PrivacyGuard
from kaypoh.external.public_evidence.inference import PublicEvidenceRetriever
from kaypoh.review.engine import Classification, ReviewResult
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
    def test_classify_stays_strict_deterministic_even_when_llm_layers_seeded(self):
        text = "Acme Corp announced its acquisition of GlobalTech in a public press release."
        llm = DummyLLMAdjudicator()
        test_app.seed_test_state(
            pipeline=["public_evidence", "llm_adjudicator"],
            models={
                "public_evidence": DummyPublicEvidence(),
                "llm_adjudicator": llm,
            },
        )

        with mock.patch("kaypoh.backend.main.emit_privacy_ledger_events") as emit_privacy_events:
            with TestClient(test_app.app) as client:
                response = client.post("/classify", json={"text": text, "entity_id": "Acme Corp"})

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["classification"], "LOW_RISK")
        self.assertIsNone(payload["public_evidence"])
        self.assertIsNone(payload["llm_adjudication"])
        self.assertEqual(payload["privacy_ledger"], [])
        self.assertEqual(payload["lexicon"], None)
        self.assertEqual(payload["model1"], None)
        self.assertEqual(payload["mosaic"], None)
        self.assertFalse(hasattr(llm, "last_payload"))
        emit_privacy_events.assert_called_once()
        self.assertEqual(emit_privacy_events.call_args.kwargs["endpoint"], "/classify")
        self.assertEqual(len(emit_privacy_events.call_args.args[0]), 0)

    def test_classify_surfaces_engine_degraded_modes(self):
        class DegradedEngine:
            def review(self, **kwargs):
                return ReviewResult(
                    overall_risk=Classification.SAFE,
                    document_score=0.0,
                    pii_score=0.0,
                    mnpi_score=0.0,
                    jurisdictions_applied=["SG"],
                    jurisdiction_policy="strictest_wins",
                    degraded_modes=[
                        {
                            "mode": "entity_size_lookup",
                            "status": "unavailable",
                            "reason": "entity_size_lookup is not configured",
                            "detail": {"entity_id": "Acme Corp"},
                        }
                    ],
                )

        with mock.patch("kaypoh.backend.main._build_review_engine", return_value=DegradedEngine()):
            response = main._classify_core(
                main.ClassifyRequest(text="Acme Corp revenue threshold check", entity_id="Acme Corp"),
                "req-1",
                "/classify",
            )

        self.assertTrue(response.observability.degraded)
        self.assertEqual(response.degraded_modes[0].mode, "entity_size_lookup")
        self.assertEqual(response.degraded_modes[0].status, "unavailable")


if __name__ == "__main__":
    unittest.main()
