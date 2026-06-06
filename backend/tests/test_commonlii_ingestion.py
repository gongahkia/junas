"""Fetcher tests for CommonLII SG ingestion."""
from __future__ import annotations

import json
from pathlib import Path

import httpx

from data.ingestion import commonlii_sg

FIXTURE_DIR = Path(__file__).parent / "fixtures" / "commonlii_sg"
SGCA_LISTING_URL = commonlii_sg.year_listing_url("SGCA", 2024)
SGCA_48_URL = commonlii_sg.judgment_url("SGCA", 2024, 48)
SGHC_251_URL = commonlii_sg.judgment_url("SGHC", 2024, 251)


def _fixture(name: str) -> str:
    return (FIXTURE_DIR / name).read_text(encoding="utf-8")


def test_parse_listing_page_extracts_canonical_case_links():
    links = commonlii_sg.parse_listing_page(_fixture("sgca_2024_listing.html"), SGCA_LISTING_URL)

    assert len(links) == 2
    assert links[0].html_url == SGCA_48_URL
    assert links[0].citation == "[2024] SGCA 48"
    assert links[0].court_code == "SGCA"
    assert links[0].year == 2024
    assert links[0].case_no == 48
    assert links[0].decision_date and links[0].decision_date.isoformat() == "2024-11-06"


def test_build_judgment_row_from_sghc_fixture():
    link = commonlii_sg.JudgmentLink(
        html_url=SGHC_251_URL,
        listing_url=commonlii_sg.year_listing_url("SGHC", 2024),
        citation="[2024] SGHC 251",
        court_code="SGHC",
        year=2024,
        case_no=251,
    )

    row = commonlii_sg.build_judgment_row(link, _fixture("sghc_2024_251.html"))

    assert row["case_id"] == commonlii_sg.stable_case_id(SGHC_251_URL)
    assert row["citation"] == "[2024] SGHC 251"
    assert row["court_code"] == "SGHC"
    assert row["decision_date"] == "2024-10-03"
    assert row["source_url"] == SGHC_251_URL
    assert row["html_url"] == SGHC_251_URL
    assert "Public Prosecutor v S Iswaran" in str(row["body_plain"])
    assert row["paragraphs"] == []
    assert row["jurisdiction_statements"] == []
    assert "Public Prosecutor v S Iswaran" in str(row["body_html"])


def test_ingest_constructs_urls_paces_and_writes(monkeypatch, tmp_path: Path):
    requests: list[str] = []
    sleeps: list[float] = []
    monkeypatch.setattr(commonlii_sg.random, "uniform", lambda _start, _end: 0)

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if str(request.url) == SGCA_LISTING_URL:
            return httpx.Response(200, text=_fixture("sgca_2024_listing.html"))
        if str(request.url) == SGCA_48_URL:
            return httpx.Response(200, text=_fixture("sgca_2024_48.html"))
        return httpx.Response(404)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        stats = commonlii_sg.ingest(
            tmp_path / "judgments.jsonl",
            court="SGCA",
            year=2024,
            limit=1,
            client=client,
            crawl_delay=5,
            sleeper=sleeps.append,
        )

    assert requests == [SGCA_LISTING_URL, SGCA_48_URL]
    assert sleeps == [5, 5]
    assert stats.listings == 1
    assert stats.candidates == 1
    assert stats.fetched == 1
    assert stats.written == 1
    row = json.loads((tmp_path / "judgments.jsonl").read_text(encoding="utf-8"))
    assert row["case_id"] == commonlii_sg.stable_case_id(SGCA_48_URL)
    assert row["citation"] == "[2024] SGCA 48"
    assert row["decision_date"] == "2024-11-06"
    assert "Li Jialin" in str(row["body_plain"])
    assert row["jurisdiction_statements"] == []


def test_fetch_html_retries_transient_status_and_paces(monkeypatch):
    calls = 0
    sleeps: list[float] = []
    monkeypatch.setattr(commonlii_sg.random, "uniform", lambda _start, _end: 0)

    def handler(_request: httpx.Request) -> httpx.Response:
        nonlocal calls
        calls += 1
        if calls == 1:
            return httpx.Response(503, text="temporarily unavailable")
        return httpx.Response(200, text="<html>ok</html>")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        text = commonlii_sg.fetch_html(
            SGCA_48_URL,
            client=client,
            max_retries=1,
            crawl_delay=5,
            sleeper=sleeps.append,
        )

    assert text == "<html>ok</html>"
    assert calls == 2
    assert sleeps == [2, 5]


def test_ingest_skips_existing_case_without_refetching_judgment(monkeypatch, tmp_path: Path):
    requests: list[str] = []
    monkeypatch.setattr(commonlii_sg.random, "uniform", lambda _start, _end: 0)
    output = tmp_path / "judgments.jsonl"
    output.write_text(json.dumps({"case_id": commonlii_sg.stable_case_id(SGCA_48_URL)}) + "\n")
    listing = """
    <html><body>
      <a href="48.html">Li Jialin and another v Wingcrown Investment Pte Ltd [2024] SGCA 48</a> (6 November 2024)
    </body></html>
    """

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(str(request.url))
        if str(request.url) == SGCA_LISTING_URL:
            return httpx.Response(200, text=listing)
        raise AssertionError(f"unexpected judgment fetch: {request.url}")

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        stats = commonlii_sg.ingest(
            output,
            court="SGCA",
            year=2024,
            client=client,
            crawl_delay=0,
        )

    assert requests == [SGCA_LISTING_URL]
    assert stats.skipped_existing == 1
    assert stats.fetched == 0
    assert output.read_text(encoding="utf-8").count("\n") == 1


def test_main_dry_run_prints_planned_urls(tmp_path: Path, capsys):
    code = commonlii_sg.main(
        [
            "--output",
            str(tmp_path / "judgments.jsonl"),
            "--court",
            "SGCA",
            "--year",
            "2024",
            "--dry-run",
        ]
    )

    assert code == 0
    assert capsys.readouterr().out.strip() == SGCA_LISTING_URL
    assert not (tmp_path / "judgments.jsonl").exists()
