"""MOM HTML parser for SGLB-05 records."""
from __future__ import annotations

import datetime as dt
import hashlib
import re
import unicodedata
from dataclasses import dataclass, field
from html import unescape
from typing import Iterable

try:
    from bs4 import BeautifulSoup, Tag
except ModuleNotFoundError as exc:  # pragma: no cover - optional at parse-time
    raise RuntimeError("beautifulsoup4 is not installed") from exc

WHITESPACE_RE = re.compile(r"\s+")
PUNCT_SPACE_RE = re.compile(r"\s+([,.;:!?%)\]])")
OPEN_SPACE_RE = re.compile(r"([(\[])\s+")
SUBSOURCE_VALUES = {"press_release", "faq", "advisory"}
CONTENT_SELECTORS = (
    "#pagecontent_0_documentcontent_0_DivCode",
    "#maincontent_0_documentcontent_0_DivCode",
    ".page-content",
    ".mom-page-content",
    "article",
    "#MainContent",
    "main",
    "body",
)
DROP_SELECTORS = (
    "script",
    "style",
    "noscript",
    "iframe",
    "form",
    "nav",
    "header",
    "footer",
    "select",
    "input",
    "button",
    "h1",
    ".article-meta",
    ".module-share",
    ".share-widget",
    ".mom-last-updated",
    ".mom-last-updated-footer",
    ".breadcrumbs-mobile",
    ".ui-breadcrumbs",
)
BLOCK_TAGS = {"p", "li", "h2", "h3", "h4", "h5", "h6", "table"}
BREACH_HEADER_MARKERS = {
    "breach",
    "breaches",
    "breach type",
    "type of breach",
    "breach category",
    "category of breach",
    "stated breach",
    "stated breaches",
    "offence type",
    "offense type",
    "contravention type",
}
BREACH_ATTR_RE = re.compile(r"\b(?:breach|contravention|offence|offense)[-_ ]?(?:tag|type|category|label)s?\b", re.I)
KNOWN_ACT_NAMES = (
    "Employment of Foreign Manpower Act",
    "Retirement and Re-employment Act",
    "Child Development Co-Savings Act",
    "Foreign Employee Dormitories Act",
    "Workplace Safety and Health Act",
    "Work Injury Compensation Act",
    "Central Provident Fund Act",
    "Employment Agencies Act",
    "Employment Claims Act",
    "Employment Act",
)
KNOWN_ACT_PATTERN = (
    r"(?:"
    + "|".join(re.escape(name) for name in KNOWN_ACT_NAMES)
    + r")(?:\s+\d{4})?"
)
SECTION_TOKEN_RE = re.compile(r"\bs(?:ection)?s?\.?\s*([0-9]+[A-Z]?(?:\([0-9A-Za-z]+\))*)", re.I)
SECTION_CHAIN_RE = re.compile(
    r"\b(?P<sections>s(?:ection)?s?\.?\s*[0-9]+[A-Z]?(?:\([0-9A-Za-z]+\))*"
    r"(?:\s*r/w\s*s(?:ection)?s?\.?\s*[0-9]+[A-Z]?(?:\([0-9A-Za-z]+\))*)*)"
    rf"\s+of\s+(?:the\s+)?(?P<act>{KNOWN_ACT_PATTERN}|[A-Z]{{2,}})",
    re.I,
)
ACT_NAME_RE = re.compile(rf"\b({KNOWN_ACT_PATTERN})\b", re.I)
ACRONYM_DEF_RE = re.compile(
    rf"\b(?P<name>{KNOWN_ACT_PATTERN})\s*"
    r"\(\s*[\"']?(?P<abbr>[A-Z]{2,})[\"']?\s*\)",
    re.I,
)
ORG_RE = re.compile(
    r"\b([A-Z][A-Za-z0-9&'.,()/-]*(?:\s+[A-Z][A-Za-z0-9&'.,()/-]*){0,8}\s+"
    r"(?:Pte\.?\s+Ltd\.?|Private\s+Limited|Ltd\.?|Limited|LLP|LLC))\b"
)
MONTHS = {
    "january": 1,
    "february": 2,
    "march": 3,
    "april": 4,
    "may": 5,
    "june": 6,
    "july": 7,
    "august": 8,
    "september": 9,
    "october": 10,
    "november": 11,
    "december": 12,
    "jan": 1,
    "feb": 2,
    "mar": 3,
    "apr": 4,
    "jun": 6,
    "jul": 7,
    "aug": 8,
    "sep": 9,
    "sept": 9,
    "oct": 10,
    "nov": 11,
    "dec": 12,
}


@dataclass(slots=True)
class MomRecord:
    doc_id: str
    source_url: str
    subsource: str
    title: str
    body_plain: str
    stated_breaches: list[str] = field(default_factory=list)
    act_references: list[str] = field(default_factory=list)
    subject_organisation: str | None = None
    pub_date: str = ""


