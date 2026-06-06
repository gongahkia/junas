"""CommonLII SG judgment parser tests."""
from __future__ import annotations

from pathlib import Path

from data.ingestion import commonlii_sg
from data.parsers.commonlii_sg_parser import parse_commonlii_sg_html, parse_commonlii_sg_row

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "commonlii_sg"
SGCA_48_URL = commonlii_sg.judgment_url("SGCA", 2024, 48)
SGHC_251_URL = commonlii_sg.judgment_url("SGHC", 2024, 251)


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def _row(html: str, *, url: str, citation: str, court_code: str, case_no: int) -> dict[str, object]:
    link = commonlii_sg.JudgmentLink(
        html_url=url,
        listing_url=commonlii_sg.year_listing_url(court_code, 2024),
        citation=citation,
        court_code=court_code,
        year=2024,
        case_no=case_no,
    )
    return commonlii_sg.build_judgment_row(link, html)


def _with_extra_body(fixture_html: str, extra_body: str) -> str:
    return fixture_html.replace("</body>", f"{extra_body}\n</body>")


def test_parse_sgca_fixture_yields_complete_record() -> None:
    html = _with_extra_body(
        _fixture("sgca_2024_48.html"),
        """
        <p>Coram: Tay Yong Kwang JCA and Woo Bih Li JAD</p>
        <p><i>Contract - Sale and purchase - Failure to complete - Damages</i></p>
        <p>For the appellants: Lim Wei Ming SC and Cheryl Tan.</p>
        <p>For the respondent: Daniel Ho.</p>
        <p>[1]&nbsp;This appeal concerned a failed sale and purchase agreement.</p>
        <p>[2] The court considered whether the deposit was forfeitable.</p>
        <p>[3] We allowed the appeal in part.</p>
        """,
    )
    row = _row(html, url=SGCA_48_URL, citation="[2024] SGCA 48", court_code="SGCA", case_no=48)

    parsed = parse_commonlii_sg_row(row)

    assert parsed["case_id"] == commonlii_sg.stable_case_id(SGCA_48_URL)
    assert parsed["body_plain"].startswith("[1] This appeal concerned")
    assert " [2] The court considered" in str(parsed["body_plain"])
    assert parsed["catchwords"] == "Contract - Sale and purchase - Failure to complete - Damages"
    assert parsed["judges"] == ["Tay Yong Kwang JCA", "Woo Bih Li JAD"]
    assert parsed["paragraphs"] == [
        {"number": 1, "text": "This appeal concerned a failed sale and purchase agreement."},
        {"number": 2, "text": "The court considered whether the deposit was forfeitable."},
        {"number": 3, "text": "We allowed the appeal in part."},
    ]
    assert parsed["counsel"] == [
        "For the appellants: Lim Wei Ming SC and Cheryl Tan.",
        "For the respondent: Daniel Ho.",
    ]


def test_parse_sghc_fixture_yields_complete_record() -> None:
    html = _with_extra_body(
        _fixture("sghc_2024_251.html"),
        """
        <p>Judge(s): Vincent Hoong J</p>
        <p><em>Criminal Law - Sentencing - Public servant - Valuable things</em></p>
        <p>For the Prosecution: Deputy Public Prosecutor Tan Zhi Hao.</p>
        <p>For the Accused: Davinder Singh SC.</p>
        <p>[1] The accused pleaded guilty to offences involving valuable things.</p>
        <p>[2] The sentencing framework required attention to public confidence.</p>
        """,
    )
    row = _row(html, url=SGHC_251_URL, citation="[2024] SGHC 251", court_code="SGHC", case_no=251)

    parsed = parse_commonlii_sg_row(row)

    assert parsed["citation"] == "[2024] SGHC 251"
    assert parsed["body_plain"] == (
        "[1] The accused pleaded guilty to offences involving valuable things. "
        "[2] The sentencing framework required attention to public confidence."
    )
    assert parsed["catchwords"] == "Criminal Law - Sentencing - Public servant - Valuable things"
    assert parsed["judges"] == ["Vincent Hoong J"]
    assert parsed["paragraphs"][-1]["number"] == 2
    assert len(parsed["counsel"]) == 2


def test_bracket_paragraph_numbering_preserved_inline() -> None:
    html = """
    <html><body>
      <p>Coram: Aedit Abdullah J</p>
      <p>[1] First paragraph.</p>
      <p>[2] Second paragraph cites [2024] SGCA 1 without treating it as a paragraph.</p>
    </body></html>
    """

    parsed = parse_commonlii_sg_html(html)

    assert parsed["body_plain"] == (
        "[1] First paragraph. "
        "[2] Second paragraph cites [2024] SGCA 1 without treating it as a paragraph."
    )
    assert parsed["paragraphs"] == [
        {"number": 1, "text": "First paragraph."},
        {"number": 2, "text": "Second paragraph cites [2024] SGCA 1 without treating it as a paragraph."},
    ]


def test_html_edge_cases_are_normalised() -> None:
    html = """
    <html><body>
      <p>Coram: The Honourable Justice Lee Seiu Kin</p>
      <p><i>Equity&nbsp;-&nbsp;Laches&nbsp;—&nbsp;Delay</i></p>
      <p>[1]&nbsp;The claimant’s “answer”&nbsp;—&nbsp;and the court’s view&nbsp;—&nbsp;was accepted.</p>
    </body></html>
    """

    parsed = parse_commonlii_sg_html(html)

    assert parsed["body_plain"] == (
        "[1] The claimant's \"answer\" - and the court's view - was accepted."
    )
    assert parsed["catchwords"] == "Equity - Laches - Delay"
    assert parsed["judges"] == ["Lee Seiu Kin"]


def test_current_b1_fixture_round_trip_keeps_plain_text_without_numbered_paragraphs() -> None:
    html = _fixture("sgca_2024_48.html")
    row = _row(html, url=SGCA_48_URL, citation="[2024] SGCA 48", court_code="SGCA", case_no=48)

    parsed = parse_commonlii_sg_row(row)

    assert "sale and purchase agreement" in str(parsed["body_plain"])
    assert "Copyright Policy" not in str(parsed["body_plain"])
    assert parsed["catchwords"] == ""
    assert parsed["judges"] == []
    assert parsed["paragraphs"] == []
    assert parsed["counsel"] == []
