from __future__ import annotations

import re
from typing import Any, Callable

from kaypoh.review.detectors.registry import DetectorContext

UK_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,4}[A-Z]?\s+[A-Z][A-Za-z' -]{2,40}\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Close|Drive|Dr|Way|Court|Ct|"
    r"Square|Sq|High\s+Street),?\s+(?:[A-Z][A-Za-z' -]{2,40},?\s+)?"
    r"[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}\b",
    re.IGNORECASE,
)
US_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,6}\s+[A-Z][A-Za-z0-9' -]{2,50}\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd|Lane|Ln|Drive|Dr|Court|Ct|"
    r"Way|Circle|Cir|Place|Pl),?\s+(?:[A-Z][A-Za-z' -]{2,50},?\s+)?"
    r"(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|"
    r"MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|"
    r"VA|WA|WV|WI|WY)\s+\d{5}(?:-\d{4})?\b",
)
HK_ADDRESS_SIGNAL_RE = re.compile(
    r"\b(?:Flat|Room|Rm|Unit)\s+[A-Z0-9-]{1,8},?\s+"
    r"(?:\d{1,3}(?:st|nd|rd|th)?\s+Floor|[A-Z0-9-]{1,8}/F),?\s+"
    r"[A-Z][A-Za-z0-9' &.-]{2,60},?\s+"
    r"(?:Hong\s+Kong|Kowloon|New\s+Territories|HK)\b",
    re.IGNORECASE,
)
AU_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9' -]{2,50}\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Court|Ct|Way|Place|Pl),?\s+"
    r"[A-Z][A-Za-z' -]{2,40}\s+(?:ACT|NSW|NT|QLD|SA|TAS|VIC|WA)\s+\d{4}\b"
)
JP_POSTAL_ADDRESS_RE = re.compile(
    r"(?:〒\s*)?\d{3}-\d{4}\s*(?:東京都|北海道|大阪府|京都府|.{2,3}県)[^\n]{2,80}"
)
KR_POSTAL_ADDRESS_RE = re.compile(
    r"\b(?P<postal>\d{5})\s+(?:서울|부산|대구|인천|광주|대전|울산|세종|경기|강원|충북|충남|전북|전남|경북|경남|제주|"
    r"Seoul|Busan|Daegu|Incheon|Gwangju|Daejeon|Ulsan|Sejong|Gyeonggi|Gangwon|Jeju)"
    r"[^\n]{0,80}(?:로|길|동|구|시|군|Road|ro|gil|dong|gu|si)\b",
    re.IGNORECASE,
)
EU_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+(?:"
    r"(?:Stra(?:ss|ß)e|Str\.|Rue|Avenue|Via|Calle|Rua|Ulica|ul\.|Gasse|Laan|Weg|"
    r"Strada|Street|Katu|Tie|Vej|Gade|N(?:á|a)m(?:ě|e)st(?:í|i))\s+"
    r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ' -]{2,50}|"
    r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ' -]{2,50}\s+(?:Stra(?:ss|ß)e|Str\.|Rue|Avenue|Via|Calle|Rua|"
    r"Ulica|ul\.|Gasse|Laan|Weg|Strada|Street|Katu|Tie|Vej|Gade|N(?:á|a)m(?:ě|e)st(?:í|i))"
    r"),?\s+"
    r"[A-Z][A-Za-zÀ-ÖØ-öø-ÿ' -]{2,40},?\s+"
    r"(?:AT|BE|CZ|DE|DK|ES|FI|FR|IE|IT|NL|PL|PT|RO|SE|SK)\s*[- ]?\d{4,6}\b",
    re.IGNORECASE,
)


def detect_address_findings(
    ctx: DetectorContext,
    idx_start: int,
    new_finding: Callable[..., Any],
) -> list[Any]:
    address_patterns: list[tuple[str, re.Pattern[str], str]] = []
    pack_codes = {pack.code for pack in ctx.packs}
    if "UK" in pack_codes:
        address_patterns.append(("uk_postal_address", UK_POSTAL_ADDRESS_RE, "UK postcode-address signal"))
    if "US" in pack_codes:
        address_patterns.append(("us_postal_address", US_POSTAL_ADDRESS_RE, "US street-address signal"))
    if "HK" in pack_codes:
        address_patterns.append(("hk_postal_address", HK_ADDRESS_SIGNAL_RE, "Hong Kong address signal"))
    if "AU" in pack_codes:
        address_patterns.append(("au_postal_address", AU_POSTAL_ADDRESS_RE, "Australia street/postcode address signal"))
    if "JP" in pack_codes:
        address_patterns.append(("jp_postal_address", JP_POSTAL_ADDRESS_RE, "Japan postcode-address signal"))
    if "KR" in pack_codes:
        address_patterns.append(("kr_postal_address", KR_POSTAL_ADDRESS_RE, "Korea postcode-address signal"))
    if "EU" in pack_codes:
        address_patterns.append(("eu_postal_address", EU_POSTAL_ADDRESS_RE, "EU street/postcode address signal"))

    out: list[Any] = []
    seen: set[tuple[str, int, int]] = set()
    idx = idx_start
    for rule, pattern, reason in address_patterns:
        for match in pattern.finditer(ctx.text):
            key = (rule, match.start(), match.end())
            if key in seen:
                continue
            seen.add(key)
            out.append(
                new_finding(
                    idx=idx,
                    category="PII",
                    rule=rule,
                    jurisdiction=ctx.jurisdiction,
                    severity="medium",
                    matched_text=match.group(0),
                    start=match.start(),
                    end=match.end(),
                    reason=reason,
                    legal_basis=ctx.legal_basis,
                )
            )
            idx += 1
    return out
