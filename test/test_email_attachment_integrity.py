"""Email coverage is measured on the exact text passed to classification."""

import base64
import zipfile
from email import policy
from email.message import EmailMessage
from io import BytesIO
from unittest.mock import patch

import pytest

from junas import DocumentInput, ReviewPipeline
from junas.configs.runtime import get_runtime_settings
from junas.review.container_scan import DOCX_MIME, _decoded_email_payload, _EmailBudget, scan_container
from junas.review.document_structure import parse_eml_structure
from test.test_document_hardening import _pptx_with_notes, _xlsx_with_hidden_sheet
from test.test_image_scan import FakeImageScanner, _png_bytes

IDENTIFIER = "S1234567D"


def _docx(text=IDENTIFIER, *, macro=False):
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.writestr(
                "word/document.xml",
                '<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">'
                f"<w:body><w:p><w:r><w:t>{text}</w:t></w:r></w:p></w:body></w:document>",
            )
            if macro:
                archive.writestr("word/vbaProject.bin", b"not executable")
        return buffer.getvalue()


def _email(body="Please review the attached document."):
    message = EmailMessage()
    message.set_content(body)
    return message


def _attach(message, data=None, name="identity.docx", mime=DOCX_MIME):
    main, sub = mime.split("/", 1)
    message.add_attachment(_docx() if data is None else data, maintype=main, subtype=sub, filename=name)


def _review(message, *, fail_closed=True):
    wire = message.as_bytes(policy=policy.default) if isinstance(message, EmailMessage) else message
    settings = get_runtime_settings({"document_ingest.fail_closed": fail_closed})
    return ReviewPipeline(settings).review(
        DocumentInput(document_base64=base64.b64encode(wire).decode(), document_filename="cover.eml")
    )


def _identifiers(result):
    return [f for f in result.review.findings if f.rule == "sg_nric_fin" and f.matched_text == IDENTIFIER]


def _assert_spans(result):
    text = result.document.text
    assert result.document.document_structure.text == text
    for finding in result.review.findings:
        if finding.source == "text":
            assert 0 <= finding.start_char < finding.end_char <= len(text)
            assert text[finding.start_char : finding.end_char] == finding.matched_text


def test_plain_email_body_remains_analyzed_once():
    result = _review(_email(IDENTIFIER))
    assert len(_identifiers(result)) == 1
    assert result.to_dict()["status"] == "completed"
    _assert_spans(result)


def test_docx_attachment_reaches_canonical_analyzed_text():
    message = _email()
    _attach(message)
    result = _review(message)
    assert "Please review the attached document." in result.document.text
    assert len(_identifiers(result)) == 1
    assert result.review.overall_risk.value == "HIGH_RISK"
    assert result.document.extraction_quality == "accepted"
    assert parse_eml_structure(message.as_bytes()).text == result.document.text
    _assert_spans(result)


def test_multiple_same_name_attachments_preserve_part_identity_and_order():
    message = _email(IDENTIFIER)
    _attach(message)
    _attach(message)
    result = _review(message)
    findings = _identifiers(result)
    assert len(findings) == 3
    assert [f.start_char for f in findings] == sorted({f.start_char for f in findings})
    origins = [f.metadata["email_sources"] for f in findings]
    assert [o[0]["part_path"] for o in origins] == ["1.1", "1.2", "1.3"]
    assert [o[0]["filename"] for o in origins] == ["", "identity.docx", "identity.docx"]
    assert _review(message).to_dict() == result.to_dict()
    _assert_spans(result)


def test_text_and_html_alternatives_each_reach_classifier_once():
    message = _email(f"Text alternative {IDENTIFIER}")
    message.add_alternative(f"<p>HTML alternative {IDENTIFIER}</p>", subtype="html")
    result = _review(message)
    assert "Text alternative" in result.document.text and "HTML alternative" in result.document.text
    assert len(_identifiers(result)) == 2
    _assert_spans(result)


def test_html_hidden_text_is_not_duplicated_and_comments_are_preserved():
    message = EmailMessage()
    message.set_content(f'<p style="display:none">{IDENTIFIER}</p><!--passport no. E1234567-->', subtype="html")
    result = _review(message)
    assert len(_identifiers(result)) == 1
    assert "E1234567" in result.document.text
    _assert_spans(result)


