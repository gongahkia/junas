"""SGLB-02 task runner + evaluators + dataset builder."""
from __future__ import annotations

import asyncio
import json
from pathlib import Path

import pytest
import yaml

from benchmark.dataset_builders import sglb_02 as builder
from benchmark.evaluators import EVALUATORS, EvaluatorContext, EvaluatorStrength, _rouge_l
from benchmark.llm_runner import PROMPT_BUILDERS, SGLB_02_PROMPT_VERSION
from benchmark.registry import TASKS
from benchmark.schema import Case

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "sso"


def _make_case(*, citation: str, answer_span: str) -> Case:
    return Case(
        name="t",
        inputs={
            "question": "Under the PDPA, what does the section on \"Purpose\" provide?",
            "act_short_name": "PDPA",
            "act_full_name": "Personal Data Protection Act 2012",
        },
        expected_output={"citation": citation, "answer_span": answer_span},
        metadata={},
    )


def _ctx(case: Case, output: str) -> EvaluatorContext:
    return EvaluatorContext(
        case_name=case.name,
        inputs=case.inputs,
        expected_output=case.expected_output,
        metadata=case.metadata,
        output=output,
    )


# --- builder unit ---


def test_short_name_known():
    assert builder._short_name("PDPA2012") == "PDPA"
    assert builder._short_name("EmA1968") == "Employment Act"


def test_short_name_unknown_falls_back():
    assert builder._short_name("UnknownCode") == "UnknownCode"


def test_is_substantive_filters_repealed():
    assert builder._is_substantive("X" * 200, "[Repealed] section") is False


def test_is_substantive_filters_short_text():
    assert builder._is_substantive("too short", "Some Heading") is False


def test_is_substantive_filters_definitions_heading():
    assert builder._is_substantive("X" * 200, "Interpretation") is False
    assert builder._is_substantive("X" * 200, "Definitions") is False
    assert builder._is_substantive("X" * 200, "Short title") is False


def test_is_substantive_accepts_normal_section():
    assert builder._is_substantive("X" * 200, "Functions of Commission") is True


def test_strip_section_number_prefix():
    assert builder._strip_section_number_prefix("13. The Commission shall...", "13") == "The Commission shall..."
    assert builder._strip_section_number_prefix("26A. —(1) Foo", "26A") == "(1) Foo"


def test_first_paragraph_truncates_at_sentence_boundary():
    text = "Sentence one. " + ("X " * 400) + "Sentence end."
    out = builder._first_paragraph(text)
    assert len(out) <= builder._MAX_ANSWER_CHARS + 5


def test_first_paragraph_passes_short_text_through():
    assert builder._first_paragraph("Short text.") == "Short text."


def test_question_template_uses_short_name_and_heading():
    q = builder._question_for("Functions of Commission", "PDPA")
    assert "PDPA" in q
    assert "Functions of Commission" in q


def test_citation_for_uses_full_name_when_available():
    assert builder._citation_for("PDPA", "Personal Data Protection Act 2012", "13") == (
        "s 13 of the Personal Data Protection Act 2012"
    )


def test_stable_case_id_is_deterministic():
    a = builder._stable_case_id("PDPA2012@2020", "13")
    b = builder._stable_case_id("PDPA2012@2020", "13")
    assert a == b
    assert a.startswith("sglb_02_")


def test_assign_split_is_deterministic_and_balanced():
    splits = [builder._assign_split(i) for i in range(100)]
    assert splits.count("train") == 80
    assert splits.count("dev") == 10
    assert splits.count("test") == 10


# --- builder end-to-end on PDPA fixture ---


@pytest.fixture(scope="module")
def materialised_sso_jsonl(tmp_path_factory):
    """Materialise an SSO JSONL from the PDPA fixture for the builder tests."""
    from data.parsers.sso_parser import parse_sso_html
    from data.ingestion.sso import write_jsonl

    toc = (FIXTURE_DIR / "pdpa_toc.html").read_text(encoding="utf-8")
    body = (FIXTURE_DIR / "pdpa_full.html").read_text(encoding="utf-8")
    act = parse_sso_html(
        body,
        "PDPA2012",
        "https://sso.agc.gov.sg/Act/PDPA2012?WholeDoc=1",
        toc_html=toc,
    )
    out_dir = tmp_path_factory.mktemp("sso")
    jsonl_path = out_dir / "statutes.jsonl"
    write_jsonl([act], jsonl_path, append=False)
    return jsonl_path


def test_build_pdpa_emits_cases(materialised_sso_jsonl):
    cases = builder.build(materialised_sso_jsonl)
    assert len(cases) >= 40
    # spot-check shape
    sample = cases[0]
    payload = sample.as_dict()
    assert payload["inputs"]["question"].startswith("Under the PDPA")
    assert payload["inputs"]["act_full_name"] == "Personal Data Protection Act 2012"
    assert payload["expected_output"]["citation"].startswith("s ")
    assert "of the Personal Data Protection Act 2012" in payload["expected_output"]["citation"]
    assert len(payload["expected_output"]["answer_span"]) >= builder._MIN_TEXT_LEN
    assert payload["extraction_rule_sha"]
    assert len(payload["extraction_rule_sha"]) == 7
    assert payload["metadata"]["dataset_version"] == builder.DATASET_VERSION
    assert payload["metadata"]["label_provenance"].startswith("mechanical-extraction")


