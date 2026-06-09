from __future__ import annotations

import csv
import hashlib
import os
import re
from dataclasses import dataclass
from datetime import date
from importlib import resources
from pathlib import Path
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
    jurisdiction: str
    total_population: int
    area_population: dict[str, int]
    age_cohorts: dict[str, int]
    postal_population: dict[str, int]
    name_population: dict[str, int]
    surname_population: dict[str, int]
    role_population: dict[str, int]
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
    "uk_company_number",
    "eu_company_id",
})
_QUASI_RULES = frozenset({
    "named_person",
    "date_of_birth",
    "age_reference",
    "sg_postal_address",
    "uk_postal_address",
    "au_postal_address",
    "jp_postal_address",
    "kr_postal_address",
    "us_postal_address",
    "eu_postal_address",
    "postal_address",
    "personal_attribute_inference",
}) | _DIRECT_UNIQUE_RULES
_MIN_DISTINCT = 3
_K_THRESHOLD = 20
_DEFAULT_K = 5
_YEAR_RE = re.compile(r"\b(?:19|20)\d{2}\b")
_AGE_RE = re.compile(r"\b(?:aged?|age|turns?|years?\s+old)\D{0,12}(\d{1,3})\b", re.IGNORECASE)
_SG_POSTAL_RE = re.compile(r"\b(?:Singapore\s*)?(\d{6})\b", re.IGNORECASE)
_AU_POSTAL_RE = re.compile(r"\b(?:Australia\s*)?(\d{4})\b", re.IGNORECASE)
_UK_POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d)[A-Z]{2}\b", re.IGNORECASE)
_NAME_PREFIX_RE = re.compile(r"^(?:Mr|Ms|Mrs|Mdm|Dr|Prof)\.?\s+", re.IGNORECASE)
_SURNAME_TOKEN_RE = re.compile(r"[A-Za-z][A-Za-z'\-]*")
_FREQUENCY_KEY_RE = re.compile(r"[A-Za-z0-9]+")
_ROLE_PREFIX_RE = re.compile(r"^(?:JUNIOR|SENIOR|PRINCIPAL|LEAD|HEAD\s+OF|ASSOCIATE)\s+", re.IGNORECASE)
_POSTAL_RULES = frozenset({
    "sg_postal_address",
    "uk_postal_address",
    "au_postal_address",
    "jp_postal_address",
    "kr_postal_address",
    "us_postal_address",
    "eu_postal_address",
    "postal_address",
})
_LOCALITY_RULES = _POSTAL_RULES | frozenset({"personal_attribute_inference"})


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


def _validate_manifest_entry(manifest: dict[str, Any], jurisdiction: str, table: str, text: str) -> None:
    entry = manifest.get(jurisdiction.upper(), {}).get(table, {})
    if not isinstance(entry, dict):
        raise RuntimeError(f"missing {jurisdiction.upper()} frequency manifest entry for {table}")
    for key in ("source_url", "license", "retrieved_date", "refresh_due_date", "sha256"):
        if not str(entry.get(key) or "").strip():
            raise RuntimeError(f"missing {jurisdiction.upper()} frequency manifest {table}.{key}")
    if str(entry["sha256"]) != _sha256_text(text):
        raise RuntimeError(f"{jurisdiction.upper()} frequency table checksum mismatch for {table}")
    refresh_due = date.fromisoformat(str(entry["refresh_due_date"]))
    if refresh_due < date.today():
        raise RuntimeError(f"{jurisdiction.upper()} frequency table refresh date passed for {table}")


