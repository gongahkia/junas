"""Extract explicit source-jurisdiction statements from SG judgments."""
from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

VALID_LABELS: tuple[str, ...] = (
    "sg_binding",
    "uk_persuasive",
    "au_persuasive",
    "hk_persuasive",
    "not_applicable",
)

_UK_SOURCE = (
    r"(?:English|England(?:\s+and\s+Wales)?|United\s+Kingdom|UK|British|"
    r"House\s+of\s+Lords|Privy\s+Council|(?:UK|United\s+Kingdom)\s+Supreme\s+Court|"
    r"Supreme\s+Court\s+of\s+the\s+United\s+Kingdom|English\s+Court\s+of\s+Appeal|"
    r"Court\s+of\s+Appeal\s+of\s+England\s+and\s+Wales)"
)
_AU_SOURCE = (
    r"(?:Australian|Australia|High\s+Court\s+of\s+Australia|Federal\s+Court\s+of\s+Australia|"
    r"New\s+South\s+Wales|NSW|Victorian?|Queensland|Western\s+Australia(?:n)?|"
    r"South\s+Australia(?:n)?)"
)
_HK_SOURCE = (
    r"(?:Hong\s+Kong|HK|Hong\s+Kong\s+Court\s+of\s+(?:Final\s+Appeal|Appeal)|HKCFA|HKCA)"
)
_FOREIGN_SOURCE = rf"(?:{_UK_SOURCE}|{_AU_SOURCE}|{_HK_SOURCE}|foreign|overseas|Commonwealth)"
_SG_APEX_SOURCE = r"(?:Singapore\s+Court\s+of\s+Appeal|SGCA|Court\s+of\s+Appeal)"
_AUTHORITY_NOUN = r"(?:authorit(?:y|ies)|case(?:s)?|decision(?:s)?|judg(?:ment|ments))"
_QUESTION_NOUN = r"(?:question|issue|point|matter)"
_POSITIVE_FRAME = (
    r"(?:persuasive|helpful|instructive|useful|of\s+assistance|of\s+guidance|"
    r"guidance|assistance)"
)
_NEGATED_POSITIVE_RE = re.compile(
    r"\b(?:not|never)\s+(?:persuasive|helpful|instructive|useful|applicable)\b|"
    r"\bof\s+no\s+(?:assistance|guidance|help)\b|"
    r"\b(?:do|does|did)\s+not\s+assist\b|"
    r"\b(?:distinguishable|unhelpful)\b|"
    r"\bdecline[sd]?\s+to\s+(?:follow|apply)\b",
    re.IGNORECASE,
)
_BODY_PARAGRAPH_RE = re.compile(
    r"\[(?P<number>\d{1,3})\]\s*(?P<text>.*?)(?=\s*\[\d{1,3}\]\s*|$)",
    re.DOTALL,
)
_WS_RE = re.compile(r"\s+")


@dataclass(frozen=True, slots=True)
class JurisdictionStatement:
    label: str
    quote: str
    paragraph: int

    def as_dict(self) -> dict[str, object]:
        return {"label": self.label, "quote": self.quote, "paragraph": self.paragraph}


@dataclass(frozen=True, slots=True)
class _StatementPattern:
    label: str
    regex: re.Pattern[str]


def _compile(pattern: str) -> re.Pattern[str]:
    return re.compile(pattern, re.IGNORECASE | re.DOTALL)


def _foreign_patterns(label: str, source: str) -> list[_StatementPattern]:
    return [
        _StatementPattern(
            label,
            _compile(
                rf"\b(?:applying|adopting|following|approving|endorsing)\s+(?:the\s+)?"
                rf"(?:principle|approach|test|rule|reasoning)\s+(?:in|from)\s+.{{0,160}}?"
                rf"\b(?:a|the)\s+decision\s+of\s+(?:the\s+)?{source}(?:\s+court(?:s)?)?\b"
            ),
        ),
        _StatementPattern(
            label,
            _compile(
                rf"\b(?:the\s+)?{source}\s+{_AUTHORITY_NOUN}(?:\s+(?:of|in)\s+.{{1,120}}?)?\s+"
                rf"(?:is|are|was|were|remain|remains|has\s+been|have\s+been)\s+"
                rf"(?:{_POSITIVE_FRAME})\b"
            ),
        ),
        _StatementPattern(
            label,
            _compile(
                rf"\b{_AUTHORITY_NOUN}\s+(?:of|from)\s+(?:the\s+)?{source}"
                rf"(?:\s+court(?:s)?)?\s+(?:is|are|was|were|remain|remains|has\s+been|"
                rf"have\s+been)?\s*(?:{_POSITIVE_FRAME})\b"
            ),
        ),
        _StatementPattern(
            label,
            _compile(
                rf"\b(?:{_POSITIVE_FRAME})\s+.{{0,80}}?\b(?:the\s+)?{source}\s+{_AUTHORITY_NOUN}\b"
            ),
        ),
        _StatementPattern(
            label,
            _compile(
                rf"\b(?:while|although)?\s*(?:the\s+)?{source}\s+"
                rf"(?:cases|courts|authorities|decisions)\s+have\s+"
                rf"(?:considered|addressed|examined)\s+(?:this|the)\s+{_QUESTION_NOUN}\b"
            ),
        ),
        _StatementPattern(
            label,
            _compile(
                rf"\b(?:draw|derive|take|obtain|find)\s+(?:some\s+)?"
                rf"(?:guidance|assistance)\s+from\s+(?:the\s+)?{source}\s+"
                rf"(?:cases|courts|authorities|decisions)\b"
            ),
        ),
    ]


