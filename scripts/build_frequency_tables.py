#!/usr/bin/env python3
"""Build generated population-prior frequency tables from aggregate extracts."""

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
import xml.etree.ElementTree as ET
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
DEFAULT_SUPPORTED = ("UK", "AU", "JP", "KR", "US")
SUPPORTED = ("SG", *DEFAULT_SUPPORTED)
SUPPORTED_TABLES = (
    "default",
    "postal_population",
    "area_population",
    "surname_frequency",
    "name_frequency",
    "role_frequency",
)
POSTAL_COLUMNS = ("postal_prefix", "postal_code", "postcode", "postcode_sector", "postcode_sectors",
                  "postcodesectors", "poa_code_2021", "poa_code21", "poa_code", "area_code", "code")
AREA_COLUMNS = ("area", "area_name", "municipality", "prefecture", "region", "admin_area", "name", "地域", "市区町村",
                "都道府県", "행정구역", "시도", "시도명", "시군구", "시군구명")
SURNAME_COLUMNS = ("surname", "name")
NAME_COLUMNS = ("name", "full_name", "fullname", "given_name", "givenname", "first_name", "firstname")
ROLE_COLUMNS = ("role", "occupation", "job_title", "jobtitle", "title")
POPULATION_COLUMNS = ("population", "total_population", "usual_residents", "persons", "total_persons", "tot_p_p",
                      "total", "count", "総数", "人口", "인구", "총인구", "계")
