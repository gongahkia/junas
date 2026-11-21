"""Small profiles exercise public and nested resource boundaries without large allocations."""

import base64
import io
import sys
import tarfile
import zipfile
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from junas import DocumentInput, PreSendReviewEngine, ReviewPipeline, classify_text, input_limits
from junas.cli import main
from junas.configs.runtime import get_runtime_settings
from junas.review import container_scan, document, metadata
from junas.review.document_structure import _structure_from_blocks, parse_docx_structure
from junas.review.image_scan import ImageLocator, ImageOcrResult, append_ocr_text_blocks
from test.test_email_attachment_integrity import _attach, _docx, _email


def _engine(text):
    return PreSendReviewEngine().review(
        text=text, source_jurisdiction="SG", destination_jurisdiction="SG", entity_id=None, include_suggestions=False
    )


@pytest.fixture
def small_source(monkeypatch):
    monkeypatch.setattr(input_limits, "MAX_SOURCE_BYTES", 8)
    monkeypatch.setattr(input_limits, "MAX_INLINE_TEXT_BYTES", 8)


@pytest.mark.parametrize("size", [7, 8, 9])
@pytest.mark.parametrize(
    "entry", [lambda s: DocumentInput(text=s), classify_text, _engine, ReviewPipeline().review_text]
)
def test_public_text_limits_at_all_entrypoints(small_source, size, entry):
    if size > 8:
        with pytest.raises(ValueError, match="limit"):
            entry("x" * size)
    else:
        entry("x" * size)


@pytest.mark.parametrize("text", ["é" * 4, "é" * 4 + "x"])
def test_text_limit_counts_utf8_bytes(small_source, text):
    if len(text.encode()) > 8:
        with pytest.raises(ValueError):
            ReviewPipeline().review_text(text)
    else:
        assert ReviewPipeline().review_text(text).document.text == text


@pytest.mark.parametrize("size", [7, 8, 9])
def test_equivalent_file_and_base64_have_same_source_limit(small_source, tmp_path, size):
    path = tmp_path / "bounded.txt"
    path.write_bytes(b"x" * size)
    pipeline = ReviewPipeline()
    if size > 8:
        with pytest.raises(ValueError):
            pipeline.review_file(path)
        with pytest.raises(ValueError):
            pipeline.review(
                DocumentInput(document_base64=base64.b64encode(path.read_bytes()).decode(), document_filename=path.name)
            )
    else:
        direct = pipeline.review_file(path)
        encoded = pipeline.review(
            DocumentInput(document_base64=base64.b64encode(path.read_bytes()).decode(), document_filename=path.name)
        )
        assert direct.to_dict() == encoded.to_dict()


@pytest.mark.parametrize("size", [9, 1000])
def test_oversized_base64_refuses_before_decoder_even_without_input_model(small_source, size):
    encoded = base64.b64encode(b"x" * size).decode()
    payload = SimpleNamespace(document_base64=encoded, document_filename="bounded.txt")
    with patch("junas.review.document.base64.b64decode", side_effect=AssertionError("decoder called")) as decode:
        with pytest.raises(ValueError, match="limit"):
            document.extract_review_document(payload)
    decode.assert_not_called()


class BoundedText(io.StringIO):
    def read(self, size=-1):
        assert 0 <= size <= 4096, "unbounded stdin read"
        return super().read(size)


@pytest.mark.parametrize("size", [7, 8, 9])
def test_stdin_is_bounded_and_exit_codes_are_preserved(small_source, monkeypatch, capsys, size):
    monkeypatch.setattr(sys, "stdin", BoundedText("x" * size))
    assert main(["classify", "--file", "-"]) == (2 if size > 8 else 0)
    if size > 8:
        assert "limit" in capsys.readouterr().err


def test_binary_stdin_reads_at_most_source_limit_plus_one(small_source, monkeypatch):
    class Binary(io.BytesIO):
        def read(self, size=-1):
            assert 0 <= size <= 9
            return super().read(size)

    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=Binary(b"x" * 100)))
    assert main(["classify", "--file", "-"]) == 2


