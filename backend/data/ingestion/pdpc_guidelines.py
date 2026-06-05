"""PDPC Advisory Guidelines PDF ingestion (SGLB-14 source corpus).

Discovers PDPC regulatory-guidance pages, resolves attached Advisory
Guidelines PDFs, extracts text with pypdf, and emits JSONL rows:

  - ``doc_id``
  - ``source_url``
  - ``title``
  - ``pdf_url``
  - ``body_plain``
  - ``section_headings``
  - ``pub_date``

CLI:

    python -m data.ingestion.pdpc_guidelines \\
      --output vendor-data/pdpc/guidelines.jsonl
"""
from __future__ import annotations

import argparse
import datetime as dt
import hashlib
import html
import json
import logging
import re
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Iterator, Sequence
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup

PDPC_BASE = "https://www.pdpc.gov.sg"
DEFAULT_SITEMAP_URL = f"{PDPC_BASE}/sitemap.xml"
DEFAULT_SOURCE_URLS: tuple[str, ...] = (DEFAULT_SITEMAP_URL,)
DEFAULT_OUTPUT = Path("vendor-data/pdpc/guidelines.jsonl")
DEFAULT_PDF_DIR = Path("vendor-data/pdpc/guidelines/pdf")
USER_AGENT = "Mozilla/5.0 (compatible; junas-research/0.1; +https://github.com/gongahkia/junas)"
DEFAULT_TIMEOUT = 60.0
DEFAULT_CRAWL_DELAY = 1.0
MIN_EXTRACTED_TEXT_CHARS = 500

logger = logging.getLogger(__name__)

_DATE_FORMATS = ("%d %b %Y", "%d %B %Y", "%Y-%m-%d")
_RE_WS = re.compile(r"[ \t\xa0]+")
_RE_MULTI_NEWLINE = re.compile(r"\n{3,}")
_RE_PUBLISHED = re.compile(r"\bPublished on\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})")
_RE_LAST_UPDATED = re.compile(r"\bLast updated\s+(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})")
_RE_RSC_H1 = re.compile(r'\["\$","h1",null,\{"children":"([^"]+)"\}\]')
_RE_RSC_PUBLISHED = re.compile(r'"Published on\s*",\s*"(\d{1,2}\s+[A-Za-z]{3,9}\s+\d{4})"')
_RE_CHAPTER_LINE = re.compile(
    r"^(?:chapter|chapters|part|annex)\s+[A-Za-z0-9IVXLCDM]+(?:\s*[-:]\s*|\s+).+",
    re.IGNORECASE,
)
_RE_NUMBERED_HEADING = re.compile(r"^\d{1,2}(?:\.\d{1,2})?\s+[A-Z][A-Za-z0-9,()/&' -]{3,}$")


@dataclass(frozen=True)
class GuidelineCandidate:
    source_url: str
    title: str
    pdf_url: str
    pub_date: dt.date | None
    page_headings: list[str] = field(default_factory=list)


@dataclass
class PdpcGuideline:
    doc_id: str
    source_url: str
    title: str
    pdf_url: str
    body_plain: str
    section_headings: list[str]
    pub_date: dt.date | None

    def as_jsonl_row(self) -> dict[str, object]:
        return {
            "doc_id": self.doc_id,
            "source_url": self.source_url,
            "title": self.title,
            "pdf_url": self.pdf_url,
            "body_plain": self.body_plain,
            "section_headings": self.section_headings,
            "pub_date": self.pub_date.isoformat() if self.pub_date else None,
        }


@dataclass
class IngestStats:
    candidates: int = 0
    written: int = 0
    fully_extracted: int = 0
    low_text_pdfs: list[str] = field(default_factory=list)
    skipped: list[tuple[str, str]] = field(default_factory=list)


def stable_id(pdf_url: str) -> str:
    digest = hashlib.sha256(pdf_url.encode("utf-8")).hexdigest()[:12]
    return f"pdpc_guideline_{digest}"


