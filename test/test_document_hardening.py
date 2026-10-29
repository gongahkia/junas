import base64
import email
import unittest
import zipfile
from email.message import EmailMessage
from io import BytesIO


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
    signature_value = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Sig"),
            NameObject("/ByteRange"): ArrayObject(
                [NumberObject(0), NumberObject(10), NumberObject(20), NumberObject(30)]
            ),
            NameObject("/Name"): TextStringObject("Priya Raman"),
            NameObject("/Reason"): TextStringObject("approved"),
        }
    )
    signature_field = DictionaryObject(
        {
            NameObject("/FT"): NameObject("/Sig"),
            NameObject("/T"): TextStringObject("ApprovalSignature"),
            NameObject("/V"): writer._add_object(signature_value),
        }
    )
    acroform = DictionaryObject(
        {
            NameObject("/Fields"): ArrayObject([writer._add_object(signature_field)]),
            NameObject("/XFA"): TextStringObject("<template/>"),
        }
    )
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
        DictionaryObject(
            {
                NameObject("/Type"): NameObject("/Font"),
                NameObject("/Subtype"): NameObject("/Type1"),
                NameObject("/BaseFont"): NameObject("/Helvetica"),
            }
        )
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): font})}
    )
    stream = StreamObject()
    stream._data = b"BT /F1 12 Tf 72 720 Td (Enough extractable text for review.) Tj ET"
    page[NameObject("/Contents")] = writer._add_object(stream)
    annotation = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Annot"),
            NameObject("/Subtype"): NameObject("/Text"),
            NameObject("/Rect"): ArrayObject([NumberObject(10), NumberObject(10), NumberObject(40), NumberObject(40)]),
            NameObject("/Contents"): TextStringObject("Annotation contains S1234567D."),
            NameObject("/T"): TextStringObject("Jane Reviewer"),
        }
    )
    page[NameObject("/Annots")] = ArrayObject([writer._add_object(annotation)])
    text_field = DictionaryObject(
        {
            NameObject("/FT"): NameObject("/Tx"),
            NameObject("/T"): TextStringObject("ReviewerField"),
            NameObject("/TU"): TextStringObject("Hidden review field"),
            NameObject("/V"): TextStringObject("Form value contains passport E1234567."),
        }
    )
    acroform = DictionaryObject({NameObject("/Fields"): ArrayObject([writer._add_object(text_field)])})
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


if __name__ == "__main__":
    unittest.main()
