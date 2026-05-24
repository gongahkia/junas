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
                       name, rule_name, pattern, severity ∈ {low,medium,high}, reason
                       and optional capture_group (int, defaults to 0 for full-match span)
"""

from __future__ import annotations

import os
import re
import tomllib
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