def stable_id(source_url: str) -> str:
    digest = hashlib.sha256(source_url.encode("utf-8")).hexdigest()[:12]
    return f"mom_{digest}"


def normalise_text(value: str) -> str:
    text = unescape(value or "")
    text = unicodedata.normalize("NFKC", text)
    text = text.replace("\u00ad", "").replace("\u200b", "").replace("\ufeff", "")
    text = WHITESPACE_RE.sub(" ", text).strip()
    text = PUNCT_SPACE_RE.sub(r"\1", text)
    text = OPEN_SPACE_RE.sub(r"\1", text)
    return text


def parse_mom_html(
    html: str,
    source_url: str,
    *,
    subsource: str | None = None,
    fallback_title: str = "",
    fallback_pub_date: str = "",
) -> MomRecord:
    soup = BeautifulSoup(html, "lxml")
    resolved_subsource = subsource or _detect_subsource(source_url)
    if resolved_subsource not in SUBSOURCE_VALUES:
        raise ValueError(f"unknown MOM subsource: {resolved_subsource}")
    title = _title_from_html(soup) or normalise_text(fallback_title)
    body_plain = _body_plain(soup)
    pub_date = _pub_date(soup, fallback_pub_date)
    return MomRecord(
        doc_id=stable_id(source_url),
        source_url=source_url,
        subsource=resolved_subsource,
        title=title,
        body_plain=body_plain,
        stated_breaches=_extract_stated_breaches(soup),
        act_references=_extract_act_references(" ".join(part for part in (title, body_plain) if part)),
        subject_organisation=_extract_subject_organisation(" ".join(part for part in (title, body_plain) if part)),
        pub_date=pub_date,
    )


def parse_press_release_html(
    html: str,
    source_url: str,
    *,
    fallback_title: str = "",
    fallback_pub_date: str = "",
) -> MomRecord:
    return parse_mom_html(
        html,
        source_url,
        subsource="press_release",
        fallback_title=fallback_title,
        fallback_pub_date=fallback_pub_date,
    )


def _detect_subsource(source_url: str) -> str:
    lowered = (source_url or "").lower()
    if "/newsroom/press-releases" in lowered:
        return "press_release"
    if "/faq" in lowered:
        return "faq"
    return "advisory"


def _meta_content(soup: BeautifulSoup, name: str) -> str:
    tag = soup.find("meta", attrs={"name": name})
    if tag and tag.get("content"):
        return normalise_text(str(tag["content"]))
    tag = soup.find("meta", attrs={"property": f"og:{name}"})
    if tag and tag.get("content"):
        return normalise_text(str(tag["content"]))
    return ""


def _title_from_html(soup: BeautifulSoup) -> str:
    h1 = soup.find("h1")
    if h1:
        title = _tag_text(h1)
        if title:
            return title
    meta_title = _meta_content(soup, "title")
    if meta_title:
        return meta_title
    title = soup.find("title")
    if title:
        return _tag_text(title)
    return ""


def _pub_date(soup: BeautifulSoup, fallback_pub_date: str) -> str:
    for raw in (
        _meta_content(soup, "published_date"),
        _meta_content(soup, "date"),
        _meta_content(soup, "article:published_time"),
        _first_time_value(soup),
        fallback_pub_date,
    ):
        parsed = _iso_date(raw)
        if parsed:
            return parsed
    return ""


def _first_time_value(soup: BeautifulSoup) -> str:
    tag = soup.find("time")
    if not tag:
        return ""
    return str(tag.get("datetime") or tag.get_text(" ", strip=True) or "")


def _iso_date(value: str) -> str:
    raw = normalise_text(value)
    if not raw:
        return ""
    raw = raw.split("T", 1)[0]
    for fmt in ("%Y-%m-%d", "%Y-%m"):
        try:
            return dt.datetime.strptime(raw, fmt).date().isoformat()
        except ValueError:
            pass
    m = re.match(r"^(\d{1,4})[-/](\d{1,2})[-/](\d{1,4})$", raw)
    if m:
        a, b, c = (int(part) for part in m.groups())
        year, month, day = (a, b, c) if a > 31 else (c, b, a)
        try:
            return dt.date(year, month, day).isoformat()
        except ValueError:
            return ""
    m = re.match(r"^(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})$", raw)
    if m:
        day, month_name, year = m.groups()
        month = MONTHS.get(month_name.lower())
        if month:
            try:
                return dt.date(int(year), month, int(day)).isoformat()
            except ValueError:
                return ""
    return ""


def _content_root(soup: BeautifulSoup | Tag) -> Tag:
    for selector in CONTENT_SELECTORS:
        tag = soup.select_one(selector)
        if tag is not None and _tag_text(tag):
            return tag
    body = soup.find("body") if isinstance(soup, BeautifulSoup) else None
    return body or soup  # type: ignore[return-value]