def test_rules_test_text_file_uses_bounded_input(small_source, tmp_path, monkeypatch):
    path = tmp_path / "input.txt"
    path.write_text("x" * 9)
    with patch("junas.review.secret_rulepacks.load_gitleaks_rule_pack") as loader:
        assert main(["rules", "test", "--gitleaks", str(tmp_path / "none.toml"), "--text-file", str(path)]) == 2
    loader.assert_not_called()


@pytest.mark.parametrize("fail_closed", [True, False])
def test_source_limit_is_not_best_effort_truncation(small_source, fail_closed):
    settings = get_runtime_settings({"document_ingest.fail_closed": fail_closed})
    with pytest.raises(ValueError):
        ReviewPipeline(settings).review_text("x" * 9)


def test_retained_text_limit_is_separate_from_source_limit(monkeypatch):
    monkeypatch.setattr(input_limits, "MAX_SOURCE_BYTES", 1024)
    monkeypatch.setattr(input_limits, "MAX_INLINE_TEXT_BYTES", 64)
    monkeypatch.setattr(input_limits, "MAX_ANALYZED_TEXT_BYTES", 8192)
    data = _docx("neutral " * 400 + " S1234567D")
    result = ReviewPipeline().review(
        DocumentInput(document_base64=base64.b64encode(data).decode(), document_filename="expanded.docx")
    )
    assert len(result.document.text) > 64
    assert any(f.rule == "sg_nric_fin" for f in result.review.findings)
    with pytest.raises(ValueError):
        _engine(result.document.text)
    for finding in result.review.findings:
        assert result.document.text[finding.start_char : finding.end_char] == finding.matched_text


@pytest.mark.parametrize("size", [7, 8, 9])
def test_analyzed_text_limit_before_detector_and_structure_assembly(monkeypatch, size):
    monkeypatch.setattr(input_limits, "MAX_ANALYZED_TEXT_BYTES", 8)
    if size > 8:
        with patch.object(PreSendReviewEngine, "_pii_findings", side_effect=AssertionError("detector called")):
            with pytest.raises(ValueError):
                ReviewPipeline().review_text("x" * size)
        with pytest.raises(ValueError):
            _structure_from_blocks([("paragraph", "x" * size, None)])
    else:
        assert _structure_from_blocks([("paragraph", "x" * size, None)]).text == "x" * size


def test_ocr_append_checks_cumulative_text_before_accepting_overflow(monkeypatch):
    monkeypatch.setattr(input_limits, "MAX_ANALYZED_TEXT_BYTES", 16)
    result = ImageOcrResult(text="sensitive", provider="fake", locator=ImageLocator("scan.png", 0))
    with pytest.raises(ValueError, match="limit"):
        append_ocr_text_blocks("body", [result])


def _siblings_zip():
    children = [_docx("neutral " * 100)] * 2
    with io.BytesIO() as buffer:
        with zipfile.ZipFile(buffer, "w") as archive:
            for i, child in enumerate(children):
                archive.writestr(f"child{i}.docx", child)
        wire = buffer.getvalue()
    with zipfile.ZipFile(io.BytesIO(wire)) as archive:
        expanded = sum(i.file_size for i in archive.infolist())
    for child in children:
        with zipfile.ZipFile(io.BytesIO(child)) as archive:
            expanded += sum(i.file_size for i in archive.infolist())
    return wire, expanded


@pytest.mark.parametrize("offset", [-1, 0, 1])
def test_nested_archives_share_cumulative_expansion_budget(monkeypatch, offset):
    wire, expanded = _siblings_zip()
    monkeypatch.setattr(container_scan, "MAX_TOTAL_UNCOMPRESSED_BYTES", expanded + offset)
    if offset < 0:
        with pytest.raises(ValueError, match="expansion"):
            container_scan.scan_container(wire, filename="nested.zip", mime_type="application/zip")
    else:
        assert "neutral" in container_scan.scan_container(wire, filename="nested.zip", mime_type="application/zip").text