_PATTERNS: tuple[_StatementPattern, ...] = (
    _StatementPattern(
        "not_applicable",
        _compile(
            rf"\b(?:the\s+)?{_FOREIGN_SOURCE}\s+{_AUTHORITY_NOUN}\s+"
            rf"(?:are|were|is|was|remain|remains)?\s*"
            rf"(?:distinguishable|unhelpful|not\s+(?:applicable|persuasive|helpful|"
            rf"instructive|useful)|of\s+no\s+(?:assistance|guidance|help))\b"
        ),
    ),
    _StatementPattern(
        "not_applicable",
        _compile(
            rf"\b(?:the\s+)?{_FOREIGN_SOURCE}\s+(?:cases|authorities|decisions)\s+"
            rf"(?:do|does|did)\s+not\s+assist\b"
        ),
    ),
    _StatementPattern(
        "not_applicable",
        _compile(
            rf"\b(?:we|I|this\s+Court|the\s+Court)\s+decline[sd]?\s+to\s+"
            rf"(?:follow|apply)\s+(?:the\s+)?{_FOREIGN_SOURCE}\s+"
            rf"(?:cases|authorities|decisions)\b"
        ),
    ),
    _StatementPattern(
        "not_applicable",
        _compile(
            rf"\bno\s+(?:{_FOREIGN_SOURCE})\s+{_AUTHORITY_NOUN}\s+"
            rf"(?:is|was|are|were)\s+(?:applicable|helpful|of\s+assistance)\b"
        ),
    ),
    _StatementPattern(
        "sg_binding",
        _compile(
            rf"\b(?:this\s+Court|the\s+Court|we)\s+(?:is|are|was|were|remain|remains)?\s*"
            rf"bound\s+by\b(?:(?!English|United\s+Kingdom|UK|Australian|Hong\s+Kong).){{0,180}}"
            rf"\b(?:the\s+)?{_SG_APEX_SOURCE}\b"
        ),
    ),
    _StatementPattern(
        "sg_binding",
        _compile(
            rf"\b(?:decision|authority|judgment)\s+of\s+(?:the\s+)?{_SG_APEX_SOURCE}"
            rf"\b(?:(?!English|United\s+Kingdom|UK|Australian|Hong\s+Kong).){{0,120}}"
            rf"\b(?:binding|binds)\b"
        ),
    ),
    _StatementPattern(
        "sg_binding",
        _compile(
            rf"\b(?:binding|binds)\s+(?:on|upon)?\s+(?:this\s+Court|the\s+Court)\b"
            rf"(?:(?!English|United\s+Kingdom|UK|Australian|Hong\s+Kong).){{0,180}}"
            rf"\b(?:the\s+)?{_SG_APEX_SOURCE}\b"
        ),
    ),
    *_foreign_patterns("uk_persuasive", _UK_SOURCE),
    *_foreign_patterns("au_persuasive", _AU_SOURCE),
    *_foreign_patterns("hk_persuasive", _HK_SOURCE),
)


def extract_jurisdiction_statements(
    source: Mapping[str, object] | Sequence[Mapping[str, object]],
) -> list[JurisdictionStatement]:
    statements: list[JurisdictionStatement] = []
    seen: set[tuple[str, int, str]] = set()
    for number, paragraph in _iter_paragraphs(source):
        for pattern in _PATTERNS:
            for match in pattern.regex.finditer(paragraph):
                if pattern.label != "not_applicable" and _NEGATED_POSITIVE_RE.search(match.group(0)):
                    continue
                quote = _sentence_for_match(paragraph, match)
                key = (pattern.label, number, quote)
                if key in seen:
                    continue
                seen.add(key)
                statements.append(JurisdictionStatement(pattern.label, quote, number))
    return statements


def _iter_paragraphs(
    source: Mapping[str, object] | Sequence[Mapping[str, object]],
) -> list[tuple[int, str]]:
    if isinstance(source, Mapping):
        paragraphs = source.get("paragraphs")
        if isinstance(paragraphs, Sequence) and not isinstance(paragraphs, (str, bytes)):
            out = _coerce_paragraphs(paragraphs)
            if out:
                return out
        body_plain = source.get("body_plain")
        if isinstance(body_plain, str):
            return _paragraphs_from_body_plain(body_plain)
        return []
    return _coerce_paragraphs(source)


def _coerce_paragraphs(paragraphs: Sequence[Mapping[str, object]]) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for raw in paragraphs:
        if not isinstance(raw, Mapping):
            continue
        number = raw.get("number", raw.get("paragraph"))
        text = raw.get("text")
        if not isinstance(number, int) or not isinstance(text, str):
            continue
        cleaned = _normalise(text)
        if cleaned:
            out.append((number, cleaned))
    return out


def _paragraphs_from_body_plain(body_plain: str) -> list[tuple[int, str]]:
    out: list[tuple[int, str]] = []
    for match in _BODY_PARAGRAPH_RE.finditer(body_plain):
        text = _normalise(match.group("text"))
        if text:
            out.append((int(match.group("number")), text))
    return out


def _sentence_for_match(text: str, match: re.Match[str]) -> str:
    start = _sentence_start(text, match.start())
    end = _sentence_end(text, match.end())
    return _normalise(text[start:end])


def _sentence_start(text: str, index: int) -> int:
    candidates = [text.rfind(boundary, 0, index) for boundary in (". ", "? ", "! ")]
    position = max(candidates)
    return 0 if position < 0 else position + 2


def _sentence_end(text: str, index: int) -> int:
    candidates = [text.find(boundary, index) for boundary in (". ", "? ", "! ")]
    positions = [position + 1 for position in candidates if position >= 0]
    return min(positions) if positions else len(text)


def _normalise(text: str) -> str:
    return _WS_RE.sub(" ", text or "").strip()
