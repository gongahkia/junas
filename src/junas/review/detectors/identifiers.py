from __future__ import annotations

import datetime as dt
import ipaddress
import re
from typing import Any, Callable

from junas.review.detectors.registry import DetectorContext

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
DATE_OF_BIRTH_RE = re.compile(
    r"(?:\b(?:DOB|D\.O\.B\.|date\s+of\s+birth|birth\s*date|birthday|born(?:\s+on)?)|"
    r"出生日期|생년월일)\s*[:#=\-]?\s*("
    + _DOB_DATE_FRAGMENT
    + r")\b",
    re.IGNORECASE,
)
AGE_FIELD_RE = re.compile(
    r"\b(?:"
    r"(?:age\s+at\s+(?:intake|onboarding|screening)|current\s+age|age)\s*[:=]\s*(?P<age_field>\d{1,3})|"
    r"(?:aged|turns?|turning)\s+(?P<age_turns>\d{1,3})|"
    r"(?:client|employee|patient|applicant|customer|data\s+subject|subject)\s+"
    r"(?:is\s+)?(?P<age_years>\d{2,3})\s+years?\s+old"
    r")\b",
    re.IGNORECASE,
)
IPV4_CONTEXT_RE = re.compile(
    r"\b(?:IP(?:v4)?\s+address|source\s+IP|client\s+IP|remote\s+IP|login\s+IP|last\s+IP|"
    r"x-forwarded-for)\s*[:=]?\s*((?:\d{1,3}\.){3}\d{1,3})\b",
    re.IGNORECASE,
)
IPV6_CONTEXT_RE = re.compile(
    r"\b(?:IPv6\s+address|source\s+IPv6|client\s+IPv6|remote\s+IPv6|login\s+IPv6|"
    r"IP\s+address)\s*[:=]?\s*([0-9A-Fa-f:]{2,39})\b",
    re.IGNORECASE,
)
MAC_ADDRESS_RE = re.compile(
    r"\b(?:MAC\s+address|device\s+MAC|Wi-?Fi\s+MAC|BSSID)\s*[:=]?\s*"
    r"((?:[0-9A-Fa-f]{2}[:-]){5}[0-9A-Fa-f]{2})\b",
    re.IGNORECASE,
)
IMEI_RE = re.compile(r"\b(?:IMEI|device\s+IMEI)\s*[:#=\-]?\s*(\d(?:[\s-]?\d){14})\b", re.IGNORECASE)
COOKIE_ID_RE = re.compile(
    r"\b(?:cookie(?:\s+id)?|session\s+cookie|browser\s+cookie)\s*[:#=]\s*"
    r"([A-Za-z0-9][A-Za-z0-9._~-]{11,127})\b",
    re.IGNORECASE,
)
ADVERTISING_ID_RE = re.compile(
    r"\b(?:IDFA|GAID|AAID|advertising\s+ID|ad\s+ID|mobile\s+ad\s+ID)\s*[:#=]\s*"
    r"([0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[1-5][0-9a-fA-F]{3}-[89abAB][0-9a-fA-F]{3}-"
    r"[0-9a-fA-F]{12})\b",
    re.IGNORECASE,
)
DEVICE_SERIAL_RE = re.compile(
    r"\b(?:device|hardware|laptop|mobile|phone|tablet)\s+"
    r"(?:serial(?:\s+number)?|S/N|SN)\s*[:#=]?\s*([A-Z0-9][A-Z0-9-]{5,31})\b",
    re.IGNORECASE,
)
EU_NATIONAL_ID_RE = re.compile(
    r"\b(?P<country>DE|FR|ES|IT|NL|BE|PL|SE|IE|AT|PT|DK|FI|CZ|SK|RO)\s+"
    r"(?:national\s+ID|identity\s+(?:card|number)|personal\s+ID|personnummer|"
    r"DNI|NIE|NIF|codice\s+fiscale|BSN|PESEL|PPSN|CPR|HETU|SVNR|CNP|birth\s+number|"
    r"tax\s+ID|TIN)\s*[:#=\-]?\s*"
    r"(?P<id>(?-i:[A-Z0-9][A-Z0-9 ./-]{5,31}[A-Z0-9]))\b",
    re.IGNORECASE,
)
EU_MEMBER_STATE_ID_RE = re.compile(
    r"\b(?P<label>"
    r"(?:Spain|Spanish|ES)\s+(?:DNI|NIE|NIF|national\s+ID)|"
    r"(?:Netherlands|Dutch|NL)\s+(?:BSN|citizen\s+service\s+number|national\s+ID)|"
    r"(?:Poland|Polish|PL)\s+(?:PESEL|national\s+ID)|"
    r"(?:France|French|FR)\s+(?:INSEE|NIR|social\s+security\s+number|national\s+ID)|"
    r"(?:Germany|German|DE)\s+(?:tax\s+ID|TIN|Steueridentifikationsnummer|national\s+ID)|"
    r"(?:Italy|Italian|IT)\s+(?:codice\s+fiscale|tax\s+code|national\s+ID)|"
    r"(?:Belgium|Belgian|BE)\s+(?:national\s+number|rijksregisternummer|num[eé]ro\s+national)|"
    r"(?:Portugal|Portuguese|PT)\s+(?:NIF|tax\s+number|national\s+ID)|"
    r"(?:Sweden|Swedish|SE)\s+(?:personnummer|personal\s+identity\s+number|national\s+ID)|"
    r"(?:Finland|Finnish|FI)\s+(?:HETU|personal\s+identity\s+code|national\s+ID)|"
    r"(?:Ireland|Irish|IE)\s+(?:PPSN|personal\s+public\s+service\s+number|national\s+ID)|"
    r"(?:Austria|Austrian|AT)\s+(?:SVNR|social\s+security\s+number|national\s+ID)|"
    r"(?:Denmark|Danish|DK)\s+(?:CPR|civil\s+registration\s+number|personal\s+identification\s+number|national\s+ID)|"
    r"(?:Czechia|Czech|CZ)\s+(?:birth\s+number|rodn[eé]\s+č[ií]slo|national\s+ID)|"
    r"(?:Slovakia|Slovak|SK)\s+(?:birth\s+number|rodn[eé]\s+č[ií]slo|national\s+ID)|"
    r"(?:Romania|Romanian|RO)\s+(?:CNP|personal\s+numeric\s+code|national\s+ID)"
    r")\s*[:#=\-]?\s*(?P<id>(?-i:[A-Z0-9][A-Z0-9 ./-]{6,31}[A-Z0-9]))\b",
    re.IGNORECASE,
)
UK_COMPANY_NUMBER_RE = re.compile(
    r"\b(?:company\s+(?:number|no\.?|registration\s+(?:number|no\.?)|registered\s+number)|"
    r"Companies\s+House\s+(?:number|no\.?)|CRN)\s*[:#=\-]?\s*"
    r"(?P<number>(?-i:(?:\d{8}|(?:AC|CE|FC|GE|GS|IC|IP|LP|NA|NC|NF|NI|NL|NO|NP|NR|NV|OC|"
    r"RC|R0|SA|SC|SE|SF|SI|SL|SO|SP|SR|SZ|ZC)\d{6})))\b",
    re.IGNORECASE,
)
EU_COMPANY_ID_RE = re.compile(
    r"\b(?:EU\s+)?(?:VAT(?:\s+(?:ID|number|no\.?|registration))?|VATIN|USt[- ]?IdNr\.?|"
    r"BTW(?:[- ]?nummer)?|TVA|IVA|Partita\s+IVA|NIF|NIPC|company\s+(?:VAT|tax|registration)\s+"
    r"(?:ID|number|no\.?))\s*[:#=\-]?\s*"
    r"(?P<id>(?-i:(?:ATU\d{8}|BE0?\d{9}|BG\d{9,10}|CY\d{8}[A-Z]|CZ\d{8,10}|"
    r"DE\d{9}|DK\d{8}|EE\d{9}|EL\d{9}|ES[A-Z0-9]\d{7}[A-Z0-9]|FI\d{8}|"
    r"FR[A-Z0-9]{2}\d{9}|HR\d{11}|HU\d{8}|IE\d{7}[A-Z]{1,2}|IT\d{11}|"
    r"LT\d{9}(?:\d{3})?|LU\d{8}|LV\d{11}|MT\d{8}|NL\d{9}B\d{2}|PL\d{10}|"
    r"PT\d{9}|RO\d{2,10}|SE\d{12}|SI\d{8}|SK\d{10})))\b",
    re.IGNORECASE,
)
_US_STATE_NAME_TO_CODE = {
    "ALABAMA": "AL", "ALASKA": "AK", "ARIZONA": "AZ", "ARKANSAS": "AR", "CALIFORNIA": "CA",
    "COLORADO": "CO", "CONNECTICUT": "CT", "DELAWARE": "DE", "FLORIDA": "FL", "GEORGIA": "GA",
    "HAWAII": "HI", "IDAHO": "ID", "ILLINOIS": "IL", "INDIANA": "IN", "IOWA": "IA",
    "KANSAS": "KS", "KENTUCKY": "KY", "LOUISIANA": "LA", "MAINE": "ME", "MARYLAND": "MD",
    "MASSACHUSETTS": "MA", "MICHIGAN": "MI", "MINNESOTA": "MN", "MISSISSIPPI": "MS",
    "MISSOURI": "MO", "MONTANA": "MT", "NEBRASKA": "NE", "NEVADA": "NV", "NEW HAMPSHIRE": "NH",
    "NEW JERSEY": "NJ", "NEW MEXICO": "NM", "NEW YORK": "NY", "NORTH CAROLINA": "NC",
    "NORTH DAKOTA": "ND", "OHIO": "OH", "OKLAHOMA": "OK", "OREGON": "OR", "PENNSYLVANIA": "PA",
    "RHODE ISLAND": "RI", "SOUTH CAROLINA": "SC", "SOUTH DAKOTA": "SD", "TENNESSEE": "TN",
    "TEXAS": "TX", "UTAH": "UT", "VERMONT": "VT", "VIRGINIA": "VA", "WASHINGTON": "WA",
    "WEST VIRGINIA": "WV", "WISCONSIN": "WI", "WYOMING": "WY",
}
_US_STATE_CODES = frozenset(_US_STATE_NAME_TO_CODE.values())
_US_STATE_TOKEN = (
    r"(?:AL|AK|AZ|AR|CA|CO|CT|DE|FL|GA|HI|ID|IL|IN|IA|KS|KY|LA|ME|MD|MA|MI|MN|MS|MO|"
    r"MT|NE|NV|NH|NJ|NM|NY|NC|ND|OH|OK|OR|PA|RI|SC|SD|TN|TX|UT|VT|VA|WA|WV|WI|WY|"
    r"Alabama|Alaska|Arizona|Arkansas|California|Colorado|Connecticut|Delaware|Florida|"
    r"Georgia|Hawaii|Idaho|Illinois|Indiana|Iowa|Kansas|Kentucky|Louisiana|Maine|Maryland|"
    r"Massachusetts|Michigan|Minnesota|Mississippi|Missouri|Montana|Nebraska|Nevada|"
    r"New\s+Hampshire|New\s+Jersey|New\s+Mexico|New\s+York|North\s+Carolina|North\s+Dakota|"
    r"Ohio|Oklahoma|Oregon|Pennsylvania|Rhode\s+Island|South\s+Carolina|South\s+Dakota|"
    r"Tennessee|Texas|Utah|Vermont|Virginia|Washington|West\s+Virginia|Wisconsin|Wyoming)"
)
_US_DRIVER_LICENSE_RE = re.compile(
    r"\b(?:(?P<state>" + _US_STATE_TOKEN + r")\s+)?"
    r"(?:driver'?s?\s+licen[cs]e|driver\s+licen[cs]e\s+number|DLN|DL\s*#|D/L|"
    r"licen[cs]e\s+(?:no\.?|number))\s*[:#=\-]?\s*(?P<number>[A-Z0-9*][A-Z0-9*\-]{3,19})\b",
    re.IGNORECASE,
)
_US_DRIVER_LICENSE_ANY_RE = re.compile(
    r"\b(?:driver'?s?\s+licen[cs]e|driver\s+licen[cs]e\s+number|DLN|DL\s*#|D/L|"
    r"licen[cs]e\s+(?:no\.?|number))\s*[:#=\-]?\s*(?P<number>[A-Z0-9*][A-Z0-9*\-]{3,19})"
    r"(?=$|\s|[.,;:)])",
    re.IGNORECASE,
)
_US_STATE_CONTEXT_RE = re.compile(
    r"\b(?:state|issuing\s+state|state\s+of\s+issue|issuer)\s*[:=]?\s*"
    r"([A-Z]{2}|[A-Za-z]+(?:\s+[A-Za-z]+)?)\b",
    re.IGNORECASE,
)
_US_DRIVER_LICENSE_PATTERNS: dict[str, str] = {
    "AL": r"\d{7,8}", "AK": r"\d{7}", "AZ": r"(?:[A-Z]\d{8}|\d{9})", "AR": r"\d{4,9}",
    "CA": r"[A-Z]\d{7}", "CO": r"(?:\d{9}|[A-Z]\d{3,6})", "CT": r"\d{9}", "DE": r"\d{1,7}",
    "FL": r"[A-Z]\d{12}", "GA": r"\d{7,9}", "HI": r"(?:[A-Z]\d{8}|\d{9})",
    "ID": r"(?:[A-Z]{2}\d{6}[A-Z]|\d{9})", "IL": r"[A-Z]\d{11,12}",
    "IN": r"(?:[A-Z]\d{9}|\d{9,10})", "IA": r"(?:\d{3}[A-Z]{2}\d{4}|\d{9})",
    "KS": r"(?:[A-Z]\d{8}|\d{9})", "KY": r"(?:[A-Z]\d{8}|\d{9})", "LA": r"\d{1,9}",
    "ME": r"\d{7,8}", "MD": r"[A-Z]\d{12}", "MA": r"(?:[A-Z]\d{8}|\d{9})",
    "MI": r"[A-Z]\d{12}", "MN": r"[A-Z]\d{12}", "MS": r"\d{9}",
    "MO": r"(?:[A-Z]\d{5,9}|\d{9})", "MT": r"(?:\d{13}|\d{9})", "NE": r"[A-Z]\d{6,8}",
    "NV": r"(?:\d{9,10}|X\d{8})", "NH": r"\d{2}[A-Z]{3}\d{5}", "NJ": r"[A-Z]\d{14}",
    "NM": r"\d{8,9}", "NY": r"(?:\d{9}|[A-Z]\d{7})", "NC": r"\d{1,12}",
    "ND": r"(?:[A-Z]{3}\d{6}|\d{9})", "OH": r"(?:[A-Z]{2}\d{6}|\d{8})",
    "OK": r"(?:[A-Z]\d{9}|\d{9})", "OR": r"\d{1,9}", "PA": r"\d{8}",
    "RI": r"(?:\d{7}|V\d{6})", "SC": r"\d{5,11}", "SD": r"(?:\d{6,10}|\d{12})",
    "TN": r"\d{7,9}", "TX": r"\d{7,8}", "UT": r"\d{4,10}", "VT": r"(?:\d{8}|\d{7}A)",
    "VA": r"(?:[A-Z]\d{8,11}|\d{9})", "WA": r"[A-Z0-9*]{12}",
    "WV": r"(?:[A-Z]\d{6}|\d{7})", "WI": r"[A-Z]\d{13}", "WY": r"\d{9,10}",
}
SG_INSURANCE_POLICY_RE = re.compile(
    r"\b(?:insurance\s+)?(?:policy|certificate|claim)\s+(?:no\.?|number|ref(?:erence)?)\s*[:#=\-]?\s*"
    r"([A-Z]{1,6}[A-Z0-9/-]{5,30})\b",
    re.IGNORECASE,
)
CRYPTO_WALLET_RE = re.compile(
    r"\b(?:crypto|digital[- ]asset|DPT|VASP|wallet|deposit|withdrawal)\s+"
    r"(?:wallet\s+)?(?:address|account|ref(?:erence)?)\s*[:#=\-]?\s*"
    r"((?:0x[a-fA-F0-9]{40}|bc1[ac-hj-np-z02-9]{25,62}|[13][a-km-zA-HJ-NP-Z1-9]{25,34}|"
    r"T[1-9A-HJ-NP-Za-km-z]{33}|[1-9A-HJ-NP-Za-km-z]{32,44}))\b",
    re.IGNORECASE,
)
SG_TRIBUNAL_REFERENCE_RE = re.compile(
    r"\b(?:(?:SCT|ECT|CDRT|STB|PDPC|IPOS)\s*(?:case|claim|complaint|dispute)?|"
    r"Small\s+Claims\s+Tribunal|Employment\s+Claims\s+Tribunal|"
    r"Community\s+Disputes\s+Resolution\s+Tribunal|Strata\s+Titles\s+Boards|"
    r"Personal\s+Data\s+Protection\s+Commission)\s+"
    r"(?:no\.?|number|ref(?:erence)?|case|claim|complaint)\s*[:#=\-]?\s*"
    r"([A-Z]{1,8}[-/ ]?\d{2,6}[-/ ]?\d{2,6}(?:[-/][A-Z0-9]{1,8})?)\b",
    re.IGNORECASE,
)
_MONTH_NAMES: dict[str, int] = {
    name: index
    for index, names in enumerate(
        (("jan", "january"), ("feb", "february"), ("mar", "march"), ("apr", "april"), ("may",),
         ("jun", "june"), ("jul", "july"), ("aug", "august"), ("sep", "sept", "september"),
         ("oct", "october"), ("nov", "november"), ("dec", "december")),
        start=1,
    )
    for name in names
}
_DATE_ISO_RE = re.compile(r"\b(\d{4})-(\d{1,2})-(\d{1,2})\b")
_DATE_DMY_NAME_RE = re.compile(r"\b(\d{1,2})\s+([A-Za-z]{3,9})\s+(\d{4})\b", re.IGNORECASE)
_DATE_MDY_NAME_RE = re.compile(r"\b([A-Za-z]{3,9})\s+(\d{1,2}),?\s+(\d{4})\b", re.IGNORECASE)
_DATE_DMY_SLASH_RE = re.compile(r"\b(\d{1,2})/(\d{1,2})/(\d{4})\b")


