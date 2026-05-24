import unittest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

import backend.main as main
from kaypoh.review.citations import mnpi_rationale, pii_rationale


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


class CitationRationaleTests(unittest.TestCase):
    def test_pii_nric_rationale_cites_pdpa_and_pdpc_advisory(self):
        text = pii_rationale(rule="sg_nric_fin", jurisdiction="SG")
        self.assertIn("PDPA", text)
        self.assertIn("NRIC", text)
        self.assertIn("Personal Data Protection Act 2012", text)

    def test_pii_rationale_chains_multiple_jurisdictions(self):
        text = pii_rationale(rule="sg_nric_fin", jurisdiction="SG+US")
        self.assertIn("Personal Data Protection Act 2012", text)
        self.assertIn("US sectoral privacy law", text)

    def test_mnpi_material_event_cites_sfa_when_sg_present(self):
        text = mnpi_rationale(rule="material_event", jurisdiction="SG+US", severity="high")
        self.assertIn("Securities and Futures Act 2001", text)
        self.assertIn("SEC insider-trading guidance", text)

    def test_mnpi_low_severity_includes_public_appearance_softener(self):
        text = mnpi_rationale(rule="material_event", jurisdiction="SG", severity="low")
        self.assertIn("appears public", text)
        self.assertIn("Securities and Futures Act 2001", text)

    def test_pii_uen_rationale_calls_out_directors_officers(self):
        text = pii_rationale(rule="sg_uen", jurisdiction="SG")
        self.assertIn("UEN", text)
        self.assertIn("directors", text)


class CitedSuggestionsEndToEndTests(unittest.TestCase):
    def setUp(self):
        main._state.clear()
        main.app.openapi_schema = None

    def test_review_emits_pdpa_cited_suggestions(self):
        text = "Send Dr Jane Tan S1234567D the draft. Confidential acquisition for $2.5 billion."

        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "text": text,
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "US",
                    "document_type": "SPA",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        suggestions = payload["suggestions"]
        self.assertTrue(suggestions)

        # at least one PII suggestion should cite PDPA, and at least one MNPI suggestion should cite SFA.
        pii_suggestions = [
            s for s in suggestions if any(f["id"] == s["finding_id"] and f["category"] == "PII" for f in payload["findings"])
        ]
        mnpi_suggestions = [
            s for s in suggestions if any(f["id"] == s["finding_id"] and f["category"] == "MNPI" for f in payload["findings"])
        ]
        self.assertTrue(pii_suggestions, "expected PII suggestions for NRIC + named person")
        self.assertTrue(mnpi_suggestions, "expected MNPI suggestions for acquisition + monetary amount")
        self.assertTrue(any("PDPA" in s["rationale"] for s in pii_suggestions))
        self.assertTrue(any("Securities and Futures Act" in s["rationale"] for s in mnpi_suggestions))


if __name__ == "__main__":
    unittest.main()
