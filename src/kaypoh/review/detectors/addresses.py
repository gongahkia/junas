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
MY_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+(?:Jalan|Lorong|Persiaran|Lebuh|Taman)\s+[A-Z][A-Za-z0-9' -]{2,60},?\s+"
    r"(?:[A-Z][A-Za-z' -]{2,40},?\s+)?\d{5}\s+(?:Kuala\s+Lumpur|Selangor|Johor|Penang|Malaysia)\b",
    re.IGNORECASE,
)
ID_POSTAL_ADDRESS_RE = re.compile(
    r"\b(?:Jl\.?|Jalan)\s+[A-Z][A-Za-z0-9' .-]{2,60}\s+(?:No\.?\s*)?\d{1,5},?\s+"
    r"(?:[A-Z][A-Za-z' -]{2,40},?\s+)?(?:Jakarta|Surabaya|Bandung|Indonesia)\s+\d{5}\b",
    re.IGNORECASE,
)
TH_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9' -]{2,60}\s+(?:Road|Rd|Soi),?\s+"
    r"(?:[A-Z][A-Za-z' -]{2,40},?\s+)?(?:Bangkok|Phuket|Chiang\s+Mai|Thailand)\s+\d{5}\b",
    re.IGNORECASE,
)
PH_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9' -]{2,60}\s+"
    r"(?:Street|St|Road|Rd|Avenue|Ave|Boulevard|Blvd),?\s+"
    r"(?:Makati|Taguig|Quezon\s+City|Manila|Cebu|Philippines)\s+\d{4}\b",
    re.IGNORECASE,
)
VN_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9' -]{2,60}\s+(?:Street|St|Road|Rd|Đường),?\s+"
    r"(?:District\s+\d{1,2},?\s+)?(?:Ho\s+Chi\s+Minh\s+City|Hanoi|Da\s+Nang|Vietnam)\s+\d{5,6}\b",
    re.IGNORECASE,
)
IN_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9' -]{2,60}\s+(?:Road|Rd|Street|St|Marg|Nagar),?\s+"
    r"(?:[A-Z][A-Za-z' -]{2,40},?\s+)?(?:IN-)?\d{6}\s+(?:India|Mumbai|Delhi|Bengaluru|Chennai)\b",
    re.IGNORECASE,
)
CN_POSTAL_ADDRESS_RE = re.compile(
    r"(?:\b\d{6}\s*(?:北京市|上海市|深圳市|广州市|杭州市)[^\n]{2,80}(?:路|街|号)|"
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9' -]{2,60}\s+(?:Road|Rd|Street|St),?\s+"
    r"(?:Beijing|Shanghai|Shenzhen|Guangzhou|China)\s+\d{6}\b)",
    re.IGNORECASE,
)
AE_POSTAL_ADDRESS_RE = re.compile(
    r"\b(?:Office|Unit|Flat|Suite)\s+[A-Z0-9-]{1,8},?\s+"
    r"[A-Z][A-Za-z0-9' -]{2,60}\s+(?:Road|Rd|Street|St),?\s+"
    r"(?:Dubai|Abu\s+Dhabi|Sharjah|UAE|United\s+Arab\s+Emirates)\b",
    re.IGNORECASE,
)
SA_POSTAL_ADDRESS_RE = re.compile(
    r"\b\d{1,5}\s+[A-Z][A-Za-z0-9' -]{2,60}\s+(?:Road|Rd|Street|St),?\s+"
    r"(?:Riyadh|Jeddah|Dammam|Saudi\s+Arabia)\s+\d{5}(?:-\d{4})?\b",
    re.IGNORECASE,
)
GENERIC_ADDRESS_LABEL_RE = re.compile(
    r"(?im)(?:^|[;\n])\s*(?P<label>residential\s+address|mailing\s+address|registered\s+address|"
    r"home\s+address|office\s+address|billing\s+address|delivery\s+address|service\s+address|"
    r"notice\s+address|signatory\s+address|invoice\s+address|address|住所|주소|地址|alamat|"
    r"địa\s+chỉ|ที่อยู่|عنوان)"
    r"\s*[:：]\s*(?P<value>[^\n]{6,160}(?:\n(?!\s*[A-Za-z][A-Za-z ]{0,40}\s*[:：])"
    r"[^\n]{6,160}){0,2})",
    re.IGNORECASE,
)
GENERIC_ADDRESS_SUBSTANCE_RE = re.compile(
    r"\b(?:Street|St|Road|Rd|Avenue|Ave|Lane|Ln|Drive|Dr|Boulevard|Blvd|Court|Ct|"
    r"Way|Place|Pl|Square|Sq|Close|High\s+Street|Block|Blk|Unit|Suite|Apt|Apartment|"
    r"Floor|Tower|Building|Jalan|Lorong|Kampong|Barangay|Brgy|Makati|Quezon|〒|丁目|"
    r"番地|号|都|府|県|市|区|町|村|路|街|道|號|楼|室|구|동|로|길|시|군|شارع|طريق|"
    r"ถนน|แขวง|เขต)\b",
    re.IGNORECASE,
)
GENERIC_ADDRESS_POSTCODE_RE = re.compile(
    r"\b(?:[A-Z]{1,2}\d[A-Z\d]?\s*\d[A-Z]{2}|\d{3}-\d{4}|\d{4,6}(?:-\d{4})?)\b",
    re.IGNORECASE,
)
GENERIC_ADDRESS_LOCALITY_RE = re.compile(
    r"\b(?:Singapore|Hong\s+Kong|Kowloon|Malaysia|Indonesia|Thailand|Philippines|Vietnam|India|China|"
    r"Australia|Japan|Korea|United\s+Kingdom|United\s+States|UAE|Saudi\s+Arabia|Dubai|Abu\s+Dhabi|"
    r"Riyadh|Jeddah|Mumbai|Delhi|Beijing|Shanghai|Bangkok|Jakarta|Manila|Hanoi|Ho\s+Chi\s+Minh|"
    r"Sydney|Melbourne|Tokyo|Seoul|London|New\s+York|California)\b",
    re.IGNORECASE,
)
BROAD_ADDRESS_ADMIN_RE = re.compile(
    r"\b(?:ACT|NSW|NT|QLD|SA|TAS|VIC|WA|AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|"
    r"LA|ME|MD|MA|MI|MN|MS|MO|MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|"
    r"VT|VA|WA|WV|WI|WY|東京都|北海道|大阪府|京都府|.{2,3}県|서울|부산|대구|인천|경기|"
    r"AT|BE|CZ|DE|DK|ES|FI|FR|IE|IT|NL|PL|PT|RO|SE|SK)\b",
)
PERSON_LINKED_ADDRESS_RE = re.compile(
    r"\b(?:Mr|Ms|Mrs|Mdm|Dr|Prof|employee|patient|client|customer|resident|applicant|data\s+subject|"
    r"home|residential|private|personal)\b",
    re.IGNORECASE,
)
ORG_ONLY_ADDRESS_RE = re.compile(
    r"\b(?:registered\s+office|corporate\s+office|head\s+office|principal\s+place\s+of\s+business|"
    r"company\s+address|organisation|organization)\b",
    re.IGNORECASE,
)


