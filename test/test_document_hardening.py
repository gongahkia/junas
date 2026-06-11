import base64
import email
import unittest
import zipfile
from contextlib import asynccontextmanager
from email.message import EmailMessage
from io import BytesIO

from fastapi.testclient import TestClient

import kaypoh.backend.main as main
from kaypoh.review.container_scan import scan_container
from kaypoh.review.metadata import inspect_metadata


@asynccontextmanager
async def _noop_lifespan(app):
    yield


main.app.router.lifespan_context = _noop_lifespan


def _docx_bytes() -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        '<w:p><w:ins w:author="Priya Raman" w:date="2026-05-25T01:02:03Z">'
        "<w:r><w:t>Send passport no. E1234567 to Dr Jane Tan.</w:t></w:r>"
        "</w:ins></w:p>"
        "</w:body></w:document>"
    )
    core_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<cp:coreProperties xmlns:cp="http://schemas.openxmlformats.org/package/2006/metadata/core-properties" '
        'xmlns:dc="http://purl.org/dc/elements/1.1/">'
        "<dc:creator>Priya Raman</dc:creator>"
        "<cp:lastModifiedBy>Legal Ops</cp:lastModifiedBy>"
        "</cp:coreProperties>"
    )
    comments_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:comment w:id="0" w:author="Jane Reviewer"><w:p><w:r><w:t>Check this NRIC.</w:t></w:r></w:p></w:comment>'
        "</w:comments>"
    )
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
            archive.writestr("docProps/core.xml", core_xml)
            archive.writestr("word/comments.xml", comments_xml)
        return buffer.getvalue()


def _docx_weird_comments_and_track_changes() -> bytes:
    document_xml = (
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
        '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        "<w:body>"
        '<w:p><w:del w:author="Priya Raman" w:date="2026-05-26T01:02:03Z">'
        "<w:r><w:delText>Deleted NRIC S1234567D.</w:delText></w:r>"
        "</w:del></w:p>"
        '<w:p><w:moveTo w:author="Jane Reviewer" w:date="2026-05-26T02:03:04Z">'
        "<w:r><w:t>Moved passport E1234567.</w:t></w:r>"
        "</w:moveTo></w:p>"
        "</w:body></w:document>"
    )
    comments_xml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<w:comments xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
        '<w:comment w:id="0" w:author="Jane Reviewer">'
        "<w:p><w:r><w:t>Comment mentions Dr Jane Tan.</w:t></w:r></w:p>"
        "</w:comment></w:comments>"
    )
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("word/document.xml", document_xml)
            archive.writestr("word/comments.xml", comments_xml)
        return buffer.getvalue()


def _xlsx_with_hidden_sheet() -> bytes:
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "xl/workbook.xml",
                (
                    '<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<sheets><sheet name="Visible" sheetId="1"/>'
                    '<sheet name="Hidden" sheetId="2" state="hidden"/></sheets>'
                    '<definedNames><definedName name="SecretRange">Hidden!$A$1</definedName></definedNames>'
                    "</workbook>"
                ),
            )
            archive.writestr(
                "xl/sharedStrings.xml",
                (
                    '<sst xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    "<si><t>Dr Jane Tan S1234567D</t></si></sst>"
                ),
            )
            archive.writestr(
                "xl/pivotCache/pivotCacheRecords1.xml",
                (
                    '<pivotCacheRecords xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">'
                    '<r><s v="Tan S1234567D"/></r></pivotCacheRecords>'
                ),
            )
        return buffer.getvalue()


def _eml_with_forwarded_message() -> bytes:
    inner = EmailMessage()
    inner["From"] = "Jane Tan <jane@example.sg>"
    inner["To"] = "Deal Team <deal@example.sg>"
    inner["Subject"] = "Project Atlas forwarded"
    inner.set_content("Forwarded body contains S1234567D for review.")
    outer = EmailMessage()
    outer["From"] = "sender@example.com"
    outer["To"] = "legal@example.sg"
    outer["Subject"] = "Outlook export"
    outer.set_content("Forwarded message attached.")
    outer.add_attachment(inner, filename="forwarded.eml")
    return outer.as_bytes(policy=email.policy.default)


