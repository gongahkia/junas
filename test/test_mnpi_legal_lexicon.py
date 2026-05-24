"""Behavioural tests for the legal-contract MNPI rules: codename, definitive_agreement,
material_adverse_change, embargo_marker. Verifies firing, defined-term suppression, and that
transaction_codename does not bleed across newlines or false-positive on prose."""

import unittest

from kaypoh.review.engine import PreSendReviewEngine


def _rules(findings, rule_name):
    return [f for f in findings if f.rule == rule_name]


class MnpiLegalLexiconTests(unittest.TestCase):
    def setUp(self):
        self.engine = PreSendReviewEngine()

    def _review(self, text, document_type="SPA"):
        return self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
            document_type=document_type,
        )

    def test_transaction_codename_detected_titlecase(self):
        result = self._review("Status update on Project Raven; closing on track.")
        self.assertEqual([f.matched_text for f in _rules(result.findings, "transaction_codename")], ["Project Raven"])

    def test_transaction_codename_does_not_swallow_newline(self):
        text = "Project Raven\n\nInternal memorandum: the deal is on track."
        result = self._review(text)
        codenames = _rules(result.findings, "transaction_codename")
        self.assertEqual(len(codenames), 1)
        self.assertEqual(codenames[0].matched_text, "Project Raven")
        self.assertNotIn("Internal", codenames[0].matched_text)

    def test_transaction_codename_ignores_lowercase_prose(self):
        result = self._review("The project status is green and the project plan is on track.")
        self.assertEqual(_rules(result.findings, "transaction_codename"), [])

    def test_definitive_agreement_fires_on_full_titles_and_abbreviations(self):
        result = self._review(
            "Share Purchase Agreement attached. The MOU was exchanged. Term sheet executed."
        )
        names = {f.matched_text for f in _rules(result.findings, "definitive_agreement")}
        self.assertIn("Share Purchase Agreement", names)
        self.assertIn("MOU", names)

    def test_definitive_agreement_suppressed_when_abbreviation_is_a_defined_term(self):
        text = (
            'This Share Purchase Agreement (the "SPA") between Acme and Globex. '
            'Under the SPA, the Purchaser shall ...'
        )
        result = self._review(text)
        # full-title match must still fire
        matches = {f.matched_text for f in _rules(result.findings, "definitive_agreement")}
        self.assertIn("Share Purchase Agreement", matches)
        # standalone "SPA" tokens should be suppressed because the contract defines SPA as its own nickname
        self.assertNotIn("SPA", matches)

    def test_material_adverse_change_detects_clause_and_acronym(self):
        text = "The Purchaser may invoke the MAC clause upon any material adverse effect."
        result = self._review(text)
        mac = _rules(result.findings, "material_adverse_change")
        self.assertTrue(mac)
        forms = {f.matched_text for f in mac}
        self.assertIn("MAC clause", forms)
        self.assertIn("material adverse effect", forms)

    def test_embargo_marker_fires_on_closing_and_signing_dates(self):
        text = "Embargoed until announcement. Signing Date is 1 June 2026; Closing Date follows."
        result = self._review(text)
        markers = {f.matched_text for f in _rules(result.findings, "embargo_marker")}
        # all three should appear
        self.assertIn("Embargoed", markers)
        self.assertIn("Signing Date", markers)
        self.assertIn("Closing Date", markers)

    def test_new_rules_carry_cited_suggestions(self):
        text = "Project Atlas: MAC clause invoked before Closing Date. SHA executed."
        result = self.engine.review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="US",
            entity_id=None,
            include_suggestions=True,
            document_type="SPA",
        )
        rationales = " | ".join(s.rationale for s in result.suggestions)
        # rationale text should reference SG SFA and US SEC since both packs apply
        self.assertIn("Securities and Futures Act", rationales)
        self.assertIn("SEC insider-trading", rationales)


if __name__ == "__main__":
    unittest.main()
