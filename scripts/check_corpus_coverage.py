#!/usr/bin/env python3
"""Gate reviewed fixture corpora by coverage class."""

from __future__ import annotations

import argparse
import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CORPUS = ROOT / "test" / "fixtures" / "legal-corpus-reviewed-candidates"
DEFAULT_MINIMA = {
    "fixtures": 50,
    "adversarial": 50,
    "ocr_broken_run": 1,
    "multilingual": 1,
    "address": 1,
    "special_category": 1,
    "sector_mnpi": 1,
}
SPECIAL_CATEGORY_RULES = {
    "religious_belief",
    "trade_union_membership",
    "political_opinion",
    "racial_ethnic_origin",
    "health_condition",
    "medical_treatment",
    "biometric_identifier",
    "genetic_data",
    "sexual_orientation",
    "sex_life_reference",
}
SECTOR_MNPI_RULES = {
    "cyber_incident_pre_disclosure",
    "pharma_trial_mnpi",
    "financial_services_regulatory_mnpi",
    "energy_reserves_mnpi",
    "legal_proceeding_mnpi",
}


def _load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _iter_labels(payload: dict[str, Any]) -> list[dict[str, Any]]:
    labels: list[dict[str, Any]] = []
    for key in ("must_detect", "ideal_must_detect"):
        raw = payload.get(key, [])
        if isinstance(raw, list):
            labels.extend(item for item in raw if isinstance(item, dict))
    return labels


def _taxonomy(label: dict[str, Any]) -> str:
    return str(label.get("_taxonomy_concept") or label.get("taxonomy_concept") or "").strip()


def _rule(label: dict[str, Any]) -> str:
    return str(label.get("rule") or label.get("rule_name") or "").strip()


def _is_multilingual(text: str, labels: list[dict[str, Any]]) -> bool:
    if any(ord(ch) > 127 for ch in text):
        return True
    return any(ord(ch) > 127 for label in labels for ch in str(label.get("matched_text") or ""))


def _is_ocr_broken_run(text: str, labels: list[dict[str, Any]]) -> bool:
    probe = f"{text}\n" + "\n".join(str(label.get("matched_text") or "") for label in labels)
    if any(ch in probe for ch in ("\u200b", "\ufb01", "\ufb02")):
        return True
    if any(term in probe.casefold() for term in ("ocr", "broken run", "broken-run", "image-only", "scanned")):
        return True
    return bool(any(pattern in probe for pattern in ("S 1234567 D", "S\n1234567D", "A 1234567 Z")))


def _classify_fixture(txt_path: Path) -> set[str]:
    label_path = txt_path.with_suffix(".labels.json")
    text = txt_path.read_text(encoding="utf-8")
    payload = _load_json(label_path) if label_path.is_file() else {}
    labels = _iter_labels(payload)
    rules = {_rule(label) for label in labels}
    taxonomies = {_taxonomy(label) for label in labels}
    doc_id = str(payload.get("doc_id") or txt_path.stem).casefold()
    tags: set[str] = {"fixtures"}
    if "adversarial" in doc_id or "negative" in doc_id or "must_not" in payload:
        tags.add("adversarial")
    if _is_multilingual(text, labels):
        tags.add("multilingual")
    if _is_ocr_broken_run(text, labels):
        tags.add("ocr_broken_run")
    if any("address" in rule for rule in rules):
        tags.add("address")
    if taxonomies & {"special_category", "special_category_pii"} or rules & SPECIAL_CATEGORY_RULES:
        tags.add("special_category")
    if taxonomies & {"sector_mnpi", "jurisdictional_mnpi"} or rules & SECTOR_MNPI_RULES:
        tags.add("sector_mnpi")
    if taxonomies & {"quasi_identifiers", "singling_out"} or "quasi_identifier_combination" in rules:
        tags.add("quasi_identifier")
    return tags


def _parse_minima(values: list[str]) -> dict[str, int]:
    minima = dict(DEFAULT_MINIMA)
    for value in values:
        if "=" not in value:
            raise ValueError("--min must use TAG=COUNT")
        tag, count = value.split("=", 1)
        minima[tag.strip()] = int(count)
    return minima


def coverage_report(corpus: Path, minima: dict[str, int]) -> dict[str, Any]:
    if not corpus.is_dir():
        return {
            "status": "missing_corpus",
            "corpus": str(corpus),
            "counts": {},
            "minima": minima,
            "missing": dict(minima),
            "fixtures_by_tag": {},
        }
    counts: Counter[str] = Counter()
    fixtures_by_tag: dict[str, list[str]] = defaultdict(list)
    for txt_path in sorted(corpus.glob("*.txt")):
        tags = _classify_fixture(txt_path)
        for tag in tags:
            counts[tag] += 1
            fixtures_by_tag[tag].append(txt_path.name)
    missing = {tag: needed - counts.get(tag, 0) for tag, needed in minima.items() if counts.get(tag, 0) < needed}
    return {
        "status": "pass" if not missing else "fail",
        "corpus": str(corpus),
        "counts": dict(sorted(counts.items())),
        "minima": minima,
        "missing": missing,
        "fixtures_by_tag": {tag: names for tag, names in sorted(fixtures_by_tag.items())},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Check reviewed corpus coverage classes")
    parser.add_argument("--corpus", type=Path, default=DEFAULT_CORPUS)
    parser.add_argument("--min", action="append", default=[], help="coverage minimum as TAG=COUNT")
    args = parser.parse_args(argv)
    try:
        minima = _parse_minima(args.min)
    except ValueError as exc:
        parser.error(str(exc))
    report = coverage_report(args.corpus, minima)
    print(json.dumps(report, indent=2, sort_keys=True))
    if report["status"] == "missing_corpus":
        return 2
    return 0 if report["status"] == "pass" else 1


if __name__ == "__main__":
    raise SystemExit(main())
