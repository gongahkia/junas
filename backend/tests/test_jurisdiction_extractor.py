"""Tests for SGLB-07 explicit jurisdiction-statement extraction."""
from __future__ import annotations

from pathlib import Path

import pytest

from data.ingestion import commonlii_sg
from data.parsers.commonlii_sg_parser import parse_commonlii_sg_html
from data.parsers.jurisdiction_extractor import (
    JurisdictionStatement,
    extract_jurisdiction_statements,
)

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "commonlii_sg"


def _paragraph(number: int, text: str) -> dict[str, object]:
    return {"number": number, "text": text}


@pytest.mark.parametrize(
    ("text", "label"),
    [
        (
            "This Court is bound by Tan Cheng Bock v Attorney-General, a decision of the Singapore Court of Appeal.",
            "sg_binding",
        ),
        (
            "The decision of the Court of Appeal in Lee Tat Development Pte Ltd v Management Corporation is binding on this Court.",
            "sg_binding",
        ),
        (
            "Applying the principle in Donoghue v Stevenson, a decision of the English courts, I reach the same conclusion.",
            "uk_persuasive",
        ),
        (
            "The English authority of Smith v Jones is persuasive on the scope of the duty.",
            "uk_persuasive",
        ),
        (
            "While UK cases have considered this question, the Singapore statute remains the starting point.",
            "uk_persuasive",
        ),
        (
            "We draw guidance from Australian authorities on the treatment of contractual penalties.",
            "au_persuasive",
        ),
        (
            "The High Court of Australia decision in Andrews is persuasive on this point.",
            "au_persuasive",
        ),
        (
            "Although Australian courts have addressed this issue, the local pleadings are different.",
            "au_persuasive",
        ),
        (
            "Hong Kong cases have considered this question and are helpful on the tracing analysis.",
            "hk_persuasive",
        ),
        (
            "The Hong Kong Court of Final Appeal authority of Akai Holdings is persuasive in this context.",
            "hk_persuasive",
        ),
        (
            "The English cases are distinguishable and of no assistance in the present context.",
            "not_applicable",
        ),
        (
            "We decline to follow the Australian authorities because the statutory scheme differs.",
            "not_applicable",
        ),
        (
            "Hong Kong decisions do not assist on this question.",
            "not_applicable",
        ),
        (
            "No foreign authority is applicable to the construction of this provision.",
            "not_applicable",
        ),
    ],
)
def test_extracts_explicit_jurisdiction_labels_from_synthetic_paragraphs(text: str, label: str) -> None:
    statements = extract_jurisdiction_statements([_paragraph(7, text)])

    assert statements == [JurisdictionStatement(label=label, quote=text, paragraph=7)]


def test_extracts_sentence_containing_trigger_not_whole_paragraph() -> None:
    paragraph = (
        "Counsel made a broader submission. "
        "The English authority of Smith v Jones is persuasive on the reliance point. "
        "I address the local statute next."
    )

    statements = extract_jurisdiction_statements([_paragraph(12, paragraph)])

    assert statements == [
        JurisdictionStatement(
            label="uk_persuasive",
            quote="The English authority of Smith v Jones is persuasive on the reliance point.",
            paragraph=12,
        )
    ]


def test_extracts_multiple_statements_for_future_multi_source_builder() -> None:
    paragraphs = [
        _paragraph(4, "The English authority of Smith v Jones is persuasive on remoteness."),
        _paragraph(5, "We draw guidance from Australian authorities on the same issue."),
        _paragraph(6, "This Court is bound by the decision of the Singapore Court of Appeal in Foo v Bar."),
    ]

    statements = extract_jurisdiction_statements(paragraphs)

    assert [(statement.label, statement.paragraph) for statement in statements] == [
        ("uk_persuasive", 4),
        ("au_persuasive", 5),
        ("sg_binding", 6),
    ]


@pytest.mark.parametrize(
    "text",
    [
        "Counsel cited Donoghue v Stevenson [1932] AC 562 in passing.",
        "The English case of Smith v Jones was cited by the appellant.",
        "In R v Brown, Lord Templeman explained the public policy concerns.",
        "The respondent relied on a line of UK cases in its written submissions.",
    ],
)
def test_uk_case_mentions_without_court_framing_do_not_match(text: str) -> None:
    assert extract_jurisdiction_statements([_paragraph(3, text)]) == []


@pytest.mark.parametrize(
    "text",
    [
        "Foo v Bar [2018] SGCA 14 concerned contractual interpretation.",
        "The court referred to [2018] SGCA 14 and [2020] SGHC 22.",
        "The Singapore decision was cited without any binding submission.",
    ],
)
def test_sg_citations_without_binding_statement_do_not_match(text: str) -> None:
    assert extract_jurisdiction_statements([_paragraph(9, text)]) == []


def test_body_plain_fallback_uses_b2_bracketed_paragraph_numbers() -> None:
    row = {
        "body_plain": (
            "[1] The pleadings were amended. "
            "[2] The English authority of Smith v Jones is persuasive on estoppel."
        )
    }

    statements = extract_jurisdiction_statements(row)

    assert statements == [
        JurisdictionStatement(
            label="uk_persuasive",
            quote="The English authority of Smith v Jones is persuasive on estoppel.",
            paragraph=2,
        )
    ]


def test_current_commonlii_fixtures_do_not_invent_jurisdiction_labels() -> None:
    for name in ("sgca_2024_48.html", "sghc_2024_251.html"):
        parsed = parse_commonlii_sg_html((FIXTURE_DIR / name).read_text(encoding="utf-8"))

        assert extract_jurisdiction_statements(parsed) == []


def test_commonlii_fixture_with_b2_paragraphs_triggers_expected_labels() -> None:
    html = (FIXTURE_DIR / "sgca_2024_48.html").read_text(encoding="utf-8").replace(
        "</body>",
        """
        <p>[1] The appeal concerns contractual damages.</p>
        <p>[2] The English authority of Smith v Jones is persuasive on remoteness.</p>
        <p>[3] This Court is bound by the decision of the Singapore Court of Appeal in Foo v Bar.</p>
        </body>
        """,
    )

    parsed = parse_commonlii_sg_html(html)
    statements = extract_jurisdiction_statements(parsed)

    assert [(statement.label, statement.paragraph) for statement in statements] == [
        ("uk_persuasive", 2),
        ("sg_binding", 3),
    ]


def test_commonlii_ingestion_row_includes_b2_fields_and_jurisdiction_statements() -> None:
    html = (FIXTURE_DIR / "sghc_2024_251.html").read_text(encoding="utf-8").replace(
        "</body>",
        """
        <p>[1] The accused pleaded guilty.</p>
        <p>[2] We decline to follow the Australian authorities because the statutory scheme differs.</p>
        </body>
        """,
    )
    link = commonlii_sg.JudgmentLink(
        html_url=commonlii_sg.judgment_url("SGHC", 2024, 251),
        listing_url=commonlii_sg.year_listing_url("SGHC", 2024),
        citation="[2024] SGHC 251",
        court_code="SGHC",
        year=2024,
        case_no=251,
    )

    row = commonlii_sg.build_judgment_row(link, html)

    assert row["paragraphs"][-1] == {
        "number": 2,
        "text": "We decline to follow the Australian authorities because the statutory scheme differs.",
    }
    assert row["jurisdiction_statements"] == [
        {
            "label": "not_applicable",
            "quote": "We decline to follow the Australian authorities because the statutory scheme differs.",
            "paragraph": 2,
        }
    ]
