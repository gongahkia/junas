from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date
from importlib import resources
from typing import Any

try:
    import tomllib
except ImportError:
    import tomli as tomllib


@dataclass(frozen=True)
class SinglingOutSpec:
    severity: str
    matched_text: str
    start_char: int
    end_char: int
    reason: str
    metadata: dict[str, Any]


@dataclass(frozen=True)
class _Tables:
    total_population: int
    area_population: dict[str, int]
    age_cohorts: dict[str, int]
    postal_population: dict[str, int]
    loaded_tables: tuple[str, ...]


_DIRECT_UNIQUE_RULES = frozenset({
    "email_address",
    "phone_number",
    "sg_nric_fin",
    "sg_uen",
    "passport_number",
    "bank_account",
    "employee_id",
    "customer_account_number",
    "medical_record_number",
    "internal_session_id",
    "bank_customer_reference",
    "insurance_member_id",
    "crypto_wallet_address",
})
_QUASI_RULES = frozenset({
    "named_person",
    "date_of_birth",
    "age_reference",
    "sg_postal_address",
    "personal_attribute_inference",
}) | _DIRECT_UNIQUE_RULES
_MIN_DISTINCT = 3
_K_THRESHOLD = 20
_DEFAULT_K = 5
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_AGE_RE = re.compile(r"\b(?:aged?|age|turns?|years?\s+old)\D{0,12}(\d{1,3})\b", re.IGNORECASE)
_POSTAL_RE = re.compile(r"\b(?:Singapore\s*)?(\d{6})\b", re.IGNORECASE)


def _resource_text(package: str, name: str) -> str:
    return resources.files(package).joinpath(name).read_text(encoding="utf-8")


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _parse_int(value: str) -> int | None:
    cleaned = str(value or "").strip().replace(",", "")
    if not cleaned or cleaned == "-":
        return None
    try:
        return int(cleaned)
    except ValueError:
        return None


def _validate_manifest_entry(manifest: dict[str, Any], table: str, text: str) -> None:
    entry = manifest.get("SG", {}).get(table, {})
    if not isinstance(entry, dict):
        raise RuntimeError(f"missing SG frequency manifest entry for {table}")
    for key in ("source_url", "license", "retrieved_date", "refresh_due_date", "sha256"):
        if not str(entry.get(key) or "").strip():
            raise RuntimeError(f"missing SG frequency manifest {table}.{key}")
    if str(entry["sha256"]) != _sha256_text(text):
        raise RuntimeError(f"SG frequency table checksum mismatch for {table}")
    refresh_due = date.fromisoformat(str(entry["refresh_due_date"]))
    if refresh_due < date.today():
        raise RuntimeError(f"SG frequency table refresh date passed for {table}")


def _load_sg_tables() -> _Tables:
    manifest = tomllib.loads(_resource_text("kaypoh.data.frequency", "MANIFEST.toml"))
    population_text = _resource_text("kaypoh.data.frequency.SG", "population_by_area_age.csv")
    postal_text = _resource_text("kaypoh.data.frequency.SG", "postal_sector_population.csv")
    _validate_manifest_entry(manifest, "population_by_area_age", population_text)
    _validate_manifest_entry(manifest, "postal_sector_population", postal_text)

    area_population: dict[str, int] = {}
    age_cohorts: dict[str, int] = {}
    total_population = 0
    for row in csv.DictReader(population_text.splitlines()):
        area = str(row.get("area") or "").strip()
        total = _parse_int(str(row.get("total") or ""))
        if not area or total is None:
            continue
        if area.casefold() == "total":
            total_population = total
            for key, value in row.items():
                if key.startswith("age_"):
                    parsed = _parse_int(str(value or ""))
                    if parsed is not None:
                        age_cohorts[key.removeprefix("age_")] = parsed
        else:
            area_population[area.casefold()] = total

    postal_population: dict[str, int] = {}
    for row in csv.DictReader(postal_text.splitlines()):
        prefix = str(row.get("postal_prefix") or "").strip()
        population = _parse_int(str(row.get("population") or ""))
        if prefix and population is not None:
            postal_population[prefix] = population

    if not total_population:
        raise RuntimeError("SG total population frequency row missing")
    return _Tables(
        total_population=total_population,
        area_population=area_population,
        age_cohorts=age_cohorts,
        postal_population=postal_population,
        loaded_tables=("population_by_area_age", "postal_sector_population"),
    )


_SG_TABLES: _Tables | None = None


def _tables_for(jurisdiction: str) -> _Tables | None:
    global _SG_TABLES
    if jurisdiction.upper() != "SG":
        return None
    if _SG_TABLES is None:
        _SG_TABLES = _load_sg_tables()
    return _SG_TABLES


