import unittest
import zipfile
from io import BytesIO

from kaypoh.review.document_structure import parse_document_structure, parse_docx_structure


def _docx_bytes() -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        '<w:p><w:pPr><w:pStyle w:val="Heading1"/></w:pPr><w:r><w:t>Background</w:t></w:r></w:p>'
        '<w:p><w:pPr><w:numPr><w:ilvl w:val="0"/></w:numPr></w:pPr><w:r><w:t>Passport copy attached</w:t></w:r></w:p>'
        "<w:tbl><w:tr>"
        "<w:tc><w:p><w:r><w:t>Name</w:t></w:r></w:p></w:tc>"
        "<w:tc><w:p><w:r><w:t>Role</w:t></w:r></w:p></w:tc>"
        "</w:tr></w:tbl>"
        "</w:body></w:document>"
    )
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
        return buffer.getvalue()


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

    def test_parses_docx_styles_lists_and_table_cells(self):
        structure = parse_docx_structure(_docx_bytes())
        kinds = [unit.kind for unit in structure.units]

        self.assertIn("Background", structure.text)
        self.assertIn("Name | Role", structure.text)
        self.assertIn("heading", kinds)
        self.assertIn("list_item", kinds)
        self.assertIn("table_row", kinds)
        self.assertIn("table_cell", kinds)


if __name__ == "__main__":
    unittest.main()