def test_forwarded_email_is_traversed_once_with_nested_attachment():
    nested = _email("Forwarded body " + IDENTIFIER)
    _attach(nested)
    outer = _email("Outer body")
    outer.add_attachment(nested, filename="forwarded.eml")
    result = _review(outer)
    assert len(_identifiers(result)) == 2
    assert result.document.text.count("Forwarded body") == 1
    assert "Outer body" in result.document.text
    paths = [_f.metadata["email_sources"][0]["part_path"] for _f in _identifiers(result)]
    assert len(set(paths)) == 2
    assert all(path.startswith("1.2.") for path in paths)
    scan = scan_container(outer.as_bytes(), filename="forwarded.eml", mime_type="message/rfc822")
    assert scan.text.count(IDENTIFIER) == 2
    _assert_spans(result)


@pytest.mark.parametrize(
    "data,name,mime",
    [
        (_xlsx_with_hidden_sheet(), "book.xlsx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (
            _pptx_with_notes(),
            "slides.pptx",
            "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        ),
        (b"S1234567D", "note.txt", "text/plain"),
        (b'{"id":"S1234567D"}', "note.json", "application/json"),
        (_docx(), "identity.docx", "application/octet-stream"),
        (_docx(), "upload.bin", DOCX_MIME),
    ],
)
def test_already_supported_attachment_formats(data, name, mime):
    message = _email()
    _attach(message, data, name, mime)
    result = _review(message)
    assert _identifiers(result)
    assert all(f.metadata["email_sources"][0]["filename"] == name for f in _identifiers(result))
    _assert_spans(result)


@pytest.mark.parametrize("fail_closed", [True, False])
@pytest.mark.parametrize(
    "data,name,mime",
    [
        (b"unknown binary", "unknown.bin", "application/octet-stream"),
        (_docx(), "macro.docm", "text/plain"),
        (_docx(macro=True), "safe.docx", DOCX_MIME),
        (_docx(), "safe.docx", "application/vnd.ms-word.document.macroEnabled.12"),
        (_docx(), "safe.docx", "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"),
        (b"corrupt ZIP", "broken.docx", DOCX_MIME),
        (b"\x89PNG\r\n\x1a\n", "scan.png", "image/png"),
    ],
)
def test_incomplete_attachments_refuse_or_report_specific_degradation(data, name, mime, fail_closed):
    message = _email("Body preserved " + IDENTIFIER)
    _attach(message, data, name, mime)
    _attach(message, _docx("passport no. E1234567"), "good.docx")
    if fail_closed:
        with pytest.raises(ValueError):
            _review(message)
    else:
        result = _review(message, fail_closed=False)
        assert "Body preserved" in result.document.text and "E1234567" in result.document.text
        assert result.to_dict()["status"] == "degraded"
        assert result.document.extraction_quality == "degraded"
        assert any(name in d.get("part_path", "") for d in result.review.degraded_modes)
        assert any(m["source"] == "eml_unreviewed_part" for m in result.document.metadata_findings)
        _assert_spans(result)


@pytest.mark.parametrize("limit", ["MAX_MEMBER_BYTES", "MAX_TOTAL_UNCOMPRESSED_BYTES", "MAX_ENTRIES", "MAX_DEPTH"])
@pytest.mark.parametrize("fail_closed", [True, False])
def test_email_limits_refuse_or_mark_incomplete(monkeypatch, limit, fail_closed):
    message = _email("Body remains available")
    _attach(message)
    monkeypatch.setattr("junas.review.container_scan." + limit, 0 if limit == "MAX_DEPTH" else 1)
    if fail_closed:
        with pytest.raises(ValueError):
            _review(message)
    else:
        result = _review(message, fail_closed=False)
        assert result.to_dict()["status"] == "degraded"
        assert result.review.degraded_modes


@pytest.mark.parametrize("fail_closed", [True, False])
def test_truncated_message_does_not_report_complete_coverage(fail_closed):
    message = _email("Preserved body " + IDENTIFIER)
    _attach(message)
    wire = message.as_bytes()
    wire = wire[: wire.rfind(b"--" + message.get_boundary().encode() + b"--")]
    if fail_closed:
        with pytest.raises(ValueError):
            _review(wire)
    else:
        result = _review(wire, fail_closed=False)
        assert "Preserved body" in result.document.text
        assert result.to_dict()["status"] == "degraded"


def test_invalid_attachment_base64_is_not_silently_repaired():
    message = _email()
    _attach(message)
    attachment = list(message.iter_attachments())[0]
    attachment.set_payload("@@@@")
    with pytest.raises(ValueError):
        _review(message)
    assert _review(message, fail_closed=False).to_dict()["status"] == "degraded"


def test_aggregate_attachment_expansion_is_bounded(monkeypatch):
    single = _email()
    _attach(single, _docx("neutral " * 1000))
    message = _email()
    for _ in range(3):
        _attach(message, _docx("neutral " * 1000))
    monkeypatch.setattr("junas.review.container_scan.MAX_TOTAL_UNCOMPRESSED_BYTES", 12000)
    assert _review(single).to_dict()["status"] == "completed"
    with pytest.raises(ValueError):
        _review(message)


@pytest.mark.parametrize("fail_closed", [True, False])
def test_encrypted_pdf_attachment_is_refused_or_qualified(fail_closed):
    from pypdf import PdfWriter

    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    writer.encrypt("synthetic-only-password")
    with BytesIO() as buffer:
        writer.write(buffer)
        data = buffer.getvalue()
    message = _email("Readable body " + IDENTIFIER)
    _attach(message, data, "encrypted.pdf", "application/pdf")
    if fail_closed:
        with pytest.raises(ValueError, match="encrypted"):
            _review(message)
    else:
        result = _review(message, fail_closed=False)
        assert _identifiers(result)
        assert result.to_dict()["status"] == "degraded"
        assert any("encrypted.pdf" in d.get("part_path", "") for d in result.review.degraded_modes)


def test_mime_node_budget_accepts_exact_limit_and_refuses_next(monkeypatch):
    message = _email()
    _attach(message)
    monkeypatch.setattr("junas.review.container_scan.MAX_ENTRIES", 3)
    assert _identifiers(_review(message))
    _attach(message)
    with pytest.raises(ValueError, match="MIME part count"):
        _review(message)


def test_8bit_size_is_checked_before_transfer_decoding(monkeypatch):
    from email import message_from_bytes

    message = EmailMessage()
    message.set_content("가가", cte="8bit")
    part = message_from_bytes(message.as_bytes(), policy=policy.default)
    monkeypatch.setattr("junas.review.container_scan.MAX_MEMBER_BYTES", 6)
    with patch.object(part, "get_payload", wraps=part.get_payload) as decode:
        with pytest.raises(ValueError, match="decoded bytes"):
            _decoded_email_payload(part, _EmailBudget())
    decode.assert_not_called()


def test_forwarding_depth_is_bounded_without_rewalking_messages():
    message = _email(IDENTIFIER)
    for _ in range(4):
        outer = _email("Outer body")
        outer.add_attachment(message, filename="forwarded.eml")
        message = outer
    with pytest.raises(ValueError, match="recursion depth"):
        _review(message)
    result = _review(message, fail_closed=False)
    assert "Outer body" in result.document.text
    assert result.to_dict()["status"] == "degraded"


def test_attachment_charset_and_control_cleanup_keep_source_offsets():
    message = _email()
    message.add_attachment("Café\x01 " + IDENTIFIER, charset="iso-8859-1", filename="note.txt")
    result = _review(message)
    assert "Café " + IDENTIFIER in result.document.text
    assert len(_identifiers(result)) == 1
    _assert_spans(result)


def test_unsupported_member_in_attached_zip_is_not_silently_ignored():
    message = _email()
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("unknown.bin", b"unreviewed binary")
            archive.writestr("safe.txt", IDENTIFIER)
        data = buffer.getvalue()
    _attach(message, data, "bundle.zip", "application/zip")
    with pytest.raises(ValueError, match="unknown.bin"):
        _review(message)
    assert _review(message, fail_closed=False).to_dict()["status"] == "degraded"


def test_office_embedded_media_uses_explicit_text_layer_exclusion():
    message = _email()
    with BytesIO(_docx()) as buffer:
        with zipfile.ZipFile(buffer, "a") as archive:
            archive.writestr("word/media/image1.png", _png_bytes())
        data = buffer.getvalue()
    _attach(message, data)
    result = _review(message)
    assert _identifiers(result)
    assert result.to_dict()["status"] == "degraded"
    assert result.document.extraction_quality == "degraded"
    assert any("reviewed text layer only" in d["reason"] for d in result.review.degraded_modes)


def test_existing_ocr_does_not_erase_attachment_degradation_or_text_provenance():
    message = _email(IDENTIFIER)
    _attach(message)
    _attach(message, b"unsupported", "unknown.bin", "application/octet-stream")
    _attach(message, _png_bytes(), "scan.png", "image/png")
    settings = get_runtime_settings({"document_ingest.fail_closed": False, "image_scan.provider": "tesseract"})
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner(text=IDENTIFIER)):
        result = ReviewPipeline(settings).review(
            DocumentInput(document_base64=base64.b64encode(message.as_bytes()).decode(), document_filename="cover.eml")
        )
    findings = _identifiers(result)
    assert len(findings) == 3
    assert result.document.extraction_quality == "degraded"
    assert result.to_dict()["status"] == "degraded"
    assert all(f.metadata.get("email_sources") for f in findings if f.source == "text")
    image = next(f for f in findings if f.source == "image_ocr")
    assert "scan.png" in image.image_locator["container_path"]
    for finding in findings:
        assert result.document.text[finding.start_char : finding.end_char] == finding.matched_text


