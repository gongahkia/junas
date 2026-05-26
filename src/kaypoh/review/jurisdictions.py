"""Jurisdiction rule-pack registry.

Packs ship as TOML in `src/kaypoh/review/jurisdictions_data/*.toml` and are loaded at import.
Customers can extend or override the registry by pointing `KAYPOH_JURISDICTION_PACKS_DIR` at
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
        "01", "02", "03", "04", "05", "06", "10", "11", "12", "13", "14", "15", "16",
        "20", "21", "22", "23", "24", "25", "26", "27",
        "30", "31", "32", "33", "34", "35", "36", "37", "38", "39",
        "40", "41", "42", "43", "44", "45", "46", "47", "48",
        "50", "51", "52", "53", "54", "55", "56", "57", "58", "59",
        "60", "61", "62", "63", "64", "65", "66", "67", "68",
        "71", "72", "73", "74", "75", "76", "77",
        "80", "81", "82", "83", "84", "85", "86", "87", "88",
        "90", "91", "92", "93", "94", "95", "98", "99",
    }
    return prefix in allocated


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
    "uk_nin": _validate_uk_nin,
}


@dataclass(frozen=True)
class JurisdictionRulePack:
    code: str
    label: str
    pii_rules: tuple[str, ...]
    mnpi_rules: tuple[str, ...]
    references: tuple[str, ...]
    recognizers: tuple[Recognizer, ...] = field(default_factory=tuple)


def _compile_recognizers(code: str, raw_list: list) -> tuple[Recognizer, ...]:
    """Compile raw TOML recognizer entries into Recognizer objects. Malformed entries are
    skipped with a stderr warning so a single typo cannot brick a whole pack."""
    import sys

    compiled: list[Recognizer] = []
    for idx, item in enumerate(raw_list or []):
        if not isinstance(item, dict):
            continue
        try:
            name = str(item["name"])
            rule_name = str(item["rule_name"])
            pattern_str = str(item["pattern"])
            severity = str(item.get("severity", "high")).lower()
            reason = str(item.get("reason", f"{name} detector"))
            capture_group = int(item.get("capture_group", 0))
            validator_name = str(item.get("validator", "")).strip()
        except (KeyError, ValueError, TypeError) as exc:
            print(
                f"kaypoh: {code} recognizer #{idx}: malformed entry skipped ({exc})",
                file=sys.stderr,
            )
            continue
        if severity not in _VALID_SEVERITIES:
            print(
                f"kaypoh: {code} recognizer {name!r}: invalid severity {severity!r}; skipping",
                file=sys.stderr,
            )
            continue
        if validator_name and validator_name not in _VALIDATORS:
            print(
                f"kaypoh: {code} recognizer {name!r}: unknown validator {validator_name!r}; skipping",
                file=sys.stderr,
            )
            continue
        # case-insensitive by default — most national-ID formats appear in mixed case.
        # packs can prefix the pattern with `(?-i:...)` if they need case-sensitive matching.
        try:
            pattern = re.compile(pattern_str, re.IGNORECASE)
        except re.error as exc:
            print(
                f"kaypoh: {code} recognizer {name!r}: pattern compile failed ({exc}); skipping",
                file=sys.stderr,
            )
            continue
        compiled.append(
            Recognizer(
                name=name,
                rule_name=rule_name,
                pattern=pattern,
                severity=severity,
                reason=reason,
                capture_group=capture_group,
                validator_name=validator_name,
            )
        )
    return tuple(compiled)


def _load_pack_file(path: Path) -> tuple[JurisdictionRulePack, list[str]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    code = str(raw["code"]).strip().upper()
    pack = JurisdictionRulePack(
        code=code,
        label=str(raw.get("label", code)),
        pii_rules=tuple(str(r) for r in raw.get("pii_rules", [])),
        mnpi_rules=tuple(str(r) for r in raw.get("mnpi_rules", [])),
        references=tuple(str(r) for r in raw.get("references", [])),
        recognizers=_compile_recognizers(code, raw.get("recognizers", [])),
    )
    aliases = [str(a).strip().upper() for a in raw.get("aliases", [])]
    if code not in aliases:
        aliases.append(code)
    return pack, aliases


def _discover_pack_dirs() -> list[Path]:
    dirs: list[Path] = [_BUILTIN_PACKS_DIR]
    override = os.environ.get("KAYPOH_JURISDICTION_PACKS_DIR", "").strip()
    if override:
        # customer override directory wins via late-registration (overrides built-ins by code)
        dirs.append(Path(override).expanduser())
    return dirs


def _load_registry() -> tuple[dict[str, JurisdictionRulePack], dict[str, str]]:
    packs: dict[str, JurisdictionRulePack] = {}
    aliases: dict[str, str] = {}
    for pack_dir in _discover_pack_dirs():
        if not pack_dir.exists() or not pack_dir.is_dir():
            continue
        for path in sorted(pack_dir.glob("*.toml")):
            try:
                pack, pack_aliases = _load_pack_file(path)
            except (KeyError, tomllib.TOMLDecodeError, OSError, UnicodeDecodeError) as exc:
                # malformed / unreadable customer pack: log to stderr and skip rather than crash
                # startup. OSError covers permission-denied / vanished file; UnicodeDecodeError
                # covers a non-utf-8 file dropped in by mistake.
                import sys

                print(f"kaypoh: skipping malformed jurisdiction pack {path}: {exc}", file=sys.stderr)
                continue
            packs[pack.code] = pack
            for alias in pack_aliases:
                aliases[alias] = pack.code
    return packs, aliases


RULE_PACKS, JURISDICTION_ALIASES = _load_registry()


def reload_registry() -> None:
    """Re-read pack TOMLs from disk. Useful in tests that point at temporary pack dirs."""
    global RULE_PACKS, JURISDICTION_ALIASES
    RULE_PACKS, JURISDICTION_ALIASES = _load_registry()


def normalize_jurisdiction(value: str | None, *, default: str = "SG") -> str:
    raw = (value or default).strip().upper()
    return JURISDICTION_ALIASES.get(raw, raw)


def resolve_rule_packs(source: str | None, destination: str | None) -> list[JurisdictionRulePack]:
    codes = [
        normalize_jurisdiction(source, default="SG"),
        normalize_jurisdiction(destination, default="SG"),
    ]
    packs: list[JurisdictionRulePack] = []
    seen: set[str] = set()
    for code in codes:
        pack = RULE_PACKS.get(code)
        if pack is None:
            pack = JurisdictionRulePack(
                code=code,
                label=code,
                pii_rules=(f"{code}_PERSONAL_DATA_BASELINE",),
                mnpi_rules=(f"{code}_MNPI_BASELINE",),
                references=(f"{code} customer-configured policy baseline",),
            )
        if pack.code not in seen:
            packs.append(pack)
            seen.add(pack.code)
    return packs