def test_root_preflight_and_extraction_do_not_double_charge_same_zip(monkeypatch):
    data = _docx()
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        expanded = sum(i.file_size for i in archive.infolist())
    monkeypatch.setattr(container_scan, "MAX_TOTAL_UNCOMPRESSED_BYTES", expanded)
    result = ReviewPipeline().review(
        DocumentInput(document_base64=base64.b64encode(data).decode(), document_filename="identity.docx")
    )
    assert any(f.rule == "sg_nric_fin" for f in result.review.findings)


def test_repeated_mime_parts_are_charged_for_each_actual_extraction(monkeypatch):
    calls = []
    original = container_scan._EmailBudget.charge_expansion

    def charge(self, size):
        calls.append(size)
        return original(self, size)

    monkeypatch.setattr(container_scan._EmailBudget, "charge_expansion", charge)
    message = _email()
    _attach(message)
    _attach(message)
    result = ReviewPipeline().review(
        DocumentInput(document_base64=base64.b64encode(message.as_bytes()).decode(), document_filename="cover.eml")
    )
    assert len(calls) == 2
    assert calls[0] == calls[1]
    assert len([f for f in result.review.findings if f.rule == "sg_nric_fin"]) == 2


@pytest.mark.parametrize("parser", [metadata.inspect_metadata, parse_docx_structure])
def test_direct_office_helpers_preflight_before_reading_xml(monkeypatch, parser):
    monkeypatch.setattr(container_scan, "MAX_MEMBER_BYTES", 32)
    args = (
        {"filename": "identity.docx", "mime_type": container_scan.DOCX_MIME}
        if parser is metadata.inspect_metadata
        else {}
    )
    with pytest.raises(ValueError, match="exceeds"):
        parser(_docx(), **args)


def test_tar_entry_limit_does_not_eagerly_enumerate_members(monkeypatch):
    with io.BytesIO() as buffer:
        with tarfile.open(fileobj=buffer, mode="w") as archive:
            for i in range(3):
                info = tarfile.TarInfo(f"{i}.txt")
                info.size = 1
                archive.addfile(info, io.BytesIO(b"x"))
        wire = buffer.getvalue()
    monkeypatch.setattr(container_scan, "MAX_ENTRIES", 2)
    with patch.object(tarfile.TarFile, "getmembers", side_effect=AssertionError("eager enumeration")):
        with pytest.raises(ValueError, match="entries"):
            container_scan.scan_container(wire, filename="small.tar", mime_type="application/x-tar")


@pytest.mark.parametrize("fail_closed", [True, False])
def test_pdf_render_cap_refuses_or_explicitly_degrades(fail_closed):
    from test.test_document_hardening import _blank_pdf_base64

    payload = DocumentInput(document_base64=_blank_pdf_base64(), document_filename="scan.pdf")
    settings = SimpleNamespace(pdf_render_pages=True, pdf_render_max_pages=1, pdf_render_scale=1.0)
    with (
        patch("junas.review.document._extract_pdf", return_value=("", 2, "ocr_pending", [])),
        patch("junas.review.document.collect_pdf_images", return_value=[]),
        patch("junas.review.document.collect_pdf_page_renders", return_value=[]) as render,
    ):
        if fail_closed:
            with pytest.raises(ValueError, match="page"):
                document.extract_review_document(
                    payload, SimpleNamespace(fail_closed=True), image_scan_enabled=True, image_scan_settings=settings
                )
            render.assert_not_called()
        else:
            result = document.extract_review_document(
                payload, SimpleNamespace(fail_closed=False), image_scan_enabled=True, image_scan_settings=settings
            )
            assert result.extraction_quality == "degraded"
            assert any("page" in w and "fail-open:" in w for w in result.extraction_warnings)


def test_cli_preserves_degraded_exit_one(monkeypatch, capsys):
    settings = get_runtime_settings({"document_ingest.fail_closed": False})
    monkeypatch.setattr("junas.cli.get_runtime_settings", lambda *_: settings)
    result = ReviewPipeline(settings).review(DocumentInput(document_base64="eA==", document_filename="unsupported.msg"))
    monkeypatch.setattr(ReviewPipeline, "review_text", lambda *a, **k: result)
    assert main(["classify", "--text", "ordinary"]) == 1
