"""SGLB-04 Citation-Verify dataset builder.

Builds deterministic SAL-grammar conformance cases for the production
Citation-Verify set. Labels are assigned only after the candidate string
is checked by ``api.services.sal_citation.validate_citation``.

CLI:
``python -m benchmark.dataset_builders.sglb_04``
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

import yaml

from api.services.sal_citation import validate_citation

DATASET_VERSION = "sglb-04-v0.1"
DEFAULT_N_PER_PERTURBATION = 120
DEFAULT_VALID_NEGATIVE_N = 240
EXTRACTION_RULE_NAME = "sglb_04_grammar_generation"
EXTRACTION_MODULE = Path(__file__)
REPO_ROOT = Path(__file__).resolve().parents[3]
DATASETS_DIR = REPO_ROOT / "backend" / "benchmark" / "datasets"
DEFAULT_FULL_OUTPUT = DATASETS_DIR / "sglb_04_citation_verify_full.yaml"
DEFAULT_SMOKE_SOURCE = DATASETS_DIR / "sglb_04_citation_verify.yaml"
DEFAULT_SMOKE_OUTPUT = DATASETS_DIR / "sglb_04_citation_verify_smoke.yaml"

PerturbationKind = Literal[
    "year_off",
    "volume_off",
    "page_off",
    "case_name_swap",
    "court_swap",
    "wholesale_fabrication",
    "composite",
]

PERTURBATION_KINDS: tuple[PerturbationKind, ...] = (
    "year_off",
    "volume_off",
    "page_off",
    "case_name_swap",
    "court_swap",
    "wholesale_fabrication",
    "composite",
)
VALID_NEGATIVE_STRATUM = "valid_negative"
VALID_COURTS: tuple[str, ...] = (
    "SGCA",
    "SGHC",
    "SGHCR",
    "SGDC",
    "SGMC",
    "SGFC",
    "SGCFI",
    "SGIA",
    "SGHCF",
    "SGSAC",
    "SGCT",
    "SGHC(A)",
    "SGHC(I)",
    "SGCA(I)",
    "SGSCT",
    "SGYC",
)
INVALID_COURTS: tuple[str, ...] = (
    "SGZZ",
    "SGCAA",
    "SGHCZ",
    "SGDCX",
    "SGMCQ",
    "SGTRIB",
    "SGAPEX",
    "SGCOURT",
)
SURNAMES: tuple[str, ...] = (
    "Tan",
    "Lim",
    "Lee",
    "Wong",
    "Chua",
    "Ong",
    "Goh",
    "Ng",
    "Teo",
    "Koh",
    "Yeo",
    "Soh",
    "Singh",
    "Kumar",
    "Rahman",
    "Pereira",
)
COMPANIES: tuple[str, ...] = (
    "Apex Trading Pte Ltd",
    "Meridian Holdings Pte Ltd",
    "Pioneer Marine Pte Ltd",
    "Sentinel Engineering Pte Ltd",
    "Stellar Logistics Pte Ltd",
    "Citadel Investments Pte Ltd",
)
STATUTES: tuple[tuple[str, int], ...] = (
    ("Penal Code", 224),
    ("Misuse of Drugs Act", 185),
    ("Companies Act", 50),
    ("Evidence Act", 97),
    ("Arbitration Act", 10),
    ("Personal Data Protection Act", 26),
    ("Employment Act", 91),
    ("Legal Profession Act", 161),
)


@dataclass(frozen=True)
class CitationTemplate:
    citation: str
    perturbation: str
    source_citation: str
    generation_rule: str


def _valid_year(i: int) -> int:
    return 1990 + ((i * 7) % 36)


def _bad_year(i: int) -> int:
    return 1800 + (i % 120) if i % 2 == 0 else 2101 + (i % 120)


def _party(i: int) -> str:
    if i % 5 == 0:
        return COMPANIES[i % len(COMPANIES)]
    return f"{SURNAMES[i % len(SURNAMES)]} {SURNAMES[(i * 3 + 1) % len(SURNAMES)]}"


def _case_name(i: int) -> str:
    return f"{_party(i)} v {_party(i + 5)}"


def _neutral_source(i: int, *, with_name: bool = False) -> str:
    body = f"[{_valid_year(i)}] {VALID_COURTS[i % len(VALID_COURTS)]} {1 + ((i * 17) % 500)}"
    return f"{_case_name(i)} {body}" if with_name else body


def _slr_source(i: int, *, with_name: bool = False) -> str:
    report = "SLR(R)" if i % 2 == 0 else "SLR"
    body = f"[{_valid_year(i)}] {1 + (i % 4)} {report} {1 + ((i * 37) % 1800)}"
    return f"{_case_name(i)} {body}" if with_name else body


def _stable_name(stratum: str, index: int, citation: str) -> str:
    digest = hashlib.sha256(citation.encode("utf-8")).hexdigest()[:10]
    clean = re.sub(r"[^a-z0-9]+", "_", stratum.lower()).strip("_")
    return f"sglb_04_{clean}_{index:04d}_{digest}"


def _assign_split(case_name: str) -> str:
    bucket = int(hashlib.sha256(case_name.encode("utf-8")).hexdigest()[:8], 16) % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def _error_codes(citation: str) -> tuple[str, ...]:
    return tuple(error.code for error in validate_citation(citation).errors)


def _builder_rule_sha() -> str:
    return hashlib.sha256(EXTRACTION_MODULE.read_bytes()).hexdigest()[:12]


def _valid_negative(i: int) -> CitationTemplate:
    year = _valid_year(i)
    court = VALID_COURTS[i % len(VALID_COURTS)]
    case_no = 1 + ((i * 19) % 600)
    volume = 1 + (i % 4)
    page = 1 + ((i * 41) % 1900)
    statute, cap = STATUTES[i % len(STATUTES)]
    family = i % 14
    if family == 0:
        citation = f"[{year}] {court} {case_no}"
    elif family == 1:
        citation = f"{_case_name(i)} [{year}] {court} {case_no}"
    elif family == 2:
        citation = f"[{year}] {court} {case_no} at [{1 + (i % 90)}]-[{2 + (i % 90)}]"
    elif family == 3:
        citation = f"[{year}] {court} {case_no} (\"{SURNAMES[i % len(SURNAMES)]}\")"
    elif family == 4:
        citation = f"[{year}] {volume} SLR(R) {page}"
    elif family == 5:
        citation = f"{_case_name(i)} [{year}] {volume} SLR(R) {page} at [{1 + (i % 70)}]"
    elif family == 6:
        citation = f"[{year}] {volume} SLR {page}"
    elif family == 7:
        citation = f"{_case_name(i)} [{year}] {volume} SLR {page} (CA)"
    elif family == 8:
        citation = f"{statute} (Cap. {cap}, {1998 + (i % 28)} Rev Ed) s {1 + i}"
    elif family == 9:
        citation = f"s {1 + (i % 250)} of the {statute}"
    elif family == 10:
        citation = f"at [{1 + (i % 100)}]"
    elif family == 11:
        citation = f"Ibid, at [{1 + i}]" if i % 2 == 0 else f"Id, at [{1 + i}]"
    elif family == 12:
        citation = f"{SURNAMES[i % len(SURNAMES)]}, supra n {1 + (i % 20)}, at [{1 + (i % 80)}]"
    else:
        citation = f"Criminal Procedure Reform Bill {year} (Bill No {1 + (i % 50)}/{year})"
    return CitationTemplate(citation, "none", "", "valid_negative")


def _year_off(i: int) -> CitationTemplate:
    source = _neutral_source(i) if i % 3 == 0 else _slr_source(i)
    citation = source.replace(f"[{_valid_year(i)}]", f"[{_bad_year(i)}]", 1)
    return CitationTemplate(citation, "year_off", source, "year_outside_1965_2100")


def _volume_off(i: int) -> CitationTemplate:
    report = "SLR(R)" if i % 2 == 0 else "SLR"
    source = _slr_source(i)
    citation = f"[{_valid_year(i)}] 0 {report} {1 + ((i * 43) % 1800)}"
    return CitationTemplate(citation, "volume_off", source, "slr_volume_zero")


def _page_off(i: int) -> CitationTemplate:
    report = "SLR(R)" if i % 2 == 0 else "SLR"
    volume = 1 + (i % 7)
    source = _slr_source(i)
    citation = f"[{_valid_year(i)}] {volume} {report} 0"
    return CitationTemplate(citation, "page_off", source, "slr_page_zero")


def _case_name_swap(i: int) -> CitationTemplate:
    source = _neutral_source(i, with_name=True)
    marker_year = 1990 + (i % 36)
    citation = (
        f"{_party(i)} [{marker_year}] Holdings "
        f"[{_valid_year(i)}] {VALID_COURTS[i % len(VALID_COURTS)]} {1 + ((i * 23) % 500)}"
    )
    return CitationTemplate(citation, "case_name_swap", source, "case_name_disrupts_citation_boundary")


def _court_swap(i: int) -> CitationTemplate:
    source = _neutral_source(i)
    citation = f"[{_valid_year(i)}] {INVALID_COURTS[i % len(INVALID_COURTS)]} {1 + ((i * 29) % 500)}"
    return CitationTemplate(citation, "court_swap", source, "unknown_sg_court_code")


def _wholesale_fabrication(i: int) -> CitationTemplate:
    year = _valid_year(i)
    court = VALID_COURTS[i % len(VALID_COURTS)]
    case_no = 1 + ((i * 31) % 600)
    options = (
        f"{year} {court} {case_no}",
        f"[{year}] Singapore Court of Appeal {case_no}",
        f"Citation No. {year}-{court}-{case_no}",
        f"{_party(i)} against {_party(i + 2)}, {year} {court} {case_no}",
        f"SG/{court}/{year}/{case_no}",
    )
    return CitationTemplate(options[i % len(options)], "wholesale_fabrication", "", "non_sal_citation_string")


def _composite(i: int) -> CitationTemplate:
    if i % 2 == 0:
        source = _neutral_source(i)
        citation = f"[{_bad_year(i)}] {INVALID_COURTS[i % len(INVALID_COURTS)]} 0"
    else:
        report = "SLR(R)" if i % 4 == 1 else "SLR"
        source = _slr_source(i)
        citation = f"[{_bad_year(i)}] 0 {report} 0"
    return CitationTemplate(citation, "composite", source, "multiple_sal_component_errors")


INVALID_GENERATORS = {
    "year_off": _year_off,
    "volume_off": _volume_off,
    "page_off": _page_off,
    "case_name_swap": _case_name_swap,
    "court_swap": _court_swap,
    "wholesale_fabrication": _wholesale_fabrication,
    "composite": _composite,
}


def _case_dict(template: CitationTemplate, index: int, rule_sha: str) -> dict[str, Any]:
    result = validate_citation(template.citation)
    expected_label = "valid" if template.perturbation == "none" else "invalid"
    actual_label = "valid" if result.valid else "invalid"
    if actual_label != expected_label:
        raise ValueError(f"{template.perturbation} generated {actual_label}: {template.citation!r}")
    stratum = VALID_NEGATIVE_STRATUM if expected_label == "valid" else template.perturbation
    name = _stable_name(stratum, index, template.citation)
    split = _assign_split(name)
    errors = _error_codes(template.citation)
    if expected_label == "invalid" and not errors:
        raise ValueError(f"invalid stratum has no grammar error: {template.citation!r}")
    breakdown = {
        "task": "SGLB-04",
        "stratum": stratum,
        "perturbation": template.perturbation,
        "validation_kind": result.kind,
        "expected_label": expected_label,
        "expected_errors": list(errors),
        "split": split,
    }
    return {
        "name": name,
        "extraction_rule_sha": rule_sha,
        "inputs": {"citation": template.citation},
        "expected_output": {"labels": [expected_label]},
        "metadata": {
            "task": "SGLB-04",
            "jurisdiction": "SG",
            "split": split,
            "kind": result.kind,
            "perturbation": template.perturbation,
            "stratum": stratum,
            "source_citation": template.source_citation,
            "generation_rule": template.generation_rule,
            "expected_errors": list(errors),
            "dataset_version": DATASET_VERSION,
            "data_tier": "synthetic",
            "source_grammar": "api.services.sal_citation.validate_citation",
            "label_provenance": "mechanical-generation-from-sal-grammar",
            "sal_validation_prerequisite": "backend/tests/test_sal_citation_published_examples.py",
            "breakdown": breakdown,
        },
    }


def _dedupe(cases: list[dict[str, Any]]) -> list[dict[str, Any]]:
    seen_names: set[str] = set()
    seen_citations: set[str] = set()
    for case in cases:
        name = str(case["name"])
        citation = " ".join(str(case["inputs"]["citation"]).split()).rstrip(".").lower()
        if name in seen_names:
            raise ValueError(f"duplicate case name: {name}")
        if citation in seen_citations:
            raise ValueError(f"duplicate citation: {case['inputs']['citation']!r}")
        seen_names.add(name)
        seen_citations.add(citation)
    return cases


def build_cases(
    *,
    n_per_perturbation: int = DEFAULT_N_PER_PERTURBATION,
    valid_negative_n: int = DEFAULT_VALID_NEGATIVE_N,
) -> list[dict[str, Any]]:
    if n_per_perturbation < 1:
        raise ValueError("n_per_perturbation must be positive")
    if valid_negative_n < 1:
        raise ValueError("valid_negative_n must be positive")
    rule_sha = _builder_rule_sha()
    cases: list[dict[str, Any]] = []
    for perturbation in PERTURBATION_KINDS:
        generator = INVALID_GENERATORS[perturbation]
        for i in range(n_per_perturbation):
            cases.append(_case_dict(generator(i), i, rule_sha))
    for i in range(valid_negative_n):
        cases.append(_case_dict(_valid_negative(i), i, rule_sha))
    return _dedupe(cases)


def build_dataset(
    *,
    n_per_perturbation: int = DEFAULT_N_PER_PERTURBATION,
    valid_negative_n: int = DEFAULT_VALID_NEGATIVE_N,
) -> dict[str, Any]:
    rule_sha = _builder_rule_sha()
    return {
        "extraction_rules": {EXTRACTION_RULE_NAME: rule_sha},
        "cases": build_cases(
            n_per_perturbation=n_per_perturbation,
            valid_negative_n=valid_negative_n,
        ),
    }


def stratum_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    return dict(Counter(str(case["metadata"]["stratum"]) for case in cases))


def split_counts(cases: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(case["metadata"]["split"]) for case in cases)
    return {split: counts.get(split, 0) for split in ("train", "dev", "test")}


def write_dataset(dataset: dict[str, Any], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        yaml.safe_dump(
            dataset,
            sort_keys=False,
            default_flow_style=False,
            width=120,
            allow_unicode=False,
        ),
        encoding="utf-8",
    )


def preserve_smoke_dataset(source: Path = DEFAULT_SMOKE_SOURCE, output: Path = DEFAULT_SMOKE_OUTPUT) -> None:
    if not source.exists():
        raise FileNotFoundError(f"smoke source not found: {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(source, output)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_04")
    parser.add_argument("--n-per-stratum", "--n-per-perturbation", type=int, default=DEFAULT_N_PER_PERTURBATION)
    parser.add_argument("--valid-negative-n", type=int, default=DEFAULT_VALID_NEGATIVE_N)
    parser.add_argument("--output", type=Path, default=DEFAULT_FULL_OUTPUT)
    parser.add_argument("--smoke-source", type=Path, default=DEFAULT_SMOKE_SOURCE)
    parser.add_argument("--smoke-output", type=Path, default=DEFAULT_SMOKE_OUTPUT)
    parser.add_argument("--skip-smoke-copy", action="store_true")
    args = parser.parse_args(argv)

    dataset = build_dataset(
        n_per_perturbation=args.n_per_stratum,
        valid_negative_n=args.valid_negative_n,
    )
    write_dataset(dataset, args.output)
    if not args.skip_smoke_copy:
        preserve_smoke_dataset(args.smoke_source, args.smoke_output)
    cases = list(dataset["cases"])
    print(
        json.dumps(
            {
                "total": len(cases),
                "by_stratum": stratum_counts(cases),
                "by_split": split_counts(cases),
                "dataset_version": DATASET_VERSION,
                "output": str(args.output),
                "smoke_output": "" if args.skip_smoke_copy else str(args.smoke_output),
            },
            indent=2,
            sort_keys=True,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
