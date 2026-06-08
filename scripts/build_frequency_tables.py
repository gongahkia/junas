#!/usr/bin/env python3
"""Build generated population-prior frequency tables from official aggregate extracts."""

from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import sys
import tempfile
import urllib.request
import zipfile
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

try:
    import tomllib
except ImportError:
    import tomli as tomllib

ROOT = Path(__file__).resolve().parent.parent
SUPPORTED = ("UK", "AU", "JP", "KR")
POSTAL_COLUMNS = ("postal_prefix", "postal_code", "postcode", "postcode_sector", "poa_code_2021", "poa_code21",
                  "poa_code", "area_code", "code")
AREA_COLUMNS = ("area", "area_name", "municipality", "prefecture", "region", "admin_area", "name", "地域", "市区町村",
                "都道府県", "행정구역", "시도", "시군구")
POPULATION_COLUMNS = ("population", "total_population", "usual_residents", "persons", "total_persons", "tot_p_p",
                      "total", "総数", "人口", "인구", "총인구")
UK_POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d)(?:[A-Z]{2})?\b", re.IGNORECASE)
AU_POSTCODE_RE = re.compile(r"\b(\d{4})\b")


@dataclass(frozen=True)
class JurisdictionSpec:
    jurisdiction: str
    table: str
    source_name: str
    source_url: str
    license: str
    license_url: str
    attribution: str
    license_scope: str
    redistribution: str
    excluded_regions: str = ""


SPECS = {
    "UK": JurisdictionSpec(
        jurisdiction="UK",
        table="postal_population",
        source_name="ONS/Nomis Census 2021 postcode-sector resident population extract",
        source_url="https://www.ons.gov.uk/methodology/geography/geographicalproducts/postcodeproducts",
        license="Open Government Licence v3.0",
        license_url="https://www.ons.gov.uk/methodology/geography/licences",
        attribution="Source: Office for National Statistics licensed under the Open Government Licence v.3.0",
        license_scope="ONS postcode products are OGL; BT/Northern Ireland postcodes need separate commercial licence",
        redistribution="bundle_allowed_excluding_bt",
        excluded_regions="Northern Ireland BT postcodes excluded unless separately licensed",
    ),
    "AU": JurisdictionSpec(
        jurisdiction="AU",
        table="postal_population",
        source_name="ABS 2021 Census DataPacks Postal Areas total persons extract",
        source_url="https://www.abs.gov.au/census/find-census-data/datapacks",
        license="ABS product licence displayed in source extract",
        license_url="https://www.abs.gov.au/about/legislation-and-policy/purchasing-data/abs-conditions-sale",
        attribution="Based on Australian Bureau of Statistics data",
        license_scope="ABS conditions say the licence displayed in the product controls reuse; verify before bundling",
        redistribution="operator_built_unbundled_until_product_licence_review",
    ),
    "JP": JurisdictionSpec(
        jurisdiction="JP",
        table="area_population",
        source_name="e-Stat municipality or prefecture population extract",
        source_url="https://www.e-stat.go.jp/en",
        license="e-Stat Terms of Use compatible with CC BY 4.0",
        license_url="https://www.e-stat.go.jp/en/terms-of-use",
        attribution="Created by editing statistics from e-Stat / Portal Site of Official Statistics of Japan",
        license_scope="e-Stat numerical data may be used freely; content terms are compatible with CC BY 4.0",
        redistribution="bundle_allowed_for_numerical_data_with_source_citation",
    ),
    "KR": JurisdictionSpec(
        jurisdiction="KR",
        table="area_population",
        source_name="KOSIS administrative-area population extract",
        source_url="https://kosis.kr/eng",
        license="KOSIS public data use policy",
        license_url="https://kosis.kr/eng/aboutKosis/policyPublicData.do",
        attribution="Source: KOSIS Korean Statistical Information Service",
        license_scope="KOSIS public data policy permits public-data use including profit purposes",
        redistribution="bundle_allowed_if_source_extract_terms_match_public_data_policy",
    ),
}


