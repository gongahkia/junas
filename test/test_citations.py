import unittest
from contextlib import asynccontextmanager

from fastapi.testclient import TestClient

import kaypoh.backend.main as main
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

    def test_matched_text_prefixes_pii_rationale(self):
        text = pii_rationale(rule="sg_nric_fin", jurisdiction="SG", matched_text="S1234567D")
        self.assertTrue(text.startswith('"S1234567D" detected → '), text)

    def test_matched_text_prefixes_mnpi_rationale(self):
        text = mnpi_rationale(
            rule="transaction_codename",
            jurisdiction="SG",
            severity="high",
            matched_text="Project Atlas",
        )
        self.assertTrue(text.startswith('"Project Atlas" detected → '), text)

    def test_matched_text_collapses_whitespace_and_truncates(self):
        long_match = "x" * 200
        text = pii_rationale(rule="named_person", jurisdiction="SG", matched_text=long_match)
        # truncation marker present, full 200-char run absent
        self.assertIn("…", text)
        self.assertNotIn("x" * 100, text)

    def test_no_prefix_when_matched_text_empty(self):
        text = pii_rationale(rule="sg_nric_fin", jurisdiction="SG", matched_text="")
        self.assertFalse(text.startswith('"'))


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
            s
            for s in suggestions
            if any(f["id"] == s["finding_id"] and f["category"] == "PII" for f in payload["findings"])
        ]
        mnpi_suggestions = [
            s
            for s in suggestions
            if any(f["id"] == s["finding_id"] and f["category"] == "MNPI" for f in payload["findings"])
        ]
        self.assertTrue(pii_suggestions, "expected PII suggestions for NRIC + named person")
        self.assertTrue(mnpi_suggestions, "expected MNPI suggestions for acquisition + monetary amount")
        self.assertTrue(any("PDPA" in s["rationale"] for s in pii_suggestions))
        self.assertTrue(any("Securities and Futures Act" in s["rationale"] for s in mnpi_suggestions))

        # every PII suggestion's rationale should lead with the matched text in quotes
        for suggestion in pii_suggestions:
            finding = next(f for f in payload["findings"] if f["id"] == suggestion["finding_id"])
            quoted_prefix = f'"{finding["matched_text"]}" detected → '
            # named_person matches may include whitespace that gets collapsed in the prefix;
            # only assert prefix presence when matched_text is short and clean
            if "\n" not in finding["matched_text"] and len(finding["matched_text"]) <= 80:
                self.assertTrue(suggestion["rationale"].startswith(quoted_prefix), suggestion["rationale"])


if __name__ == "__main__":
    unittest.main()
