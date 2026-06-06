"""MOM parser tests using A1 fixtures."""
from __future__ import annotations

from dataclasses import fields
from pathlib import Path

from data.parsers.mom_parser import MomRecord, parse_mom_html

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "mom"
PRESS_RELEASE = FIXTURE_DIR / "press_release_2026_0528_efma_offences.html"
PRESS_RELEASE_LISTING = FIXTURE_DIR / "press_releases_foreign_manpower_listing.html"
PRESS_RELEASE_URL = (
    "https://www.mom.gov.sg/newsroom/press-releases/2026/"
    "0528-2-singaporeans-and-an-employment-agency-charged-for-efma-offences"
)
PRESS_RELEASE_LISTING_URL = "https://www.mom.gov.sg/newsroom/press-releases?category=Foreign+manpower"


def test_parse_a1_press_release_fixture_yields_full_record() -> None:
    record = parse_mom_html(PRESS_RELEASE.read_text(encoding="utf-8"), PRESS_RELEASE_URL)
    assert [field.name for field in fields(MomRecord)] == [
        "doc_id",
        "source_url",
        "subsource",
        "title",
        "body_plain",
        "stated_breaches",
        "act_references",
        "subject_organisation",
        "pub_date",
    ]
    assert record.doc_id.startswith("mom_")
    assert record.source_url == PRESS_RELEASE_URL
    assert record.subsource == "press_release"
    assert record.title == (
        "Two Singaporeans and an employment agency charged with offences under "
        "the Employment of Foreign Manpower Act"
    )
    assert record.pub_date == "2026-05-28"
    assert record.subject_organisation == "Wonderful Agency Pte Ltd"
    assert record.stated_breaches == [
        "False declaration of employment",
        "False declaration of salary",
        "Collection of kickbacks",
    ]
    assert "s 22(1)(d) of the Employment of Foreign Manpower Act 1990" in record.act_references
    assert "s 20(1)(a) of the Employment of Foreign Manpower Act 1990" in record.act_references
    assert "s 22A(1)(a) of the Employment of Foreign Manpower Act 1990" in record.act_references
    assert "Employment of Foreign Manpower Act 1990" in record.act_references
    assert record.body_plain.startswith("On 28 May 2026, two Singaporeans")
    assert "Investigations revealed" in record.body_plain
    assert "Foreign manpower Work passes and permits" not in record.body_plain


def test_parse_a1_listing_fixture_does_not_infer_category_breaches() -> None:
    record = parse_mom_html(PRESS_RELEASE_LISTING.read_text(encoding="utf-8"), PRESS_RELEASE_LISTING_URL)
    assert record.subsource == "press_release"
    assert record.title == "Press releases"
    assert record.pub_date == "2024-03-14"
    assert record.stated_breaches == []
    assert "Two Singaporeans and an employment agency charged" in record.body_plain


def test_empty_stated_breaches_is_empty_list_not_none() -> None:
    html = """
    <html><head><meta name="published_date" content="2024-01-15"></head>
    <body><main><h1>FAQ on salary payment</h1>
    <p>Employers should pay salaries on time.</p></main></body></html>
    """
    record = parse_mom_html(html, "https://www.mom.gov.sg/faq/salary", subsource="faq")
    assert record.stated_breaches == []
    assert record.stated_breaches is not None


def test_repealed_or_withdrawn_pages_are_handled_gracefully() -> None:
    html = """
    <html><body><main>
    <h1>Withdrawn advisory on employment practices</h1>
    <p>This page has been withdrawn and is kept for reference only.</p>
    </main></body></html>
    """
    record = parse_mom_html(
        html,
        "https://www.mom.gov.sg/employment-practices/withdrawn-advisory",
        subsource="advisory",
    )
    assert record.title == "Withdrawn advisory on employment practices"
    assert record.body_plain == "This page has been withdrawn and is kept for reference only."
    assert record.stated_breaches == []
    assert record.pub_date == ""


def test_unicode_and_whitespace_are_normalised() -> None:
    html = """
    <html><head><meta name="published_date" content="3/2/2024"></head>
    <body><main><h1>Salary&nbsp;\t advisory</h1>
    <p>Acme&nbsp;Pte&nbsp;Ltd&nbsp;failed\u00ad to pay salary.<br>Workers said \u201cno CPF\u201d.</p>
    <table><tr><td><strong>Type of Breach</strong></td></tr>
    <tr><td>Notice&nbsp;&nbsp;Period\tBreach</td></tr></table>
    </main></body></html>
    """
    record = parse_mom_html(html, "https://www.mom.gov.sg/example", subsource="advisory")
    assert record.title == "Salary advisory"
    assert record.pub_date == "2024-02-03"
    assert record.subject_organisation == "Acme Pte Ltd"
    assert "failed to pay salary. Workers said \u201cno CPF\u201d." in record.body_plain
    assert record.stated_breaches == ["Notice Period Breach"]