def _pptx_with_notes() -> bytes:
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "ppt/presentation.xml",
                '<p:presentation xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main"/>',
            )
            archive.writestr(
                "ppt/slides/slide1.xml",
                '<p:sld xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                "<a:t>Public slide</a:t></p:sld>",
            )
            archive.writestr(
                "ppt/notesSlides/notesSlide1.xml",
                '<p:notes xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                "<a:t>Speaker note: S1234567D</a:t></p:notes>",
            )
            archive.writestr(
                "ppt/slideMasters/slideMaster1.xml",
                '<p:sldMaster xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
                'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">'
                "<a:t>Master contains Jane Tan</a:t></p:sldMaster>",
            )
        return buffer.getvalue()


def _zip_bytes(name: str, payload: bytes) -> bytes:
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(name, payload)
        return buffer.getvalue()


def _docx_with_media_and_object() -> bytes:
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr(
                "word/document.xml",
                (
                    '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                    "<w:body><w:p><w:r><w:t>Visible text.</w:t></w:r></w:p></w:body></w:document>"
                ),
            )
            archive.writestr("word/media/image1.png", b"\x89PNG\r\n\x1a\n")
            archive.writestr("word/embeddings/oleObject1.bin", b"ole payload")
        return buffer.getvalue()


def _pdf_with_xfa_and_signature() -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import ArrayObject, DictionaryObject, NameObject, NumberObject, TextStringObject

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    signature_value = DictionaryObject({
        NameObject("/Type"): NameObject("/Sig"),
        NameObject("/ByteRange"): ArrayObject([NumberObject(0), NumberObject(10), NumberObject(20), NumberObject(30)]),
        NameObject("/Name"): TextStringObject("Priya Raman"),
        NameObject("/Reason"): TextStringObject("approved"),
    })
    signature_field = DictionaryObject({
        NameObject("/FT"): NameObject("/Sig"),
        NameObject("/T"): TextStringObject("ApprovalSignature"),
        NameObject("/V"): writer._add_object(signature_value),
    })
    acroform = DictionaryObject({
        NameObject("/Fields"): ArrayObject([writer._add_object(signature_field)]),
        NameObject("/XFA"): TextStringObject("<template/>"),
    })
    writer._root_object.update({NameObject("/AcroForm"): writer._add_object(acroform)})
    with BytesIO() as buffer:
        writer.write(buffer)
        return buffer.getvalue()


def _pdf_with_annotation_and_form() -> bytes:
    from pypdf import PdfWriter
    from pypdf.generic import (
        ArrayObject,
        DictionaryObject,
        NameObject,
        NumberObject,
        StreamObject,
        TextStringObject,
    )

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
    stream._data = b"BT /F1 12 Tf 72 720 Td (Enough extractable text for review.) Tj ET"
    page[NameObject("/Contents")] = writer._add_object(stream)
    annotation = DictionaryObject({
        NameObject("/Type"): NameObject("/Annot"),
        NameObject("/Subtype"): NameObject("/Text"),
        NameObject("/Rect"): ArrayObject([NumberObject(10), NumberObject(10), NumberObject(40), NumberObject(40)]),
        NameObject("/Contents"): TextStringObject("Annotation contains S1234567D."),
        NameObject("/T"): TextStringObject("Jane Reviewer"),
    })
    page[NameObject("/Annots")] = ArrayObject([writer._add_object(annotation)])
    text_field = DictionaryObject({
        NameObject("/FT"): NameObject("/Tx"),
        NameObject("/T"): TextStringObject("ReviewerField"),
        NameObject("/TU"): TextStringObject("Hidden review field"),
        NameObject("/V"): TextStringObject("Form value contains passport E1234567."),
    })
    acroform = DictionaryObject({
        NameObject("/Fields"): ArrayObject([writer._add_object(text_field)])
    })
    writer._root_object.update({NameObject("/AcroForm"): writer._add_object(acroform)})
    with BytesIO() as buffer:
        writer.write(buffer)
        return buffer.getvalue()