def _load_bundled_tables(jurisdiction: str) -> _Tables | None:
    code = jurisdiction.upper()
    manifest = tomllib.loads(_resource_text("kaypoh.data.frequency", "MANIFEST.toml"))
    entries = manifest.get(code, {})
    if not isinstance(entries, dict):
        return None
    area_population: dict[str, int] = {}
    age_cohorts: dict[str, int] = {}
    postal_population: dict[str, int] = {}
    name_population: dict[str, int] = {}
    surname_population: dict[str, int] = {}
    role_population: dict[str, int] = {}
    total_population = 0
    loaded: list[str] = []

    if isinstance(entries.get("population_by_area_age"), dict):
        population_text = _resource_text(f"kaypoh.data.frequency.{code}", "population_by_area_age.csv")
        _validate_manifest_entry(manifest, code, "population_by_area_age", population_text)
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
        loaded.append("population_by_area_age")

    if isinstance(entries.get("area_population"), dict):
        area_text = _resource_text(f"kaypoh.data.frequency.{code}", "area_population.csv")
        _validate_manifest_entry(manifest, code, "area_population", area_text)
        for row in csv.DictReader(area_text.splitlines()):
            area = str(row.get("area") or "").strip()
            population = _parse_int(str(row.get("population") or ""))
            if area and population is not None:
                area_population[area.casefold()] = population
        loaded.append("area_population")

    for table in ("postal_sector_population", "postal_population"):
        if not isinstance(entries.get(table), dict):
            continue
        postal_text = _resource_text(f"kaypoh.data.frequency.{code}", f"{table}.csv")
        _validate_manifest_entry(manifest, code, table, postal_text)
        for row in csv.DictReader(postal_text.splitlines()):
            prefix = str(row.get("postal_prefix") or "").strip().upper()
            population = _parse_int(str(row.get("population") or ""))
            if prefix and population is not None:
                postal_population[prefix] = population
        loaded.append(table)

    if isinstance(entries.get("name_frequency"), dict):
        name_text = _resource_text(f"kaypoh.data.frequency.{code}", "name_frequency.csv")
        _validate_manifest_entry(manifest, code, "name_frequency", name_text)
        for row in csv.DictReader(name_text.splitlines()):
            name = _frequency_key(str(row.get("name") or ""))
            population = _parse_int(str(row.get("population") or ""))
            if name and population is not None:
                name_population[name] = population
        loaded.append("name_frequency")

    if isinstance(entries.get("surname_frequency"), dict):
        surname_text = _resource_text(f"kaypoh.data.frequency.{code}", "surname_frequency.csv")
        _validate_manifest_entry(manifest, code, "surname_frequency", surname_text)
        for row in csv.DictReader(surname_text.splitlines()):
            surname = str(row.get("surname") or "").strip().upper()
            population = _parse_int(str(row.get("population") or ""))
            if surname and population is not None:
                surname_population[surname] = population
        loaded.append("surname_frequency")

    if isinstance(entries.get("role_frequency"), dict):
        role_text = _resource_text(f"kaypoh.data.frequency.{code}", "role_frequency.csv")
        _validate_manifest_entry(manifest, code, "role_frequency", role_text)
        for row in csv.DictReader(role_text.splitlines()):
            role = _role_key(str(row.get("role") or ""))
            population = _parse_int(str(row.get("population") or ""))
            if role and population is not None:
                role_population[role] = population
        loaded.append("role_frequency")

    if not loaded:
        return None
    total_population = (
        total_population
        or sum(area_population.values())
        or sum(postal_population.values())
        or sum(name_population.values())
        or sum(surname_population.values())
        or sum(role_population.values())
    )
    if not total_population:
        raise RuntimeError(f"{code} bundled frequency tables have no population rows")
    return _Tables(
        jurisdiction=code,
        total_population=total_population,
        area_population=area_population,
        age_cohorts=age_cohorts,
        postal_population=postal_population,
        name_population=name_population,
        surname_population=surname_population,
        role_population=role_population,
        loaded_tables=tuple(sorted(set(loaded))),
    )


def _load_sg_tables() -> _Tables:
    tables = _load_bundled_tables("SG")
    if tables is None:
        raise RuntimeError("SG bundled frequency tables missing")
    return tables


_BUNDLED_TABLES: dict[str, _Tables | None] = {}
_GENERATED_TABLES: dict[tuple[str, str], _Tables | None] = {}


def _read_generated_table(base_dir: Path, relative_path: str) -> str:
    path = (base_dir / relative_path).resolve()
    if not path.is_file():
        raise RuntimeError(f"generated frequency table missing: {relative_path}")
    return path.read_text(encoding="utf-8")


