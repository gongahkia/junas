"""CommonLII Singapore judgment HTML parser.

Parses a CommonLII SG judgment page into the structured fields needed by
the SGLB-07 jurisdiction-routing pipeline. CommonLII pages are simple
server-rendered HTML; the stable marker is bracketed judgment paragraph
numbering such as ``[1]`` and ``[2]`` in the visible body text.
"""
from __future__ import annotations

import re
import unicodedata
from collections.abc import Mapping
from dataclasses import dataclass, field
from html import unescape

try:
    from bs4 import BeautifulSoup, Tag
except ModuleNotFoundError as exc:  # pragma: no cover - optional at parse-time
    raise RuntimeError("beautifulsoup4 is not installed") from exc

WHITESPACE_RE = re.compile(r"\s+")
PARAGRAPH_MARKER_RE = re.compile(r"(?:^|\n)\s*\[(?P<number>\d{1,3})\]\s*", re.MULTILINE)
PARAGRAPH_LINE_RE = re.compile(r"^\[(\d{1,3})\]\s+")
JUDGE_LABEL_RE = re.compile(
    r"^(?:coram|before|judge(?:\(s\))?|judges?|bench)\s*:?\s*(?P<names>.+)$",
    re.IGNORECASE,
)
DELIVERED_BY_RE = re.compile(r"\bdelivered by\s+(?P<names>[^):]+)", re.IGNORECASE)
JUDGE_TITLE_RE = re.compile(r"\b(?:CJ|JCA|JA|JAD|JC|J|AR|DJ)\b")
COUNSEL_RE = re.compile(
    r"^(?:for (?:the )?[^:]{2,80}|counsel for [^:]{2,80}|solicitors? for [^:]{2,80}):\s+\S",
    re.IGNORECASE,
)
CHROME_MARKERS = (
    "copyright policy",
    "disclaimers",
    "privacy policy",
    "feedback",
)
TEXT_BLOCK_TAGS = ("h1", "h2", "h3", "h4", "h5", "h6", "p", "li", "td", "th", "blockquote", "center")
QUOTE_TRANSLATION = {
    ord("\u00a0"): " ",
    ord("\u1680"): " ",
    ord("\u2000"): " ",
    ord("\u2001"): " ",
    ord("\u2002"): " ",
    ord("\u2003"): " ",
    ord("\u2004"): " ",
    ord("\u2005"): " ",
    ord("\u2006"): " ",
    ord("\u2007"): " ",
    ord("\u2008"): " ",
    ord("\u2009"): " ",
    ord("\u200a"): " ",
    ord("\u202f"): " ",
    ord("\u205f"): " ",
    ord("\u3000"): " ",
    ord("\u2018"): "'",
    ord("\u2019"): "'",
    ord("\u201a"): "'",
    ord("\u201b"): "'",
    ord("\u201c"): '"',
    ord("\u201d"): '"',
    ord("\u201e"): '"',
    ord("\u201f"): '"',
    ord("\u2010"): "-",
    ord("\u2011"): "-",
    ord("\u2012"): " - ",
    ord("\u2013"): " - ",
    ord("\u2014"): " - ",
    ord("\u2015"): " - ",
    ord("\u2212"): "-",
    ord("\u2026"): "...",
}


@dataclass(slots=True)
class CommonliiSgJudgment:
    body_plain: str
    catchwords: str
    judges: list[str] = field(default_factory=list)
    paragraphs: list[dict[str, object]] = field(default_factory=list)
    counsel: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, object]:
        return {
            "body_plain": self.body_plain,
            "catchwords": self.catchwords,
            "judges": self.judges,
            "paragraphs": self.paragraphs,
            "counsel": self.counsel,
        }


def normalise_text(raw: str) -> str:
    if not raw:
        return ""
    text = unicodedata.normalize("NFKC", unescape(raw))
    text = text.translate(QUOTE_TRANSLATION)
    return WHITESPACE_RE.sub(" ", text).strip()


def parse_commonlii_sg_html(
    html: str,
    base_row: Mapping[str, object] | None = None,
) -> dict[str, object]:
    """Extend a B1 CommonLII SG raw judgment row with parsed text fields."""
    row = dict(base_row or {})
    body_html = html or str(row.get("body_html") or "")
    parsed = parse_judgment(body_html)
    row.update(parsed.as_dict())
    return row


def parse_commonlii_sg_row(row: Mapping[str, object]) -> dict[str, object]:
    return parse_commonlii_sg_html(str(row.get("body_html") or ""), row)


def parse_judgment(html: str) -> CommonliiSgJudgment:
    soup = BeautifulSoup(html or "", "lxml")
    _drop_nontext_nodes(soup)
    lines = _visible_lines(soup)
    paragraphs = _extract_paragraphs(lines)
    top_lines = _top_lines(lines)
    body_plain = _paragraph_body_plain(paragraphs) if paragraphs else normalise_text(" ".join(lines))
    return CommonliiSgJudgment(
        body_plain=body_plain,
        catchwords=_extract_catchwords(soup),
        judges=_extract_judges(top_lines),
        paragraphs=paragraphs,
        counsel=_extract_counsel(top_lines),
    )