def _age_band_from_text(text: str) -> str | None:
    year_match = _YEAR_RE.search(text)
    if year_match:
        age = max(0, date.today().year - int(year_match.group(0)))
    else:
        age_match = _AGE_RE.search(text)
        if not age_match:
            return None
        age = int(age_match.group(1))
    lower = (age // 5) * 5
    upper = lower + 4
    key = f"{lower}_{upper}"
    return key if 20 <= lower <= 55 else None


def _area_population(unit_text: str, tables: _Tables) -> int | None:
    folded = unit_text.casefold()
    matches = [population for area, population in tables.area_population.items() if area in folded]
    return min(matches) if matches else None


def _postal_population(unit_text: str, tables: _Tables) -> int | None:
    populations: list[int] = []
    for match in _POSTAL_RE.finditer(unit_text):
        prefix = match.group(1)[:2]
        if prefix in tables.postal_population:
            populations.append(tables.postal_population[prefix])
    return min(populations) if populations else None


def _severity_for_k(k: int) -> str:
    if k < 2:
        return "high"
    if k < _DEFAULT_K:
        return "medium"
    return "low"


def _unit_for(finding: Any, document_structure: Any) -> Any:
    if document_structure is None:
        return None
    try:
        return document_structure.containing_span(finding.start_char, finding.end_char)
    except Exception:
        return None


def _estimate_k(unit_text: str, findings: list[Any], tables: _Tables) -> tuple[int, list[str], list[str]]:
    rules = {str(f.rule) for f in findings}
    used: list[str] = []
    missing: list[str] = []
    if rules & _DIRECT_UNIQUE_RULES:
        return 1, list(tables.loaded_tables), missing

    estimates: list[int] = []
    age_band = _age_band_from_text(unit_text)
    if age_band and age_band in tables.age_cohorts:
        estimates.append(tables.age_cohorts[age_band])
        used.append("population_by_area_age")
    elif rules & {"date_of_birth", "age_reference"}:
        missing.append("age_cohort")

    area_population = _area_population(unit_text, tables)
    if area_population is not None:
        estimates.append(area_population)
        used.append("population_by_area_age")

    postal_population = _postal_population(unit_text, tables)
    if postal_population is not None:
        estimates.append(postal_population)
        used.append("postal_sector_population")
    elif "sg_postal_address" in rules:
        missing.append("postal_sector_population")

    if "named_person" in rules:
        missing.append("name_density")
    if "personal_attribute_inference" in rules:
        missing.append("role_rarity")

    if not estimates:
        return tables.total_population, used, sorted(set(missing))
    k = max(1, min(estimates))
    return k, sorted(set(used)), sorted(set(missing))


def detect_singling_out(
    findings: list[Any],
    *,
    jurisdiction: str,
    legal_basis: str,
    document_structure: Any,
) -> list[SinglingOutSpec]:
    tables = _tables_for(jurisdiction)
    if tables is None:
        return []
    quasi = [finding for finding in findings if str(getattr(finding, "rule", "")) in _QUASI_RULES]
    grouped: dict[tuple[str, int, int], list[Any]] = {}
    for finding in quasi:
        unit = _unit_for(finding, document_structure)
        if unit is None:
            key = ("document", 0, max((getattr(f, "end_char", 0) for f in quasi), default=0))
        else:
            key = (str(unit.kind), int(unit.start_char), int(unit.end_char))
        grouped.setdefault(key, []).append(finding)

    out: list[SinglingOutSpec] = []
    for (unit_kind, unit_start, unit_end), group in sorted(grouped.items(), key=lambda item: item[0][1]):
        rules = {str(f.rule) for f in group}
        if len(rules) < _MIN_DISTINCT:
            continue
        unit_text = ""
        if document_structure is not None:
            unit_text = str(getattr(document_structure, "text", "")[unit_start:unit_end])
        k, used, missing = _estimate_k(unit_text, group, tables)
        if k >= _K_THRESHOLD:
            continue
        start = min(int(f.start_char) for f in group)
        end = max(int(f.end_char) for f in group)
        probability = round(1.0 / max(1, k), 6)
        metadata = {
            "layer": "singling_out_v2",
            "re_identification_estimate": probability,
            "k_anonymity_equivalence": k,
            "singling_out_scope": unit_kind,
            "frequency_tables_used": used,
            "frequency_tables_missing": missing,
            "distinct_quasi_identifier_rules": sorted(rules),
            "legal_basis": legal_basis,
        }
        out.append(
            SinglingOutSpec(
                severity=_severity_for_k(k),
                matched_text=str(getattr(document_structure, "text", "")[start:end]) if document_structure else "",
                start_char=start,
                end_char=end,
                reason=(
                    f"{len(rules)} quasi-identifier rules co-occur in one {unit_kind}; "
                    f"SG population-prior estimate k={k}"
                ),
                metadata=metadata,
            )
        )
    return out
