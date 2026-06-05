"""SGLB-06 Rules-of-Court-2021 dataset builder.

Reads the same SSO JSONL as SGLB-02 (one section per row), filters to
``chapter_number == "ROC2021"``, and emits one case per Rule. Each case
asks "Given the following procedural scenario, which Order and Rule of
the Rules of Court 2021 applies?" and expects a JSON array of
``O. <N>, r. <M>`` labels.

Mechanical extraction:
- Scenario = the Rule's own scope/heading text (first paragraph after
  the leading number, stripped of citation chrome).
- Gold label = ``O. <order>, r. <rule>`` derived from the Order header
  that wraps the section and the section number itself.

The builder cannot run end-to-end until ``make ingest-sso
SSO_CODE=ROC2021`` materialises ROC2021 sections into the SSO JSONL.
The runner + scorers + spec ship now (matches the SGLB-04 "smoke"
pattern) so the harness has a complete v0.1 shape.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator

import yaml

from data.ingestion import sso
from data.ingestion._provenance import extraction_rule_sha

DATASET_VERSION = "sglb-06-v0.1"
ROC_CHAPTER_NUMBER = "ROC2021"
_MIN_SCENARIO_LEN = 100
_MAX_SCENARIO_CHARS = 600

_ORDER_RE = re.compile(r"\bOrder\s+(\d+[A-Z]?)\b", re.IGNORECASE)
_RULE_NUM_RE = re.compile(r"^\s*(\d+[A-Z]?)\b")
_REPEALED_RE = re.compile(r"\[Repealed\]", re.IGNORECASE)


@dataclass
class Sglb06Case:
    case_id: str
    scenario: str
    order: str
    rule: str
    label: str  # "O. 9, r. 1"
    section_heading: str
    source_url: str
    version_id: str
    valid_start_date: str
    extraction_rule_sha: str
    split: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "extraction_rule_sha": self.extraction_rule_sha,
            "inputs": {"scenario": self.scenario},
            "expected_output": {"labels": [self.label]},
            "metadata": {
                "task": "SGLB-06",
                "split": self.split,
                "jurisdiction": "SG",
                "order": self.order,
                "rule": self.rule,
                "section_heading": self.section_heading,
                "source_url": self.source_url,
                "version_id": self.version_id,
                "valid_start_date": self.valid_start_date,
                "dataset_version": DATASET_VERSION,
                "source_adapter": "api.adapters.public.sso.SsoAdapter",
                "label_provenance": "mechanical-extraction-from-roc2021-section-scope",
            },
        }


def _normalise_label(order: str, rule: str) -> str:
    return f"O. {order}, r. {rule}"


def _order_from_part(part_text: str) -> str:
    """Extract numeric Order from an SSO ``part`` heading like
    ``"Order 9 PRE-ACTION PROTOCOLS AND ORIGINATING PROCESSES"``."""
    match = _ORDER_RE.search(part_text or "")
    return match.group(1) if match else ""


def _strip_number_prefix(text: str, rule_number: str) -> str:
    pattern = re.compile(rf"^{re.escape(rule_number)}\.\s*(?:—\s*)?")
    return pattern.sub("", text).strip()


def _first_paragraph(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text).strip()
    if len(cleaned) <= _MAX_SCENARIO_CHARS:
        return cleaned
    cut = cleaned[: _MAX_SCENARIO_CHARS + 1]
    last_period = cut.rfind(". ")
    if last_period >= int(_MAX_SCENARIO_CHARS * 0.5):
        return cut[: last_period + 1].strip()
    return cleaned[:_MAX_SCENARIO_CHARS].rstrip() + "…"


def _stable_case_id(version_id: str, order: str, rule: str) -> str:
    sid = re.sub(
        r"[^A-Za-z0-9]+", "_", f"{version_id}:o{order}:r{rule}"
    ).strip("_")
    return f"sglb_06_{sid}"


def _assign_split(idx: int) -> str:
    bucket = idx % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def _source_rule_sha(row: dict) -> str:
    return str(row.get("extraction_rule_sha") or "").strip() or extraction_rule_sha(sso.EXTRACTION_MODULE)


def _extraction_rules(cases: list[Sglb06Case]) -> dict[str, str]:
    shas = {case.extraction_rule_sha for case in cases if case.extraction_rule_sha}
    if not shas:
        shas = {extraction_rule_sha(sso.EXTRACTION_MODULE)}
    if len(shas) != 1:
        raise ValueError(f"mixed SSO extraction_rule_sha values: {sorted(shas)}")
    return {sso.EXTRACTION_RULE_NAME: next(iter(shas))}


def iter_cases(jsonl_path: Path) -> Iterator[Sglb06Case]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"SSO JSONL not found: {jsonl_path}")
    idx = 0
    with jsonl_path.open(encoding="utf-8") as handle:
        for line in handle:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            if str(row.get("chapter_number") or "") != ROC_CHAPTER_NUMBER:
                continue
            heading = str(row.get("name") or "").strip()
            if _REPEALED_RE.search(heading):
                continue
            text = str(row.get("text_plain") or "")
            rule_number = str(row.get("number") or "").strip()
            if not rule_number:
                continue
            part = str(row.get("part") or "")
            order = _order_from_part(part)
            if not order:
                continue
            scenario = _first_paragraph(_strip_number_prefix(text, rule_number))
            if len(scenario) < _MIN_SCENARIO_LEN:
                continue
            version_id = str(row.get("version_id") or "").strip()
            case = Sglb06Case(
                case_id=_stable_case_id(version_id or ROC_CHAPTER_NUMBER, order, rule_number),
                scenario=scenario,
                order=order,
                rule=rule_number,
                label=_normalise_label(order, rule_number),
                section_heading=heading,
                source_url=str(row.get("source_url") or ""),
                version_id=version_id,
                valid_start_date=str(row.get("valid_start_date") or ""),
                extraction_rule_sha=_source_rule_sha(row),
            )
            case.split = _assign_split(idx)
            idx += 1
            yield case


def build(jsonl_path: Path) -> list[Sglb06Case]:
    cases = list(iter_cases(jsonl_path))
    seen: set[str] = set()
    deduped: list[Sglb06Case] = []
    for case in cases:
        if case.case_id in seen:
            continue
        seen.add(case.case_id)
        deduped.append(case)
    deduped.sort(key=lambda c: (int(re.sub(r"[^0-9]", "", c.order) or "0"), c.rule, c.case_id))
    return deduped


def write_outputs(cases: list[Sglb06Case], yaml_path: Path, jsonl_dir: Path) -> dict[str, int]:
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(
        yaml.safe_dump(
            {
                "extraction_rules": _extraction_rules(cases),
                "cases": [c.as_dict() for c in cases],
            },
            sort_keys=False,
            default_flow_style=False,
            width=120,
            allow_unicode=True,
        ),
        encoding="utf-8",
    )
    jsonl_dir.mkdir(parents=True, exist_ok=True)
    counts: dict[str, int] = {"train": 0, "dev": 0, "test": 0}
    for split in counts:
        path = jsonl_dir / f"{split}.jsonl"
        with path.open("w", encoding="utf-8") as fp:
            for case in cases:
                if case.split != split:
                    continue
                payload = case.as_dict()
                payload["id"] = case.case_id
                fp.write(json.dumps(payload, sort_keys=True) + "\n")
                counts[split] += 1
    return counts


def main(argv: list[str] | None = None) -> int:
    root = Path(__file__).resolve().parents[3]
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_06")
    parser.add_argument(
        "--input",
        default=str(root / "backend" / "vendor-data" / "sso" / "statutes.jsonl"),
    )
    parser.add_argument(
        "--yaml",
        default=str(root / "backend" / "benchmark" / "datasets" / "sglb_06_roc_2021.yaml"),
    )
    parser.add_argument(
        "--output",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_06_roc_2021"),
    )
    args = parser.parse_args(argv)

    cases = build(Path(args.input))
    counts = write_outputs(cases, Path(args.yaml), Path(args.output))
    print(
        json.dumps(
            {
                "total": len(cases),
                "by_split": counts,
                "dataset_version": DATASET_VERSION,
            },
            indent=2,
            sort_keys=True,
        )
    )
    if not cases:
        print(
            "note: 0 cases emitted. Run `make ingest-sso SSO_CODE=ROC2021` "
            "to materialise ROC 2021 sections into the SSO JSONL first.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