def _drop_nontext_nodes(soup: BeautifulSoup) -> None:
    for tag in soup.find_all(["script", "style", "noscript"]):
        tag.decompose()


def _visible_lines(soup: BeautifulSoup) -> list[str]:
    body = soup.body or soup
    lines: list[str] = []
    for raw in body.get_text("\n", strip=True).splitlines():
        line = normalise_text(raw)
        if not line or _is_commonlii_chrome(line):
            continue
        if lines and lines[-1] == line:
            continue
        lines.append(line)
    return lines


def _is_commonlii_chrome(line: str) -> bool:
    lower = line.lower()
    if lower.startswith("commonlii:"):
        return True
    return any(marker in lower for marker in CHROME_MARKERS)


def _extract_paragraphs(lines: list[str]) -> list[dict[str, object]]:
    text = "\n".join(lines)
    matches = list(PARAGRAPH_MARKER_RE.finditer(text))
    paragraphs: list[dict[str, object]] = []
    for index, match in enumerate(matches):
        number = int(match.group("number"))
        start = match.end()
        end = matches[index + 1].start() if index + 1 < len(matches) else len(text)
        paragraph_text = normalise_text(text[start:end])
        if paragraph_text:
            paragraphs.append({"number": number, "text": paragraph_text})
    return paragraphs


def _paragraph_body_plain(paragraphs: list[dict[str, object]]) -> str:
    return normalise_text(
        " ".join(f"[{paragraph['number']}] {paragraph['text']}" for paragraph in paragraphs)
    )


def _top_lines(lines: list[str]) -> list[str]:
    for index, line in enumerate(lines):
        if PARAGRAPH_LINE_RE.match(line):
            return lines[:index]
    return lines[:80]


def _extract_catchwords(soup: BeautifulSoup) -> str:
    values: list[str] = []
    for block in _iter_text_blocks(soup):
        text = normalise_text(block.get_text(" ", strip=True))
        if not text or _is_commonlii_chrome(text):
            continue
        if PARAGRAPH_LINE_RE.match(text):
            break
        if not block.find(["i", "em"]):
            continue
        value = _strip_label(text, "catchwords")
        if _looks_like_catchwords(value):
            values.append(value)
    return normalise_text(" | ".join(_dedupe(values)))


def _iter_text_blocks(soup: BeautifulSoup):
    body = soup.body or soup
    for block in body.find_all(TEXT_BLOCK_TAGS):
        if not isinstance(block, Tag):
            continue
        yield block


def _strip_label(value: str, label: str) -> str:
    return re.sub(rf"^{re.escape(label)}\s*:?\s*", "", value, flags=re.IGNORECASE).strip()


def _looks_like_catchwords(value: str) -> bool:
    if len(value) < 8:
        return False
    lower = value.lower()
    if lower.startswith(("version no", "judgment of", "grounds of", "decision of")):
        return False
    return True


def _extract_judges(lines: list[str]) -> list[str]:
    judges: list[str] = []
    for line in lines:
        match = JUDGE_LABEL_RE.match(line)
        if match:
            judges.extend(_split_judge_names(match.group("names"), labelled=True))
            continue
        delivered = DELIVERED_BY_RE.search(line)
        if delivered:
            judges.extend(_split_judge_names(delivered.group("names"), labelled=False))
    return _dedupe(judges)


def _split_judge_names(value: str, *, labelled: bool) -> list[str]:
    cleaned = normalise_text(value)
    cleaned = re.sub(r"\s+\([^)]*$", "", cleaned).strip()
    cleaned = re.sub(r"\b(?:and|with)\b", ",", cleaned, flags=re.IGNORECASE)
    names: list[str] = []
    for raw in re.split(r"\s*[,;]\s*", cleaned):
        name = _clean_judge_name(raw)
        if not name:
            continue
        if labelled or JUDGE_TITLE_RE.search(name):
            names.append(name)
    return names


def _clean_judge_name(value: str) -> str:
    name = normalise_text(value)
    name = re.sub(r"^(?:the\s+)?honou?rable\s+", "", name, flags=re.IGNORECASE)
    name = re.sub(r"^(?:chief\s+justice|justice(?:\s+of\s+appeal)?|judge)\s+", "", name, flags=re.IGNORECASE)
    if not name or len(name) < 3:
        return ""
    lowered = name.lower()
    if any(term in lowered for term in ("court of appeal", "high court", "republic of singapore")):
        return ""
    return name.rstrip(" :")


def _extract_counsel(lines: list[str]) -> list[str]:
    values = [line for line in lines if COUNSEL_RE.match(line)]
    return _dedupe(values)


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for value in values:
        normalised = normalise_text(value)
        if not normalised or normalised in seen:
            continue
        seen.add(normalised)
        out.append(normalised)
    return out
