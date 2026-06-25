import unittest

from junas.review.defined_terms import extract_defined_terms, is_defined_term


class DefinedTermExtractionTests(unittest.TestCase):
    def test_extracts_parenthetical_quoted_terms(self):
        text = (
            'This Agreement (the "Agreement") is between Acme Pte Ltd (the "Vendor") '
            'and Globex Pte Ltd (the "Purchaser").'
        )
        self.assertEqual(extract_defined_terms(text), {"agreement", "vendor", "purchaser"})

    def test_extracts_collectively_form(self):
        text = '(collectively, the "Sellers") and (collectively the "Parties")'
        self.assertEqual(extract_defined_terms(text), {"sellers", "parties"})

    def test_extracts_means_form(self):
        text = '"Company" means Acme. "Buyer" shall mean Globex.'
        self.assertEqual(extract_defined_terms(text), {"company", "buyer"})

    def test_ignores_lowercase_quoted_fragments(self):
        # only Title Case fragments anchor defined-term suppression to avoid eating ordinary quotes.
        text = '"hello world" means greeting'
        self.assertEqual(extract_defined_terms(text), set())

    def test_is_defined_term_strips_honorific(self):
        defined = {"purchaser", "vendor"}
        self.assertTrue(is_defined_term("Dr Purchaser", defined))
        self.assertTrue(is_defined_term("vendor", defined))
        self.assertFalse(is_defined_term("Jane Tan", defined))
        self.assertFalse(is_defined_term("Purchaser", set()))


if __name__ == "__main__":
    unittest.main()
