"""MOM enforcement/guidance network ingestion (SGLB-05).

This module intentionally stops at the network boundary. It discovers
candidate MOM enforcement/guidance pages, fetches the raw public payloads
with conservative pacing/retry, and writes JSONL rows with the SGLB-05
envelope plus raw HTML/JSON for ``data.parsers.mom_parser`` to interpret.

Network safety: CLI runs are dry-run by default. Pass ``--live`` only
after the operator has approved live MOM requests.
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import logging
import random
import re
import time
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable, Iterator
from urllib.parse import parse_qs, urlencode, urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

from data.ingestion._provenance import extraction_rule_sha

logger = logging.getLogger(__name__)

MOM_BASE = "https://www.mom.gov.sg"
USER_AGENT = "Mozilla/5.0 (compatible; junas-research/0.1; +https://github.com/gongahkia/junas)"
DEFAULT_CRAWL_DELAY = 3.0
DEFAULT_TIMEOUT = 60.0
MAX_RETRIES = 4
BACKOFF_BASE = 2.0
DEFAULT_OUTPUT = Path("vendor-data/mom/enforcement.jsonl")
EXTRACTION_MODULE = Path(__file__)
EXTRACTION_RULE_NAME = "mom"

PRESS_RELEASE_CATEGORIES: tuple[str, ...] = (
    "Employment practices",
    "Foreign manpower",
    "Work passes and permits",
)
GUIDANCE_URLS: tuple[str, ...] = (
    f"{MOM_BASE}/employment-practices",
    f"{MOM_BASE}/employment-practices/employers-convicted-under-employment-act",
)
FAQ_INDEX_URL = f"{MOM_BASE}/faq"
CONVICTED_EMPLOYERS_APP = "employers-convicted-employment-act"
CONVICTED_EMPLOYERS_PAGE = f"{MOM_BASE}/employment-practices/employers-convicted-under-employment-act"
CONVICTED_EMPLOYERS_API = f"{MOM_BASE}/api/v2/Rows"
CONVICTED_EMPLOYERS_PER_PAGE = 20

_ENFORCEMENT_TITLE_RE = re.compile(
    r"\b("
    r"arrest(?:ed|s)?|charg(?:ed|es?)|convict(?:ed|ion|s)?|enforcement|"
    r"offen[cs]es?|prosecut(?:ed|ion|e)?|fined?|penalt(?:y|ies)|"
    r"kickbacks?|false declarations?|illegal employment|fail(?:ed|ing)? to pay|"
    r"salary offences?|employment act"
    r")\b",
    re.IGNORECASE,
)
_PRESS_RELEASE_PATH_RE = re.compile(r"^/newsroom/press-releases/\d{4}/[^/?#]+$")


@dataclass(frozen=True)
class PlannedUrl:
    kind: str
    url: str
    note: str = ""


@dataclass(frozen=True)
class ListingItem:
    url: str
    title: str
    pub_date: str
    categories: tuple[str, ...]


@dataclass
class MomRecord:
    doc_id: str
    source_url: str
    subsource: str
    title: str
    body_plain: str
    stated_breaches: list[str]
    act_references: list[str]
    subject_organisation: str | None
    pub_date: str
    extraction_rule_sha: str
    raw_html: str = ""
    raw_json: dict[str, Any] | None = None
    fetched_at: str = ""
    candidate_reason: str = ""
    content_type: str = ""

    def as_jsonl_row(self) -> dict[str, Any]:
        return asdict(self)


def stable_id(source_url: str) -> str:
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:12]
    return f"mom_{digest}"


def _sleep_with_jitter(delay: float) -> None:
    if delay <= 0:
        return
    time.sleep(delay + random.uniform(0, 0.5))  # nosec - pacing jitter, not crypto


def fetch_text(
    url: str,
    *,
    client: httpx.Client | None = None,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    max_retries: int = MAX_RETRIES,
) -> str:
    """Fetch one MOM URL with SSO-style retry/backoff and post-request pacing."""
    owned = False
    if client is None:
        client = httpx.Client(
            headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
            timeout=DEFAULT_TIMEOUT,
            follow_redirects=True,
        )
        owned = True
    try:
        last_exc: Exception | None = None
        for attempt in range(max_retries + 1):
            try:
                response = client.get(url)
                if response.status_code == 200:
                    return response.text
                if response.status_code == 429 or 500 <= response.status_code <= 599:
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
                backoff = max(crawl_delay, BACKOFF_BASE * (2 ** attempt)) + random.uniform(0, 1)  # nosec
                logger.warning("MOM fetch %s failed (%s); retry in %.1fs", url, exc, backoff)
                time.sleep(backoff)
        raise RuntimeError(f"MOM fetch failed after {max_retries + 1} attempts: {url}") from last_exc
    finally:
        if owned:
            client.close()
        _sleep_with_jitter(crawl_delay)


def press_release_listing_url(category: str, page: int = 1) -> str:
    params: dict[str, str] = {"category": category}
    if page > 1:
        params["page"] = str(page)
    return f"{MOM_BASE}/newsroom/press-releases?{urlencode(params)}"


def convicted_employers_api_url(page: int = 1) -> str:
    params = {
        "app_name": CONVICTED_EMPLOYERS_APP,
        "per_page": str(CONVICTED_EMPLOYERS_PER_PAGE),
        "page": str(page),
        "order": "ASC",
        "orderby": "",
        "q": "",
    }
    return f"{CONVICTED_EMPLOYERS_API}?{urlencode(params)}"


def planned_urls() -> list[PlannedUrl]:
    planned = [
        PlannedUrl(
            "press_release_listing",
            press_release_listing_url(category),
            "pagination discovered from page links; detail URLs discovered from listing items",
        )
        for category in PRESS_RELEASE_CATEGORIES
    ]
    planned.extend(PlannedUrl("guidance_page", url, "raw HTML guidance/advisory seed") for url in GUIDANCE_URLS)
    planned.append(
        PlannedUrl(
            "advisory_api",
            convicted_employers_api_url(1),
            "DB app endpoint for convicted Employment Act employers; pagination discovered from JSON",
        )
    )
    planned.append(
        PlannedUrl(
            "faq_index",
            FAQ_INDEX_URL,
            "index only; robots.txt disallows direct /faq?faqItem= crawls",
        )
    )
    return planned


def print_dry_run() -> int:
    for item in planned_urls():
        suffix = f" # {item.note}" if item.note else ""
        print(f"{item.kind}\t{item.url}{suffix}")
    return 0


def _meta_content(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return str(tag["content"]).strip()
    tag = soup.find("meta", attrs={"property": f"og:{name}"})
    if tag and tag.get("content"):
        return str(tag["content"]).strip()
    return ""


def _title_from_html(soup: BeautifulSoup) -> str:
    meta_title = _meta_content(soup, "title")
    if meta_title:
        return html.unescape(meta_title)
    h1 = soup.find("h1")
    if h1:
        return " ".join(h1.get_text(" ", strip=True).split())
    title = soup.find("title")
    if title:
        return " ".join(title.get_text(" ", strip=True).split())
    return ""


def _parse_page_number(url: str) -> int | None:
    raw = parse_qs(urlparse(url).query).get("page", [""])[0]
    if not raw:
        return None
    try:
        return int(raw)
    except ValueError:
        return None


def extract_last_page(html_text: str) -> int:
    soup = BeautifulSoup(html_text, "html.parser")
    pages = [1]
    for anchor in soup.find_all("a", href=True):
        page = _parse_page_number(str(anchor["href"]))
        if page:
            pages.append(page)
    return max(pages)


def extract_listing_items(html_text: str) -> list[ListingItem]:
    soup = BeautifulSoup(html_text, "html.parser")
    items: list[ListingItem] = []
    for article in soup.find_all("article"):
        link = article.find("a", href=True)
        if not link:
            continue
        href = str(link["href"]).strip()
        parsed = urlparse(href)
        path = parsed.path if parsed.scheme else href.split("?", 1)[0]
        if not _PRESS_RELEASE_PATH_RE.match(path):
            continue
        time_tag = article.find("time")
        categories = tuple(
            " ".join(a.get_text(" ", strip=True).split())
            for a in article.find_all("a", href=True)
            if "/newsroom/press-releases?category=" in str(a["href"])
        )
        items.append(
            ListingItem(
                url=urljoin(MOM_BASE, href),
                title=" ".join(link.get_text(" ", strip=True).split()),
                pub_date=str(time_tag.get("datetime", "")).strip() if time_tag else "",
                categories=categories,
            )
        )
    return items


def is_enforcement_candidate(item: ListingItem) -> bool:
    haystack = " ".join((item.title, *item.categories))
    return bool(_ENFORCEMENT_TITLE_RE.search(haystack))


def _normalise_listing_date(raw: str) -> str:
    raw = (raw or "").strip()
    if not raw:
        return ""
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            continue
    parts = raw.split("-")
    if len(parts) == 3 and all(part.isdigit() for part in parts):
        year, month, day = (int(part) for part in parts)
        try:
            return dt.date(year, month, day).isoformat()
        except ValueError:
            return raw
    return raw


def _record_from_html(
    url: str,
    html_text: str,
    *,
    subsource: str,
    fallback_title: str = "",
    fallback_pub_date: str = "",
    candidate_reason: str = "",
    rule_sha: str | None = None,
) -> MomRecord:
    soup = BeautifulSoup(html_text, "html.parser")
    pub_date = _meta_content(soup, "published_date") or _normalise_listing_date(fallback_pub_date)
    return MomRecord(
        doc_id=stable_id(url),
        source_url=url,
        subsource=subsource,
        title=_title_from_html(soup) or fallback_title,
        body_plain="",
        stated_breaches=[],
        act_references=[],
        subject_organisation=None,
        pub_date=pub_date,
        extraction_rule_sha=rule_sha or extraction_rule_sha(EXTRACTION_MODULE),
        raw_html=html_text,
        fetched_at=dt.datetime.now(dt.UTC).isoformat(),
        candidate_reason=candidate_reason,
        content_type="text/html",
    )


def _record_from_convicted_row(row: dict[str, Any], *, page_url: str, rule_sha: str) -> MomRecord:
    row_id = str(row.get("id") or row.get("ID") or "")
    source_url = f"{CONVICTED_EMPLOYERS_PAGE}#row-{row_id}" if row_id else page_url
    pub_date = str(row.get("dateofsentence") or "")
    return MomRecord(
        doc_id=stable_id(source_url),
        source_url=source_url,
        subsource="advisory",
        title=str(row.get("nameofoffender") or "Employers convicted under the Employment Act"),
        body_plain="",
        stated_breaches=[],
        act_references=[],
        subject_organisation=str(row.get("nameofoffender") or "") or None,
        pub_date=pub_date,
        extraction_rule_sha=rule_sha,
        raw_json=row,
        fetched_at=dt.datetime.now(dt.UTC).isoformat(),
        candidate_reason="convicted-employers-dbapp-row",
        content_type="application/json",
    )


def discover_press_release_items(
    *,
    client: httpx.Client,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    max_listing_pages: int | None = None,
) -> list[ListingItem]:
    seen_urls: set[str] = set()
    out: list[ListingItem] = []
    for category in PRESS_RELEASE_CATEGORIES:
        first_url = press_release_listing_url(category)
        first_html = fetch_text(first_url, client=client, crawl_delay=crawl_delay)
        last_page = extract_last_page(first_html)
        if max_listing_pages is not None:
            last_page = min(last_page, max_listing_pages)
        for item in extract_listing_items(first_html):
            if item.url not in seen_urls and is_enforcement_candidate(item):
                seen_urls.add(item.url)
                out.append(item)
        for page in range(2, last_page + 1):
            listing_html = fetch_text(press_release_listing_url(category, page), client=client, crawl_delay=crawl_delay)
            for item in extract_listing_items(listing_html):
                if item.url in seen_urls or not is_enforcement_candidate(item):
                    continue
                seen_urls.add(item.url)
                out.append(item)
    return out


def _iter_convicted_employer_records(
    *,
    client: httpx.Client,
    crawl_delay: float,
    rule_sha: str,
) -> Iterator[MomRecord]:
    first_url = convicted_employers_api_url(1)
    first_payload = json.loads(fetch_text(first_url, client=client, crawl_delay=crawl_delay))
    response = first_payload.get("response") or {}
    per_page = int(response.get("per_page") or CONVICTED_EMPLOYERS_PER_PAGE)
    total_rows = int(response.get("total_rows") or 0)
    total_pages = max(1, (total_rows + per_page - 1) // per_page)
    for row in response.get("rows") or []:
        if isinstance(row, dict):
            yield _record_from_convicted_row(row, page_url=first_url, rule_sha=rule_sha)
    for page in range(2, total_pages + 1):
        page_url = convicted_employers_api_url(page)
        payload = json.loads(fetch_text(page_url, client=client, crawl_delay=crawl_delay))
        for row in (payload.get("response") or {}).get("rows") or []:
            if isinstance(row, dict):
                yield _record_from_convicted_row(row, page_url=page_url, rule_sha=rule_sha)


def iter_records(
    *,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    max_listing_pages: int | None = None,
) -> Iterator[MomRecord]:
    rule_sha = extraction_rule_sha(EXTRACTION_MODULE)
    with httpx.Client(
        headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/json"},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    ) as client:
        for item in discover_press_release_items(
            client=client,
            crawl_delay=crawl_delay,
            max_listing_pages=max_listing_pages,
        ):
            detail_html = fetch_text(item.url, client=client, crawl_delay=crawl_delay)
            yield _record_from_html(
                item.url,
                detail_html,
                subsource="press_release",
                fallback_title=item.title,
                fallback_pub_date=item.pub_date,
                candidate_reason="press-release-title-match",
                rule_sha=rule_sha,
            )
        for url in GUIDANCE_URLS:
            html_text = fetch_text(url, client=client, crawl_delay=crawl_delay)
            yield _record_from_html(
                url,
                html_text,
                subsource="advisory",
                candidate_reason="fixed-guidance-seed",
                rule_sha=rule_sha,
            )
        faq_html = fetch_text(FAQ_INDEX_URL, client=client, crawl_delay=crawl_delay)
        yield _record_from_html(
            FAQ_INDEX_URL,
            faq_html,
            subsource="faq",
            candidate_reason="faq-index-only",
            rule_sha=rule_sha,
        )
        yield from _iter_convicted_employer_records(
            client=client,
            crawl_delay=crawl_delay,
            rule_sha=rule_sha,
        )


def _existing_doc_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    seen: set[str] = set()
    with path.open(encoding="utf-8") as handle:
        for line in handle:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            doc_id = row.get("doc_id")
            if doc_id:
                seen.add(str(doc_id))
    return seen


def write_jsonl(records: Iterable[MomRecord], output_path: Path, *, append: bool = True) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    mode = "a" if append else "w"
    seen = _existing_doc_ids(output_path) if append else set()
    written = 0
    with output_path.open(mode, encoding="utf-8") as handle:
        for record in records:
            if record.doc_id in seen:
                continue
            seen.add(record.doc_id)
            handle.write(json.dumps(record.as_jsonl_row(), ensure_ascii=False, sort_keys=True) + "\n")
            written += 1
    return written


def run(
    output_path: Path | str = DEFAULT_OUTPUT,
    *,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    force: bool = False,
    dry_run: bool = True,
    max_listing_pages: int | None = None,
) -> int:
    """Fetch MOM network payloads and append JSONL rows. Returns rows written."""
    if dry_run:
        return print_dry_run()
    output_path = Path(output_path)
    written = write_jsonl(
        iter_records(crawl_delay=crawl_delay, max_listing_pages=max_listing_pages),
        output_path,
        append=not force,
    )
    logger.info("MOM wrote %d network rows to %s", written, output_path)
    return written


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Ingest MOM enforcement/guidance network payloads")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--crawl-delay", type=float, default=DEFAULT_CRAWL_DELAY)
    parser.add_argument("--force", action="store_true", help="rebuild from scratch")
    parser.add_argument("--dry-run", action="store_true", help="print planned URLs without HTTP")
    parser.add_argument("--live", action="store_true", help="perform live HTTP fetches")
    parser.add_argument("--max-listing-pages", type=int, default=None, help="limit press-release pages per category")
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    return run(
        args.output,
        crawl_delay=args.crawl_delay,
        force=args.force,
        dry_run=args.dry_run or not args.live,
        max_listing_pages=args.max_listing_pages,
    )


if __name__ == "__main__":
    raise SystemExit(0 if main() >= 0 else 1)
