"""Exercise the complete local path without HTTP, product state or provider traffic."""

import base64
import json
import subprocess
import sys
from dataclasses import replace
from pathlib import Path
from unittest.mock import patch

import pytest

from junas import DocumentInput, ReviewPipeline, classify_text
from junas.configs.runtime import get_runtime_settings
from junas.review.image_scan import ImageScanError
from test.test_document_hardening import (
    _blank_pdf_base64,
    _docx_bytes,
    _docx_weird_comments_and_track_changes,
    _eml_with_forwarded_message,
    _pdf_with_annotation_and_form,
    _pdf_with_xfa_and_signature,
    _pptx_with_notes,
    _text_pdf_base64,
    _xlsx_with_hidden_sheet,
    _zip_bytes,
)
from test.test_image_scan import FakeImageScanner, _png_bytes


def test_text_pipeline_preserves_offsets_and_has_no_workflow_decision():
    output = ReviewPipeline().review_text("  Contact alice@example.com.\n").to_dict()
    email = next(f for f in output["findings"] if f["rule"] == "email_address")
    assert output["document"]["text"][email["start_char"] : email["end_char"]] == "alice@example.com"
    assert "send_allowed" not in output
    assert "policy_decision" not in output
    assert classify_text("S1234567D").pii_score > 0


@pytest.mark.parametrize("kwargs", [{}, {"text": " "}, {"text": "hello", "document_base64": "eA=="}])
def test_ambiguous_or_empty_input_is_rejected(kwargs):
    with pytest.raises(ValueError):
        DocumentInput(**kwargs)


@pytest.mark.parametrize(
    "factory,filename,sources",
    [
        (_docx_weird_comments_and_track_changes, "draft.docx", {"docx_comments", "docx_track_changes"}),
        (_xlsx_with_hidden_sheet, "hidden.xlsx", {"xlsx_hidden_sheet", "xlsx_defined_name"}),
        (_pptx_with_notes, "slides.pptx", {"pptx_speaker_notes", "pptx_slide_master"}),
        (_eml_with_forwarded_message, "forwarded.eml", {"eml_forwarded_message"}),
        (_pdf_with_annotation_and_form, "annotated.pdf", {"pdf_annotation", "pdf_acroform"}),
    ],
)
def test_hidden_document_content_reaches_the_detector(factory, filename, sources):
    payload = DocumentInput(document_base64=base64.b64encode(factory()).decode(), document_filename=filename)
    result = ReviewPipeline().review(payload)
    assert "S1234567D" in result.document.text
    assert any(f.rule == "sg_nric_fin" and f.matched_text == "S1234567D" for f in result.review.findings)
    assert sources <= {item["source"] for item in result.document.metadata_findings}


def test_author_metadata_and_track_changes_are_preserved_for_research():
    result = ReviewPipeline().review(
        DocumentInput(document_base64=base64.b64encode(_docx_bytes()).decode(), document_filename="draft.docx")
    )
    sources = {item["source"] for item in result.document.metadata_findings}
    assert {"docx_core_properties", "docx_comments", "docx_track_changes"} <= sources
    assert any(f.rule == "passport_number" for f in result.review.findings)


def test_pdf_signature_semantics_are_inspected_without_claiming_signature_validation():
    from junas.review.container_scan import scan_container

    result = scan_container(_pdf_with_xfa_and_signature(), filename="signed.pdf", mime_type="application/pdf")
    sources = {item.source for item in result.findings}
    assert {"pdf_xfa", "pdf_signature_field", "pdf_signature_byte_range", "pdf_signature_metadata"} <= sources


def test_pdf_text_extraction_and_unreadable_pdf_rejection():
    pipeline = ReviewPipeline()
    result = pipeline.review(DocumentInput(document_base64=_text_pdf_base64(), document_filename="memo.pdf"))
    assert result.document.text.strip()
    with pytest.raises(ValueError):
        pipeline.review(DocumentInput(document_base64=_blank_pdf_base64(), document_filename="scan.pdf"))


@pytest.mark.parametrize(
    "filename,data",
    [
        ("mail.msg", b"unsupported example"),
        ("archive.7z", b"unsupported example"),
        ("macro.docm", _docx_bytes()),
        ("archive.zip", _zip_bytes("../secret.txt", b"S1234567D")),
    ],
)
def test_unsupported_and_unsafe_containers_are_rejected(filename, data):
    with pytest.raises(ValueError):
        ReviewPipeline().review(
            DocumentInput(document_base64=base64.b64encode(data).decode(), document_filename=filename)
        )


def test_best_effort_is_explicitly_degraded():
    settings = get_runtime_settings({"document_ingest.fail_closed": False})
    result = ReviewPipeline(settings).review(DocumentInput(document_base64="eA==", document_filename="mail.msg"))
    assert result.to_dict()["status"] == "degraded"
    assert result.review.degraded_modes


def test_image_ocr_findings_preserve_coordinates_and_do_not_redact():
    settings = get_runtime_settings({"image_scan.provider": "tesseract"})
    payload = DocumentInput(document_base64=base64.b64encode(_png_bytes()).decode(), document_filename="scan.png")
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner()):
        output = ReviewPipeline(settings).review(payload).to_dict()
    nric = next(f for f in output["findings"] if f["rule"] == "sg_nric_fin")
    assert nric["source"] == "image_ocr"
    assert nric["image_ocr_regions"][0]["bounding_box"]
    assert output["document"]["text"][nric["start_char"] : nric["end_char"]] == "S1234567D"
    assert "redacted_document" not in output


def test_ocr_failure_cannot_be_reported_as_completed():
    settings = get_runtime_settings({"image_scan.provider": "tesseract"})
    payload = DocumentInput(document_base64=base64.b64encode(_png_bytes()).decode(), document_filename="scan.png")
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner(fail=True)):
        with pytest.raises(ImageScanError):
            ReviewPipeline(settings).review(payload)
        best_effort = replace(settings, document_ingest=replace(settings.document_ingest, fail_closed=False))
        assert ReviewPipeline(best_effort).review(payload).to_dict()["status"] == "degraded"


def test_strict_does_not_construct_optional_advisory_providers():
    settings = get_runtime_settings({"public_evidence.enabled": True, "public_evidence.provider": "exa"})
    with patch(
        "junas.external.public_evidence.inference.PublicEvidenceRetriever", side_effect=AssertionError("network")
    ):
        result = ReviewPipeline(settings).review_text("Contact alice@example.com")
    assert result.review.public_evidence is None


def test_cli_works_from_a_different_directory_without_server_dependencies(tmp_path):
    result = subprocess.run(
        [sys.executable, "-m", "junas.cli", "classify", "--text", "Contact alice@example.com"],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert any(f["rule"] == "email_address" for f in json.loads(result.stdout)["findings"])
    assert list(tmp_path.iterdir()) == []


def test_context_terms_are_explicit_and_do_not_persist(tmp_path, monkeypatch):
    from junas.review.defined_terms import extract_defined_terms
    from junas.review.engine import PreSendReviewEngine

    monkeypatch.chdir(tmp_path)
    terms = extract_defined_terms('"Project Raven" means the Purchaser.')
    engine = PreSendReviewEngine()
    options = dict(
        text="Project Raven",
        source_jurisdiction="SG",
        destination_jurisdiction="SG",
        entity_id=None,
        include_suggestions=False,
    )
    baseline = engine.review(**options)
    engine.review(**options, context_terms=terms)
    assert engine.review(**options) == baseline
    assert list(Path.cwd().iterdir()) == []
