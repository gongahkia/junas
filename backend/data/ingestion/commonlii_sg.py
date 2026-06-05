"""CommonLII Singapore case judgment ingestion.

Fetches court/year listing pages from CommonLII SG, follows judgment links,
and emits one raw-HTML JSONL row per judgment. Parsing into plain text and
jurisdiction statements is intentionally left to the downstream B2 parser.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import json
import logging
import random
import re
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Iterator, Sequence
from urllib.parse import urljoin, urlparse, urlunparse

import httpx
from bs4 import BeautifulSoup

from api.adapters.public.commonlii_sg import CommonliiSgAdapter
from data.ingestion._provenance import extraction_rule_sha

logger = logging.getLogger(__name__)

COMMONLII_BASE = "http://www.commonlii.org"
COMMONLII_CASES_BASE = f"{COMMONLII_BASE}/sg/cases/"
COURTS: tuple[str, ...] = ("SGCA", "SGHC", "SGDC", "SGMC", "SGSAC")
DEFAULT_OUTPUT = Path("vendor-data/sg_cases/judgments.jsonl")
USER_AGENT = "Mozilla/5.0 (compatible; junas-research/0.1; +https://github.com/gongahkia/junas)"
DEFAULT_TIMEOUT = 60.0
DEFAULT_CRAWL_DELAY = CommonliiSgAdapter.metadata.crawl_delay_seconds
MAX_RETRIES = 4
BACKOFF_BASE = 2.0
EXTRACTION_MODULE = Path(__file__)

_CASE_URL_RE = re.compile(
    r"^/sg/cases/(?P<court>SGCA|SGHC|SGDC|SGMC|SGSAC)/(?P<year>\d{4})/(?P<case_no>\d+)\.html$"
)
_YEAR_URL_RE = re.compile(
    r"^/sg/cases/(?P<court>SGCA|SGHC|SGDC|SGMC|SGSAC)/(?P<year>\d{4})/?$"
)
_NEUTRAL_CITATION_RE = re.compile(
    r"\[(?P<year>\d{4})\]\s+(?P<court>SGCA|SGHC|SGDC|SGMC|SGSAC)\s+(?P<case_no>\d+)"
)
_DATE_RE = re.compile(r"\b\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4}\b")
_PAREN_DATE_RE = re.compile(r"\(([^()]*\d{4}[^()]*)\)")
_WS_RE = re.compile(r"\s+")

_DATE_FORMATS = (
    "%d %b %Y",
    "%d %B %Y",
    "%d %b, %Y",
    "%d %B, %Y",
    "%Y-%m-%d",
)

Sleeper = Callable[[float], None]


@dataclass(frozen=True)
class JudgmentLink:
    html_url: str
    listing_url: str
    citation: str
    court_code: str
    year: int
    case_no: int
    decision_date: dt.date | None = None
    title: str = ""


@dataclass
class IngestStats:
    listings: int = 0
    candidates: int = 0
    fetched: int = 0
    written: int = 0
    skipped_existing: int = 0
    skipped_errors: int = 0


def _sleep_with_jitter(delay: float, *, sleeper: Sleeper = time.sleep) -> None:
    if delay <= 0:
        return
    sleeper(delay + random.uniform(0, 0.5))  # nosec - pacing jitter, not crypto


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html"},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )


def _looks_like_cloudflare_challenge(text: str) -> bool:
    lowered = text[:4096].lower()
    return "just a moment" in lowered and "__cf_chl" in lowered


def fetch_html(
    url: str,
    *,
    client: httpx.Client | None = None,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    max_retries: int = MAX_RETRIES,
    sleeper: Sleeper = time.sleep,
) -> str:
    """Fetch one CommonLII page with SSO-style retry and pacing."""
    owned = False
    if client is None:
        client = _client()
        owned = True
    try:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = client.get(url)
                if response.status_code == 200:
                    if _looks_like_cloudflare_challenge(response.text):
                        raise RuntimeError(
                            f"CommonLII returned a browser challenge instead of HTML: {url}"
                        )
                    return response.text
                if response.status_code in (429, 500, 502, 503, 504):
                    raise httpx.HTTPStatusError(
                        f"transient {response.status_code}",
                        request=response.request,
                        response=response,
                    )
                response.raise_for_status()
                return response.text
            except (httpx.HTTPError, httpx.TransportError) as exc:
                last_exc = exc
                if attempt == max_retries:
                    break
                backoff = BACKOFF_BASE * (2**attempt) + random.uniform(0, 1)  # nosec
                logger.warning("CommonLII fetch %s failed (%s); retry in %.1fs", url, exc, backoff)
                sleeper(backoff)
        raise RuntimeError(f"CommonLII fetch failed after {max_retries + 1} attempts: {url}") from last_exc
    finally:
        if owned:
            client.close()
        _sleep_with_jitter(crawl_delay, sleeper=sleeper)


def canonical_url(url: str, base_url: str = COMMONLII_CASES_BASE) -> str:
    parsed = urlparse(urljoin(base_url, url))
    return urlunparse(("http", "www.commonlii.org", parsed.path, "", "", ""))


def court_index_url(court_code: str) -> str:
    return f"{COMMONLII_CASES_BASE}{court_code}/"


def year_listing_url(court_code: str, year: int) -> str:
    return f"{COMMONLII_CASES_BASE}{court_code}/{year}/"


def judgment_url(court_code: str, year: int, case_no: int) -> str:
    return f"{COMMONLII_CASES_BASE}{court_code}/{year}/{case_no}.html"


def stable_case_id(html_url: str) -> str:
    digest = hashlib.sha256(canonical_url(html_url).encode("utf-8")).hexdigest()[:12]
    return f"commonlii_sg_{digest}"


def planned_urls(court: str | None = None, year: int | None = None) -> list[str]:
    courts = _selected_courts(court)
    if year is not None:
        return [year_listing_url(c, year) for c in courts]
    return [court_index_url(c) for c in courts]


def parse_court_years(html: str, court_url: str) -> list[int]:
    soup = BeautifulSoup(html, "html.parser")
    years: set[int] = set()
    for link in soup.find_all("a", href=True):
        href = str(link.get("href") or "")
        parsed = urlparse(canonical_url(href, court_url))
        match = _YEAR_URL_RE.match(parsed.path)
        if match:
            years.add(int(match.group("year")))
            continue
        text = _normalise_text(link.get_text(" ", strip=True))
        if re.fullmatch(r"\d{4}", text):
            years.add(int(text))
    return sorted(years, reverse=True)


def parse_listing_page(html: str, listing_url: str) -> list[JudgmentLink]:
    soup = BeautifulSoup(html, "html.parser")
    links: list[JudgmentLink] = []
    seen: set[str] = set()
    for anchor in soup.find_all("a", href=True):
        html_url = canonical_url(str(anchor.get("href") or ""), listing_url)
        match = _case_url_match(html_url)
        if match is None or html_url in seen:
            continue
        seen.add(html_url)
        anchor_text = _normalise_text(anchor.get_text(" ", strip=True))
        parent_text = _normalise_text(anchor.parent.get_text(" ", strip=True)) if anchor.parent else ""
        text = parent_text or anchor_text
        court_code = match.group("court")
        year = int(match.group("year"))
        case_no = int(match.group("case_no"))
        citation = _citation_from_text(text) or f"[{year}] {court_code} {case_no}"
        links.append(
            JudgmentLink(
                html_url=html_url,
                listing_url=canonical_url(listing_url),
                citation=citation,
                court_code=court_code,
                year=year,
                case_no=case_no,
                decision_date=_date_from_text(text, fallback_year=year),
                title=_title_from_listing_text(anchor_text, citation),
            )
        )
    return links


def build_judgment_row(link: JudgmentLink, body_html: str) -> dict[str, object]:
    text = _normalise_text(BeautifulSoup(body_html, "html.parser").get_text(" ", strip=True))
    citation = _citation_from_text(text) or link.citation
    decision_date = link.decision_date or _date_from_text(text, fallback_year=link.year)
    return {
        "case_id": stable_case_id(link.html_url),
        "citation": citation,
        "court_code": link.court_code,
        "year": link.year,
        "case_no": link.case_no,
        "decision_date": decision_date.isoformat() if decision_date else "",
        "source_url": link.html_url,
        "html_url": link.html_url,
        "body_html": body_html,
        "body_plain": "",
        "extraction_rule_sha": _extraction_rule_sha(),
    }


def write_jsonl(rows: Sequence[dict[str, object]], output_path: Path, *, append: bool = False) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    existing = _existing_case_ids(output_path) if append else set()
    mode = "a" if append else "w"
    written = 0
    with output_path.open(mode, encoding="utf-8") as handle:
        for row in rows:
            case_id = str(row.get("case_id") or "")
            if not case_id or case_id in existing:
                continue
            existing.add(case_id)
            handle.write(json.dumps(row, ensure_ascii=False) + "\n")
            written += 1
    return written


def discover_listing_urls(
    courts: Sequence[str],
    *,
    year: int | None = None,
    client: httpx.Client,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    sleeper: Sleeper = time.sleep,
) -> Iterator[str]:
    if year is not None:
        for court_code in courts:
            yield year_listing_url(court_code, year)
        return
    for court_code in courts:
        court_url = court_index_url(court_code)
        html = fetch_html(court_url, client=client, crawl_delay=crawl_delay, sleeper=sleeper)
        years = parse_court_years(html, court_url)
        for found_year in years:
            yield year_listing_url(court_code, found_year)


def ingest(
    output_path: Path | str = DEFAULT_OUTPUT,
    *,
    court: str | None = None,
    year: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    client: httpx.Client | None = None,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    force: bool = False,
    sleeper: Sleeper = time.sleep,
) -> IngestStats:
    output = Path(output_path)
    courts = _selected_courts(court)
    if dry_run:
        for url in planned_urls(court, year):
            print(url)
        return IngestStats(listings=len(planned_urls(court, year)))

    existing = set() if force else _existing_case_ids(output)
    rows: list[dict[str, object]] = []
    stats = IngestStats()
    owned = False
    if client is None:
        client = _client()
        owned = True
    try:
        for listing_url in discover_listing_urls(
            courts,
            year=year,
            client=client,
            crawl_delay=crawl_delay,
            sleeper=sleeper,
        ):
            if limit is not None and len(rows) >= limit:
                break
            stats.listings += 1
            try:
                listing_html = fetch_html(
                    listing_url,
                    client=client,
                    crawl_delay=crawl_delay,
                    sleeper=sleeper,
                )
            except RuntimeError as exc:
                stats.skipped_errors += 1
                logger.warning("CommonLII skip listing %s: %s", listing_url, exc)
                continue
            for link in parse_listing_page(listing_html, listing_url):
                if limit is not None and len(rows) >= limit:
                    break
                stats.candidates += 1
                case_id = stable_case_id(link.html_url)
                if case_id in existing:
                    stats.skipped_existing += 1
                    continue
                try:
                    body_html = fetch_html(
                        link.html_url,
                        client=client,
                        crawl_delay=crawl_delay,
                        sleeper=sleeper,
                    )
                except RuntimeError as exc:
                    stats.skipped_errors += 1
                    logger.warning("CommonLII skip judgment %s: %s", link.html_url, exc)
                    continue
                row = build_judgment_row(link, body_html)
                rows.append(row)
                existing.add(case_id)
                stats.fetched += 1
        stats.written = write_jsonl(rows, output, append=not force)
        logger.info("CommonLII SG wrote %d judgment rows to %s", stats.written, output)
        return stats
    finally:
        if owned:
            client.close()


def run(
    output_path: Path | str = DEFAULT_OUTPUT,
    *,
    court: str | None = None,
    year: int | None = None,
    limit: int | None = None,
    dry_run: bool = False,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    force: bool = False,
) -> int:
    stats = ingest(
        output_path,
        court=court,
        year=year,
        limit=limit,
        dry_run=dry_run,
        crawl_delay=crawl_delay,
        force=force,
    )
    return stats.written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest SG judgments from CommonLII")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--court", choices=COURTS)
    parser.add_argument("--year", type=int)
    parser.add_argument("--limit", type=int)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--crawl-delay", type=float, default=DEFAULT_CRAWL_DELAY)
    parser.add_argument("--force", action="store_true", help="rebuild output instead of appending")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(
        args.output,
        court=args.court,
        year=args.year,
        limit=args.limit,
        dry_run=args.dry_run,
        crawl_delay=args.crawl_delay,
        force=args.force,
    )


def _selected_courts(court: str | None) -> tuple[str, ...]:
    if court is None:
        return COURTS
    value = court.upper()
    if value not in COURTS:
        raise ValueError(f"unsupported CommonLII SG court: {court}")
    return (value,)


def _case_url_match(html_url: str) -> re.Match[str] | None:
    return _CASE_URL_RE.match(urlparse(canonical_url(html_url)).path)


def _normalise_text(raw: str) -> str:
    return _WS_RE.sub(" ", raw or "").strip()


def _citation_from_text(text: str) -> str:
    match = _NEUTRAL_CITATION_RE.search(text or "")
    return match.group(0) if match else ""


def _title_from_listing_text(text: str, citation: str) -> str:
    value = text
    if citation:
        value = value.split(citation, 1)[0]
    value = re.sub(r"\s*[-–]\s*$", "", value)
    return _normalise_text(value)


def _date_from_text(text: str, *, fallback_year: int | None = None) -> dt.date | None:
    for paren in _PAREN_DATE_RE.findall(text or ""):
        parsed = _parse_date(paren, fallback_year=fallback_year)
        if parsed:
            return parsed
    match = _DATE_RE.search(text or "")
    if not match:
        return None
    return _parse_date(match.group(0), fallback_year=fallback_year)


def _parse_date(raw: str, *, fallback_year: int | None = None) -> dt.date | None:
    cleaned = _normalise_text(raw.replace("\xa0", " "))
    if fallback_year is not None and not re.search(r"\b\d{4}\b", cleaned):
        cleaned = f"{cleaned} {fallback_year}"
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(cleaned, fmt).date()
        except ValueError:
            continue
    return None


def _existing_case_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    ids: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            case_id = row.get("case_id")
            if case_id:
                ids.add(str(case_id))
    return ids


def _extraction_rule_sha() -> str:
    try:
        return extraction_rule_sha(EXTRACTION_MODULE)
    except RuntimeError:
        return hashlib.sha256(EXTRACTION_MODULE.read_bytes()).hexdigest()[:7]


if __name__ == "__main__":
    raise SystemExit(0 if main() >= 0 else 1)
