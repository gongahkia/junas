"""Jurisdiction rule-pack registry.

Packs ship as TOML in `src/junas/review/jurisdictions_data/*.toml` and are loaded at import.
Customers can extend or override the registry by pointing `JUNAS_JURISDICTION_PACKS_DIR` at
an additional directory of `*.toml` files. Customer packs override built-ins with the same
`code`, so a tenant can re-cite policy without forking the engine.

Each pack TOML carries:
    code            -- canonical code (e.g. "SG"); upper-cased
    label           -- human label
    pii_rules       -- list of rule identifiers
    mnpi_rules      -- list of rule identifiers
    references      -- list of citation strings
    aliases         -- optional list of aliases that normalise to `code`
    [[recognizers]] -- optional list of jurisdiction-local PII recognizers, each with:
                       name, rule_name, pattern, severity ∈ {low,medium,high}, reason,
                       optional capture_group (int, defaults to 0 for full-match span),
                       and optional validator (named checksum/shape validator)

Unknown request identifiers are rejected. Malformed configured packs disable resolution
until a successful reload; recognizers remain optional for policy-only packs.
"""

from __future__ import annotations

import os
import re
import tomllib
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

_BUILTIN_PACKS_DIR = Path(__file__).parent / "jurisdictions_data"


_VALID_SEVERITIES = frozenset({"low", "medium", "high"})


@dataclass(frozen=True)
class Recognizer:
    """A jurisdiction-local PII recognizer compiled from a TOML pack."""

    name: str  # human-readable identifier; also used in error messages
    rule_name: str  # the rule string emitted on the finding
    pattern: "re.Pattern[str]"
    severity: str
    reason: str
    capture_group: int = 0  # 0 = full match; >0 = pick that capture group's span
    validator_name: str = ""

    def is_valid(self, value: str) -> bool:
        if not self.validator_name:
            return True
        return _VALIDATORS[self.validator_name](value)


def _digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def _validate_hk_hkid(value: str) -> bool:
    normalized = re.sub(r"[\s()\-]", "", value).upper()
    match = re.fullmatch(r"([A-Z]{1,2})(\d{6})([0-9A])", normalized)
    if not match:
        return False
    letters, digits, check = match.groups()
    letter_values = [ord(ch) - 55 for ch in letters]  # A=10 ... Z=35
    if len(letter_values) == 1:
        letter_values.insert(0, 36)  # single-letter HKIDs use a leading space value
    values = letter_values + [int(ch) for ch in digits]
    weights = [9, 8, 7, 6, 5, 4, 3, 2]
    check_value = 10 if check == "A" else int(check)
    return (sum(value * weight for value, weight in zip(values, weights)) + check_value) % 11 == 0


