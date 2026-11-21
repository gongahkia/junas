"""Occurrence-aware evidence and duplicate-insensitive scoring regressions."""

import base64
from dataclasses import replace
from unittest.mock import patch

import pytest

from junas import DocumentInput, ReviewPipeline
from junas.configs.runtime import get_runtime_settings
from junas.review.engine import PreSendReviewEngine, ReviewFinding, ReviewLayerError, _risk_from_score
from test.test_image_scan import FakeImageScanner, _png_bytes


def _review(text, *, engine=None, profile="strict"):
    return (engine or PreSendReviewEngine()).review(
        text=text,
        source_jurisdiction="SG",
        destination_jurisdiction="SG",
        entity_id=None,
        include_suggestions=False,
        review_profile=profile,
    )


def _assert_spans(text, findings):
    for finding in findings:
        assert 0 <= finding.start_char < finding.end_char <= len(text), finding
        assert text[finding.start_char : finding.end_char] == finding.matched_text, finding


def _finding():
    return ReviewFinding(
        id="original",
        category="MNPI",
        rule="material_event",
        jurisdiction="SG",
        severity="medium",
        score=55.0,
        matched_text="acquisition",
        start_char=0,
        end_char=11,
        reason="Material corporate or market event language",
        legal_basis="SG_SFA_INSIDER_TRADING",
    )


@pytest.mark.parametrize("whitespace", [" ", "\t", "\r", "\u00a0", " \t\r"])
def test_contextual_findings_trim_coordinates_with_text(whitespace):
    line = "Acme Corp confidential acquisition is pending."
    text = whitespace + line + whitespace
    result = _review(text)
    contextual = [f for f in result.findings if f.rule in {"material_event", "conjunctive_mnpi"}]
    assert {f.rule for f in contextual} == {"material_event", "conjunctive_mnpi"}
    assert all(f.start_char == len(whitespace) for f in contextual)
    assert all(f.matched_text == line for f in contextual)
    _assert_spans(text, result.findings)


def test_long_conjunctive_context_keeps_exact_coordinates():
    text = "Heading\n\tAcme Corp confidential " + "neutral " * 60 + "acquisition pending.  \nEnd"
    result = _review(text)
    assert any(f.rule == "conjunctive_mnpi" for f in result.findings)
    _assert_spans(text, result.findings)


def test_multiple_event_keywords_on_one_line_are_one_detection():
    text = "Acme acquisition merger takeover buyout earnings guidance is pending."
    result = _review(text)
    events = [f for f in result.findings if f.rule == "material_event"]
    assert len(events) == 1
    assert events[0].matched_text == text
    assert result.mnpi_score == 55.0
    assert result.overall_risk.value == "LOW_RISK"


def test_repeated_text_retains_each_occurrence():
    line = "Acme acquisition merger is pending."
    text = f"  {line}  \n\t{line}\t"
    result = _review(text)
    events = [f for f in result.findings if f.rule == "material_event"]
    assert [(f.start_char, f.end_char) for f in events] == [
        (2, 2 + len(line)),
        (len(line) + 6, 2 * len(line) + 6),
    ]
    assert result.mnpi_score == 58.0
    _assert_spans(text, result.findings)


def test_overlapping_different_rules_are_preserved():
    text = "definitive agreement"
    result = _review(text)
    findings = [f for f in result.findings if f.rule in {"material_event", "definitive_agreement"}]
    assert {f.rule for f in findings} == {"material_event", "definitive_agreement"}
    assert all((f.start_char, f.end_char) == (0, len(text)) for f in findings)
    assert result.mnpi_score == 58.0
    _assert_spans(text, findings)


def test_eu_recognizer_overlap_is_one_exact_detection():
    result = PreSendReviewEngine().review(
        text="PT NIF: 123456789",
        source_jurisdiction="EU",
        destination_jurisdiction="EU",
        entity_id=None,
        include_suggestions=False,
    )
    identifiers = [f for f in result.findings if f.rule == "eu_national_id"]
    assert len(identifiers) == 1
    assert identifiers[0].metadata["member_state"] == "PT"
    assert identifiers[0].metadata["validator"] == "checksum"


@pytest.mark.parametrize("severity,score", [("medium", 55.0), ("high", 85.0)])
def test_duplicate_ids_cannot_inflate_score_or_risk(severity, score):
    finding = replace(_finding(), severity=severity, score=score)
    duplicates = [replace(finding, id=f"emission:{i}") for i in range(8)]
    engine = PreSendReviewEngine()
    assert engine._score(duplicates, "MNPI") == score
    assert _risk_from_score(engine._score(duplicates, "MNPI")) == _risk_from_score(score)


@pytest.mark.parametrize(
    "different",
    [
        {"rule": "another_interpretation"},
        {"reason": "Another valid interpretation"},
        {"metadata": {"interpretation": "distinct"}},
        {"jurisdiction": "EU"},
        {"source": "image_ocr", "image_locator": {"image_index": 1}},
        {"source_verification": "ambiguous"},
    ],
)
def test_same_span_with_distinct_interpretation_or_provenance_still_counts(different):
    original = _finding()
    other = replace(original, id="other", **different)
    assert PreSendReviewEngine()._score([original, other], "MNPI") == 58.0