def _blank_pdf_base64() -> str:
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    with BytesIO() as buffer:
        writer.write(buffer)
        return base64.b64encode(buffer.getvalue()).decode("ascii")


def _text_pdf_base64() -> str:
    lines = [
        "%PDF-1.4",
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        (
            "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            "/Resources << /Font << /F1 4 0 R >> >> /Contents 5 0 R >> endobj"
        ),
        "4 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
        "5 0 obj << /Length 80 >> stream",
        "BT /F1 12 Tf 72 720 Td (Hello Jane Tan with enough extractable text for review.) Tj ET",
        "endstream endobj",
        "xref",
        "0 6",
        "0000000000 65535 f ",
        "0000000009 00000 n ",
        "0000000058 00000 n ",
        "0000000115 00000 n ",
        "0000000241 00000 n ",
        "0000000311 00000 n ",
        "trailer << /Root 1 0 R /Size 6 >>",
        "startxref",
        "441",
        "%%EOF",
    ]
    pdf = ("\n".join(lines) + "\n").encode("ascii")
    return base64.b64encode(pdf).decode("ascii")


class DocumentHardeningTests(unittest.TestCase):
    def setUp(self):
        main.app.router.lifespan_context = _noop_lifespan
        main._state.clear()
        main.app.openapi_schema = None

    def test_docx_metadata_findings_are_separate_from_text_findings(self):
        encoded = base64.b64encode(_docx_bytes()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "document_base64": encoded,
                    "document_filename": "draft.docx",
                    "source_jurisdiction": "SG",
                    "destination_jurisdiction": "SG",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        sources = {finding["source"] for finding in payload["document"]["metadata_findings"]}
        self.assertIn("docx_core_properties", sources)
        self.assertIn("docx_comments", sources)
        self.assertIn("docx_track_changes", sources)
        self.assertTrue(any(finding["rule"] == "passport_number" for finding in payload["findings"]))

    def test_docx_scrub_removes_metadata_parts_and_track_change_attrs(self):
        encoded = base64.b64encode(_docx_bytes()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/documents/scrub",
                json={
                    "document_base64": encoded,
                    "document_filename": "draft.docx",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(payload["scrubbed"])
        self.assertTrue(payload["metadata_findings"])
        scrubbed = base64.b64decode(payload["document_base64"])
        with zipfile.ZipFile(BytesIO(scrubbed)) as archive:
            names = set(archive.namelist())
            self.assertNotIn("docProps/core.xml", names)
            self.assertNotIn("word/comments.xml", names)
            document_xml = archive.read("word/document.xml").decode("utf-8")
        self.assertNotIn("Priya Raman", document_xml)
        self.assertNotIn("2026-05-25T01:02:03Z", document_xml)

    def test_pdf_without_text_layer_fails_closed(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "document_base64": _blank_pdf_base64(),
                    "document_filename": "scan.pdf",
                },
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("failed closed", response.json()["detail"])

    def test_pdf_with_text_layer_passes_quality_gate(self):
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={
                    "document_base64": _text_pdf_base64(),
                    "document_filename": "memo.pdf",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(response.json()["document"]["extraction_method"], "pypdf")

    def test_pdf_metadata_scrub_removes_author(self):
        from pypdf import PdfReader, PdfWriter

        writer = PdfWriter()
        writer.add_blank_page(width=72, height=72)
        writer.add_metadata({"/Author": "Priya Raman"})
        with BytesIO() as buffer:
            writer.write(buffer)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        with TestClient(main.app) as client:
            response = client.post(
                "/documents/scrub",
                json={"document_base64": encoded, "document_filename": "memo.pdf"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(any(finding["field"] == "Author" for finding in payload["metadata_findings"]))
        scrubbed = base64.b64decode(payload["document_base64"])
        metadata = PdfReader(BytesIO(scrubbed)).metadata or {}
        self.assertNotIn("/Author", metadata)

    def test_image_exif_scrub_removes_artist(self):
        try:
            from PIL import Image
        except Exception:
            self.skipTest("Pillow is not installed")

        image = Image.new("RGB", (10, 10), color=(255, 255, 255))
        exif = Image.Exif()
        exif[315] = "Priya Raman"  # Artist
        with BytesIO() as buffer:
            image.save(buffer, format="JPEG", exif=exif)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        with TestClient(main.app) as client:
            response = client.post(
                "/documents/scrub",
                json={
                    "document_base64": encoded,
                    "document_filename": "photo.jpg",
                },
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(any(finding["field"] == "Artist" for finding in payload["metadata_findings"]))
        remaining = inspect_metadata(
            base64.b64decode(payload["document_base64"]),
            filename="photo.jpg",
            mime_type="image/jpeg",
        )
        self.assertFalse(any(finding.field == "Artist" for finding in remaining))

    def test_docx_hidden_parts_are_extracted_for_review(self):
        document_xml = (
            '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:body><w:p><w:r><w:t>Visible text only.</w:t></w:r></w:p></w:body></w:document>"
        )
        footnotes_xml = (
            '<w:footnotes xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
            "<w:footnote><w:p><w:r><w:t>S1234567D in footnote.</w:t></w:r></w:p></w:footnote></w:footnotes>"
        )
        with BytesIO() as buffer:
            with zipfile.ZipFile(buffer, "w") as archive:
                archive.writestr("word/document.xml", document_xml)
                archive.writestr("word/footnotes.xml", footnotes_xml)
            encoded = base64.b64encode(buffer.getvalue()).decode("ascii")

        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "draft.docx"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(any(finding["rule"] == "sg_nric_fin" for finding in response.json()["findings"]))
        sources = {finding["source"] for finding in response.json()["document"]["metadata_findings"]}
        self.assertIn("docx_hidden_part", sources)

    def test_docx_weird_comments_and_track_changes_are_reviewed(self):
        encoded = base64.b64encode(_docx_weird_comments_and_track_changes()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "weird-comments.docx"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        rules = {finding["rule"] for finding in payload["findings"]}
        sources = {finding["source"] for finding in payload["document"]["metadata_findings"]}
        self.assertIn("sg_nric_fin", rules)
        self.assertIn("passport_number", rules)
        self.assertIn("docx_comments", sources)
        self.assertIn("docx_track_changes", sources)

    def test_xlsx_hidden_sheet_and_pivot_cache_are_reviewed(self):
        encoded = base64.b64encode(_xlsx_with_hidden_sheet()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "book.xlsx"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(any(finding["rule"] == "sg_nric_fin" for finding in payload["findings"]))
        sources = {finding["source"] for finding in payload["document"]["metadata_findings"]}
        self.assertIn("xlsx_hidden_sheet", sources)
        self.assertIn("xlsx_defined_name", sources)

    def test_pptx_notes_and_masters_are_reviewed(self):
        encoded = base64.b64encode(_pptx_with_notes()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "deck.pptx"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(any(finding["rule"] == "sg_nric_fin" for finding in payload["findings"]))
        sources = {finding["source"] for finding in payload["document"]["metadata_findings"]}
        self.assertIn("pptx_speaker_notes", sources)
        self.assertIn("pptx_slide_master", sources)

    def test_office_embedded_media_and_objects_are_mapped_without_ocr(self):
        encoded = base64.b64encode(_docx_with_media_and_object()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "media.docx"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        sources = {finding["source"] for finding in response.json()["document"]["metadata_findings"]}
        self.assertIn("docx_embedded_media", sources)
        self.assertIn("docx_embedded_object", sources)

    def test_pdf_xfa_and_signature_semantics_are_flagged(self):
        result = scan_container(
            _pdf_with_xfa_and_signature(),
            filename="signed.pdf",
            mime_type="application/pdf",
        )
        sources = {finding.source for finding in result.findings}

        self.assertIn("pdf_xfa", sources)
        self.assertIn("pdf_signature_field", sources)
        self.assertIn("pdf_signature_byte_range", sources)
        self.assertIn("pdf_signature_metadata", sources)

    def test_pdf_annotations_and_form_values_are_reviewed(self):
        encoded = base64.b64encode(_pdf_with_annotation_and_form()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "annotated-form.pdf"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        rules = {finding["rule"] for finding in payload["findings"]}
        sources = {finding["source"] for finding in payload["document"]["metadata_findings"]}
        self.assertIn("sg_nric_fin", rules)
        self.assertIn("passport_number", rules)
        self.assertIn("pdf_annotation", sources)
        self.assertIn("pdf_acroform", sources)

    def test_eml_attachment_is_recursed(self):
        message = EmailMessage()
        message["From"] = "sender@example.com"
        message["To"] = "recipient@example.com"
        message["Subject"] = "Draft"
        message.set_content("See attachment.")
        message.add_attachment(
            b"S1234567D in attachment",
            maintype="text",
            subtype="plain",
            filename="attachment.txt",
        )
        encoded = base64.b64encode(message.as_bytes(policy=email.policy.default)).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "mail.eml"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        self.assertTrue(any(finding["rule"] == "sg_nric_fin" for finding in response.json()["findings"]))

    def test_outlook_forwarded_eml_attachment_is_recursed(self):
        encoded = base64.b64encode(_eml_with_forwarded_message()).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "outlook-export.eml"},
            )

        self.assertEqual(response.status_code, 200, response.text)
        payload = response.json()
        self.assertTrue(any(finding["rule"] == "sg_nric_fin" for finding in payload["findings"]))
        sources = {finding["source"] for finding in payload["document"]["metadata_findings"]}
        self.assertIn("eml_forwarded_message", sources)

    def test_zip_path_traversal_fails_closed(self):
        encoded = base64.b64encode(_zip_bytes("../secret.txt", b"S1234567D")).decode("ascii")
        with TestClient(main.app) as client:
            response = client.post(
                "/review",
                json={"document_base64": encoded, "document_filename": "archive.zip"},
            )

        self.assertEqual(response.status_code, 422)
        self.assertIn("container scan failed closed", response.json()["detail"])

    def test_html_svg_markdown_and_rtf_hidden_content_are_reviewed(self):
        cases = [
            ("page.html", b'<!-- S1234567D --><div style="display:none">Jane Tan</div>'),
            ("image.svg", b'<svg xmlns="http://www.w3.org/2000/svg"><metadata>S1234567D</metadata></svg>'),
            ("note.md", b"Visible\n<!-- S1234567D -->\n![Jane Tan](x.png)"),
            ("doc.rtf", b"{\\rtf1\\ansi S1234567D \\object hidden}"),
        ]
        with TestClient(main.app) as client:
            for filename, payload in cases:
                response = client.post(
                    "/review",
                    json={"document_base64": base64.b64encode(payload).decode("ascii"), "document_filename": filename},
                )
                self.assertEqual(response.status_code, 200, response.text)
                self.assertTrue(any(finding["rule"] == "sg_nric_fin" for finding in response.json()["findings"]))

    def test_msg_7z_and_macro_enabled_containers_fail_closed(self):
        msg_response_payload = base64.b64encode(b"not really msg").decode("ascii")
        with TestClient(main.app) as client:
            msg_response = client.post(
                "/review",
                json={"document_base64": msg_response_payload, "document_filename": "mail.msg"},
            )
            seven_z_response = client.post(
                "/review",
                json={"document_base64": base64.b64encode(b"7z payload").decode("ascii"), "document_filename": "a.7z"},
            )
            docm_response = client.post(
                "/review",
                json={
                    "document_base64": base64.b64encode(_docx_bytes()).decode("ascii"),
                    "document_filename": "macro.docm",
                    "document_mime_type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                },
            )

        self.assertEqual(msg_response.status_code, 422)
        self.assertEqual(seven_z_response.status_code, 422)
        self.assertEqual(docm_response.status_code, 422)


if __name__ == "__main__":
    unittest.main()