def _body_plain(soup: BeautifulSoup) -> str:
    root = BeautifulSoup(str(_content_root(soup)), "lxml")
    content = _content_root(root)
    for tag in content.select(",".join(DROP_SELECTORS)):
        tag.decompose()
    for br in content.find_all("br"):
        br.replace_with(" ")
    blocks: list[str] = []
    for tag in content.find_all(BLOCK_TAGS):
        if _has_block_parent(tag, content):
            continue
        text = _table_text(tag) if tag.name == "table" else _tag_text(tag)
        if _is_body_noise(text):
            continue
        blocks.append(text)
    if not blocks:
        text = _tag_text(content)
        return "" if _is_body_noise(text) else text
    return normalise_text(" ".join(blocks))


def _has_block_parent(tag: Tag, root: Tag) -> bool:
    parent = tag.parent
    while isinstance(parent, Tag) and parent is not root:
        if parent.name in BLOCK_TAGS:
            return True
        parent = parent.parent
    return False


def _is_body_noise(text: str) -> bool:
    lowered = text.lower()
    return not text or lowered in {"## end of release ##", "end of release", "annex"}


def _tag_text(tag: Tag) -> str:
    return normalise_text(tag.get_text("", strip=False))


def _table_text(table: Tag) -> str:
    rows: list[str] = []
    for tr in table.find_all("tr"):
        cells = [_tag_text(cell) for cell in tr.find_all(["th", "td"], recursive=False)]
        cells = [cell for cell in cells if cell]
        if cells:
            rows.append(" | ".join(cells))
    return normalise_text(" ".join(rows))


def _extract_stated_breaches(soup: BeautifulSoup) -> list[str]:
    root = _content_root(soup)
    breaches: list[str] = []
    _extend_unique(breaches, _breaches_from_tables(root))
    _extend_unique(breaches, _breaches_from_marker_elements(root))
    return breaches


def _breaches_from_tables(root: Tag) -> list[str]:
    breaches: list[str] = []
    for table in root.find_all("table"):
        rows = table.find_all("tr")
        if not rows:
            continue
        header_cells = rows[0].find_all(["th", "td"], recursive=False)
        headers = [_header_key(_tag_text(cell)) for cell in header_cells]
        indexes = [idx for idx, header in enumerate(headers) if header in BREACH_HEADER_MARKERS]
        if not indexes:
            continue
        for tr in rows[1:]:
            cells = tr.find_all(["th", "td"], recursive=False)
            for idx in indexes:
                if idx >= len(cells):
                    continue
                text = _tag_text(cells[idx])
                if text and _header_key(text) not in BREACH_HEADER_MARKERS:
                    _append_unique(breaches, text)
    return breaches


def _breaches_from_marker_elements(root: Tag) -> list[str]:
    breaches: list[str] = []
    for tag in root.find_all(True):
        if _inside_article_meta(tag):
            continue
        marker = " ".join(
            str(value)
            for value in (
                tag.get("class", []),
                tag.get("id", ""),
                tag.get("data-category", ""),
                tag.get("data-tag", ""),
                tag.get("aria-label", ""),
            )
        )
        if not BREACH_ATTR_RE.search(marker):
            continue
        if tag.find("table"):
            continue
        for child in _marker_text_nodes(tag):
            _append_unique(breaches, child)
    return breaches


def _inside_article_meta(tag: Tag) -> bool:
    return tag.find_parent(class_="article-meta") is not None


def _marker_text_nodes(tag: Tag) -> Iterable[str]:
    child_tags = [child for child in tag.find_all(["a", "span", "li"], recursive=False)]
    if not child_tags:
        text = _tag_text(tag)
        return [text] if text else []
    return [_tag_text(child) for child in child_tags if _tag_text(child)]


def _header_key(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", " ", value.lower()).strip()


def _extract_act_references(text: str) -> list[str]:
    refs: list[str] = []
    acronyms = _acronym_map(text)
    for match in SECTION_CHAIN_RE.finditer(text):
        act = _normalise_act_name(match.group("act"), acronyms)
        for section in SECTION_TOKEN_RE.findall(match.group("sections")):
            _append_unique(refs, f"s {section} of the {act}")
    for act in ACT_NAME_RE.findall(text):
        _append_unique(refs, _normalise_act_name(act, acronyms))
    return refs


def _acronym_map(text: str) -> dict[str, str]:
    return {match.group("abbr"): normalise_text(match.group("name")) for match in ACRONYM_DEF_RE.finditer(text)}


def _normalise_act_name(raw: str, acronyms: dict[str, str]) -> str:
    value = normalise_text(raw)
    return acronyms.get(value, value)


def _extract_subject_organisation(text: str) -> str | None:
    match = ORG_RE.search(text)
    if not match:
        return None
    return normalise_text(match.group(1))


def _extend_unique(target: list[str], values: Iterable[str]) -> None:
    for value in values:
        _append_unique(target, value)


def _append_unique(target: list[str], value: str) -> None:
    norm = normalise_text(value)
    if norm and norm not in target:
        target.append(norm)
