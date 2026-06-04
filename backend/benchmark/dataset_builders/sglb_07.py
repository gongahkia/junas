"""SGLB-07 Jurisdiction-Routing dataset builder.

Reads a SG case-law JSONL (one judgment per row, schema produced by the
planned CommonLII SG ingest, dep on [#34](https://github.com/gongahkia/junas/issues/34))
and emits one case per judgment that contains an explicit
source-jurisdiction statement. The model classifies the
controlling-authority jurisdiction from the question.

Expected JSONL row schema (target, mechanical extraction only):
- ``case_id``: stable id
- ``citation``: neutral citation (e.g. ``[2018] SGCA 14``)
- ``court_code``: SGCA / SGHC / SGDC / SGMC / SGSAC
- ``decision_date``: ISO date string
- ``source_url``: canonical link (CommonLII or eLitigation public page)
- ``body_plain``: judgment text
- ``jurisdiction_statements``: list of dict pre-extracted by the
  ingestion step, each ``{"label": "uk_persuasive", "quote": "...",
  "paragraph": int}``. The ingestion step uses regex over the judgment
  body to locate the published court statement; this builder never
  makes the legal judgment itself.

Mechanical extraction rule:
- Gold label = first statement's ``label`` when the judgment has
  exactly one source-jurisdiction statement (multi-source cases are
  excluded from v0.1, per spec).
- Question = a procedural framing of the legal question the court
  answered, derived from the judgment's "Catchwords" section if
  present; otherwise the first ``question_template`` matching token in
  the body.

This is data-pending: the builder ships now so the harness has a
complete v0.1 shape; data lands once #34 produces ``backend/vendor-
data/sg_cases/judgments.jsonl``.
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

DATASET_VERSION = "sglb-07-v0.1"

VALID_LABELS: tuple[str, ...] = (
    "sg_binding",
    "uk_persuasive",
    "au_persuasive",
    "hk_persuasive",
    "not_applicable",
)

_MIN_QUESTION_LEN = 40
_MAX_QUESTION_CHARS = 600
_NEUTRAL_CITATION_RE = re.compile(r"\[\d{4}\]\s+SG[A-Z]+\s+\d+")


@dataclass
class Sglb07Case:
    case_id: str
    question: str
    label: str
    citation: str
    court_code: str
    decision_date: str
    source_url: str
    split: str = ""

    def as_dict(self) -> dict:
        return {
            "name": self.case_id,
            "inputs": {"question": self.question},
            "expected_output": {"labels": [self.label]},
            "metadata": {
                "task": "SGLB-07",
                "split": self.split,
                "jurisdiction": "SG",
                "citation": self.citation,
                "court_code": self.court_code,
                "decision_date": self.decision_date,
                "source_url": self.source_url,
                "dataset_version": DATASET_VERSION,
                "source_adapter": "api.adapters.public.commonlii_sg.CommonliiSgAdapter",
                "label_provenance": "mechanical-extraction-from-court-source-statement",
            },
        }


def _stable_case_id(case_id: str) -> str:
    sid = re.sub(r"[^A-Za-z0-9]+", "_", case_id).strip("_")
    return f"sglb_07_{sid}"


def _assign_split(idx: int) -> str:
    bucket = idx % 10
    if bucket < 8:
        return "train"
    if bucket == 8:
        return "dev"
    return "test"


def _trim_question(text: str) -> str:
    cleaned = re.sub(r"\s+", " ", text or "").strip()
    if not cleaned:
        return ""
    if len(cleaned) <= _MAX_QUESTION_CHARS:
        return cleaned
    cut = cleaned[: _MAX_QUESTION_CHARS + 1]
    last_period = cut.rfind(". ")
    if last_period >= int(_MAX_QUESTION_CHARS * 0.5):
        return cut[: last_period + 1].strip()
    return cleaned[:_MAX_QUESTION_CHARS].rstrip() + "…"


def _normalise_label(raw: str) -> str:
    s = (raw or "").strip().lower().replace("-", "_")
    return s if s in VALID_LABELS else ""


def iter_cases(jsonl_path: Path) -> Iterator[Sglb07Case]:
    if not jsonl_path.exists():
        raise FileNotFoundError(f"SG case JSONL not found: {jsonl_path}")
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
            case_id = str(row.get("case_id") or "")
            statements = row.get("jurisdiction_statements") or []
            # v0.1 excludes multi-source cases per spec.
            if not isinstance(statements, list) or len(statements) != 1:
                continue
            stmt = statements[0]
            if not isinstance(stmt, dict):
                continue
            label = _normalise_label(str(stmt.get("label") or ""))
            if not label:
                continue
            question = _trim_question(str(row.get("question") or row.get("catchwords") or ""))
            if len(question) < _MIN_QUESTION_LEN:
                continue
            citation = str(row.get("citation") or "")
            if citation and not _NEUTRAL_CITATION_RE.search(citation):
                # Non-SG citations should not slip into the corpus.
                continue
            case = Sglb07Case(
                case_id=_stable_case_id(case_id or citation or f"row_{idx}"),
                question=question,
                label=label,
                citation=citation,
                court_code=str(row.get("court_code") or ""),
                decision_date=str(row.get("decision_date") or ""),
                source_url=str(row.get("source_url") or ""),
            )
            case.split = _assign_split(idx)
            idx += 1
            yield case


def build(jsonl_path: Path) -> list[Sglb07Case]:
    cases = list(iter_cases(jsonl_path))
    seen: set[str] = set()
    deduped: list[Sglb07Case] = []
    for case in cases:
        if case.case_id in seen:
            continue
        seen.add(case.case_id)
        deduped.append(case)
    deduped.sort(key=lambda c: (c.decision_date, c.case_id))
    return deduped


def write_outputs(cases: list[Sglb07Case], yaml_path: Path, jsonl_dir: Path) -> dict[str, int]:
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
    parser = argparse.ArgumentParser(prog="benchmark.dataset_builders.sglb_07")
    parser.add_argument(
        "--input",
        default=str(root / "backend" / "vendor-data" / "sg_cases" / "judgments.jsonl"),
    )
    parser.add_argument(
        "--yaml",
        default=str(root / "backend" / "benchmark" / "datasets" / "sglb_07_jurisdiction_routing.yaml"),
    )
    parser.add_argument(
        "--output",
        default=str(root / "backend" / "data" / "benchmarks" / "sglb_07_jurisdiction_routing"),
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
            "note: 0 cases emitted. CommonLII SG case corpus pending; "
            "see #34 for the upstream ingestion plan.",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