def parse_pub_date(raw: str | None) -> dt.date | None:
    s = (raw or "").strip()
    if not s:
        return None
    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(s, fmt).date()
        except ValueError:
            continue
    return None


def normalise_text(raw: str) -> str:
    lines = [_RE_WS.sub(" ", line).strip() for line in raw.replace("\r", "\n").split("\n")]
    text = "\n".join(lines)
    return _RE_MULTI_NEWLINE.sub("\n\n", text).strip()


def extract_pdf_text(pdf_path: Path | str) -> str:
    try:
        from pypdf import PdfReader
    except ImportError as exc:  # pragma: no cover
        raise RuntimeError("pypdf is required for PDPC Advisory Guidelines ingestion") from exc

    with Path(pdf_path).open("rb") as fp:
        reader = PdfReader(fp)
        pages: list[str] = []
        for page in reader.pages:
            pages.append(page.extract_text() or "")
    return normalise_text("\n\n".join(pages))


def extract_section_headings(body_plain: str) -> list[str]:
    headings: list[str] = []
    for line in body_plain.splitlines():
        cleaned = _clean_heading(line)
        if cleaned and _looks_like_section_heading(cleaned):
            headings.append(cleaned)
    return _dedupe_keep_order(headings)


def parse_sitemap_urls(sitemap_xml: str) -> list[str]:
    root = ET.fromstring(sitemap_xml)
    urls: list[str] = []
    for loc in root.findall(".//{*}loc"):
        value = (loc.text or "").strip()
        if value:
            urls.append(value)
    return urls


def is_guideline_page_url(url: str) -> bool:
    path = urlparse(url).path.lower().rstrip("/")
    if path in {"/advisory-guidelines", "/sector-specific-guidelines"}:
        return True
    if "/organisations/regulations-decisions/regulatory-guidance/" not in path:
        return False
    return any(
        token in path
        for token in (
            "advisory-guidelines",
            "introduction-to-the-guidelines",
            "application-of-the-nric-advisory-guidelines",
        )
    )


def is_guideline_pdf_url(url: str) -> bool:
    path = urlparse(url).path.lower()
    return path.endswith(".pdf") and (
        "advisory-guidelines" in path
        or "sector-specific-advisory" in path
        or "/pdf-files/advisory-" in path
    )


def parse_guideline_page(page_text: str, source_url: str) -> list[GuidelineCandidate]:
    decoded = _decode_htmlish(page_text)
    soup = BeautifulSoup(decoded, "html.parser")
    title = _page_title(soup, decoded)
    pub_date = _page_pub_date(soup, decoded)
    page_headings = _page_headings(soup)
    candidates: list[GuidelineCandidate] = []
    for link in soup.find_all("a", href=True):
        href = html.unescape(str(link.get("href") or "")).strip()
        anchor = normalise_text(link.get_text(" ", strip=True))
        if not _looks_like_document_href(href, anchor):
            continue
        pdf_url = urljoin(source_url, href)
        candidate_title = title
        if anchor and anchor.lower() not in {"here", "full document is available here"}:
            candidate_title = f"{title} - {anchor}"
        candidates.append(
            GuidelineCandidate(
                source_url=source_url,
                title=candidate_title,
                pdf_url=pdf_url,
                pub_date=pub_date,
                page_headings=page_headings,
            )
        )
    return _dedupe_candidates(candidates)


