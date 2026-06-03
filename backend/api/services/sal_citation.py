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
_NEUTRAL_CITATION_RE = re.compile(r"^\[(\d{4})\]\s+(SG[A-Z]+)\s+(\d+)$")
_SLR_R_RE = re.compile(r"^\[(\d{4})\]\s+(\d+)\s+SLR\(R\)\s+(\d+)$")
_SLR_RE = re.compile(r"^\[(\d{4})\]\s+(\d+)\s+SLR\s+(\d+)$")

# Statute citation. Anchor on the trailing (Cap. NN[, YYYY Rev Ed]) marker;
# allow any preceding text starting with a capital, including embedded
# (Amendment) suffixes. Accommodates "Penal Code", "Misuse of Drugs Act",
# "Companies (Amendment) Act", etc.
_STATUTE_CAP_RE = re.compile(
    r"^([A-Z].*?)\s*\(Cap\.?\s*\d+[A-Z]?(?:\s*,\s*\d{4}\s+Rev\s+Ed)?\)$"
)

# Statute section reference (eg "s 9 of the Penal Code")
_STATUTE_SECTION_RE = re.compile(
    r"^s(?:\.|ection)?\s+\d+[A-Z]?(?:\(\d+\))?(?:\s+of\s+the\s+[A-Z][A-Za-z0-9&'/\s-]+Act)?$"
)

# Pinpoint reference standalone
_PINPOINT_RE = re.compile(r"^at\s+\[\d+\](?:-\[\d+\])?$")


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
    }
)


CitationKind = Literal[
    "neutral_case",
    "slr_r_case",
    "slr_case",
    "statute_cap",
    "statute_section",
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


def _validate_neutral(match: re.Match[str]) -> ValidationResult:
    year_str, court, case_no_str = match.group(1), match.group(2), match.group(3)
    errors: list[ValidationError] = []
    year = int(year_str)
    if year < 1965 or year > 2100:
        errors.append(ValidationError("year_out_of_range", f"year {year} outside [1965, 2100]"))
    if court not in _SG_COURT_CODES:
        errors.append(ValidationError("unknown_court", f"court code {court!r} not recognised"))
    if int(case_no_str) <= 0:
        errors.append(ValidationError("case_no_non_positive", "case number must be positive"))
    return ValidationResult(valid=not errors, kind="neutral_case", errors=tuple(errors))


def _validate_slr(match: re.Match[str], kind: CitationKind) -> ValidationResult:
    year_str, volume_str, page_str = match.group(1), match.group(2), match.group(3)
    errors: list[ValidationError] = []
    year = int(year_str)
    if year < 1965 or year > 2100:
        errors.append(ValidationError("year_out_of_range", f"year {year} outside [1965, 2100]"))
    if int(volume_str) <= 0:
        errors.append(ValidationError("volume_non_positive", "volume must be positive"))
    if int(page_str) <= 0:
        errors.append(ValidationError("page_non_positive", "page must be positive"))
    return ValidationResult(valid=not errors, kind=kind, errors=tuple(errors))


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

    stripped = re.sub(r"\.+$", "", raw)

    match = _NEUTRAL_CITATION_RE.match(stripped)
    if match:
        return _validate_neutral(match)

    match = _SLR_R_RE.match(stripped)
    if match:
        return _validate_slr(match, "slr_r_case")

    match = _SLR_RE.match(stripped)
    if match:
        return _validate_slr(match, "slr_case")

    if _STATUTE_CAP_RE.match(stripped):
        return ValidationResult(valid=True, kind="statute_cap")

    if _STATUTE_SECTION_RE.match(stripped):
        return ValidationResult(valid=True, kind="statute_section")

    if _PINPOINT_RE.match(stripped):
        return ValidationResult(valid=True, kind="pinpoint")

    if stripped == "Ibid":
        return ValidationResult(valid=True, kind="ibid")

    if re.match(r"^Id(,\s+at\s+\[\d+\](?:-\[\d+\])?)?$", stripped):
        return ValidationResult(valid=True, kind="id_with_pinpoint")

    if re.match(r"^.+,\s+supra\s+n\s+\d+(?:,\s+at\s+\[\d+\](?:-\[\d+\])?)?$", stripped):
        return ValidationResult(valid=True, kind="supra")

    return ValidationResult(
        valid=False,
        kind="unknown",
        errors=(ValidationError("no_grammar_match", "no SAL citation grammar rule matched"),),
    )