def _digits_only(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _parse_date(text: str) -> tuple[int, int, int] | None:
    text = text.strip()
    m = _DATE_ISO_RE.search(text)
    if m:
        try:
            dt.date(int(m.group(1)), int(m.group(2)), int(m.group(3)))
            return int(m.group(1)), int(m.group(2)), int(m.group(3))
        except ValueError:
            pass
    m = _DATE_DMY_NAME_RE.search(text)
    if m:
        month = _MONTH_NAMES.get(m.group(2).lower())
        if month:
            try:
                dt.date(int(m.group(3)), month, int(m.group(1)))
                return int(m.group(3)), month, int(m.group(1))
            except ValueError:
                pass
    m = _DATE_MDY_NAME_RE.search(text)
    if m:
        month = _MONTH_NAMES.get(m.group(1).lower())
        if month:
            try:
                dt.date(int(m.group(3)), month, int(m.group(2)))
                return int(m.group(3)), month, int(m.group(2))
            except ValueError:
                pass
    m = _DATE_DMY_SLASH_RE.search(text)
    if m:
        try:
            dt.date(int(m.group(3)), int(m.group(2)), int(m.group(1)))
            return int(m.group(3)), int(m.group(2)), int(m.group(1))
        except ValueError:
            pass
    return None


def _valid_dob_date(value: str) -> bool:
    parsed = _parse_date(value)
    if parsed is None:
        slash = re.fullmatch(r"\s*(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})\s*", value)
        if slash:
            first, second, year = int(slash.group(1)), int(slash.group(2)), int(slash.group(3))
            if year < 100:
                year += 2000 if year <= 30 else 1900
            for month, day in ((first, second), (second, first)):
                try:
                    dt.date(year, month, day)
                    parsed = (year, month, day)
                    break
                except ValueError:
                    continue
    if parsed is None:
        return False
    return 1900 <= parsed[0] <= 2100


def _valid_calendar_date(year: int, month: int, day: int) -> bool:
    try:
        dt.date(year, month, day)
        return True
    except ValueError:
        return False


def _luhn_valid(digits: str) -> bool:
    if not digits or not digits.isdigit():
        return False
    total = 0
    double = False
    for char in reversed(digits):
        value = int(char)
        if double:
            value *= 2
            if value > 9:
                value -= 9
        total += value
        double = not double
    return total % 10 == 0


def _normalise_identifier_value(value: str) -> str:
    return re.sub(r"[\s./-]", "", value).upper()


def _validate_es_dni_nie(value: str) -> bool:
    compact = _normalise_identifier_value(value)
    letters = "TRWAGMYFPDXBNJZSQVHLCKE"
    if re.fullmatch(r"\d{8}[A-Z]", compact):
        return compact[-1] == letters[int(compact[:8]) % 23]
    if re.fullmatch(r"[XYZ]\d{7}[A-Z]", compact):
        prefix = {"X": "0", "Y": "1", "Z": "2"}[compact[0]]
        return compact[-1] == letters[int(prefix + compact[1:8]) % 23]
    return False


def _validate_nl_bsn(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) == 8:
        digits = "0" + digits
    if len(digits) != 9:
        return False
    weights = [9, 8, 7, 6, 5, 4, 3, 2, -1]
    return sum(int(digit) * weight for digit, weight in zip(digits, weights)) % 11 == 0


def _validate_pl_pesel(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 11:
        return False
    weights = [1, 3, 7, 9, 1, 3, 7, 9, 1, 3]
    check = (10 - sum(int(digits[i]) * weights[i] for i in range(10)) % 10) % 10
    return check == int(digits[-1])


def _validate_fr_insee(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) not in {13, 15}:
        return False
    if len(digits) == 13:
        return True
    body = int(digits[:13])
    key = int(digits[13:])
    return (97 - (body % 97)) == key


def _validate_de_tax_id(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 11 or digits[0] == "0":
        return False
    p = 10
    for char in digits[:10]:
        s = (int(char) + p) % 10
        if s == 0:
            s = 10
        p = (2 * s) % 11
    check = (11 - p) % 10
    return check == int(digits[-1])


_IT_ODD = {
    **{str(i): v for i, v in enumerate((1, 0, 5, 7, 9, 13, 15, 17, 19, 21))},
    **dict(zip(
        "ABCDEFGHIJKLMNOPQRSTUVWXYZ",
        (1, 0, 5, 7, 9, 13, 15, 17, 19, 21, 2, 4, 18, 20, 11, 3, 6, 8, 12, 14, 16, 10, 22, 25, 24, 23),
    )),
}
_IT_EVEN = {**{str(i): i for i in range(10)}, **{chr(ord("A") + i): i for i in range(26)}}


def _validate_it_codice_fiscale(value: str) -> bool:
    compact = _normalise_identifier_value(value)
    if not re.fullmatch(r"[A-Z]{6}\d{2}[A-Z]\d{2}[A-Z]\d{3}[A-Z]", compact):
        return False
    total = 0
    for pos, char in enumerate(compact[:15], start=1):
        total += _IT_ODD[char] if pos % 2 else _IT_EVEN[char]
    return chr(ord("A") + total % 26) == compact[-1]


def _validate_be_national_number(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 11:
        return False
    body = int(digits[:9])
    check = int(digits[9:])
    return check == 97 - (body % 97) or check == 97 - (int("2" + digits[:9]) % 97)


def _validate_pt_nif(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 9 or digits[0] not in "1235689":
        return False
    total = sum(int(digits[i]) * (9 - i) for i in range(8))
    check = 11 - (total % 11)
    if check >= 10:
        check = 0
    return check == int(digits[-1])


def _validate_se_personnummer(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) == 12:
        digits = digits[2:]
    return len(digits) == 10 and _luhn_valid(digits)


def _validate_fi_hetu(value: str) -> bool:
    compact = re.sub(r"\s", "", value).upper()
    match = re.fullmatch(r"(\d{2})(\d{2})(\d{2})([+\-A])(\d{3})([0-9A-Z])", compact)
    if not match:
        return False
    day, month, year = int(match.group(1)), int(match.group(2)), int(match.group(3))
    century = {"+": 1800, "-": 1900, "A": 2000}[match.group(4)]
    if not _valid_calendar_date(century + year, month, day):
        return False
    chars = "0123456789ABCDEFHJKLMNPRSTUVWXY"
    return chars[int(match.group(1) + match.group(2) + match.group(3) + match.group(5)) % 31] == match.group(6)


def _validate_ie_ppsn(value: str) -> bool:
    compact = _normalise_identifier_value(value)
    match = re.fullmatch(r"(\d{7})([A-W])([A-W]?)", compact)
    if not match:
        return False
    second_letter = match.group(3)
    total = sum(int(digit) * weight for digit, weight in zip(match.group(1), range(8, 1, -1)))
    if second_letter:
        total += (ord(second_letter) - ord("A") + 1) * 9
    chars = "WABCDEFGHIJKLMNOPQRSTUV"
    return chars[total % 23] == match.group(2)


def _validate_at_svnr(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 10:
        return False
    day, month, year = int(digits[4:6]), int(digits[6:8]), int(digits[8:10])
    if not any(_valid_calendar_date(century + year, month, day) for century in (1900, 2000)):
        return False
    payload = digits[:3] + digits[4:]
    weights = [3, 7, 9, 5, 8, 4, 2, 1, 6]
    check = sum(int(digit) * weight for digit, weight in zip(payload, weights)) % 11
    return check < 10 and check == int(digits[3])


def _validate_cz_sk_birth_number(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 10 or int(digits) % 11 != 0:
        return False
    yy, raw_month, day = int(digits[:2]), int(digits[2:4]), int(digits[4:6])
    month = raw_month
    for offset in (70, 50, 20):
        if month > offset:
            month -= offset
            break
    if not 1 <= month <= 12:
        return False
    return any(_valid_calendar_date(century + yy, month, day) for century in (1900, 2000))


def _validate_ro_cnp(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 13 or digits[0] not in "12345678":
        return False
    century = {"1": 1900, "2": 1900, "3": 1800, "4": 1800, "5": 2000, "6": 2000, "7": 1900, "8": 1900}[digits[0]]
    if not _valid_calendar_date(century + int(digits[1:3]), int(digits[3:5]), int(digits[5:7])):
        return False
    weights = "279146358279"
    check = sum(int(digits[i]) * int(weights[i]) for i in range(12)) % 11
    if check == 10:
        check = 1
    return check == int(digits[-1])


def _validate_dk_cpr(value: str) -> bool:
    digits = _digits_only(value)
    if len(digits) != 10:
        return False
    day, month, year = int(digits[:2]), int(digits[2:4]), int(digits[4:6])
    return any(_valid_calendar_date(century + year, month, day) for century in (1900, 2000))


def _eu_member_state_label(label: str) -> str | None:
    normalized = label.casefold()
    if "dni" in normalized or "nie" in normalized or "spanish" in normalized or normalized.startswith("es"):
        return "ES"
    if "bsn" in normalized or "dutch" in normalized or "netherlands" in normalized or normalized.startswith("nl"):
        return "NL"
    if "pesel" in normalized or "polish" in normalized or normalized.startswith("pl"):
        return "PL"
    if "insee" in normalized or "nir" in normalized or "french" in normalized or normalized.startswith("fr"):
        return "FR"
    if "german" in normalized or "steuer" in normalized or normalized.startswith("de"):
        return "DE"
    if "codice" in normalized or "italian" in normalized or "tax code" in normalized or normalized.startswith("it"):
        return "IT"
    if "belg" in normalized or "rijks" in normalized or "national number" in normalized or normalized.startswith("be"):
        return "BE"
    if "nif" in normalized or "portuguese" in normalized or normalized.startswith("pt"):
        return "PT"
    if "personnummer" in normalized or "swedish" in normalized or normalized.startswith("se"):
        return "SE"
    if "hetu" in normalized or "finnish" in normalized or normalized.startswith("fi"):
        return "FI"
    if "ppsn" in normalized or "irish" in normalized or normalized.startswith("ie"):
        return "IE"
    if "svnr" in normalized or "austrian" in normalized or normalized.startswith("at"):
        return "AT"
    if "cpr" in normalized or "danish" in normalized or "denmark" in normalized or normalized.startswith("dk"):
        return "DK"
    if "czech" in normalized or normalized.startswith("cz"):
        return "CZ"
    if "slovak" in normalized or normalized.startswith("sk"):
        return "SK"
    if "cnp" in normalized or "romanian" in normalized or normalized.startswith("ro"):
        return "RO"
    return None


def _validate_eu_member_state_id(country: str | None, value: str) -> bool:
    if country == "ES":
        return _validate_es_dni_nie(value)
    if country == "NL":
        return _validate_nl_bsn(value)
    if country == "PL":
        return _validate_pl_pesel(value)
    if country == "FR":
        return _validate_fr_insee(value)
    if country == "DE":
        return _validate_de_tax_id(value)
    if country == "IT":
        return _validate_it_codice_fiscale(value)
    if country == "BE":
        return _validate_be_national_number(value)
    if country == "PT":
        return _validate_pt_nif(value)
    if country == "SE":
        return _validate_se_personnummer(value)
    if country == "FI":
        return _validate_fi_hetu(value)
    if country == "IE":
        return _validate_ie_ppsn(value)
    if country == "AT":
        return _validate_at_svnr(value)
    if country in {"CZ", "SK"}:
        return _validate_cz_sk_birth_number(value)
    if country == "RO":
        return _validate_ro_cnp(value)
    if country == "DK":
        return _validate_dk_cpr(value)
    return True


def _valid_uk_company_number(value: str) -> bool:
    compact = re.sub(r"\s+", "", value).upper()
    return bool(re.fullmatch(
        r"(?:\d{8}|(?:AC|CE|FC|GE|GS|IC|IP|LP|NA|NC|NF|NI|NL|NO|NP|NR|NV|OC|RC|R0|"
        r"SA|SC|SE|SF|SI|SL|SO|SP|SR|SZ|ZC)\d{6})",
        compact,
    ))


def _valid_eu_company_id_shape(value: str) -> bool:
    compact = re.sub(r"[\s.-]", "", value).upper()
    digits = "".join(ch for ch in compact if ch.isdigit())
    if digits and set(digits) == {"0"}:
        return False
    return bool(re.fullmatch(
        r"(?:ATU\d{8}|BE0?\d{9}|BG\d{9,10}|CY\d{8}[A-Z]|CZ\d{8,10}|DE\d{9}|DK\d{8}|EE\d{9}|"
        r"EL\d{9}|ES[A-Z0-9]\d{7}[A-Z0-9]|FI\d{8}|FR[A-Z0-9]{2}\d{9}|HR\d{11}|HU\d{8}|"
        r"IE\d{7}[A-Z]{1,2}|IT\d{11}|LT\d{9}(?:\d{3})?|LU\d{8}|LV\d{11}|MT\d{8}|"
        r"NL\d{9}B\d{2}|PL\d{10}|PT\d{9}|RO\d{2,10}|SE\d{12}|SI\d{8}|SK\d{10})",
        compact,
    ))


def _ip_version(value: str) -> int | None:
    try:
        return ipaddress.ip_address(value).version
    except ValueError:
        return None


def _normalise_us_state(value: str | None) -> str | None:
    if not value:
        return None
    normalized = " ".join(value.upper().split())
    if normalized in _US_STATE_CODES:
        return normalized
    return _US_STATE_NAME_TO_CODE.get(normalized)


def _state_near_driver_license(text: str, start: int, end: int, explicit_state: str | None) -> str | None:
    state = _normalise_us_state(explicit_state)
    if state:
        return state
    window = text[max(0, start - 90): min(len(text), end + 90)]
    for match in _US_STATE_CONTEXT_RE.finditer(window):
        state = _normalise_us_state(match.group(1))
        if state:
            return state
    return None


def _potential_state_near_driver_license(text: str, start: int, end: int) -> str | None:
    window = text[max(0, start - 40): min(len(text), end + 40)]
    before = re.search(r"\b([A-Z]{2})\s*$", window[: min(40, start - max(0, start - 40))])
    if before:
        return before.group(1)
    context = _US_STATE_CONTEXT_RE.search(window)
    if context:
        return " ".join(context.group(1).upper().split())
    return None


def _valid_us_driver_license(state: str, value: str) -> bool:
    compact = re.sub(r"[\s-]", "", value).upper()
    pattern = _US_DRIVER_LICENSE_PATTERNS.get(state)
    return bool(pattern and re.fullmatch(pattern, compact))


def _age_from_match(match: re.Match[str]) -> int | None:
    for group_name in ("age_field", "age_turns", "age_years"):
        value = match.groupdict().get(group_name)
        if not value:
            continue
        try:
            return int(value)
        except ValueError:
            return None
    return None


def _driver_license_value_is_masked(value: str) -> bool:
    compact = re.sub(r"[\s-]", "", value)
    return bool(re.search(r"(?:\*{2,}|X{3,}|x{3,})", compact))


def detect_core_identifier_findings(
    ctx: DetectorContext,
    idx_start: int,
    new_finding: Callable[..., Any],
    *,
    is_non_attributive_identifier_context: Callable[[str, int, int], bool],
    is_negated_mac_address_context: Callable[[str, int, int], bool],
) -> list[Any]:
    out: list[Any] = []
    idx = idx_start
    for match in DATE_OF_BIRTH_RE.finditer(ctx.text):
        value = match.group(1)
        if not _valid_dob_date(value):
            continue
        if is_non_attributive_identifier_context(ctx.text, match.start(1), match.end(1)):
            continue
        out.append(new_finding(
            idx=idx, category="PII", rule="date_of_birth", jurisdiction=ctx.jurisdiction, severity="high",
            matched_text=value, start=match.start(1), end=match.end(1), reason="Date-of-birth field detected",
            legal_basis=ctx.legal_basis,
        ))
        idx += 1
    for match in AGE_FIELD_RE.finditer(ctx.text):
        age = _age_from_match(match)
        if age is None or age < 20 or age > 120:
            continue
        matched_text = str(age)
        start = match.start(match.lastgroup) if match.lastgroup else match.start()
        end = match.end(match.lastgroup) if match.lastgroup else match.end()
        out.append(new_finding(
            idx=idx, category="PII", rule="age_reference", jurisdiction=ctx.jurisdiction, severity="medium",
            matched_text=matched_text, start=start, end=end,
            reason="Age field detected; minor ages are owned by minor_data_reference", legal_basis=ctx.legal_basis,
        ))
        idx += 1
    network_patterns = (
        ("ip_address", IPV4_CONTEXT_RE, 4, "IPv4 address / online identifier detected"),
        ("ip_address", IPV6_CONTEXT_RE, 6, "IPv6 address / online identifier detected"),
    )
    for rule, pattern, version, reason in network_patterns:
        for match in pattern.finditer(ctx.text):
            value = match.group(1)
            if _ip_version(value) != version:
                continue
            out.append(new_finding(
                idx=idx, category="PII", rule=rule, jurisdiction=ctx.jurisdiction, severity="medium",
                matched_text=value, start=match.start(1), end=match.end(1), reason=reason,
                legal_basis=ctx.legal_basis,
            ))
            idx += 1
    for match in MAC_ADDRESS_RE.finditer(ctx.text):
        value = match.group(1)
        if is_negated_mac_address_context(ctx.text, match.start(), match.end()):
            continue
        out.append(new_finding(
            idx=idx, category="PII", rule="mac_address", jurisdiction=ctx.jurisdiction, severity="medium",
            matched_text=value, start=match.start(1), end=match.end(1),
            reason="MAC address / device identifier detected", legal_basis=ctx.legal_basis,
        ))
        idx += 1
    for match in IMEI_RE.finditer(ctx.text):
        value = match.group(1)
        digits = _digits_only(value)
        if len(digits) != 15 or not _luhn_valid(digits):
            continue
        out.append(new_finding(
            idx=idx, category="PII", rule="imei", jurisdiction=ctx.jurisdiction, severity="high",
            matched_text=value, start=match.start(1), end=match.end(1),
            reason="IMEI / mobile-device identifier detected", legal_basis=ctx.legal_basis,
        ))
        idx += 1
    for match in COOKIE_ID_RE.finditer(ctx.text):
        out.append(new_finding(
            idx=idx, category="PII", rule="cookie_id", jurisdiction=ctx.jurisdiction, severity="medium",
            matched_text=match.group(1), start=match.start(1), end=match.end(1),
            reason="Cookie identifier / online identifier detected", legal_basis=ctx.legal_basis,
        ))
        idx += 1
    for match in ADVERTISING_ID_RE.finditer(ctx.text):
        out.append(new_finding(
            idx=idx, category="PII", rule="advertising_id", jurisdiction=ctx.jurisdiction, severity="medium",
            matched_text=match.group(1), start=match.start(1), end=match.end(1),
            reason="Advertising identifier / online identifier detected", legal_basis=ctx.legal_basis,
        ))
        idx += 1
    for match in DEVICE_SERIAL_RE.finditer(ctx.text):
        if is_non_attributive_identifier_context(ctx.text, match.start(1), match.end(1)):
            continue
        out.append(new_finding(
            idx=idx, category="PII", rule="device_serial_number", jurisdiction=ctx.jurisdiction, severity="medium",
            matched_text=match.group(1), start=match.start(1), end=match.end(1),
            reason="Device serial number detected", legal_basis=ctx.legal_basis,
        ))
        idx += 1
    if any(pack.code == "EU" for pack in ctx.packs):
        for match in EU_NATIONAL_ID_RE.finditer(ctx.text):
            country = match.group("country").upper()
            value = match.group("id")
            validated_countries = {
                "ES", "NL", "PL", "FR", "DE", "IT", "BE", "PT", "SE", "FI", "IE", "AT", "CZ", "SK", "RO",
                "DK",
            }
            de_tax_label = re.search(r"\b(?:tax\s+ID|TIN|Steueridentifikationsnummer)\b", match.group(0), re.I)
            country_requires_validation = country in validated_countries and (country != "DE" or bool(de_tax_label))
            if country_requires_validation and not _validate_eu_member_state_id(country, value):
                continue
            validator = "date_shape" if country == "DK" else "checksum"
            out.append(new_finding(
                idx=idx, category="PII", rule="eu_national_id", jurisdiction=ctx.jurisdiction, severity="high",
                matched_text=value, start=match.start("id"), end=match.end("id"),
                reason=f"EU {country} national identifier detected", legal_basis=ctx.legal_basis,
                metadata={
                    "member_state": country,
                    "validator": validator if country in validated_countries else "label",
                },
            ))
            idx += 1
        for match in EU_MEMBER_STATE_ID_RE.finditer(ctx.text):
            country = _eu_member_state_label(match.group("label"))
            value = match.group("id")
            if not _validate_eu_member_state_id(country, value):
                continue
            out.append(new_finding(
                idx=idx, category="PII", rule="eu_national_id", jurisdiction=ctx.jurisdiction, severity="high",
                matched_text=value, start=match.start("id"), end=match.end("id"),
                reason=f"EU {country or 'member-state'} national identifier detected", legal_basis=ctx.legal_basis,
                metadata={
                    "member_state": country,
                    "validator": "date_shape" if country == "DK" else ("checksum" if country else "label"),
                },
            ))
            idx += 1
    if any(pack.code == "UK" for pack in ctx.packs):
        for match in UK_COMPANY_NUMBER_RE.finditer(ctx.text):
            value = match.group("number")
            if not _valid_uk_company_number(value):
                continue
            out.append(new_finding(
                idx=idx, category="PII", rule="uk_company_number", jurisdiction=ctx.jurisdiction, severity="medium",
                matched_text=value, start=match.start("number"), end=match.end("number"),
                reason="UK Companies House company number detected", legal_basis=ctx.legal_basis,
                metadata={"validator": "companies_house_shape"},
            ))
            idx += 1
    if any(pack.code == "EU" for pack in ctx.packs):
        for match in EU_COMPANY_ID_RE.finditer(ctx.text):
            value = match.group("id")
            if not _valid_eu_company_id_shape(value):
                continue
            out.append(new_finding(
                idx=idx, category="PII", rule="eu_company_id", jurisdiction=ctx.jurisdiction, severity="medium",
                matched_text=value, start=match.start("id"), end=match.end("id"),
                reason="EU VAT / member-state company tax identifier detected", legal_basis=ctx.legal_basis,
                metadata={"validator": "eu_vat_shape"},
            ))
            idx += 1
    return out


def detect_us_driver_license_findings(
    ctx: DetectorContext,
    idx_start: int,
    new_finding: Callable[..., Any],
) -> list[Any]:
    if not any(pack.code == "US" for pack in ctx.packs):
        return []
    out: list[Any] = []
    idx = idx_start
    seen_spans: set[tuple[int, int]] = set()
    for match in _US_DRIVER_LICENSE_RE.finditer(ctx.text):
        state = _state_near_driver_license(ctx.text, match.start(), match.end(), match.group("state"))
        if not state or _driver_license_value_is_masked(match.group("number")):
            continue
        if not _valid_us_driver_license(state, match.group("number")):
            continue
        span = match.span("number")
        if span in seen_spans:
            continue
        seen_spans.add(span)
        out.append(new_finding(
            idx=idx, category="PII", rule="us_driver_license", jurisdiction=ctx.jurisdiction, severity="high",
            matched_text=match.group("number"), start=span[0], end=span[1],
            reason=f"US {state} driver-license identifier detected", legal_basis=ctx.legal_basis,
        ))
        idx += 1
    return out


def detect_sg_wedge_remainder_findings(
    ctx: DetectorContext,
    idx_start: int,
    new_finding: Callable[..., Any],
) -> list[Any]:
    if not any(pack.code == "SG" for pack in ctx.packs):
        return []
    out: list[Any] = []
    idx = idx_start
    rules = [
        ("sg_insurance_policy_number", SG_INSURANCE_POLICY_RE, "medium",
         "Singapore insurance policy / certificate / claim reference detected"),
        ("crypto_wallet_address", CRYPTO_WALLET_RE, "high",
         "Crypto wallet / DPT transfer address detected in a labelled VASP/payment context"),
        ("sg_tribunal_reference", SG_TRIBUNAL_REFERENCE_RE, "medium",
         "Singapore tribunal / regulator dispute reference detected"),
    ]
    seen: set[tuple[str, int, int]] = set()
    for rule, pattern, severity, reason in rules:
        for match in pattern.finditer(ctx.text):
            span = match.span(1)
            key = (rule, span[0], span[1])
            if key in seen:
                continue
            seen.add(key)
            out.append(new_finding(
                idx=idx, category="PII", rule=rule, jurisdiction=ctx.jurisdiction, severity=severity,
                matched_text=match.group(1), start=span[0], end=span[1], reason=reason,
                legal_basis=ctx.legal_basis,
            ))
            idx += 1
    return out


def driver_license_coverage_warnings(
    text: str,
    *,
    packs: list[Any],
    review_profile: str,
) -> list[dict[str, Any]]:
    if review_profile != "audit_grade" or not any(pack.code == "US" for pack in packs):
        return []
    warnings: list[dict[str, Any]] = []
    for match in _US_DRIVER_LICENSE_ANY_RE.finditer(text):
        state = _state_near_driver_license(text, match.start(), match.end(), None)
        number = match.group("number")
        if state:
            if not _valid_us_driver_license(state, number) and _driver_license_value_is_masked(number):
                warnings.append({
                    "rule_guess": "us_driver_license",
                    "why": (
                        "Driver-license-like field appears masked or partial; "
                        "state-specific validation was not applied."
                    ),
                    "confidence": 0.68,
                })
            continue
        candidate = _potential_state_near_driver_license(text, match.start(), match.end())
        if candidate in _US_STATE_CODES and _driver_license_value_is_masked(number):
            warnings.append({
                "rule_guess": "us_driver_license",
                "why": (
                    "Driver-license-like field appears masked or partial; "
                    "state-specific validation was not applied."
                ),
                "confidence": 0.68,
            })
        elif candidate and candidate not in _US_STATE_CODES:
            warnings.append({
                "rule_guess": "us_driver_license",
                "why": (
                    "Driver-license-like field has an unsupported issuer/state; "
                    "state-specific validation was not applied."
                ),
                "confidence": 0.72,
            })
        else:
            warnings.append({
                "rule_guess": "us_driver_license",
                "why": (
                    "Driver-license-like field is missing an issuing state; "
                    "state-specific validation was not applied."
                ),
                "confidence": 0.7,
            })
    return warnings
