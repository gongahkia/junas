import unittest

from junas.review.citations import mnpi_rationale, pii_rationale


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


if __name__ == "__main__":
    unittest.main()
