import os
import tempfile
import unittest
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi.testclient import TestClient

import junas.backend.main as main
from junas.review import citations
from junas.review.engine import EntitySizeLookup, PreSendReviewEngine


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


class _Lookup(EntitySizeLookup):
    def lookup(self, entity_id, jurisdiction):
        return {"revenue": 1_000_000_000, "market_cap": 5_000_000_000}


class ConjunctiveMNPITests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()
        main._state.clear()
        main.app.openapi_schema = None
        self._orig_override = os.environ.get("JUNAS_CITATIONS_OVERRIDE")
        citations._CITATIONS_OVERRIDE_CACHE.clear()

    def tearDown(self):
        if self._orig_override is None:
            os.environ.pop("JUNAS_CITATIONS_OVERRIDE", None)
        else:
            os.environ["JUNAS_CITATIONS_OVERRIDE"] = self._orig_override
        citations._CITATIONS_OVERRIDE_CACHE.clear()

    def _conjunctive(self, text, *, engine=None, entity_id=None, include_suggestions=False):
        result = (engine or self.engine).review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="US",
            entity_id=entity_id,
            include_suggestions=include_suggestions,
            document_type="memo",
            review_profile="strict",
        )
        findings = [finding for finding in result.findings if finding.rule == "conjunctive_mnpi"]
        self.assertEqual(len(findings), 1)
        return findings[0], result

    def test_lexicalised_materiality_state(self):
        finding, result = self._conjunctive("Confidential Acme Corp acquisition before announcement.")
        self.assertEqual(finding.severity, "medium")
        self.assertEqual(result.overall_risk.value, "HIGH_RISK")
        self.assertEqual(finding.metadata["materiality_state"], "lexicalised")
        self.assertTrue(finding.metadata["non_public_element_satisfied"])
        self.assertTrue(finding.metadata["entity_element_satisfied"])
        self.assertIn("material_event", finding.metadata["element_rules"]["materiality"])

    def test_quantitative_materiality_state(self):
        engine = PreSendReviewEngine(entity_size_lookup=_Lookup())
        finding, _ = self._conjunctive(
            "Confidential Acme Corp value is $300 million.",
            engine=engine,
            entity_id="Acme Corp",
        )
        self.assertEqual(finding.metadata["materiality_state"], "quantitative")
        self.assertIn("financial_amount", finding.metadata["element_rules"]["materiality"])

    def test_implied_materiality_state(self):
        finding, _ = self._conjunctive(
            "Acme Corp confidential note: please share with select investors before the call."
        )
        self.assertEqual(finding.metadata["materiality_state"], "implied")
        self.assertIn("tipping_language", finding.metadata["element_rules"]["materiality"])

    def test_strict_mode_emits_review_required_when_materiality_undetermined(self):
        finding, _ = self._conjunctive("Acme Corp confidential board memo for internal circulation only.")
        self.assertEqual(finding.metadata["materiality_state"], "undetermined")
        self.assertTrue(finding.metadata["review_required"])
        self.assertIn("Review under SFA", finding.reason)

    def test_no_entity_or_public_source_does_not_emit(self):
        result = self.engine.review(
            text="Confidential acquisition before announcement.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
            review_profile="strict",
        )
        self.assertFalse([f for f in result.findings if f.rule == "conjunctive_mnpi"])

        public = self.engine.review(
            text="Acme Corp publicly announced acquisition at https://example.com/press.",
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type="memo",
            review_profile="strict",
        )
        self.assertFalse([f for f in public.findings if f.rule == "conjunctive_mnpi"])

    def test_citation_override_applies_to_conjunctive_suggestion(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "citations.toml"
            path.write_text(
                "[mnpi.conjunctive_mnpi]\n"
                'default = "Internal Trading Policy §12 — conjunctive MNPI review"\n',
                encoding="utf-8",
            )
            os.environ["JUNAS_CITATIONS_OVERRIDE"] = str(path)
            finding, result = self._conjunctive(
                "Confidential Acme Corp acquisition before announcement.",
                include_suggestions=True,
            )

        suggestion = next(item for item in result.suggestions if item.finding_id == finding.id)
        self.assertIn("Internal Trading Policy §12", suggestion.rationale)

    def test_api_response_includes_conjunctive_metadata(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": "Confidential Acme Corp acquisition before announcement.",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "memo",
                    "include_suggestions": False,
                },
            )

        self.assertEqual(response.status_code, 200)
        payload = response.json()
        finding = next(item for item in payload["findings"] if item["rule"] == "conjunctive_mnpi")
        self.assertEqual(finding["metadata"]["materiality_state"], "lexicalised")
        self.assertTrue(finding["metadata"]["entity_element_satisfied"])
