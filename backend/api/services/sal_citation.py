"""SAL Style Guide citation engine.

Ports kevanwee/sal-citation-generator (TS/JS) to Python. Provides:

- footnote dataclasses (CaseFootnote, TextFootnote)
- eLitigation URL → neutral-citation parser
- short-form logic (Ibid / Id / supra) for a footnote sequence
- a grammar-based citation validator (used as the SGLB-04 scorer)

Style-guide sources baked in:
- SAL_Style_Guide_Quick_Reference_2007_Ed.pdf
- SLR_Style_Guide_2021.pdf

This module is import-safe: no network, no DB, no LLM.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Literal

DEFAULT_PINPOINT_SEPARATOR = "-"

# === Footnote dataclasses ===


@dataclass
class CaseFootnote:
    case_name: str = ""
    short_name: str = ""
    report_citation: str = ""  # eg "[2009] 2 SLR(R) 332"
    year: str = ""
    court: str = ""
    case_no: str = ""
    para_start: str = ""
    para_end: str = ""
    source: Literal["elitigation", "manual"] = "manual"
    id: str = ""
    type: Literal["case"] = "case"


@dataclass
class TextFootnote:
    text: str = ""
    id: str = ""
    type: Literal["text"] = "text"


Footnote = CaseFootnote | TextFootnote


@dataclass(frozen=True)
class CitationOutput:
    text: str
    html: str


# === Normalisers ===


def _normalize_string(value: object) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _strip_outer_brackets(value: str) -> str:
    return _normalize_string(value).removeprefix("[").removesuffix("]")


def _escape_html(value: str) -> str:
    return (
        _normalize_string(value)
        .replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
        .replace("'", "&#39;")
    )


def _normalize_text_citation(text: str) -> str:
    return re.sub(r"\.+$", "", _normalize_string(text))


def _normalize_case_number(case_no: str) -> str:
    normalized = _normalize_string(case_no)
    if not normalized.isdigit():
        return normalized
    return str(int(normalized))


def _normalize_case_identity(note: Footnote | None) -> str:
    if not isinstance(note, CaseFootnote):
        return ""
    report = _normalize_string(note.report_citation).lower()
    if report:
        return f"report:{report}"
    year = _normalize_string(note.year)
    court = _normalize_string(note.court).upper()
    case_no = _normalize_case_number(note.case_no)
    if year and court and case_no:
        return f"neutral:{year}|{court}|{case_no}"
    return f"name:{_normalize_string(note.case_name).lower()}"


def _get_pinpoint_parts(note: Footnote | None) -> tuple[str, str]:
    if not isinstance(note, CaseFootnote):
        return "", ""
    return _strip_outer_brackets(note.para_start), _strip_outer_brackets(note.para_end)


def _is_same_case(left: Footnote | None, right: Footnote | None) -> bool:
    left_id = _normalize_case_identity(left)
    return bool(left_id) and left_id == _normalize_case_identity(right)


def _is_same_pinpoint(left: Footnote | None, right: Footnote | None) -> bool:
    return _get_pinpoint_parts(left) == _get_pinpoint_parts(right)


def _resolve_pinpoint(note: Footnote | None, separator: str = DEFAULT_PINPOINT_SEPARATOR) -> str:
    start, end = _get_pinpoint_parts(note)
    if not start:
        return ""
    if end and end != start:
        return f"at [{start}]{separator}[{end}]"
    return f"at [{start}]"


def _resolve_neutral_citation(note: CaseFootnote) -> str:
    year = _normalize_string(note.year)
    court = _normalize_string(note.court).upper()
    case_no = _normalize_case_number(note.case_no)
    if not (year and court and case_no):
        return ""
    return f"[{year}] {court} {case_no}"


def _resolve_primary_case_citation(note: CaseFootnote) -> str:
    report = _normalize_string(note.report_citation)
    if report:
        return report
    return _resolve_neutral_citation(note)


def _resolve_short_case_name(note: CaseFootnote) -> str:
    short = _normalize_string(note.short_name)
    if short:
        return short
    name = _normalize_string(note.case_name)
    if name:
        return name
    return _resolve_primary_case_citation(note)


def _ensure_trailing_period(text: str) -> str:
    return re.sub(r"\.+$", "", _normalize_string(text)) + "."


# === Formatters ===


def _format_text_citation(note: TextFootnote) -> CitationOutput:
    text = _normalize_text_citation(note.text)
    return CitationOutput(text=f"{text}.", html=f"{_escape_html(text)}.")


def _format_full_case_citation(note: CaseFootnote) -> CitationOutput:
    case_name = _normalize_string(note.case_name)
    citation = _resolve_primary_case_citation(note)
    pinpoint = _resolve_pinpoint(note)

    text_parts: list[str] = []
    html_parts: list[str] = []
    if case_name:
        text_parts.append(case_name)
        html_parts.append(f'<span class="italic">{_escape_html(case_name)}</span>')
    if citation:
        text_parts.append(citation)
        html_parts.append(_escape_html(citation))
    if pinpoint:
        text_parts.append(pinpoint)
        html_parts.append(_escape_html(pinpoint))

    return CitationOutput(
        text=_ensure_trailing_period(" ".join(text_parts)),
        html=_ensure_trailing_period(" ".join(html_parts)),
    )


def _format_ibid() -> CitationOutput:
    return CitationOutput(text="Ibid.", html='<span class="italic">Ibid</span>.')


def _format_id(note: CaseFootnote) -> CitationOutput:
    pinpoint = _resolve_pinpoint(note)
    if not pinpoint:
        return CitationOutput(text="Id.", html='<span class="italic">Id</span>.')
    return CitationOutput(
        text=f"Id, {pinpoint}.",
        html=f'<span class="italic">Id</span>, {_escape_html(pinpoint)}.',
    )


def _format_supra(note: CaseFootnote, first_index: int) -> CitationOutput:
    short = _resolve_short_case_name(note)
    pinpoint = _resolve_pinpoint(note)
    suffix = f", {pinpoint}" if pinpoint else ""
    return CitationOutput(
        text=f"{short}, supra n {first_index + 1}{suffix}.",
        html=f"{_escape_html(short)}, <span class=\"italic\">supra</span> n {first_index + 1}{_escape_html(suffix)}.",
    )


# === Public: eLitigation URL parser ===

_ELITIGATION_NEUTRAL_RE = re.compile(r"(\d{4})_(SG[A-Z]+)_(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class ElitigationParse:
    year: str
    court: str
    case_no: str


def parse_elitigation_url(url: str) -> ElitigationParse | None:
    """Extract neutral citation fields from an eLitigation URL.

    Accepts forms like ``https://www.elitigation.sg/gd/s/2023_SGCA_5`` and
    decoded variants. Returns ``None`` if no neutral-citation pattern matches.
    """
    raw = _normalize_string(url)
    if not raw:
        return None
    from urllib.parse import unquote

    match = _ELITIGATION_NEUTRAL_RE.search(unquote(raw))
    if not match:
        return None
    return ElitigationParse(
        year=match.group(1),
        court=match.group(2).upper(),
        case_no=_normalize_case_number(match.group(3)),
    )


# === Public: sequence-aware citation formatter ===


def compute_citation_outputs(footnotes: list[Footnote]) -> list[CitationOutput]:
    """Format a sequence of footnotes with SAL short-form logic.

    Rules applied (per SAL Style Guide):
    - First reference to a case → full case citation with pinpoint.
    - Immediate repeat, same pinpoint → ``Ibid.``
    - Immediate repeat, different pinpoint → ``Id, at [x].``
    - Non-immediate repeat → ``short name, supra n N, at [x].`` where N is
      the 1-indexed first occurrence.
    - Text footnotes → trailing-period normalised.
    """
    items = list(footnotes or [])
    outputs: list[CitationOutput] = [CitationOutput(text="", html="")] * len(items)
    first_case_reference: dict[str, int] = {}

    for index, note in enumerate(items):
        if isinstance(note, CaseFootnote):
            key = _normalize_case_identity(note)
            if key and key not in first_case_reference:
                first_case_reference[key] = index

    for index, note in enumerate(items):
        if isinstance(note, TextFootnote):
            outputs[index] = _format_text_citation(note)
            continue
        if not isinstance(note, CaseFootnote):
            outputs[index] = _format_text_citation(TextFootnote(text=""))
            continue

        previous = items[index - 1] if index > 0 else None
        if isinstance(previous, CaseFootnote) and _is_same_case(note, previous):
            outputs[index] = _format_ibid() if _is_same_pinpoint(note, previous) else _format_id(note)
            continue

        first_index = first_case_reference.get(_normalize_case_identity(note))
        if first_index is not None and first_index < index:
            outputs[index] = _format_supra(note, first_index)
            continue

        outputs[index] = _format_full_case_citation(note)

    return outputs


# === Public: factory helpers ===


def create_case_footnote_from_elitigation(parsed: ElitigationParse) -> CaseFootnote:
    return CaseFootnote(
        source="elitigation",
        year=_normalize_string(parsed.year),
        court=_normalize_string(parsed.court).upper(),
        case_no=_normalize_case_number(parsed.case_no),
    )


def create_text_footnote(text: str) -> TextFootnote:
    return TextFootnote(text=_normalize_string(text))


# === SGLB-04 scorer: grammar-based citation validation ===
#
# Recognises SAL Style Guide citation forms. Each pattern uses the format
# documented in the SLR Style Guide 2021 + SAL Quick Reference 2007.

# Case citations
_PINPOINT_TOKEN_RE = (
    r"(?:"
    r"\[\d+\](?:\s*[–-]\s*\[\d+\])?(?:\s*(?:,|and)\s*\[\d+\](?:\s*[–-]\s*\[\d+\])?)*"
    r"|\d+[A-Z]?(?:\s*[–-]\s*\d+[A-Z]?)*(?:\s*(?:,|and)\s*(?:\d+[A-Z]?(?:\s*[–-]\s*\d+[A-Z]?)*|\[\d+\](?:\s*[–-]\s*\[\d+\])?))*"
    r"(?:\s+(?:LHC|RHC))?"
    r"|\*\d+"
    r"|p+\s+[\w./–-]+"
    r"|para(?:s)?\s+[\d./–-]+"
    r")"
)
_SHORT_NAME_RE = r"(?:\s+\((?:\"[^\"]+\"|“[^”]+”)\))?"
_SG_COURT_CODE_RE = r"SG[A-Z]+(?:\([A-Z]\))?"
_NEUTRAL_CITATION_RE = re.compile(
    rf"^(?:(?P<case_name>[^\[]+?)\s+)?\[(?P<year>\d{{4}})\]\s+(?P<court>{_SG_COURT_CODE_RE})\s+"
    rf"(?P<case_no>\d+){_SHORT_NAME_RE}(?:\s+at\s+(?P<pinpoint>{_PINPOINT_TOKEN_RE}))?$"
)
_SLR_R_RE = re.compile(
    rf"^(?:(?P<case_name>[^\[]+?)\s+)?\[(?P<year>\d{{4}})\]\s+(?P<volume>\d+)\s+SLR\(R\)\s+"
    rf"(?P<page>\d+){_SHORT_NAME_RE}(?:\s+at\s+(?P<pinpoint>{_PINPOINT_TOKEN_RE}))?$"
)
_SLR_RE = re.compile(
    rf"^(?:(?P<case_name>[^\[]+?)\s+)?\[(?P<year>\d{{4}})\]\s+(?P<volume>\d+)\s+SLR\s+"
    rf"(?P<page>\d+){_SHORT_NAME_RE}(?:\s+at\s+(?P<pinpoint>{_PINPOINT_TOKEN_RE}))?"
    rf"(?:\s+\((?P<court_level>[A-Z][A-Za-z]*(?:,\s*[A-Za-z’']+)?)\))?$"
)
_REPORTED_CASE_RE = re.compile(
    rf"^(?P<case_name>(?:In re\s+.+?|Re\s+.+?|The\s+.+?|.+?\sv\s+.+?))\s+"
    rf"(?P<citation>(?:\[\d{{4}}\]|\(\d{{4}}\)|\d{{4}})\s+(?:\d+(?:\(\d+\))?\s+)?"
    rf"[A-Z][A-Za-z0-9’'&.() ]+\s+\d+)"
    rf"{_SHORT_NAME_RE}(?:\s+at\s+(?P<pinpoint>{_PINPOINT_TOKEN_RE}))?"
    rf"(?:\s+\([^)]+\))?(?:[;,]\s+.+)?$"
)
_US_CASE_RE = re.compile(
    rf"^(?P<case_name>.+?\sv\s.+?)\s+(?P<volume>\d+)\s+"
    rf"(?P<report>US|F\s+\d+d|F\s+Supp|[A-Z][A-Za-z ]+)\s+(?P<page>\d+)"
    rf"(?:\s+at\s+(?P<pinpoint>{_PINPOINT_TOKEN_RE}))?\s+\((?P<court_year>[^)]*\d{{4}})\)$"
)
_INDIAN_SCOTTISH_CASE_RE = re.compile(
    r"^(?P<case_name>(?:In re\s+.+|.+?\sv\s+.+?))\s+(?P<citation>(?:AIR\s+\d{4}\s+[A-Za-z]+\s+\d+|\d{4}\s+SC\s+\d+))$"
)
_UNREPORTED_CASE_RE = re.compile(
    rf"^(?P<case_name>.+?\sv\s.+?)\s+(?:(?P<case_no>[A-Z]+/[A-Z]+\s+\d+/\d{{4}}|[A-Z][A-Za-z ]+ No \d+ of \d{{4}}|Nos? [^)]+)"
    rf"\s+)?\((?P<date_or_court>[^)]*\d{{4}}[^)]*)\)(?:\s+\([^)]+\))?(?:\s+at\s+(?P<pinpoint>{_PINPOINT_TOKEN_RE}))?$"
)
_ELECTRONIC_CASE_RE = re.compile(
    r"^(?P<case_name>.+?\sv\s.+?)(?:\s+No[s]? [^,]+,|\s+[A-Z][A-Za-z ]+ No \d+ of \d{4},)?"
    r".*(?:LEXIS|\bWL\b|<https?://).*$"
)
_CASE_DIGEST_RE = re.compile(r"^(?:…\s+)?digested at .*(?:Digest|CLY|CL|Issue No).*\d+.*$")
_CASE_SUBSEQUENT_RE = re.compile(r"^.+\(\[\d+\]\s+supra\)(?:\s+at\s+[\d[\]][^,]*)?.*$")

# Statute citation. Anchor on the trailing (Cap. NN[, YYYY Rev Ed]) marker;
# allow any preceding text starting with a capital, including embedded
# (Amendment) suffixes. Accommodates "Penal Code", "Misuse of Drugs Act",
# "Companies (Amendment) Act", etc.
_STATUTE_CAP_RE = re.compile(
    r"^(?P<title>[A-Z].*?)\s*\((?P<cap>(?:SS\s+)?Cap\.?\s*\d+[A-Z]?"
    r"(?:\s*,\s*(?:R|Rg)\s*\d+)?(?:\s*,\s*\d{4}\s+Rev\s+(?:Ed|Edition))?)\)"
    r"(?:\s+(?P<pinpoint>(?:s|ss|Art|O|r|reg|regs|cl)\s+.+))?$"
)

# Statute section reference (eg "s 9 of the Penal Code")
_STATUTE_SECTION_RE = re.compile(
    r"^(?:s|ss|Section|Sections)(?:\.|ection)?\s+\d+[A-Z]?(?:\(\d+\))?(?:\([a-z]\))?(?:\([ivx]+\))?"
    r"(?:\s*(?:,|and|to|–|-)\s*\d+[A-Z]?(?:\(\d+\))?(?:\([a-z]\))?(?:\([ivx]+\))?)*"
    r"(?:\s+of\s+the\s+[A-Z][A-Za-z0-9&'/\s-]+Act)?$"
)
_STATUTE_ABBREV_SECTION_RE = re.compile(r"^[A-Z]{2,}\s+(?:s|ss|reg|regs|r|rr|O|Art)\s+.+$")

# Pinpoint reference standalone
_PINPOINT_RE = re.compile(rf"^at\s+{_PINPOINT_TOKEN_RE}$")

_BILL_RE = re.compile(r"^[A-Z].* Bill(?:\s+\d{4})? \((?:Bill )?(?:No \d+/\d{2,4}|\d+ of \d{4})\)(?:\s+cl\s+.+)?$")
_LEGISLATION_RE = re.compile(
    r"^[A-Z].*?(?:Act|Ordinance|Proclamation|Constitution|Regulations|Rules|Order|Code|Notification|List|Agreement)"
    r".*?(?:\((?:Act|Indian Act|SS Ord|Procl|No|GN|SS GN|SS Govt Gazette|GN Supp|CA|PU\([AB]\)|SR|c|SI|2020 Rev Ed|"
    r"\d{4} Rev Ed|\d{4} Reprint|M’sia|NZ|Can|Cth|Vic|US)[^)]*\)|\d{4} \(Act \d+ of \d{4}\)|\d+\s+USC|\d+\s+CFR).*$"
)
_CONSTITUTION_RE = re.compile(r"^Constitution(?: of the Republic of Singapore)?(?:\s+\(\d{4} Rev Ed,\s+\d{4} Reprint\)|\s+\(\d{4} Reprint\))?(?:\s+Art\s+.+)?$")
_GAZETTE_LEGISLATION_RE = re.compile(r"^[A-Z].*\((?:SS\s+)?(?:GN|GN Sp|GN Supp|CA|PU\([AB]\)|SS Govt Gazette).*\)(?:\s+.+)?$")
_BARE_YEAR_LEGISLATION_RE = re.compile(
    r"^[A-Z].*?(?:Act|Ordinance|Regulations|Rules|Order|Notification)\s+\d{4}(?:\s+\([^)]+\))?(?:\s+(?:s|ss|reg|regs|r|rr|O|ch|Art|Amend)\s+.+)?$"
)
_REVISED_YEAR_LEGISLATION_RE = re.compile(
    r"^[A-Z].*?\(\d{4} Rev Ed(?:,\s+\d{4} Reprint)?\)(?:\s+(?:s|ss|reg|regs|r|rr|O|ch|Art|Amend)\s+.+)?$"
)
_FOREIGN_YEAR_LEGISLATION_RE = re.compile(
    r"^[A-Z].*\d{4}\s+\((?:Cth|Vic|NZ|M’sia|UK|Can)\)(?:\s+(?:s|ss|reg|regs|r|rr|O|ch|Art|Amend)\s+.+)?$"
)
_US_CONSTITUTION_RE = re.compile(r"^US Constitution (?:Art|Amend) .+$")
_US_CODE_RE = re.compile(r"^(?:[A-Z].*?\s+)?\d+\s+(?:USC|CFR)\s+\(US\)\s+§\s*[\w.()]+(?:\s+\(\d{4}\))?$")
_GOVERNMENT_PUBLICATION_RE = re.compile(
    r"^(?P<title>.+?(?:Parliamentary Debates|Legislative Council Proceedings|Official Report|Report of|White Paper|"
    r"Command Paper|Cmnd|Cmd|Parl \d+ of|Proceed with Care|Final Report).*)$"
)
_BOOK_RE = re.compile(
    r"^(?P<title>(?:[A-Z][^,]+,\s+)?[^<>“”\"]+?)\s+\([^)]+(?:\d{4}|\d{4} issue|release)[^)]*\)"
    r"(?:\s+\([^)]+\))*?(?:\s+at\s+(?:p|pp|para|ch)\s+[\w./–-]+)?$"
)
_BOOK_SUBSEQUENT_RE = re.compile(r"^[A-Z][A-Za-z &',-]+(?:,\s+[A-Z][A-Za-z &'’:-]+)?\s+at\s+(?:p|para|ch)\s+[\w./–-]+$")
_ARTICLE_RE = re.compile(
    r"^(?P<author>.+?,\s+)?[“\"‘'][^”\"’']+[”\"’'].*(?:\([^)]*\d{4}[^)]*\)|\[\d{4}\]|\d{4};|Law Times|Singapore Law Gazette|"
    r"The Straits Times|The Times|Time|UPI|Newswire|FindLaw|available in).*$"
)
_ARTICLE_SUBSEQUENT_RE = re.compile(r"^[A-Z][A-Za-z '-]+,\s+[“\"‘'][^”\"’']+[”\"’']\s+at\s+(?:p|pp|para|ch)\s+[\w./–-]+$")
_INTERNET_MATERIAL_RE = re.compile(r"^.+<https?://.+>(?:\s+\(accessed [^)]+\))?(?:\s+at\s+.+)?$")
_LAW_REFORM_RE = re.compile(
    r"^.*(?:Law Reform|Commission|Attorney-General’s Chambers|Discussion Paper|LRRD No).*"
    r"(?:\([^)]*\d{4}|\d{1,2}\s+[A-Z][a-z]+\s+\d{4}).*$"
)
_UNPUBLISHED_RE = re.compile(
    r"^(?:Letter from|Memorandum from|Telephone interview|E-mail interview|.+interview with|.+speech at|.+press statement|.+lunch talk at|.+keynote address at).*$"
    r"|^.*(?:unpublished|archived at).*$"
)
_FORTHCOMING_RE = re.compile(r"^.+\([^)]*forthcoming,[^)]*\).*$")
_TREATY_RE = re.compile(
    r"^.*(?:Convention|Covenant|Agreement|Free Trade Agreement).*\(\d{1,2}\s+[A-Z][a-z]+\s+\d{4}\).*"
    r"(?:UNTS|ILM|Treaty|entered into force|<https?://).*$"
)
_INTERNATIONAL_CASE_RE = re.compile(
    r"^.+(?:ICJ|PCIJ|ECR|CMLR|EHRR|Eur Ct HR|Eur Comm HR|YB Eur Conv HR|EU:C:).*$"
)
_UN_MATERIAL_RE = re.compile(r"^.+(?:UN GAOR|UN SCOR|UN Doc|GA Res|SC Res|UN Sales No|YB\s+Int’l L\s+Comm’n).*$")
_EU_MATERIAL_RE = re.compile(r"^.*(?:EC Council|EC Commission|EU Council|European Parliament|European Commission|European Central Bank|OJ [LC]).*$")
_COUNCIL_OF_EUROPE_RE = re.compile(r"^Council of Europe, .+$")
_WTO_GATT_RE = re.compile(r"^.+(?:WTO|GATT|BISD).*$")


_SG_COURT_CODES = frozenset(
    {
        "SGCA",
        "SGHC",
        "SGHCR",
        "SGDC",
        "SGMC",
        "SGFC",
        "SGCFI",
        "SGIA",
        "SGHCF",
        "SGSAC",
        "SGCT",
        "SGHC(A)",
        "SGHC(I)",
        "SGCA(I)",
        "SGSCT",
        "SGYC",
    }
)


CitationKind = Literal[
    "neutral_case",
    "slr_r_case",
    "slr_case",
    "reported_case",
    "us_case",
    "unreported_case",
    "electronic_case",
    "case_digest",
    "case_subsequent",
    "statute_cap",
    "statute_section",
    "legislation",
    "bill",
    "government_publication",
    "book",
    "book_subsequent",
    "article",
    "internet_material",
    "law_reform_report",
    "unpublished_material",
    "forthcoming_material",
    "treaty",
    "international_case",
    "un_material",
    "eu_material",
    "council_of_europe_material",
    "wto_gatt_material",
    "pinpoint",
    "ibid",
    "id_with_pinpoint",
    "supra",
    "unknown",
]


@dataclass(frozen=True)
class ValidationError:
    code: str
    message: str


@dataclass(frozen=True)
class ValidationResult:
    valid: bool
    kind: CitationKind
    errors: tuple[ValidationError, ...] = field(default_factory=tuple)
    components: dict[str, str] = field(default_factory=dict)


def _validate_neutral(match: re.Match[str]) -> ValidationResult:
    year_str, court, case_no_str = match.group("year"), match.group("court"), match.group("case_no")
    errors: list[ValidationError] = []
    year = int(year_str)
    if year < 1965 or year > 2100:
        errors.append(ValidationError("year_out_of_range", f"year {year} outside [1965, 2100]"))
    if court not in _SG_COURT_CODES:
        errors.append(ValidationError("unknown_court", f"court code {court!r} not recognised"))
    if int(case_no_str) <= 0:
        errors.append(ValidationError("case_no_non_positive", "case number must be positive"))
    components = {
        "year": year_str,
        "court": court,
        "case_no": case_no_str,
    }
    if match.groupdict().get("case_name"):
        components["case_name"] = match.group("case_name")
    if match.groupdict().get("pinpoint"):
        components["pinpoint"] = match.group("pinpoint")
    return ValidationResult(valid=not errors, kind="neutral_case", errors=tuple(errors), components=components)


def _validate_slr(match: re.Match[str], kind: CitationKind) -> ValidationResult:
    year_str, volume_str, page_str = match.group("year"), match.group("volume"), match.group("page")
    errors: list[ValidationError] = []
    year = int(year_str)
    if year < 1965 or year > 2100:
        errors.append(ValidationError("year_out_of_range", f"year {year} outside [1965, 2100]"))
    if int(volume_str) <= 0:
        errors.append(ValidationError("volume_non_positive", "volume must be positive"))
    if int(page_str) <= 0:
        errors.append(ValidationError("page_non_positive", "page must be positive"))
    components = {
        "year": year_str,
        "volume": volume_str,
        "report": "SLR(R)" if kind == "slr_r_case" else "SLR",
        "page": page_str,
    }
    if match.groupdict().get("case_name"):
        components["case_name"] = match.group("case_name")
    if match.groupdict().get("pinpoint"):
        components["pinpoint"] = match.group("pinpoint")
    if match.groupdict().get("court_level"):
        components["court_level"] = match.group("court_level")
    return ValidationResult(valid=not errors, kind=kind, errors=tuple(errors), components=components)


def _valid(kind: CitationKind, **components: str) -> ValidationResult:
    return ValidationResult(valid=True, kind=kind, components={k: v for k, v in components.items() if v})


def _validate_reported_case(match: re.Match[str]) -> ValidationResult:
    citation = match.group("citation")
    pinpoint = match.groupdict().get("pinpoint")
    if not pinpoint and " at " in citation:
        possible_citation, possible_pinpoint = citation.rsplit(" at ", 1)
        if re.match(rf"^{_PINPOINT_TOKEN_RE}$", possible_pinpoint):
            citation = possible_citation
            pinpoint = possible_pinpoint
    components = {"case_name": match.group("case_name"), "citation": citation}
    if pinpoint:
        components["pinpoint"] = pinpoint
    return _valid("reported_case", **components)


def validate_citation(citation: str) -> ValidationResult:
    """Validate a citation string against SAL Style Guide grammar.

    Recognises SG case (neutral, SLR(R), SLR), SG statute (Cap.), section
    references, pinpoints, and short forms (Ibid, Id, supra). Returns a
    structured result with the citation kind and any per-rule errors.

    This is the canonical scorer for SGLB-04 Citation-Verify.
    """
    raw = _normalize_string(citation)
    if not raw:
        return ValidationResult(
            valid=False,
            kind="unknown",
            errors=(ValidationError("empty", "citation is empty"),),
        )

    stripped = re.sub(r"\s+", " ", raw)
    stripped = re.sub(r"\.+$", "", stripped)

    match = _NEUTRAL_CITATION_RE.match(stripped)
    if match:
        return _validate_neutral(match)

    match = _SLR_R_RE.match(stripped)
    if match:
        return _validate_slr(match, "slr_r_case")

    match = _SLR_RE.match(stripped)
    if match:
        return _validate_slr(match, "slr_case")

    if _INTERNATIONAL_CASE_RE.match(stripped):
        return _valid("international_case", marker="international_case")

    match = _ELECTRONIC_CASE_RE.match(stripped)
    if match:
        components = {"case_name": match.group("case_name"), "marker": "electronic"}
        pinpoint_match = re.search(rf"\sat\s+({_PINPOINT_TOKEN_RE})(?:\s+\(|$)", stripped)
        if pinpoint_match:
            components["pinpoint"] = pinpoint_match.group(1)
        return _valid("electronic_case", **components)

    match = _US_CASE_RE.match(stripped)
    if match:
        components = {
            "case_name": match.group("case_name"),
            "volume": match.group("volume"),
            "report": match.group("report"),
            "page": match.group("page"),
            "court_year": match.group("court_year"),
        }
        if match.groupdict().get("pinpoint"):
            components["pinpoint"] = match.group("pinpoint")
        return _valid("us_case", **components)

    match = _INDIAN_SCOTTISH_CASE_RE.match(stripped)
    if match:
        return _validate_reported_case(match)

    match = _UNREPORTED_CASE_RE.match(stripped)
    if match:
        components = {"case_name": match.group("case_name"), "date_or_court": match.group("date_or_court")}
        if match.groupdict().get("case_no"):
            components["case_no"] = match.group("case_no")
        if match.groupdict().get("pinpoint"):
            components["pinpoint"] = match.group("pinpoint")
        return _valid("unreported_case", **components)

    match = _REPORTED_CASE_RE.match(stripped)
    if match:
        return _validate_reported_case(match)

    if _CASE_DIGEST_RE.match(stripped):
        return _valid("case_digest", marker="digested at")

    if _CASE_SUBSEQUENT_RE.match(stripped):
        return _valid("case_subsequent", marker="supra")

    match = _STATUTE_CAP_RE.match(stripped)
    if match:
        components = {"title": match.group("title"), "cap": match.group("cap")}
        if match.groupdict().get("pinpoint"):
            components["pinpoint"] = match.group("pinpoint")
        return _valid("statute_cap", **components)

    if _STATUTE_SECTION_RE.match(stripped):
        return _valid("statute_section", marker="section")

    if _STATUTE_ABBREV_SECTION_RE.match(stripped):
        return _valid("statute_section", marker="section")

    if _PINPOINT_RE.match(stripped):
        return _valid("pinpoint", pinpoint=stripped.removeprefix("at "))

    if re.match(r"^(?:.+,\s+)?Ibid(?:,\s+at\s+.+)?$", stripped, re.IGNORECASE):
        components = {"marker": "ibid"}
        if "," in stripped:
            components["pinpoint"] = stripped.split(",", 1)[1].strip()
        return _valid("ibid", **components)

    if re.match(rf"^Id(?:,\s+at\s+{_PINPOINT_TOKEN_RE})?$", stripped, re.IGNORECASE):
        components = {"marker": "id"}
        if "," in stripped:
            components["pinpoint"] = stripped.split(",", 1)[1].strip()
        return _valid("id_with_pinpoint", **components)

    if re.match(rf"^(?:.+,\s+)?supra\s+n\s+\d+(?:,\s+at\s+{_PINPOINT_TOKEN_RE})?(?:\s+and\s+\d+)?$", stripped, re.IGNORECASE):
        return _valid("supra", marker="supra")

    if _BILL_RE.match(stripped):
        return _valid("bill", marker="Bill")

    if _CONSTITUTION_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _GAZETTE_LEGISLATION_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _BARE_YEAR_LEGISLATION_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _REVISED_YEAR_LEGISLATION_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _FOREIGN_YEAR_LEGISLATION_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _US_CONSTITUTION_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _US_CODE_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _LEGISLATION_RE.match(stripped):
        return _valid("legislation", marker="legislation")

    if _COUNCIL_OF_EUROPE_RE.match(stripped):
        return _valid("council_of_europe_material", marker="Council of Europe")

    if _UN_MATERIAL_RE.match(stripped):
        return _valid("un_material", marker="UN")

    if _EU_MATERIAL_RE.match(stripped):
        return _valid("eu_material", marker="EU")

    if _WTO_GATT_RE.match(stripped):
        return _valid("wto_gatt_material", marker="WTO/GATT")

    if _TREATY_RE.match(stripped):
        return _valid("treaty", marker="treaty")

    if _LAW_REFORM_RE.match(stripped):
        return _valid("law_reform_report", marker="law_reform")

    if _GOVERNMENT_PUBLICATION_RE.match(stripped):
        return _valid("government_publication", marker="government_publication")

    if _FORTHCOMING_RE.match(stripped):
        return _valid("forthcoming_material", marker="forthcoming")

    if _UNPUBLISHED_RE.match(stripped):
        return _valid("unpublished_material", marker="unpublished")

    if _ARTICLE_RE.match(stripped):
        return _valid("article", marker="article")

    if _ARTICLE_SUBSEQUENT_RE.match(stripped):
        return _valid("article", marker="article")

    if _INTERNET_MATERIAL_RE.match(stripped):
        return _valid("internet_material", marker="internet")

    if _BOOK_SUBSEQUENT_RE.match(stripped):
        return _valid("book_subsequent", marker="book")

    if _BOOK_RE.match(stripped):
        return _valid("book", marker="book")

    return ValidationResult(
        valid=False,
        kind="unknown",
        errors=(ValidationError("no_grammar_match", "no SAL citation grammar rule matched"),),
    )