def _validate_au_tfn(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 9:
        return False
    weights = [1, 4, 3, 7, 5, 8, 6, 9, 10]
    return sum(int(digit) * weight for digit, weight in zip(digits, weights)) % 11 == 0


def _validate_au_abn(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 11:
        return False
    weights = [10, 1, 3, 5, 7, 9, 11, 13, 15, 17, 19]
    adjusted = [int(digit) for digit in digits]
    adjusted[0] -= 1
    return sum(digit * weight for digit, weight in zip(adjusted, weights)) % 89 == 0


def _validate_au_acn(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 9:
        return False
    weights = [8, 7, 6, 5, 4, 3, 2, 1]
    check_digit = (10 - (sum(int(digit) * weight for digit, weight in zip(digits[:8], weights)) % 10)) % 10
    return check_digit == int(digits[8])


def _validate_jp_my_number(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 12:
        return False
    weights = [6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
    remainder = sum(int(digit) * weight for digit, weight in zip(digits[:11], weights)) % 11
    check_digit = 0 if remainder <= 1 else 11 - remainder
    return check_digit == int(digits[11])


def _validate_jp_corporate_number(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 13:
        return False
    total = 0
    for index, digit in enumerate(reversed(digits[1:]), start=1):
        total += int(digit) * (1 if index % 2 else 2)
    check_digit = 9 - (total % 9)
    return check_digit == int(digits[0])


def _validate_kr_rrn(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 13:
        return False
    weights = [2, 3, 4, 5, 6, 7, 8, 9, 2, 3, 4, 5]
    check_digit = (11 - (sum(int(digit) * weight for digit, weight in zip(digits[:12], weights)) % 11)) % 10
    return check_digit == int(digits[12])


def _validate_kr_business_registration(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 10:
        return False
    weights = [1, 3, 7, 1, 3, 7, 1, 3, 5]
    products = [int(digit) * weight for digit, weight in zip(digits[:9], weights)]
    check_digit = (10 - ((sum(products) + products[-1] // 10) % 10)) % 10
    return check_digit == int(digits[9])


def _validate_us_ssn(value: str) -> bool:
    # SSA disallows: area 000 / 666 / 900-999; group 00; serial 0000.
    # also reject the famous test number 078-05-1120 and the 219-09-9999 advertising leak —
    # both are public-knowledge "never valid" sentinels per SSA.
    digits = _digits(value)
    if len(digits) != 9:
        return False
    area, group, serial = digits[0:3], digits[3:5], digits[5:9]
    if area in {"000", "666"} or area.startswith("9"):
        return False
    if group == "00" or serial == "0000":
        return False
    if digits in {"078051120", "219099999"}:
        return False
    return True


def _validate_us_ein(value: str) -> bool:
    # IRS publishes a closed prefix list; only allocated prefixes are valid.
    digits = _digits(value)
    if len(digits) != 9:
        return False
    prefix = digits[0:2]
    allocated = {
        "01",
        "02",
        "03",
        "04",
        "05",
        "06",
        "10",
        "11",
        "12",
        "13",
        "14",
        "15",
        "16",
        "20",
        "21",
        "22",
        "23",
        "24",
        "25",
        "26",
        "27",
        "30",
        "31",
        "32",
        "33",
        "34",
        "35",
        "36",
        "37",
        "38",
        "39",
        "40",
        "41",
        "42",
        "43",
        "44",
        "45",
        "46",
        "47",
        "48",
        "50",
        "51",
        "52",
        "53",
        "54",
        "55",
        "56",
        "57",
        "58",
        "59",
        "60",
        "61",
        "62",
        "63",
        "64",
        "65",
        "66",
        "67",
        "68",
        "71",
        "72",
        "73",
        "74",
        "75",
        "76",
        "77",
        "80",
        "81",
        "82",
        "83",
        "84",
        "85",
        "86",
        "87",
        "88",
        "90",
        "91",
        "92",
        "93",
        "94",
        "95",
        "98",
        "99",
    }
    return prefix in allocated


def _validate_us_itin(value: str) -> bool:
    # IRS IRM: ITINs are 9XX-50-XXXX through 9XX-65-XXXX,
    # 9XX-70-XXXX through 9XX-88-XXXX, 9XX-90-XXXX through 9XX-92-XXXX,
    # or 9XX-94-XXXX through 9XX-99-XXXX.
    digits = _digits(value)
    if len(digits) != 9 or not digits.startswith("9"):
        return False
    middle = int(digits[3:5])
    return 50 <= middle <= 65 or 70 <= middle <= 88 or 90 <= middle <= 92 or 94 <= middle <= 99


# item 102: India Aadhaar Verhoeff checksum. UIDAI publishes the 12-digit identifier
# with the Verhoeff check digit in the final position; UIDAI issues numbers beginning
# with 2-9 only (0 and 1 are reserved). Rejects all-same-digit and well-known UIDAI
# test vectors. Source: aadhaarvalidate.com, UIDAI Developer Documentation.
_VERHOEFF_D = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 2, 3, 4, 0, 6, 7, 8, 9, 5),
    (2, 3, 4, 0, 1, 7, 8, 9, 5, 6),
    (3, 4, 0, 1, 2, 8, 9, 5, 6, 7),
    (4, 0, 1, 2, 3, 9, 5, 6, 7, 8),
    (5, 9, 8, 7, 6, 0, 4, 3, 2, 1),
    (6, 5, 9, 8, 7, 1, 0, 4, 3, 2),
    (7, 6, 5, 9, 8, 2, 1, 0, 4, 3),
    (8, 7, 6, 5, 9, 3, 2, 1, 0, 4),
    (9, 8, 7, 6, 5, 4, 3, 2, 1, 0),
)
_VERHOEFF_P = (
    (0, 1, 2, 3, 4, 5, 6, 7, 8, 9),
    (1, 5, 7, 6, 2, 8, 3, 0, 9, 4),
    (5, 8, 0, 3, 7, 9, 6, 1, 4, 2),
    (8, 9, 1, 6, 0, 4, 3, 5, 2, 7),
    (9, 4, 5, 3, 1, 2, 6, 8, 7, 0),
    (4, 2, 8, 6, 5, 7, 3, 9, 0, 1),
    (2, 7, 9, 3, 8, 0, 6, 4, 1, 5),
    (7, 0, 4, 6, 9, 1, 3, 2, 5, 8),
)


def _validate_in_aadhaar(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 12:
        return False
    # UIDAI: leading digit must be 2-9 (0 and 1 reserved).
    if digits[0] in {"0", "1"}:
        return False
    # reject obvious test patterns: all-same-digit / sequential.
    if len(set(digits)) == 1:
        return False
    if digits in {"123456789012", "999999999999"}:
        return False
    check = 0
    for index, digit in enumerate(reversed(digits)):
        check = _VERHOEFF_D[check][_VERHOEFF_P[index % 8][int(digit)]]
    return check == 0


# item 102: India PAN format. 10 chars: [A-Z]{3}[PCHFATBLJ][A-Z][0-9]{4}[A-Z].
# 4th char encodes entity type: P=Individual, C=Company, H=HUF, F=Firm, A=AOP,
# T=Trust, B=BOI, L=Local-Authority, J=AOP-other-than-trust. (G=Government also
# appears in practice — included.) Validator is format-only.
def _validate_in_pan(value: str) -> bool:
    normalized = re.sub(r"\s", "", value).upper()
    return bool(re.fullmatch(r"[A-Z]{3}[PCHFATBLJG][A-Z]\d{4}[A-Z]", normalized))


# item 103: China Resident ID. 18-digit identifier with ISO 7064 MOD 11-2 checksum.
# Weights: [7,9,10,5,8,4,2,1,6,3,7,9,10,5,8,4,2]; check digit lookup [1,0,X,9,8,7,6,5,4,3,2]
# indexed by `sum(weighted) % 11`. Last digit is 0-9 or 'X'. Source: GB 11643-1999,
# ISO 7064:1983 + Wikipedia Resident Identity Card.
_CN_RESIDENT_WEIGHTS = (7, 9, 10, 5, 8, 4, 2, 1, 6, 3, 7, 9, 10, 5, 8, 4, 2)
_CN_RESIDENT_CHECKS = ("1", "0", "X", "9", "8", "7", "6", "5", "4", "3", "2")


def _validate_cn_resident_id(value: str) -> bool:
    normalized = re.sub(r"\s", "", value).upper()
    if not re.fullmatch(r"\d{17}[\dX]", normalized):
        return False
    total = sum(int(normalized[i]) * _CN_RESIDENT_WEIGHTS[i] for i in range(17))
    return _CN_RESIDENT_CHECKS[total % 11] == normalized[17]


# item 103: China Unified Social Credit Code (USCC). 18-char alphanumeric;
# excludes I, O, Z, S, V. Position 1: registration management dept; position 2:
# institution category; positions 3-8: GB/T 2260 administrative division;
# positions 9-17: subject identifier; position 18: ISO 7064 MOD 31-3 checksum.
# Source: GB 32100-2015. Weights are powers-of-2 mod 31 (doubling sequence
# adjusted for 17 positions).
_USCC_ALPHABET = "0123456789ABCDEFGHJKLMNPQRTUWXY"  # 31 chars, excludes I O Z S V
_USCC_WEIGHTS = (1, 3, 9, 27, 19, 26, 16, 17, 20, 29, 25, 13, 8, 24, 10, 30, 28)


def _validate_cn_uscc(value: str) -> bool:
    normalized = re.sub(r"\s", "", value).upper()
    if len(normalized) != 18:
        return False
    if not all(c in _USCC_ALPHABET for c in normalized):
        return False
    total = sum(_USCC_ALPHABET.index(normalized[i]) * _USCC_WEIGHTS[i] for i in range(17))
    check = (31 - (total % 31)) % 31
    return _USCC_ALPHABET[check] == normalized[17]


# item 104: UAE Emirates ID format. 15 digits, must start with 784 (UAE country code);
# pattern: 784-YYYY-NNNNNNN-N. UAE government checksum algorithm is not publicly
# documented (per web search 2026-05-27); validator is format + 784-prefix only.
def _validate_ae_emirates_id(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 15:
        return False
    return digits.startswith("784")


# item 104: KSA National ID format. 10 digits; first digit 1 = citizen, 2 = resident
# (Iqama). Saudi MOI checksum algorithm is not publicly documented (per web search
# 2026-05-27); validator is format + leading-digit only.
def _validate_sa_national_id(value: str) -> bool:
    digits = _digits(value)
    if len(digits) != 10:
        return False
    return digits[0] in {"1", "2"}


def _validate_sa_iqama(value: str) -> bool:
    # Iqama is a 10-digit residence permit. Starts with 2.
    digits = _digits(value)
    if len(digits) != 10:
        return False
    return digits[0] == "2"


def _validate_uk_nin(value: str) -> bool:
    # HMRC NINO format: 2 letters + 6 digits + 1 of [A B C D].
    # Disallowed first letters: D F I Q U V. Disallowed second letters: D F I Q U V O.
    # Reserved prefixes never issued: BG GB KN NK NT TN ZZ.
    normalized = re.sub(r"\s", "", value).upper()
    match = re.fullmatch(r"([A-Z]{2})(\d{6})([A-D])", normalized)
    if not match:
        return False
    prefix = match.group(1)
    if prefix[0] in {"D", "F", "I", "Q", "U", "V"}:
        return False
    if prefix[1] in {"D", "F", "I", "Q", "U", "V", "O"}:
        return False
    if prefix in {"BG", "GB", "KN", "NK", "NT", "TN", "ZZ"}:
        return False
    return True


def _validate_th_national_id(value: str) -> bool:
    # Thailand personal ID / natural-person TIN: 13 digits, first digit 1-8.
    # The final digit is (11 - weighted_sum_mod_11) mod 10 over the first 12 digits,
    # with weights 13..2. Leading 0 is reserved for juristic-person tax IDs.
    digits = _digits(value)
    if len(digits) != 13:
        return False
    if digits[0] == "0" or digits[0] == "9":
        return False
    total = sum(int(digit) * weight for digit, weight in zip(digits[:12], range(13, 1, -1)))
    check_digit = (11 - (total % 11)) % 10
    return check_digit == int(digits[12])


_VALIDATORS: dict[str, Callable[[str], bool]] = {
    "hk_hkid": _validate_hk_hkid,
    "au_tfn": _validate_au_tfn,
    "au_abn": _validate_au_abn,
    "au_acn": _validate_au_acn,
    "jp_my_number": _validate_jp_my_number,
    "jp_corporate_number": _validate_jp_corporate_number,
    "kr_rrn": _validate_kr_rrn,
    "kr_business_registration": _validate_kr_business_registration,
    "us_ssn": _validate_us_ssn,
    "us_ein": _validate_us_ein,
    "us_itin": _validate_us_itin,
    "uk_nin": _validate_uk_nin,
    "in_aadhaar": _validate_in_aadhaar,
    "in_pan": _validate_in_pan,
    "cn_resident_id": _validate_cn_resident_id,
    "cn_uscc": _validate_cn_uscc,
    "ae_emirates_id": _validate_ae_emirates_id,
    "sa_national_id": _validate_sa_national_id,
    "sa_iqama": _validate_sa_iqama,
    "th_national_id": _validate_th_national_id,
}


@dataclass(frozen=True)
class JurisdictionRulePack:
    code: str
    label: str
    pii_rules: tuple[str, ...]
    mnpi_rules: tuple[str, ...]
    references: tuple[str, ...]
    recognizers: tuple[Recognizer, ...] = field(default_factory=tuple)


def _string(value: object, *, label: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{label} must be a nonempty string")
    return value


def _string_list(raw: dict, key: str) -> tuple[str, ...]:
    values = raw.get(key, [])
    if not isinstance(values, list):
        raise ValueError(f"{key} must be an array of strings")
    return tuple(_string(value, label=key) for value in values)


def _compile_recognizers(code: str, raw_list: list) -> tuple[Recognizer, ...]:
    """Reject malformed declarations instead of silently losing local detectors."""
    if not isinstance(raw_list, list):
        raise ValueError(f"{code} recognizers must be an array of tables")
    compiled: list[Recognizer] = []
    fields = {"name", "rule_name", "pattern", "severity", "reason", "capture_group", "validator"}
    for idx, item in enumerate(raw_list):
        label = f"{code} recognizer #{idx}"
        if not isinstance(item, dict) or set(item) - fields:
            raise ValueError(f"{label}: expected a recognizer table with supported fields {sorted(fields)}")
        name = _string(item.get("name"), label=f"{label}.name")
        rule_name = _string(item.get("rule_name"), label=f"{label}.rule_name")
        pattern_str = _string(item.get("pattern"), label=f"{label}.pattern")
        severity = _string(item.get("severity", "high"), label=f"{label}.severity").lower()
        reason = _string(item.get("reason", f"{name} detector"), label=f"{label}.reason")
        capture_group = item.get("capture_group", 0)
        validator_name = item.get("validator", "")
        if not isinstance(validator_name, str):
            raise ValueError(f"{label}: validator must be a string")
        validator_name = validator_name.strip()
        if severity not in _VALID_SEVERITIES:
            raise ValueError(f"{label}: invalid severity {severity!r}")
        if validator_name and validator_name not in _VALIDATORS:
            raise ValueError(f"{label}: unknown validator {validator_name!r}")
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error as exc:
            raise ValueError(f"{label}: pattern compile failed: {exc}") from exc
        if type(capture_group) is not int or not 0 <= capture_group <= pattern.groups:
            raise ValueError(f"{label}: capture_group must be an integer between 0 and {pattern.groups}")
        compiled.append(Recognizer(name, rule_name, pattern, severity, reason, capture_group, validator_name))
    return tuple(compiled)


def _load_pack_file(path: Path) -> tuple[JurisdictionRulePack, list[str]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    fields = {"code", "label", "pii_rules", "mnpi_rules", "references", "aliases", "recognizers"}
    if unknown := set(raw) - fields:
        raise ValueError(f"unknown jurisdiction pack fields: {sorted(unknown)}")
    code = _string(raw.get("code"), label="jurisdiction code").strip().upper()
    pack = JurisdictionRulePack(
        code=code,
        label=_string(raw.get("label", code), label="label"),
        pii_rules=_string_list(raw, "pii_rules"),
        mnpi_rules=_string_list(raw, "mnpi_rules"),
        references=_string_list(raw, "references"),
        recognizers=_compile_recognizers(code, raw.get("recognizers", [])),
    )
    aliases = [a.strip().upper() for a in _string_list(raw, "aliases")]
    if code not in aliases:
        aliases.append(code)
    return pack, aliases


def _discover_pack_dirs() -> list[Path]:
    dirs = [_BUILTIN_PACKS_DIR]
    override = os.environ.get("JUNAS_JURISDICTION_PACKS_DIR", "").strip()
    if override:
        try:
            dirs.append(Path(override).expanduser())
        except (RuntimeError, ValueError) as exc:
            raise ValueError(f"invalid jurisdiction pack directory {override!r}: {exc}") from exc
    return dirs


def _load_registry() -> tuple[dict[str, JurisdictionRulePack], dict[str, str]]:
    packs: dict[str, JurisdictionRulePack] = {}
    aliases: dict[str, str] = {}
    for pack_dir in _discover_pack_dirs():
        if not pack_dir.is_dir():
            raise ValueError(f"jurisdiction pack directory does not exist or is not a directory: {pack_dir}")
        try:
            paths = sorted(path for path in pack_dir.iterdir() if path.name.endswith(".toml"))
        except OSError as exc:
            raise ValueError(f"cannot read jurisdiction pack directory {pack_dir}: {exc}") from exc
        layer_codes: set[str] = set()
        for path in paths:
            try:
                pack, pack_aliases = _load_pack_file(path)
                if pack.code in layer_codes:
                    raise ValueError(f"duplicate jurisdiction code {pack.code!r} in {pack_dir}")
                layer_codes.add(pack.code)
                if pack.code in aliases and aliases[pack.code] != pack.code:
                    raise ValueError(f"canonical code {pack.code!r} conflicts with an existing alias")
                for alias in pack_aliases:
                    if (alias in packs and alias != pack.code) or aliases.get(alias, pack.code) != pack.code:
                        raise ValueError(f"alias {alias!r} conflicts with another jurisdiction")
                packs[pack.code] = pack
                for alias in pack_aliases:
                    aliases[alias] = pack.code
            except (ValueError, OSError, UnicodeError) as exc:
                raise ValueError(f"invalid jurisdiction pack {path}: {exc}") from exc
    return packs, aliases


RULE_PACKS: dict[str, JurisdictionRulePack] = {}
JURISDICTION_ALIASES: dict[str, str] = {}
_REGISTRY_ERROR: str | None = None


def reload_registry() -> None:
    """Publish a complete valid registry, or disable resolution until a successful reload."""
    global RULE_PACKS, JURISDICTION_ALIASES, _REGISTRY_ERROR
    try:
        packs, aliases = _load_registry()
    except ValueError as exc:
        RULE_PACKS, JURISDICTION_ALIASES = {}, {}
        _REGISTRY_ERROR = str(exc)
        raise
    RULE_PACKS, JURISDICTION_ALIASES = packs, aliases
    _REGISTRY_ERROR = None


# defer initial configuration failures to the request boundary so CLI errors use
# the existing invalid-input exit code instead of an import-time traceback.
try:
    reload_registry()
except ValueError:
    pass


def normalize_jurisdiction(value: str | None, *, default: str = "SG") -> str:
    """Normalize labels; resolve_rule_packs performs admission against the registry."""
    raw = (value or default).strip().upper()
    return JURISDICTION_ALIASES.get(raw, raw)


def resolve_rule_packs(source: str | None, destination: str | None) -> list[JurisdictionRulePack]:
    if _REGISTRY_ERROR is not None:
        raise ValueError(f"jurisdiction configuration unavailable: {_REGISTRY_ERROR}")
    packs: list[JurisdictionRulePack] = []
    for role, value in (("source", source), ("destination", destination)):
        if value is not None and (not isinstance(value, str) or not value.strip()):
            raise ValueError(f"{role} jurisdiction must be a nonempty registered code or alias")
        code = normalize_jurisdiction(value, default="SG")
        pack = RULE_PACKS.get(code)
        if pack is None:
            raise ValueError(
                f"unknown {role} jurisdiction {value!r}; use a registered code or alias: "
                f"{', '.join(sorted(RULE_PACKS))}"
            )
        if pack not in packs:
            packs.append(pack)
    return packs
