"""Text-only public entrypoints preserve source evidence and refuse retired formats."""

import json
import subprocess
import sys
from dataclasses import asdict
from pathlib import Path
from unittest.mock import patch

import pytest

from junas import DocumentInput, PreSendReviewEngine, ReviewPipeline, classify_text
from junas.configs.runtime import ConfigError, get_runtime_settings


@pytest.mark.parametrize("text", ["", " \n", None, b"bytes", "binary\x00text"])
def test_empty_nontext_and_binary_inputs_are_rejected(text):
    with pytest.raises(ValueError):
        DocumentInput(text=text)


def test_base64_document_api_is_removed():
    with pytest.raises(TypeError):
        DocumentInput(document_base64="eA==", document_filename="removed.pdf")


def test_cli_preserves_degraded_exit_one(monkeypatch):
    from junas.cli import main

    result = ReviewPipeline().review_text("ordinary")
    result.review.degraded_modes.append({"layer": "local_ner", "mode": "unavailable", "reason": "synthetic test"})
    monkeypatch.setattr(ReviewPipeline, "review_text", lambda *a, **k: result)
    assert main(["classify", "--text", "ordinary"]) == 1


@pytest.mark.parametrize("suffix", [".pdf", ".docx", ".xlsx", ".pptx", ".eml", ".msg", ".zip", ".png"])
def test_native_document_formats_are_refused_before_reading(tmp_path, suffix):
    pipeline = ReviewPipeline()
    with patch.object(Path, "open", side_effect=AssertionError("retired input opened")):
        with pytest.raises(ValueError, match="text files only"):
            pipeline.review_file(tmp_path / ("input" + suffix))


@pytest.mark.parametrize("data", [b"%PDF-1.7", b"\n %PDF-1.7", b"PK\x03\x04stuff", b"binary\0stuff", b"\xff\xfe"])
def test_binary_content_disguised_as_text_is_refused(tmp_path, data):
    path = tmp_path / "disguised.txt"
    path.write_bytes(data)
    with pytest.raises(ValueError):
        ReviewPipeline().review_file(path)


def test_utf8_file_preserves_crlf_unicode_and_exact_detector_output(tmp_path):
    text = "  Straße note\r\nContact alice@example.test.\r\nNRIC S1234567D.\r\n"
    path = tmp_path / "canonical.txt"
    path.write_bytes(text.encode("utf-8"))
    pipeline = ReviewPipeline()
    result = pipeline.review_file(path)
    assert result.document.text == text
    assert asdict(result.review) == asdict(pipeline.review_text(text).review)
    assert asdict(result.review) == asdict(
        PreSendReviewEngine().review(
            text=text,
            source_jurisdiction="SG",
            destination_jurisdiction="SG",
            entity_id=None,
            include_suggestions=False,
        )
    )
    for finding in result.review.findings:
        assert text[finding.start_char : finding.end_char] == finding.matched_text


@pytest.mark.parametrize("section", ["document_ingest", "image_scan"])
def test_retired_configuration_is_explicitly_rejected(tmp_path, section):
    config = tmp_path / "removed.toml"
    config.write_text(f'[{section}]\nprovider = "none"\n')
    with pytest.raises(ConfigError):
        get_runtime_settings({"config_path": str(config)})
    with pytest.raises(ConfigError, match="text only"):
        get_runtime_settings({section + ".provider": "none"})


def test_retired_ocr_environment_is_rejected(monkeypatch):
    monkeypatch.setenv("JUNAS_IMAGE_SCAN_PROVIDER", "tesseract")
    with pytest.raises(ConfigError, match="text only"):
        get_runtime_settings()


def test_text_pipeline_preserves_offsets_and_has_no_workflow_decision():
    output = ReviewPipeline().review_text("  Contact alice@example.com.\n").to_dict()
    email = next(f for f in output["findings"] if f["rule"] == "email_address")
    assert output["document"]["text"][email["start_char"] : email["end_char"]] == "alice@example.com"
    assert "send_allowed" not in output
    assert "policy_decision" not in output
    assert classify_text("S1234567D").pii_score > 0


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
