import unittest

from kaypoh.review.document_structure import parse_document_structure


class DocumentStructureTests(unittest.TestCase):
    def test_parses_headings_paragraphs_lists_and_signatures(self):
        text = (
            "1. Background\n"
            "Dr Jane Tan lives in Bukit Timah.\n"
            "\n"
            "- Passport copy attached\n"
            "| Name | Role |\n"
            "| Jane | CFO |\n"
            "Signature: Jane Tan\n"
        )
        structure = parse_document_structure(text)
        kinds = [unit.kind for unit in structure.units]

        self.assertIn("document", kinds)
        self.assertIn("heading", kinds)
        self.assertIn("paragraph", kinds)
        self.assertIn("list_item", kinds)
        self.assertIn("table_row", kinds)
        self.assertIn("signature_block", kinds)

    def test_containing_span_prefers_smallest_unit(self):
        text = "Definitions\n\"Company\" means Acme Pte Ltd.\n\nDr Jane Tan works at Acme.\n"
        structure = parse_document_structure(text)
        start = text.index("Jane")
        unit = structure.containing_span(start, start + len("Jane"))

        self.assertIsNotNone(unit)
        self.assertEqual(unit.kind, "paragraph")
        self.assertIn("works at", unit.text)

    def test_detects_defined_term_lines(self):
        text = "\"Purchaser\" means Raven Bidco Pte Ltd.\n"
        structure = parse_document_structure(text)

        self.assertTrue(any(unit.kind == "defined_term" for unit in structure.units))


if __name__ == "__main__":
    unittest.main()