def _load_generated_tables(jurisdiction: str, base_dir: str | os.PathLike[str]) -> _Tables | None:
    code = jurisdiction.upper()
    root = Path(base_dir)
    manifest_path = root / "MANIFEST.generated.toml"
    if not manifest_path.is_file():
        return None
    manifest = tomllib.loads(manifest_path.read_text(encoding="utf-8"))
    entries = manifest.get(code, {})
    if not isinstance(entries, dict):
        return None

    loaded: list[str] = []
    area_population: dict[str, int] = {}
    age_cohorts: dict[str, int] = {}
    postal_population: dict[str, int] = {}
    name_population: dict[str, int] = {}
    surname_population: dict[str, int] = {}
    role_population: dict[str, int] = {}

    if isinstance(entries.get("area_population"), dict):
        text = _read_generated_table(root, str(entries["area_population"].get("path") or ""))
        _validate_manifest_entry(manifest, code, "area_population", text)
        for row in csv.DictReader(text.splitlines()):
            area = str(row.get("area") or "").strip()
            population = _parse_int(str(row.get("population") or ""))
            if area and population is not None:
                area_population[area.casefold()] = population
        loaded.append("area_population")

    if isinstance(entries.get("postal_population"), dict):
        text = _read_generated_table(root, str(entries["postal_population"].get("path") or ""))
        _validate_manifest_entry(manifest, code, "postal_population", text)
        for row in csv.DictReader(text.splitlines()):
            prefix = str(row.get("postal_prefix") or "").strip().upper()
            population = _parse_int(str(row.get("population") or ""))
            if prefix and population is not None:
                postal_population[prefix] = population
        loaded.append("postal_population")

    if isinstance(entries.get("name_frequency"), dict):
        text = _read_generated_table(root, str(entries["name_frequency"].get("path") or ""))
        _validate_manifest_entry(manifest, code, "name_frequency", text)
        for row in csv.DictReader(text.splitlines()):
            name = _frequency_key(str(row.get("name") or ""))
            population = _parse_int(str(row.get("population") or ""))
            if name and population is not None:
                name_population[name] = population
        loaded.append("name_frequency")

    if isinstance(entries.get("surname_frequency"), dict):
        text = _read_generated_table(root, str(entries["surname_frequency"].get("path") or ""))
        _validate_manifest_entry(manifest, code, "surname_frequency", text)
        for row in csv.DictReader(text.splitlines()):
            surname = str(row.get("surname") or "").strip().upper()
            population = _parse_int(str(row.get("population") or ""))
            if surname and population is not None:
                surname_population[surname] = population
        loaded.append("surname_frequency")

    if isinstance(entries.get("role_frequency"), dict):
        text = _read_generated_table(root, str(entries["role_frequency"].get("path") or ""))
        _validate_manifest_entry(manifest, code, "role_frequency", text)
        for row in csv.DictReader(text.splitlines()):
            role = _role_key(str(row.get("role") or ""))
            population = _parse_int(str(row.get("population") or ""))
            if role and population is not None:
                role_population[role] = population
        loaded.append("role_frequency")

    if not loaded:
        return None
    total_population = (
        sum(area_population.values())
        or sum(postal_population.values())
        or sum(name_population.values())
        or sum(surname_population.values())
        or sum(role_population.values())
    )
    if not total_population:
        raise RuntimeError(f"{code} generated frequency tables have no population rows")
    return _Tables(
        jurisdiction=code,
        total_population=total_population,
        area_population=area_population,
        age_cohorts=age_cohorts,
        postal_population=postal_population,
        name_population=name_population,
        surname_population=surname_population,
        role_population=role_population,
        loaded_tables=tuple(sorted(loaded)),
    )


def _tables_for(jurisdiction: str) -> _Tables | None:
    code = jurisdiction.upper()
    base_dir = os.environ.get("KAYPOH_FREQUENCY_DATA_DIR", "").strip()
    if base_dir:
        cache_key = (code, str(Path(base_dir).resolve()))
        if cache_key not in _GENERATED_TABLES:
            try:
                _GENERATED_TABLES[cache_key] = _load_generated_tables(code, base_dir)
            except Exception:
                _GENERATED_TABLES[cache_key] = None
        if _GENERATED_TABLES[cache_key] is not None:
            return _GENERATED_TABLES[cache_key]
    if code not in _BUNDLED_TABLES:
        try:
            _BUNDLED_TABLES[code] = _load_bundled_tables(code)
        except Exception:
            _BUNDLED_TABLES[code] = None
    return _BUNDLED_TABLES[code]


def clear_table_cache_for_tests() -> None:
    _BUNDLED_TABLES.clear()
    _GENERATED_TABLES.clear()


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
    code = tables.jurisdiction.upper()
    if code == "UK":
        for match in _UK_POSTCODE_RE.finditer(unit_text):
            prefix = f"{match.group(1).upper()} {match.group(2)}"
            if prefix in tables.postal_population:
                populations.append(tables.postal_population[prefix])
    elif code == "AU":
        for match in _AU_POSTAL_RE.finditer(unit_text):
            prefix = match.group(1)
            if prefix in tables.postal_population:
                populations.append(tables.postal_population[prefix])
    else:
        for match in _SG_POSTAL_RE.finditer(unit_text):
            prefix = match.group(1)[:2] if code == "SG" else match.group(1).upper()
            if prefix in tables.postal_population:
                populations.append(tables.postal_population[prefix])
    return min(populations) if populations else None


def _frequency_key(value: str) -> str | None:
    parts = [match.group(0).upper() for match in _FREQUENCY_KEY_RE.finditer(str(value or ""))]
    return " ".join(parts) if parts else None


def _role_key(value: str) -> str | None:
    key = _frequency_key(value)
    if not key:
        return None
    trimmed = _ROLE_PREFIX_RE.sub("", key).strip()
    return trimmed or key


def _surname_from_name(value: str) -> str | None:
    stripped = _NAME_PREFIX_RE.sub("", str(value or "").strip())
    tokens = [
        match.group(0).replace("'", "").replace("-", "").upper()
        for match in _SURNAME_TOKEN_RE.finditer(stripped)
    ]
    return tokens[-1] if tokens else None