@pytest.mark.parametrize("filename", ["macro.docm", "wrong.docx"])
def test_office_declarations_are_checked_before_forwarded_message_traversal(filename):
    outer = _email("Preserved outer body")
    outer.add_attachment(_email(IDENTIFIER), filename=filename)
    with pytest.raises(ValueError, match="macro-enabled|mismatch"):
        _review(outer)
    result = _review(outer, fail_closed=False)
    assert result.to_dict()["status"] == "degraded"
    assert not _identifiers(result)
    assert "Preserved outer body" in result.document.text


def test_supported_docx_inside_attached_zip_reaches_classifier():
    message = _email()
    with BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            archive.writestr("nested/identity.docx", _docx())
        data = buffer.getvalue()
    _attach(message, data, "bundle.zip", "application/zip")
    result = _review(message)
    assert len(_identifiers(result)) == 1
    assert "nested/identity.docx" in result.document.text
    assert _identifiers(result)[0].metadata["email_sources"][0]["filename"] == "bundle.zip"
    _assert_spans(result)


def test_supported_pdf_text_attachment_reaches_classifier():
    from pypdf import PdfWriter
    from pypdf.generic import DecodedStreamObject, DictionaryObject, NameObject

    writer = PdfWriter()
    page = writer.add_blank_page(width=612, height=792)
    font = DictionaryObject(
        {
            NameObject("/Type"): NameObject("/Font"),
            NameObject("/Subtype"): NameObject("/Type1"),
            NameObject("/BaseFont"): NameObject("/Helvetica"),
        }
    )
    page[NameObject("/Resources")] = DictionaryObject(
        {NameObject("/Font"): DictionaryObject({NameObject("/F1"): writer._add_object(font)})}
    )
    stream = DecodedStreamObject()
    stream.set_data(
        b"BT /F1 12 Tf 72 720 Td (Synthetic identity record S1234567D provided for classification review only.) Tj ET"
    )
    page[NameObject("/Contents")] = writer._add_object(stream)
    with BytesIO() as buffer:
        writer.write(buffer)
        data = buffer.getvalue()
    message = _email()
    _attach(message, data, "identity.pdf", "application/pdf")
    result = _review(message)
    assert len(_identifiers(result)) == 1
    assert result.to_dict()["status"] == "completed"
    _assert_spans(result)


@pytest.mark.parametrize("fail_closed", [True, False])
def test_unsupported_structured_message_cannot_be_silently_walked_as_empty_text(fail_closed):
    message = _email("Readable report body")
    status = EmailMessage()
    status.set_type("message/delivery-status")
    fields = EmailMessage()
    fields["Final-Recipient"] = "rfc822; synthetic@example.test"
    status.set_payload([fields])
    message.make_mixed()
    message.attach(status)
    if fail_closed:
        with pytest.raises(ValueError, match="unsupported structured MIME part"):
            _review(message)
    else:
        result = _review(message, fail_closed=False)
        assert "Readable report body" in result.document.text
        assert result.to_dict()["status"] == "degraded"
