"""SGLB-05 Employment-Issue dataset builder.

Reads MOM enforcement/guidance JSONL (one document per row, schema
produced by the planned ``data.ingestion.mom`` scraper, tracked as
[#59](https://github.com/gongahkia/junas/issues/59)) and emits one case
per scenario with multi-label issue tags.

Input schema (per MOM JSONL row, target):
- ``doc_id``: stable id
- ``source_url``: link to the published MOM page
- ``subsource``: ``"press_release" | "faq" | "advisory"``
- ``title``: document title
- ``body_plain``: published narrative text
- ``stated_breaches``: list[str] — MOM's own categorisation (gold labels)
- ``act_references``: list[str] — Employment Act sections referenced
- ``subject_organisation``: str | null
- ``pub_date``: ISO date string

Mechanical extraction rule:
- gold labels = ``stated_breaches`` verbatim from MOM (normalised to
  lowercase snake_case)
- scenario = ``body_plain`` with the published outcome verbs masked so
  the model cannot read its own answer back

The builder is **data-pending**: it ships v0.1 code so the harness has
the full shape; data lands once #59 produces ``backend/vendor-data/mom/
enforcement.jsonl``.
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

DATASET_VERSION = "sglb-05-v0.1"
_MIN_SCENARIO_LEN = 150
_MAX_SCENARIO_CHARS = 1200

# Outcome-leakage redaction patterns applied to body_plain → scenario.
# MOM press releases routinely state the outcome up front ("MOM imposed
# penalties for ..."); we mask the obvious leakage but preserve the
# factual narrative.
_REDACTORS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?:S\$|\$)\s*\d[\d,]*(?:\.\d{2})?", re.IGNORECASE), "[AMOUNT_REDACTED]"),
    (re.compile(r"\bMOM (?:imposed|took action against|issued)\b", re.IGNORECASE), "Action was taken in respect of"),
    (re.compile(r"\bcourt (?:fined|imposed)\b", re.IGNORECASE), "The matter was disposed of with"),
    (re.compile(r"\s{2,}"), " "),
)


@dataclass
class Sglb05Case:
    case_id: str
    scenario: str
    issue_labels: list[str]
    act_references: list[str]
    subsource: str
    pub_date: str
    source_url: str
    split: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "inputs": {"scenario": self.scenario},
            "expected_output": {"labels": list(self.issue_labels)},
            "metadata": {
                "task": "SGLB-05",
                "split": self.split,
                "jurisdiction": "SG",
                "subsource": self.subsource,
                "pub_date": self.pub_date,
                "source_url": self.source_url,
                "act_references": list(self.act_references),
                "dataset_version": DATASET_VERSION,
                "source_adapter": "api.adapters.public.mom.MomAdapter",
                "label_provenance": "mechanical-extraction-from-mom-stated-breaches",
            },
        }


def _normalise_issue(raw: str) -> str:
    """Normalise an MOM-stated breach label to lowercase snake_case."""
    s = (raw or "").strip().lower()
    s = re.sub(r"[^a-z0-9]+", "_", s)
    return s.strip("_")


def _normalise_issues(raw: list) -> list[str]:
    if not raw:
        return []
    seen: list[str] = []
    for item in raw:
        norm = _normalise_issue(str(item))
        if norm and norm not in seen:
            seen.append(norm)
    return seen


def _redact_scenario(body_plain: str) -> str:
    text = (body_plain or "").strip()
    for pattern, repl in _REDACTORS:
        text = pattern.sub(repl, text)
    if len(text) > _MAX_SCENARIO_CHARS:
        cut = text[: _MAX_SCENARIO_CHARS + 1]
        last_period = cut.rfind(". ")
        if last_period >= int(_MAX_SCENARIO_CHARS * 0.5):
            return cut[: last_period + 1].strip()
        return text[:_MAX_SCENARIO_CHARS].rstrip() + "…"
    return text


def _stable_case_id(doc_id: str) -> str:
    sid = re.sub(r"[^A-Za-z0-9]+", "_", doc_id).strip("_")
    return f"sglb_05_{sid}"


def _assign_split(idx: int) -> str:
    bucket = idx % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def iter_cases(jsonl_path: Path) -> Iterator[Sglb05Case]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"MOM JSONL not found: {jsonl_path}")
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
            doc_id = str(row.get("doc_id") or "")
            body = str(row.get("body_plain") or "")
            labels = _normalise_issues(row.get("stated_breaches") or [])
            if not doc_id or not labels:
                continue
            scenario = _redact_scenario(body)
            if len(scenario) < _MIN_SCENARIO_LEN:
                continue
            case = Sglb05Case(
                case_id=_stable_case_id(doc_id),
                scenario=scenario,
                issue_labels=labels,
                act_references=[str(x) for x in (row.get("act_references") or [])],
                subsource=str(row.get("subsource") or ""),
                pub_date=str(row.get("pub_date") or ""),
                source_url=str(row.get("source_url") or ""),
            )
            case.split = _assign_split(idx)
            idx += 1
            yield case


def build(jsonl_path: Path) -> list[Sglb05Case]:
    cases = list(iter_cases(jsonl_path))
    seen: set[str] = set()
    deduped: list[Sglb05Case] = []
    for case in cases:
        if case.case_id in seen:
            continue
        seen.add(case.case_id)
        deduped.append(case)
    deduped.sort(key=lambda c: (c.pub_date, c.case_id))
    return deduped


def write_outputs(cases: list[Sglb05Case], yaml_path: Path, jsonl_dir: Path) -> dict[str, int]:
    yaml_path.parent.mkdir(parents=True, exist_ok=True)
    yaml_path.write_text(
        yaml.safe_dump(
            {"cases": [c.as_dict() for c in cases]},
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
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_05")
    parser.add_argument(
        "--input",
        default=str(root / "backend" / "vendor-data" / "mom" / "enforcement.jsonl"),
    )
    parser.add_argument(
        "--yaml",
        default=str(root / "backend" / "benchmark" / "datasets" / "sglb_05_employment_issue.yaml"),
    )
    parser.add_argument(
        "--output",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_05_employment_issue"),
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
            "note: 0 cases emitted. Run the MOM scraper (#59) to "
            "materialise enforcement records into vendor-data/mom/enforcement.jsonl first.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