def _given_from_name(value: str) -> str | None:
    stripped = _NAME_PREFIX_RE.sub("", str(value or "").strip())
    for match in _SURNAME_TOKEN_RE.finditer(stripped):
        return match.group(0).replace("'", "").replace("-", "").upper()
    return None


def _name_population(findings: list[Any], tables: _Tables) -> tuple[int, str] | None:
    populations: list[tuple[int, str]] = []
    for finding in findings:
        if str(getattr(finding, "rule", "")) != "named_person":
            continue
        value = str(getattr(finding, "matched_text", ""))
        name_key = _frequency_key(_NAME_PREFIX_RE.sub("", value).strip())
        if name_key and name_key in tables.name_population:
            populations.append((tables.name_population[name_key], "name_frequency"))
        given = _given_from_name(value)
        if given and given in tables.name_population:
            populations.append((tables.name_population[given], "name_frequency"))
        surname = _surname_from_name(value)
        if surname and surname in tables.surname_population:
            populations.append((tables.surname_population[surname], "surname_frequency"))
    return min(populations, key=lambda item: item[0]) if populations else None


def _role_population(findings: list[Any], tables: _Tables) -> int | None:
    populations: list[int] = []
    for finding in findings:
        if str(getattr(finding, "rule", "")) != "personal_attribute_inference":
            continue
        metadata = getattr(finding, "metadata", {}) or {}
        value = metadata.get("inferred_value")
        if not isinstance(value, str):
            continue
        candidates = [key for key in (_frequency_key(value), _role_key(value)) if key]
        for key in candidates:
            if key in tables.role_population:
                populations.append(tables.role_population[key])
                break
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
        postal_table = (
            "postal_sector_population" if "postal_sector_population" in tables.loaded_tables else "postal_population"
        )
        used.append(postal_table)
    elif rules & _POSTAL_RULES:
        missing.append("postal_population")

    if "named_person" in rules:
        name_population = _name_population(findings, tables)
        if name_population is not None:
            population, table = name_population
            estimates.append(population)
            used.append(table)
        else:
            missing.append("name_density")
    if "personal_attribute_inference" in rules:
        role_population = _role_population(findings, tables)
        if role_population is not None:
            estimates.append(role_population)
            used.append("role_frequency")
        else:
            missing.append("role_rarity")

    if not estimates:
        return tables.total_population, used, sorted(set(missing))
    k = max(1, min(estimates))
    return k, sorted(set(used)), sorted(set(missing))


def _locality_evidence(unit_text: str, findings: list[Any], tables: _Tables) -> list[dict[str, Any]]:
    evidence: list[dict[str, Any]] = []
    postal_population = _postal_population(unit_text, tables)
    if postal_population is not None:
        evidence.append({"kind": "postal_population", "population": postal_population})
    area_population = _area_population(unit_text, tables)
    if area_population is not None:
        evidence.append({"kind": "area_population", "population": area_population})
    for finding in findings:
        if str(getattr(finding, "rule", "")) != "personal_attribute_inference":
            continue
        metadata = getattr(finding, "metadata", {}) or {}
        if metadata.get("attribute_type") != "location":
            continue
        value = metadata.get("inferred_value")
        if isinstance(value, str) and value.strip():
            evidence.append({"kind": "inferred_location", "value": value.strip()})
    return evidence


def _component_spans(findings: list[Any]) -> list[dict[str, Any]]:
    spans: list[dict[str, Any]] = []
    for finding in sorted(findings, key=lambda item: (int(item.start_char), int(item.end_char), str(item.rule))):
        spans.append(
            {
                "rule": str(getattr(finding, "rule", "")),
                "start_char": int(getattr(finding, "start_char", 0)),
                "end_char": int(getattr(finding, "end_char", 0)),
                "matched_text": str(getattr(finding, "matched_text", "")),
            }
        )
    return spans


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
            "components": _component_spans(group),
            "quasi_identifier_component_spans": _component_spans(group),
            "legal_basis": legal_basis,
        }
        if rules & _LOCALITY_RULES:
            locality = _locality_evidence(unit_text, group, tables)
            if locality:
                metadata["locality_evidence"] = locality
        out.append(
            SinglingOutSpec(
                severity=_severity_for_k(k),
                matched_text=str(getattr(document_structure, "text", "")[start:end]) if document_structure else "",
                start_char=start,
                end_char=end,
                reason=(
                    f"{len(rules)} quasi-identifier rules co-occur in one {unit_kind}; "
                    f"{tables.jurisdiction} population-prior estimate k={k}"
                ),
                metadata=metadata,
            )
        )
    return out