def collect_candidates(
    source_urls: Sequence[str] = DEFAULT_SOURCE_URLS,
    *,
    client: httpx.Client | None = None,
    limit: int | None = None,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
) -> list[GuidelineCandidate]:
    owned = False
    if client is None:
        client = _client()
        owned = True
    try:
        candidates: list[GuidelineCandidate] = []
        page_urls: list[str] = []
        for source_url in source_urls:
            if _is_sitemap_url(source_url):
                sitemap = fetch_text(source_url, client=client)
                for url in parse_sitemap_urls(sitemap):
                    if is_guideline_page_url(url):
                        page_urls.append(url)
                    elif is_guideline_pdf_url(url):
                        candidates.append(_direct_pdf_candidate(url))
                _sleep(crawl_delay)
                continue
            if _is_pdf_url(source_url):
                candidates.append(_direct_pdf_candidate(source_url))
                continue
            page_urls.append(source_url)

        for page_url in _dedupe_keep_order(page_urls):
            try:
                text = fetch_page_text(page_url, client=client)
            except RuntimeError as exc:
                logger.warning("PDPC skip page %s: %s", page_url, exc)
                continue
            candidates.extend(parse_guideline_page(text, page_url))
            _sleep(crawl_delay)
            if limit is not None and len(candidates) >= limit:
                break
        return _dedupe_candidates(candidates)[:limit]
    finally:
        if owned:
            client.close()


def fetch_text(url: str, *, client: httpx.Client) -> str:
    try:
        response = client.get(url)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"fetch failed: {url}") from exc
    return response.text


def fetch_page_text(url: str, *, client: httpx.Client) -> str:
    headers = {"Accept": "text/x-component", "RSC": "1", "Next-Url": urlparse(url).path}
    try:
        response = client.get(url, headers=headers)
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"fetch failed: {url}") from exc
    return response.text


def fetch_pdf_bytes(url: str, *, client: httpx.Client) -> bytes:
    try:
        response = client.get(url, headers={"Accept": "application/pdf"})
        response.raise_for_status()
    except httpx.HTTPError as exc:
        raise RuntimeError(f"pdf fetch failed: {url}") from exc
    data = response.content
    if not data.startswith(b"%PDF"):
        raise RuntimeError(f"not a PDF response: {url}")
    return data


def download_pdf(
    candidate: GuidelineCandidate,
    pdf_dir: Path,
    *,
    client: httpx.Client,
    force: bool = False,
) -> Path:
    pdf_dir.mkdir(parents=True, exist_ok=True)
    path = pdf_dir / f"{stable_id(candidate.pdf_url)}.pdf"
    if path.exists() and not force:
        return path
    path.write_bytes(fetch_pdf_bytes(candidate.pdf_url, client=client))
    return path


def build_guideline_from_pdf(candidate: GuidelineCandidate, pdf_path: Path | str) -> PdpcGuideline:
    body_plain = extract_pdf_text(pdf_path)
    section_headings = _dedupe_keep_order(candidate.page_headings + extract_section_headings(body_plain))
    return PdpcGuideline(
        doc_id=stable_id(candidate.pdf_url),
        source_url=candidate.source_url,
        title=candidate.title,
        pdf_url=candidate.pdf_url,
        body_plain=body_plain,
        section_headings=section_headings,
        pub_date=candidate.pub_date,
    )


def write_jsonl(rows: Iterable[PdpcGuideline], output_path: Path) -> int:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    count = 0
    with output_path.open("w", encoding="utf-8") as fp:
        for row in rows:
            fp.write(json.dumps(row.as_jsonl_row(), ensure_ascii=False, sort_keys=True) + "\n")
            count += 1
    return count


def load_jsonl(path: Path | str = DEFAULT_OUTPUT) -> Iterator[dict[str, object]]:
    with Path(path).open(encoding="utf-8") as fp:
        for line in fp:
            if line.strip():
                yield json.loads(line)


