"""Unsupported Office evidence must be refused before content extraction."""

import base64
import zipfile
from io import BytesIO
from unittest.mock import patch

import pytest

from junas import DocumentInput, ReviewPipeline
from junas.configs.runtime import get_runtime_settings
from junas.review.container_scan import DOCX_MIME, PPTX_MIME, XLSX_MIME, scan_container
from test.test_document_hardening import _docx_bytes, _pptx_with_notes, _xlsx_with_hidden_sheet, _zip_bytes

OFFICE = [
    (_docx_bytes, "docx", DOCX_MIME, "word/document.xml", "wordprocessingml.document"),
    (_xlsx_with_hidden_sheet, "xlsx", XLSX_MIME, "xl/workbook.xml", "spreadsheetml.sheet"),
    (_pptx_with_notes, "pptx", PPTX_MIME, "ppt/presentation.xml", "presentationml.presentation"),
]


def _package(factory, additions):
    with BytesIO() as buffer:
        with zipfile.ZipFile(BytesIO(factory())) as original, zipfile.ZipFile(buffer, "w") as archive:
            for name in original.namelist():
                archive.writestr(name, original.read(name))
            for name, data in additions.items():
                archive.writestr(name, data)
        return buffer.getvalue()


def _types(part, content_type):
    return (
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
        f'<Override PartName="/{part}" ContentType="{content_type}"/>'
        "</Types>"
    )


def _review(data, filename, mime=None, *, fail_closed=True):
    return ReviewPipeline(get_runtime_settings({"document_ingest.fail_closed": fail_closed})).review(
        DocumentInput(
            document_base64=base64.b64encode(data).decode(),
            document_filename=filename,
            document_mime_type=mime,
        )
    )


@pytest.mark.parametrize(
    "extension", ["docm", "xlsm", "pptm", "dotm", "xltm", "xlam", "potm", "ppam", "ppsm", "sldm", "xlsb"]
)
@pytest.mark.parametrize("fail_closed", [True, False])
def test_macro_extensions_refuse_before_opening_a_package(extension, fail_closed):
    with (
        patch("junas.review.document.inspect_metadata") as metadata,
        patch("junas.review.container_scan._zip_archive", side_effect=AssertionError("ZIP opened")),
        pytest.raises(ValueError, match="macro-enabled"),
    ):
        _review(b"not even a ZIP", f"macro.{extension.upper()}", DOCX_MIME, fail_closed=fail_closed)
    metadata.assert_not_called()


@pytest.mark.parametrize(
    "mime",
    [
        "application/vnd.ms-word.document.macroEnabled.12",
        "application/vnd.ms-word.template.macroEnabled.12",
        "application/vnd.ms-excel.sheet.macroEnabled.12",
        "application/vnd.ms-excel.sheet.binary.macroEnabled.12",
        "application/vnd.ms-powerpoint.presentation.macroEnabled.12",
        "application/vnd.ms-powerpoint.slideshow.macroEnabled.12; charset=utf-8",
    ],
)
def test_macro_mime_cannot_be_overridden_by_safe_extension(mime):
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError, match="macro-enabled"):
        _review(_docx_bytes(), "safe.docx", mime)
    metadata.assert_not_called()


@pytest.mark.parametrize("factory,extension,mime,part,family", OFFICE)
@pytest.mark.parametrize("evidence", ["vba_member", "macro_main_type", "renamed_vba_type"])
@pytest.mark.parametrize("disguise", ["office", "text", "archive"])
def test_container_evidence_refuses_disguised_macros_before_metadata(
    factory, extension, mime, part, family, evidence, disguise
):
    if evidence == "vba_member":
        additions = {part.split("/")[0] + "/VBAProject.bin": b"unread macro payload"}
    elif evidence == "macro_main_type":
        additions = {
            "[Content_Types].xml": _types(part, "application/vnd.ms-office.document.macro&#69;nabled.main+xml")
        }
    else:
        additions = {
            "[Content_Types].xml": _types("custom/renamed.bin", "application/vnd.ms-office.vbaProject"),
            "custom/renamed.bin": b"unread macro payload",
        }
    data = _package(factory, additions)
    filename, declared = {
        "office": ("safe." + extension, mime),
        "text": ("safe.txt", "text/plain"),
        "archive": ("safe.zip", "application/zip"),
    }[disguise]
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError):
        _review(data, filename, declared, fail_closed=False)
    metadata.assert_not_called()
    with pytest.raises(ValueError):
        scan_container(data, filename=filename, mime_type=declared)


def test_macro_sheet_without_vba_project_is_refused():
    data = _package(_xlsx_with_hidden_sheet, {"xl/macrosheets/sheet1.xml": "<macrosheet/>"})
    with pytest.raises(ValueError, match="macro-enabled"):
        _review(data, "safe.xlsx")