def _overlaps(span: tuple[int, int], ranges: list[tuple[int, int]]) -> bool:
    start, end = span
    return any(start < other_end and end > other_start for other_start, other_end in ranges)


def _trim_address_value(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start] in " \t\r\n":
        start += 1
    while end > start and text[end - 1] in " \t\r\n.;":
        end -= 1
    return start, end


def _has_generic_address_substance(value: str) -> bool:
    if not any(ch.isdigit() for ch in value):
        return False
    if GENERIC_ADDRESS_SUBSTANCE_RE.search(value):
        return bool(
            GENERIC_ADDRESS_POSTCODE_RE.search(value)
            or GENERIC_ADDRESS_LOCALITY_RE.search(value)
            or BROAD_ADDRESS_ADMIN_RE.search(value)
        )
    return bool(GENERIC_ADDRESS_POSTCODE_RE.search(value) and GENERIC_ADDRESS_LOCALITY_RE.search(value))


def _line_windows(text: str) -> list[tuple[int, int, str]]:
    lines: list[tuple[int, int, str]] = []
    offset = 0
    for raw in text.splitlines(keepends=True):
        start = offset
        end = offset + len(raw)
        content_end = end - (len(raw) - len(raw.rstrip("\r\n")))
        stripped_start = start + (len(raw[: content_end - start]) - len(raw[: content_end - start].lstrip()))
        lines.append((stripped_start, content_end, text[stripped_start:content_end]))
        offset = end
    windows: list[tuple[int, int, str]] = []
    for index, (start, end, value) in enumerate(lines):
        if not value.strip():
            continue
        window_start, window_end = start, end
        parts = [value]
        for follow_start, follow_end, follow_value in lines[index + 1 : index + 3]:
            if not follow_value.strip():
                break
            if re.match(r"\s*[A-Za-z][A-Za-z ]{0,40}\s*[:：]", follow_value):
                break
            window_end = follow_end
            parts.append(follow_value)
        windows.append((window_start, window_end, "\n".join(part.strip() for part in parts if part.strip())))
    return windows


def _line_context(text: str, start: int, end: int) -> str:
    left = text.rfind("\n", 0, start) + 1
    right = text.find("\n", end)
    if right < 0:
        right = len(text)
    return text[left:right].strip()