def ingest(
    *,
    output_path: Path = DEFAULT_OUTPUT,
    pdf_dir: Path = DEFAULT_PDF_DIR,
    source_urls: Sequence[str] = DEFAULT_SOURCE_URLS,
    limit: int | None = None,
    crawl_delay: float = DEFAULT_CRAWL_DELAY,
    min_text_chars: int = MIN_EXTRACTED_TEXT_CHARS,
    force: bool = False,
    client: httpx.Client | None = None,
) -> IngestStats:
    owned = False
    if client is None:
        client = _client()
        owned = True
    try:
        candidates = collect_candidates(
            source_urls,
            client=client,
            limit=limit,
            crawl_delay=crawl_delay,
        )
        rows: list[PdpcGuideline] = []
        stats = IngestStats(candidates=len(candidates))
        for candidate in candidates:
            try:
                pdf_path = download_pdf(candidate, pdf_dir, client=client, force=force)
                row = build_guideline_from_pdf(candidate, pdf_path)
            except RuntimeError as exc:
                stats.skipped.append((candidate.pdf_url, str(exc)))
                continue
            rows.append(row)
            if len(row.body_plain) >= min_text_chars:
                stats.fully_extracted += 1
            else:
                stats.low_text_pdfs.append(row.pdf_url)
            _sleep(crawl_delay)
        stats.written = write_jsonl(rows, output_path)
        return stats
    finally:
        if owned:
            client.close()


def _client() -> httpx.Client:
    return httpx.Client(
        headers={"User-Agent": USER_AGENT},
        timeout=DEFAULT_TIMEOUT,
        follow_redirects=True,
    )


def _sleep(delay: float) -> None:
    if delay > 0:
        time.sleep(delay)


def _is_sitemap_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".xml")


def _is_pdf_url(url: str) -> bool:
    return urlparse(url).path.lower().endswith(".pdf")


def _direct_pdf_candidate(url: str) -> GuidelineCandidate:
    title = _title_from_url(url)
    return GuidelineCandidate(source_url=url, title=title, pdf_url=url, pub_date=None)


def _title_from_url(url: str) -> str:
    stem = Path(urlparse(url).path).stem
    cleaned = re.sub(r"[-_]+", " ", stem).strip()
    return cleaned.title() if cleaned else "PDPC Advisory Guidelines"


def _decode_htmlish(value: str) -> str:
    decoded = value
    replacements = {
        "\\u003c": "<",
        "\\u003C": "<",
        "\\u003e": ">",
        "\\u003E": ">",
        "\\u0026": "&",
        "\\n": "\n",
        '\\"': '"',
    }
    for old, new in replacements.items():
        decoded = decoded.replace(old, new)
    return html.unescape(decoded)


def _page_title(soup: BeautifulSoup, raw_text: str) -> str:
    h1 = soup.find("h1")
    if h1:
        title = normalise_text(h1.get_text(" ", strip=True))
        if title:
            return title
    match = _RE_RSC_H1.search(raw_text)
    if match:
        return normalise_text(match.group(1))
    meta = soup.find("meta", attrs={"property": "og:title"})
    if meta and meta.get("content"):
        return normalise_text(str(meta["content"]))
    if soup.title and soup.title.string:
        return normalise_text(soup.title.string).removeprefix("PDPC | ").strip()
    return "PDPC Advisory Guidelines"


def _page_pub_date(soup: BeautifulSoup, raw_text: str) -> dt.date | None:
    text = normalise_text(soup.get_text(" ", strip=True))
    for pattern in (_RE_PUBLISHED, _RE_LAST_UPDATED):
        match = pattern.search(text)
        if match:
            parsed = parse_pub_date(match.group(1))
            if parsed:
                return parsed
    match = _RE_RSC_PUBLISHED.search(raw_text)
    if match:
        return parse_pub_date(match.group(1))
    return None


def _page_headings(soup: BeautifulSoup) -> list[str]:
    headings: list[str] = []
    for tag in soup.find_all(["h2", "h3", "h4"]):
        cleaned = _clean_heading(tag.get_text(" ", strip=True))
        if cleaned and _looks_like_section_heading(cleaned):
            headings.append(cleaned)
        if cleaned and cleaned.lower() == "chapters listing":
            for sibling in tag.find_next_siblings():
                if sibling.name and sibling.name.startswith("h"):
                    break
                for item in sibling.find_all("li"):
                    item_text = _clean_heading(item.get_text(" ", strip=True))
                    if item_text:
                        headings.append(item_text)
                if sibling.name == "ul":
                    break
    return _dedupe_keep_order(headings)


