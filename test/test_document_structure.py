import base64
import unittest
import zipfile
from io import BytesIO
from types import SimpleNamespace

from junas.review.document import SUPPORTED_XLSX_MIME, extract_review_document
from junas.review.document_structure import (
    parse_document_structure,
    parse_docx_structure,
    parse_eml_structure,
    parse_pdf_structure,
    parse_pptx_structure,
    parse_xlsx_structure,
)


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


def _xlsx_bytes() -> bytes:
    workbook_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheets><sheet name=\"People\" sheetId=\"1\" r:id=\"rId1\" "
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"/></sheets>'
        "</workbook>"
    )
    shared_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<si><t>Name</t></si><si><t>Dr Jane Tan</t></si><si><t>CFO</t></si>"
        "</sst>"
    )
    sheet_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
        "<sheetData><row r=\"1\"><c t=\"s\"><v>0</v></c><c t=\"s\"><v>1</v></c>"
        "<c t=\"s\"><v>2</v></c></row></sheetData></worksheet>"
    )
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("xl/workbook.xml", workbook_xml)
            archive.writestr("xl/sharedStrings.xml", shared_xml)
            archive.writestr("xl/worksheets/sheet1.xml", sheet_xml)
        return buffer.getvalue()


def _pptx_bytes() -> bytes:
    presentation_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>'
    )
    slide_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Project Atlas confidential</a:t>"
        "</a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:sld>"
    )
    notes_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
        "<p:cSld><p:spTree><p:sp><p:txBody><a:p><a:r><a:t>Speaker note: call Ms Tan</a:t>"
        "</a:r></a:p></p:txBody></p:sp></p:spTree></p:cSld></p:notes>"
    )
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("ppt/presentation.xml", presentation_xml)
            archive.writestr("ppt/slides/slide1.xml", slide_xml)
            archive.writestr("ppt/notesSlides/notesSlide1.xml", notes_xml)
        return buffer.getvalue()


def _eml_bytes() -> bytes:
    return (
        "From: Jane Tan <jane@example.sg>\n"
        "To: Legal <legal@example.sg>\n"
        "Subject: Project Atlas\n"
        "Content-Type: text/plain; charset=utf-8\n"
        "\n"
        "Dr Jane Tan is 42 years old and lives in Singapore 068810.\n"
    ).encode("utf-8")


def _pdf_bytes() -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import DictionaryObject, NameObject, StreamObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = writer._add_object(
        DictionaryObject({
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        })
    )
    page[NameObject("/Resources")] = DictionaryObject({
        NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})
    })
    stream = StreamObject()
    stream._data = b"BT /F1 12 Tf 72 720 Td (Dr Jane Tan Age 42) Tj ET"
    page[NameObject("/Contents")] = writer._add_object(stream)
    with BytesIO() as buffer:
        writer.write(buffer)
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

    def test_parses_xlsx_sheets_rows_and_cells(self):
        structure = parse_xlsx_structure(_xlsx_bytes())
        kinds = [unit.kind for unit in structure.units]

        self.assertIn("Sheet: People", structure.text)
        self.assertIn("Dr Jane Tan", structure.text)
        self.assertIn("sheet", kinds)
        self.assertIn("table_row", kinds)
        self.assertIn("table_cell", kinds)

    def test_parses_pptx_slides_and_speaker_notes(self):
        structure = parse_pptx_structure(_pptx_bytes())
        kinds = [unit.kind for unit in structure.units]

        self.assertIn("Project Atlas confidential", structure.text)
        self.assertIn("Speaker note: call Ms Tan", structure.text)
        self.assertIn("slide", kinds)
        self.assertIn("speaker_notes", kinds)

    def test_parses_eml_headers_and_body(self):
        structure = parse_eml_structure(_eml_bytes())
        kinds = [unit.kind for unit in structure.units]

        self.assertIn("Project Atlas", structure.text)
        self.assertIn("Dr Jane Tan", structure.text)
        self.assertIn("email_header", kinds)
        self.assertIn("email_body", kinds)

    def test_parses_pdf_pages(self):
        structure = parse_pdf_structure(_pdf_bytes())
        unit = structure.containing_span(structure.text.index("Jane"), structure.text.index("Jane") + len("Jane"))

        self.assertIn("Dr Jane Tan", structure.text)
        self.assertIsNotNone(unit)
        self.assertEqual(unit.kind, "page")

    def test_xlsx_extraction_passes_structure_through(self):
        payload = SimpleNamespace(
            document_base64=base64.b64encode(_xlsx_bytes()).decode("ascii"),
            document_filename="people.xlsx",
            document_mime_type=SUPPORTED_XLSX_MIME,
        )
        document = extract_review_document(payload)

        self.assertIn("Dr Jane Tan", document.text)
        self.assertIsNotNone(document.document_structure)
        self.assertIn("table_cell", [unit.kind for unit in document.document_structure.units])


if __name__ == "__main__":
    unittest.main()
