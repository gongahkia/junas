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
"""

from __future__ import annotations

import os
import tomllib
from dataclasses import dataclass
from pathlib import Path


_BUILTIN_PACKS_DIR = Path(__file__).parent / "jurisdictions_data"


@dataclass(frozen=True)
class JurisdictionRulePack:
    code: str
    label: str
    pii_rules: tuple[str, ...]
    mnpi_rules: tuple[str, ...]
    references: tuple[str, ...]


def _load_pack_file(path: Path) -> tuple[JurisdictionRulePack, list[str]]:
    raw = tomllib.loads(path.read_text(encoding="utf-8"))
    code = str(raw["code"]).strip().upper()
    pack = JurisdictionRulePack(
        code=code,
        label=str(raw.get("label", code)),
        pii_rules=tuple(str(r) for r in raw.get("pii_rules", [])),
        mnpi_rules=tuple(str(r) for r in raw.get("mnpi_rules", [])),
        references=tuple(str(r) for r in raw.get("references", [])),
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
