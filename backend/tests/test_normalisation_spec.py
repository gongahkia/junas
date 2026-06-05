from __future__ import annotations

import re
from pathlib import Path

import pytest
import yaml

from api.services.sal_citation import parse_elitigation_url, validate_citation
from benchmark.evaluators import _normalise_section_citation, _normalise_statute_name

CORPUS_PATH = Path(__file__).parent / "fixtures" / "normalisation" / "corpus.yaml"
MIN_POSITIVE_CASES = 10
MIN_NEGATIVE_CASES = 3

_NEUTRAL_RE = re.compile(r"^\[(?P<year>\d{4})\]\s+(?P<court>SG[A-Z]+)\s+(?P<case_no>\d+)\.?\s*$")
_SLR_PATTERNS = (
    (re.compile(r"^\[(?P<year>\d{4})\]\s+(?P<volume>\d+)\s+SLR\(R\)\s+(?P<page>\d+)\.?\s*$"), "SLR(R)", "slr_r_case"),
    (re.compile(r"^\[(?P<year>\d{4})\]\s+(?P<volume>\d+)\s+SLR\s+(?P<page>\d+)\.?\s*$"), "SLR", "slr_case"),
)


def _load_corpus() -> dict:
    return yaml.safe_load(CORPUS_PATH.read_text(encoding="utf-8"))


CORPUS = _load_corpus()


def _normalise_neutral_case(value: str) -> str:
    raw = str(value or "").strip()
    parsed = parse_elitigation_url(raw)
    if parsed:
        candidate = f"[{parsed.year}] {parsed.court} {parsed.case_no}"
    else:
        match = _NEUTRAL_RE.match(raw)
        if not match:
            return ""
        candidate = f"[{match.group('year')}] {match.group('court')} {int(match.group('case_no'))}"
    result = validate_citation(candidate)
    if result.valid and result.kind == "neutral_case":
        return candidate
    return ""


def _normalise_slr_case(value: str) -> str:
    raw = str(value or "").strip()
    for pattern, reporter, kind in _SLR_PATTERNS:
        match = pattern.match(raw)
        if not match:
            continue
        candidate = f"[{match.group('year')}] {int(match.group('volume'))} {reporter} {int(match.group('page'))}"
        result = validate_citation(candidate)
        if result.valid and result.kind == kind:
            return candidate
    return ""


NORMALISERS = {
    "section_citation": _normalise_section_citation,
    "statute_short_name": _normalise_statute_name,
    "neutral_case": _normalise_neutral_case,
    "slr_case": _normalise_slr_case,
}


def _positive_cases() -> list[tuple[str, dict]]:
    return [
        (kind, case)
        for kind, payload in CORPUS["kinds"].items()
        for case in payload.get("positive", [])
    ]


def _negative_cases() -> list[tuple[str, dict]]:
    return [
        (kind, case)
        for kind, payload in CORPUS["kinds"].items()
        for case in payload.get("negative", [])
    ]


def _case_id(item: tuple[str, dict]) -> str:
    kind, case = item
    raw = str(case.get("raw_form", "blank"))
    return f"{kind}:{raw[:48]}"


def test_corpus_declares_every_normaliser_kind():
    assert set(CORPUS["kinds"]) == set(NORMALISERS)


@pytest.mark.parametrize("kind,payload", CORPUS["kinds"].items())
def test_each_kind_has_vendor_reviewable_coverage(kind: str, payload: dict):
    assert len(payload.get("positive", [])) >= MIN_POSITIVE_CASES
    assert len(payload.get("negative", [])) >= MIN_NEGATIVE_CASES


@pytest.mark.parametrize("kind,case", _positive_cases(), ids=[_case_id(item) for item in _positive_cases()])
def test_positive_corpus_pairs_match_canonical_form(kind: str, case: dict):
    assert NORMALISERS[kind](case["raw_form"]) == case["canonical_form"]


@pytest.mark.parametrize("kind,case", _negative_cases(), ids=[_case_id(item) for item in _negative_cases()])
def test_negative_corpus_cases_do_not_normalise(kind: str, case: dict):
    assert NORMALISERS[kind](case["raw_form"]) == ""