def _looks_like_document_href(href: str, anchor_text: str) -> bool:
    if not href or href.startswith(("#", "mailto:", "tel:")):
        return False
    lower_href = href.lower()
    lower_anchor = anchor_text.lower()
    if lower_href.endswith(".pdf") or ".pdf?" in lower_href:
        return True
    if "/assets/" not in lower_href:
        return False
    return any(
        token in lower_anchor
        for token in ("full document", "document", "guideline", "guide", "annex", "pdf", "here")
    )


def _clean_heading(value: str) -> str:
    cleaned = normalise_text(value)
    cleaned = re.sub(r"\.{4,}\s*\d+$", "", cleaned).strip()
    cleaned = re.sub(r"\s{2,}", " ", cleaned)
    return cleaned.strip(" .")


def _looks_like_section_heading(value: str) -> bool:
    if not value or len(value) < 4 or len(value) > 160:
        return False
    lower = value.lower()
    if lower in {"share", "back to top", "personal data protection commission"}:
        return False
    if re.fullmatch(r"\d+", value):
        return False
    if _RE_CHAPTER_LINE.match(value):
        return True
    if _RE_NUMBERED_HEADING.match(value) and len(value.split()) <= 14:
        return True
    words = value.split()
    if value.isupper() and 2 <= len(words) <= 14 and "PDPC" not in value:
        return True
    return False


def _dedupe_keep_order(items: Iterable[str]) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for item in items:
        key = item.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(item)
    return out


def _dedupe_candidates(candidates: Iterable[GuidelineCandidate]) -> list[GuidelineCandidate]:
    out: list[GuidelineCandidate] = []
    seen: set[str] = set()
    for candidate in candidates:
        key = candidate.pdf_url
        if key in seen:
            continue
        seen.add(key)
        out.append(candidate)
    return out


def _default_repo_root() -> Path:
    return Path(__file__).resolve().parents[3]


def main(argv: list[str] | None = None) -> int:
    root = _default_repo_root()
    parser = argparse.ArgumentParser(
        prog="data.ingestion.pdpc_guidelines",
        description="Ingest PDPC Advisory Guidelines PDFs for SGLB-14",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=root / DEFAULT_OUTPUT,
        help="output JSONL path",
    )
    parser.add_argument(
        "--pdf-dir",
        type=Path,
        default=root / DEFAULT_PDF_DIR,
        help="PDF cache directory",
    )
    parser.add_argument(
        "--source-url",
        action="append",
        help="sitemap, page, or PDF URL to ingest; repeatable",
    )
    parser.add_argument("--limit", type=int, help="maximum PDF candidates to process")
    parser.add_argument("--crawl-delay", type=float, default=DEFAULT_CRAWL_DELAY)
    parser.add_argument("--min-text-chars", type=int, default=MIN_EXTRACTED_TEXT_CHARS)
    parser.add_argument("--force", action="store_true", help="redownload cached PDFs")
    args = parser.parse_args(argv)

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    source_urls = tuple(args.source_url or DEFAULT_SOURCE_URLS)
    stats = ingest(
        output_path=args.output,
        pdf_dir=args.pdf_dir,
        source_urls=source_urls,
        limit=args.limit,
        crawl_delay=args.crawl_delay,
        min_text_chars=args.min_text_chars,
        force=args.force,
    )
    payload = {
        "candidates": stats.candidates,
        "written": stats.written,
        "fully_extracted": stats.fully_extracted,
        "low_text_pdfs": stats.low_text_pdfs,
        "skipped": stats.skipped,
        "output": str(args.output),
        "pdf_dir": str(args.pdf_dir),
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if stats.low_text_pdfs:
        print(
            f"note: {len(stats.low_text_pdfs)} PDFs had little/no extractable text; "
            "these may be scanned images",
            file=sys.stderr,
        )
    return 0 if stats.written else 1


if __name__ == "__main__":
    raise SystemExit(main())