@pytest.mark.parametrize("factory,extension,mime,part,family", OFFICE)
@pytest.mark.parametrize("manifest", [False, True])
@pytest.mark.parametrize("declared", [False, True])
def test_supported_office_documents_remain_supported(factory, extension, mime, part, family, manifest, declared):
    additions = {
        "[Content_Types].xml": _types(part, f"application/vnd.openxmlformats-officedocument.{family}.main+xml")
    }
    data = _package(factory, additions) if manifest else factory()
    result = _review(data, "safe." + extension, mime.upper() + "; charset=utf-8" if declared else None)
    evidence, rule = ("E1234567", "passport_number") if extension == "docx" else ("S1234567D", "sg_nric_fin")
    assert evidence in result.document.text
    assert any(f.rule == rule for f in result.review.findings)
    assert result.document.extraction_quality == "accepted"


@pytest.mark.parametrize("factory,extension,mime,part,family", OFFICE)
def test_safe_supported_type_can_be_declared_for_a_generic_filename(factory, extension, mime, part, family):
    evidence = "E1234567" if extension == "docx" else "S1234567D"
    assert evidence in _review(factory(), "upload.bin", mime).document.text


@pytest.mark.parametrize("factory,extension,mime,part,family", OFFICE)
def test_disagreeing_supported_office_declarations_refuse_before_metadata(factory, extension, mime, part, family):
    other_mime = XLSX_MIME if mime != XLSX_MIME else DOCX_MIME
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError, match="mismatch"):
        _review(factory(), "safe." + extension, other_mime)
    metadata.assert_not_called()


def test_package_family_must_match_declared_office_type_before_metadata():
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError, match="mismatch"):
        _review(_xlsx_with_hidden_sheet(), "safe.docx", DOCX_MIME)
    metadata.assert_not_called()


def test_main_part_content_type_must_match_supported_office_type():
    data = _package(
        _docx_bytes,
        {
            "[Content_Types].xml": _types(
                "word/document.xml", "application/vnd.openxmlformats-officedocument.wordprocessingml.template.main+xml"
            )
        },
    )
    with pytest.raises(ValueError, match="mismatch"):
        _review(data, "safe.docx")


@pytest.mark.parametrize("filename,mime", [("safe.txt", "text/plain"), ("safe.docx", DOCX_MIME)])
def test_legacy_ole_cannot_be_disguised_as_supported_content(filename, mime):
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError):
        _review(bytes.fromhex("d0cf11e0a1b11ae1") + b"unsupported legacy object", filename, mime)
    metadata.assert_not_called()


def test_zip_limits_are_checked_before_metadata(monkeypatch):
    monkeypatch.setattr("junas.review.container_scan.MAX_MEMBER_BYTES", 32)
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError, match="exceeds"):
        _review(_docx_bytes(), "safe.docx")
    metadata.assert_not_called()


def test_regular_zip_archive_is_still_supported():
    result = _review(_zip_bytes("note.txt", b"Contact alice@example.test"), "safe.zip")
    assert "alice@example.test" in result.document.text


def test_disguised_zip_with_image_prefix_cannot_be_decoded_as_text():
    data = b"\x89PNG\r\n\x1a\n" + _docx_bytes()
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError, match="mismatch"):
        _review(data, "safe.txt", "text/plain")
    metadata.assert_not_called()


@pytest.mark.parametrize("compression", [zipfile.ZIP_STORED, zipfile.ZIP_DEFLATED])
def test_macro_document_is_refused_before_classification_regardless_of_compression(compression):
    with BytesIO() as buffer:
        with (
            zipfile.ZipFile(BytesIO(_docx_bytes())) as original,
            zipfile.ZipFile(buffer, "w", compression=compression) as archive,
        ):
            for name in original.namelist():
                archive.writestr(name, original.read(name))
        data = buffer.getvalue()
    with (
        patch("junas.pipeline.PreSendReviewEngine.review") as classify,
        pytest.raises(ValueError, match="macro-enabled"),
    ):
        _review(data, "macro.docm")
    classify.assert_not_called()


def test_malformed_content_type_manifest_refuses_before_metadata():
    data = _package(_docx_bytes, {"[Content_Types].xml": "<Types><Override"})
    with patch("junas.review.document.inspect_metadata") as metadata, pytest.raises(ValueError, match="malformed XML"):
        _review(data, "safe.docx", fail_closed=False)
    metadata.assert_not_called()


def test_duplicate_manifest_cannot_hide_macro_evidence():
    data = _package(
        _docx_bytes,
        {"[Content_Types].xml": _types("word/document.xml", "application/vnd.ms-word.document.macroEnabled.main+xml")},
    )
    with BytesIO(data) as buffer:
        with zipfile.ZipFile(buffer, "a") as archive, pytest.warns(UserWarning, match="Duplicate name"):
            archive.writestr(
                "[Content_Types].xml",
                _types(
                    "word/document.xml",
                    "application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml",
                ),
            )
        data = buffer.getvalue()
    with pytest.raises(ValueError, match="macro-enabled"):
        _review(data, "safe.docx")