def test_build_assigns_all_three_splits(materialised_sso_jsonl):
    cases = builder.build(materialised_sso_jsonl)
    splits = {c.split for c in cases}
    assert splits == {"train", "dev", "test"}


def test_build_drops_short_title_and_repealed(materialised_sso_jsonl):
    cases = builder.build(materialised_sso_jsonl)
    headings = {c.section_heading.lower() for c in cases}
    assert not any(h.startswith("short title") for h in headings)
    assert not any("[repealed]" in h for h in headings)


def test_write_yaml_includes_extraction_rules(materialised_sso_jsonl, tmp_path: Path):
    cases = builder.build(materialised_sso_jsonl)
    out = tmp_path / "sglb_02.yaml"
    builder.write_yaml(cases, out)
    payload = yaml.safe_load(out.read_text(encoding="utf-8"))
    assert payload["extraction_rules"]["sso"] == cases[0].extraction_rule_sha
    assert payload["cases"][0]["extraction_rule_sha"] == cases[0].extraction_rule_sha


# --- evaluator unit ---


def test_rouge_l_perfect_match():
    assert _rouge_l("the quick brown fox", "the quick brown fox") == pytest.approx(1.0)


def test_rouge_l_zero_overlap():
    assert _rouge_l("foo bar baz", "qux quux corge") == 0.0


def test_rouge_l_partial_overlap():
    # ref: A B C D ; cand: A C D → LCS = A C D (len 3)
    # p = 3/3 = 1.0, r = 3/4 = 0.75, f1 = 2*1*0.75/1.75 ≈ 0.857
    score = _rouge_l("a b c d", "a c d")
    assert score == pytest.approx(2 * 1.0 * 0.75 / 1.75, abs=1e-4)


def test_rouge_l_empty_input():
    assert _rouge_l("", "anything") == 0.0
    assert _rouge_l("anything", "") == 0.0


def test_sglb_02_citation_match_normalises_section_form():
    case = _make_case(citation="s 13 of the Personal Data Protection Act 2012", answer_span="x")
    output = json.dumps({"citation": "Section 13 of the Personal Data Protection Act 2012.", "answer": "x"})
    score = asyncio.run(EVALUATORS["sglb_02_citation_match"].evaluate(_ctx(case, output)))
    assert score.score == 1.0


def test_sglb_02_citation_match_accepts_bare_string_output():
    case = _make_case(citation="s 7 of the Personal Data Protection Act 2012", answer_span="x")
    score = asyncio.run(
        EVALUATORS["sglb_02_citation_match"].evaluate(_ctx(case, "s 7 of the Personal Data Protection Act 2012"))
    )
    assert score.score == 1.0


def test_sglb_02_citation_match_zero_on_wrong_section():
    case = _make_case(citation="s 13 of the Personal Data Protection Act 2012", answer_span="x")
    output = json.dumps({"citation": "s 14 of the Personal Data Protection Act 2012", "answer": "x"})
    score = asyncio.run(EVALUATORS["sglb_02_citation_match"].evaluate(_ctx(case, output)))
    assert score.score == 0.0


def test_rouge_l_answer_uses_answer_field_when_present():
    case = _make_case(citation="s 3 of the Personal Data Protection Act 2012", answer_span="purpose of the act governs collection use disclosure")
    output = json.dumps({"citation": "s 3 of the Personal Data Protection Act 2012", "answer": "purpose of the act governs collection use disclosure"})
    score = asyncio.run(EVALUATORS["rouge_l_answer"].evaluate(_ctx(case, output)))
    assert score.score == pytest.approx(1.0)


def test_rouge_l_answer_falls_back_to_full_output():
    case = _make_case(citation="s 3", answer_span="purpose of the act")
    score = asyncio.run(EVALUATORS["rouge_l_answer"].evaluate(_ctx(case, "purpose of the act")))
    assert score.score == pytest.approx(1.0)


# --- task registration ---


def test_sglb_02_task_registered():
    assert "sglb_02" in TASKS


def test_sglb_02_prompt_builder_registered():
    assert "sglb_02" in PROMPT_BUILDERS
    builder_fn, version = PROMPT_BUILDERS["sglb_02"]
    assert version == SGLB_02_PROMPT_VERSION
    case = _make_case(citation="s 3 of the PDPA", answer_span="x")
    msgs = builder_fn(case)
    assert msgs[0]["role"] == "system"
    assert msgs[-1]["role"] == "user"
    assert "PDPA" in msgs[-1]["content"]
    # System prompt must specify the JSON output contract.
    assert "JSON object" in msgs[0]["content"]
    assert "citation" in msgs[0]["content"]
    assert "answer" in msgs[0]["content"]


def test_sglb_02_evaluators_registered_strong():
    assert EVALUATORS["sglb_02_citation_match"].strength == EvaluatorStrength.STRONG
    assert EVALUATORS["rouge_l_answer"].strength == EvaluatorStrength.STRONG


def test_oracle_runner_scores_perfectly():
    case = _make_case(
        citation="s 13 of the Personal Data Protection Act 2012",
        answer_span="An organisation shall not collect personal data about an individual unless the individual gives consent.",
    )
    output = asyncio.run(TASKS["sglb_02"](case))
    cit = asyncio.run(EVALUATORS["sglb_02_citation_match"].evaluate(_ctx(case, output)))
    rouge = asyncio.run(EVALUATORS["rouge_l_answer"].evaluate(_ctx(case, output)))
    assert cit.score == 1.0
    assert rouge.score == pytest.approx(1.0)