def _norm_header(value: str) -> str:
    return re.sub(r"[\s_\-().]+", "", value.strip().casefold())


def _parse_int(value: str) -> int | None:
    cleaned = re.sub(r"[^\d]", "", str(value or ""))
    if not cleaned:
        return None
    return int(cleaned)


def _read_source(source: str) -> tuple[bytes, str]:
    if re.match(r"https?://", source, re.IGNORECASE):
        with urllib.request.urlopen(source, timeout=60) as response:
            return response.read(), source
    path = Path(source)
    return path.read_bytes(), path.resolve().as_uri()


def _iter_csv_payloads(payload: bytes, source_name: str) -> Iterable[tuple[str, str]]:
    with tempfile.NamedTemporaryFile(suffix=Path(source_name).suffix) as tmp:
        tmp.write(payload)
        tmp.flush()
        if zipfile.is_zipfile(tmp.name):
            with zipfile.ZipFile(tmp.name) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".csv"):
                        yield name, zf.read(name).decode("utf-8-sig", errors="replace")
            return
    yield source_name, payload.decode("utf-8-sig", errors="replace")


def _column(fieldnames: list[str], candidates: tuple[str, ...]) -> str | None:
    normalized = {_norm_header(field): field for field in fieldnames}
    for candidate in candidates:
        field = normalized.get(_norm_header(candidate))
        if field:
            return field
    return None


def _uk_sector(value: str) -> str | None:
    candidate = str(value or "").strip().upper().replace(" ", "")
    if candidate.startswith("BT"):
        return None
    match = UK_POSTCODE_RE.search(candidate)
    if not match:
        return None
    return f"{match.group(1).upper()} {match.group(2)}"


def _au_postcode(value: str) -> str | None:
    match = AU_POSTCODE_RE.search(str(value or ""))
    return match.group(1) if match else None


def _postal_key(jurisdiction: str, value: str) -> str | None:
    if jurisdiction == "UK":
        return _uk_sector(value)
    if jurisdiction == "AU":
        return _au_postcode(value)
    value = str(value or "").strip().upper()
    return value or None


def _records_from_csv(text: str, spec: JurisdictionSpec) -> dict[str, int]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return {}
    key_col = _column(reader.fieldnames, POSTAL_COLUMNS if spec.table == "postal_population" else AREA_COLUMNS)
    population_col = _column(reader.fieldnames, POPULATION_COLUMNS)
    if not key_col or not population_col:
        return {}
    out: dict[str, int] = {}
    for row in reader:
        population = _parse_int(str(row.get(population_col) or ""))
        if population is None:
            continue
        raw_key = str(row.get(key_col) or "").strip()
        key = _postal_key(spec.jurisdiction, raw_key) if spec.table == "postal_population" else raw_key
        if not key:
            continue
        out[key] = out.get(key, 0) + population
    return out


def _build_records(payload: bytes, source_ref: str, spec: JurisdictionSpec) -> dict[str, int]:
    merged: dict[str, int] = {}
    for name, text in _iter_csv_payloads(payload, source_ref):
        records = _records_from_csv(text, spec)
        if records:
            merged.update(records)
    if not merged:
        raise RuntimeError(f"{spec.jurisdiction}: no rows found with recognized {spec.table} columns")
    return merged


def _render_csv(table: str, records: dict[str, int]) -> str:
    key = "postal_prefix" if table == "postal_population" else "area"
    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow([key, "population"])
    for value, population in sorted(records.items()):
        writer.writerow([value, population])
    return out.getvalue()


def _sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _load_manifest(path: Path) -> dict:
    if not path.is_file():
        return {"schema_version": 1, "generated_by": "scripts/build_frequency_tables.py"}
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    payload.setdefault("schema_version", 1)
    payload.setdefault("generated_by", "scripts/build_frequency_tables.py")
    return payload


def _toml_scalar(value: object) -> str:
    if isinstance(value, int):
        return str(value)
    return json.dumps(str(value))


