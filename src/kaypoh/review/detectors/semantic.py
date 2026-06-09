from __future__ import annotations

import datetime as dt
import os
import re
from typing import Any, Callable

from kaypoh.review.detectors.registry import DetectorContext

_DOB_MONTH = (
    r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|Jun(?:e)?|Jul(?:y)?|"
    r"Aug(?:ust)?|Sep(?:t|tember)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?)"
)
_DOB_DATE_FRAGMENT = (
    r"(?:\d{4}-\d{1,2}-\d{1,2}|"
    r"\d{1,2}[/-]\d{1,2}[/-]\d{2,4}|"
    r"\d{1,2}\s+" + _DOB_MONTH + r"\s+\d{4}|"
    + _DOB_MONTH + r"\s+\d{1,2},?\s+\d{4})"
)
SEMANTIC_NAME_LABEL_RE = re.compile(
    r"(?:^|[;\n])\s*(?i:(?:full\s+name|legal\s+name|client\s+name|patient\s+name|employee\s+name|"
    r"data\s+subject\s+name|contact\s+person|name|姓名|氏名|名前|성명|이름|ชื่อ|nama|họ\s+tên|الاسم))"
    r"\s*[:：=]\s*"
    r"(?P<name>(?-i:[A-Z][a-z]+(?:[-\u2010-\u2015][A-Z][a-z]+)?"
    r"(?:[ \t]+[A-Z][a-z]+(?:[-\u2010-\u2015][A-Z][a-z]+)?){1,4}))\b",
    re.IGNORECASE,
)
SEMANTIC_DOB_LABEL_RE = re.compile(
    r"(?:^|[;\n])\s*(?i:(?:DOB|D\.O\.B\.|date\s+of\s+birth|birth\s*date|patient\s+DOB|"
    r"client\s+DOB|born|出生日期|生年月日|생년월일|วันเกิด|tanggal\s+lahir|ngày\s+sinh|تاريخ\s+الميلاد))"
    r"\s*(?:[:：=]|\bis\b|\bwas\b|\brecorded\s+as\b|\blisted\s+as\b|\bnoted\s+as\b)\s*(?P<dob>"
    + _DOB_DATE_FRAGMENT
    + r")\b",
    re.IGNORECASE,
)
SEMANTIC_AGE_LABEL_RE = re.compile(
    r"(?:^|[;\n])\s*(?i:(?:(?:patient|client|employee|applicant|customer|data\s+subject|subject)\s+age|"
    r"age|年齢|年龄|年齡|나이|อายุ|umur|tuổi|العمر))"
    r"\s*(?:[:：=]|\bis\b|\bwas\b|\brecorded\s+as\b|\blisted\s+as\b|\bnoted\s+as\b)\s*(?P<age>\d{1,3})\b",
    re.IGNORECASE,
)


def _enabled() -> bool:
    return os.environ.get("KAYPOH_SEMANTIC_PII_FALLBACK", "").strip().casefold() in {"1", "true", "yes", "on"}


def _valid_dob_date(value: str) -> bool:
    value = str(value or "").strip()
    formats = ("%Y-%m-%d", "%d %B %Y", "%d %b %Y", "%B %d %Y", "%B %d, %Y", "%b %d %Y", "%b %d, %Y")
    for fmt in formats:
        try:
            parsed = dt.datetime.strptime(value, fmt).date()
            return 1900 <= parsed.year <= 2100
        except ValueError:
            continue
    slash = re.fullmatch(r"\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s*", value)
    if not slash:
        return False
    first, second, year = int(slash.group(1)), int(slash.group(2)), int(slash.group(3))
    if year < 100:
        year += 2000 if year <= 30 else 1900
    for month, day in ((first, second), (second, first)):
        try:
            parsed = dt.date(year, month, day)
            return 1900 <= parsed.year <= 2100
        except ValueError:
            continue
    return False


def detect_semantic_pii_fallback_findings(
    ctx: DetectorContext,
    idx_start: int,
    new_finding: Callable[..., Any],
) -> list[Any]:
    if not _enabled():
        return []
    out: list[Any] = []
    idx = idx_start
    seen: set[tuple[int, int]] = set()
    for match in SEMANTIC_NAME_LABEL_RE.finditer(ctx.text):
        span = match.span("name")
        if span in seen:
            continue
        seen.add(span)
        out.append(
            new_finding(
                idx=idx,
                category="PII",
                rule="named_person",
                jurisdiction=ctx.jurisdiction,
                severity="low",
                matched_text=match.group("name"),
                start=span[0],
                end=span[1],
                reason="Label-anchored semantic personal-name fallback",
                legal_basis=ctx.legal_basis,
                metadata={"fallback": "semantic_label_anchor", "source": "KAYPOH_SEMANTIC_PII_FALLBACK"},
            )
        )
        idx += 1
    for match in SEMANTIC_DOB_LABEL_RE.finditer(ctx.text):
        value = match.group("dob")
        if not _valid_dob_date(value):
            continue
        span = match.span("dob")
        if span in seen:
            continue
        seen.add(span)
        out.append(
            new_finding(
                idx=idx,
                category="PII",
                rule="date_of_birth",
                jurisdiction=ctx.jurisdiction,
                severity="high",
                matched_text=value,
                start=span[0],
                end=span[1],
                reason="Label-anchored semantic date-of-birth fallback",
                legal_basis=ctx.legal_basis,
                metadata={"fallback": "semantic_label_anchor", "source": "KAYPOH_SEMANTIC_PII_FALLBACK"},
            )
        )
        idx += 1
    for match in SEMANTIC_AGE_LABEL_RE.finditer(ctx.text):
        try:
            age = int(match.group("age"))
        except ValueError:
            continue
        if not 18 <= age <= 120:
            continue
        span = match.span("age")
        if span in seen:
            continue
        seen.add(span)
        out.append(
            new_finding(
                idx=idx,
                category="PII",
                rule="age_reference",
                jurisdiction=ctx.jurisdiction,
                severity="medium",
                matched_text=match.group("age"),
                start=span[0],
                end=span[1],
                reason="Label-anchored semantic age fallback",
                legal_basis=ctx.legal_basis,
                metadata={"fallback": "semantic_label_anchor", "source": "KAYPOH_SEMANTIC_PII_FALLBACK"},
            )
        )
        idx += 1
    return out
