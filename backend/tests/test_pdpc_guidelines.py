"""Unit tests for PDPC Advisory Guidelines ingestion (SGLB-14 source corpus)."""
from __future__ import annotations

import io
import json
from pathlib import Path

import httpx
from pypdf import PdfWriter

from api.adapters.public.pdpc_guidance import PdpcGuidanceAdapter
from data.ingestion import pdpc_guidelines

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "pdpc_guidelines"
PDF_FIXTURE = FIXTURE_DIR / "introduction-part-1-270717.pdf"


def test_extract_pdf_text_from_pdpc_fixture():
    text = pdpc_guidelines.extract_pdf_text(PDF_FIXTURE)
    assert "The Personal Data Protection Act 2012" in text
    assert "Guidelines are advisory in nature" in text
    assert len(text) > 5_000


def test_extract_section_headings_from_pdf_text():
    text = pdpc_guidelines.extract_pdf_text(PDF_FIXTURE)
    headings = pdpc_guidelines.extract_section_headings(text)
    assert "PART I: INTRODUCTION" in headings
    assert "1 Introduction" in headings


def test_parse_guideline_page_extracts_metadata_pdf_links_and_headings():
    page = """
    <h1>Advisory Guidelines on Key Concepts in the PDPA</h1>
    <span class="page-banner__date">Published on 23 Sep 2013</span>
    <p>The <a href="/assets/key-concepts">full document is available here</a>.</p>
    <h2>Chapters Listing</h2>
    <ul>
      <li>Chapter 12: The Consent Obligation</li>
      <li>Annex A: Framework for the Collection, Use and Disclosure of Personal Data</li>
    </ul>
    """
    candidates = pdpc_guidelines.parse_guideline_page(
        page,
        "https://www.pdpc.gov.sg/organisations/regulations-decisions/regulatory-guidance/key",
    )
    assert len(candidates) == 1
    candidate = candidates[0]
    assert candidate.title == "Advisory Guidelines on Key Concepts in the PDPA"
    assert candidate.pdf_url == "https://www.pdpc.gov.sg/assets/key-concepts"
    assert candidate.pub_date == pdpc_guidelines.parse_pub_date("23 Sep 2013")
    assert "Chapter 12: The Consent Obligation" in candidate.page_headings


def test_parse_guideline_page_handles_next_rsc_banner_fields():
    page = """
    21:["$","h1",null,{"children":"Advisory Guidelines on Key Concepts in the Personal Data Protection Act"}]
    22:["$","span",null,{"className":"page-banner__date","children":["Published on ","23 Sep 2013"]}]
    27:T123,<p>The <a href="/assets/key-concepts">full document is available here</a>.</p>
    """
    candidates = pdpc_guidelines.parse_guideline_page(
        page,
        "https://www.pdpc.gov.sg/organisations/regulations-decisions/regulatory-guidance/key",
    )
    assert candidates[0].title == (
        "Advisory Guidelines on Key Concepts in the Personal Data Protection Act"
    )
    assert candidates[0].pub_date == pdpc_guidelines.parse_pub_date("23 Sep 2013")


def test_build_guideline_jsonl_row_shape_from_fixture():
    candidate = pdpc_guidelines.GuidelineCandidate(
        source_url="https://www.pdpc.gov.sg/source",
        title="PDPC fixture",
        pdf_url="https://www.pdpc.gov.sg/fixture.pdf",
        pub_date=pdpc_guidelines.parse_pub_date("27 Jul 2017"),
        page_headings=["Chapters Listing"],
    )
    row = pdpc_guidelines.build_guideline_from_pdf(candidate, PDF_FIXTURE).as_jsonl_row()
    assert set(row) == {
        "doc_id",
        "source_url",
        "title",
        "pdf_url",
        "body_plain",
        "section_headings",
        "pub_date",
    }
    assert row["doc_id"].startswith("pdpc_guideline_")
    assert row["pub_date"] == "2017-07-27"
    assert "The Personal Data Protection Act 2012" in str(row["body_plain"])