def _render_manifest(payload: dict) -> str:
    lines: list[str] = []
    for key in ("schema_version", "generated_by"):
        if key in payload:
            lines.append(f"{key} = {_toml_scalar(payload[key])}")
    for jurisdiction in sorted(k for k, v in payload.items() if isinstance(v, dict)):
        for table in sorted(payload[jurisdiction]):
            lines.append("")
            lines.append(f"[{jurisdiction}.{table}]")
            for key, value in payload[jurisdiction][table].items():
                lines.append(f"{key} = {_toml_scalar(value)}")
    return "\n".join(lines) + "\n"


def _source_map(values: list[str]) -> dict[str, str]:
    out: dict[str, str] = {}
    for value in values:
        if "=" not in value:
            raise ValueError("--source must use JURISDICTION=path-or-url")
        jurisdiction, source = value.split("=", 1)
        out[jurisdiction.strip().upper()] = source.strip()
    return out


def _build_one(spec: JurisdictionSpec, source: str, out_dir: Path, retrieved_date: date, refresh_days: int) -> None:
    payload, source_ref = _read_source(source)
    records = _build_records(payload, source_ref, spec)
    csv_text = _render_csv(spec.table, records)
    table_dir = out_dir / spec.jurisdiction
    table_dir.mkdir(parents=True, exist_ok=True)
    table_path = table_dir / f"{spec.table}.csv"
    table_path.write_text(csv_text, encoding="utf-8")

    manifest_path = out_dir / "MANIFEST.generated.toml"
    manifest = _load_manifest(manifest_path)
    manifest.setdefault(spec.jurisdiction, {})
    manifest[spec.jurisdiction][spec.table] = {
        "path": f"{spec.jurisdiction}/{spec.table}.csv",
        "source_name": spec.source_name,
        "source_url": source_ref if source_ref.startswith("http") else spec.source_url,
        "license": spec.license,
        "license_url": spec.license_url,
        "attribution": spec.attribution,
        "license_scope": spec.license_scope,
        "redistribution": spec.redistribution,
        "retrieved_date": retrieved_date.isoformat(),
        "refresh_due_date": (retrieved_date + timedelta(days=refresh_days)).isoformat(),
        "sha256": _sha256_text(csv_text),
    }
    if spec.excluded_regions:
        manifest[spec.jurisdiction][spec.table]["excluded_regions"] = spec.excluded_regions
    manifest_path.write_text(_render_manifest(manifest), encoding="utf-8")
    print(f"{spec.jurisdiction}: wrote {len(records)} {spec.table} rows to {table_path}", file=sys.stderr)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Build generated keyless frequency tables")
    parser.add_argument("--jurisdiction", choices=(*SUPPORTED, "all"))
    parser.add_argument("--source", action="append", default=[], help="JURISDICTION=path-or-url")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--retrieved-date", default=date.today().isoformat())
    parser.add_argument("--refresh-days", type=int, default=365)
    parser.add_argument("--list-sources", action="store_true", help="print official source/licence profiles and exit")
    args = parser.parse_args(argv)

    if args.list_sources:
        jurisdictions = SUPPORTED if args.jurisdiction in (None, "all") else (args.jurisdiction,)
        print(json.dumps({code: SPECS[code].__dict__ for code in jurisdictions}, indent=2, sort_keys=True))
        return 0
    if args.jurisdiction is None:
        parser.error("--jurisdiction is required unless --list-sources is set")
    jurisdictions = SUPPORTED if args.jurisdiction == "all" else (args.jurisdiction,)
    if args.out is None:
        parser.error("--out is required unless --list-sources is set")
    sources = _source_map(args.source)
    retrieved = date.fromisoformat(args.retrieved_date)
    missing = [code for code in jurisdictions if code not in sources]
    if missing:
        print(f"missing --source for: {', '.join(missing)}", file=sys.stderr)
        return 2
    for code in jurisdictions:
        _build_one(SPECS[code], sources[code], args.out, retrieved, args.refresh_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