UK_POSTCODE_RE = re.compile(r"\b([A-Z]{1,2}\d[A-Z\d]?)\s*(\d)(?:[A-Z]{2})?\b", re.IGNORECASE)
AU_POSTCODE_RE = re.compile(r"(\d{4})")


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
        source_url="https://www.nomisweb.co.uk/output/census/2021/pcds_p003.csv",
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
        source_url="https://www.abs.gov.au/census/find-census-data/datapacks/download/2021_GCP_POA_for_AUS_short-header.zip",
        license="Creative Commons Attribution 4.0 International",
        license_url="https://creativecommons.org/licenses/by/4.0/",
        attribution="Based on Australian Bureau of Statistics DataPacks data",
        license_scope="DataPacks readme licenses the product under CC BY 4.0 with ABS attribution",
        redistribution="bundle_allowed_with_attribution",
    ),
    "JP": JurisdictionSpec(
        jurisdiction="JP",
        table="area_population",
        source_name="e-Stat municipality or prefecture population extract",
        source_url="https://www.e-stat.go.jp/en/stat-search/file-download?fileKind=4&statInfId=000013168605",
        license="e-Stat Terms of Use compatible with CC BY 4.0",
        license_url="https://www.e-stat.go.jp/en/terms-of-use",
        attribution="Created by editing statistics from e-Stat / Portal Site of Official Statistics of Japan",
        license_scope="e-Stat numerical data may be used freely; content terms are compatible with CC BY 4.0",
        redistribution="bundle_allowed_for_numerical_data_with_source_citation",
    ),
    "KR": JurisdictionSpec(
        jurisdiction="KR",
        table="area_population",
        source_name="MOIS resident-registration population by administrative dong extract",
        source_url="https://www.data.go.kr/cmm/cmm/fileDownload.do?atchFileId=FILE_000000003649470&fileDetailSn=1&insertDataPrcus=N",
        license="Open Government Data Portal scope of use: limitless",
        license_url="https://www.data.go.kr/en/ugs/selectPortalPolicyView.do",
        attribution="Source: Ministry of the Interior and Safety via Korea Open Government Data Portal",
        license_scope=(
            "Dataset metadata says file data downloads require no login and use-permission range is limitless"
        ),
        redistribution="bundle_allowed_with_source_citation",
    ),
    "US": JurisdictionSpec(
        jurisdiction="US",
        table="surname_frequency",
        source_name="U.S. Census Bureau 2010 Census surnames frequency table",
        source_url="https://www2.census.gov/topics/genealogy/2010surnames/names.zip",
        license="U.S. federal public-domain data, 17 U.S.C. §105",
        license_url="https://www.govinfo.gov/content/pkg/USCODE-2018-title17/pdf/USCODE-2018-title17-chap1-sec105.pdf",
        attribution="U.S. Census Bureau, Names_2010Census.csv, 2010 Census surnames",
        license_scope=(
            "Census data files are U.S. federal government data; citation guidance asks for Census Bureau attribution"
        ),
        redistribution="bundle_allowed_public_domain_with_attribution",
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


def _decode_csv_payload(payload: bytes) -> str:
    for encoding in ("utf-8-sig", "cp949", "euc-kr"):
        try:
            return payload.decode(encoding)
        except UnicodeDecodeError:
            continue
    return payload.decode("utf-8-sig", errors="replace")


def _iter_csv_payloads(payload: bytes, source_name: str) -> Iterable[tuple[str, str]]:
    with tempfile.NamedTemporaryFile(suffix=Path(source_name).suffix) as tmp:
        tmp.write(payload)
        tmp.flush()
        if zipfile.is_zipfile(tmp.name):
            with zipfile.ZipFile(tmp.name) as zf:
                for name in zf.namelist():
                    if name.lower().endswith(".csv"):
                        yield name, _decode_csv_payload(zf.read(name))
            return
    yield source_name, _decode_csv_payload(payload)


def _xlsx_shared_strings(zf: zipfile.ZipFile) -> list[str]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    if "xl/sharedStrings.xml" not in zf.namelist():
        return []
    root = ET.fromstring(zf.read("xl/sharedStrings.xml"))
    out: list[str] = []
    for item in root.findall("a:si", ns):
        out.append("".join(text.text or "" for text in item.findall(".//a:t", ns)))
    return out


def _xlsx_cell_value(cell: ET.Element, shared_strings: list[str]) -> str:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    value = cell.find("a:v", ns)
    if value is None or value.text is None:
        return ""
    if cell.attrib.get("t") == "s":
        return shared_strings[int(value.text)]
    return value.text


def _jp_prefecture_records_from_xlsx(payload: bytes) -> dict[str, int]:
    ns = {"a": "http://schemas.openxmlformats.org/spreadsheetml/2006/main"}
    records: dict[str, int] = {}
    with tempfile.NamedTemporaryFile(suffix=".xlsx") as tmp:
        tmp.write(payload)
        tmp.flush()
        if not zipfile.is_zipfile(tmp.name):
            return {}
        with zipfile.ZipFile(tmp.name) as zf:
            if "xl/worksheets/sheet3.xml" not in zf.namelist():
                return {}
            shared_strings = _xlsx_shared_strings(zf)
            root = ET.fromstring(zf.read("xl/worksheets/sheet3.xml"))
            for row in root.findall(".//a:sheetData/a:row", ns):
                cells = {
                    cell.attrib.get("r", ""): _xlsx_cell_value(cell, shared_strings)
                    for cell in row.findall("a:c", ns)
                }
                row_no = row.attrib.get("r", "")
                pref = re.sub(r"[\s\u3000]+", "", cells.get(f"C{row_no}", ""))
                population = _parse_int(cells.get(f"J{row_no}", ""))
                if not pref or population is None:
                    continue
                if not cells.get(f"B{row_no}", "").isdigit():
                    continue
                records[pref] = population * 1000
    return records


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


def _kr_area_key(row: dict[str, str]) -> str | None:
    sido = str(row.get("시도명") or row.get("시도") or "").strip()
    sigungu = str(row.get("시군구명") or row.get("시군구") or "").strip()
    if not sido:
        return None
    short_sido = re.sub(r"(특별자치시|특별자치도|특별시|광역시|도)$", "", sido)
    return " ".join(part for part in (short_sido, sigungu) if part).strip()


def _records_from_csv(text: str, spec: JurisdictionSpec) -> dict[str, int]:
    reader = csv.DictReader(io.StringIO(text))
    if not reader.fieldnames:
        return {}
    if spec.table in {"name_frequency", "role_frequency"}:
        key_col = _column(reader.fieldnames, NAME_COLUMNS if spec.table == "name_frequency" else ROLE_COLUMNS)
        population_col = _column(reader.fieldnames, POPULATION_COLUMNS)
        if not key_col or not population_col:
            return {}
        out: dict[str, int] = {}
        for row in reader:
            raw_key = str(row.get(key_col) or "").strip()
            key = re.sub(r"\s+", " ", raw_key).upper()
            population = _parse_int(str(row.get(population_col) or ""))
            if key and population is not None:
                out[key] = out.get(key, 0) + population
        return out
    if spec.table == "surname_frequency":
        key_col = _column(reader.fieldnames, SURNAME_COLUMNS)
        population_col = _column(reader.fieldnames, POPULATION_COLUMNS)
        if not key_col or not population_col:
            return {}
        out: dict[str, int] = {}
        for row in reader:
            raw_surname = str(row.get(key_col) or "").strip().upper()
            if raw_surname in {"ALL OTHER NAMES", "OTHER NAMES", "TOTAL"}:
                continue
            surname = re.sub(r"[^A-Z]", "", raw_surname)
            population = _parse_int(str(row.get(population_col) or ""))
            if surname and population is not None:
                out[surname] = population
        return out
    if spec.jurisdiction == "KR" and spec.table == "area_population":
        out: dict[str, int] = {}
        for row in reader:
            key = _kr_area_key(row)
            population = _parse_int(str(row.get("계") or row.get("총인구") or ""))
            if key and population is not None:
                out[key] = out.get(key, 0) + population
        return out
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
    if spec.jurisdiction == "JP" and spec.table == "area_population":
        records = _jp_prefecture_records_from_xlsx(payload)
        if records:
            return records
    merged: dict[str, int] = {}
    for name, text in _iter_csv_payloads(payload, source_ref):
        records = _records_from_csv(text, spec)
        if records:
            merged.update(records)
    if not merged:
        raise RuntimeError(f"{spec.jurisdiction}: no rows found with recognized {spec.table} columns")
    return merged


def _render_csv(table: str, records: dict[str, int]) -> str:
    if table == "postal_population":
        key = "postal_prefix"
    elif table == "surname_frequency":
        key = "surname"
    elif table == "name_frequency":
        key = "name"
    elif table == "role_frequency":
        key = "role"
    else:
        key = "area"
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


def _require_metadata(parser: argparse.ArgumentParser, args: argparse.Namespace, fields: tuple[str, ...]) -> None:
    missing = [field for field in fields if not str(getattr(args, field) or "").strip()]
    if missing:
        rendered = ", ".join(f"--{field.replace('_', '-')}" for field in missing)
        parser.error(f"--table {args.table} requires metadata: {rendered}")


def _spec_for(parser: argparse.ArgumentParser, args: argparse.Namespace, code: str) -> JurisdictionSpec:
    table = args.table
    if table == "default":
        if code not in SPECS:
            parser.error(f"{code} has no default public-source build; use --table name_frequency or role_frequency")
        return SPECS[code]
    if table in {"name_frequency", "role_frequency"}:
        _require_metadata(
            parser,
            args,
            ("source_name", "source_url", "license", "license_url", "attribution", "license_scope", "redistribution"),
        )
        return JurisdictionSpec(
            jurisdiction=code,
            table=table,
            source_name=args.source_name.strip(),
            source_url=args.source_url.strip(),
            license=args.license.strip(),
            license_url=args.license_url.strip(),
            attribution=args.attribution.strip(),
            license_scope=args.license_scope.strip(),
            redistribution=args.redistribution.strip(),
        )
    if code not in SPECS:
        parser.error(f"{code} has no built-in profile for --table {table}")
    spec = SPECS[code]
    if spec.table != table:
        parser.error(f"{code} default profile builds {spec.table}, not {table}")
    return spec


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
    parser.add_argument("--table", choices=SUPPORTED_TABLES, default="default")
    parser.add_argument("--source", action="append", default=[], help="JURISDICTION=path-or-url")
    parser.add_argument("--out", type=Path)
    parser.add_argument("--retrieved-date", default=date.today().isoformat())
    parser.add_argument("--refresh-days", type=int, default=365)
    parser.add_argument("--source-name", default="")
    parser.add_argument("--source-url", default="")
    parser.add_argument("--license", default="")
    parser.add_argument("--license-url", default="")
    parser.add_argument("--attribution", default="")
    parser.add_argument("--license-scope", default="")
    parser.add_argument("--redistribution", default="")
    parser.add_argument("--list-sources", action="store_true", help="print official source/licence profiles and exit")
    args = parser.parse_args(argv)

    if args.list_sources:
        jurisdictions = DEFAULT_SUPPORTED if args.jurisdiction in (None, "all") else (args.jurisdiction,)
        profiles = {code: SPECS[code].__dict__ for code in jurisdictions if code in SPECS}
        profiles["_custom_tables"] = {
            "tables": ["name_frequency", "role_frequency"],
            "required_metadata": [
                "source_name",
                "source_url",
                "license",
                "license_url",
                "attribution",
                "license_scope",
                "redistribution",
            ],
            "note": "Operator-supplied name/role tables are generated only from caller-provided licensed sources.",
        }
        print(json.dumps(profiles, indent=2, sort_keys=True))
        return 0
    if args.jurisdiction is None:
        parser.error("--jurisdiction is required unless --list-sources is set")
    jurisdictions = SUPPORTED if args.jurisdiction == "all" else (args.jurisdiction,)
    if args.out is None:
        parser.error("--out is required unless --list-sources is set")
    sources = _source_map(args.source)
    retrieved = date.fromisoformat(args.retrieved_date)
    if args.refresh_days <= 0:
        parser.error("--refresh-days must be positive")
    missing = [code for code in jurisdictions if code not in sources]
    if missing:
        print(f"missing --source for: {', '.join(missing)}", file=sys.stderr)
        return 2
    for code in jurisdictions:
        _build_one(_spec_for(parser, args, code), sources[code], args.out, retrieved, args.refresh_days)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