def test_deduplication_preserves_a_high_severity_interpretation():
    original = _finding()
    high = replace(original, id="high", severity="high", score=85.0)
    assert PreSendReviewEngine()._score([original, high, replace(high, id="repeat")], "MNPI") == 88.0


def test_repeated_detector_output_does_not_change_public_findings_or_scores():
    original = _finding()
    engine = PreSendReviewEngine()
    with patch.object(engine, "_mnpi_findings", return_value=[original]):
        baseline = _review("acquisition", engine=engine)
    with patch.object(engine, "_mnpi_findings", return_value=[original, replace(original, id="repeat")]):
        repeated = _review("acquisition", engine=engine)
    assert repeated == baseline


@pytest.mark.parametrize(
    "invalid",
    [
        {"start_char": -1},
        {"end_char": 0},
        {"end_char": 12},
        {"matched_text": "wrong occurrence"},
    ],
)
def test_invalid_text_evidence_refuses_instead_of_searching_or_dropping(invalid):
    engine = PreSendReviewEngine()
    with patch.object(engine, "_mnpi_findings", return_value=[replace(_finding(), **invalid)]):
        with pytest.raises(ReviewLayerError) as error:
            _review("acquisition", engine=engine)
    assert error.value.layer == "finding_integrity"


def test_audit_profile_quasi_identifier_evidence_uses_its_existing_window():
    text = "Dr Jane Tan, S1234567A, +65 9123 4567 in line."
    result = _review(text, profile="audit_grade")
    assert any(f.rule == "quasi_identifier_combination" for f in result.findings)
    _assert_spans(text, result.findings)


def test_document_level_advisory_does_not_receive_a_fabricated_span():
    advisory = replace(
        _finding(),
        rule="llm_raised_finding",
        source="llm_coverage_audit",
        matched_text="[LLM_COVERAGE_WARNING]",
        start_char=0,
        end_char=0,
    )
    engine = PreSendReviewEngine()
    with patch.object(engine, "_mnpi_findings", return_value=[advisory]):
        result = _review("acquisition", engine=engine)
    assert result.findings == [advisory]


@pytest.mark.parametrize(
    "body,entity,expected",
    [
        ("Ticker: SGX:D05", None, "D05"),
        ("Straße note; dBs group discussed; dBs group repeated.", None, "dBs group"),
        ("Straße note; STRASSE Group discussed.", None, "STRASSE Group"),
        ("Quiet period applies.", "D05", None),
    ],
)
def test_operator_calendar_evidence_keeps_real_coordinates_or_external_provenance(
    tmp_path, monkeypatch, body, entity, expected
):
    calendar = tmp_path / "earnings.csv"
    issuer = "Straße Group" if "STRASSE Group" in body else "DBS Group"
    calendar.write_text(
        "jurisdiction,ticker,period,announcement_date,issuer\n" + f"SG,D05,interim,2026-08-10,{issuer}\n"
    )
    monkeypatch.setenv("JUNAS_EARNINGS_CALENDAR_CSV", str(calendar))
    text = "Date: 1 Aug 2026\n" + body
    result = PreSendReviewEngine().review(
        text=text,
        source_jurisdiction="SG",
        destination_jurisdiction="SG",
        entity_id=entity,
        include_suggestions=False,
    )
    blackouts = [f for f in result.findings if f.rule == "blackout_period_reference"]
    assert len(blackouts) == 1
    finding = blackouts[0]
    assert finding.metadata["earnings_calendar_source"] == "operator_csv"
    assert finding.metadata["issuer"] == issuer
    if expected is None:
        assert finding.source == "operator_csv"
        assert (finding.start_char, finding.end_char, finding.matched_text) == (0, 0, "")
    else:
        assert finding.source == "text"
        assert finding.matched_text == expected
        prefix = "Ticker: SGX:" if body.startswith("Ticker:") else "Straße note; "
        start = len("Date: 1 Aug 2026\n") + len(prefix)
        assert finding.start_char == start
        _assert_spans(text, result.findings)


def test_ocr_evidence_uses_appended_text_and_preserves_image_provenance():
    settings = get_runtime_settings({"image_scan.provider": "tesseract"})
    line = "Acme acquisition merger is pending."
    payload = DocumentInput(document_base64=base64.b64encode(_png_bytes()).decode(), document_filename="scan.png")
    with patch("junas.pipeline.build_image_scanner", return_value=FakeImageScanner(text=f"{line}\n{line}")):
        result = ReviewPipeline(settings).review(payload)
    _assert_spans(result.document.text, result.review.findings)
    events = [f for f in result.review.findings if f.rule == "material_event"]
    assert len(events) == 2
    assert events[0].start_char > 0
    assert events[0].end_char < events[1].start_char
    assert all(f.source == "image_ocr" and f.image_locator["container_path"] == "scan.png" for f in events)
    assert all(f.image_ocr_regions for f in events)