def _looks_org_only_address(value: str) -> bool:
    return bool(ORG_ONLY_ADDRESS_RE.search(value) and not PERSON_LINKED_ADDRESS_RE.search(value))


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
    if "MY" in pack_codes:
        address_patterns.append(("my_postal_address", MY_POSTAL_ADDRESS_RE, "Malaysia street/postcode address signal"))
    if "ID" in pack_codes:
        address_patterns.append(("id_postal_address", ID_POSTAL_ADDRESS_RE, "Indonesia street/postcode address signal"))
    if "TH" in pack_codes:
        address_patterns.append(("th_postal_address", TH_POSTAL_ADDRESS_RE, "Thailand street/postcode address signal"))
    if "PH" in pack_codes:
        address_patterns.append(("ph_postal_address", PH_POSTAL_ADDRESS_RE, "Philippines street/postcode address signal"))
    if "VN" in pack_codes:
        address_patterns.append(("vn_postal_address", VN_POSTAL_ADDRESS_RE, "Vietnam street/postcode address signal"))
    if "IN" in pack_codes:
        address_patterns.append(("in_postal_address", IN_POSTAL_ADDRESS_RE, "India street/postcode address signal"))
    if "CN" in pack_codes:
        address_patterns.append(("cn_postal_address", CN_POSTAL_ADDRESS_RE, "China street/postcode address signal"))
    if "AE" in pack_codes:
        address_patterns.append(("ae_postal_address", AE_POSTAL_ADDRESS_RE, "UAE address signal"))
    if "SA" in pack_codes:
        address_patterns.append(("sa_postal_address", SA_POSTAL_ADDRESS_RE, "Saudi Arabia street/postcode address signal"))

    out: list[Any] = []
    seen: set[tuple[str, int, int]] = set()
    occupied: list[tuple[int, int]] = []
    idx = idx_start
    for rule, pattern, reason in address_patterns:
        for match in pattern.finditer(ctx.text):
            key = (rule, match.start(), match.end())
            if key in seen:
                continue
            if _looks_org_only_address(_line_context(ctx.text, match.start(), match.end())):
                continue
            seen.add(key)
            occupied.append((match.start(), match.end()))
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
    for match in GENERIC_ADDRESS_LABEL_RE.finditer(ctx.text):
        start, end = _trim_address_value(ctx.text, *match.span("value"))
        if end <= start or _overlaps((start, end), occupied):
            continue
        value = ctx.text[start:end]
        if not _has_generic_address_substance(value):
            continue
        key = ("postal_address", start, end)
        if key in seen:
            continue
        seen.add(key)
        occupied.append((start, end))
        out.append(
            new_finding(
                idx=idx,
                category="PII",
                rule="postal_address",
                jurisdiction=ctx.jurisdiction,
                severity="medium",
                matched_text=value,
                start=start,
                end=end,
                reason="Label-anchored postal-address signal",
                legal_basis=ctx.legal_basis,
                metadata={"fallback": "label_anchored_postal_address"},
            )
        )
        idx += 1
    for start, end, value in _line_windows(ctx.text):
        start, end = _trim_address_value(ctx.text, start, end)
        if end <= start or _overlaps((start, end), occupied):
            continue
        value = ctx.text[start:end].strip()
        lines = value.splitlines()
        first_line = lines[0] if lines else value
        if not PERSON_LINKED_ADDRESS_RE.search(first_line):
            continue
        candidate_start, candidate_end, candidate_value = start, end, value
        if len(lines) > 1 and not _has_generic_address_substance(first_line):
            tail_match = re.search(r"\r?\n[ \t]*(?P<tail>\S.*)", value, re.DOTALL)
            if tail_match:
                tail_value = tail_match.group("tail").strip()
                if _has_generic_address_substance(tail_value):
                    candidate_start = start + tail_match.start("tail")
                    candidate_end = candidate_start + len(tail_value)
                    candidate_start, candidate_end = _trim_address_value(ctx.text, candidate_start, candidate_end)
                    candidate_value = ctx.text[candidate_start:candidate_end]
        candidate_lines = candidate_value.splitlines()
        if "\n" in candidate_value and not any(ch.isdigit() for ch in "\n".join(candidate_lines[1:])):
            continue
        if _looks_org_only_address(candidate_value):
            continue
        if not _has_generic_address_substance(candidate_value):
            continue
        key = ("postal_address", candidate_start, candidate_end)
        if key in seen:
            continue
        seen.add(key)
        occupied.append((candidate_start, candidate_end))
        out.append(
            new_finding(
                idx=idx,
                category="PII",
                rule="postal_address",
                jurisdiction=ctx.jurisdiction,
                severity="medium",
                matched_text=candidate_value,
                start=candidate_start,
                end=candidate_end,
                reason="Broad unlabelled postal-address signal",
                legal_basis=ctx.legal_basis,
                metadata={"fallback": "broad_unlabelled_postal_address"},
            )
        )
        idx += 1
    return out