def test_ingest_discovers_assets_downloads_pdf_and_writes_jsonl(tmp_path: Path):
    fixture_bytes = PDF_FIXTURE.read_bytes()
    page_url = (
        "https://www.pdpc.gov.sg/organisations/regulations-decisions/"
        "regulatory-guidance/advisory-guidelines-on-key-concepts-in-the-personal-data-protection-act"
    )
    sitemap = f"""
    <urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">
      <url><loc>{page_url}</loc></url>
    </urlset>
    """
    page = """
    <h1>Advisory Guidelines on Key Concepts in the PDPA</h1>
    <span class="page-banner__date">Published on 23 Sep 2013</span>
    <p>The <a href="/assets/key-concepts">full document is available here</a>.</p>
    <h2>Chapters Listing</h2><ul><li>Chapter 12: The Consent Obligation</li></ul>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == "https://www.pdpc.gov.sg/sitemap.xml":
            return httpx.Response(200, text=sitemap)
        if str(request.url) == page_url:
            return httpx.Response(200, text=page)
        if str(request.url) == "https://www.pdpc.gov.sg/assets/key-concepts":
            return httpx.Response(200, content=fixture_bytes, headers={"content-type": "application/pdf"})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        stats = pdpc_guidelines.ingest(
            output_path=tmp_path / "guidelines.jsonl",
            pdf_dir=tmp_path / "pdf",
            source_urls=("https://www.pdpc.gov.sg/sitemap.xml",),
            crawl_delay=0,
            client=client,
        )

    assert stats.candidates == 1
    assert stats.written == 1
    assert stats.fully_extracted == 1
    assert not stats.low_text_pdfs
    line = (tmp_path / "guidelines.jsonl").read_text(encoding="utf-8").splitlines()[0]
    row = json.loads(line)
    assert row["pdf_url"] == "https://www.pdpc.gov.sg/assets/key-concepts"
    assert "The Personal Data Protection Act 2012" in row["body_plain"]


def test_ingest_flags_low_text_pdf(tmp_path: Path):
    writer = PdfWriter()
    writer.add_blank_page(width=72, height=72)
    blank = io.BytesIO()
    writer.write(blank)
    page_url = (
        "https://www.pdpc.gov.sg/organisations/regulations-decisions/"
        "regulatory-guidance/advisory-guidelines-on-the-do-not-call-provisions"
    )

    def handler(request: httpx.Request) -> httpx.Response:
        if str(request.url) == page_url:
            return httpx.Response(
                200,
                text=(
                    "<h1>Advisory Guidelines on the Do Not Call Provisions</h1>"
                    '<a href="/assets/scanned">full document is available here</a>'
                ),
            )
        if str(request.url) == "https://www.pdpc.gov.sg/assets/scanned":
            return httpx.Response(200, content=blank.getvalue(), headers={"content-type": "application/pdf"})
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler), follow_redirects=True) as client:
        stats = pdpc_guidelines.ingest(
            output_path=tmp_path / "guidelines.jsonl",
            pdf_dir=tmp_path / "pdf",
            source_urls=(page_url,),
            crawl_delay=0,
            min_text_chars=10,
            client=client,
        )

    assert stats.written == 1
    assert stats.fully_extracted == 0
    assert stats.low_text_pdfs == ["https://www.pdpc.gov.sg/assets/scanned"]


def test_pdpc_guidance_adapter_wraps_jsonl_rows(tmp_path: Path):
    row = pdpc_guidelines.PdpcGuideline(
        doc_id="pdpc_guideline_test",
        source_url="https://www.pdpc.gov.sg/source",
        title="Advisory Guidelines on Key Concepts in the PDPA",
        pdf_url="https://www.pdpc.gov.sg/assets/key",
        body_plain="The Personal Data Protection Act 2012 establishes a general data protection law.",
        section_headings=["Chapter 12: The Consent Obligation"],
        pub_date=pdpc_guidelines.parse_pub_date("23 Sep 2013"),
    )
    path = tmp_path / "guidelines.jsonl"
    pdpc_guidelines.write_jsonl([row], path)

    docs = list(PdpcGuidanceAdapter(jsonl_path=path).fetch_all())
    assert len(docs) == 1
    doc = docs[0]
    assert doc.document_id == "pdpc_guideline_test"
    assert doc.doc_type == "guideline"
    assert doc.published_date == pdpc_guidelines.parse_pub_date("23 Sep 2013")
    assert doc.extra["pdf_url"] == "https://www.pdpc.gov.sg/assets/key"
    assert doc.extra["section_headings"] == ["Chapter 12: The Consent Obligation"]
