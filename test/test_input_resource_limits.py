"""Bounded text admission remains active after retiring native document ingestion."""

import io
import sys
from types import SimpleNamespace
from unittest.mock import patch

import pytest

from junas import DocumentInput, PreSendReviewEngine, ReviewPipeline, classify_text, input_limits
from junas.cli import main
from junas.review.document_structure import _structure_from_blocks


@pytest.mark.parametrize("size", [7, 8, 9])
def test_text_file_capture_keeps_the_source_limit(small_source, tmp_path, size):
    path = tmp_path / "bounded.txt"
    path.write_bytes(b"x" * size)
    if size > 8:
        with pytest.raises(ValueError, match="limit"):
            ReviewPipeline().review_file(path)
    else:
        assert ReviewPipeline().review_file(path).document.text == "x" * size


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


@pytest.mark.parametrize("size", [7, 8, 9])
def test_short_binary_reads_are_not_mistaken_for_end_of_input(small_source, monkeypatch, size):
    class Short(io.BytesIO):
        def read(self, size=-1):
            assert size >= 0
            return super().read(min(2, size))

    stream = Short(b"x" * size)
    if size > 8:
        with pytest.raises(ValueError):
            input_limits.read_source(stream)
    else:
        assert input_limits.read_source(stream) == b"x" * size
    monkeypatch.setattr(sys, "stdin", SimpleNamespace(buffer=Short(b"x" * size)))
    assert main(["classify", "--file", "-"]) == (2 if size > 8 else 0)
