"""SSO (Singapore Statutes Online) HTML parser.

Parses the ``WholeDoc=1`` HTML page for an Act or Subsidiary Legislation
into a structured ``act -> part -> division -> section`` tree.

Implementation note: SSO's HTML is server-rendered tables. The salient
markers we rely on are stable across the corpus:

- ``td.actHd``            act title
- ``td.revdHdr`` / ``td.revdTxt`` revised-edition string and effective text
- ``td.part`` / ``td.partHdr`` / ``div.partNo``  part wrapper / header
- ``div.div`` / ``td.divHdr`` / ``td.subDivHdr`` division / subdivision
- ``td.order`` / ``td.orderHdr``  ROC-style order container (used as part)
- ``div.prov1`` ``td.prov1Hdr`` ``td.prov1Txt``  per-section block
- ``div.amendNote``         per-section amendment trailer
- ``data-date``             revision dates surfaced in timeline markers

We extract the section ``number`` from the leading ``<strong>N.</strong>``
in ``prov1Txt`` (falling back to the ``pr<N>-`` element id).
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from html import unescape
from typing import Iterator

try:  # bs4 listed in pyproject; guard for import-time fallback
    from bs4 import BeautifulSoup, Tag
except ModuleNotFoundError as exc:  # pragma: no cover - optional at parse-time
    raise RuntimeError("beautifulsoup4 is not installed") from exc

HTML_TAG_RE = re.compile(r"<[^>]+>")
WHITESPACE_RE = re.compile(r"\s+")
SECTION_NUM_RE = re.compile(r"^\s*<strong>\s*([0-9A-Z]+[A-Z]*)\s*\.?\s*</strong>", re.IGNORECASE)
SECTION_NUM_ID_RE = re.compile(r"^pr([0-9A-Z]+[A-Z]*)-")
AMENDMENT_RE = re.compile(r"\[([0-9]+/[0-9]{2,4}(?:;\s*[0-9]+/[0-9]{2,4})*)\]")
CROSS_REF_RE = re.compile(r"\bsection[s]?\s+([0-9]+[A-Z]*(?:\([0-9A-Za-z]+\))?)", re.IGNORECASE)


@dataclass(slots=True)
class SsoSection:
    """One section-level record. Mirrors the JSONL row written to disk."""

    number: str  # canonical section number, e.g. "13" or "26A"
    name: str  # section heading text
    chapter_number: str  # act short code, e.g. "PDPA2012"
    act_title: str
    part: str  # part heading text (may be empty)
    division: str  # division/subdivision heading (may be empty)
    edition: int  # revised edition year, 0 if unknown
    kind: str  # "act" | "sl"
    text_html: str  # section body HTML
    text_plain: str
    amendment_history: str
    cross_references: list[str] = field(default_factory=list)
    source_url: str = ""
    version_id: str = ""  # stable id, e.g. "PDPA2012@2020"
    valid_start_date: str = ""  # ISO date when this revision came into force


@dataclass(slots=True)
class SsoAct:
    """Container yielded once per act/SL."""

    chapter_number: str
    act_title: str
    kind: str
    edition: int
    revised_edition_text: str
    valid_start_date: str
    source_url: str
    version_id: str
    sections: list[SsoSection] = field(default_factory=list)


def strip_html(value: str) -> str:
    if not value:
        return ""
    text = HTML_TAG_RE.sub(" ", value)
    text = unescape(text)
    return WHITESPACE_RE.sub(" ", text).strip()


def _section_number_from(prov1_txt_html: str, hdr_id: str) -> str:
    match = SECTION_NUM_RE.search(prov1_txt_html or "")
    if match:
        return match.group(1)
    if hdr_id:
        m = SECTION_NUM_ID_RE.match(hdr_id)
        if m:
            return m.group(1)
    return ""


def _heading_text(tag: Tag | None) -> str:
    if tag is None:
        return ""
    return strip_html(tag.decode_contents() if hasattr(tag, "decode_contents") else str(tag))


def _extract_amendments(text_plain: str) -> str:
    matches = AMENDMENT_RE.findall(text_plain or "")
    return "; ".join(sorted(set(matches)))


def _extract_cross_refs(text_plain: str, self_number: str) -> list[str]:
    raw = CROSS_REF_RE.findall(text_plain or "")
    refs: list[str] = []
    seen: set[str] = set()
    for ref in raw:
        norm = ref.split("(")[0]
        if norm == self_number or norm in seen:
            continue
        seen.add(norm)
        refs.append(norm)
    refs.sort()
    return refs


def _detect_kind(soup: BeautifulSoup, source_url: str) -> str:
    if "/SL" in source_url or "/SL-Supp" in source_url:
        return "sl"
    if soup.find("td", class_="orderHdr") or soup.find("td", class_="order"):
        return "sl"  # ROC-style subsidiary legislation
    return "act"


def _detect_edition(revd_hdr_text: str) -> int:
    match = re.search(r"(\d{4})\s+REVISED EDITION", revd_hdr_text or "", re.IGNORECASE)
    if match:
        return int(match.group(1))
    return 0


def _detect_valid_start_date(soup: BeautifulSoup, revd_txt: str) -> str:
    # try the revised-edition effect text first: "comes into operation on 31 December 2021"
    match = re.search(
        r"comes into operation on\s+(\d{1,2}\s+\w+\s+\d{4})", revd_txt or "", re.IGNORECASE
    )
    if match:
        return _iso_date(match.group(1))
    # fall back to the most recent timeline data-date
    dates: list[str] = [str(tag.get("data-date", "") or "") for tag in soup.find_all(attrs={"data-date": True})]
    parsed = [_iso_date(d) for d in dates if d]
    parsed = [d for d in parsed if d]
    if parsed:
        return max(parsed)
    return ""


_MONTHS = {
    "january": 1, "february": 2, "march": 3, "april": 4, "may": 5, "june": 6,
    "july": 7, "august": 8, "september": 9, "october": 10, "november": 11, "december": 12,
    "jan": 1, "feb": 2, "mar": 3, "apr": 4, "jun": 6, "jul": 7, "aug": 8,
    "sep": 9, "sept": 9, "oct": 10, "nov": 11, "dec": 12,
}


def _iso_date(value: str) -> str:
    m = re.match(r"(\d{1,2})\s+([A-Za-z]+)\s+(\d{4})", (value or "").strip())
    if not m:
        return ""
    day, month_name, year = m.groups()
    month = _MONTHS.get(month_name.lower())
    if not month:
        return ""
    return f"{int(year):04d}-{month:02d}-{int(day):02d}"


def parse_toc(html: str) -> tuple[dict[str, str], dict[str, str], list[str]]:
    """Parse the SSO print-filter / TOC sidebar to extract:

    - ``section_to_part``: map of ``"prN-"`` → ``"Part N TITLE"``;
    - ``section_to_division``: map of ``"prN-"`` → division/order label;
    - ``ordered_prov_ids``: the list of ``"prN-"`` ids in document order.

    The TOC is rendered server-side inside ``div#contents.filter`` and
    survives across ``WholeDoc=1`` requests even when ``legisContent`` is
    later populated lazily.
    """
    soup = BeautifulSoup(html, "lxml")
    contents = soup.find("div", id="contents")
    if contents is None:
        return {}, {}, []
    section_to_part: dict[str, str] = {}
    section_to_division: dict[str, str] = {}
    ordered: list[str] = []
    current_part = ""
    current_division = ""
    # iterate over relevant TOC elements in document order
    for elem in contents.find_all(["p", "div", "blockquote"]):
        classes: list[str] = list(elem.get("class") or [])
        # part-level label: <p class="HeadingParagraph filter"> ... <b>Part N TITLE</b>
        if elem.name == "p" and "HeadingParagraph" in classes and "filter" in classes:
            bold = elem.find("b")
            if bold:
                label = strip_html(str(bold))
                if label.lower().startswith(("part ", "order ", "schedule ", "rule ")):
                    current_part = label
                    current_division = ""
                elif label.lower().startswith(("division ", "subdivision ", "chapter ")):
                    current_division = label
            continue
        # section input: <input ... value="prN-" ... /> <label>N TitleText</label>
        if elem.name == "div":
            input_tag = elem.find("input", attrs={"name": "item"})
            if input_tag is None:
                continue
            value = str(input_tag.get("value", "") or "")
            if not value.startswith("pr"):
                continue
            if value in section_to_part:
                continue
            section_to_part[value] = current_part
            section_to_division[value] = current_division
            ordered.append(value)
    return section_to_part, section_to_division, ordered


def parse_sso_html(
    html: str,
    chapter_number: str,
    source_url: str,
    *,
    toc_html: str | None = None,
    fallback_title: str = "",
) -> SsoAct:
    """Parse one SSO ``WholeDoc=1`` page into an ``SsoAct`` tree.

    If the response was obtained via ``?ProvIds=...`` (no act header
    chrome), pass ``toc_html`` from the original ``WholeDoc=1`` page so
    we can recover act title / part labels / valid_start_date.
    """
    soup = BeautifulSoup(html, "lxml")
    toc_soup = BeautifulSoup(toc_html, "lxml") if toc_html else soup

    act_title = strip_html(str(toc_soup.find("td", class_="actHd") or "")).replace("\xa0", " ").strip()
    if not act_title:
        # ProvIds page exposes the title in the desktop-toolbar legis-title span
        title_tag = toc_soup.find("div", class_="legis-title")
        if title_tag is not None:
            inner = title_tag.find("span")
            if inner is not None:
                act_title = strip_html(str(inner))
    if not act_title and fallback_title:
        act_title = fallback_title
    revd_hdr = strip_html(str(toc_soup.find("td", class_="revdHdr") or ""))
    revd_txt = strip_html(str(toc_soup.find("td", class_="revdTxt") or ""))
    edition = _detect_edition(revd_hdr)
    kind = _detect_kind(toc_soup, source_url)
    valid_start = _detect_valid_start_date(toc_soup, revd_txt)
    version_id = f"{chapter_number}@{edition}" if edition else f"{chapter_number}@{valid_start or 'current'}"

    # build section→part/division map from the TOC if available
    section_to_part: dict[str, str] = {}
    section_to_division: dict[str, str] = {}
    if toc_html is not None:
        section_to_part, section_to_division, _ = parse_toc(toc_html)
    else:
        section_to_part, section_to_division, _ = parse_toc(html)

    act = SsoAct(
        chapter_number=chapter_number,
        act_title=act_title,
        kind=kind,
        edition=edition,
        revised_edition_text=revd_hdr,
        valid_start_date=valid_start,
        source_url=source_url,
        version_id=version_id,
    )

    # walk body in document order, tracking current part / division as we go
    body = soup.find("div", class_="body") or soup
    current_part = ""
    current_division = ""

    for node in body.find_all(["td", "div"]):
        classes: list[str] = list(node.get("class") or [])
        # part / order headers reset division
        if "partHdr" in classes:
            current_part = strip_html(str(node))
            current_division = ""
            continue
        if "orderHdr" in classes:
            current_part = strip_html(str(node))
            current_division = ""
            continue
        if "divHdr" in classes or "subDivHdr" in classes or "crossHdr" in classes:
            current_division = strip_html(str(node))
            continue
        if ("prov1Rep" in classes) and node.name == "div":
            # repealed section: <div class="prov1Rep" id="prN-"><td class="prov1RepText">N. [Repealed by ...]</td></div>
            rep_id = str(node.get("id", "") or "")
            rep_txt = node.find("td", class_="prov1RepText")
            if rep_txt is None:
                continue
            text_html = str(rep_txt)
            text_plain = strip_html(text_html)
            section_number = _section_number_from(text_html, rep_id)
            if not section_number:
                continue
            prov_key = f"pr{section_number}-"
            section = SsoSection(
                number=section_number,
                name="[Repealed]",
                chapter_number=chapter_number,
                act_title=act_title,
                part=current_part or section_to_part.get(prov_key, ""),
                division=current_division or section_to_division.get(prov_key, ""),
                edition=edition,
                kind=kind,
                text_html=text_html,
                text_plain=text_plain,
                amendment_history=_extract_amendments(text_plain),
                cross_references=[],
                source_url=f"{source_url}#pr{section_number}-",
                version_id=version_id,
                valid_start_date=valid_start,
            )
            act.sections.append(section)
            continue
        if "prov1" in classes and node.name == "div":
            hdr = node.find("td", class_="prov1Hdr")
            txt = node.find("td", class_="prov1Txt")
            if hdr is None or txt is None:
                continue
            hdr_id = str(hdr.get("id", "") or "")
            name = _heading_text(hdr)
            # the hdr text often contains an empty noBold span + real heading span
            spans = hdr.find_all("span")
            if spans:
                name = strip_html(" ".join(str(s) for s in spans))
            text_html = str(txt)
            text_plain = strip_html(text_html)
            section_number = _section_number_from(text_html, hdr_id)
            if not section_number:
                continue
            prov_key = f"pr{section_number}-"
            effective_part = current_part or section_to_part.get(prov_key, "")
            effective_division = current_division or section_to_division.get(prov_key, "")
            section = SsoSection(
                number=section_number,
                name=name,
                chapter_number=chapter_number,
                act_title=act_title,
                part=effective_part,
                division=effective_division,
                edition=edition,
                kind=kind,
                text_html=text_html,
                text_plain=text_plain,
                amendment_history=_extract_amendments(text_plain),
                cross_references=_extract_cross_refs(text_plain, section_number),
                source_url=f"{source_url}#pr{section_number}-",
                version_id=version_id,
                valid_start_date=valid_start,
            )
            act.sections.append(section)

    return act


def iter_sections(act: SsoAct) -> Iterator[SsoSection]:
    yield from act.sections
